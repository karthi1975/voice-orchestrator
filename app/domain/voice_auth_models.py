"""Domain dataclasses for voice authentication.

Pure Python; no framework / ORM dependencies. Repositories translate to/from
these and whatever storage backs them (SQLAlchemy or in-memory).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.voice_auth_enums import (
    ChallengeResult,
    ChallengeType,
    EnrollmentStatus,
)


@dataclass
class Enrollment:
    """A user's opt-in saying 'require voice auth before firing this automation'.

    Invariant: (user_ref, automation_id) is unique. Enforced at DB level via
    uq_enrollment_user_automation. The same user can enroll the SAME automation
    on a DIFFERENT home by using a different automation_id (e.g., "decorations_on_home1").
    """
    id: str
    user_ref: str
    home_id: str
    automation_id: str            # client-supplied stable key
    automation_name: str           # display label, e.g. "Decorations On"
    ha_service: str                # scene | script | switch | light | lock | ...
    ha_entity: str                 # entity suffix, e.g. "decorations_on"
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    challenge_type: ChallengeType = ChallengeType.VERIFICATION
    max_attempts: int = 3
    cooldown_seconds: int = 30
    metadata_json: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    def is_active(self) -> bool:
        return self.status == EnrollmentStatus.ACTIVE


@dataclass
class ChallengeLog:
    """One row per challenge attempt. Keeps denormalized keys so the row is
    still useful even if the parent enrollment is later deleted."""
    id: str
    user_ref: str
    automation_id: str
    started_at: datetime
    result: ChallengeResult = ChallengeResult.PENDING
    enrollment_id: Optional[str] = None
    home_id: Optional[str] = None
    vapi_call_id: Optional[str] = None
    initiated_by: Optional[str] = None
    failure_reason: Optional[str] = None
    confidence_score: Optional[float] = None
    request_payload: Optional[str] = None    # redacted JSON string
    response_payload: Optional[str] = None   # redacted JSON string
    completed_at: Optional[datetime] = None


@dataclass
class PhoneMapping:
    """Maps a caller phone number (E.164) to a user_ref + home.

    Used on inbound VAPI phone calls so the assistant knows who is calling
    without asking. The phone number is treated as an identifier, not an
    authenticator — the challenge phrase remains the actual gate.
    """
    id: str
    phone_e164: str
    user_ref: str
    home_id: str
    vapi_phone_number_id: Optional[str] = None
    label: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
