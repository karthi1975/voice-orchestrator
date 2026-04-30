"""Extend favorite_devices: kind, device_id, primary_entity_id

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa


revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('favorite_devices',
                  sa.Column('kind', sa.String(16), nullable=False, server_default='entity'))
    op.add_column('favorite_devices',
                  sa.Column('device_id', sa.String(64), nullable=True))
    op.add_column('favorite_devices',
                  sa.Column('primary_entity_id', sa.String(255), nullable=True))
    op.create_index(
        'idx_favorite_user_home_device',
        'favorite_devices',
        ['user_ref', 'home_id', 'device_id'],
    )


def downgrade():
    op.drop_index('idx_favorite_user_home_device', table_name='favorite_devices')
    op.drop_column('favorite_devices', 'primary_entity_id')
    op.drop_column('favorite_devices', 'device_id')
    op.drop_column('favorite_devices', 'kind')
