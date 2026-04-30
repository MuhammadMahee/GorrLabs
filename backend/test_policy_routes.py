"""
Comprehensive policy-framework test suite covering all 4 routes:

  Route A — External model override (high-sensitivity → force local)
  Route B — PII anonymization (<PERSON>, <EMAIL_ADDRESS>, etc.)
  Route C — Block: clearance exceeded or collection denied
  Route D — Human review queue (pending/dedup/approve/reject)

Run from backend/:
    python -m pytest test_policy_routes.py -v

Each test is self-contained: database calls are mocked so no live DB is needed.
"""

import asyncio
import hashlib
import sys
import time
import types
import uuid
from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal DB stub — prevents imports from failing when there is no live DB
# ---------------------------------------------------------------------------
def _stub_db_modules():
    """Inject lightweight stubs for DB-dependent modules if not already loaded."""
    for mod_path in [
        "arkive.internal.db",
        "arkive.models.policy_decisions",
        "arkive.models.usage_policies",
        "arkive.models.user_policies",
    ]:
        if mod_path not in sys.modules:
            sys.modules[mod_path] = types.ModuleType(mod_path)

    # internal.db
    db_mod = sys.modules["arkive.internal.db"]
    if not hasattr(db_mod, "Base"):
        from unittest.mock import MagicMock
        db_mod.Base = MagicMock()
        db_mod.get_db_context = MagicMock()

    # policy_decisions
    pd_mod = sys.modules["arkive.models.policy_decisions"]
    if not hasattr(pd_mod, "PolicyDecisions"):
        pd_mod.PolicyDecisions = MagicMock()
        pd_mod.PolicyDecisionForm = MagicMock()

    # usage_policies / user_policies
    for mod_path in ["arkive.models.usage_policies", "arkive.models.user_policies"]:
        m = sys.modules[mod_path]
        if not hasattr(m, "UsagePolicies"):
            m.UsagePolicies = MagicMock()
        if not hasattr(m, "UserPolicies"):
            m.UserPolicies = MagicMock()


_stub_db_modules()

