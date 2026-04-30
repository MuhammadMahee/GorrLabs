import asyncio
import logging
import httpx

from arkive.env import OLLAMA_BASE_URL, OLLAMA_MODEL

log = logging.getLogger(__name__)

ENRICHMENT_TIMEOUT = 30.0
ENRICHMENT_CONCURRENCY = 5  # max parallel Ollama calls

ENRICHMENT_PROMPT = """You are an expert document indexing system optimized for semantic search and retrieval.

Task:
Generate a precise 1–2 sentence description of the provided content, explicitly connecting it to the document titled "{document_title}".

Requirements:
- Clearly state the main topic and intent of the content.
- Include important entities (e.g., names, concepts, technologies, locations) when present.
- Explain how this content contributes to the overall document (e.g., introduces, defines, analyzes, compares, or concludes).
- Use concrete, information-dense language suitable for search indexing.
- Avoid vague phrasing, filler, or generic summaries.

Constraints:
- Do NOT refer to the text as "this chunk", "this section", etc.
- Do NOT repeat the document title verbatim unless necessary for clarity.
- Do NOT exceed 2 sentences.
- Output must be standalone and interpretable without additional context.

---

Examples:

Document Title: "Introduction to Machine Learning"

Content:
"Supervised learning is a type of machine learning where models are trained on labeled data to predict outputs from inputs."

Good Output:
"Defines supervised learning as a machine learning approach using labeled datasets to map inputs to outputs, forming a foundational concept in the document’s introduction to learning paradigms."

Bad Output:
"This section explains supervised learning."
→ Too vague, no entities, no role in document.

---

Document Title: "Blockchain Fundamentals"

Content:
"Ethereum introduced smart contracts, enabling decentralized applications (dApps) to run without intermediaries."

Good Output:
"Explains Ethereum’s introduction of smart contracts, highlighting their role in enabling decentralized applications (dApps) without intermediaries within the broader discussion of blockchain capabilities."

Bad Output:
"Ethereum and smart contracts are discussed."
→ Missing purpose, weak phrasing, no contextual role.

---

Document Title: "Climate Change Impacts"

Content:
"Rising global temperatures have led to increased frequency of extreme weather events, including hurricanes, droughts, and wildfires."

Good Output:
"Analyzes the impact of rising global temperatures on the increased frequency of extreme weather events such as hurricanes, droughts, and wildfires, supporting the document’s examination of climate change consequences."

Bad Output:
"Talks about climate change effects."
→ Generic, no detail, not useful for retrieval.

---

Content:
{chunk_content}

Output:
"""

async def _enrich_single_chunk(
    chunk_content: str,
    document_title: str,
    semaphore: asyncio.Semaphore,
) -> str:
    """
    Calls Ollama to generate a context description for one chunk.
    Prepends the description to the chunk content.
    Falls back to original chunk content on any failure.
    Never raises.
    """
    async with semaphore:
        try:
            prompt = ENRICHMENT_PROMPT.format(
                document_title=document_title,
                chunk_content=chunk_content[:2000],
            )

            openai_payload = {
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0.0,
                "keep_alive": -1,
            }

            native_payload = {
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.0},
                "keep_alive": -1,
            }

            context_summary = None

            async with httpx.AsyncClient(timeout=ENRICHMENT_TIMEOUT) as client:
                _max_attempts = 4
                for attempt in range(_max_attempts):
                    try:
                        response = await client.post(
                            f"{OLLAMA_BASE_URL}/v1/chat/completions",
                            json=openai_payload,
                        )
                        response.raise_for_status()
                        data = response.json()
                        context_summary = (
                            data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                            .strip()
                        )
                        break
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 500:
                            if attempt < _max_attempts - 1:
                                wait = 2 ** attempt  # 1s, 2s, 4s
                                log.warning(
                                    f"[enricher] 500 on attempt {attempt + 1} "
                                    f"— retrying in {wait}s"
                                )
                                await asyncio.sleep(wait)
                                continue
                            raise
                        if e.response.status_code != 404:
                            raise
                        # Fall back to native Ollama /api/chat endpoint
                        response = await client.post(
                            f"{OLLAMA_BASE_URL}/api/chat",
                            json=native_payload,
                        )
                        response.raise_for_status()
                        data = response.json()
                        context_summary = (
                            (data.get("message") or {})
                            .get("content", "")
                            .strip()
                        )
                        break

            if not context_summary:
                return chunk_content

            enriched = f"{context_summary}\n\n{chunk_content}"
            log.debug(
                f"[enricher] enriched chunk "
                f"({len(chunk_content)} → {len(enriched)} chars)"
            )
            return enriched

        except httpx.TimeoutException:
            log.warning("[enricher] timeout — using original chunk")
            return chunk_content
        except Exception as e:
            log.warning(f"[enricher] failed: {e} — using original chunk")
            return chunk_content


async def enrich_chunks(
    docs: list,
    document_title: str,
) -> list:
    """
    Enriches a list of document chunks in parallel (max ENRICHMENT_CONCURRENCY
    concurrent Ollama calls).

    docs: chunked Document list from save_docs_to_vector_db().
          Each item is a langchain Document with .page_content (str)
          and .metadata (dict).

    document_title: injected into the prompt so the LLM knows which
                    document the chunk belongs to. Pass
                    doc.metadata.get('name', 'Unknown Document').

    Returns the same list with .page_content updated in-place.
    If enrichment fails for any chunk, that chunk is unchanged.
    If enrichment fails entirely, returns docs unchanged.
    Never raises.
    """
    if not docs:
        return docs

    semaphore = asyncio.Semaphore(ENRICHMENT_CONCURRENCY)

    try:
        enriched_contents = await asyncio.gather(
            *[
                _enrich_single_chunk(
                    chunk_content=doc.page_content,
                    document_title=document_title,
                    semaphore=semaphore,
                )
                for doc in docs
            ],
            return_exceptions=True,
        )

        for doc, result in zip(docs, enriched_contents):
            if isinstance(result, Exception):
                log.warning(
                    f"[enricher] chunk failed with exception: {result}"
                    " — keeping original"
                )
            elif isinstance(result, str):
                doc.page_content = result

        enriched_count = sum(
            1 for r in enriched_contents
            if isinstance(r, str) and r
        )
        log.info(
            f"[enricher] enriched {enriched_count}/{len(docs)} chunks "
            f"from '{document_title}'"
        )

    except Exception as e:
        log.exception(
            f"[enricher] batch enrichment failed: {e} "
            "— returning original chunks"
        )

    return docs
