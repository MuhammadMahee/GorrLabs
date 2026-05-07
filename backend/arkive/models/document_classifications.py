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
from sqlalchemy.dialects.postgresql import ARRAY, UUID, insert as pg_insert

log = logging.getLogger(__name__)

####################
# DocumentClassification DB Schema
####################


class DocumentClassification(Base):
    __tablename__ = 'document_classifications'

    id = Column(UUID(as_uuid=True), primary_key=True)
    file_id = Column(Text, nullable=False, unique=True)
    sensitivity_level = Column(Integer, nullable=False, default=0)
    detected_entities = Column(JSON, nullable=False, default=list)
    topic_labels = Column(ARRAY(Text), nullable=False, default=list)
    classification_source = Column(Text, nullable=False, default='auto')
    classified_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class DocumentClassificationModel(BaseModel):
    id: uuid.UUID
    file_id: str
    sensitivity_level: int = 0
    detected_entities: list[Any] = []
    topic_labels: list[str] = []
    classification_source: str = 'auto'
    classified_at: int  # timestamp in epoch
    updated_at: int  # timestamp in epoch

    model_config = ConfigDict(from_attributes=True)


####################
# Forms
####################


class DocumentClassificationForm(BaseModel):
    sensitivity_level: int = 0
    detected_entities: list[Any] = []
    topic_labels: list[str] = []
    classification_source: str = 'auto'


class DocumentClassificationsTable:
    def insert_or_update_classification(
        self,
        file_id: str,
        form_data: DocumentClassificationForm,
        db: Optional[Session] = None,
    ) -> Optional[DocumentClassificationModel]:
        with get_db_context(db) as db:
            try:
                now = int(time.time())
                payload = form_data.model_dump()

                stmt = pg_insert(DocumentClassification).values(
                    id=uuid.uuid4(),
                    file_id=file_id,
                    **payload,
                    classified_at=now,
                    updated_at=now,
                )
                # On conflict over file_id, keep original id + classified_at,
                # refresh the classification fields and updated_at.
                stmt = stmt.on_conflict_do_update(
                    index_elements=['file_id'],
                    set_={
                        **payload,
                        'updated_at': now,
                    },
                )
                db.execute(stmt)
                db.commit()
                result = self.get_classification_by_file_id(file_id=file_id, db=db)
                if result:
                    try:
                        from arkive.solana.tasks import fire_and_forget
                        from arkive.solana.payloads import payload_document_classification

                        fire_and_forget(
                            event_type='document_classification',
                            event_id=str(result.file_id),
                            payload=payload_document_classification(
                                {
                                    'file_id': str(result.file_id),
                                    'sensitivity_level': result.sensitivity_level,
                                    'topic_labels': result.topic_labels or [],
                                    'entity_types_detected': [
                                        entity.get('entity_type')
                                        for entity in (result.detected_entities or [])
                                        if isinstance(entity, dict) and entity.get('entity_type')
                                    ],
                                    'classification_method': result.classification_source or 'auto',
                                    'classified_at': str(result.classified_at),
                                }
                            ),
                        )
                    except Exception:
                        pass
                return result
            except Exception as e:
                log.exception(f'Error upserting document classification: {e}')
                return None

    def get_classification_by_file_id(
        self, file_id: str, db: Optional[Session] = None
    ) -> Optional[DocumentClassificationModel]:
        try:
            with get_db_context(db) as db:
                classification = (
                    db.query(DocumentClassification)
                    .filter_by(file_id=file_id)
                    .first()
                )
                return (
                    DocumentClassificationModel.model_validate(classification)
                    if classification
                    else None
                )
        except Exception:
            return None

    def get_classifications_above_level(
        self, level: int, db: Optional[Session] = None
    ) -> list[DocumentClassificationModel]:
        with get_db_context(db) as db:
            classifications = (
                db.query(DocumentClassification)
                .filter(DocumentClassification.sensitivity_level >= level)
                .order_by(DocumentClassification.classified_at.desc())
                .all()
            )
            return [
                DocumentClassificationModel.model_validate(c) for c in classifications
            ]

    def update_classification_by_file_id(
        self,
        file_id: str,
        form_data: DocumentClassificationForm,
        db: Optional[Session] = None,
    ) -> Optional[DocumentClassificationModel]:
        try:
            with get_db_context(db) as db:
                db.query(DocumentClassification).filter_by(file_id=file_id).update(
                    {
                        **form_data.model_dump(),
                        'updated_at': int(time.time()),
                    }
                )
                db.commit()
                return self.get_classification_by_file_id(file_id=file_id, db=db)
        except Exception as e:
            log.exception(f'Error updating document classification: {e}')
            return None


DocumentClassifications = DocumentClassificationsTable()
