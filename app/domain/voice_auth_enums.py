"""Enums for voice authentication enrollments and challenges."""

from enum import Enum


class EnrollmentStatus(str, Enum):
    """Lifecycle of a voice-auth enrollment.

    ACTIVE    — enrolled; challenges permitted.
    PAUSED    — temporarily disabled (user can reactivate without re-enrolling).
    REVOKED   — terminal; user must re-enroll to use again.
    """
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"


class ChallengeType(str, Enum):
    """Why the challenge is being run.

    VERIFICATION — routine identity/presence check before action.
    STEP_UP      — elevated risk; app wants an extra guard.
    CONFIRMATION — low-risk "are you sure" (still uses a challenge phrase).
    """
    VERIFICATION = "VERIFICATION"
    STEP_UP = "STEP_UP"
    CONFIRMATION = "CONFIRMATION"


class ChallengeResult(str, Enum):
    """Outcome of one challenge attempt.

    PENDING               — in flight (issued; awaiting verify).
    SUCCESS               — phrase matched; action dispatched.
    FAIL                  — phrase mismatch within attempts.
    TIMEOUT               — challenge TTL expired before verify.
    ERROR                 — upstream error (HA unreachable, misconfig, etc.).
    ABANDONED             — user ended the call before answering.
    DENIED_COOLDOWN       — rejected before issuing: cooldown window active.
    DENIED_LOCKED         — rejected: enrollment status != ACTIVE.
    DENIED_NO_ENROLLMENT  — rejected: no enrollment for (user_ref, automation_id).
    """
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    ABANDONED = "ABANDONED"
    DENIED_COOLDOWN = "DENIED_COOLDOWN"
    DENIED_LOCKED = "DENIED_LOCKED"
    DENIED_NO_ENROLLMENT = "DENIED_NO_ENROLLMENT"

    @classmethod
    def is_terminal(cls, v: "ChallengeResult") -> bool:
        return v is not cls.PENDING

    @classmethod
    def is_denial(cls, v: "ChallengeResult") -> bool:
        return v in (cls.DENIED_COOLDOWN, cls.DENIED_LOCKED, cls.DENIED_NO_ENROLLMENT)
