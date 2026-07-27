"""add_profile_company_url_domain

Revision ID: a2b3c4d5e6f7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-27 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('company_name', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('company_url', sa.String(length=1024), nullable=True))
    op.add_column('competitors', sa.Column('company_url', sa.Text(), nullable=True))
    op.add_column('competitors', sa.Column('domain', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_competitors_domain'), 'competitors', ['domain'], unique=False)
    op.create_unique_constraint('uq_user_competitor_domain', 'competitors', ['user_id', 'domain'])


def downgrade() -> None:
    op.drop_constraint('uq_user_competitor_domain', 'competitors', type_='unique')
    op.drop_index(op.f('ix_competitors_domain'), table_name='competitors')
    op.drop_column('competitors', 'domain')
    op.drop_column('competitors', 'company_url')
    op.drop_column('users', 'company_url')
    op.drop_column('users', 'company_name')
