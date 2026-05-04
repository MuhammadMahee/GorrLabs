"""
Amazon Bedrock router.
Uses httpx with Bearer token auth (Bedrock API Key format).
Streaming uses AWS Event Stream binary frame parsing.
"""

import asyncio
import json
import logging
import struct
import time
import urllib.parse
import uuid
from typing import AsyncIterator

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from arkive.utils.auth import get_verified_user
from arkive.env import (
    AWS_BEDROCK_MODEL,
    AWS_BEDROCK_REGION,
    AWS_BEDROCK_ENDPOINT_URL,
    ENABLE_BEDROCK_API,
    AWS_BEDROCK_API_KEY,
)

log = logging.getLogger(__name__)
router = APIRouter()


def _bedrock_url(model_id: str, operation: str) -> str:
    base = AWS_BEDROCK_ENDPOINT_URL.rstrip('/') if AWS_BEDROCK_ENDPOINT_URL else f'https://bedrock-runtime.{AWS_BEDROCK_REGION}.amazonaws.com'
    return f'{base}/model/{urllib.parse.quote(model_id, safe="")}/{operation}'


def _auth_headers() -> dict:
    return {
        'Authorization': f'Bearer {AWS_BEDROCK_API_KEY}',
        'Content-Type': 'application/json',
    }


def _to_bedrock_messages(openai_messages: list[dict]) -> tuple[list[dict], list[dict]]:
    system_blocks, turns = [], []
    for msg in openai_messages:
        role = msg.get('role', '')
        content = msg.get('content', '')
        if role == 'system':
            text = content if isinstance(content, str) else ' '.join(
                p.get('text', '') for p in content if isinstance(p, dict)
            )
            system_blocks.append({'text': text})
        else:
            bedrock_role = 'user' if role == 'user' else 'assistant'
            if isinstance(content, str):
                turns.append({'role': bedrock_role, 'content': [{'text': content}]})
            elif isinstance(content, list):
                text_parts = [p.get('text', '') for p in content if p.get('type') == 'text']
                turns.append({'role': bedrock_role, 'content': [{'text': ' '.join(text_parts)}]})
    return system_blocks, turns


def _openai_response(model_id: str, content: str, in_tokens: int, out_tokens: int) -> dict:
    return {
        'id': f'chatcmpl-{uuid.uuid4().hex}',
        'object': 'chat.completion',
        'created': int(time.time()),
        'model': model_id,
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
        'usage': {'prompt_tokens': in_tokens, 'completion_tokens': out_tokens, 'total_tokens': in_tokens + out_tokens},
    }


def _parse_event_headers(data: bytes) -> dict:
    """Parse AWS Event Stream binary header block into a dict."""
    headers = {}
    pos = 0
    while pos < len(data):
        if pos >= len(data):
            break
        name_len = data[pos]; pos += 1
        if pos + name_len > len(data):
            break
        name = data[pos:pos + name_len].decode('utf-8', errors='replace'); pos += name_len
        if pos >= len(data):
            break
        value_type = data[pos]; pos += 1
        if value_type == 7:  # string
            if pos + 2 > len(data):
                break
            value_len = struct.unpack('>H', data[pos:pos + 2])[0]; pos += 2
            value = data[pos:pos + value_len].decode('utf-8', errors='replace'); pos += value_len
            headers[name] = value
        elif value_type in (0, 1):
            headers[name] = value_type == 0
        elif value_type == 2:
            headers[name] = data[pos]; pos += 1
        elif value_type == 3:
            headers[name] = struct.unpack('>h', data[pos:pos + 2])[0]; pos += 2
        elif value_type == 4:
            headers[name] = struct.unpack('>i', data[pos:pos + 4])[0]; pos += 4
        elif value_type == 5:
            headers[name] = struct.unpack('>q', data[pos:pos + 8])[0]; pos += 8
        elif value_type in (6, 9):
            if pos + 2 > len(data):
                break
            value_len = struct.unpack('>H', data[pos:pos + 2])[0]; pos += 2
            headers[name] = data[pos:pos + value_len]; pos += value_len
        elif value_type == 8:
            headers[name] = struct.unpack('>q', data[pos:pos + 8])[0]; pos += 8
        else:
            break
    return headers


def _parse_event_frames(data: bytes) -> tuple[list[dict], bytes]:
    """
    Parse complete AWS Event Stream frames from data.
    Returns (events_as_boto3_dicts, remaining_incomplete_bytes).
    Each event is {event_type: payload_dict}, matching boto3's converse_stream format.
    """
    events = []
    pos = 0
    while pos + 12 <= len(data):
        total_length = struct.unpack('>I', data[pos:pos + 4])[0]
        if total_length < 16 or pos + total_length > len(data):
            break  # incomplete frame — wait for more bytes
        header_length = struct.unpack('>I', data[pos + 4:pos + 8])[0]
        headers_bytes = data[pos + 12:pos + 12 + header_length]
        payload_bytes = data[pos + 12 + header_length:pos + total_length - 4]

        headers = _parse_event_headers(headers_bytes)
        event_type = headers.get(':event-type', '')
        message_type = headers.get(':message-type', 'event')

        if payload_bytes:
            try:
                payload = json.loads(payload_bytes)
                if message_type == 'exception':
                    events.append({'__exception__': payload, '__exception_type__': event_type})
                elif event_type:
                    events.append({event_type: payload})
            except Exception:
                pass

        pos += total_length
    return events, data[pos:]


