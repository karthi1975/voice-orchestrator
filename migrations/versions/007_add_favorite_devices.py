"""Add favorite_devices table

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa


revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'favorite_devices',
        sa.Column('id', sa.String(64), nullable=False),
        sa.Column('user_ref', sa.String(255), nullable=False),
        sa.Column('home_id', sa.String(255), nullable=False),
        sa.Column('entity_id', sa.String(255), nullable=False),
        sa.Column('friendly_name', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(64), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['home_id'], ['homes.home_id']),
    )
    op.create_index(
        'idx_favorite_user_home_entity',
        'favorite_devices',
        ['user_ref', 'home_id', 'entity_id'],
        unique=True,
    )
    op.create_index(
        'idx_favorite_user_home_position',
        'favorite_devices',
        ['user_ref', 'home_id', 'position'],
    )
    op.create_index(
        'ix_favorite_devices_user_ref',
        'favorite_devices',
        ['user_ref'],
    )
    op.create_index(
        'ix_favorite_devices_home_id',
        'favorite_devices',
        ['home_id'],
    )


def downgrade():
    op.drop_index('ix_favorite_devices_home_id', table_name='favorite_devices')
    op.drop_index('ix_favorite_devices_user_ref', table_name='favorite_devices')
    op.drop_index('idx_favorite_user_home_position', table_name='favorite_devices')
    op.drop_index('idx_favorite_user_home_entity', table_name='favorite_devices')
    op.drop_table('favorite_devices')
