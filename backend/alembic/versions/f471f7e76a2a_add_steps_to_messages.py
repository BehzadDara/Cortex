"""add steps to messages

Revision ID: f471f7e76a2a
Revises: 265dbbb950e5
Create Date: 2026-08-08 14:41:46.576285
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = 'f471f7e76a2a'
down_revision = '265dbbb950e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("steps", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "steps")
