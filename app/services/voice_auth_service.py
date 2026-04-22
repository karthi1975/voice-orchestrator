"""Voice authentication service.

Business logic for:
  - enrolling automations ("require voice auth before firing X")
  - resolving an enrollment for a VAPI challenge (with cooldown + attempts checks)
  - recording challenge results to the audit log

The VAPI route calls into this service on request_scene_challenge and
verify_challenge_response when variableValues carry (user_ref, automation_id).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from app.domain.voice_auth_enums import (
    ChallengeResult,
    ChallengeType,
    EnrollmentStatus,
)
from app.domain.voice_auth_models import ChallengeLog, Enrollment, PhoneMapping
from app.repositories.voice_auth_repository import (
    IChallengeLogRepository,
    IEnrollmentRepository,
    IPhoneMappingRepository,
)

logger = logging.getLogger(__name__)


# ---------- DTO-ish results ------------------------------------------------


@dataclass
class ResolveOutcome:
    """Result of resolving an enrollment at challenge-request time.

    Exactly one of `enrollment` or `denial_reason` will be set.
    """
    enrollment: Optional[Enrollment] = None
    denial_reason: Optional[ChallengeResult] = None
    detail: Optional[str] = None
    cooldown_remaining_seconds: int = 0
    attempts_remaining: Optional[int] = None

    def denied(self) -> bool:
        return self.enrollment is None


@dataclass
class EnrollmentCheck:
    """Summary for the mobile app's /check endpoint."""
    exists: bool
    enrollment: Optional[Enrollment] = None
    cooldown_remaining_seconds: int = 0
    attempts_remaining: Optional[int] = None
    enrollment_required: bool = False


# ---------- helpers --------------------------------------------------------


ALLOWED_SERVICES = {
    "scene", "script", "switch", "light", "lock", "cover",
    "media_player", "climate", "input_boolean", "fan",
}


