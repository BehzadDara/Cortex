"""add sources to messages

Revision ID: bbb3b23283de
Revises: f471f7e76a2a
Create Date: 2026-08-08 17:21:06.274163
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = 'bbb3b23283de'
down_revision = 'f471f7e76a2a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("sources", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "sources")