# ---------------------------------------------------------------------------
# Import engine under test
# ---------------------------------------------------------------------------
from arkive.utils.user_context import UserContext
from arkive.utils.policy_engine import (
    PolicyDecisionResult,
    anonymize_query,
    detect_entities,
    evaluate_request,
)
from arkive.env import LOCAL_FALLBACK_MODEL, LOCAL_ONLY_ABOVE_SENSITIVITY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(
    *,
    clearance: int = 3,
    review_threshold: int = 99,   # no review unless overridden
    allowed_collections: Optional[list] = None,
    is_admin: bool = False,
) -> UserContext:
    return UserContext(
        user_id="test-user",
        email="test@example.com",
        role="admin" if is_admin else "user",
        department=None,
        clearance_level=clearance,
        geo_zone=None,
        usage_policy_id=None,
        allowed_collection_ids=allowed_collections if allowed_collections is not None else [],
        can_export=False,
        can_upload=True,
        requires_review_above_clearance=review_threshold,
        is_admin=is_admin,
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mock_audit(inserted_id=None):
    """Returns a mock PolicyDecisions.insert_policy_decision that returns a fake row."""
    fake = MagicMock()
    fake.id = inserted_id or uuid.uuid4()
    mock = MagicMock(return_value=fake)
    return mock


# Always stub llm_classify to return (0, None) so we get deterministic results
# unless a specific test patches it to something else.
_LLM_PATCH = "arkive.utils.policy_engine.llm_classify"
_AUDIT_PATCH = "arkive.models.policy_decisions.PolicyDecisions.insert_policy_decision"
_PR_PATCH_MODULE = "arkive.models.pending_reviews"


# ===========================================================================
#  ROUTE B — PII anonymization
# ===========================================================================

class TestRouteB_Anonymization:
    """
    Route B: queries that contain PII are anonymized (not blocked) so
    they can proceed safely. Raw PII is never forwarded to the LLM.
    """

    def test_person_name_replaced(self):
        """A full name triggers PERSON detection and is replaced with <PERSON>."""
        query = "What are John Smith's leave days?"
        entities = detect_entities(query)
        redacted = anonymize_query(query, entities)
        print(f"\n[B1] original : {query!r}")
        print(f"     redacted : {redacted!r}")
        print(f"     entities : {[e.entity_type for e in entities]}")
        assert "<PERSON>" in redacted, f"Expected <PERSON> in: {redacted!r}"
        assert "John Smith" not in redacted, "Raw name must not appear in redacted query"

    def test_email_replaced(self):
        """An email address triggers EMAIL_ADDRESS and is replaced with <EMAIL_ADDRESS>."""
        query = "Send the report to jane.doe@example.com please"
        entities = detect_entities(query)
        redacted = anonymize_query(query, entities)
        print(f"\n[B2] original : {query!r}")
        print(f"     redacted : {redacted!r}")
        assert "<EMAIL_ADDRESS>" in redacted
        assert "jane.doe@example.com" not in redacted

    def test_ssn_replaced(self):
        """A Social Security Number is replaced with <US_SSN>."""
        query = "Can you look up SSN 123-45-6788 for this employee?"
        entities = detect_entities(query)
        redacted = anonymize_query(query, entities)
        print(f"\n[B3] original : {query!r}")
        print(f"     redacted : {redacted!r}")
        assert "<US_SSN>" in redacted
        assert "123-45-6788" not in redacted

    def test_credit_card_replaced(self):
        """A 16-digit card number with dashes is replaced with <CREDIT_CARD>."""
        query = "Charge card 4111-1111-1111-1111 for the purchase"
        entities = detect_entities(query)
        redacted = anonymize_query(query, entities)
        print(f"\n[B4] original : {query!r}")
        print(f"     redacted : {redacted!r}")
        assert "<CREDIT_CARD>" in redacted
        assert "4111" not in redacted

    def test_date_time_NOT_anonymized(self):
        """DATE_TIME is excluded from _QUERY_ANONYMIZE_ENTITIES — benign tokens like
        'annual' score as DATE_TIME but must not corrupt the query."""
        query = "How many annual leave days do I have?"
        entities = detect_entities(query)
        redacted = anonymize_query(query, entities)
        print(f"\n[B5] original : {query!r}")
        print(f"     redacted : {redacted!r}")
        print(f"     entities : {[e.entity_type for e in entities]}")
        # The query must come through unchanged even if Presidio fires DATE_TIME
        assert "annual leave" in redacted, f"DATE_TIME must not corrupt query: {redacted!r}"

    def test_location_NOT_anonymized(self):
        """LOCATION is excluded to avoid stripping city names from benign queries."""
        query = "Show me the office addresses in New York"
        entities = detect_entities(query)
        redacted = anonymize_query(query, entities)
        print(f"\n[B6] original : {query!r}")
        print(f"     redacted : {redacted!r}")
        assert "New York" in redacted, f"LOCATION must not be stripped: {redacted!r}"

    def test_no_pii_unchanged(self):
        """Queries with no PII pass through unmodified."""
        query = "What is the company refund policy?"
        entities = detect_entities(query)
        redacted = anonymize_query(query, entities)
        print(f"\n[B7] query unchanged: {redacted!r}")
        assert redacted == query

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_evaluate_request_proceeds_with_anonymized_query(self, mock_audit):
        """
        evaluate_request on a query with a name and email:
        - decision = 'proceed' (user has clearance=3, sensitivity=2)
        - redacted_query contains <PERSON> / <EMAIL_ADDRESS> tokens
        - permitted = True
        """
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "What benefits does Alice Johnson at alice@corp.com qualify for?"
        ctx = _user(clearance=3)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result: PolicyDecisionResult = _run(evaluate_request(ctx, query))
        print(f"\n[B8] decision   : {result.decision}")
        print(f"     sensitivity: {result.sensitivity_level}")
        print(f"     redacted   : {result.redacted_query!r}")
        assert result.permitted
        assert result.decision == "proceed"
        assert "<PERSON>" in result.redacted_query or "<EMAIL_ADDRESS>" in result.redacted_query


# ===========================================================================
#  ROUTE C — Block (clearance exceeded / collection denied)
# ===========================================================================

class TestRouteC_Block:
    """
    Route C: queries are blocked when:
      (a) sensitivity_level > user's clearance_level, or
      (b) the requested collection is not in the user's allowed list.
    Exception: accessing a shared (pre-redacted) KB bypasses the clearance block.
    """

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_clearance_exceeded_blocked(self, mock_audit):
        """SSN query (level 3) by a clearance-1 user → block."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Employee SSN is 987-65-4320 for tax filing"
        ctx = _user(clearance=1)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query))
        print(f"\n[C1] decision    : {result.decision}")
        print(f"     sensitivity : {result.sensitivity_level}")
        assert result.decision == "block"
        assert not result.permitted
        assert result.sensitivity_level == 3

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_clearance_matched_proceeds(self, mock_audit):
        """SSN query (level 3) by a clearance-3 user → proceed."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Employee SSN is 987-65-4321 for tax filing"
        ctx = _user(clearance=3)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query))
        print(f"\n[C2] decision    : {result.decision}")
        assert result.decision == "proceed"
        assert result.permitted

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_shared_kb_bypass_clearance(self, mock_audit):
        """
        Clearance-0 user querying a shared (pre-redacted) KB with a level-2 query.
        accessing_shared_kb=True triggers the bypass — decision must be 'proceed'.
        """
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Contact me at bob@example.com about the contract"
        ctx = _user(clearance=0)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query, accessing_shared_kb=True))
        print(f"\n[C3] decision    : {result.decision}")
        print(f"     reason      : {result.reason}")
        assert result.permitted
        # block-from-clearance is the relevant case; block-from-collection is separate
        assert "shared" in result.reason.lower() or result.decision == "proceed"

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_collection_denied(self, mock_audit):
        """User is restricted to collection A but requests collection B → block."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Show me the confidential project files"
        ctx = _user(clearance=3, allowed_collections=["collection-A"])
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(
                evaluate_request(ctx, query, collection_ids=["collection-B"])
            )
        print(f"\n[C4] decision    : {result.decision}")
        print(f"     reason      : {result.reason}")
        assert result.decision == "block"
        assert "collection" in result.reason.lower()

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_collection_allowed(self, mock_audit):
        """User requests a collection they're allowed into → no block from collection rule."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Show me project files"
        ctx = _user(clearance=3, allowed_collections=["collection-A", "collection-B"])
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(
                evaluate_request(ctx, query, collection_ids=["collection-A"])
            )
        print(f"\n[C5] decision    : {result.decision}")
        assert result.decision == "proceed"
        assert result.permitted

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_admin_bypasses_clearance(self, mock_audit):
        """Admin users bypass all clearance and collection rules."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Show SSN 123-45-6787 for all employees"
        ctx = _user(clearance=0, is_admin=True)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query))
        print(f"\n[C6] admin bypass → decision: {result.decision}")
        assert result.decision == "proceed"
        assert result.permitted


# ===========================================================================
#  ROUTE D — Human review queue
# ===========================================================================

class TestRouteD_PendingReview:
    """
    Route D: flagged queries (sensitivity >= review_threshold) are held in
    the pending_reviews table rather than blocked, returning decision='pending'.
    Admin approval unlocks the hash for 24h.
    """

    def _make_pending_reviews_mock(
        self,
        *,
        is_approved: bool = False,
        has_pending: bool = False,
        inserted_id: Optional[uuid.UUID] = None,
    ):
        """Build a mock PendingReviews singleton with controllable return values."""
        pr_mock = MagicMock()
        pr_mock.is_approved.return_value = is_approved
        pr_mock.has_pending.return_value = has_pending
        fake_review = MagicMock()
        fake_review.id = inserted_id or uuid.uuid4()
        pr_mock.insert.return_value = fake_review
        return pr_mock

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_flag_creates_pending_review(self, mock_audit):
        """
        A flagged query (sensitivity=2, review_threshold=2) by a non-admin
        creates a pending_reviews row and returns decision='pending'.
        """
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        review_id = uuid.uuid4()
        pr_mock = self._make_pending_reviews_mock(
            is_approved=False, has_pending=False, inserted_id=review_id
        )

        query = "What are the SSN details of all employees?"
        ctx = _user(clearance=3, review_threshold=2)

        with patch(_LLM_PATCH, new=AsyncMock(return_value=(2, "Sensitive intent detected"))):
            with patch(f"{_PR_PATCH_MODULE}.PendingReviews", pr_mock):
                result = _run(evaluate_request(ctx, query))

        print(f"\n[D1] decision         : {result.decision}")
        print(f"     pending_review_id : {result.pending_review_id}")
        assert result.decision == "pending"
        assert not result.permitted
        assert result.pending_review_id == str(review_id)
        pr_mock.insert.assert_called_once()

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_duplicate_flag_no_new_insert(self, mock_audit):
        """
        If there's already an open pending review for the same query hash,
        no second row is inserted — just decision='pending' silently.
        """
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        pr_mock = self._make_pending_reviews_mock(
            is_approved=False, has_pending=True  # already has a pending row
        )

        query = "What are the SSN details of all employees?"
        ctx = _user(clearance=3, review_threshold=2)

        with patch(_LLM_PATCH, new=AsyncMock(return_value=(2, "Sensitive intent detected"))):
            with patch(f"{_PR_PATCH_MODULE}.PendingReviews", pr_mock):
                result = _run(evaluate_request(ctx, query))

        print(f"\n[D2] decision  : {result.decision}")
        print(f"     insert called: {pr_mock.insert.called}")
        assert result.decision == "pending"
        assert not result.permitted
        pr_mock.insert.assert_not_called()  # no duplicate insert

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_approved_hash_proceeds(self, mock_audit):
        """
        If the same query hash was approved within 24h, the request proceeds
        without creating a new review row. Reason includes '[previously approved]'.
        """
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        pr_mock = self._make_pending_reviews_mock(
            is_approved=True  # hash is approved
        )

        query = "What are the SSN details of all employees?"
        ctx = _user(clearance=3, review_threshold=2)

        with patch(_LLM_PATCH, new=AsyncMock(return_value=(2, "Sensitive intent detected"))):
            with patch(f"{_PR_PATCH_MODULE}.PendingReviews", pr_mock):
                result = _run(evaluate_request(ctx, query))

        print(f"\n[D3] decision : {result.decision}")
        print(f"     reason   : {result.reason}")
        assert result.decision == "proceed"
        assert result.permitted
        assert "previously approved" in result.reason
        pr_mock.insert.assert_not_called()

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_admin_never_pending(self, mock_audit):
        """Admin queries always proceed regardless of sensitivity or review threshold."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        pr_mock = self._make_pending_reviews_mock(is_approved=False, has_pending=False)

        query = "Show me all employee SSNs and credit card data"
        ctx = _user(clearance=0, review_threshold=1, is_admin=True)

        with patch(_LLM_PATCH, new=AsyncMock(return_value=(3, "Highly sensitive"))):
            with patch(f"{_PR_PATCH_MODULE}.PendingReviews", pr_mock):
                result = _run(evaluate_request(ctx, query))

        print(f"\n[D4] admin → decision: {result.decision}")
        assert result.decision == "proceed"
        assert result.permitted
        pr_mock.insert.assert_not_called()

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_review_queue_failure_falls_back_to_block(self, mock_audit):
        """
        If the pending_reviews insert throws, the engine falls back to
        decision='block' (safe default — never silently proceed on error).
        """
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        pr_mock = MagicMock()
        pr_mock.is_approved.return_value = False
        pr_mock.has_pending.side_effect = RuntimeError("DB connection lost")

        query = "What are all employee SSNs?"
        ctx = _user(clearance=3, review_threshold=2)

        with patch(_LLM_PATCH, new=AsyncMock(return_value=(2, "Sensitive intent"))):
            with patch(f"{_PR_PATCH_MODULE}.PendingReviews", pr_mock):
                result = _run(evaluate_request(ctx, query))

        print(f"\n[D5] DB failure → decision: {result.decision}")
        assert result.decision == "block"
        assert not result.permitted


