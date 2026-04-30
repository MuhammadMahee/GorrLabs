import hashlib
import logging
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import (
    DateRecognizer,
    EmailRecognizer,
    IbanRecognizer,
    IpRecognizer,
    MedicalLicenseRecognizer,
    PhoneRecognizer,
    UrlRecognizer,
    UsBankRecognizer,
    UsLicenseRecognizer,
)

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from arkive.models.policy_decisions import PolicyDecisionForm, PolicyDecisions
from arkive.utils.llm_classifier import llm_classify
from arkive.utils.user_context import UserContext

log = logging.getLogger(__name__)


####################
# Policy engine
#
# Runs on every authenticated request before RAG / LLM invocation.
# Detects PII via Presidio, classifies sensitivity, redacts the query,
# applies clearance + collection rules, and writes an append-only
# audit row to policy_decisions.
####################


def _is_valid_card_format(text: str) -> bool:
    """
    Validates credit card format only (not Luhn).
    Accepts: 16 digits with spaces, dashes, or no separator.
    Rejects: anything that does not match standard card groupings.
    """
    cleaned = re.sub(r'[-\s]', '', text)
    return bool(re.fullmatch(r'\d{16}', cleaned))


class CreditCardRecognizer(PatternRecognizer):
    def validate_result(self, pattern_text):
        return _is_valid_card_format(pattern_text)


def _build_analyzer() -> AnalyzerEngine:
    # Build the analyzer explicitly instead of relying on Presidio's
    # implicit recognizer auto-loader. The auto-loader can discover our
    # local PatternRecognizer subclass and try to instantiate it without
    # the required constructor args during first request initialization.
    nlp_engine = NlpEngineProvider().create_engine()
    registry = RecognizerRegistry(supported_languages=['en'])
    registry.add_nlp_recognizer(nlp_engine=nlp_engine)

    # Register the English recognizers Arkive uses in policy checks.
    for recognizer in [
        EmailRecognizer(),
        PhoneRecognizer(),
        UrlRecognizer(),
        IbanRecognizer(),
        IpRecognizer(),
        DateRecognizer(),
        UsBankRecognizer(),
        UsLicenseRecognizer(),
        MedicalLicenseRecognizer(),
    ]:
        registry.add_recognizer(recognizer)

    engine = AnalyzerEngine(
        registry=registry,
        nlp_engine=nlp_engine,
        supported_languages=['en'],
    )

    # Presidio's ML model often scores well-known PII patterns below the
    # 0.7 threshold when they appear without rich surrounding context.
    # Regex recognizers give deterministic confidence; a subclass
    # validator rejects digit runs that pass the regex but aren't valid
    # card groupings.

    engine.registry.add_recognizer(CreditCardRecognizer(
        supported_entity='CREDIT_CARD',
        patterns=[Pattern(
            name='cc_groups',
            regex=r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            score=1.0,
        )],
        context=[
            'card', 'credit card', 'debit card', 'visa',
            'mastercard', 'amex', 'payment', 'charge',
            'billing', 'card number',
        ],
    ))

    engine.registry.add_recognizer(PatternRecognizer(
        supported_entity='US_SSN',
        patterns=[Pattern(
            name='ssn_dashes',
            regex=r'\b\d{3}-\d{2}-\d{4}\b',
            score=1.0,
        )],
        deny_list=[
            '123-45-6789', '000-00-0000', '999-99-9999',
            '111-11-1111', '222-22-2222', '333-33-3333',
            '444-44-4444', '555-55-5555', '666-66-6666',
            '777-77-7777', '888-88-8888',
        ],
        context=[
            'ssn', 'social security', 'social', 'patient',
            'taxpayer', 'identification', 'employee id',
        ],
    ))

    # Numeric-only passports score below threshold on their own; context
    # words ("passport", "travel doc") boost them above 0.7 via Presidio's
    # context enhancer. Alpha-prefixed strings are more distinctive and
    # carry slightly higher base confidence.
    # Pakistani IBAN — PK + 2 check digits + 4 alpha bank code + 8-20 alphanumeric account.
    # Presidio's built-in IbanRecognizer doesn't cover PK format.
    engine.registry.add_recognizer(PatternRecognizer(
        supported_entity='IBAN_CODE',
        patterns=[Pattern(
            name='pk_iban',
            regex=r'\bPK\d{2}[A-Z]{4}[0-9A-Z]{8,20}\b',
            score=1.0,
        )],
        context=['bank', 'account', 'iban', 'transfer', 'payment'],
    ))

    engine.registry.add_recognizer(PatternRecognizer(
        supported_entity='US_PASSPORT',
        patterns=[
            Pattern(
                name='passport_numeric',
                regex=r'\b\d{9}\b',
                score=0.4,
            ),
            Pattern(
                name='passport_alpha_prefix',
                regex=r'\b[A-Z]{1,2}\d{7,8}\b',
                score=0.6,
            ),
        ],
        context=[
            'passport', 'passport number', 'travel document',
            'nationality', 'border', 'immigration',
        ],
    ))

    return engine