async def _stream_sse(model_id: str, turns: list, system_blocks: list, inference_config: dict) -> AsyncIterator[str]:
    url = _bedrock_url(model_id, 'converse-stream')
    body: dict = {'messages': turns, 'inferenceConfig': inference_config}
    if system_blocks:
        body['system'] = system_blocks

    headers = {**_auth_headers(), 'Accept': 'application/vnd.amazon.eventstream'}
    completion_id = f'chatcmpl-{uuid.uuid4().hex}'
    created = int(time.time())

    log.info(f'[bedrock] POST {url}')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10)) as client:
            async with client.stream('POST', url, json=body, headers=headers) as response:
                if response.status_code != 200:
                    raw = await response.aread()
                    log.error(f'[bedrock] stream HTTP {response.status_code}: {raw[:500]}')
                    raise HTTPException(
                        status_code=502,
                        detail=f'Bedrock {response.status_code}: {raw[:300].decode(errors="replace")}',
                    )

                buffer = b''
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    buffer += chunk
                    events, buffer = _parse_event_frames(buffer)
                    for event in events:
                        if '__exception__' in event:
                            msg = str(event['__exception__'])
                            log.error(f'[bedrock] stream exception event: {msg}')
                            raise HTTPException(status_code=502, detail=f'Bedrock error: {msg}')
                        if 'contentBlockDelta' in event:
                            text = event['contentBlockDelta'].get('delta', {}).get('text', '')
                            if text:
                                yield f'data: {json.dumps({"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model_id, "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]})}\n\n'
                        elif 'messageStop' in event:
                            yield f'data: {json.dumps({"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model_id, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})}\n\n'
                            yield 'data: [DONE]\n\n'
                            return
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f'[bedrock] stream error: {exc}', exc_info=True)
        raise HTTPException(status_code=502, detail=f'Bedrock streaming error: {exc}')


async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user=None,
    bypass_system_prompt: bool = False,
):
    if not ENABLE_BEDROCK_API:
        raise HTTPException(status_code=503, detail='Bedrock API is disabled')
    if not AWS_BEDROCK_API_KEY:
        raise HTTPException(status_code=503, detail='AWS_BEDROCK_API_KEY not configured')

    model_id = form_data.get('model', AWS_BEDROCK_MODEL)
    system_blocks, turns = _to_bedrock_messages(form_data.get('messages', []))
    stream = form_data.get('stream', False)

    inference_config: dict = {'maxTokens': 2048}
    if form_data.get('max_tokens'):
        inference_config['maxTokens'] = int(form_data['max_tokens'])
    if form_data.get('temperature') is not None:
        inference_config['temperature'] = float(form_data['temperature'])
    if form_data.get('top_p') is not None:
        inference_config['topP'] = float(form_data['top_p'])

    if stream:
        return StreamingResponse(
            _stream_sse(model_id, turns, system_blocks, inference_config),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
        )

    # Non-streaming
    url = _bedrock_url(model_id, 'converse')
    body: dict = {'messages': turns, 'inferenceConfig': inference_config}
    if system_blocks:
        body['system'] = system_blocks

    log.info(f'[bedrock] POST {url}')
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=body, headers=_auth_headers())
        if response.status_code != 200:
            log.error(f'[bedrock] converse HTTP {response.status_code}: {response.text[:500]}')
            raise HTTPException(
                status_code=502,
                detail=f'Bedrock {response.status_code}: {response.text[:300]}',
            )
        data = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Bedrock error: {exc}') from exc

    content = ''.join(
        b.get('text', '') for b in data.get('output', {}).get('message', {}).get('content', [])
    )
    usage = data.get('usage', {})
    return _openai_response(model_id, content, usage.get('inputTokens', 0), usage.get('outputTokens', 0))


async def get_all_models():
    if not ENABLE_BEDROCK_API or not AWS_BEDROCK_MODEL:
        return {'models': []}
    name = AWS_BEDROCK_MODEL.split('/')[-1].replace('-', ' ').replace('.', ' ').title()
    return {'models': [{'model': AWS_BEDROCK_MODEL, 'name': name, 'modified_at': '', 'size': 0, 'digest': '', 'details': {}, 'connection_type': 'external'}]}


@router.get('/api/tags')
async def get_bedrock_tags(user=Depends(get_verified_user)):
    return await get_all_models()
