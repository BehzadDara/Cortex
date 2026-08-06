"""add fulltext index to chunks

Revision ID: 55c33631d72e
Revises: 5ca7c93f4608
Create Date: 2026-08-06 13:59:44.489213
"""
from alembic import op

revision = '55c33631d72e'
down_revision = '5ca7c93f4608'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX chunk_content_fts ON chunks "
        "USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX chunk_content_fts")
