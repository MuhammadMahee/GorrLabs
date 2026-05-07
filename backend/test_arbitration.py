"""
Arbitration combiner tests — validates the 3 scenarios of Week 3.

Run: python -m pytest test_arbitration.py -v

Scenario 1 — Local succeeds:          routing=anything, local finds docs  → local answer, external never called
Scenario 2 — Local fails, local_only:  routing=local_only, fell_back=True  → return empty, sovereign boundary held
Scenario 3 — Local fails, hybrid:      routing=hybrid_allowed, fell_back=True → external fires, labeled external_general
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(coro):
    """Run async coroutine synchronously — no pytest-asyncio needed."""
    return asyncio.get_event_loop().run_until_complete(coro)


@dataclass
class FakeClassification:
    query_type: object = None
    confidence: float = 0.9
    domain: str = "general"

    def __post_init__(self):
        if self.query_type is None:
            from arkive.agents.query_classifier import QueryType
            self.query_type = QueryType.SIMPLE


@dataclass
class FakeUserContext:
    user_id: str = "user-123"
    clearance_level: int = 1
    allowed_collection_ids: list = field(default_factory=list)
    is_admin: bool = False


def _make_fake_request():
    req = MagicMock()
    req.state = MagicMock()
    return req


def _empty_tool():
    """Returns a tool mock that always returns no content."""
    mock = AsyncMock(return_value=MagicMock(
        content="",
        sources=[],
        status=MagicMock(value="error"),
        metadata={},
    ))
    return mock


def _rich_tool(content="Annual leave is 25 days.", sources=None):
    """Returns a tool mock with real content."""
    mock = AsyncMock(return_value=MagicMock(
        content=content,
        sources=sources or ["hr_policy.pdf"],
        status=MagicMock(value="success"),
        metadata={"avg_score": 0.85},
    ))
    return mock


# ── Scenario 1 — Local succeeds ───────────────────────────────────────────────

class TestScenario1LocalSucceeds:

    def test_local_answer_returned_when_tools_succeed(self):
        """When local RAG finds documents, return local answer. External never called."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select, \
             patch("arkive.agents.supervisor._evaluate_sufficiency", new_callable=AsyncMock) as mock_suf:

            mock_tools.return_value = {"search_knowledge_base": _rich_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")
            mock_suf.return_value = (True, None)

            result = run(run_supervisor(
                query="What is our leave policy?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="local_only",
                redacted_query="What is our leave policy?",
            ))

        assert result.fell_back is False
        mock_ext.assert_not_called()

    def test_local_answer_returned_even_when_routing_is_hybrid(self):
        """hybrid_allowed routing — local succeeds anyway, external never fires."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select, \
             patch("arkive.agents.supervisor._evaluate_sufficiency", new_callable=AsyncMock) as mock_suf:

            mock_tools.return_value = {"search_knowledge_base": _rich_tool("NDA clause: 2 years.", ["contracts.pdf"])}
            mock_select.return_value = (["search_knowledge_base"], "")
            mock_suf.return_value = (True, None)

            result = run(run_supervisor(
                query="What is the NDA clause?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="What is the NDA clause?",
            ))

        assert result.fell_back is False
        assert result.metadata.get("answer_source") != "external_general"
        mock_ext.assert_not_called()


# ── Scenario 2 — Local fails, local_only / block / human_review ───────────────

class TestScenario2SovereignBoundary:

    def test_returns_empty_when_local_fails_and_routing_local_only(self):
        """Sensitivity detected → routing=local_only → fell_back=True, external never called."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="What is <PERSON>'s salary?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="local_only",
                redacted_query="What is <PERSON>'s salary?",
            ))

        assert result.fell_back is True
        assert result.answer == ""
        mock_ext.assert_not_called()

    def test_block_routing_holds_boundary(self):
        """routing=block should never call external."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="List all employee SSNs",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="block",
                redacted_query="",
            ))

        assert result.fell_back is True
        mock_ext.assert_not_called()

    def test_human_review_routing_holds_boundary(self):
        """routing=human_review should never call external."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="What did the CEO say about layoffs?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="human_review",
                redacted_query="",
            ))

        assert result.fell_back is True
        mock_ext.assert_not_called()


