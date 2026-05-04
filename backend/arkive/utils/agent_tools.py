import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from pydantic import BaseModel, ValidationError

from arkive.utils.bedrock_client import bedrock_llm_call


class _MultiQueryResponse(BaseModel):
    queries: list[str]


class _SufficiencyResponse(BaseModel):
    sufficient: bool
    refined_query: str | None = None

log = logging.getLogger(__name__)

_TOOL_LLM_TIMEOUT = float(os.getenv("TOOL_LLM_TIMEOUT", "20.0"))


# ── Data structures ──────────────────────────────────────────────────────────

class ToolStatus(str, Enum):
    SUCCESS = "success"
    EMPTY   = "empty"
    ERROR   = "error"


@dataclass
class ToolResult:
    tool_name:   str
    status:      ToolStatus
    content:     str         # formatted context string ready for LLM injection
    sources:     list[str]   # document names / titles for citation
    chunks_used: int         # number of chunks that contributed
    metadata:    dict = field(default_factory=dict)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _format_chunks(
    sources: list[dict],
    max_chars: int = 12000,
) -> tuple[str, list[str], int]:
    """
    Convert filter_chunks_by_clearance() output into
    (content_str, source_names, chunk_count).

    Chunks are added in order (reranker has already sorted by relevance
    score descending) until max_chars is reached. This ensures the LLM
    context window is not overflowed and highest-scored chunks are kept.
    """
    parts: list[str] = []
    names: list[str] = []
    count = 0
    total_chars = 0

    for source in sources:
        documents = source.get("document") or []
        metadatas = source.get("metadata") or []
        for doc, meta in zip(documents, metadatas):
            if not doc:
                continue
            name = (
                (meta or {}).get("name")
                or (meta or {}).get("source")
                or (meta or {}).get("title")
                or "Unknown"
            )
            chunk_str = f"[Source: {name}]\n{doc}"

            if total_chars + len(chunk_str) > max_chars:
                log.debug(
                    f"[agent_tools] token budget reached at "
                    f"{total_chars} chars — stopping at chunk {count}"
                )
                break

            parts.append(chunk_str)
            total_chars += len(chunk_str)
            if name not in names:
                names.append(name)
            count += 1

        else:
            continue
        break

    return "\n---\n".join(parts), names, count


async def _rerank_sources(
    query: str,
    sources: list[dict],
    request,
) -> list[dict]:
    """
    Reranks filtered sources using the app's reranking function.

    Takes the same source shape that filter_chunks_by_clearance() returns
    (list of dicts with 'document' and 'metadata' flat lists).
    Rebuilds the same shape after reranking so _format_chunks() receives
    chunks sorted by reranker score descending.

    Falls back to original sources on any failure — never raises.
    If RERANKING_FUNCTION is None, returns sources unchanged.
    """
    try:
        reranking_fn = getattr(
            getattr(getattr(request, "app", None), "state", None),
            "RERANKING_FUNCTION",
            None,
        )
        if reranking_fn is None:
            return sources

        from langchain_core.documents import Document
        from arkive.retrieval.utils import RerankCompressor

        # Flatten all chunks into LangChain Document objects
        all_docs: list[Document] = []
        for source in sources:
            for doc_text, meta in zip(
                source.get("document") or [],
                source.get("metadata") or [],
            ):
                if not doc_text:
                    continue
                all_docs.append(Document(page_content=doc_text, metadata=meta or {}))

        if not all_docs:
            return sources

        state = request.app.state
        config = getattr(state, "config", None)
        top_n = getattr(config, "TOP_K_RERANKER", 5)
        r_score = getattr(config, "RELEVANCE_THRESHOLD", 0.0)
        embedding_fn = getattr(state, "EMBEDDING_FUNCTION", None)

        compressor = RerankCompressor(
            embedding_function=embedding_fn,
            top_n=top_n,
            reranking_function=reranking_fn,
            r_score=r_score,
        )

        reranked = await compressor.acompress_documents(all_docs, query)

        if not reranked:
            return sources

        # Rebuild into the flat-list shape that _format_chunks() expects
        return [{
            "document": [d.page_content for d in reranked],
            "metadata": [d.metadata for d in reranked],
        }]

    except Exception as exc:
        log.warning(f"[agent_tools._rerank_sources] failed — using original order: {exc}")
        return sources


async def _llm_call(prompt: str, max_tokens: int = 300) -> str:
    """Returns raw content string. Falls back to "" on any failure. Never raises."""
    return await bedrock_llm_call(prompt, max_tokens=max_tokens, timeout=_TOOL_LLM_TIMEOUT)


