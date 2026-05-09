"""Response audit log model — Tracks each stage of response generation."""

import logging
import time
import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, Column, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID

from pydantic import BaseModel, ConfigDict

from arkive.internal.db import Base, get_db_context

log = logging.getLogger(__name__)


####################
# Enums
####################

class AuditStage(str, Enum):
    """Stages of response generation."""
    RETRIEVAL = "retrieval"
    REDACTION = "redaction"
    MODEL_CALL = "model_call"
    RESPONSE_COMPOSITION = "response_composition"
    FINAL = "final"


####################
# Database Model
####################

class ResponseAuditLog(Base):
    """Append-only audit log for response generation stages."""
    __tablename__ = 'response_audit_log'

    id = Column(UUID(as_uuid=True), primary_key=True)
    message_id = Column(Text, nullable=True)
    user_id = Column(Text, nullable=False)
    stage = Column(Text, nullable=False)  # AuditStage enum value
    stage_input = Column(JSON, nullable=True)
    stage_output = Column(JSON, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(Text, nullable=False)  # 'success' or 'error'
    error_message = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)  # epoch ms


####################
# Pydantic Model (for API responses)
####################

class ResponseAuditModel(BaseModel):
    """Pydantic schema for API serialization."""
    id: uuid.UUID
    message_id: Optional[str] = None
    user_id: str
    stage: str
    stage_input: Optional[dict] = None
    stage_output: Optional[dict] = None
    duration_ms: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    created_at: int  # epoch ms

    model_config = ConfigDict(from_attributes=True)


####################
# CRUD Operations
####################

class ResponseAudits:
    """CRUD operations for response audit logs (append-only)."""

    @staticmethod
    def insert_stage_log(
        user_id: str,
        message_id: Optional[str] = None,
        stage: AuditStage = AuditStage.RETRIEVAL,
        status: str = 'success',
        stage_input: Optional[dict] = None,
        stage_output: Optional[dict] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ResponseAuditModel]:
        """
        Insert a new audit log entry (append-only).

        Args:
            user_id: ID of the user
            message_id: ID of the chat message (optional)
            stage: Which stage (retrieval, redaction, model_call, response_composition, final)
            status: 'success' or 'error'
            stage_input: JSON input to this stage
            stage_output: JSON output from this stage
            duration_ms: How long this stage took
            error_message: If status='error', the error message

        Returns:
            ResponseAuditModel if successful, None if failed
        """
        with get_db_context() as db:
            try:
                log_entry = ResponseAuditLog(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    message_id=message_id,
                    stage=stage.value if isinstance(stage, AuditStage) else stage,
                    status=status,
                    stage_input=stage_input,
                    stage_output=stage_output,
                    duration_ms=duration_ms,
                    error_message=error_message,
                    created_at=int(time.time() * 1000),  # milliseconds
                )
                db.add(log_entry)
                db.commit()
                db.refresh(log_entry)
                return ResponseAuditModel.model_validate(log_entry)
            except Exception as e:
                log.error(f'[ResponseAudits.insert_stage_log] failed: {e}')
                db.rollback()
                return None

    @staticmethod
    def get_by_message_id(message_id: str) -> list[ResponseAuditModel]:
        """Get all audit logs for a specific message (full trail)."""
        with get_db_context() as db:
            try:
                logs = (
                    db.query(ResponseAuditLog)
                    .filter_by(message_id=message_id)
                    .order_by(ResponseAuditLog.created_at.asc())
                    .all()
                )
                return [ResponseAuditModel.model_validate(log) for log in logs]
            except Exception as e:
                log.error(f'[ResponseAudits.get_by_message_id] failed: {e}')
                return []

    @staticmethod
    def get_by_message_and_stage(
        message_id: str,
        stage: str,
    ) -> Optional[ResponseAuditModel]:
        """Get the audit log for a specific stage of a message."""
        with get_db_context() as db:
            try:
                log_entry = (
                    db.query(ResponseAuditLog)
                    .filter_by(message_id=message_id, stage=stage)
                    .order_by(ResponseAuditLog.created_at.desc())
                    .first()
                )
                return ResponseAuditModel.model_validate(log_entry) if log_entry else None
            except Exception as e:
                log.error(f'[ResponseAudits.get_by_message_and_stage] failed: {e}')
                return None

    @staticmethod
    def get_by_user_id(user_id: str, limit: int = 100) -> list[ResponseAuditModel]:
        """Get recent audit logs for a user."""
        with get_db_context() as db:
            try:
                logs = (
                    db.query(ResponseAuditLog)
                    .filter_by(user_id=user_id)
                    .order_by(ResponseAuditLog.created_at.desc())
                    .limit(limit)
                    .all()
                )
                return [ResponseAuditModel.model_validate(log) for log in logs]
            except Exception as e:
                log.error(f'[ResponseAudits.get_by_user_id] failed: {e}')
                return []

    @staticmethod
    def count_all() -> int:
        """Count total audit log entries."""
        with get_db_context() as db:
            try:
                return db.query(ResponseAuditLog).count()
            except Exception as e:
                log.error(f'[ResponseAudits.count_all] failed: {e}')
                return 0
