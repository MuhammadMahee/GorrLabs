"""SQLAlchemy model and helpers for Solana audit anchors."""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID

from arkive.internal.db import Base, get_db_context

log = logging.getLogger(__name__)


class AuditAnchor(Base):
    __tablename__ = 'audit_anchors'

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text('gen_random_uuid()'),
    )
    event_type = Column(Text, nullable=False)
    event_id = Column(Text, nullable=False)
    event_hash = Column(Text, nullable=False)
    canonical = Column(Text, nullable=False)
    tx_id = Column(Text, nullable=True)
    anchored_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text('now()'),
    )


class AuditAnchors:
    @staticmethod
    def insert(
        event_type: str,
        event_id: str,
        event_hash: str,
        canonical: str,
        tx_id: str | None = None,
        anchored_at: datetime | None = None,
    ) -> Optional[AuditAnchor]:
        """Insert a new anchor record. Returns the inserted row."""
        try:
            with get_db_context() as db:
                record = AuditAnchor(
                    event_type=event_type,
                    event_id=event_id,
                    event_hash=event_hash,
                    canonical=canonical,
                    tx_id=tx_id,
                    anchored_at=anchored_at,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return record
        except Exception as e:
            log.exception(f'[audit_anchors] insert failed: {e}')
            return None

    @staticmethod
    def get_by_event(
        event_type: str,
        event_id: str,
    ) -> Optional[AuditAnchor]:
        """Fetch anchor record for a specific event."""
        try:
            with get_db_context() as db:
                return (
                    db.query(AuditAnchor)
                    .filter(
                        AuditAnchor.event_type == event_type,
                        AuditAnchor.event_id == event_id,
                    )
                    .order_by(AuditAnchor.created_at.desc())
                    .first()
                )
        except Exception as e:
            log.exception(f'[audit_anchors] get_by_event failed: {e}')
            return None

    @staticmethod
    def get_unanchored(limit: int = 100) -> list[AuditAnchor]:
        """Fetch rows where tx_id IS NULL for retry sweep."""
        try:
            with get_db_context() as db:
                return (
                    db.query(AuditAnchor)
                    .filter(AuditAnchor.tx_id.is_(None))
                    .order_by(AuditAnchor.created_at.asc())
                    .limit(limit)
                    .all()
                )
        except Exception as e:
            log.exception(f'[audit_anchors] get_unanchored failed: {e}')
            return []

    @staticmethod
    def get_all(
        page: int = 1,
        page_size: int = 50,
        event_type: str | None = None,
        anchored: bool | None = None,
    ) -> tuple[list["AuditAnchor"], int]:
        """Return paginated anchors and total count."""
        try:
            with get_db_context() as db:
                q = db.query(AuditAnchor)
                if event_type:
                    q = q.filter(AuditAnchor.event_type == event_type)
                if anchored is True:
                    q = q.filter(AuditAnchor.tx_id.isnot(None))
                elif anchored is False:
                    q = q.filter(AuditAnchor.tx_id.is_(None))
                total = q.count()
                rows = (
                    q.order_by(AuditAnchor.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                    .all()
                )
                return rows, total
        except Exception as e:
            log.exception(f'[audit_anchors] get_all failed: {e}')
            return [], 0

    @staticmethod
    def get_by_id(anchor_id: str) -> Optional["AuditAnchor"]:
        """Fetch a single anchor by primary key."""
        try:
            parsed = uuid.UUID(str(anchor_id))
            with get_db_context() as db:
                return db.query(AuditAnchor).filter(AuditAnchor.id == parsed).first()
        except Exception as e:
            log.exception(f'[audit_anchors] get_by_id failed: {e}')
            return None

    @staticmethod
    def get_stats() -> dict:
        """Return aggregate stats for the Trust Console."""
        try:
            from sqlalchemy import func
            with get_db_context() as db:
                total = db.query(func.count(AuditAnchor.id)).scalar() or 0
                anchored = (
                    db.query(func.count(AuditAnchor.id))
                    .filter(AuditAnchor.tx_id.isnot(None))
                    .scalar()
                    or 0
                )
                pending = total - anchored
                by_type = (
                    db.query(AuditAnchor.event_type, func.count(AuditAnchor.id))
                    .group_by(AuditAnchor.event_type)
                    .all()
                )
                return {
                    "total": total,
                    "anchored": anchored,
                    "pending": pending,
                    "by_event_type": {et: cnt for et, cnt in by_type},
                }
        except Exception as e:
            log.exception(f'[audit_anchors] get_stats failed: {e}')
            return {"total": 0, "anchored": 0, "pending": 0, "by_event_type": {}}

    @staticmethod
    def mark_anchored(
        anchor_id: str,
        tx_id: str,
        anchored_at: datetime,
    ) -> None:
        """Update tx_id and anchored_at after successful submission."""
        try:
            with get_db_context() as db:
                try:
                    parsed_anchor_id = uuid.UUID(str(anchor_id))
                except ValueError:
                    log.warning(f'[audit_anchors] invalid anchor_id: {anchor_id}')
                    return

                record = db.query(AuditAnchor).filter(AuditAnchor.id == parsed_anchor_id).first()
                if not record:
                    return

                record.tx_id = tx_id
                record.anchored_at = anchored_at
                db.commit()
        except Exception as e:
            log.exception(f'[audit_anchors] mark_anchored failed: {e}')
