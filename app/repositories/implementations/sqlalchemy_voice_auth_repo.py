"""SQLAlchemy implementations for voice-auth repositories."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.voice_auth_enums import ChallengeResult, EnrollmentStatus
from app.domain.voice_auth_models import ChallengeLog, Enrollment, PhoneMapping
from app.repositories.voice_auth_repository import (
    IChallengeLogRepository,
    IEnrollmentRepository,
    IPhoneMappingRepository,
)
from app.repositories.implementations.sqlalchemy_models import (
    VoiceAuthChallengeLogModel,
    VoiceAuthEnrollmentModel,
    VoiceAuthPhoneMappingModel,
)


# ------- Enrollments --------------------------------------------------------


def _to_enrollment(m: VoiceAuthEnrollmentModel) -> Enrollment:
    return Enrollment(
        id=m.id,
        user_ref=m.user_ref,
        home_id=m.home_id,
        automation_id=m.automation_id,
        automation_name=m.automation_name,
        ha_service=m.ha_service,
        ha_entity=m.ha_entity,
        status=EnrollmentStatus(m.status),
        challenge_type=_safe_challenge_type(m.challenge_type),
        max_attempts=m.max_attempts,
        cooldown_seconds=m.cooldown_seconds,
        metadata_json=m.metadata_json,
        created_at=m.created_at,
        updated_at=m.updated_at,
        created_by=m.created_by,
    )


def _safe_challenge_type(v: str):
    from app.domain.voice_auth_enums import ChallengeType
    try:
        return ChallengeType(v)
    except ValueError:
        return ChallengeType.VERIFICATION


def _apply_to_model(model: VoiceAuthEnrollmentModel, e: Enrollment) -> None:
    model.user_ref = e.user_ref
    model.home_id = e.home_id
    model.automation_id = e.automation_id
    model.automation_name = e.automation_name
    model.ha_service = e.ha_service
    model.ha_entity = e.ha_entity
    model.status = e.status.value
    model.challenge_type = e.challenge_type.value
    model.max_attempts = e.max_attempts
    model.cooldown_seconds = e.cooldown_seconds
    model.metadata_json = e.metadata_json
    model.created_at = e.created_at
    model.updated_at = e.updated_at
    model.created_by = e.created_by


class SQLAlchemyEnrollmentRepository(IEnrollmentRepository):
    def __init__(self, session: Session):
        self._s = session

    def add(self, e: Enrollment) -> Enrollment:
        m = VoiceAuthEnrollmentModel(id=e.id)
        _apply_to_model(m, e)
        self._s.add(m)
        self._s.commit()
        self._s.refresh(m)
        return _to_enrollment(m)

    def get_by_id(self, enrollment_id: str) -> Optional[Enrollment]:
        m = self._s.get(VoiceAuthEnrollmentModel, enrollment_id)
        return _to_enrollment(m) if m else None

    def get_by_user_and_automation(self, user_ref: str, automation_id: str) -> Optional[Enrollment]:
        m = self._s.execute(
            select(VoiceAuthEnrollmentModel)
            .where(VoiceAuthEnrollmentModel.user_ref == user_ref)
            .where(VoiceAuthEnrollmentModel.automation_id == automation_id)
        ).scalar_one_or_none()
        return _to_enrollment(m) if m else None

    def list_for_user(self, user_ref: str,
                      status: Optional[EnrollmentStatus] = None) -> List[Enrollment]:
        stmt = select(VoiceAuthEnrollmentModel).where(VoiceAuthEnrollmentModel.user_ref == user_ref)
        if status:
            stmt = stmt.where(VoiceAuthEnrollmentModel.status == status.value)
        stmt = stmt.order_by(VoiceAuthEnrollmentModel.created_at.desc())
        return [_to_enrollment(m) for m in self._s.execute(stmt).scalars().all()]

    def list_for_home(self, home_id: str) -> List[Enrollment]:
        stmt = (select(VoiceAuthEnrollmentModel)
                .where(VoiceAuthEnrollmentModel.home_id == home_id)
                .order_by(VoiceAuthEnrollmentModel.created_at.desc()))
        return [_to_enrollment(m) for m in self._s.execute(stmt).scalars().all()]

    def update(self, e: Enrollment) -> Enrollment:
        m = self._s.get(VoiceAuthEnrollmentModel, e.id)
        if not m:
            raise KeyError(f"Enrollment {e.id} not found")
        e.updated_at = datetime.utcnow()
        _apply_to_model(m, e)
        self._s.commit()
        self._s.refresh(m)
        return _to_enrollment(m)

    def delete(self, enrollment_id: str) -> bool:
        m = self._s.get(VoiceAuthEnrollmentModel, enrollment_id)
        if not m:
            return False
        self._s.delete(m)
        self._s.commit()
        return True


# ------- Challenge logs -----------------------------------------------------


def _to_log(m: VoiceAuthChallengeLogModel) -> ChallengeLog:
    return ChallengeLog(
        id=m.id,
        enrollment_id=m.enrollment_id,
        user_ref=m.user_ref,
        home_id=m.home_id,
        automation_id=m.automation_id,
        vapi_call_id=m.vapi_call_id,
        initiated_by=m.initiated_by,
        result=ChallengeResult(m.result),
        failure_reason=m.failure_reason,
        confidence_score=m.confidence_score,
        request_payload=m.request_payload,
        response_payload=m.response_payload,
        started_at=m.started_at,
        completed_at=m.completed_at,
    )


def _log_to_model(m: VoiceAuthChallengeLogModel, l: ChallengeLog) -> None:
    m.enrollment_id = l.enrollment_id
    m.user_ref = l.user_ref
    m.home_id = l.home_id
    m.automation_id = l.automation_id
    m.vapi_call_id = l.vapi_call_id
    m.initiated_by = l.initiated_by
    m.result = l.result.value
    m.failure_reason = l.failure_reason
    m.confidence_score = l.confidence_score
    m.request_payload = l.request_payload
    m.response_payload = l.response_payload
    m.started_at = l.started_at
    m.completed_at = l.completed_at


class SQLAlchemyChallengeLogRepository(IChallengeLogRepository):
    def __init__(self, session: Session):
        self._s = session

    def add(self, l: ChallengeLog) -> ChallengeLog:
        m = VoiceAuthChallengeLogModel(id=l.id)
        _log_to_model(m, l)
        self._s.add(m)
        self._s.commit()
        self._s.refresh(m)
        return _to_log(m)

    def get_by_id(self, log_id: str) -> Optional[ChallengeLog]:
        m = self._s.get(VoiceAuthChallengeLogModel, log_id)
        return _to_log(m) if m else None

    def get_by_vapi_call_id(self, vapi_call_id: str) -> Optional[ChallengeLog]:
        m = self._s.execute(
            select(VoiceAuthChallengeLogModel)
            .where(VoiceAuthChallengeLogModel.vapi_call_id == vapi_call_id)
            .order_by(VoiceAuthChallengeLogModel.started_at.desc())
        ).scalars().first()
        return _to_log(m) if m else None

    def update(self, l: ChallengeLog) -> ChallengeLog:
        m = self._s.get(VoiceAuthChallengeLogModel, l.id)
        if not m:
            raise KeyError(f"ChallengeLog {l.id} not found")
        _log_to_model(m, l)
        self._s.commit()
        self._s.refresh(m)
        return _to_log(m)

    def list_for_user(self, user_ref: str, limit: int = 50) -> List[ChallengeLog]:
        stmt = (select(VoiceAuthChallengeLogModel)
                .where(VoiceAuthChallengeLogModel.user_ref == user_ref)
                .order_by(VoiceAuthChallengeLogModel.started_at.desc())
                .limit(max(1, min(limit, 500))))
        return [_to_log(m) for m in self._s.execute(stmt).scalars().all()]

    def last_success_for(self, user_ref: str, automation_id: str) -> Optional[ChallengeLog]:
        m = self._s.execute(
            select(VoiceAuthChallengeLogModel)
            .where(VoiceAuthChallengeLogModel.user_ref == user_ref)
            .where(VoiceAuthChallengeLogModel.automation_id == automation_id)
            .where(VoiceAuthChallengeLogModel.result == ChallengeResult.SUCCESS.value)
            .order_by(VoiceAuthChallengeLogModel.started_at.desc())
        ).scalars().first()
        return _to_log(m) if m else None

    def count_fails_since(self, user_ref: str, automation_id: str, since: datetime) -> int:
        return self._s.execute(
            select(func.count(VoiceAuthChallengeLogModel.id))
            .where(VoiceAuthChallengeLogModel.user_ref == user_ref)
            .where(VoiceAuthChallengeLogModel.automation_id == automation_id)
            .where(VoiceAuthChallengeLogModel.result == ChallengeResult.FAIL.value)
            .where(VoiceAuthChallengeLogModel.started_at >= since)
        ).scalar_one()


# ------- Phone mappings -----------------------------------------------------


def _to_phone(m: VoiceAuthPhoneMappingModel) -> PhoneMapping:
    return PhoneMapping(
        id=m.id,
        phone_e164=m.phone_e164,
        user_ref=m.user_ref,
        home_id=m.home_id,
        vapi_phone_number_id=m.vapi_phone_number_id,
        label=m.label,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _phone_to_model(m: VoiceAuthPhoneMappingModel, p: PhoneMapping) -> None:
    m.phone_e164 = p.phone_e164
    m.user_ref = p.user_ref
    m.home_id = p.home_id
    m.vapi_phone_number_id = p.vapi_phone_number_id
    m.label = p.label
    m.is_active = p.is_active
    m.created_at = p.created_at
    m.updated_at = p.updated_at


class SQLAlchemyPhoneMappingRepository(IPhoneMappingRepository):
    def __init__(self, session: Session):
        self._s = session

    def add(self, p: PhoneMapping) -> PhoneMapping:
        m = VoiceAuthPhoneMappingModel(id=p.id)
        _phone_to_model(m, p)
        self._s.add(m)
        self._s.commit()
        self._s.refresh(m)
        return _to_phone(m)

    def get_by_phone(self, phone_e164: str) -> Optional[PhoneMapping]:
        m = self._s.execute(
            select(VoiceAuthPhoneMappingModel)
            .where(VoiceAuthPhoneMappingModel.phone_e164 == phone_e164)
            .where(VoiceAuthPhoneMappingModel.is_active.is_(True))
        ).scalar_one_or_none()
        return _to_phone(m) if m else None

    def list_for_user(self, user_ref: str) -> List[PhoneMapping]:
        stmt = (select(VoiceAuthPhoneMappingModel)
                .where(VoiceAuthPhoneMappingModel.user_ref == user_ref)
                .order_by(VoiceAuthPhoneMappingModel.created_at.desc()))
        return [_to_phone(m) for m in self._s.execute(stmt).scalars().all()]

    def update(self, p: PhoneMapping) -> PhoneMapping:
        m = self._s.get(VoiceAuthPhoneMappingModel, p.id)
        if not m:
            raise KeyError(f"PhoneMapping {p.id} not found")
        p.updated_at = datetime.utcnow()
        _phone_to_model(m, p)
        self._s.commit()
        self._s.refresh(m)
        return _to_phone(m)

    def delete(self, mapping_id: str) -> bool:
        m = self._s.get(VoiceAuthPhoneMappingModel, mapping_id)
        if not m:
            return False
        self._s.delete(m)
        self._s.commit()
        return True
