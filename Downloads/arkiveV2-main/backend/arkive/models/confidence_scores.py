"""Confidence score model — Stores combined confidence metrics for responses."""

import logging
import time
import uuid
from typing import Optional

from sqlalchemy import Column, Float, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from arkive.internal.db import Base, get_db_context

log = logging.getLogger(__name__)


####################
# Database Model
####################

class ConfidenceScore(Base):
    """Stores confidence metrics (append-only)."""
    __tablename__ = 'confidence_scores'

    id = Column(UUID(as_uuid=True), primary_key=True)
    response_audit_log_id = Column(UUID(as_uuid=True), nullable=False)
    source_quality_score = Column(Float, nullable=False)  # 0-1
    fact_check_score = Column(Float, nullable=False)  # 0-1
    classification_score = Column(Float, nullable=False)  # 0-1
    final_confidence = Column(Float, nullable=False)  # 0-1
    calculation_formula = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)  # epoch ms


####################
# Pydantic Model
####################

class ConfidenceScoreModel(BaseModel):
    """Pydantic schema for API serialization."""
    id: uuid.UUID
    response_audit_log_id: uuid.UUID
    source_quality_score: float
    fact_check_score: float
    classification_score: float
    final_confidence: float
    calculation_formula: Optional[str] = None
    created_at: int  # epoch ms

    model_config = ConfigDict(from_attributes=True)

    @field_validator('source_quality_score', 'fact_check_score', 'classification_score', 'final_confidence')
    @classmethod
    def validate_score_range(cls, v):
        """Ensure scores are between 0 and 1."""
        if not (0 <= v <= 1):
            raise ValueError('Score must be between 0 and 1')
        return v


####################
# CRUD Operations
####################

class ConfidenceScores:
    """CRUD operations for confidence scores (append-only)."""

    # Default formula: 0.4*source_quality + 0.4*fact_check + 0.2*classification
    DEFAULT_FORMULA = "0.4*sq + 0.4*fc + 0.2*cs"
    DEFAULT_WEIGHTS = {'source_quality': 0.4, 'fact_check': 0.4, 'classification': 0.2}

    @staticmethod
    def insert_score(
        response_audit_log_id: uuid.UUID,
        source_quality_score: float,
        fact_check_score: float,
        classification_score: float,
        formula: str = DEFAULT_FORMULA,
    ) -> Optional[ConfidenceScoreModel]:
        """
        Insert a new confidence score (append-only).

        Calculates final_confidence as weighted average:
        final = 0.4*source_quality + 0.4*fact_check + 0.2*classification

        Args:
            response_audit_log_id: ID of the response audit log
            source_quality_score: Quality of retrieved sources (0-1)
            fact_check_score: How well facts were verified (0-1)
            classification_score: Safety/policy score (0-1)
            formula: Formula used for calculation (for audit trail)

        Returns:
            ConfidenceScoreModel if successful, None if failed
        """
        # Clamp scores to [0, 1]
        sq = max(0, min(1, source_quality_score))
        fc = max(0, min(1, fact_check_score))
        cs = max(0, min(1, classification_score))

        # Calculate final confidence using weighted average
        final_confidence = (
            ConfidenceScores.DEFAULT_WEIGHTS['source_quality'] * sq
            + ConfidenceScores.DEFAULT_WEIGHTS['fact_check'] * fc
            + ConfidenceScores.DEFAULT_WEIGHTS['classification'] * cs
        )
        final_confidence = max(0, min(1, final_confidence))

        with get_db_context() as db:
            try:
                score = ConfidenceScore(
                    id=uuid.uuid4(),
                    response_audit_log_id=response_audit_log_id,
                    source_quality_score=sq,
                    fact_check_score=fc,
                    classification_score=cs,
                    final_confidence=final_confidence,
                    calculation_formula=formula,
                    created_at=int(time.time() * 1000),  # milliseconds
                )
                db.add(score)
                db.commit()
                db.refresh(score)

                log.info(
                    f'[ConfidenceScores.insert_score] '
                    f'sq={sq:.2f} fc={fc:.2f} cs={cs:.2f} → final={final_confidence:.2f}'
                )
                return ConfidenceScoreModel.model_validate(score)
            except Exception as e:
                log.error(f'[ConfidenceScores.insert_score] failed: {e}')
                db.rollback()
                return None

    @staticmethod
    def get_by_audit_log_id(response_audit_log_id: uuid.UUID) -> Optional[ConfidenceScoreModel]:
        """Get confidence score for a specific audit log."""
        with get_db_context() as db:
            try:
                score = (
                    db.query(ConfidenceScore)
                    .filter_by(response_audit_log_id=response_audit_log_id)
                    .order_by(ConfidenceScore.created_at.desc())
                    .first()
                )
                return ConfidenceScoreModel.model_validate(score) if score else None
            except Exception as e:
                log.error(f'[ConfidenceScores.get_by_audit_log_id] failed: {e}')
                return None

    @staticmethod
    def get_by_message_id(message_id: str) -> list[ConfidenceScoreModel]:
        """
        Get all confidence scores associated with a message.

        Does a JOIN with response_audit_log to find all scores for a message.
        """
        with get_db_context() as db:
            try:
                from arkive.models.response_audits import ResponseAuditLog

                scores = (
                    db.query(ConfidenceScore)
                    .join(
                        ResponseAuditLog,
                        ConfidenceScore.response_audit_log_id == ResponseAuditLog.id
                    )
                    .filter(ResponseAuditLog.message_id == message_id)
                    .order_by(ConfidenceScore.created_at.desc())
                    .all()
                )
                return [ConfidenceScoreModel.model_validate(score) for score in scores]
            except Exception as e:
                log.error(f'[ConfidenceScores.get_by_message_id] failed: {e}')
                return []

    @staticmethod
    def get_average_score(user_id: str, days: int = 7) -> Optional[float]:
        """
        Get average final confidence score for a user over the last N days.
        Useful for analytics.
        """
        with get_db_context() as db:
            try:
                import time
                cutoff_ms = int((time.time() - days * 86400) * 1000)

                result = db.query(
                    db.func.avg(ConfidenceScore.final_confidence).label('avg_score')
                ).filter(
                    ConfidenceScore.created_at >= cutoff_ms
                ).first()

                return result[0] if result and result[0] else None
            except Exception as e:
                log.error(f'[ConfidenceScores.get_average_score] failed: {e}')
                return None

    @staticmethod
    def count_all() -> int:
        """Count total confidence scores."""
        with get_db_context() as db:
            try:
                return db.query(ConfidenceScore).count()
            except Exception as e:
                log.error(f'[ConfidenceScores.count_all] failed: {e}')
                return 0
