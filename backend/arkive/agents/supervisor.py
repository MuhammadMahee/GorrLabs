import asyncio
import json
import logging
import os
from dataclasses import dataclass, field

from arkive.utils.bedrock_client import bedrock_llm_call

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
    """Returns raw content string. Returns "" on any failure. Never raises."""
    try:
        return await bedrock_llm_call(prompt, max_tokens=max_tokens, timeout=timeout)
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

# Domain-specific search prefixes.
# Prepended to the query before tool calls to bias retrieval
# toward domain-relevant terminology without changing tool logic.
_DOMAIN_HINTS: dict[str, str] = {
    "finance":  "financial figures, budget, invoice, pricing, cost:",
    "legal":    "legal terms, compliance, policy, agreement, regulation:",
    "hr":       "HR policy, employee, leave, payroll, hiring, benefits:",
    "product":  "product features, roadmap, technical specification, release:",
    "general":  "",  # no prefix for general queries
}


def select_initial_tools(classification) -> tuple[list[str], str]:
    """
    Returns (tool_list, domain_hint).
    domain_hint is prepended to the query before tool calls
    to bias retrieval toward domain-relevant terminology.
    Empty string means no prefix.
    """
    from arkive.agents.query_classifier import QueryType

    hint = _DOMAIN_HINTS.get(
        getattr(classification, 'domain', 'general'), ""
    )
    qt = classification.query_type

    if qt == QueryType.SIMPLE:
        return (["search_knowledge_base"], hint)

    if qt == QueryType.PROCEDURAL:
        tools = ["search_knowledge_base"]
        if classification.needs_full_doc:
            tools.append("retrieve_full_document")
        return (tools, hint)

    if qt in (QueryType.ANALYTICAL, QueryType.COMPARATIVE):
        return (["search_with_multi_query"], hint)

    return (["search_knowledge_base"], hint)


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


# ── Part 3c — Diagnosis and query reformulation ───────────────────────────────

async def _diagnose_and_reformulate(
    original_query: str,
    accumulated_context: str,
    tools_already_called: list[str],
) -> tuple[str, str]:
    """
    When retrieval is insufficient, asks the LLM to reason about
    what is missing and produce a better search query.

    Returns (reformulated_query, diagnosis) tuple.
    - reformulated_query: a new search query that targets the gap.
      Falls back to original_query if LLM fails or returns empty.
    - diagnosis: one sentence explaining what is missing.
      Used only for logging.

    Never raises.
    """
    prompt = (
        "You are a retrieval strategist for an enterprise AI system.\n\n"
        "Original question: {query}\n\n"
        "Context retrieved so far:\n{context}\n\n"
        "Tools already tried: {tools}\n\n"
        "The retrieved context is not sufficient to answer the question.\n"
        "Analyze what specific information is missing and write a better "
        "search query that would find it.\n\n"
        "Rules:\n"
        "- The new query must target the gap, not repeat what was already searched\n"
        "- Be specific — use different keywords than the original query\n"
        "- Keep the new query under 20 words\n\n"
        "Respond with valid JSON only:\n"
        '{{"diagnosis": "one sentence: what is missing", '
        '"reformulated_query": "the new search query"}}'
    ).format(
        query=original_query[:300],
        context=accumulated_context[:2000],
        tools=", ".join(tools_already_called) or "none",
    )

    raw = await _llm_call(prompt, max_tokens=150, timeout=_SUFFICIENCY_TIMEOUT)

    if not raw:
        return original_query, "diagnosis unavailable"

    cleaned = _strip_json_fences(raw)
    try:
        parsed = json.loads(cleaned)
        reformulated = str(parsed.get("reformulated_query", "")).strip()
        diagnosis = str(parsed.get("diagnosis", "")).strip()

        if not reformulated:
            return original_query, diagnosis or "no reformulation produced"

        return reformulated, diagnosis

    except json.JSONDecodeError:
        log.warning("[supervisor._diagnose_and_reformulate] JSON parse failed — using original query")
        return original_query, "parse error"


# ── Part 4a — Query decomposer ────────────────────────────────────────────────