# Lazy-initialized on first use.
# Module-level instantiation causes Presidio registry
# state issues on uvicorn hot reload.
_analyzer: AnalyzerEngine | None = None
_anonymizer: AnonymizerEngine | None = None


def _get_analyzer() -> AnalyzerEngine:
    global _analyzer
    if _analyzer is None:
        _analyzer = _build_analyzer()
    return _analyzer


def _get_anonymizer() -> AnonymizerEngine:
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = AnonymizerEngine()
    return _anonymizer


_SUPPORTED_ENTITIES = [
    'PERSON',
    'EMAIL_ADDRESS',
    'PHONE_NUMBER',
    'CREDIT_CARD',
    'IBAN_CODE',
    'US_SSN',
    'US_BANK_NUMBER',
    'IP_ADDRESS',
    'URL',
    'LOCATION',
    'DATE_TIME',
    'NRP',
    'MEDICAL_LICENSE',
    'US_DRIVER_LICENSE',
    'US_PASSPORT',
]

_SCORE_THRESHOLD = 0.7

# Replace operator per entity type: <PERSON>, <EMAIL_ADDRESS>, etc.
# Unknown types fall through to DEFAULT → <REDACTED>.
_ANONYMIZER_OPERATORS: Dict[str, OperatorConfig] = {
    entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
    for entity in _SUPPORTED_ENTITIES
}
_ANONYMIZER_OPERATORS["DEFAULT"] = OperatorConfig("replace", {"new_value": "<REDACTED>"})

# Entity types that are replaced in queries.
# Deliberately excludes DATE_TIME, LOCATION, NRP — these fire on benign
# tokens ("annual", "daily", city names in normal context) and would
# corrupt query semantics without adding meaningful privacy protection.
# They still influence sensitivity_level; they just aren't substituted.
_QUERY_ANONYMIZE_ENTITIES = {
    'PERSON',
    'EMAIL_ADDRESS',
    'PHONE_NUMBER',
    'CREDIT_CARD',
    'IBAN_CODE',
    'US_SSN',
    'US_BANK_NUMBER',
    'IP_ADDRESS',
    'URL',
    'MEDICAL_LICENSE',
    'US_DRIVER_LICENSE',
    'US_PASSPORT',
}

_LEVEL_3_TYPES = {
    'US_SSN',
    'CREDIT_CARD',
    'IBAN_CODE',
    'US_BANK_NUMBER',
    'MEDICAL_LICENSE',
    'US_PASSPORT',
    'US_DRIVER_LICENSE',
}

_LEVEL_1_TYPES = {'PERSON', 'LOCATION', 'IP_ADDRESS', 'NRP'}

# Narrow entity set used when scanning LLM responses.
# Deliberately excludes PERSON, LOCATION, DATE_TIME, NRP —
# those trigger false positives on conversational language
# ("today", "you", "I", etc.).
_RESPONSE_SCAN_ENTITIES = [
    'EMAIL_ADDRESS',
    'PHONE_NUMBER',
    'CREDIT_CARD',
    'IBAN_CODE',
    'US_SSN',
    'US_BANK_NUMBER',
    'MEDICAL_LICENSE',
    'US_PASSPORT',
    'US_DRIVER_LICENSE',
]

_EXTRACT_ENTITY_TYPES = {
    'US_SSN', 'CREDIT_CARD', 'IBAN_CODE', 'US_BANK_NUMBER',
    'US_PASSPORT', 'US_DRIVER_LICENSE', 'MEDICAL_LICENSE',
    'EMAIL_ADDRESS', 'PHONE_NUMBER',
}


####################
# Ingest-time entity detection
####################


