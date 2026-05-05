"""Add audit_anchors table

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-05 00:00:00.000000

Stores deterministic audit event hashes and Solana memo transaction IDs.
This table intentionally has no foreign keys so audit records survive even
when source rows are deleted.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'audit_anchors',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('event_id', sa.Text(), nullable=False),
        sa.Column('event_hash', sa.Text(), nullable=False),
        sa.Column('canonical', sa.Text(), nullable=False),
        sa.Column('tx_id', sa.Text(), nullable=True),
        sa.Column('anchored_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )
    op.create_index('ix_audit_anchors_event_type', 'audit_anchors', ['event_type'])
    op.create_index('ix_audit_anchors_event_hash', 'audit_anchors', ['event_hash'])
    op.create_index('ix_audit_anchors_tx_id', 'audit_anchors', ['tx_id'])


def downgrade() -> None:
    op.drop_index('ix_audit_anchors_tx_id', table_name='audit_anchors')
    op.drop_index('ix_audit_anchors_event_hash', table_name='audit_anchors')
    op.drop_index('ix_audit_anchors_event_type', table_name='audit_anchors')
    op.drop_table('audit_anchors')