async def _decompose_query(query: str) -> list[str]:
    """
    Detects whether a query has multiple distinct information
    needs and decomposes it into atomic sub-queries.

    Returns a list of sub-query strings.
    - If decomposition is needed: 2-4 short atomic sub-queries
    - If query is already atomic: [query] (single item)
    - On any LLM failure: [query] (safe fallback, never raises)

    Examples:
    Input:  "compare our leave policy to industry and summarize expense procedure"
    Output: ["leave policy terms entitlement", "expense claim procedure steps"]

    Input:  "how many days of annual leave do employees get?"
    Output: ["how many days of annual leave do employees get?"]
    """
    prompt = (
        "You are a query decomposition specialist for an enterprise "
        "retrieval system.\n\n"
        "Analyze this query and determine if it contains multiple "
        "distinct information needs that require separate document "
        "searches to answer completely.\n\n"
        "Query: {query}\n\n"
        "Rules:\n"
        "- Only decompose if there are 2 or more genuinely different "
        "topics that need separate retrieval\n"
        "- Each sub-query must be independently searchable (atomic)\n"
        "- Each sub-query must be under 15 words\n"
        "- Maximum 4 sub-queries\n"
        "- If the query is already atomic or asks about one topic, "
        "return it unchanged as a single-item array\n"
        "- Do not paraphrase — keep domain terminology exact\n\n"
        "Return a JSON array of strings only. No explanation.\n"
        "Examples:\n"
        '  Input: "compare leave policy to industry and explain expense steps"\n'
        '  Output: ["leave policy entitlement terms", '
        '"expense claim procedure steps"]\n\n'
        '  Input: "how many days of annual leave do employees get?"\n'
        '  Output: ["how many days of annual leave do employees get?"]\n\n'
        "Query to decompose: {query}\n"
        "Output:"
    ).format(query=query[:400])

    raw = await _llm_call(prompt, max_tokens=200, timeout=_SUFFICIENCY_TIMEOUT)

    if not raw:
        return [query]

    cleaned = _strip_json_fences(raw)
    try:
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list):
            return [query]

        sub_queries = [
            str(q).strip()
            for q in parsed
            if q and str(q).strip()
        ]

        if not sub_queries:
            return [query]

        sub_queries = sub_queries[:4]

        log.info(
            f"[supervisor._decompose_query] "
            f"{'decomposed into ' + str(len(sub_queries)) + ' sub-queries' if len(sub_queries) > 1 else 'no decomposition needed'}: "
            f"{sub_queries}"
        )
        return sub_queries

    except json.JSONDecodeError:
        log.warning(
            "[supervisor._decompose_query] JSON parse failed — "
            "using original query"
        )
        return [query]


# ── Part 4 — Main supervisor loop ─────────────────────────────────────────────

