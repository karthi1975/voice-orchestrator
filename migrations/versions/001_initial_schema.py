"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create challenges table."""
    op.create_table(
        'challenges',
        sa.Column('id', sa.String(255), nullable=False),
        sa.Column('identifier', sa.String(255), nullable=False),
        sa.Column('phrase', sa.String(100), nullable=False),
        sa.Column('client_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('intent', sa.String(100), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_challenges_identifier', 'challenges', ['identifier'])
    op.create_index('ix_challenges_client_type', 'challenges', ['client_type'])
    op.create_index('ix_challenges_status', 'challenges', ['status'])
    op.create_index('ix_challenges_created_at', 'challenges', ['created_at'])
    op.create_index('ix_challenges_expires_at', 'challenges', ['expires_at'])
    
    # Create composite indexes
    op.create_index('idx_identifier_client_type', 'challenges', ['identifier', 'client_type'])
    op.create_index('idx_client_type_status', 'challenges', ['client_type', 'status'])
    op.create_index('idx_expires_at_status', 'challenges', ['expires_at', 'status'])


def downgrade() -> None:
    """Drop challenges table."""
    op.drop_table('challenges')
