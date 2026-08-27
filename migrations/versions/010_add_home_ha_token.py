"""Add nullable ha_token_encrypted to homes (encrypted HA long-lived token)

Additive only: existing rows untouched (NULL = no DB token; dispatcher falls
back to the legacy HOME_CONFIGS_JSON env var). No data modified or removed.

Revision ID: 010
Revises: 009
"""
from alembic import op
import sqlalchemy as sa


revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('homes',
                  sa.Column('ha_token_encrypted', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('homes', 'ha_token_encrypted')
