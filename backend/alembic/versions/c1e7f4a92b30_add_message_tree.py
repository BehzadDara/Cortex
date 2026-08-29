"""add message tree

Revision ID: c1e7f4a92b30
Revises: b41c7d92e6a3
Create Date: 2026-08-29 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c1e7f4a92b30'
down_revision = 'b41c7d92e6a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('parent_id', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('active_child_id', sa.Integer(), nullable=True))
    op.add_column('messages', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('summarized_depth', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'messages_parent_id_fkey', 'messages', 'messages',
        ['parent_id'], ['id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'messages_active_child_id_fkey', 'messages', 'messages',
        ['active_child_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_messages_parent_id', 'messages', ['parent_id'])
    op.create_index(
        'ix_messages_conversation_parent', 'messages', ['conversation_id', 'parent_id']
    )

    op.add_column(
        'conversations', sa.Column('active_root_id', sa.Integer(), nullable=True)
    )
    op.add_column(
        'conversations', sa.Column('active_parent_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'conversations_active_root_id_fkey', 'conversations', 'messages',
        ['active_root_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'conversations_active_parent_id_fkey', 'conversations', 'messages',
        ['active_parent_id'], ['id'], ondelete='SET NULL',
    )

    op.execute("""
        UPDATE messages AS child
        SET parent_id = ordered.previous_id
        FROM (
            SELECT id,
                   LAG(id) OVER (PARTITION BY conversation_id ORDER BY id) AS previous_id
            FROM messages
        ) AS ordered
        WHERE child.id = ordered.id AND ordered.previous_id IS NOT NULL
    """)
    op.execute("""
        UPDATE messages AS parent
        SET active_child_id = child.id
        FROM messages AS child
        WHERE child.parent_id = parent.id
    """)
    op.execute("""
        UPDATE conversations AS conversation
        SET active_root_id = root.id
        FROM messages AS root
        WHERE root.conversation_id = conversation.id AND root.parent_id IS NULL
    """)
    op.execute("""
        UPDATE messages AS boundary
        SET summary = conversation.summary,
            summarized_depth = conversation.summarized_count
        FROM conversations AS conversation
        WHERE conversation.summary IS NOT NULL
          AND conversation.summarized_count > 0
          AND boundary.id = (
              SELECT id FROM messages
              WHERE conversation_id = conversation.id
              ORDER BY id
              OFFSET conversation.summarized_count - 1
              LIMIT 1
          )
    """)

    op.drop_column('conversations', 'summary')
    op.drop_column('conversations', 'summarized_count')


def downgrade() -> None:
    op.add_column('conversations', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column(
        'conversations',
        sa.Column('summarized_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.execute("""
        UPDATE conversations AS conversation
        SET summary = deepest.summary,
            summarized_count = deepest.summarized_depth
        FROM (
            SELECT DISTINCT ON (conversation_id)
                   conversation_id, summary, summarized_depth
            FROM messages
            WHERE summary IS NOT NULL
            ORDER BY conversation_id, summarized_depth DESC
        ) AS deepest
        WHERE deepest.conversation_id = conversation.id
    """)
    op.drop_constraint(
        'conversations_active_parent_id_fkey', 'conversations', type_='foreignkey'
    )
    op.drop_constraint(
        'conversations_active_root_id_fkey', 'conversations', type_='foreignkey'
    )
    op.drop_column('conversations', 'active_parent_id')
    op.drop_column('conversations', 'active_root_id')
    op.drop_index('ix_messages_conversation_parent', table_name='messages')
    op.drop_index('ix_messages_parent_id', table_name='messages')
    op.drop_constraint('messages_active_child_id_fkey', 'messages', type_='foreignkey')
    op.drop_constraint('messages_parent_id_fkey', 'messages', type_='foreignkey')
    op.drop_column('messages', 'summarized_depth')
    op.drop_column('messages', 'summary')
    op.drop_column('messages', 'active_child_id')
    op.drop_column('messages', 'parent_id')
