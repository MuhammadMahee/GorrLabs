"""Confidence scores API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from arkive.models.confidence_scores import ConfidenceScoreModel, ConfidenceScores
from arkive.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.get('/scores/{audit_log_id}', response_model=ConfidenceScoreModel)
async def get_confidence_score(
    audit_log_id: str,
    user=Depends(get_verified_user),
):
    """
    Get confidence score for a specific response audit log.

    Returns:
        ConfidenceScoreModel with all metrics
    """
    try:
        import uuid
        audit_id = uuid.UUID(audit_log_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid audit_log_id format',
        )

    score = ConfidenceScores.get_by_audit_log_id(audit_id)

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Confidence score not found for audit log {audit_log_id}',
        )

    log.info(
        f'[confidence] retrieved score for audit_log={audit_log_id} '
        f'user={user.id}'
    )
    return score


@router.get('/scores/breakdown/{message_id}')
async def get_score_breakdown(
    message_id: str,
    user=Depends(get_verified_user),
):
    """
    Get detailed confidence score breakdown for a message.

    Returns:
        {
            'score': float,
            'breakdown': {
                'source_quality': {'value': float, 'weight': float},
                'fact_check': {'value': float, 'weight': float},
                'classification': {'value': float, 'weight': float},
            },
            'interpretation': str,
            'created_at': int,
        }
    """
    scores = ConfidenceScores.get_by_message_id(message_id)

    if not scores:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'No confidence scores found for message {message_id}',
        )

    # Return the most recent score with full breakdown
    latest = scores[0]

    response = {
        'score': latest.final_confidence,
        'breakdown': {
            'source_quality': {
                'value': latest.source_quality_score,
                'weight': 0.4,
            },
            'fact_check': {
                'value': latest.fact_check_score,
                'weight': 0.4,
            },
            'classification': {
                'value': latest.classification_score,
                'weight': 0.2,
            },
        },
        'interpretation': _interpret_confidence(latest.final_confidence),
        'created_at': latest.created_at,
    }

    log.info(
        f'[confidence] retrieved breakdown for message={message_id} '
        f'score={latest.final_confidence:.2f} user={user.id}'
    )
    return response


@router.get('/average/{user_id}')
async def get_average_confidence(
    user_id: str,
    days: int = 7,
    user=Depends(get_verified_user),
):
    """
    Get average confidence score for a user over the last N days.

    Useful for analytics and monitoring response quality.

    Args:
        user_id: User ID to get average for
        days: Number of days to look back (default 7)

    Returns:
        {
            'average_confidence': float,
            'days': int,
            'user_id': str,
        }
    """
    avg = ConfidenceScores.get_average_score(user_id, days)

    if avg is None:
        return {
            'average_confidence': None,
            'days': days,
            'user_id': user_id,
            'message': 'No confidence scores found for this period',
        }

    log.info(
        f'[confidence] average for user={user_id} days={days} avg={avg:.2f}'
    )
    return {
        'average_confidence': avg,
        'days': days,
        'user_id': user_id,
    }


def _interpret_confidence(score: float) -> str:
    """Get human-readable interpretation of confidence score."""
    if score >= 0.85:
        return '✅ High confidence — well-supported by sources'
    elif score >= 0.65:
        return '⚠️ Moderate confidence — reasonably supported'
    elif score >= 0.45:
        return '⚠️ Low confidence — limited support'
    else:
        return '❌ Very low confidence — may be unreliable'
