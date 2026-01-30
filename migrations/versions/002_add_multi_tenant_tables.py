"""Add multi-tenant tables (users and homes)

Revision ID: 002
Revises: 001
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create users and homes tables."""

    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('user_id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )

    # Create indexes for users
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_is_active', 'users', ['is_active'])
    op.create_index('ix_users_created_at', 'users', ['created_at'])

    # Create homes table
    op.create_table(
        'homes',
        sa.Column('home_id', sa.String(255), nullable=False),
        sa.Column('user_id', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('ha_url', sa.String(500), nullable=False),
        sa.Column('ha_webhook_id', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('home_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
    )

    # Create indexes for homes
    op.create_index('idx_homes_user_id', 'homes', ['user_id'])
    op.create_index('idx_homes_is_active', 'homes', ['is_active'])
    op.create_index('ix_homes_created_at', 'homes', ['created_at'])
    op.create_index('idx_user_home_unique', 'homes', ['user_id', 'home_id'], unique=True)


def downgrade() -> None:
    """Drop users and homes tables."""
    op.drop_table('homes')
    op.drop_table('users')
