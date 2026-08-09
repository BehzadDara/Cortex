"""add token counts to messages

Revision ID: 3c19eef930f9
Revises: 9f9926b962ce
Create Date: 2026-08-09 13:36:14.008459
"""
from alembic import op
import sqlalchemy as sa


revision = '3c19eef930f9'
down_revision = '9f9926b962ce'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('prompt_tokens', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('response_tokens', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'response_tokens')
    op.drop_column('messages', 'prompt_tokens')
