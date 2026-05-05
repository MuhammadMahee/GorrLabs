"""Background task entry points for Solana audit anchoring.

The rest of the application should call fire_and_forget() and move on. This
module intentionally treats anchoring as best-effort: Solana, database, or
serialization failures are logged and never raised to the request pipeline.
"""

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from arkive.solana.client import get_client
from arkive.solana.models import AuditAnchor, AuditAnchors
from arkive.solana.normalizer import hash_event, normalize_and_hash

log = logging.getLogger(__name__)

_BACKGROUND_LOOP: Optional[asyncio.AbstractEventLoop] = None
_BACKGROUND_LOOP_LOCK = threading.Lock()

# Maps event_type to the payload field that
# contains the single most meaningful
# non-sensitive descriptor for that event.
# This becomes the key_field in the memo string.
# Never map to user_id, email, or any PII field.
_KEY_FIELD_MAP: dict[str, str] = {
    'http_request': 'method',
    'auth_event': 'event',
    'api_key_usage': 'key_id',
    'user_activity': 'change_type',
    'chat_event': 'event_type',
    'chat_message': 'model_id',
    'policy_decision': 'decision',
    'pending_review': 'status',
    'user_feedback': 'rating',
    'document_classification': 'sensitivity_level',
    'knowledge_base_event': 'event_type',
    'file_upload': 'content_type',
    'channel_event': 'event_type',
    'channel_membership': 'event_type',
    'message_event': 'reaction_count',
    'oauth_session': 'provider',
    'prompt_history': 'version',
    'access_grant': 'permission_level',
    'analytics_snapshot': 'model_id',
    'trace_event': 'operation_name',
}


async def anchor_event(
    event_type: str,
    event_id: str,
    payload: dict,
) -> None:
    """Normalize, store, and submit one audit event hash to Solana."""
    try:
        canonical, event_hash = normalize_and_hash(event_type, payload)
        anchor = AuditAnchors.insert(event_type, event_id, event_hash, canonical)
        if anchor is None:
            log.info(
                '[solana_anchor] failed to insert anchor event_type=%s event_id=%s',
                event_type,
                event_id,
            )
            return

        # Extract key_field from payload using the map.
        # Fall back to "unknown" if field missing.
        _key_field_name = _KEY_FIELD_MAP.get(
            event_type, 'unknown'
        )
        _key_field_value = str(
            payload.get(_key_field_name, 'unknown')
        )

        # Extract sensitivity_level if present in payload.
        # Default 0 - non-sensitive events have no level field.
        _sensitivity = int(
            payload.get('sensitivity_level', 0) or 0
        )

        tx_id = await get_client().anchor(
            hash_str=event_hash,
            event_type=event_type,
            key_field=_key_field_value,
            sensitivity_level=_sensitivity,
        )
        if tx_id is None:
            log.info(
                '[solana_anchor] submission failed event_type=%s event_id=%s anchor_id=%s',
                event_type,
                event_id,
                anchor.id,
            )
            return

        AuditAnchors.mark_anchored(anchor.id, tx_id, datetime.now(timezone.utc))
        log.info(
            '[solana_anchor] anchored event_type=%s event_id=%s anchor_id=%s tx_id=%s',
            event_type,
            event_id,
            anchor.id,
            tx_id,
        )
    except Exception as e:
        log.info(
            '[solana_anchor] anchor_event failed event_type=%s event_id=%s error=%s',
            event_type,
            event_id,
            e,
        )


async def retry_unanchored(limit: int = 100) -> None:
    """Retry Solana submission for stored rows that do not have tx_id yet."""
    try:
        anchors = AuditAnchors.get_unanchored(limit=limit)
        if not anchors:
            log.info('[solana_anchor] retry sweep found no unanchored rows')
            return

        for anchor in anchors:
            await _retry_anchor(anchor)
    except Exception as e:
        log.info('[solana_anchor] retry sweep failed error=%s', e)


def fire_and_forget(
    event_type: str,
    event_id: str,
    payload: dict,
) -> None:
    """Schedule audit anchoring without awaiting or raising to the caller."""
    try:
        task = asyncio.create_task(anchor_event(event_type, event_id, payload))
        task.add_done_callback(_log_task_exception)
    except RuntimeError:
        try:
            loop = _get_background_loop()
            loop.call_soon_threadsafe(
                _schedule_on_background_loop,
                event_type,
                event_id,
                payload,
            )
        except Exception as e:
            log.info(
                '[solana_anchor] failed to schedule background task event_type=%s event_id=%s error=%s',
                event_type,
                event_id,
                e,
            )
    except Exception as e:
        log.info(
            '[solana_anchor] failed to schedule task event_type=%s event_id=%s error=%s',
            event_type,
            event_id,
            e,
        )


async def _retry_anchor(anchor: AuditAnchor) -> None:
    try:
        event_hash = hash_event(anchor.canonical)
        tx_id = await get_client().anchor(event_hash)
        if tx_id is None:
            log.info(
                '[solana_anchor] retry failed event_type=%s event_id=%s anchor_id=%s',
                anchor.event_type,
                anchor.event_id,
                anchor.id,
            )
            return

        AuditAnchors.mark_anchored(anchor.id, tx_id, datetime.now(timezone.utc))
        log.info(
            '[solana_anchor] retry anchored event_type=%s event_id=%s anchor_id=%s tx_id=%s',
            anchor.event_type,
            anchor.event_id,
            anchor.id,
            tx_id,
        )
    except Exception as e:
        log.info(
            '[solana_anchor] retry failed event_type=%s event_id=%s anchor_id=%s error=%s',
            getattr(anchor, 'event_type', None),
            getattr(anchor, 'event_id', None),
            getattr(anchor, 'id', None),
            e,
        )


def _get_background_loop() -> asyncio.AbstractEventLoop:
    global _BACKGROUND_LOOP

    with _BACKGROUND_LOOP_LOCK:
        if _BACKGROUND_LOOP and _BACKGROUND_LOOP.is_running():
            return _BACKGROUND_LOOP

        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=_run_background_loop,
            args=(loop,),
            name='solana-audit-anchor-loop',
            daemon=True,
        )
        thread.start()
        _BACKGROUND_LOOP = loop
        return loop


def _run_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _schedule_on_background_loop(event_type: str, event_id: str, payload: dict) -> None:
    try:
        task = asyncio.create_task(anchor_event(event_type, event_id, payload))
        task.add_done_callback(_log_task_exception)
    except Exception as e:
        log.info(
            '[solana_anchor] background loop scheduling failed event_type=%s event_id=%s error=%s',
            event_type,
            event_id,
            e,
        )


def _log_task_exception(task: asyncio.Task) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        log.info('[solana_anchor] background task cancelled')
    except Exception as e:
        log.info('[solana_anchor] unhandled background task error=%s', e)