class RedactedEntityType(str, Enum):
    """Internal PII classification enum. Never leak Presidio labels outside this module."""
    NATIONAL_ID       = "NATIONAL_ID"       # SSN, NIN, Aadhaar, CNIC, numeric passport
    BANK_ACCOUNT      = "BANK_ACCOUNT"      # US bank account, IBAN
    CREDIT_CARD       = "CREDIT_CARD"
    PASSPORT          = "PASSPORT"          # alpha-prefixed passports
    DRIVERS_LICENSE   = "DRIVERS_LICENSE"
    MEDICAL_LICENSE   = "MEDICAL_LICENSE"
    PHONE             = "PHONE"
    SALARY            = "SALARY"            # LLM-detected salary/compensation values
    MEDICAL_CONDITION = "MEDICAL_CONDITION" # LLM-detected diagnoses/illnesses
    CREDENTIAL        = "CREDENTIAL"        # LLM-detected passwords/API keys


# Presidio entity type → internal enum.
_PRESIDIO_TO_INTERNAL: Dict[str, RedactedEntityType] = {
    'US_SSN':            RedactedEntityType.NATIONAL_ID,
    'US_BANK_NUMBER':    RedactedEntityType.BANK_ACCOUNT,
    'IBAN_CODE':         RedactedEntityType.BANK_ACCOUNT,
    'CREDIT_CARD':       RedactedEntityType.CREDIT_CARD,
    'US_PASSPORT':       RedactedEntityType.PASSPORT,
    'US_DRIVER_LICENSE': RedactedEntityType.DRIVERS_LICENSE,
    'MEDICAL_LICENSE':   RedactedEntityType.MEDICAL_LICENSE,
    'PHONE_NUMBER':      RedactedEntityType.PHONE,
}

# Per-type minimum confidence floor applied AFTER Presidio runs.
# Types with aggressive pattern sets (UsLicenseRecognizer) generate
# many low-score false positives on short alphanumeric tokens.
# Setting a higher floor filters noise without disabling the recogniser.
# Zero means no floor (use score_threshold=0.0 for that type).
_INGEST_MIN_CONFIDENCE: Dict[RedactedEntityType, float] = {
    RedactedEntityType.DRIVERS_LICENSE: 0.6,  # UsLicenseRecognizer fires on short tokens
}

# Ordered most-specific → least-specific so the deduplication step
# keeps the tighter pattern when spans overlap.
# (pattern, entity_type, confidence_score)
_REGEX_FALLBACK_PATTERNS: List[tuple] = [
    # International phone: +92-XXX-XXXXXXX, +1 (800) 555-1234, etc.
    (
        re.compile(r'\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}'),
        RedactedEntityType.PHONE,
        0.75,
    ),
    # Ungrouped 13–16 digit runs → credit/debit card
    (
        re.compile(r'\b\d{13,16}\b'),
        RedactedEntityType.CREDIT_CARD,
        0.60,
    ),
    # Bare 9-digit run → SSN without dashes or numeric passport
    (
        re.compile(r'\b\d{9}\b'),
        RedactedEntityType.NATIONAL_ID,
        0.50,
    ),
    # 8–20 digit run → bank account (broadest; intentionally runs last)
    (
        re.compile(r'\b\d{8,20}\b'),
        RedactedEntityType.BANK_ACCOUNT,
        0.40,
    ),
]