# ===========================================================================
#  ROUTE A — External model override
# ===========================================================================

class TestRouteA_ModelOverride:
    """
    Route A logic lives in middleware.py but the rules are:
      - sensitivity_level >= LOCAL_ONLY_ABOVE_SENSITIVITY  (default 3)
      - selected model NOT in app.state.OLLAMA_MODELS
      → override form_data['model'] to LOCAL_FALLBACK_MODEL

    We test the decision logic directly, mirroring what middleware.py does,
    so this remains fast without spinning up the full ASGI stack.
    """

    def _should_override(self, selected_model: str, sensitivity: int, ollama_models: dict) -> bool:
        """Mirrors the Route A condition in middleware.py."""
        return (
            sensitivity >= LOCAL_ONLY_ABOVE_SENSITIVITY
            and bool(selected_model)
            and selected_model not in ollama_models
        )

    def _apply_override(self, form_data: dict, sensitivity: int, ollama_models: dict) -> dict:
        """Applies the Route A override to form_data, returning updated form_data."""
        selected = form_data.get("model", "")
        if self._should_override(selected, sensitivity, ollama_models):
            form_data = dict(form_data)
            form_data["model"] = LOCAL_FALLBACK_MODEL
        return form_data

    def test_external_model_high_sensitivity_overridden(self):
        """
        gpt-4o is not in OLLAMA_MODELS + sensitivity=3 → model overridden to LOCAL_FALLBACK_MODEL.
        """
        form_data = {"model": "gpt-4o"}
        ollama_models = {"qwen2.5:7b": {}, "llama3.2:latest": {}}
        result = self._apply_override(form_data, sensitivity=3, ollama_models=ollama_models)
        print(f"\n[A1] gpt-4o + sensitivity=3 → model={result['model']!r}")
        assert result["model"] == LOCAL_FALLBACK_MODEL
        assert result["model"] != "gpt-4o"

    def test_external_model_low_sensitivity_not_overridden(self):
        """
        gpt-4o with sensitivity=1 (below threshold=3) → model unchanged.
        """
        form_data = {"model": "gpt-4o"}
        ollama_models = {"qwen2.5:7b": {}}
        result = self._apply_override(form_data, sensitivity=1, ollama_models=ollama_models)
        print(f"\n[A2] gpt-4o + sensitivity=1 → model={result['model']!r}")
        assert result["model"] == "gpt-4o"

    def test_local_model_high_sensitivity_not_overridden(self):
        """
        qwen2.5:7b is already in OLLAMA_MODELS → no override even at sensitivity=3.
        """
        form_data = {"model": "qwen2.5:7b"}
        ollama_models = {"qwen2.5:7b": {}}
        result = self._apply_override(form_data, sensitivity=3, ollama_models=ollama_models)
        print(f"\n[A3] qwen2.5:7b local + sensitivity=3 → model={result['model']!r}")
        assert result["model"] == "qwen2.5:7b"

    def test_gpt_oss_treated_as_local_no_override(self):
        """
        gpt-oss:120b-cloud served via Ollama is in OLLAMA_MODELS →
        treated as local, not overridden.
        """
        form_data = {"model": "gpt-oss:120b-cloud"}
        ollama_models = {"gpt-oss:120b-cloud": {}, "qwen2.5:7b": {}}
        result = self._apply_override(form_data, sensitivity=3, ollama_models=ollama_models)
        print(f"\n[A4] gpt-oss local + sensitivity=3 → model={result['model']!r}")
        assert result["model"] == "gpt-oss:120b-cloud"

    def test_threshold_boundary_exactly_at_threshold(self):
        """sensitivity == LOCAL_ONLY_ABOVE_SENSITIVITY (=3) must trigger the override."""
        form_data = {"model": "claude-3-opus"}
        ollama_models = {}
        result = self._apply_override(
            form_data,
            sensitivity=LOCAL_ONLY_ABOVE_SENSITIVITY,
            ollama_models=ollama_models,
        )
        print(f"\n[A5] sensitivity={LOCAL_ONLY_ABOVE_SENSITIVITY} (boundary) → model={result['model']!r}")
        assert result["model"] == LOCAL_FALLBACK_MODEL

    def test_threshold_one_below_no_override(self):
        """sensitivity == LOCAL_ONLY_ABOVE_SENSITIVITY - 1 must NOT trigger the override."""
        form_data = {"model": "claude-3-opus"}
        ollama_models = {}
        result = self._apply_override(
            form_data,
            sensitivity=LOCAL_ONLY_ABOVE_SENSITIVITY - 1,
            ollama_models=ollama_models,
        )
        print(f"\n[A6] sensitivity={LOCAL_ONLY_ABOVE_SENSITIVITY - 1} (just below) → model={result['model']!r}")
        assert result["model"] == "claude-3-opus"

    def test_empty_model_name_no_override(self):
        """Empty model string means none selected — no override should happen."""
        form_data = {"model": ""}
        ollama_models = {}
        result = self._apply_override(form_data, sensitivity=3, ollama_models=ollama_models)
        print(f"\n[A7] empty model → model={result['model']!r}")
        assert result["model"] == ""

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_full_evaluate_ssn_query_is_level3(self, mock_audit):
        """
        End-to-end: an SSN query yields sensitivity_level=3, which meets the
        Route A threshold. Confirms the evaluate_request output feeds correctly
        into the Route A check.
        """
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Update SSN 987-65-4322 in the HR system"
        ctx = _user(clearance=3)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query))
        print(f"\n[A8] SSN query → sensitivity={result.sensitivity_level}")
        assert result.sensitivity_level >= LOCAL_ONLY_ABOVE_SENSITIVITY
        assert result.decision == "proceed"  # admin clearance=3 allows it to proceed


