"""Add routing field to policy_decisions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-04 00:00:00.000000

Adds routing column to the policy_decisions audit table.
Values: 'local_only' | 'hybrid_allowed' | 'block' | 'human_review'
Nullable because existing rows pre-date this field and cannot be backfilled.
New rows always have routing set by the application layer.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'policy_decisions',
        sa.Column('routing', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('policy_decisions', 'routing')