# Detection precision note:
# scan_chunk_entities optimises for precision and span stability,
# not maximum recall. Whitespace/separator variants of known PII
# formats (e.g. "487 23 6019") are intentionally not normalised
# before matching. A space-separated SSN will not be detected here.
# This is a conscious tradeoff: normalising would require storing
# derived positions that may not align with the original text,
# risking incorrect redaction boundaries. If a variant slips through,
# the stream-time redaction and post-stream scan_response() act as
# safety nets. If recall must be increased, add explicit recognisers
# for each variant in _REGEX_FALLBACK_PATTERNS — do not add
# pre-normalisation to this function.
def scan_chunk_entities(text: str) -> List[Dict]:
    """
    Detection-only pass over a document chunk.

    Two sources:
      Pass 1 — Presidio (score_threshold=0.0, all detections captured)
      Pass 2 — Regex fallback (catches bare digit runs Presidio misses)

    Spans are deduplicated: when two detections overlap the one with
    higher confidence is kept; Presidio beats regex on equal confidence.
    Final list is sorted by start index — output is fully deterministic.

    Does NOT perform redaction. Callers must pass the result to
    redact_chunk() to produce the stored text.

    Returns list of dicts:
        {
            "type":       RedactedEntityType,
            "start":      int,   # inclusive character offset
            "end":        int,   # exclusive character offset
            "confidence": float,
            "source":     "presidio" | "regex"
        }
    """
    if not text or not text.strip():
        return []

    detections: List[Dict] = []

    # ── Pass 1: Presidio ──────────────────────────────────────────────────
    try:
        results = _get_analyzer().analyze(
            text=text,
            language='en',
            entities=list(_PRESIDIO_TO_INTERNAL.keys()),
            score_threshold=0.0,  # no threshold — capture everything, dedup below
        )
        for r in results:
            internal = _PRESIDIO_TO_INTERNAL.get(r.entity_type)
            if internal is None:
                continue
            confidence = float(r.score)
            min_conf = _INGEST_MIN_CONFIDENCE.get(internal, 0.0)
            if confidence < min_conf:
                continue
            detections.append({
                'type':       internal,
                'start':      r.start,
                'end':        r.end,
                'confidence': confidence,
                'source':     'presidio',
            })
    except Exception as _e:
        log.warning(f'[scan_chunk_entities] presidio pass failed: {_e}')

    # ── Pass 2: Regex fallback ────────────────────────────────────────────
    for pattern, entity_type, confidence in _REGEX_FALLBACK_PATTERNS:
        for m in pattern.finditer(text):
            detections.append({
                'type':       entity_type,
                'start':      m.start(),
                'end':        m.end(),
                'confidence': confidence,
                'source':     'regex',
            })

    # ── Deduplication ─────────────────────────────────────────────────────
    # Greedy keep in confidence-desc order. On equal confidence, presidio
    # beats regex. Tie-break by start index for full determinism.
    detections.sort(key=lambda d: (
        -d['confidence'],
        0 if d['source'] == 'presidio' else 1,
        d['start'],
    ))

    kept: List[Dict] = []
    for d in detections:
        if not any(
            not (d['end'] <= k['start'] or d['start'] >= k['end'])
            for k in kept
        ):
            kept.append(d)

    kept.sort(key=lambda d: d['start'])
    return kept


_HEURISTIC_KEYWORDS: List[str] = [
    'ssn', 'social security', 'account', 'bank', 'card',
    'phone', 'passport', 'license',
]

# Matches digit runs that may contain spaces or dashes (spaced SSNs,
# formatted account numbers, etc.). Minimum 8 chars, starts and ends
# with a digit.
_PROXIMITY_RE = re.compile(r'\d[\d\s\-]{6,}\d')

# Tight consecutive-digit run used for the loose fallback pass.
_LOOSE_NUMERIC_RE = re.compile(r'\d{8,}')

_SOURCE_PRIORITY: Dict[str, int] = {
    'presidio':  0,
    'regex':     1,
    'heuristic': 2,
}


def _digit_count(s: str) -> int:
    return sum(c.isdigit() for c in s)


def _classify_by_digits(n: int) -> 'Optional[RedactedEntityType]':
    if n == 9:
        return RedactedEntityType.NATIONAL_ID
    if 13 <= n <= 16:
        return RedactedEntityType.CREDIT_CARD
    if 8 <= n <= 20:
        return RedactedEntityType.BANK_ACCOUNT
    return None


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end <= b_start or a_start >= b_end)


