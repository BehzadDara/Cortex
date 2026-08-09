"""add elapsed ms to messages

Revision ID: 436dfff9a92b
Revises: 3c19eef930f9
Create Date: 2026-08-09 13:50:18.178214
"""
from alembic import op
import sqlalchemy as sa


revision = '436dfff9a92b'
down_revision = '3c19eef930f9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('elapsed_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'elapsed_ms')
