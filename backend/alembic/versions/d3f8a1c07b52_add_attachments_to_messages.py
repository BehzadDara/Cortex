"""add attachments to messages

Revision ID: d3f8a1c07b52
Revises: c1e7f4a92b30
Create Date: 2026-08-29 16:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'd3f8a1c07b52'
down_revision = 'c1e7f4a92b30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'messages', sa.Column('attachments', postgresql.JSONB(), nullable=True)
    )
    op.execute(r"""
        UPDATE messages
        SET attachments = jsonb_build_array(
                jsonb_build_object(
                    'name', substring(content from '\(image: ([^)]+)\)$'),
                    'filename', NULL
                )
            ),
            content = regexp_replace(content, '\s*\(image: [^)]+\)$', '')
        WHERE role = 'user' AND content ~ '\(image: [^)]+\)$'
    """)


def downgrade() -> None:
    op.execute(r"""
        UPDATE messages
        SET content = content || ' (image: ' || (attachments -> 0 ->> 'name') || ')'
        WHERE attachments -> 0 ->> 'name' IS NOT NULL
    """)
    op.drop_column('messages', 'attachments')
