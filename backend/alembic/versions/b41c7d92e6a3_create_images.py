"""create images

Revision ID: b41c7d92e6a3
Revises: d7a2c48e91b5
Create Date: 2026-08-13 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b41c7d92e6a3'
down_revision = 'd7a2c48e91b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('document_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('caption', sa.Text(), nullable=False),
    sa.Column('source_url', sa.String(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('images')
