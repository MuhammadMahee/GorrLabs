import json
import logging
import httpx
from typing import Optional

from arkive.env import OLLAMA_BASE_URL, OLLAMA_MODEL

log = logging.getLogger(__name__)

EXTRACT_TIMEOUT = 30.0  # seconds — runs at publish time, not query time

EXTRACT_PROMPT = """You are a data privacy analyst for an enterprise platform.

Your job: identify every sensitive value in the text and return them as a JSON array.
Do NOT rewrite the text. Only find and label the sensitive spans.

For each sensitive value output:
  {{"value": "<exact substring from the text>", "type": "<TYPE>"}}

Types:
  SALARY           — salary, wage, compensation, income, pay, CTC (numeric values)
  NATIONAL_ID      — CNIC, NIC, SSN, Aadhaar, national ID of any country
  MEDICAL_CONDITION — diagnosis, disease, illness, medical condition values
  CREDENTIAL       — passwords, API keys, tokens, secrets

Important:
- Only return types from the list above. Presidio already handles emails, phones, bank accounts, credit cards, SSNs — do NOT duplicate those.
- "value" must be the EXACT substring as it appears in the text (copy-paste, no paraphrasing)
- If nothing sensitive is found, return an empty array: []
- Return ONLY valid JSON. No explanation, no markdown fences.

Text:
{text}"""
CLASSIFIER_TIMEOUT = 8.0  # seconds — never block the pipeline longer than this

CLASSIFICATION_PROMPT = """You are a data privacy classifier for an
enterprise AI platform. Your job is to detect if a query contains
sensitive information that should be restricted.

Rate the following query on this scale:
0 = Public — completely safe, no sensitive information
1 = Internal — mentions people, internal topics, company references
2 = Confidential — personal identifiers used together, private
    business information
3 = Restricted — financial IDs, government IDs (SSN, passport),
    medical records, credentials, API keys, passwords

Important rules:
- Rate based on what information is PRESENT in the query
- A question asking FOR sensitive info is not itself sensitive
- Only rate 3 if actual restricted data appears in the text
- Be conservative — when uncertain, rate lower not higher

Query to classify:
"{query}"

Respond with valid JSON only. No explanation. No markdown.
Example: {{"level": 0, "reason": "general question, no PII"}}"""


async def llm_classify(query: str) -> tuple[int, str]:
    """
    Calls the local LLM to classify query sensitivity.
    Returns (level, reason) tuple.
    Falls back to (0, "classifier unavailable") on any failure.
    Never raises — pipeline must not break if LLM is down.

    Only call this when Presidio returns level 0.
    """
    prompt = CLASSIFICATION_PROMPT.format(query=query)

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        # Reasoning-style models (qwen3, deepseek-r1) burn 200-400 tokens
        # on internal <think> before emitting JSON. 80 tokens starved them
        # and the API returned empty content; 512 is a safe headroom.
        "max_tokens": 512,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=CLASSIFIER_TIMEOUT) as client:
            content = None

            try:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise

                # Older/non-OpenAI-compatible Ollama builds expose /api/chat instead.
                native_payload = {
                    "model": OLLAMA_MODEL,
                    "messages": payload["messages"],
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                    },
                }
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json=native_payload,
                )
                response.raise_for_status()
                data = response.json()
                content = (data.get("message", {}) or {}).get("content", "").strip()

            if not content:
                return 0, "classifier empty response"

            # Strip any markdown fences the model adds despite instructions
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            parsed = json.loads(content)
            level = int(parsed.get("level", 0))
            reason = str(parsed.get("reason", "llm classification"))

            # Clamp to valid range
            level = max(0, min(3, level))

            log.debug(
                f"[llm_classifier] level={level} reason={reason!r}"
            )
            return level, reason

    except httpx.TimeoutException:
        log.warning("[llm_classifier] timeout — falling back to level 0")
        return 0, "classifier timeout"
    except json.JSONDecodeError as e:
        log.warning(f"[llm_classifier] invalid JSON response: {e}")
        return 0, "classifier parse error"
    except Exception as e:
        log.warning(f"[llm_classifier] unexpected error: {e}")
        return 0, "classifier unavailable"


async def llm_extract_entities(text: str) -> list[dict]:
    """
    Asks the LLM to identify sensitive spans Presidio misses (salary values,
    medical conditions, country-specific IDs, etc.) and returns them as a list
    of entity dicts compatible with scan_chunk_entities() output:

        {"type": RedactedEntityType, "start": int, "end": int,
         "confidence": float, "source": "llm"}

    The caller merges this list with Presidio detections and passes the combined
    result to redact_chunk() — the LLM never rewrites the document itself.
    Falls back to [] on any failure. Never raises.
    """
    if not text or not text.strip():
        return []

    prompt = EXTRACT_PROMPT.format(text=text)
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": False,
    }

    _TYPE_MAP = {
        "SALARY":            "SALARY",
        "NATIONAL_ID":       "NATIONAL_ID",
        "MEDICAL_CONDITION": "MEDICAL_CONDITION",
        "CREDENTIAL":        "CREDENTIAL",
    }

    raw_content = None
    try:
        async with httpx.AsyncClient(timeout=EXTRACT_TIMEOUT) as client:
            try:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                raw_content = response.json()["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise
                native_payload = {
                    "model": OLLAMA_MODEL,
                    "messages": payload["messages"],
                    "stream": False,
                    "options": {"temperature": 0.0},
                }
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json=native_payload,
                )
                response.raise_for_status()
                raw_content = (response.json().get("message", {}) or {}).get("content", "").strip()

        if not raw_content:
            return []

        # Strip markdown fences the model may add despite instructions
        if "```" in raw_content:
            raw_content = raw_content.split("```")[1]
            if raw_content.startswith("json"):
                raw_content = raw_content[4:]
        raw_content = raw_content.strip()

        items = json.loads(raw_content)
        if not isinstance(items, list):
            return []

        entities = []
        for item in items:
            value = (item.get("value") or "").strip()
            entity_type = _TYPE_MAP.get((item.get("type") or "").upper())
            if not value or not entity_type:
                continue

            # Find every occurrence of this exact value in the text
            start = 0
            while True:
                pos = text.find(value, start)
                if pos == -1:
                    break
                entities.append({
                    "type":       entity_type,
                    "start":      pos,
                    "end":        pos + len(value),
                    "confidence": 0.9,
                    "source":     "llm",
                })
                start = pos + len(value)

        log.debug(f"[llm_extract_entities] found {len(entities)} entities in {len(text)} chars")
        return entities

    except httpx.TimeoutException:
        log.warning("[llm_extract_entities] timeout — skipping LLM pass")
        return []
    except json.JSONDecodeError as e:
        log.warning(f"[llm_extract_entities] invalid JSON from model: {e} | raw={raw_content!r:.200}")
        return []
    except Exception as e:
        log.warning(f"[llm_extract_entities] unexpected error: {e}")
        return []