def _strip_json_fences(text: str) -> str:
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


# ── Tool 1: search_knowledge_base ────────────────────────────────────────────

async def search_knowledge_base(
    query: str,
    user_context,                         # UserContext
    request,                              # FastAPI Request — needed for app.state
    collection_ids: list[str] | None = None,
    limit: int = 20,
) -> ToolResult:
    """
    Hybrid semantic + BM25 search over the user's knowledge base.
    Enforces clearance via filter_chunks_by_clearance().
    Primary retrieval tool — use for most queries.
    """
    try:
        from arkive.retrieval.utils import (
            query_collection,
            filter_chunks_by_clearance,
        )
        from arkive.config import RAG_EMBEDDING_QUERY_PREFIX

        # Resolve collection names to search
        if collection_ids:
            names = list(collection_ids)
        elif user_context.allowed_collection_ids:
            names = list(user_context.allowed_collection_ids)
        else:
            # No restriction — search all collections via wildcard sentinel.
            # query_collection handles empty gracefully; pass empty list and
            # let the caller supply collection_ids when targeting a specific KB.
            names = []

        if not names:
            return ToolResult(
                tool_name="search_knowledge_base",
                status=ToolStatus.EMPTY,
                content="No collections available to search.",
                sources=[],
                chunks_used=0,
            )

        embedding_function = request.app.state.EMBEDDING_FUNCTION

        raw = await query_collection(
            request=request,
            collection_names=names,
            queries=[query],
            embedding_function=embedding_function,
            k=limit,
        )

        # Build sources list in the shape filter_chunks_by_clearance() expects
        documents  = (raw.get("documents")  or [[]])[0]
        metadatas  = (raw.get("metadatas")  or [[]])[0]
        distances  = (raw.get("distances")  or [[]])[0]

        if not documents:
            return ToolResult(
                tool_name="search_knowledge_base",
                status=ToolStatus.EMPTY,
                content="No chunks found for this query.",
                sources=[],
                chunks_used=0,
            )

        sources_raw = [{
            "source":   {"collection_names": names},
            "document": documents,
            "metadata": metadatas,
            "distances": distances,
        }]

        filtered = await filter_chunks_by_clearance(
            sources=sources_raw,
            user_clearance=user_context.clearance_level,
        )

        # Rerank after clearance filter — uses app's configured
        # reranking model (BAAI/bge-reranker-v2-m3).
        # Falls back to original order if reranker unavailable.
        filtered = await _rerank_sources(
            query=query,
            sources=filtered,
            request=request,
        )

        content, source_names, count = _format_chunks(filtered)

        if count == 0:
            return ToolResult(
                tool_name="search_knowledge_base",
                status=ToolStatus.EMPTY,
                content="No chunks passed clearance filter.",
                sources=[],
                chunks_used=0,
            )

        return ToolResult(
            tool_name="search_knowledge_base",
            status=ToolStatus.SUCCESS,
            content=content,
            sources=source_names,
            chunks_used=count,
            metadata={"collections_searched": names, "limit": limit},
        )

    except Exception as exc:
        log.exception(f"[agent_tools.search_knowledge_base] failed: {exc}")
        return ToolResult(
            tool_name="search_knowledge_base",
            status=ToolStatus.ERROR,
            content=f"Search failed: {exc}",
            sources=[],
            chunks_used=0,
        )


# ── Tool 2: retrieve_full_document ───────────────────────────────────────────