def enhance_entities_with_context(text: str, entities: List[Dict]) -> List[Dict]:
    """
    Heuristic layer that runs AFTER scan_chunk_entities().

    Adds detections for PII variants missed by Presidio and regex:
      Step 1 — Keyword proximity: search ±50 chars around known PII
               keywords for formatted numeric strings (spaces/dashes OK).
      Step 2 — Loose numeric fallback: catch bare 8+ digit runs not
               already covered by any prior detection.
      Step 3 — Merge all sources, deduplicate by highest-confidence
               greedy keep, sort by start index.

    Contracts:
    - Never modifies spans in the incoming entity list.
    - All returned spans are character offsets into the original text.
    - No text normalisation at any stage.
    - Heuristic detections are never dropped solely for low confidence
      (fail-closed: over-detection is preferred to under-detection).
    - Output is fully deterministic.
    """
    if not text or not text.strip():
        return list(entities)

    heuristic: List[Dict] = []
    text_lower = text.lower()

    # ── Step 1: Keyword proximity detection ──────────────────────────────
    for keyword in _HEURISTIC_KEYWORDS:
        search_pos = 0
        while True:
            kw_idx = text_lower.find(keyword, search_pos)
            if kw_idx == -1:
                break

            window_start = max(0, kw_idx - 50)
            window_end   = min(len(text), kw_idx + len(keyword) + 50)

            for m in _PROXIMITY_RE.finditer(text):
                # Span must fall entirely within the keyword window so
                # that positions always refer to the original text.
                if m.start() >= window_start and m.end() <= window_end:
                    n = _digit_count(m.group())
                    entity_type = _classify_by_digits(n)
                    if entity_type is not None:
                        heuristic.append({
                            'type':       entity_type,
                            'start':      m.start(),
                            'end':        m.end(),
                            'confidence': 0.4,
                            'source':     'heuristic',
                        })

            search_pos = kw_idx + 1

    # ── Step 2: Loose numeric fallback ───────────────────────────────────
    # Combines the original entities and the heuristic hits from Step 1
    # so we don't re-flag spans that are already covered.
    covered: List[Dict] = list(entities) + heuristic
    for m in _LOOSE_NUMERIC_RE.finditer(text):
        already_covered = any(
            _overlaps(m.start(), m.end(), e['start'], e['end'])
            for e in covered
        )
        if already_covered:
            continue
        n = _digit_count(m.group())
        entity_type = _classify_by_digits(n)
        if entity_type is not None:
            heuristic.append({
                'type':       entity_type,
                'start':      m.start(),
                'end':        m.end(),
                'confidence': 0.3,
                'source':     'heuristic',
            })

    # ── Step 3: Merge + deduplicate ───────────────────────────────────────
    combined = list(entities) + heuristic

    # Sort: highest confidence first; on tie, prefer earlier source
    # (presidio > regex > heuristic); on further tie, earlier span.
    combined.sort(key=lambda d: (
        -d['confidence'],
        _SOURCE_PRIORITY.get(d['source'], 99),
        d['start'],
    ))

    kept: List[Dict] = []
    for d in combined:
        if not any(_overlaps(d['start'], d['end'], k['start'], k['end']) for k in kept):
            kept.append(d)

    kept.sort(key=lambda d: d['start'])
    return kept


def redact_chunk(text: str, entities: List[Dict]) -> str:
    """
    Applies structured redaction to a document chunk using the entity
    list produced by scan_chunk_entities().

    Contract:
    - Entities must already be deduplicated and sorted by start index
      (scan_chunk_entities guarantees this).
    - Spans are used as-is against the original text — no normalisation.
    - Overlapping or out-of-order spans are skipped defensively; they
      should never appear given the contract above.
    - Token format: [NATIONAL_ID], [BANK_ACCOUNT], [CREDIT_CARD], etc.
      The full enum value is used so downstream code can parse type from token.
    - Output is deterministic: same text + same entities → same result.

    Does NOT modify the entity list. Never raises.
    """
    if not text or not entities:
        return text

    parts: List[str] = []
    cursor = 0

    for entity in entities:
        start = entity['start']
        end = entity['end']
        entity_type = entity['type']

        # Defensive: skip spans that are out-of-order or overlap the cursor.
        # Correctly produced entity lists never trigger this.
        if start < cursor or end <= start:
            continue

        parts.append(text[cursor:start])
        # Use enum value so token is human-readable and type-parseable.
        token = entity_type.value if isinstance(entity_type, RedactedEntityType) else str(entity_type)
        parts.append(f'[{token}]')
        cursor = end

    parts.append(text[cursor:])
    return ''.join(parts)


####################
# Result types
####################


@dataclass
class DetectedEntity:
    entity_type: str
    start: int
    end: int
    score: float
    text: str


@dataclass
class PolicyDecisionResult:
    permitted: bool
    decision: str  # 'proceed', 'block', 'flag', 'pending'
    reason: str
    detected_entities: list[DetectedEntity]
    redacted_query: str
    audit_required: bool
    sensitivity_level: int
    audit_id: str | None = None
    pending_review_id: str | None = None  # set when decision == 'pending'


####################
# Detection + redaction
####################


def detect_entities(
    text: str,
    entities: Optional[list[str]] = None,
) -> list[DetectedEntity]:
    if not text:
        return []

    results = _get_analyzer().analyze(
        text=text,
        language='en',
        entities=entities or _SUPPORTED_ENTITIES,
        score_threshold=_SCORE_THRESHOLD,
    )

    entities = [
        DetectedEntity(
            entity_type=r.entity_type,
            start=r.start,
            end=r.end,
            score=float(r.score),
            text=text[r.start:r.end],
        )
        for r in results
    ]
    entities.sort(key=lambda e: e.start)
    return entities


