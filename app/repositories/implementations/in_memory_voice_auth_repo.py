"""In-memory implementations of voice-auth repositories (for tests + dev)."""

from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Dict, List, Optional

from app.domain.voice_auth_enums import ChallengeResult, EnrollmentStatus
from app.domain.voice_auth_models import ChallengeLog, Enrollment, PhoneMapping
from app.repositories.voice_auth_repository import (
    IChallengeLogRepository,
    IEnrollmentRepository,
    IPhoneMappingRepository,
)


class InMemoryEnrollmentRepository(IEnrollmentRepository):
    def __init__(self):
        self._by_id: Dict[str, Enrollment] = {}
        self._lock = RLock()

    def add(self, e: Enrollment) -> Enrollment:
        with self._lock:
            for existing in self._by_id.values():
                if existing.user_ref == e.user_ref and existing.automation_id == e.automation_id:
                    raise ValueError(
                        f"duplicate enrollment for user_ref={e.user_ref}, "
                        f"automation_id={e.automation_id}"
                    )
            self._by_id[e.id] = replace(e)
            return replace(self._by_id[e.id])

    def get_by_id(self, enrollment_id: str) -> Optional[Enrollment]:
        with self._lock:
            m = self._by_id.get(enrollment_id)
            return replace(m) if m else None

    def get_by_user_and_automation(self, user_ref: str, automation_id: str) -> Optional[Enrollment]:
        with self._lock:
            for e in self._by_id.values():
                if e.user_ref == user_ref and e.automation_id == automation_id:
                    return replace(e)
            return None

    def list_for_user(self, user_ref: str,
                      status: Optional[EnrollmentStatus] = None) -> List[Enrollment]:
        with self._lock:
            out = [e for e in self._by_id.values() if e.user_ref == user_ref]
            if status:
                out = [e for e in out if e.status == status]
            return [replace(e) for e in sorted(out, key=lambda x: x.created_at, reverse=True)]

    def list_for_home(self, home_id: str) -> List[Enrollment]:
        with self._lock:
            out = [e for e in self._by_id.values() if e.home_id == home_id]
            return [replace(e) for e in sorted(out, key=lambda x: x.created_at, reverse=True)]

    def update(self, e: Enrollment) -> Enrollment:
        with self._lock:
            if e.id not in self._by_id:
                raise KeyError(e.id)
            e.updated_at = datetime.utcnow()
            self._by_id[e.id] = replace(e)
            return replace(self._by_id[e.id])

    def delete(self, enrollment_id: str) -> bool:
        with self._lock:
            return self._by_id.pop(enrollment_id, None) is not None


class InMemoryChallengeLogRepository(IChallengeLogRepository):
    def __init__(self):
        self._by_id: Dict[str, ChallengeLog] = {}
        self._lock = RLock()

    def add(self, l: ChallengeLog) -> ChallengeLog:
        with self._lock:
            self._by_id[l.id] = replace(l)
            return replace(self._by_id[l.id])

    def get_by_id(self, log_id: str) -> Optional[ChallengeLog]:
        with self._lock:
            m = self._by_id.get(log_id)
            return replace(m) if m else None

    def get_by_vapi_call_id(self, vapi_call_id: str) -> Optional[ChallengeLog]:
        with self._lock:
            matches = [l for l in self._by_id.values() if l.vapi_call_id == vapi_call_id]
            if not matches:
                return None
            return replace(sorted(matches, key=lambda x: x.started_at, reverse=True)[0])

    def update(self, l: ChallengeLog) -> ChallengeLog:
        with self._lock:
            if l.id not in self._by_id:
                raise KeyError(l.id)
            self._by_id[l.id] = replace(l)
            return replace(self._by_id[l.id])

    def list_for_user(self, user_ref: str, limit: int = 50) -> List[ChallengeLog]:
        with self._lock:
            out = [l for l in self._by_id.values() if l.user_ref == user_ref]
            out = sorted(out, key=lambda x: x.started_at, reverse=True)
            return [replace(l) for l in out[:max(1, min(limit, 500))]]

    def last_success_for(self, user_ref: str, automation_id: str) -> Optional[ChallengeLog]:
        with self._lock:
            matches = [l for l in self._by_id.values()
                       if l.user_ref == user_ref
                       and l.automation_id == automation_id
                       and l.result == ChallengeResult.SUCCESS]
            if not matches:
                return None
            return replace(sorted(matches, key=lambda x: x.started_at, reverse=True)[0])

    def count_fails_since(self, user_ref: str, automation_id: str, since: datetime) -> int:
        with self._lock:
            return sum(
                1
                for l in self._by_id.values()
                if l.user_ref == user_ref
                and l.automation_id == automation_id
                and l.result == ChallengeResult.FAIL
                and l.started_at >= since
            )


class InMemoryPhoneMappingRepository(IPhoneMappingRepository):
    def __init__(self):
        self._by_id: Dict[str, PhoneMapping] = {}
        self._lock = RLock()

    def add(self, p: PhoneMapping) -> PhoneMapping:
        with self._lock:
            for existing in self._by_id.values():
                if existing.phone_e164 == p.phone_e164 and existing.is_active:
                    raise ValueError(f"phone {p.phone_e164} already mapped")
            self._by_id[p.id] = replace(p)
            return replace(self._by_id[p.id])

    def get_by_phone(self, phone_e164: str) -> Optional[PhoneMapping]:
        with self._lock:
            for p in self._by_id.values():
                if p.phone_e164 == phone_e164 and p.is_active:
                    return replace(p)
            return None

    def list_for_user(self, user_ref: str) -> List[PhoneMapping]:
        with self._lock:
            out = [p for p in self._by_id.values() if p.user_ref == user_ref]
            return [replace(p) for p in sorted(out, key=lambda x: x.created_at, reverse=True)]

    def update(self, p: PhoneMapping) -> PhoneMapping:
        with self._lock:
            if p.id not in self._by_id:
                raise KeyError(p.id)
            p.updated_at = datetime.utcnow()
            self._by_id[p.id] = replace(p)
            return replace(self._by_id[p.id])

    def delete(self, mapping_id: str) -> bool:
        with self._lock:
            return self._by_id.pop(mapping_id, None) is not None
