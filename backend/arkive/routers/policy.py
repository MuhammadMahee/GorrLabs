import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from arkive.models.pending_reviews import PendingReviewModel, PendingReviews
from arkive.utils.auth import get_admin_user, get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.get('/reviews', response_model=list[PendingReviewModel])
async def list_reviews(
    status: Optional[str] = None,
    user=Depends(get_admin_user),
):
    """List review queue. status=pending|approved|rejected, or all if omitted."""
    return PendingReviews.list_all(status=status)


@router.post('/reviews/{review_id}/approve', response_model=PendingReviewModel)
async def approve_review(
    review_id: str,
    user=Depends(get_admin_user),
):
    """
    Approve a pending review. The user's original query hash is marked
    approved for 24 hours — any re-submission within that window proceeds
    without re-flagging.
    """
    result = PendingReviews.update_status(
        review_id=review_id,
        status='approved',
        reviewed_by=user.id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Review {review_id} not found',
        )
    log.info(
        f'[policy_review] review_id={review_id} approved by admin={user.id}'
    )
    return result


@router.post('/reviews/{review_id}/reject', response_model=PendingReviewModel)
async def reject_review(
    review_id: str,
    user=Depends(get_admin_user),
):
    """
    Reject a pending review. The query remains blocked — user will
    receive a 403 if they re-submit.
    """
    result = PendingReviews.update_status(
        review_id=review_id,
        status='rejected',
        reviewed_by=user.id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Review {review_id} not found',
        )
    log.info(
        f'[policy_review] review_id={review_id} rejected by admin={user.id}'
    )
    return result