def extract_sensitive_terms(chunk_text: str) -> set[str]:
    """
    Extracts actual sensitive string values from a document chunk.
    Only runs on chunks from sensitive documents (level >= 1).
    Returns a set of raw string values for exact-match redaction.

    Deliberately narrow entity set — excludes PERSON, LOCATION,
    DATE_TIME, NRP to prevent false positives in response matching.
    Never raises.
    """
    try:
        entities = detect_entities(
            chunk_text,
            entities=list(_EXTRACT_ENTITY_TYPES),
        )
        return {e.text for e in entities if e.text.strip()}
    except Exception:
        return set()


def scan_response(
    response_text: str,
    sensitive_terms: set[str],
) -> str:
    """
    Context-aware three-step response scanner.

    Step 1 — Exact match: redact any known sensitive term that
    appears in the response. These came from actual retrieved
    documents so any appearance is a real leak.

    Step 2 — Presidio Level 3 fallback: run Presidio on the
    response for structurally verifiable types only. Catches
    PII the LLM may have generated that was not in the documents.
    Uses _RESPONSE_SCAN_ENTITIES (narrow set, no false positives
    on conversational language).

    Step 3 — Return redacted text. If nothing was found, return
    original text unchanged.

    Never raises — caller must handle failures.
    """
    if not response_text:
        return response_text

    redacted = response_text
    found_types: list[str] = []

    # Step 1 — exact string match on known sensitive terms
    for term in sensitive_terms:
        if term and term in redacted:
            redacted = redacted.replace(term, '[REDACTED]')
            found_types.append(f'exact:{term[:4]}...')

    # Step 2 — Presidio fallback for Level 3 structural types
    try:
        residual_entities = detect_entities(
            redacted,
            entities=_RESPONSE_SCAN_ENTITIES,
        )
        if residual_entities:
            redacted = redact_text(redacted, residual_entities)
            found_types.extend(
                [e.entity_type for e in residual_entities]
            )
    except Exception as _e:
        log.warning(f'[scan_response] presidio fallback failed: {_e}')

    if found_types:
        log.warning(
            f'[scan_response] redacted from LLM output: {found_types}'
        )
    else:
        log.debug('[scan_response] output clean')

    return redacted


####################
# Query-time masking
####################

# All token types that can appear in stored chunk text.
_TOKEN_RE = re.compile(
    r'\[(NATIONAL_ID|BANK_ACCOUNT|CREDIT_CARD|PASSPORT'
    r'|DRIVERS_LICENSE|MEDICAL_LICENSE|PHONE)\]'
)

# Mask format per entity type using the last-4 hint.
_MASK_FORMATS: Dict[str, str] = {
    'NATIONAL_ID':     'XXX-XX-{last4}',
    'BANK_ACCOUNT':    '****{last4}',
    'CREDIT_CARD':     '**** **** **** {last4}',
    'PHONE':           '***-***-{last4}',
    'PASSPORT':        '******{last4}',
    'DRIVERS_LICENSE': '******{last4}',
    'MEDICAL_LICENSE': '******{last4}',
}


def mask_token(token_type: str, last4: str) -> str:
    """
    Returns the masked display string for a given token type and last-4 hint.
    Never returns raw PII. Unknown types fall back to generic mask.
    """
    fmt = _MASK_FORMATS.get(token_type, '******{last4}')
    return fmt.format(last4=last4)


def apply_query_time_masking(
    redacted_text: str,
    metadata: Dict,
    clearance_level: int,
    reveal_hints: Optional[Dict] = None,
) -> str:
    """
    Presentation-only transform of stored chunk text.

    The vector DB stores only opaque tokens ([NATIONAL_ID], etc.).
    This function controls how those tokens are rendered for the
    requesting user based on clearance level and reveal hints.

    Clearance policy:
      0–1  → tokens stay fully opaque — no change
      2–3  → tokens replaced with partial mask IF a hint is available
             (e.g. XXX-XX-6019, ****1234); otherwise remain opaque.
             Clearance 3 behaves identically to clearance 2 here.
             Raw PII is NEVER returned at any clearance level.
             Full controlled disclosure is a separate future mechanism.

    reveal_hints format:
      {"NATIONAL_ID": ["6019", "1122"], "BANK_ACCOUNT": ["1234"]}
      Each list entry maps 1:1 to token occurrences in left-to-right
      order. Tokens without a matching hint remain opaque.

    Constraints:
      - Never reconstructs raw values from metadata spans.
      - Never fetches external data.
      - Does NOT modify the stored vector DB text.
      - Deterministic: same inputs → same output always.
    """
    if not redacted_text:
        return redacted_text

    # Clearance 0–1: no reveal at all.
    if clearance_level < 2:
        return redacted_text

    # Clearance 2–3: partial reveal where hints are available.
    if not reveal_hints:
        return redacted_text

    # Per-type counters track occurrence index (0-based, left-to-right).
    occurrence_counters: Dict[str, int] = {}

    def _replace(m: re.Match) -> str:
        token_type = m.group(1)
        idx = occurrence_counters.get(token_type, 0)
        occurrence_counters[token_type] = idx + 1

        hints_for_type = reveal_hints.get(token_type, [])
        if idx < len(hints_for_type):
            return mask_token(token_type, hints_for_type[idx])

        # No hint for this occurrence — keep opaque.
        return m.group(0)

    return _TOKEN_RE.sub(_replace, redacted_text)