# ── Scenario 3 — Local fails, hybrid_allowed ─────────────────────────────────

class TestScenario3HybridFallback:

    def test_external_fires_when_local_fails_and_hybrid_allowed(self):
        """Clean query, no internal docs → external answers from general knowledge."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "A P/E ratio (Price-to-Earnings ratio) is a valuation metric..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="What is a P/E ratio?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="What is a P/E ratio?",
            ))

        assert result.fell_back is False
        assert result.metadata.get("answer_source") == "external_general"
        assert result.sources == []
        mock_ext.assert_called_once_with("What is a P/E ratio?")

    def test_external_receives_redacted_query_not_raw(self):
        """External fallback must receive already-redacted query, not the raw original."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "GDPR defines a data processor as..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            run(run_supervisor(
                query="Explain GDPR for our company John Smith",     # raw — has PII
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="Explain GDPR for our company <PERSON>",  # sanitized
            ))

        mock_ext.assert_called_once_with("Explain GDPR for our company <PERSON>")

    def test_fell_back_true_when_external_also_fails(self):
        """If external returns empty, fell_back=True — genuine no-answer."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = ""   # external also empty
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="Explain TLS 1.3",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="Explain TLS 1.3",
            ))

        assert result.fell_back is True
        assert result.answer == ""

    def test_empty_redacted_query_falls_back_to_original_query(self):
        """If redacted_query is empty, external receives original_query as safe fallback."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "REST APIs use HTTP methods..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            run(run_supervisor(
                query="What is a PUT request?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="",          # empty — should use original_query
            ))

        mock_ext.assert_called_once_with("What is a PUT request?")

    def test_answer_source_metadata_is_external_general(self):
        """answer_source=external_general must be set in metadata on external path."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.ANALYTICAL)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select, \
             patch("arkive.agents.supervisor._decompose_query", new_callable=AsyncMock) as mock_decomp:

            mock_ext.return_value = "Machine learning uses statistical models..."
            mock_decomp.return_value = ["What is ML?"]
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="What is machine learning?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="What is machine learning?",
            ))

        assert result.metadata.get("answer_source") == "external_general"
        assert result.fell_back is False


# ── Middleware signature checks (sync) ────────────────────────────────────────

class TestSignatureAndDefaults:

    def test_run_agentic_rag_accepts_routing_param(self):
        import inspect
        from arkive.agents.supervisor import run_agentic_rag
        sig = inspect.signature(run_agentic_rag)
        assert "routing" in sig.parameters
        assert "redacted_query" in sig.parameters

    def test_run_supervisor_accepts_routing_param(self):
        import inspect
        from arkive.agents.supervisor import run_supervisor
        sig = inspect.signature(run_supervisor)
        assert "routing" in sig.parameters
        assert "redacted_query" in sig.parameters

    def test_routing_defaults_to_local_only(self):
        """Default must be local_only — safe by default, never accidentally goes external."""
        import inspect
        from arkive.agents.supervisor import run_supervisor
        sig = inspect.signature(run_supervisor)
        assert sig.parameters["routing"].default == "local_only"

    def test_external_fallback_helper_exists_and_is_callable(self):
        from arkive.agents.supervisor import _call_external_fallback
        assert callable(_call_external_fallback)


# ── Scenario 4 — LOW_QUALITY local result (Option A: no external) ─────────────

class TestScenario4LowQualityOptionA:
    """
    LOW_QUALITY means local retrieved SOMETHING — weak, low-confidence chunks.
    Option A: do NOT call external. Local answer only, even if weak.
    External is purely a fallback for ZERO local coverage.
    """

    def test_low_quality_local_does_not_trigger_external(self):
        """LOW_QUALITY tool result → supervisor still has context → fell_back=False, no external."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType
        from arkive.agents.tools import ToolStatus

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select, \
             patch("arkive.agents.supervisor._evaluate_sufficiency", new_callable=AsyncMock) as mock_suf:

            # LOW_QUALITY but still returns content
            low_quality_tool = AsyncMock(return_value=MagicMock(
                content="Leave policy: partial information found.",
                sources=["hr_doc.pdf"],
                status=MagicMock(value="low_quality"),
                metadata={"avg_score": 0.3},
            ))
            mock_tools.return_value = {"search_knowledge_base": low_quality_tool}
            mock_select.return_value = (["search_knowledge_base"], "")
            mock_suf.return_value = (True, None)

            result = run(run_supervisor(
                query="What is the leave policy?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="What is the leave policy?",
            ))

        # Local had content — external must NOT fire (Option A)
        assert result.fell_back is False
        assert result.metadata.get("answer_source") != "external_general"
        mock_ext.assert_not_called()


