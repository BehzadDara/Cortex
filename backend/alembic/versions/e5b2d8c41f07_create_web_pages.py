"""create web_pages

Revision ID: e5b2d8c41f07
Revises: a7c3e9d15f42
Create Date: 2026-10-04 16:50:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5b2d8c41f07'
down_revision = 'a7c3e9d15f42'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'web_pages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'parent_id',
            sa.Integer(),
            sa.ForeignKey('web_pages.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('request', sa.Text(), nullable=False),
        sa.Column('html', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table('web_pages')
