import logging
import time
from typing import Any, Optional
import uuid

from sqlalchemy.orm import Session
from arkive.internal.db import Base, get_db_context

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    JSON,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

log = logging.getLogger(__name__)

####################
# PolicyDecision DB Schema
#
# Append-only audit log. Database-level RULES block UPDATE and DELETE
# (see migration c3d4e5f6a7b8). Do not add update/delete methods here.
####################


class PolicyDecision(Base):
    __tablename__ = 'policy_decisions'

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(Text, nullable=True)
    team_id = Column(Text, nullable=True)
    query_hash = Column(Text, nullable=False)
    detected_entities = Column(JSON, nullable=False, default=list)
    sensitivity_level = Column(Integer, nullable=True)
    decision = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    routing = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False)


class PolicyDecisionModel(BaseModel):
    id: uuid.UUID
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    query_hash: str
    detected_entities: list[Any] = []
    sensitivity_level: Optional[int] = None
    decision: str
    reason: Optional[str] = None
    routing: Optional[str] = None
    created_at: int  # timestamp in epoch

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class PolicyDecisionForm(BaseModel):
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    query_hash: str
    detected_entities: list[Any] = []
    sensitivity_level: Optional[int] = None
    decision: str
    reason: Optional[str] = None
    routing: Optional[str] = None


class PolicyDecisionsTable:
    def insert_policy_decision(
        self,
        form_data: PolicyDecisionForm,
        db: Optional[Session] = None,
    ) -> Optional[PolicyDecisionModel]:
        with get_db_context(db) as db:
            try:
                decision = PolicyDecision(
                    id=uuid.uuid4(),
                    **form_data.model_dump(),
                    created_at=int(time.time()),
                )
                db.add(decision)
                db.commit()
                db.refresh(decision)
                return PolicyDecisionModel.model_validate(decision)
            except Exception as e:
                log.exception(f'Error inserting policy decision: {e}')
                return None

    def get_decisions_by_user_id(
        self, user_id: str, limit: int = 100, db: Optional[Session] = None
    ) -> list[PolicyDecisionModel]:
        with get_db_context(db) as db:
            decisions = (
                db.query(PolicyDecision)
                .filter_by(user_id=user_id)
                .order_by(PolicyDecision.created_at.desc())
                .limit(limit)
                .all()
            )
            return [PolicyDecisionModel.model_validate(d) for d in decisions]

    def get_recent_decisions(
        self, limit: int = 100, db: Optional[Session] = None
    ) -> list[PolicyDecisionModel]:
        with get_db_context(db) as db:
            decisions = (
                db.query(PolicyDecision)
                .order_by(PolicyDecision.created_at.desc())
                .limit(limit)
                .all()
            )
            return [PolicyDecisionModel.model_validate(d) for d in decisions]


PolicyDecisions = PolicyDecisionsTable()
