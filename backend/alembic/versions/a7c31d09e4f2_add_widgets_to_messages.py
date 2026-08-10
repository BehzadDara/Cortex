"""add widgets to messages

Revision ID: a7c31d09e4f2
Revises: 436dfff9a92b
Create Date: 2026-08-10 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = 'a7c31d09e4f2'
down_revision = '436dfff9a92b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("widgets", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "widgets")
