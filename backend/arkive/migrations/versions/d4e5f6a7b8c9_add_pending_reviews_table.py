"""Add pending_reviews table for Route D human review queue

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-30 00:00:00.000000

Adds pending_reviews: holds queries that were flagged by the policy engine
and are awaiting admin approval before processing continues.

Flow:
  evaluate_request() → decision='flag' → insert row (status='pending')
  Admin approves/rejects via /api/v1/policy/reviews/{id}/approve|reject
  User re-submits → hash check finds approved row → proceeds normally
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from arkive.migrations.util import get_existing_tables

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if 'pending_reviews' not in existing_tables:
        op.create_table(
            'pending_reviews',
            sa.Column(
                'id',
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text('gen_random_uuid()'),
            ),
            sa.Column('user_id', sa.Text(), nullable=False),
            sa.Column('query_hash', sa.Text(), nullable=False),
            sa.Column('query_preview', sa.Text(), nullable=True),
            sa.Column('sensitivity_level', sa.Integer(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column(
                'status',
                sa.Text(),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column('created_at', sa.BigInteger(), nullable=False),
            sa.Column('reviewed_by', sa.Text(), nullable=True),
            sa.Column('reviewed_at', sa.BigInteger(), nullable=True),
            sa.Column(
                'policy_decision_id',
                postgresql.UUID(as_uuid=True),
                nullable=True,
            ),
        )
        op.create_index('idx_pending_reviews_user_id', 'pending_reviews', ['user_id'])
        op.create_index('idx_pending_reviews_status', 'pending_reviews', ['status'])
        op.create_index('idx_pending_reviews_created_at', 'pending_reviews', ['created_at'])
        op.create_index('idx_pending_reviews_query_hash', 'pending_reviews', ['query_hash'])


def downgrade() -> None:
    op.drop_index('idx_pending_reviews_query_hash', table_name='pending_reviews')
    op.drop_index('idx_pending_reviews_created_at', table_name='pending_reviews')
    op.drop_index('idx_pending_reviews_status', table_name='pending_reviews')
    op.drop_index('idx_pending_reviews_user_id', table_name='pending_reviews')
    op.drop_table('pending_reviews')