def anonymize_query(text: str, entities: list[DetectedEntity]) -> str:
    """
    Anonymizes PII in a query using presidio-anonymizer.

    Produces <ENTITY_TYPE> tokens (e.g. <PERSON>, <EMAIL_ADDRESS>) so the
    query can still be semantically meaningful after anonymization. The
    original text is never stored or forwarded downstream once PII is found.

    Only replaces entity types in _QUERY_ANONYMIZE_ENTITIES — DATE_TIME,
    LOCATION, and NRP are excluded to prevent false positives on benign
    tokens ("annual", city names, etc.) from corrupting query semantics.

    Falls back to bracket-redaction via redact_text() on any error.
    """
    if not entities:
        return text
    try:
        analyzer_results = [
            RecognizerResult(
                entity_type=e.entity_type,
                start=e.start,
                end=e.end,
                score=e.score,
            )
            for e in entities
            if e.entity_type in _QUERY_ANONYMIZE_ENTITIES
        ]
        if not analyzer_results:
            return text
        result = _get_anonymizer().anonymize(
            text=text,
            analyzer_results=analyzer_results,
            operators=_ANONYMIZER_OPERATORS,
        )
        return result.text
    except Exception as _e:
        log.warning(f'[anonymize_query] anonymizer failed: {_e} — using bracket redaction')
        return redact_text(text, entities)


def redact_text(text: str, entities: list[DetectedEntity]) -> str:
    if not entities:
        return text

    # Resolve overlaps: walk entities in score-desc order and greedily keep
    # any that don't intersect a higher-scored span we've already accepted.
    by_score = sorted(entities, key=lambda e: e.score, reverse=True)
    kept: list[DetectedEntity] = []
    for e in by_score:
        overlaps = any(not (e.end <= k.start or e.start >= k.end) for k in kept)
        if not overlaps:
            kept.append(e)

    kept.sort(key=lambda e: e.start)

    parts: list[str] = []
    cursor = 0
    for e in kept:
        parts.append(text[cursor:e.start])
        parts.append(f'[{e.entity_type}]')
        cursor = e.end
    parts.append(text[cursor:])
    return ''.join(parts)


def classify_query_sensitivity(entities: list[DetectedEntity]) -> int:
    if not entities:
        return 0

    types = {e.entity_type for e in entities}

    if types & _LEVEL_3_TYPES:
        return 3

    if 'PERSON' in types and (
        'EMAIL_ADDRESS' in types
        or 'PHONE_NUMBER' in types
        or 'LOCATION' in types
    ):
        return 2

    if types & _LEVEL_1_TYPES:
        return 1

    return 0


####################
# Main entry point
####################


