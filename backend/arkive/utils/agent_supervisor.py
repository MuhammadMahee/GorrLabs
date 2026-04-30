import asyncio
import json
import logging
import os
from dataclasses import dataclass, field

import httpx

from arkive.env import OLLAMA_BASE_URL, OLLAMA_MODEL

log = logging.getLogger(__name__)

SUPERVISOR_TIMEOUT = float(os.getenv("SUPERVISOR_TIMEOUT", "30.0"))
_SUFFICIENCY_TIMEOUT = float(os.getenv("SUFFICIENCY_TIMEOUT", "10.0"))
MAX_TOOL_ITERATIONS = 4


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class AgentResponse:
    answer:     str
    tools_used: list[str]
    sources:    list[str]
    iterations: int
    fell_back:  bool = False
    metadata:   dict = field(default_factory=dict)


_FALLBACK_RESPONSE = AgentResponse(
    answer="",
    tools_used=[],
    sources=[],
    iterations=0,
    fell_back=True,
)


# ── Internal LLM helper ───────────────────────────────────────────────────────

async def _llm_call(prompt: str, max_tokens: int, timeout: float) -> str:
    """
    Single Ollama call with dual-endpoint fallback.
    Returns raw content string. Returns "" on any failure. Never raises.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    native_payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                r = await client.post(
                    f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                )
                r.raise_for_status()
                return (
                    r.json()
                     .get("choices", [{}])[0]
                     .get("message", {})
                     .get("content", "")
                     .strip()
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise
                r = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json=native_payload,
                )
                r.raise_for_status()
                return (
                    (r.json().get("message") or {})
                    .get("content", "")
                    .strip()
                )
    except Exception as exc:
        log.warning(f"[supervisor._llm_call] failed: {exc}")
        return ""


def _strip_json_fences(text: str) -> str:
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


# ── Part 2 — Tool selection ───────────────────────────────────────────────────

def select_initial_tools(classification) -> list[str]:
    """
    Returns an ordered list of tool names to try first,
    based on query classification. Cheapest tool first.
    """
    from arkive.utils.query_classifier import QueryType

    qt = classification.query_type

    if qt == QueryType.SIMPLE:
        return ["search_knowledge_base"]

    if qt == QueryType.PROCEDURAL:
        tools = ["search_knowledge_base"]
        if classification.needs_full_doc:
            tools.append("retrieve_full_document")
        return tools

    if qt in (QueryType.ANALYTICAL, QueryType.COMPARATIVE):
        return ["search_with_multi_query"]

    # Fallback for any unknown type
    return ["search_knowledge_base"]


# ── Part 3 — Sufficiency evaluator ───────────────────────────────────────────

_SUFFICIENCY_PROMPT = (
    "You are an AI retrieval evaluator.\n\n"
    "Question: {query}\n\n"
    "Retrieved context so far:\n{context}\n\n"
    "Is this context sufficient to give a complete, accurate answer?\n\n"
    'If yes: {{"sufficient": true, "next_tool": null}}\n'
    'If no:  {{"sufficient": false, "next_tool": "tool_name"}}\n\n'
    "Available tools: search_knowledge_base, retrieve_full_document, "
    "search_with_multi_query, search_with_self_reflection\n\n"
    "Respond with JSON only."
)


async def _evaluate_sufficiency(
    query: str,
    accumulated_context: str,
) -> tuple[bool, str | None]:
    """
    Asks the local LLM if accumulated context is sufficient.
    Returns (is_sufficient, next_tool_suggestion).
    Falls back to (True, None) on any failure — never blocks.
    """
    prompt = _SUFFICIENCY_PROMPT.format(
        query=query[:300],
        context=accumulated_context[:3000],
    )
    raw = await _llm_call(prompt, max_tokens=80, timeout=_SUFFICIENCY_TIMEOUT)

    if not raw:
        return True, None

    cleaned = _strip_json_fences(raw)
    try:
        parsed = json.loads(cleaned)
        sufficient = bool(parsed.get("sufficient", True))
        next_tool = parsed.get("next_tool") or None
        return sufficient, next_tool
    except json.JSONDecodeError:
        log.warning("[supervisor._evaluate_sufficiency] JSON parse failed — treating as sufficient")
        return True, None




# ── Part 3b — Answer synthesizer ─────────────────────────────────────────────

async def _synthesize_answer(
    query: str,
    accumulated_context: str,
    sources: list[str],
) -> str:
    """
    Synthesizes a final answer from accumulated tool results.
    Falls back to returning accumulated_context if LLM fails.
    """
    prompt = (
        "You are an enterprise knowledge assistant.\n\n"
        "Answer the following question using ONLY the context "
        "provided below. Follow these rules strictly:\n\n"
        "1. If the context does not contain enough information "
        "to answer, respond with exactly: "
        "'I don't have access to information about that topic.' "
        "Do not use external knowledge. Do not estimate.\n\n"
        "2. For comparative questions: state the internal company "
        "figure first, then the external benchmark, then your "
        "assessment. Be explicit about both numbers.\n\n"
        "3. For procedural questions: list every step in order. "
        "Include all conditions, thresholds, and exceptions.\n\n"
        "4. Always cite the source document name when referencing "
        "specific figures or policies.\n\n"
        f"Question: {query}\n\n"
        f"Context:\n{accumulated_context}\n\n"
        "Answer:"
    )
    answer = await _llm_call(prompt, max_tokens=1000, timeout=SUPERVISOR_TIMEOUT)
    if not answer:
        log.warning(
            "[supervisor._synthesize_answer] LLM unavailable "
            "— returning raw context"
        )
        return accumulated_context
    return answer


# ── Part 4 — Document title extractor ────────────────────────────────────────

async def _extract_document_title(query: str) -> str:
    """
    Uses the local LLM to extract the most likely document
    title or filename from an abstract query.

    Example:
    Query: "How do I get reimbursed for work expenses?"
    Returns: "expense" or "expense claim" or "reimbursement policy"

    Falls back to the raw query if LLM fails.
    Never raises.
    """
    prompt = (
        "A user is looking for a specific document. "
        "Extract the most likely document name or topic "
        "from this query. Return 1-4 words only that would "
        "appear in the document filename. No explanation.\n\n"
        f"Query: {query}\n\n"
        "Document topic (1-4 words):"
    )
    result = await _llm_call(prompt, max_tokens=20, timeout=6.0)
    if result and len(result.strip()) > 0:
        return result.strip().lower()
    return query


# ── Part 4 — Main supervisor loop ─────────────────────────────────────────────

async def run_supervisor(
    query: str,
    classification,          # QueryClassification
    user_context,            # UserContext
    request,                 # FastAPI Request
    collection_ids: list[str] | None = None,
) -> AgentResponse:
    """
    Main agentic RAG loop. Selects tools, calls them in sequence,
    evaluates sufficiency after each success, synthesizes final answer.
    Never raises — returns fell_back=True on unhandled errors.
    """
    from arkive.utils.agent_tools import get_tools_for_user, ToolStatus

    try:
        tools_registry = get_tools_for_user(user_context)

        # Build the initial tool queue
        tool_queue: list[str] = select_initial_tools(classification)
        called_tools: set[str] = set()
        tools_used: list[str] = []
        all_sources: list[str] = []
        context_parts: list[str] = []
        iteration = 0

        while tool_queue and iteration < MAX_TOOL_ITERATIONS:
            tool_name = tool_queue.pop(0)

            # Never call the same tool twice
            if tool_name in called_tools:
                continue

            tool_fn = tools_registry.get(tool_name)
            if tool_fn is None:
                log.warning(f"[supervisor] tool={tool_name} not in registry — skipping")
                continue

            log.info(f"[supervisor] calling tool={tool_name} iteration={iteration + 1}")
            called_tools.add(tool_name)
            iteration += 1

            # Call the tool — all tools share the same core signature
            try:
                if tool_name == "retrieve_full_document":
                    # retrieve_full_document takes document_title not query
                    _doc_title = await _extract_document_title(query)
                    log.info(f"[supervisor] title_extraction query='{query[:50]}' → '{_doc_title}'")
                    result = await tool_fn(
                        document_title=_doc_title,
                        user_context=user_context,
                        request=request,
                    )
                else:
                    result = await tool_fn(
                        query=query,
                        user_context=user_context,
                        request=request,
                        collection_ids=collection_ids,
                    )
            except Exception as tool_exc:
                log.warning(f"[supervisor] tool={tool_name} raised: {tool_exc} — skipping")
                continue

            if result.status in (ToolStatus.ERROR, ToolStatus.EMPTY):
                log.info(f"[supervisor] tool={tool_name} status={result.status.value} — skipping")
                continue

            # SUCCESS — accumulate context
            tools_used.append(tool_name)
            context_parts.append(result.content)
            for src in result.sources:
                if src not in all_sources:
                    all_sources.append(src)

            accumulated_context = "\n\n=== Additional Context ===\n\n".join(context_parts)

            # Evaluate sufficiency after each success
            sufficient, next_tool = await _evaluate_sufficiency(query, accumulated_context)

            if sufficient:
                log.info(f"[supervisor] sufficiency met after tool={tool_name}")
                break

            # Not sufficient — add suggested tool if valid and not yet called
            if (
                next_tool
                and next_tool in tools_registry
                and next_tool not in called_tools
                and next_tool not in tool_queue
                and iteration < MAX_TOOL_ITERATIONS
            ):
                log.info(f"[supervisor] adding suggested tool={next_tool} to queue")
                tool_queue.append(next_tool)

        # Build final accumulated context
        accumulated_context = "\n\n=== Additional Context ===\n\n".join(context_parts)

        fell_back = not accumulated_context

        if fell_back:
            log.info(
                f"[supervisor] complete tools={tools_used} iterations={iteration} "
                f"fell_back=True — all tools returned empty or error"
            )
            return AgentResponse(
                answer="",
                tools_used=tools_used,
                sources=all_sources,
                iterations=iteration,
                fell_back=True,
            )

        # Synthesis only runs for query types where combining
        # multiple sources adds real value.
        # For SIMPLE and PROCEDURAL: inject raw context and let
        # the main chat model handle synthesis — it is more
        # reliable than running a second synthesis LLM call.
        from arkive.utils.query_classifier import QueryType
        _needs_synthesis = classification.query_type in (
            QueryType.ANALYTICAL,
            QueryType.COMPARATIVE,
        )

        if _needs_synthesis:
            answer = await _synthesize_answer(
                query=query,
                accumulated_context=accumulated_context,
                sources=all_sources,
            )
            log.info("[supervisor] synthesis complete")
        else:
            # Raw context injection — main chat model synthesizes
            answer = accumulated_context
            log.info(
                "[supervisor] skipping synthesis — "
                f"query_type={classification.query_type.value} "
                "raw context injected"
            )

        log.info(
            f"[supervisor] complete tools={tools_used} "
            f"iterations={iteration} fell_back=False"
        )

        return AgentResponse(
            answer=answer,
            tools_used=tools_used,
            sources=all_sources,
            iterations=iteration,
            fell_back=False,
            metadata={
                "query_type": classification.query_type.value,
                "confidence": classification.confidence,
            },
        )

    except Exception as exc:
        log.exception(f"[supervisor] unhandled error: {exc} — falling back")
        return AgentResponse(
            answer="",
            tools_used=[],
            sources=[],
            iterations=0,
            fell_back=True,
        )


# ── Part 6 — Public entry point ───────────────────────────────────────────────

async def run_agentic_rag(
    query: str,
    classification,          # QueryClassification
    user_context,            # UserContext
    request,                 # FastAPI Request
    collection_ids: list[str] | None = None,
) -> AgentResponse:
    """
    Public entry point. Wraps run_supervisor with top-level error handling.
    If run_supervisor raises for any reason, returns fell_back=True so the
    caller routes to standard RAG instead.
    """
    try:
        return await run_supervisor(
            query=query,
            classification=classification,
            user_context=user_context,
            request=request,
            collection_ids=collection_ids,
        )
    except Exception as exc:
        log.exception(f"[supervisor.run_agentic_rag] unexpected error: {exc}")
        return AgentResponse(
            answer="",
            tools_used=[],
            sources=[],
            iterations=0,
            fell_back=True,
        )
