"""Add nullable default_home_id to users (per-account preferred home)

NULL = no preference: login keeps returning the oldest home the user belongs
to, exactly as before. The value is only honoured while the user is still a
member of that home and the home is active (fallback rule in
MobileAuthService.bootstrap), so no cleanup is needed when memberships change.

Additive only: no existing rows are modified or removed.

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa


revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'default_home_id' not in cols:  # tolerate create_all() having run first
        op.add_column('users',
                      sa.Column('default_home_id', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('users', 'default_home_id')
