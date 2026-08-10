"""add feedback to messages

Revision ID: c9d4a1f27b3e
Revises: a7c31d09e4f2
Create Date: 2026-08-10 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d4a1f27b3e'
down_revision = 'a7c31d09e4f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("feedback", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "feedback")