def _slug(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_phone(raw: str) -> str:
    """Minimal E.164-ish normalization. Refuses anything that doesn't look
    like a phone number — rejects with ValueError rather than silently munging."""
    if raw is None:
        raise ValueError("phone is required")
    s = "".join(ch for ch in raw.strip() if ch.isdigit() or ch == "+")
    if s.startswith("+"):
        digits = s[1:]
    else:
        digits = s
    if not digits.isdigit() or not (7 <= len(digits) <= 15):
        raise ValueError(f"invalid phone: {raw!r}")
    return "+" + digits if not s.startswith("+") else s


# ---------- main service ---------------------------------------------------


class VoiceAuthService:
    def __init__(
        self,
        enrollment_repo: IEnrollmentRepository,
        log_repo: IChallengeLogRepository,
        phone_repo: IPhoneMappingRepository,
        *,
        fail_window_seconds: int = 3600,
    ):
        self._enrollments = enrollment_repo
        self._logs = log_repo
        self._phones = phone_repo
        self._fail_window = fail_window_seconds

    # ---- Enrollment CRUD --------------------------------------------------

    def create_enrollment(
        self,
        *,
        user_ref: str,
        home_id: str,
        automation_name: str,
        ha_service: str,
        ha_entity: str,
        automation_id: Optional[str] = None,
        challenge_type: ChallengeType = ChallengeType.VERIFICATION,
        max_attempts: int = 3,
        cooldown_seconds: int = 30,
        metadata_json: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Enrollment:
        if not user_ref or not user_ref.strip():
            raise ValueError("user_ref is required")
        if not home_id or not home_id.strip():
            raise ValueError("home_id is required")
        if not automation_name or not automation_name.strip():
            raise ValueError("automation_name is required")
        if ha_service not in ALLOWED_SERVICES:
            raise ValueError(
                f"ha_service must be one of {sorted(ALLOWED_SERVICES)}; got {ha_service!r}"
            )
        if not ha_entity or "." in ha_entity:
            raise ValueError("ha_entity is the entity suffix only, e.g. 'decorations_on'")
        if max_attempts < 1 or max_attempts > 10:
            raise ValueError("max_attempts must be between 1 and 10")
        if cooldown_seconds < 0 or cooldown_seconds > 86_400:
            raise ValueError("cooldown_seconds must be 0..86400")

        aid = _slug(automation_id or automation_name)
        if not aid:
            raise ValueError("automation_id derived to empty; supply one explicitly")

        # Idempotent: if identical enrollment exists, return it instead of erroring
        existing = self._enrollments.get_by_user_and_automation(user_ref, aid)
        if existing:
            return existing

        e = Enrollment(
            id=str(uuid.uuid4()),
            user_ref=user_ref.strip(),
            home_id=home_id.strip(),
            automation_id=aid,
            automation_name=automation_name.strip(),
            ha_service=ha_service,
            ha_entity=ha_entity.strip(),
            status=EnrollmentStatus.ACTIVE,
            challenge_type=challenge_type,
            max_attempts=max_attempts,
            cooldown_seconds=cooldown_seconds,
            metadata_json=metadata_json,
            created_at=datetime.utcnow(),
            created_by=created_by,
        )
        out = self._enrollments.add(e)
        logger.info(f"ENROLLMENT created id={out.id} user={user_ref} automation={aid} home={home_id}")
        return out

    def list_enrollments(
        self, user_ref: str, status: Optional[EnrollmentStatus] = None
    ) -> list[Enrollment]:
        return self._enrollments.list_for_user(user_ref, status)

    def get_enrollment(self, enrollment_id: str) -> Optional[Enrollment]:
        return self._enrollments.get_by_id(enrollment_id)

    def update_status(
        self, enrollment_id: str, new_status: EnrollmentStatus
    ) -> Optional[Enrollment]:
        e = self._enrollments.get_by_id(enrollment_id)
        if not e:
            return None
        # REVOKED is terminal — block reversal at the service layer
        if e.status == EnrollmentStatus.REVOKED:
            raise ValueError("cannot change status of a REVOKED enrollment; create a new one")
        e.status = new_status
        return self._enrollments.update(e)

    def delete_enrollment(self, enrollment_id: str) -> bool:
        return self._enrollments.delete(enrollment_id)

    # ---- Check / resolve for VAPI flow ------------------------------------

    def check(self, user_ref: str, automation_id: str) -> EnrollmentCheck:
        """Summarize enrollment state for the mobile app's /check endpoint."""
        e = self._enrollments.get_by_user_and_automation(user_ref, _slug(automation_id))
        if not e:
            return EnrollmentCheck(exists=False, enrollment_required=True)
        cooldown = self._cooldown_remaining(e)
        attempts_left = self._attempts_remaining(e)
        return EnrollmentCheck(
            exists=True,
            enrollment=e,
            cooldown_remaining_seconds=cooldown,
            attempts_remaining=attempts_left,
        )

    def resolve_for_challenge(
        self, *, user_ref: str, automation_id: str
    ) -> ResolveOutcome:
        """Called by /vapi/auth/request when variableValues carry (user_ref, automation_id).

        Checks:
          - enrollment exists?
          - status == ACTIVE?
          - cooldown window clear?
          - attempts budget remaining?

        Returns an outcome the caller uses to either proceed with a phrase challenge
        or deny with a specific reason.
        """
        if not user_ref or not automation_id:
            return ResolveOutcome(denial_reason=ChallengeResult.DENIED_NO_ENROLLMENT,
                                  detail="missing user_ref or automation_id")

        e = self._enrollments.get_by_user_and_automation(user_ref, _slug(automation_id))
        if not e:
            return ResolveOutcome(denial_reason=ChallengeResult.DENIED_NO_ENROLLMENT,
                                  detail="no enrollment for user+automation")

        if e.status != EnrollmentStatus.ACTIVE:
            return ResolveOutcome(denial_reason=ChallengeResult.DENIED_LOCKED,
                                  detail=f"enrollment status is {e.status.value}")

        cooldown = self._cooldown_remaining(e)
        if cooldown > 0:
            return ResolveOutcome(
                denial_reason=ChallengeResult.DENIED_COOLDOWN,
                detail=f"{cooldown}s cooldown remaining",
                cooldown_remaining_seconds=cooldown,
            )

        attempts_left = self._attempts_remaining(e)
        if attempts_left is not None and attempts_left <= 0:
            return ResolveOutcome(
                denial_reason=ChallengeResult.DENIED_LOCKED,
                detail="max attempts exhausted in window",
                attempts_remaining=0,
            )

        return ResolveOutcome(
            enrollment=e,
            cooldown_remaining_seconds=cooldown,
            attempts_remaining=attempts_left,
        )

    # ---- Challenge log lifecycle -----------------------------------------

    def open_log(
        self,
        *,
        enrollment: Optional[Enrollment],
        user_ref: str,
        automation_id: str,
        vapi_call_id: Optional[str],
        initiated_by: Optional[str],
        home_id: Optional[str] = None,
        request_payload: Optional[str] = None,
        initial_result: ChallengeResult = ChallengeResult.PENDING,
        failure_reason: Optional[str] = None,
    ) -> ChallengeLog:
        l = ChallengeLog(
            id=str(uuid.uuid4()),
            enrollment_id=enrollment.id if enrollment else None,
            user_ref=user_ref,
            home_id=home_id or (enrollment.home_id if enrollment else None),
            automation_id=_slug(automation_id),
            vapi_call_id=vapi_call_id,
            initiated_by=initiated_by,
            result=initial_result,
            failure_reason=failure_reason,
            started_at=datetime.utcnow(),
            request_payload=request_payload,
            completed_at=datetime.utcnow() if ChallengeResult.is_terminal(initial_result) else None,
        )
        out = self._logs.add(l)
        logger.info(
            f"CHALLENGE_LOG open id={out.id} user={user_ref} "
            f"automation={automation_id} result={out.result.value} call={vapi_call_id}"
        )
        return out

    def close_log(
        self,
        log_id: str,
        *,
        result: ChallengeResult,
        failure_reason: Optional[str] = None,
        response_payload: Optional[str] = None,
        confidence_score: Optional[float] = None,
    ) -> Optional[ChallengeLog]:
        l = self._logs.get_by_id(log_id)
        if not l:
            logger.warning(f"close_log: no log {log_id}")
            return None
        l.result = result
        l.failure_reason = failure_reason
        l.response_payload = response_payload
        l.confidence_score = confidence_score
        l.completed_at = datetime.utcnow()
        updated = self._logs.update(l)
        logger.info(
            f"CHALLENGE_LOG close id={log_id} result={result.value} "
            f"user={l.user_ref} automation={l.automation_id}"
        )
        return updated

    def recent_logs(self, user_ref: str, limit: int = 50) -> list[ChallengeLog]:
        return self._logs.list_for_user(user_ref, limit=limit)

    # ---- Phone mappings ---------------------------------------------------

    def map_phone(
        self,
        *,
        phone: str,
        user_ref: str,
        home_id: str,
        vapi_phone_number_id: Optional[str] = None,
        label: Optional[str] = None,
    ) -> PhoneMapping:
        normalized = _normalize_phone(phone)
        existing = self._phones.get_by_phone(normalized)
        if existing and existing.is_active:
            # idempotent if same user+home
            if existing.user_ref == user_ref and existing.home_id == home_id:
                return existing
            raise ValueError(f"phone {normalized} already mapped to another user/home")
        p = PhoneMapping(
            id=str(uuid.uuid4()),
            phone_e164=normalized,
            user_ref=user_ref,
            home_id=home_id,
            vapi_phone_number_id=vapi_phone_number_id,
            label=label,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        return self._phones.add(p)

    def lookup_phone(self, phone: str) -> Optional[PhoneMapping]:
        try:
            return self._phones.get_by_phone(_normalize_phone(phone))
        except ValueError:
            return None

    def list_phones_for_user(self, user_ref: str) -> list[PhoneMapping]:
        return self._phones.list_for_user(user_ref)

    def delete_phone(self, mapping_id: str) -> bool:
        return self._phones.delete(mapping_id)

    # ---- Internal helpers -------------------------------------------------

    def _cooldown_remaining(self, e: Enrollment) -> int:
        last = self._logs.last_success_for(e.user_ref, e.automation_id)
        if not last or not last.completed_at:
            return 0
        elapsed = (datetime.utcnow() - last.completed_at).total_seconds()
        remaining = e.cooldown_seconds - int(elapsed)
        return max(0, remaining)

    def _attempts_remaining(self, e: Enrollment) -> Optional[int]:
        if e.max_attempts is None:
            return None
        since = datetime.utcnow() - timedelta(seconds=self._fail_window)
        fails = self._logs.count_fails_since(e.user_ref, e.automation_id, since)
        return max(0, e.max_attempts - fails)
