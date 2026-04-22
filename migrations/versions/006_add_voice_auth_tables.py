"""Add voice auth enrollments, challenge logs, and phone mappings

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa


revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # voice_auth_enrollments — per-user opt-in: "require voice auth for this automation"
    op.create_table(
        'voice_auth_enrollments',
        sa.Column('id', sa.String(64), primary_key=True),

        # External-facing user ref (opaque id from SmartHome app's auth system)
        sa.Column('user_ref', sa.String(255), nullable=False, index=True),

        # Which home's HA to dispatch to; FK to existing homes table
        sa.Column('home_id', sa.String(255), sa.ForeignKey('homes.home_id'), nullable=False, index=True),

        # Stable client-supplied id for the automation (slug or UUID from the mobile app)
        sa.Column('automation_id', sa.String(255), nullable=False),
        sa.Column('automation_name', sa.String(255), nullable=False),

        # What to fire on success — mirrors HADirectDispatcher's dispatch target
        sa.Column('ha_service', sa.String(64), nullable=False),   # scene | script | switch | light | ...
        sa.Column('ha_entity', sa.String(255), nullable=False),   # entity suffix, e.g. "decorations_on"

        # Lifecycle / policy
        sa.Column('status', sa.String(32), nullable=False, server_default='ACTIVE'),     # ACTIVE | PAUSED | REVOKED
        sa.Column('challenge_type', sa.String(32), nullable=False, server_default='VERIFICATION'),  # VERIFICATION | STEP_UP | CONFIRMATION
        sa.Column('max_attempts', sa.Integer, nullable=False, server_default='3'),
        sa.Column('cooldown_seconds', sa.Integer, nullable=False, server_default='30'),

        # Free-form JSON for per-enrollment flags (locale, risk, channel, etc.)
        sa.Column('metadata_json', sa.Text, nullable=True),

        # Audit
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),

        sa.UniqueConstraint('user_ref', 'automation_id', name='uq_enrollment_user_automation'),
    )
    op.create_index('idx_enrollment_user_ref', 'voice_auth_enrollments', ['user_ref'])
    op.create_index('idx_enrollment_home_id', 'voice_auth_enrollments', ['home_id'])
    op.create_index('idx_enrollment_status', 'voice_auth_enrollments', ['status'])

    # voice_auth_challenge_logs — audit trail for every challenge attempt
    op.create_table(
        'voice_auth_challenge_logs',
        sa.Column('id', sa.String(64), primary_key=True),

        # FK to enrollment; NULL if the challenge was orphaned (enrollment revoked mid-flight)
        sa.Column('enrollment_id', sa.String(64),
                  sa.ForeignKey('voice_auth_enrollments.id', ondelete='SET NULL'),
                  nullable=True, index=True),

        # Denormalized keys so logs remain queryable if the enrollment is deleted
        sa.Column('user_ref', sa.String(255), nullable=False, index=True),
        sa.Column('home_id', sa.String(255), nullable=True, index=True),
        sa.Column('automation_id', sa.String(255), nullable=False),

        # VAPI call correlation
        sa.Column('vapi_call_id', sa.String(255), nullable=True, index=True),

        # Who triggered this challenge
        sa.Column('initiated_by', sa.String(64), nullable=True),  # MOBILE_IOS | MOBILE_ANDROID | WEB | SYSTEM | AGENT

        # Result
        sa.Column('result', sa.String(32), nullable=False, server_default='PENDING'),
        # PENDING | SUCCESS | FAIL | TIMEOUT | ERROR | ABANDONED | DENIED_COOLDOWN | DENIED_LOCKED | DENIED_NO_ENROLLMENT
        sa.Column('failure_reason', sa.String(255), nullable=True),
        sa.Column('confidence_score', sa.Float, nullable=True),   # reserved for voiceprint; NULL for phrase challenges

        # Redacted payloads (no raw audio, no PHI)
        sa.Column('request_payload', sa.Text, nullable=True),
        sa.Column('response_payload', sa.Text, nullable=True),

        sa.Column('started_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
    )
    op.create_index('idx_challenge_log_user_time', 'voice_auth_challenge_logs', ['user_ref', 'started_at'])
    op.create_index('idx_challenge_log_result_time', 'voice_auth_challenge_logs', ['result', 'started_at'])

    # voice_auth_phone_mappings — caller phone number -> user_ref/home_id
    # For inbound VAPI phone calls, caller is identified by From-number and injected
    # as metadata so the assistant knows which user + home to act on.
    op.create_table(
        'voice_auth_phone_mappings',
        sa.Column('id', sa.String(64), primary_key=True),

        # E.164 normalized phone number (leading +, digits only); unique — one phone -> one identity
        sa.Column('phone_e164', sa.String(32), nullable=False, unique=True, index=True),

        sa.Column('user_ref', sa.String(255), nullable=False, index=True),
        sa.Column('home_id', sa.String(255), sa.ForeignKey('homes.home_id'), nullable=False, index=True),

        # Optional: restrict to a specific VAPI phone number (if you have multiple numbers per tenant)
        sa.Column('vapi_phone_number_id', sa.String(255), nullable=True),

        sa.Column('label', sa.String(255), nullable=True),       # e.g., "Scott's mobile"
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true')),

        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table('voice_auth_phone_mappings')
    op.drop_index('idx_challenge_log_result_time', table_name='voice_auth_challenge_logs')
    op.drop_index('idx_challenge_log_user_time', table_name='voice_auth_challenge_logs')
    op.drop_table('voice_auth_challenge_logs')
    op.drop_index('idx_enrollment_status', table_name='voice_auth_enrollments')
    op.drop_index('idx_enrollment_home_id', table_name='voice_auth_enrollments')
    op.drop_index('idx_enrollment_user_ref', table_name='voice_auth_enrollments')
    op.drop_table('voice_auth_enrollments')
