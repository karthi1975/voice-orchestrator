"""Repository interfaces for voice authentication."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from app.domain.voice_auth_enums import ChallengeResult, EnrollmentStatus
from app.domain.voice_auth_models import ChallengeLog, Enrollment, PhoneMapping


class IEnrollmentRepository(ABC):
    @abstractmethod
    def add(self, enrollment: Enrollment) -> Enrollment: ...

    @abstractmethod
    def get_by_id(self, enrollment_id: str) -> Optional[Enrollment]: ...

    @abstractmethod
    def get_by_user_and_automation(self, user_ref: str, automation_id: str) -> Optional[Enrollment]: ...

    @abstractmethod
    def list_for_user(self, user_ref: str,
                      status: Optional[EnrollmentStatus] = None) -> List[Enrollment]: ...

    @abstractmethod
    def list_for_home(self, home_id: str) -> List[Enrollment]: ...

    @abstractmethod
    def update(self, enrollment: Enrollment) -> Enrollment: ...

    @abstractmethod
    def delete(self, enrollment_id: str) -> bool: ...


class IChallengeLogRepository(ABC):
    @abstractmethod
    def add(self, log: ChallengeLog) -> ChallengeLog: ...

    @abstractmethod
    def get_by_id(self, log_id: str) -> Optional[ChallengeLog]: ...

    @abstractmethod
    def get_by_vapi_call_id(self, vapi_call_id: str) -> Optional[ChallengeLog]: ...

    @abstractmethod
    def update(self, log: ChallengeLog) -> ChallengeLog: ...

    @abstractmethod
    def list_for_user(self, user_ref: str, limit: int = 50) -> List[ChallengeLog]: ...

    @abstractmethod
    def last_success_for(self, user_ref: str, automation_id: str) -> Optional[ChallengeLog]: ...

    @abstractmethod
    def count_fails_since(self, user_ref: str, automation_id: str, since: datetime) -> int: ...


class IPhoneMappingRepository(ABC):
    @abstractmethod
    def add(self, mapping: PhoneMapping) -> PhoneMapping: ...

    @abstractmethod
    def get_by_phone(self, phone_e164: str) -> Optional[PhoneMapping]: ...

    @abstractmethod
    def list_for_user(self, user_ref: str) -> List[PhoneMapping]: ...

    @abstractmethod
    def update(self, mapping: PhoneMapping) -> PhoneMapping: ...

    @abstractmethod
    def delete(self, mapping_id: str) -> bool: ...
