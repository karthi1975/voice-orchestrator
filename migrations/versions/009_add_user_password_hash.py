"""Add nullable password_hash to users for mobile app login

Additive only: existing rows are untouched (password_hash stays NULL,
which simply means "cannot log in yet"). No data is modified or removed.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa


revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users',
                  sa.Column('password_hash', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('users', 'password_hash')
