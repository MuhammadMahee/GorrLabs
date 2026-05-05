"""
Public entry point for Solana audit anchoring.

All model files import from this module only.
Never import tasks, client, or normalizer directly
from outside the solana/ package.

Usage:
    from arkive.solana.anchor import anchor_audit_event

    anchor_audit_event(
        event_type="policy_decision",
        event_id=str(inserted.id),
        payload={...},
    )
"""

from arkive.solana.tasks import fire_and_forget


def anchor_audit_event(
    event_type: str,
    event_id: str,
    payload: dict,
) -> None:
    """
    Public entry point for anchoring any audit event.

    Schedules a background Solana memo transaction
    for the given event. Never blocks. Never raises.
    Safe to call from any model insert function.

    Args:
        event_type: One of the 18 supported event
                    type strings (e.g. "policy_decision")
        event_id:   String form of the source record
                    primary key
        payload:    Dict produced by the matching
                    payload_{event_type}() function
                    from payloads.py
    """
    try:
        fire_and_forget(
            event_type=event_type,
            event_id=event_id,
            payload=payload,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            f"[anchor] anchor_audit_event failed to "
            f"schedule: event_type={event_type} "
            f"event_id={event_id} error={exc}"
        )
