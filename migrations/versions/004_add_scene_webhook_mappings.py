"""Add scene_webhook_mappings table

Revision ID: 004
Revises: 003
Create Date: 2026-03-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create scene_webhook_mappings table."""
    op.create_table(
        'scene_webhook_mappings',
        sa.Column('id', sa.String(255), nullable=False),
        sa.Column('home_id', sa.String(255), nullable=False),
        sa.Column('scene_name', sa.String(255), nullable=False),
        sa.Column('webhook_id', sa.String(500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['home_id'], ['homes.home_id']),
    )
    op.create_index('idx_scene_home_name', 'scene_webhook_mappings', ['home_id', 'scene_name'], unique=True)
    op.create_index('idx_scene_home_active', 'scene_webhook_mappings', ['home_id', 'is_active'])
    op.create_index('ix_scene_webhook_mappings_home_id', 'scene_webhook_mappings', ['home_id'])
    op.create_index('ix_scene_webhook_mappings_created_at', 'scene_webhook_mappings', ['created_at'])


def downgrade() -> None:
    """Drop scene_webhook_mappings table."""
    op.drop_index('ix_scene_webhook_mappings_created_at', table_name='scene_webhook_mappings')
    op.drop_index('ix_scene_webhook_mappings_home_id', table_name='scene_webhook_mappings')
    op.drop_index('idx_scene_home_active', table_name='scene_webhook_mappings')
    op.drop_index('idx_scene_home_name', table_name='scene_webhook_mappings')
    op.drop_table('scene_webhook_mappings')