# ── Scenario 5 — Multi-tool: first fails, second succeeds ─────────────────────

class TestScenario5MultiTool:

    def test_same_tool_deduplicated_so_external_fires_on_hybrid(self):
        """
        Supervisor deduplicates tool calls by name (called_tools set).
        If search_knowledge_base fails and gets queued again after reformulation,
        it is skipped the second time → fell_back=True → hybrid fires external.
        This is the correct behavior: same tool can't succeed on retry.
        """
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.PROCEDURAL)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "Onboarding general answer from external..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            # Queue same tool twice — second will be skipped by deduplication
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="How does onboarding work?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="How does onboarding work?",
            ))

        # Deduplication means second tool call never fired → fell_back → hybrid fires
        assert result.fell_back is False
        assert result.metadata["answer_source"] == "external_general"
        mock_ext.assert_called_once()

    def test_all_tools_fail_then_external_fires_for_hybrid(self):
        """All tools in queue return empty → fell_back=True → hybrid fires external."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "Merger means combining two companies..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="What is a merger?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="What is a merger?",
            ))

        assert result.fell_back is False
        assert result.metadata["answer_source"] == "external_general"
        mock_ext.assert_called_once()


# ── Scenario 6 — Query type preserved in metadata on external path ────────────

class TestScenario6MetadataIntegrity:

    def _run_with_query_type(self, query_type, extra_patches=None):
        from arkive.agents.supervisor import run_supervisor

        clf = FakeClassification(query_type=query_type)
        patches = [
            patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock),
            patch("arkive.agents.tools.get_tools_for_user"),
            patch("arkive.agents.supervisor.select_initial_tools"),
        ]
        if extra_patches:
            patches.extend(extra_patches)

        with patches[0] as mock_ext, patches[1] as mock_tools, patches[2] as mock_select:
            mock_ext.return_value = "General answer..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="test query",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="test query",
            ))
        return result, mock_ext

    def test_simple_query_type_preserved_in_external_metadata(self):
        from arkive.agents.query_classifier import QueryType
        result, _ = self._run_with_query_type(QueryType.SIMPLE)
        assert result.metadata["query_type"] == "simple"
        assert result.metadata["answer_source"] == "external_general"

    def test_procedural_query_type_preserved_in_external_metadata(self):
        from arkive.agents.query_classifier import QueryType
        result, _ = self._run_with_query_type(QueryType.PROCEDURAL)
        assert result.metadata["query_type"] == "procedural"
        assert result.metadata["answer_source"] == "external_general"

    def test_classification_confidence_preserved_in_external_metadata(self):
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType
        clf = FakeClassification(query_type=QueryType.SIMPLE, confidence=0.77)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "Some answer"
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="test",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="test",
            ))

        assert result.metadata["confidence"] == 0.77

    def test_external_answer_has_empty_sources(self):
        """External general knowledge answers must have no internal document sources."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "TLS 1.3 uses ECDHE for key exchange..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="Explain TLS 1.3",
                classification=FakeClassification(query_type=QueryType.SIMPLE),
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="Explain TLS 1.3",
            ))

        assert result.sources == [], "External answers must not claim internal document sources"


# ── Scenario 7 — Unknown / future routing values hold boundary ────────────────

