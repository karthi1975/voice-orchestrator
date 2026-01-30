"""Add home_id to challenges table

Revision ID: 003
Revises: 002
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add home_id column to challenges table."""

    # Add home_id column (nullable for backward compatibility)
    op.add_column(
        'challenges',
        sa.Column('home_id', sa.String(255), nullable=True)
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_challenges_home_id',
        'challenges',
        'homes',
        ['home_id'],
        ['home_id']
    )

    # Create indexes
    op.create_index('idx_challenges_home_id', 'challenges', ['home_id'])
    op.create_index('idx_challenges_home_status', 'challenges', ['home_id', 'status'])


def downgrade() -> None:
    """Remove home_id column from challenges table."""
    op.drop_index('idx_challenges_home_status', table_name='challenges')
    op.drop_index('idx_challenges_home_id', table_name='challenges')
    op.drop_constraint('fk_challenges_home_id', 'challenges', type_='foreignkey')
    op.drop_column('challenges', 'home_id')