async def evaluate_request(
    user_context: UserContext,
    query: str,
    collection_ids: Optional[list[str]] = None,
    accessing_shared_kb: bool = False,
) -> PolicyDecisionResult:
    # Layer 1 + 2 — Presidio structural + ML detection
    entities = detect_entities(query)
    presidio_level = classify_query_sensitivity(entities)

    # Layer 3 — LLM semantic fallback
    # Only fires when Presidio finds nothing (level 0).
    # Catches sensitive intent and ambiguous phrasing
    # that pattern matching misses.
    llm_level = 0
    llm_reason = None
    if presidio_level == 0:
        llm_level, llm_reason = await llm_classify(query)

    # Final sensitivity is the maximum across all layers.
    # If any layer flags it, it is flagged.
    sensitivity_level = max(presidio_level, llm_level)
    redacted_query = anonymize_query(query, entities)
    query_hash = hashlib.sha256(query.encode('utf-8')).hexdigest()

    # Decision logic. Severity order: block > flag > proceed.
    # We evaluate weaker-to-stronger so stronger outcomes overwrite.
    decision = 'proceed'
    reason = 'ok'

    if user_context.is_admin:
        decision = 'proceed'
        reason = 'admin bypass'
    else:
        if sensitivity_level >= user_context.requires_review_above_clearance:
            decision = 'flag'
            reason = 'Query requires review before processing'

        if sensitivity_level > user_context.clearance_level:
            if accessing_shared_kb:
                # The user is querying a published shared KB whose content is
                # already redacted by the platform. The retrieval layer will
                # only serve sanitised chunks, so blocking here adds no
                # protection while preventing legitimate use.
                decision = 'proceed'
                reason = 'clearance bypass — accessing pre-redacted shared KB'
                log.debug(
                    f'[policy] user={user_context.user_id} '
                    f'sensitivity={sensitivity_level} > clearance={user_context.clearance_level} '
                    f'but accessing_shared_kb=True — proceeding'
                )
            else:
                decision = 'block'
                reason = 'Query sensitivity exceeds your clearance level'

        # Empty allowed_collection_ids means no restrictions — skip check.
        if collection_ids and user_context.allowed_collection_ids:
            denied = [
                cid
                for cid in collection_ids
                if cid not in user_context.allowed_collection_ids
            ]
            if denied:
                decision = 'block'
                reason = f'Access to collection {denied[0]} not permitted'

    # If LLM classifier was the deciding layer, surface
    # its reason in the audit log for traceability.
    if llm_level > presidio_level and llm_reason:
        reason = f"{reason} [llm: {llm_reason}]"

    # Route D — Human review queue.
    # A 'flag' decision becomes 'pending' unless:
    #   (a) the query hash was already approved within the last 24 h, or
    #   (b) there is already an open pending review for this hash (dedup).
    # Approved queries proceed normally; re-flagging is silently suppressed.
    pending_review_id: str | None = None
    if decision == 'flag':
        try:
            from arkive.models.pending_reviews import PendingReviews
            if PendingReviews.is_approved(query_hash):
                decision = 'proceed'
                reason = f'{reason} [previously approved]'
                log.info(
                    f'[policy] user={user_context.user_id} '
                    f'hash={query_hash[:12]}... approved within 24h — proceeding'
                )
            elif not PendingReviews.has_pending(query_hash):
                pr = PendingReviews.insert(
                    user_id=user_context.user_id,
                    query_hash=query_hash,
                    query_preview=redacted_query[:200],
                    sensitivity_level=sensitivity_level,
                    reason=reason,
                )
                if pr:
                    pending_review_id = str(pr.id)
                    decision = 'pending'
                    log.info(
                        f'[policy] user={user_context.user_id} '
                        f'query held for review review_id={pending_review_id}'
                    )
            else:
                decision = 'pending'
                log.info(
                    f'[policy] user={user_context.user_id} '
                    f'duplicate pending review for hash={query_hash[:12]}... — holding'
                )
        except Exception as _pr_err:
            log.exception(f'[policy] pending review queue failed: {_pr_err} — blocking as safe fallback')
            decision = 'block'
            reason = f'{reason} [review queue unavailable]'

    permitted = decision == 'proceed'
    audit_required = (
        decision != 'proceed'
        or sensitivity_level >= user_context.requires_review_above_clearance
        or (user_context.is_admin and sensitivity_level >= 2)
    )

    # Append-only audit row. Never store the raw query, only its hash.
    audit_id: str | None = None
    try:
        inserted = PolicyDecisions.insert_policy_decision(
            PolicyDecisionForm(
                user_id=user_context.user_id,
                team_id=None,
                query_hash=query_hash,
                detected_entities=[asdict(e) for e in entities],
                sensitivity_level=sensitivity_level,
                decision=decision,
                reason=reason,
            )
        )
        audit_id = str(inserted.id) if inserted else None
    except Exception as e:
        # Audit log failure must not block the request pipeline, but
        # we surface it loudly — a gap in the audit trail is a compliance issue.
        log.exception(f'Failed to write policy_decisions audit row: {e}')

    log.info(
        f'[policy] user={user_context.user_id} decision={decision} '
        f'presidio={presidio_level} llm={llm_level} '
        f'final={sensitivity_level} '
        f'entities={[e.entity_type for e in entities]} '
        f'audit_id={audit_id} reason={reason!r}'
    )

    return PolicyDecisionResult(
        permitted=permitted,
        decision=decision,
        reason=reason,
        detected_entities=entities,
        redacted_query=redacted_query,
        audit_required=audit_required,
        sensitivity_level=sensitivity_level,
        audit_id=audit_id,
        pending_review_id=pending_review_id,
    )
