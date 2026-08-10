"""add_snapshot_source_url

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-10 09:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7g8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('snapshots', sa.Column('source_url', sa.String(length=2048), nullable=True))
    op.create_index(op.f('ix_snapshots_source_url'), 'snapshots', ['source_url'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_snapshots_source_url'), table_name='snapshots')
    op.drop_column('snapshots', 'source_url')