class TestScenario7UnknownRouting:

    def test_unknown_routing_value_holds_sovereign_boundary(self):
        """Any routing value that is NOT 'hybrid_allowed' must hold the boundary."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        for unknown_routing in ["restricted", "unknown", "", "HYBRID_ALLOWED", "hybrid"]:
            with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
                 patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
                 patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

                mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
                mock_select.return_value = (["search_knowledge_base"], "")

                result = run(run_supervisor(
                    query="test query",
                    classification=FakeClassification(query_type=QueryType.SIMPLE),
                    user_context=FakeUserContext(),
                    request=_make_fake_request(),
                    routing=unknown_routing,
                    redacted_query="test query",
                ))

            assert result.fell_back is True, \
                f"routing={unknown_routing!r} should hold boundary but external fired"
            mock_ext.assert_not_called()


# ── Scenario 8 — Whitespace-only redacted_query treated as empty ──────────────

class TestScenario8WhitespaceRedactedQuery:

    def test_whitespace_redacted_query_uses_original_query(self):
        """Whitespace-only redacted_query.strip() == '' → external receives original_query."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "REST answer..."
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            run(run_supervisor(
                query="What is REST?",
                classification=FakeClassification(query_type=QueryType.SIMPLE),
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="   ",   # whitespace only
            ))

        mock_ext.assert_called_once_with("What is REST?")


# ── Scenario 9 — _call_external_fallback prompt safety ───────────────────────

