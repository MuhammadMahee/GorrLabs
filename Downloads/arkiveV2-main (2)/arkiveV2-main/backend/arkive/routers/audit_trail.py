"""Audit trail API endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from arkive.models.response_audits import ResponseAuditModel, ResponseAudits
from arkive.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.get('/trail/{message_id}', response_model=List[ResponseAuditModel])
async def get_response_trail(
    message_id: str,
    user=Depends(get_verified_user),
):
    """
    Get complete audit trail for a message (all stages).

    Returns:
        List of ResponseAuditModel, ordered by time (earliest first)

    Stages (in order):
        1. RETRIEVAL — Documents retrieved, quality scored
        2. REDACTION — Sensitive content detected and redacted
        3. MODEL_CALL — LLM invoked, response generated
        4. RESPONSE_COMPOSITION — Final response assembled with citations
        5. FINAL — Complete audit record linking all stages
    """
    trail = ResponseAudits.get_by_message_id(message_id)

    if not trail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No audit trail found for message {message_id}',
        )

    log.info(
        f'[audit_trail] retrieved trail for message={message_id} '
        f'stages={len(trail)} user={user.id}'
    )
    return trail


@router.get('/trail/{message_id}/stage/{stage_name}', response_model=ResponseAuditModel)
async def get_stage_log(
    message_id: str,
    stage_name: str,
    user=Depends(get_verified_user),
):
    """
    Get audit log for a specific stage of a message.

    Args:
        message_id: ID of the chat message
        stage_name: Stage name ('retrieval', 'redaction', 'model_call', 'response_composition', 'final')

    Returns:
        ResponseAuditModel for that stage
    """
    valid_stages = ['retrieval', 'redaction', 'model_call', 'response_composition', 'final']
    if stage_name not in valid_stages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid stage: {stage_name}. Must be one of: {", ".join(valid_stages)}',
        )

    stage_log = ResponseAudits.get_by_message_and_stage(message_id, stage_name)

    if not stage_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No {stage_name} audit log found for message {message_id}',
        )

    log.info(
        f'[audit_trail] retrieved {stage_name} stage for message={message_id} '
        f'status={stage_log.status} user={user.id}'
    )
    return stage_log


@router.get('/summary/{message_id}')
async def get_audit_summary(
    message_id: str,
    user=Depends(get_verified_user),
):
    """
    Get a summary of the audit trail for a message.

    Returns:
        {
            'message_id': str,
            'stages': {
                'stage_name': {
                    'status': 'success' | 'error',
                    'duration_ms': int,
                    'timestamp': int,
                }
            },
            'total_duration_ms': int,
            'created_at': int,
            'created_at_iso': str,
        }
    """
    trail = ResponseAudits.get_by_message_id(message_id)

    if not trail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No audit trail found for message {message_id}',
        )

    stages = {}
    total_duration = 0

    for log_entry in trail:
        duration = log_entry.duration_ms or 0
        total_duration += duration

        stages[log_entry.stage] = {
            'status': log_entry.status,
            'duration_ms': duration,
            'timestamp': log_entry.created_at,
        }

    # Convert timestamp to ISO format
    from datetime import datetime
    created_at_iso = datetime.fromtimestamp(
        trail[0].created_at / 1000
    ).isoformat() if trail else None

    response = {
        'message_id': message_id,
        'stages': stages,
        'total_duration_ms': total_duration,
        'created_at': trail[0].created_at if trail else None,
        'created_at_iso': created_at_iso,
    }

    log.info(
        f'[audit_trail] summary for message={message_id} '
        f'duration={total_duration}ms user={user.id}'
    )
    return response


@router.get('/user/{user_id}', response_model=List[ResponseAuditModel])
async def get_user_audit_logs(
    user_id: str,
    limit: int = 100,
    user=Depends(get_verified_user),
):
    """
    Get recent audit logs for a specific user.

    Args:
        user_id: User ID to get logs for
        limit: Maximum number of logs to return (default 100, max 1000)

    Returns:
        List of ResponseAuditModel, ordered by most recent first
    """
    if limit > 1000:
        limit = 1000
    if limit < 1:
        limit = 1

    logs = ResponseAudits.get_by_user_id(user_id, limit=limit)

    log.info(
        f'[audit_trail] retrieved {len(logs)} logs for user={user_id} '
        f'requested_by={user.id}'
    )
    return logs
