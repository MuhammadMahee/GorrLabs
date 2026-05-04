"""Rename geo_zone to region, add clearance_level check constraint

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-02 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'user_policies',
        'geo_zone',
        new_column_name='region',
    )
    op.create_check_constraint(
        'ck_user_policies_clearance_level',
        'user_policies',
        'clearance_level IN (0, 1, 2, 3)',
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_user_policies_clearance_level',
        'user_policies',
        type_='check',
    )
    op.alter_column(
        'user_policies',
        'region',
        new_column_name='geo_zone',
    )
