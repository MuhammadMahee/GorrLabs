import logging
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, Integer, Text
from sqlalchemy.dialects.postgresql import UUID

from arkive.internal.db import Base, get_db_context

log = logging.getLogger(__name__)


class PendingReview(Base):
    __tablename__ = 'pending_reviews'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Text, nullable=False)
    query_hash = Column(Text, nullable=False)
    query_preview = Column(Text, nullable=True)
    sensitivity_level = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default='pending')
    created_at = Column(BigInteger, nullable=False)
    reviewed_by = Column(Text, nullable=True)
    reviewed_at = Column(BigInteger, nullable=True)
    policy_decision_id = Column(UUID(as_uuid=True), nullable=True)


class PendingReviewModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    query_hash: str
    query_preview: Optional[str] = None
    sensitivity_level: int
    reason: Optional[str] = None
    status: str
    created_at: int
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[int] = None
    policy_decision_id: Optional[uuid.UUID] = None


class PendingReviewsTable:
    def insert(
        self,
        user_id: str,
        query_hash: str,
        query_preview: str,
        sensitivity_level: int,
        reason: str,
        policy_decision_id: Optional[uuid.UUID] = None,
    ) -> Optional[PendingReviewModel]:
        try:
            with get_db_context() as db:
                record = PendingReview(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    query_hash=query_hash,
                    query_preview=query_preview[:200] if query_preview else None,
                    sensitivity_level=sensitivity_level,
                    reason=reason,
                    status='pending',
                    created_at=int(time.time()),
                    policy_decision_id=policy_decision_id,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return PendingReviewModel.model_validate(record)
        except Exception as e:
            log.exception(f'[pending_reviews] insert failed: {e}')
            return None

    def list_all(self, status: Optional[str] = None) -> list[PendingReviewModel]:
        try:
            with get_db_context() as db:
                q = db.query(PendingReview)
                if status:
                    q = q.filter(PendingReview.status == status)
                records = q.order_by(PendingReview.created_at.desc()).limit(200).all()
                return [PendingReviewModel.model_validate(r) for r in records]
        except Exception as e:
            log.exception(f'[pending_reviews] list_all failed: {e}')
            return []

    def update_status(
        self,
        review_id: str,
        status: str,
        reviewed_by: str,
    ) -> Optional[PendingReviewModel]:
        try:
            with get_db_context() as db:
                record = (
                    db.query(PendingReview)
                    .filter(PendingReview.id == uuid.UUID(review_id))
                    .first()
                )
                if not record:
                    return None
                record.status = status
                record.reviewed_by = reviewed_by
                record.reviewed_at = int(time.time())
                db.commit()
                db.refresh(record)
                return PendingReviewModel.model_validate(record)
        except Exception as e:
            log.exception(f'[pending_reviews] update_status failed: {e}')
            return None

    def is_approved(self, query_hash: str, window_seconds: int = 86400) -> bool:
        """True if this query hash was approved within the last window_seconds (default 24h)."""
        try:
            with get_db_context() as db:
                cutoff = int(time.time()) - window_seconds
                record = (
                    db.query(PendingReview)
                    .filter(
                        PendingReview.query_hash == query_hash,
                        PendingReview.status == 'approved',
                        PendingReview.reviewed_at >= cutoff,
                    )
                    .first()
                )
                return record is not None
        except Exception as e:
            log.exception(f'[pending_reviews] is_approved failed: {e}')
            return False

    def has_pending(self, query_hash: str) -> bool:
        """True if there's already an open pending review for this hash."""
        try:
            with get_db_context() as db:
                record = (
                    db.query(PendingReview)
                    .filter(
                        PendingReview.query_hash == query_hash,
                        PendingReview.status == 'pending',
                    )
                    .first()
                )
                return record is not None
        except Exception as e:
            log.exception(f'[pending_reviews] has_pending failed: {e}')
            return False


PendingReviews = PendingReviewsTable()
