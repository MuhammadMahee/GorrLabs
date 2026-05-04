import os
import json
import logging
from dataclasses import dataclass
from enum import Enum

from arkive.utils.bedrock_client import bedrock_llm_call

log = logging.getLogger(__name__)

CLASSIFIER_TIMEOUT = float(os.getenv("CLASSIFIER_TIMEOUT", "20.0"))


class QueryType(str, Enum):
    SIMPLE = "simple"
    ANALYTICAL = "analytical"
    COMPARATIVE = "comparative"
    PROCEDURAL = "procedural"


@dataclass
class QueryClassification:
    query_type: QueryType
    confidence: float        # 0.0 - 1.0
    reasoning: str           # one sentence explaining the decision
    needs_web: bool          # True if external data would help
    needs_full_doc: bool     # True if full document context needed


CLASSIFICATION_PROMPT = """You are a strict query classifier for an enterprise retrieval system.

Task:
Classify the query into exactly ONE type and set retrieval flags.

Types (mutually exclusive):
- simple: single fact or definition; answerable from one chunk or document
- analytical: requires synthesis, summarization, or reasoning across multiple sources
- comparative: explicitly compares two or more entities, policies, or datasets
- procedural: asks for steps, instructions, workflows, or "how-to" guidance

Decision Rules (apply strictly):
- If the query contains comparison intent (e.g., "compare", "difference", "vs"), use comparative.
- If the query asks "how", "steps", "process", or implies instructions, use procedural.
- If multiple sources are needed but no comparison is requested, use analytical.
- Otherwise default to simple.

Flags:
- needs_web = true ONLY if the query requires current, external, or real-time information not present in internal documents.
- needs_full_doc = true if type is "procedural" (steps/instructions require the full source document).
  Also true if a complete policy or legal document is required to preserve meaning.
  Default to false only for simple factual lookups.

Constraints:
- Choose exactly one type.
- Be conservative with needs_web (default to false unless clearly required).
- For procedural queries, always set needs_full_doc = true.
- Do not guess external needs if uncertain.

Query:
"{query}"

Output format (strict JSON, no extra text):
{
  "type": "simple | analytical | comparative | procedural",
  "confidence": 0.0-1.0,
  "needs_web": true | false,
  "needs_full_doc": true | false
}
"""


async def classify_query(query: str) -> QueryClassification:
    """
    Classifies a query into a QueryType bucket.

    Returns QueryClassification.
    Falls back to QueryType.SIMPLE on any failure so the
    standard RAG path always runs — agentic path is additive,
    not a replacement.
    Never raises.
    """
    _default = QueryClassification(
        query_type=QueryType.SIMPLE,
        confidence=0.0,
        reasoning="classifier unavailable — defaulting to simple",
        needs_web=False,
        needs_full_doc=False,
    )

    try:
        prompt = CLASSIFICATION_PROMPT.replace("{query}", query[:500])

        content = await bedrock_llm_call(prompt, max_tokens=200, timeout=CLASSIFIER_TIMEOUT)

        if not content:
            return _default

        # Strip markdown fences if model adds them despite instructions
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        # Wrap bare key-value output in braces if model omits outer {}
        if content and not content.startswith("{"):
            content = "{" + content.rstrip(",") + "}"

        parsed = json.loads(content)

        query_type_str = parsed.get("type", "simple").lower()
        try:
            query_type = QueryType(query_type_str)
        except ValueError:
            query_type = QueryType.SIMPLE

        return QueryClassification(
            query_type=query_type,
            confidence=float(parsed.get("confidence", 0.5)),
            reasoning=str(parsed.get("reasoning", "")),
            needs_web=bool(parsed.get("needs_web", False)),
            needs_full_doc=bool(parsed.get("needs_full_doc", False)),
        )

    except json.JSONDecodeError as e:
        log.warning(f"[query_classifier] JSON parse error: {e} — defaulting to simple")
        return _default
    except Exception as e:
        log.warning(f"[query_classifier] failed: {e} — defaulting to simple")
        return _default


def should_use_agentic_path(classification: QueryClassification) -> bool:
    """
    Returns True if the query should be routed to the agentic path.

    Routing rules:
    - SIMPLE queries always use standard RAG
    - ANALYTICAL, COMPARATIVE, PROCEDURAL use agentic path
      only when confidence >= 0.7
    - If needs_web is True, always use agentic path (web agent needed)
    - Default (low confidence or classifier failure) → standard RAG

    Standard RAG is always the safe fallback.
    """
    if classification.query_type == QueryType.SIMPLE:
        return classification.confidence >= 0.8

    if classification.needs_web:
        return True

    if classification.confidence >= 0.7:
        return True

    return False
