"""add_model_used_to_reports

Revision ID: a1b2c3d4e5f6
Revises: 99a0152ad423
Create Date: 2026-07-27 11:32:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '99a0152ad423'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('reports', sa.Column('model_used', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('reports', 'model_used')
