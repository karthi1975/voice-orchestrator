"""Add home_members (shared homes) and home_invites (OTP-style join codes)

home_members lets a home be listed for several users at once. It is
backfilled with one 'owner' row per existing home (from homes.user_id) so
nobody loses access. homes.user_id is kept untouched as the legacy owner
column. home_invites holds admin-generated codes that attach a user to a
home at sign-up (or later via /auth/redeem-invite).

Additive only: no existing rows are modified or removed.

Revision ID: 011
Revises: 010
"""
from alembic import op
import sqlalchemy as sa


revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    # The app also runs Base.metadata.create_all() at boot, so tolerate the
    # tables already existing (e.g. app started before this migration ran).
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade():
    if not _has_table('home_members'):
        op.create_table(
            'home_members',
            sa.Column('home_id', sa.String(255),
                      sa.ForeignKey('homes.home_id'), primary_key=True),
            sa.Column('user_id', sa.String(255),
                      sa.ForeignKey('users.user_id'), primary_key=True),
            sa.Column('role', sa.String(32), nullable=False,
                      server_default='member'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('idx_home_members_user_id', 'home_members', ['user_id'])

    # Backfill: every current owner becomes an 'owner' member. Idempotent —
    # skips pairs that already exist.
    op.execute("""
        INSERT INTO home_members (home_id, user_id, role, created_at)
        SELECT h.home_id, h.user_id, 'owner', h.created_at
          FROM homes h
         WHERE NOT EXISTS (
               SELECT 1 FROM home_members m
                WHERE m.home_id = h.home_id AND m.user_id = h.user_id)
    """)

    if not _has_table('home_invites'):
        op.create_table(
            'home_invites',
            sa.Column('code', sa.String(32), primary_key=True),
            sa.Column('home_id', sa.String(255),
                      sa.ForeignKey('homes.home_id'), nullable=False),
            sa.Column('role', sa.String(32), nullable=False,
                      server_default='member'),
            sa.Column('created_by', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('max_uses', sa.Integer(), nullable=False,
                      server_default='1'),
            sa.Column('use_count', sa.Integer(), nullable=False,
                      server_default='0'),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_home_invites_home_id', 'home_invites', ['home_id'])


def downgrade():
    op.drop_table('home_invites')
    op.drop_table('home_members')
