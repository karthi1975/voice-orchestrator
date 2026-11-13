"""Add nullable gender to users ("female" | "male" | NULL = not specified)

Sent to the health educator portal at single sign-on, where it selects the
gender-specific education material. NULL keeps every existing user exactly
as before.

Additive only: no existing rows are modified or removed.

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa


revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'gender' not in cols:  # tolerate create_all() having run first
        op.add_column('users', sa.Column('gender', sa.String(16), nullable=True))


def downgrade():
    op.drop_column('users', 'gender')
