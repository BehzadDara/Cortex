"""add trace_id to messages

Revision ID: a7c3e9d15f42
Revises: d3f8a1c07b52
Create Date: 2026-10-04 13:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7c3e9d15f42'
down_revision = 'd3f8a1c07b52'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('trace_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'trace_id')
