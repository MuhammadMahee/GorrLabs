import logging
import time
from typing import Optional
import uuid
from enum import IntEnum

from sqlalchemy.orm import Session
from arkive.internal.db import Base, get_db_context

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID, insert as pg_insert

log = logging.getLogger(__name__)


class ClearanceLevel(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3


####################
# UserPolicy DB Schema
####################


class UserPolicy(Base):
    __tablename__ = 'user_policies'

    user_id = Column(Text, primary_key=True)
    department = Column(Text, nullable=True)
    clearance_level = Column(Integer, nullable=False, default=0)
    region = Column(Text, nullable=True)
    usage_policy_id = Column(UUID(as_uuid=True), nullable=True)
    allowed_collection_ids = Column(ARRAY(Text), nullable=False, default=list)
    can_export = Column(Boolean, nullable=False, default=False)
    can_upload = Column(Boolean, nullable=False, default=True)
    updated_at = Column(BigInteger, nullable=False)


class UserPolicyModel(BaseModel):
    user_id: str
    department: Optional[str] = None
    clearance_level: int = 0
    region: Optional[str] = None
    usage_policy_id: Optional[uuid.UUID] = None
    allowed_collection_ids: list[str] = []
    can_export: bool = False
    can_upload: bool = True
    updated_at: int  # timestamp in epoch

    model_config = ConfigDict(from_attributes=True)

    @field_validator('clearance_level')
    @classmethod
    def validate_clearance_level(cls, v: int) -> int:
        if v not in (0, 1, 2, 3):
            raise ValueError(f'clearance_level must be 0-3 (public/internal/confidential/restricted), got {v}')
        return v


####################
# Forms
####################


class UserPolicyForm(BaseModel):
    department: Optional[str] = None
    clearance_level: int = 0
    region: Optional[str] = None
    usage_policy_id: Optional[uuid.UUID] = None
    allowed_collection_ids: list[str] = []
    can_export: bool = False
    can_upload: bool = True

    @field_validator('clearance_level')
    @classmethod
    def validate_clearance_level(cls, v: int) -> int:
        if v not in (0, 1, 2, 3):
            raise ValueError(f'clearance_level must be 0-3 (public/internal/confidential/restricted), got {v}')
        return v


class UserPoliciesTable:
    def insert_or_update_user_policy(
        self,
        user_id: str,
        form_data: UserPolicyForm,
        db: Optional[Session] = None,
    ) -> Optional[UserPolicyModel]:
        with get_db_context(db) as db:
            try:
                now = int(time.time())
                payload = form_data.model_dump()

                stmt = pg_insert(UserPolicy).values(
                    user_id=user_id,
                    **payload,
                    updated_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['user_id'],
                    set_={
                        **payload,
                        'updated_at': now,
                    },
                )
                db.execute(stmt)
                db.commit()
                return self.get_user_policy_by_user_id(user_id=user_id, db=db)
            except Exception as e:
                log.exception(f'Error upserting user policy: {e}')
                return None

    def get_user_policy_by_user_id(
        self, user_id: str, db: Optional[Session] = None
    ) -> Optional[UserPolicyModel]:
        try:
            with get_db_context(db) as db:
                policy = db.query(UserPolicy).filter_by(user_id=user_id).first()
                return UserPolicyModel.model_validate(policy) if policy else None
        except Exception:
            return None

    def delete_user_policy_by_user_id(
        self, user_id: str, db: Optional[Session] = None
    ) -> bool:
        try:
            with get_db_context(db) as db:
                db.query(UserPolicy).filter_by(user_id=user_id).delete()
                db.commit()
                return True
        except Exception:
            return False


UserPolicies = UserPoliciesTable()
