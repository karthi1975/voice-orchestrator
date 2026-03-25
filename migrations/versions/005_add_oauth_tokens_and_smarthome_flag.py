"""Add OAuth tokens table and smarthome_enabled flag

Revision ID: 005
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'

def upgrade():
    # Create oauth_tokens table
    op.create_table(
        'oauth_tokens',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('home_id', sa.String(255), sa.ForeignKey('homes.home_id'), nullable=False, index=True),
        sa.Column('access_token', sa.String(2000), nullable=False, unique=True, index=True),
        sa.Column('refresh_token', sa.String(2000), nullable=False, unique=True),
        sa.Column('token_type', sa.String(50), nullable=False, server_default='bearer'),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('amazon_user_id', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )

    # Add smarthome_enabled to scene_webhook_mappings
    op.add_column('scene_webhook_mappings',
        sa.Column('smarthome_enabled', sa.Boolean, nullable=False, server_default='true')
    )

def downgrade():
    op.drop_column('scene_webhook_mappings', 'smarthome_enabled')
    op.drop_table('oauth_tokens')