async def retrieve_full_document(
    document_title: str,
    user_context,                         # UserContext
    request=None,                         # unused, kept for uniform supervisor call signature
) -> ToolResult:
    """
    Retrieves full document content by title from Postgres.
    Use when chunks lack sufficient context.
    Enforces clearance by checking document_classifications.
    """
    try:
        from arkive.models.files import Files
        from arkive.models.document_classifications import DocumentClassifications

        # Case-insensitive pattern search via glob wildcard
        matches = Files.search_files(filename=f"*{document_title}*", limit=10)

        if not matches:
            # Return EMPTY with a hint — list most recent 10 docs
            recent = Files.search_files(limit=10)
            titles = [f.filename for f in recent]
            hint = ", ".join(titles) if titles else "none found"
            return ToolResult(
                tool_name="retrieve_full_document",
                status=ToolStatus.EMPTY,
                content=(
                    f"No document matching '{document_title}' found. "
                    f"Available documents (recent): {hint}"
                ),
                sources=[],
                chunks_used=0,
            )

        # Use the best match (first result — ordered by created_at desc)
        file_obj = matches[0]

        # Clearance check
        classification = DocumentClassifications.get_classification_by_file_id(file_obj.id)
        doc_level = classification.sensitivity_level if classification else 0

        if doc_level > user_context.clearance_level:
            log.warning(
                f"[agent_tools.retrieve_full_document] access denied "
                f"file_id={file_obj.id} doc_level={doc_level} "
                f"user_clearance={user_context.clearance_level}"
            )
            return ToolResult(
                tool_name="retrieve_full_document",
                status=ToolStatus.ERROR,
                content="Access denied: insufficient clearance for this document.",
                sources=[],
                chunks_used=0,
            )

        content = (file_obj.data or {}).get("content", "")
        if not content:
            return ToolResult(
                tool_name="retrieve_full_document",
                status=ToolStatus.EMPTY,
                content=f"Document '{file_obj.filename}' exists but has no extractable text content.",
                sources=[file_obj.filename],
                chunks_used=0,
            )

        return ToolResult(
            tool_name="retrieve_full_document",
            status=ToolStatus.SUCCESS,
            content=f"[Source: {file_obj.filename}]\n{content}",
            sources=[file_obj.filename],
            chunks_used=1,
            metadata={"file_id": file_obj.id, "sensitivity_level": doc_level},
        )

    except Exception as exc:
        log.exception(f"[agent_tools.retrieve_full_document] failed: {exc}")
        return ToolResult(
            tool_name="retrieve_full_document",
            status=ToolStatus.ERROR,
            content=f"Document retrieval failed: {exc}",
            sources=[],
            chunks_used=0,
        )


# ── Tool 3: search_with_multi_query ──────────────────────────────────────────

_MULTI_QUERY_PROMPT = (
    "Generate 3 different search queries that would help answer the following "
    "question from different angles. Return as a JSON array of strings only. "
    "No explanation.\n"
    "Question: {query}\n"
    'Example output: ["query1", "query2", "query3"]'
)


async def search_with_multi_query(
    query: str,
    user_context,                         # UserContext
    request,                              # FastAPI Request
    collection_ids: list[str] | None = None,
) -> ToolResult:
    """
    Generates 3 query variations then runs parallel searches.
    Deduplicates results by chunk content hash.
    Use for ambiguous queries or broad coverage needs.
    """
    try:
        # Generate query variations
        raw = await _llm_call(
            _MULTI_QUERY_PROMPT.format(query=query[:400]),
            max_tokens=200,
        )

        variations: list[str] = [query]  # always include original as fallback
        if raw:
            cleaned = _strip_json_fences(raw)
            try:
                raw_parsed = json.loads(cleaned)
                if isinstance(raw_parsed, list):
                    variations = [str(v) for v in raw_parsed if v][:3]
                    if query not in variations:
                        variations.insert(0, query)
                elif isinstance(raw_parsed, dict):
                    validated = _MultiQueryResponse.model_validate(raw_parsed)
                    variations = validated.queries[:3]
                else:
                    raise ValueError("unexpected JSON shape")
            except (json.JSONDecodeError, ValidationError, ValueError) as _e:
                log.warning(
                    f"[agent_tools.search_with_multi_query] "
                    f"could not parse query variations ({_e}) — using original only"
                )

        log.info(f"[agent_tools.search_with_multi_query] running {len(variations)} queries")

        # Run all searches in parallel
        results: list[ToolResult] = await asyncio.gather(
            *[
                search_knowledge_base(
                    query=v,
                    user_context=user_context,
                    request=request,
                    collection_ids=collection_ids,
                )
                for v in variations
            ],
            return_exceptions=True,
        )

        # Deduplicate chunks across results by MD5 hash of content
        seen_hashes: set[str] = set()
        merged_parts: list[str] = []
        merged_sources: list[str] = []
        total_chunks = 0

        for result in results:
            if isinstance(result, Exception):
                log.warning(f"[agent_tools.search_with_multi_query] sub-search failed: {result}")
                continue
            if not isinstance(result, ToolResult) or result.status != ToolStatus.SUCCESS:
                continue

            # Split back on separator to get individual chunks
            for chunk in result.content.split("\n---\n"):
                import re
                normalized = re.sub(r'\s+', ' ', chunk.lower().strip())
                chunk_hash = hashlib.md5(normalized.encode()).hexdigest()
                if chunk_hash not in seen_hashes:
                    seen_hashes.add(chunk_hash)
                    merged_parts.append(chunk)
                    total_chunks += 1

            for src in result.sources:
                if src not in merged_sources:
                    merged_sources.append(src)

        if not merged_parts:
            return ToolResult(
                tool_name="search_with_multi_query",
                status=ToolStatus.EMPTY,
                content="No results found across any query variation.",
                sources=[],
                chunks_used=0,
            )

        return ToolResult(
            tool_name="search_with_multi_query",
            status=ToolStatus.SUCCESS,
            content="\n---\n".join(merged_parts),
            sources=merged_sources,
            chunks_used=total_chunks,
            metadata={"queries_used": variations},
        )

    except Exception as exc:
        log.exception(f"[agent_tools.search_with_multi_query] failed: {exc}")
        return ToolResult(
            tool_name="search_with_multi_query",
            status=ToolStatus.ERROR,
            content=f"Multi-query search failed: {exc}",
            sources=[],
            chunks_used=0,
        )


