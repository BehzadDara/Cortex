"""create audio_overviews

Revision ID: f3a9c27d5e18
Revises: e5b2d8c41f07
Create Date: 2026-10-21 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'f3a9c27d5e18'
down_revision = 'e5b2d8c41f07'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audio_overviews',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'collection_id',
            sa.Integer(),
            sa.ForeignKey('collections.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('length', sa.String(), nullable=False),
        sa.Column('focus', sa.Text(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('stage', sa.String(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=False),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('segments', postgresql.JSONB(), nullable=True),
        sa.Column('lines', postgresql.JSONB(), nullable=True),
        sa.Column('sources', postgresql.JSONB(), nullable=True),
        sa.Column('audio_filename', sa.String(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('audio_overviews')
