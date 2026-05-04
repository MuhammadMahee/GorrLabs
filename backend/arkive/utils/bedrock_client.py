"""
Shared async Bedrock helper for internal backend tasks.
Uses httpx with Bearer token (Bedrock API Key format).
"""

import asyncio
import logging

import httpx

from arkive.env import (
    AWS_BEDROCK_API_KEY,
    AWS_BEDROCK_REGION,
    AWS_BEDROCK_MODEL,
    AWS_BEDROCK_ENDPOINT_URL,
    ENABLE_BEDROCK_API,
)

log = logging.getLogger(__name__)


def _bedrock_url(operation: str) -> str:
    base = AWS_BEDROCK_ENDPOINT_URL.rstrip('/') if AWS_BEDROCK_ENDPOINT_URL else f'https://bedrock-runtime.{AWS_BEDROCK_REGION}.amazonaws.com'
    import urllib.parse
    return f'{base}/model/{urllib.parse.quote(AWS_BEDROCK_MODEL, safe="")}/{operation}'


def _call_sync(prompt: str, max_tokens: int, temperature: float) -> str:
    import httpx as _httpx
    url = _bedrock_url('converse')
    body = {
        'messages': [{'role': 'user', 'content': [{'text': prompt}]}],
        'inferenceConfig': {'maxTokens': max_tokens, 'temperature': temperature},
    }
    headers = {
        'Authorization': f'Bearer {AWS_BEDROCK_API_KEY}',
        'Content-Type': 'application/json',
    }
    response = _httpx.post(url, json=body, headers=headers, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f'Bedrock {response.status_code}: {response.text[:300]}')
    data = response.json()
    blocks = data.get('output', {}).get('message', {}).get('content', [])
    return ''.join(b.get('text', '') for b in blocks).strip()


async def bedrock_llm_call(
    prompt: str,
    max_tokens: int = 512,
    temperature: float = 0.0,
    timeout: float = 120.0,
) -> str:
    """Async wrapper. Returns text. Returns '' on failure. Never raises."""
    if not ENABLE_BEDROCK_API or not AWS_BEDROCK_API_KEY:
        return ''
    try:
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, _call_sync, prompt, max_tokens, temperature),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        log.warning(f'[bedrock_client] timeout after {timeout}s')
        return ''
    except Exception as exc:
        log.warning(f'[bedrock_client] error: {exc}')
        return ''