class TestScenario9ExternalFallbackPrompt:

    def test_external_fallback_returns_empty_on_llm_failure(self):
        """If bedrock_llm_call raises, _call_external_fallback returns '' — never raises."""
        from arkive.agents.supervisor import _call_external_fallback

        with patch("arkive.agents.supervisor.bedrock_llm_call", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("Bedrock unreachable")
            result = run(_call_external_fallback("What is REST?"))

        assert result == ""

    def test_external_fallback_returns_empty_on_empty_llm_response(self):
        """If bedrock returns empty string, _call_external_fallback returns ''."""
        from arkive.agents.supervisor import _call_external_fallback

        with patch("arkive.agents.supervisor.bedrock_llm_call", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ""
            result = run(_call_external_fallback("What is a REST API?"))

        assert result == ""

    def test_external_fallback_passes_query_to_llm(self):
        """The query text must appear in the prompt sent to the LLM."""
        from arkive.agents.supervisor import _call_external_fallback

        captured_prompt = {}

        async def capture(prompt, **kwargs):
            captured_prompt["p"] = prompt
            return "some answer"

        with patch("arkive.agents.supervisor.bedrock_llm_call", side_effect=capture):
            run(_call_external_fallback("Explain GDPR article 17"))

        assert "Explain GDPR article 17" in captured_prompt["p"]

    def test_external_fallback_prompt_warns_against_internal_facts(self):
        """Prompt must instruct LLM not to invent internal company policies."""
        from arkive.agents.supervisor import _call_external_fallback

        captured_prompt = {}

        async def capture(prompt, **kwargs):
            captured_prompt["p"] = prompt
            return "answer"

        with patch("arkive.agents.supervisor.bedrock_llm_call", side_effect=capture):
            run(_call_external_fallback("What is our leave policy?"))

        prompt_lower = captured_prompt["p"].lower()
        assert "internal" in prompt_lower or "company" in prompt_lower

    def test_external_fallback_preserves_pii_tokens_in_query(self):
        """Redacted PII tokens like <PERSON> must be passed to LLM as-is."""
        from arkive.agents.supervisor import _call_external_fallback

        captured_prompt = {}

        async def capture(prompt, **kwargs):
            captured_prompt["p"] = prompt
            return "GDPR answer"

        with patch("arkive.agents.supervisor.bedrock_llm_call", side_effect=capture):
            run(_call_external_fallback("Explain GDPR for <PERSON> at <ORG>"))

        assert "<PERSON>" in captured_prompt["p"]
        assert "<ORG>" in captured_prompt["p"]


# ── Scenario 10 — run_agentic_rag wrapper passthrough ────────────────────────

class TestScenario10AgenticRagWrapper:

    def test_run_agentic_rag_passes_routing_to_supervisor(self):
        """run_agentic_rag must forward routing= down to run_supervisor."""
        from arkive.agents.supervisor import run_agentic_rag
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor.run_supervisor", new_callable=AsyncMock) as mock_sup:
            mock_sup.return_value = MagicMock(
                fell_back=False, answer="ok", tools_used=[], sources=[], iterations=1,
                metadata={}
            )
            run(run_agentic_rag(
                query="test",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="test redacted",
            ))

        call_kwargs = mock_sup.call_args.kwargs
        assert call_kwargs["routing"] == "hybrid_allowed"
        assert call_kwargs["redacted_query"] == "test redacted"

    def test_run_agentic_rag_returns_fell_back_when_supervisor_raises(self):
        """If run_supervisor raises for any reason, run_agentic_rag returns fell_back=True."""
        from arkive.agents.supervisor import run_agentic_rag
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor.run_supervisor", new_callable=AsyncMock) as mock_sup:
            mock_sup.side_effect = RuntimeError("unexpected crash")

            result = run(run_agentic_rag(
                query="test",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="test",
            ))

        assert result.fell_back is True
        assert result.answer == ""

    def test_run_agentic_rag_default_routing_is_local_only(self):
        """When middleware omits routing, run_agentic_rag must default to local_only."""
        import inspect
        from arkive.agents.supervisor import run_agentic_rag
        sig = inspect.signature(run_agentic_rag)
        assert sig.parameters["routing"].default == "local_only"


# ── Scenario 11 — Local success metadata shape ────────────────────────────────

class TestScenario11LocalSuccessMetadata:

    def test_local_success_has_no_external_general_answer_source(self):
        """Successful local answer must NOT have answer_source=external_general."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select, \
             patch("arkive.agents.supervisor._evaluate_sufficiency", new_callable=AsyncMock) as mock_suf:

            mock_tools.return_value = {"search_knowledge_base": _rich_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")
            mock_suf.return_value = (True, None)

            result = run(run_supervisor(
                query="What is the expense policy?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="What is the expense policy?",
            ))

        assert result.metadata.get("answer_source") != "external_general"
        mock_ext.assert_not_called()

    def test_local_success_tools_used_is_populated(self):
        """tools_used list must be non-empty when local RAG succeeds."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback"), \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select, \
             patch("arkive.agents.supervisor._evaluate_sufficiency", new_callable=AsyncMock) as mock_suf:

            mock_tools.return_value = {"search_knowledge_base": _rich_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")
            mock_suf.return_value = (True, None)

            result = run(run_supervisor(
                query="What is the IT security policy?",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="local_only",
                redacted_query="What is the IT security policy?",
            ))

        assert result.tools_used != []
        assert "search_knowledge_base" in result.tools_used

    def test_external_answer_tools_used_reflects_failed_attempts(self):
        """Even when external fires, tools_used shows which tools were tried."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        clf = FakeClassification(query_type=QueryType.SIMPLE)

        with patch("arkive.agents.supervisor._call_external_fallback", new_callable=AsyncMock) as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_ext.return_value = "General answer about REST"
            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="Explain REST",
                classification=clf,
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed",
                redacted_query="Explain REST",
            ))

        # Tools were attempted even though they returned nothing
        assert "search_knowledge_base" in result.tools_used


# ── Scenario 12 — Routing case-sensitivity ────────────────────────────────────

class TestScenario12RoutingCaseSensitivity:

    def test_hybrid_allowed_uppercase_does_not_trigger_external(self):
        """'HYBRID_ALLOWED' (wrong case) must NOT fire external — exact match required."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="test",
                classification=FakeClassification(query_type=QueryType.SIMPLE),
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="HYBRID_ALLOWED",
                redacted_query="test",
            ))

        assert result.fell_back is True
        mock_ext.assert_not_called()

    def test_hybrid_allowed_with_trailing_space_does_not_trigger_external(self):
        """'hybrid_allowed ' (trailing space) must NOT fire external."""
        from arkive.agents.supervisor import run_supervisor
        from arkive.agents.query_classifier import QueryType

        with patch("arkive.agents.supervisor._call_external_fallback") as mock_ext, \
             patch("arkive.agents.tools.get_tools_for_user") as mock_tools, \
             patch("arkive.agents.supervisor.select_initial_tools") as mock_select:

            mock_tools.return_value = {"search_knowledge_base": _empty_tool()}
            mock_select.return_value = (["search_knowledge_base"], "")

            result = run(run_supervisor(
                query="test",
                classification=FakeClassification(query_type=QueryType.SIMPLE),
                user_context=FakeUserContext(),
                request=_make_fake_request(),
                routing="hybrid_allowed ",
                redacted_query="test",
            ))

        assert result.fell_back is True
        mock_ext.assert_not_called()