# ── Tool 4: search_with_self_reflection ──────────────────────────────────────

_SUFFICIENCY_PROMPT = (
    'Given this question:\n"{query}"\n\n'
    "And these retrieved chunks (summary):\n{chunks_summary}\n\n"
    "Is this sufficient to answer the question fully?\n"
    'If yes respond: {{"sufficient": true, "refined_query": null}}\n'
    'If no respond: {{"sufficient": false, "refined_query": "better search query"}}\n'
    "Respond with valid JSON only. No explanation."
)


async def search_with_self_reflection(
    query: str,
    user_context,                         # UserContext
    request,                              # FastAPI Request
    collection_ids: list[str] | None = None,
    max_iterations: int = 3,
) -> ToolResult:
    """
    Iterative search: retrieves, evaluates sufficiency,
    refines query and searches again if needed.
    Use for complex research questions.
    Max 3 iterations to bound latency.
    """
    try:
        best_result: ToolResult | None = None
        current_query = query

        for iteration in range(max_iterations):
            log.info(
                f"[agent_tools.search_with_self_reflection] "
                f"iteration {iteration + 1}/{max_iterations} query={current_query[:80]!r}"
            )

            result = await search_knowledge_base(
                query=current_query,
                user_context=user_context,
                request=request,
                collection_ids=collection_ids,
            )

            # Track the best result (most chunks)
            if best_result is None or (
                result.status == ToolStatus.SUCCESS
                and result.chunks_used > best_result.chunks_used
            ):
                best_result = result

            if result.status != ToolStatus.SUCCESS or not result.content:
                break  # nothing to reflect on

            # Build a short summary of retrieved content for the LLM (cap at 1500 chars)
            chunks_summary = result.content[:1500]

            raw = await _llm_call(
                _SUFFICIENCY_PROMPT.format(
                    query=query[:300],
                    chunks_summary=chunks_summary,
                ),
                max_tokens=150,
            )

            if not raw:
                break  # LLM unavailable — return what we have

            cleaned = _strip_json_fences(raw)
            try:
                validated = _SufficiencyResponse.model_validate_json(cleaned)
                sufficient = validated.sufficient
                refined_query = validated.refined_query
            except (ValidationError, json.JSONDecodeError, ValueError) as _e:
                log.warning(
                    f"[agent_tools.search_with_self_reflection] "
                    f"sufficiency parse failed ({_e}) — treating as sufficient"
                )
                break

            if sufficient or not refined_query or iteration == max_iterations - 1:
                break

            current_query = str(refined_query)

        if best_result is None:
            return ToolResult(
                tool_name="search_with_self_reflection",
                status=ToolStatus.EMPTY,
                content="No results found after iterative search.",
                sources=[],
                chunks_used=0,
            )

        # Overwrite tool_name so the supervisor knows which tool produced it
        best_result.tool_name = "search_with_self_reflection"
        best_result.metadata["iterations"] = max_iterations
        return best_result

    except Exception as exc:
        log.exception(f"[agent_tools.search_with_self_reflection] failed: {exc}")
        return ToolResult(
            tool_name="search_with_self_reflection",
            status=ToolStatus.ERROR,
            content=f"Self-reflection search failed: {exc}",
            sources=[],
            chunks_used=0,
        )


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS: dict[str, Callable] = {
    "search_knowledge_base":      search_knowledge_base,
    "retrieve_full_document":     retrieve_full_document,
    "search_with_multi_query":    search_with_multi_query,
    "search_with_self_reflection": search_with_self_reflection,
}


def get_tools_for_user(user_context) -> dict[str, Callable]:
    """
    Returns the tool registry for the given user.
    All tools enforce clearance internally — no filtering needed here.
    Future: restrict specific tools by role if required.
    """
    return TOOLS