async def run_supervisor(
    query: str,
    classification,          # QueryClassification
    user_context,            # UserContext
    request,                 # FastAPI Request
    collection_ids: list[str] | None = None,
    conversation_history: list[str] | None = None,
) -> AgentResponse:
    """
    Main agentic RAG loop. Selects tools, calls them in sequence,
    evaluates sufficiency after each success, synthesizes final answer.
    Never raises — returns fell_back=True on unhandled errors.
    """
    from arkive.agents.tools import get_tools_for_user, ToolStatus

    try:
        tools_registry = get_tools_for_user(user_context)

        # Build the initial tool queue
        original_query = query
        tool_queue, _domain_hint = select_initial_tools(classification)

        # Apply domain hint to query if present.
        # The hint biases retrieval toward domain terminology
        # without changing what the user asked.
        if _domain_hint:
            query = f"{_domain_hint} {query}"
            log.info(
                f"[supervisor] domain={getattr(classification, 'domain', 'general')} "
                f"hint applied to query"
            )
        called_tools: set[str] = set()
        tools_used: list[str] = []
        all_sources: list[str] = []
        context_parts: list[str] = []
        iteration = 0

        # Prepend sanitized conversation history so agents know
        # what ground was already covered in previous turns.
        # This prevents re-searching the same documents and lets
        # the supervisor build on prior context rather than starting
        # fresh every turn.
        if conversation_history:
            history_block = (
                "=== Prior Conversation ===\n"
                + "\n".join(conversation_history)
                + "\n=== End Prior Conversation ==="
            )
            context_parts.append(history_block)
            log.info(
                f"[supervisor] loaded {len(conversation_history)} "
                f"history messages from prior turns"
            )

        # ── Query decomposition ───────────────────────────────────────
        # Only fires for ANALYTICAL and COMPARATIVE queries — the types
        # where complex multi-part questions are likely.
        # Decomposition is a free pre-retrieval step: parallel fetches
        # run outside the tool loop so MAX_TOOL_ITERATIONS is preserved.
        from arkive.agents.query_classifier import QueryType as _QT
        _should_decompose = classification.query_type in (
            _QT.ANALYTICAL, _QT.COMPARATIVE
        )

        if _should_decompose:
            sub_queries = await _decompose_query(query)
        else:
            sub_queries = [query]

        if len(sub_queries) > 1:
            from arkive.agents.tools import search_knowledge_base, ToolStatus as _TS

            log.info(
                f"[supervisor] decomposition — running "
                f"{len(sub_queries)} parallel fetches"
            )

            _fetch_results = await asyncio.gather(
                *[
                    search_knowledge_base(
                        query=sq,
                        user_context=user_context,
                        request=request,
                        collection_ids=collection_ids,
                    )
                    for sq in sub_queries
                ],
                return_exceptions=True,
            )

            _merged_parts: list[str] = []
            _merged_sources: list[str] = []

            for _sq, _res in zip(sub_queries, _fetch_results):
                if isinstance(_res, Exception):
                    log.warning(
                        f"[supervisor] decomposition fetch failed "
                        f"for sub-query={_sq!r}: {_res}"
                    )
                    continue
                if _res.status in (_TS.EMPTY, _TS.ERROR):
                    log.debug(
                        f"[supervisor] decomposition fetch "
                        f"status={_res.status.value} for sub-query={_sq!r} — skipping"
                    )
                    continue
                _merged_parts.append(
                    f"[Sub-query: {_sq}]\n{_res.content}"
                )
                for _src in _res.sources:
                    if _src not in _merged_sources:
                        _merged_sources.append(_src)

            if _merged_parts:
                _merged_block = (
                    "=== Decomposed Retrieval ===\n\n"
                    + "\n\n---\n\n".join(_merged_parts)
                )
                context_parts.append(_merged_block)
                for _src in _merged_sources:
                    if _src not in all_sources:
                        all_sources.append(_src)

                log.info(
                    f"[supervisor] decomposition merged "
                    f"{len(_merged_parts)}/{len(sub_queries)} fetches — "
                    f"context_parts now has {len(context_parts)} block(s) "
                    f"before tool loop"
                )
        # ── End query decomposition ───────────────────────────────────

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

            # SUCCESS or LOW_QUALITY — accumulate context either way
            tools_used.append(tool_name)
            context_parts.append(result.content)
            for src in result.sources:
                if src not in all_sources:
                    all_sources.append(src)

            accumulated_context = "\n\n=== Additional Context ===\n\n".join(context_parts)

            # LOW_QUALITY: content is usable but reranker scores were weak.
            # Skip sufficiency check and go straight to reformulation so the
            # next iteration searches with better-targeted keywords.
            next_tool: str | None = None
            if result.status == ToolStatus.LOW_QUALITY:
                log.info(
                    f"[supervisor] tool={tool_name} LOW_QUALITY "
                    f"avg_score={result.metadata.get('avg_score', 0):.3f} "
                    "— skipping sufficiency, reformulating"
                )
            else:
                # SUCCESS — evaluate whether we have enough context already
                sufficient, next_tool = await _evaluate_sufficiency(
                    query, accumulated_context
                )

                if sufficient:
                    log.info(f"[supervisor] sufficiency met after tool={tool_name}")
                    break

                # Not sufficient — fall through to reformulation below

            # Diagnose what is missing and reformulate the query before the
            # next tool call so each iteration searches for something different.
            reformulated_query, diagnosis = await _diagnose_and_reformulate(
                original_query=query,
                accumulated_context=accumulated_context,
                tools_already_called=list(called_tools),
            )

            if reformulated_query != query:
                log.info(
                    f"[supervisor] query reformulated after tool={tool_name} "
                    f"diagnosis={diagnosis!r} "
                    f"original={query[:60]!r} → new={reformulated_query[:60]!r}"
                )
                query = reformulated_query
            else:
                log.debug(
                    f"[supervisor] reformulation unchanged — "
                    f"diagnosis={diagnosis!r}"
                )

            # Add suggested tool to queue if valid and not yet called
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
        from arkive.agents.query_classifier import QueryType
        _needs_synthesis = classification.query_type in (
            QueryType.ANALYTICAL,
            QueryType.COMPARATIVE,
        )

        if _needs_synthesis:
            answer = await _synthesize_answer(
                query=original_query,
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
    conversation_history: list[str] | None = None,
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
            conversation_history=conversation_history or [],
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
