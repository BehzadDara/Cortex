"""add active thread to conversations

Revision ID: 9f9926b962ce
Revises: bbb3b23283de
Create Date: 2026-08-08 17:30:04.630829
"""
from alembic import op
import sqlalchemy as sa


revision = '9f9926b962ce'
down_revision = 'bbb3b23283de'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("active_thread", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "active_thread")
