"""add branching to conversations

Revision ID: d7a2c48e91b5
Revises: c9d4a1f27b3e
Create Date: 2026-08-10 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'd7a2c48e91b5'
down_revision = 'c9d4a1f27b3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "branched_from_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "conversations", sa.Column("branched_count", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("conversations", "branched_count")
    op.drop_column("conversations", "branched_from_id")
