"""
Admin-only endpoints for the Solana audit anchor Trust Console.

Endpoints:
    GET /api/v1/audit/anchors          list + filter + paginate
    GET /api/v1/audit/anchors/stats    aggregate counts
    GET /api/v1/audit/anchors/{id}/verify  on-chain presence check
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from arkive.solana.models import AuditAnchors
from arkive.solana.client import get_client
from arkive.utils.auth import get_admin_user

log = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AnchorItem(BaseModel):
    id: str
    event_type: str
    event_id: str
    event_hash: str
    tx_id: Optional[str]
    anchored_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AnchorListResponse(BaseModel):
    anchors: list[AnchorItem]
    total: int
    page: int
    page_size: int


class AnchorStatsResponse(BaseModel):
    total: int
    anchored: int
    pending: int
    by_event_type: dict[str, int]


class VerifyResponse(BaseModel):
    anchor_id: str
    tx_id: Optional[str]
    on_chain: bool
    memo: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get('/anchors', response_model=AnchorListResponse)
async def list_anchors(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None),
    anchored: Optional[bool] = Query(None, description='true=anchored, false=pending'),
    user=Depends(get_admin_user),
):
    rows, total = AuditAnchors.get_all(
        page=page,
        page_size=page_size,
        event_type=event_type,
        anchored=anchored,
    )
    return AnchorListResponse(
        anchors=[AnchorItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get('/anchors/stats', response_model=AnchorStatsResponse)
async def get_anchor_stats(user=Depends(get_admin_user)):
    stats = AuditAnchors.get_stats()
    return AnchorStatsResponse(**stats)


@router.get('/anchors/{anchor_id}/verify', response_model=VerifyResponse)
async def verify_anchor(anchor_id: str, user=Depends(get_admin_user)):
    record = AuditAnchors.get_by_id(anchor_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Anchor {anchor_id} not found',
        )

    if not record.tx_id:
        return VerifyResponse(
            anchor_id=anchor_id,
            tx_id=None,
            on_chain=False,
        )

    try:
        client = get_client()
        memo = await client.fetch_memo(record.tx_id)
        on_chain = memo is not None
    except Exception as exc:
        log.warning(f'[audit_viewer] verify failed anchor_id={anchor_id}: {exc}')
        return VerifyResponse(
            anchor_id=anchor_id,
            tx_id=record.tx_id,
            on_chain=False,
        )

    return VerifyResponse(
        anchor_id=anchor_id,
        tx_id=record.tx_id,
        on_chain=on_chain,
        memo=memo,
    )