# ===========================================================================
#  Integration — All routes in sequence
# ===========================================================================

class TestIntegration:
    """
    Scenario: a non-admin user submits queries that exercise each route in turn.
    """

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_benign_query_proceeds_unmodified(self, mock_audit):
        """No PII, no sensitivity → straight proceed, redacted_query == original."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "What is the company leave policy?"
        ctx = _user(clearance=1)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query))
        print(f"\n[INT1] benign → decision={result.decision}, sensitivity={result.sensitivity_level}")
        assert result.permitted
        assert result.decision == "proceed"
        assert result.sensitivity_level == 0
        assert result.redacted_query == query

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_person_email_combo_sensitivity2(self, mock_audit):
        """PERSON + EMAIL_ADDRESS combo → sensitivity_level=2 (Route B anonymizes, Route C passes for clearance-2 user)."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Contact Alice Johnson at alice.j@company.com about her contract"
        ctx = _user(clearance=2)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query))
        print(f"\n[INT2] PERSON+EMAIL → sensitivity={result.sensitivity_level}, decision={result.decision}")
        print(f"       redacted: {result.redacted_query!r}")
        assert result.sensitivity_level == 2
        assert result.permitted
        assert "<PERSON>" in result.redacted_query or "<EMAIL_ADDRESS>" in result.redacted_query

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_ssn_blocked_for_low_clearance_user(self, mock_audit):
        """SSN query (level 3) by clearance-1 user → block (Route C)."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        query = "Get SSN 987-65-4323 for the payroll run"
        ctx = _user(clearance=1)
        with patch(_LLM_PATCH, new=AsyncMock(return_value=(0, None))):
            result = _run(evaluate_request(ctx, query))
        print(f"\n[INT3] SSN + low clearance → decision={result.decision}")
        assert result.decision == "block"
        assert not result.permitted

    @patch(_AUDIT_PATCH, new_callable=MagicMock)
    def test_flagged_query_becomes_pending(self, mock_audit):
        """Flagged query (LLM level 2, review_threshold=2) → pending (Route D)."""
        mock_audit.return_value = MagicMock(id=uuid.uuid4())
        review_uuid = uuid.uuid4()
        pr_mock = MagicMock()
        pr_mock.is_approved.return_value = False
        pr_mock.has_pending.return_value = False
        fake_review = MagicMock()
        fake_review.id = review_uuid
        pr_mock.insert.return_value = fake_review

        query = "How do I access the classified project documents?"
        ctx = _user(clearance=3, review_threshold=2)

        with patch(_LLM_PATCH, new=AsyncMock(return_value=(2, "Attempting to access restricted info"))):
            with patch(f"{_PR_PATCH_MODULE}.PendingReviews", pr_mock):
                result = _run(evaluate_request(ctx, query))

        print(f"\n[INT4] flagged query → decision={result.decision}, review_id={result.pending_review_id}")
        assert result.decision == "pending"
        assert not result.permitted
        assert result.pending_review_id == str(review_uuid)


# ===========================================================================
#  Entry point (also runnable directly: python test_policy_routes.py)
# ===========================================================================

if __name__ == "__main__":
    import traceback

    tests = [
        # Route B
        ("B1 - PERSON anonymized", TestRouteB_Anonymization().test_person_name_replaced),
        ("B2 - EMAIL anonymized", TestRouteB_Anonymization().test_email_replaced),
        ("B3 - SSN anonymized", TestRouteB_Anonymization().test_ssn_replaced),
        ("B4 - CREDIT_CARD anonymized", TestRouteB_Anonymization().test_credit_card_replaced),
        ("B5 - DATE_TIME not anonymized", TestRouteB_Anonymization().test_date_time_NOT_anonymized),
        ("B6 - LOCATION not anonymized", TestRouteB_Anonymization().test_location_NOT_anonymized),
        ("B7 - no PII unchanged", TestRouteB_Anonymization().test_no_pii_unchanged),
        # Route C
        ("C1 - clearance exceeded → block", lambda: TestRouteC_Block().test_clearance_exceeded_blocked(MagicMock(return_value=MagicMock(id=uuid.uuid4())))),
        ("C2 - clearance ok → proceed", lambda: TestRouteC_Block().test_clearance_matched_proceeds(MagicMock(return_value=MagicMock(id=uuid.uuid4())))),
        ("C3 - shared KB bypass", lambda: TestRouteC_Block().test_shared_kb_bypass_clearance(MagicMock(return_value=MagicMock(id=uuid.uuid4())))),
        ("C4 - collection denied", lambda: TestRouteC_Block().test_collection_denied(MagicMock(return_value=MagicMock(id=uuid.uuid4())))),
        ("C5 - collection allowed", lambda: TestRouteC_Block().test_collection_allowed(MagicMock(return_value=MagicMock(id=uuid.uuid4())))),
        ("C6 - admin bypass", lambda: TestRouteC_Block().test_admin_bypasses_clearance(MagicMock(return_value=MagicMock(id=uuid.uuid4())))),
        # Route A
        ("A1 - external+high → override", TestRouteA_ModelOverride().test_external_model_high_sensitivity_overridden),
        ("A2 - external+low → no override", TestRouteA_ModelOverride().test_external_model_low_sensitivity_not_overridden),
        ("A3 - local model → no override", TestRouteA_ModelOverride().test_local_model_high_sensitivity_not_overridden),
        ("A4 - gpt-oss local → no override", TestRouteA_ModelOverride().test_gpt_oss_treated_as_local_no_override),
        ("A5 - threshold boundary override", TestRouteA_ModelOverride().test_threshold_boundary_exactly_at_threshold),
        ("A6 - just below threshold no override", TestRouteA_ModelOverride().test_threshold_one_below_no_override),
        ("A7 - empty model → no override", TestRouteA_ModelOverride().test_empty_model_name_no_override),
    ]

    passed = failed = 0
    for label, fn in tests:
        try:
            fn()
            print(f"  PASS  {label}")
            passed += 1
        except Exception:
            print(f"  FAIL  {label}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed+failed} tests")
    if failed:
        sys.exit(1)
