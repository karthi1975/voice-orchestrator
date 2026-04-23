"""Unit tests for VoiceAuthService.

Covers:
  - Enrollment create (validation, idempotency, slug derivation)
  - Status transitions (PAUSED reversible, REVOKED terminal)
  - Cooldown enforcement
  - Max-attempts enforcement (rolling fail window)
  - Resolve outcome branches (no enrollment / locked / cooldown / allowed)
  - Phone mapping (normalization, uniqueness, lookup)
"""

from datetime import datetime, timedelta

import pytest

from app.domain.voice_auth_enums import (
    ChallengeResult,
    ChallengeType,
    EnrollmentStatus,
)
from app.repositories.implementations.in_memory_voice_auth_repo import (
    InMemoryChallengeLogRepository,
    InMemoryEnrollmentRepository,
    InMemoryPhoneMappingRepository,
)
from app.services.voice_auth_service import (
    VoiceAuthService,
    _normalize_phone,
    _slug,
)


# ---------- fixtures --------------------------------------------------------


@pytest.fixture
def service():
    return VoiceAuthService(
        enrollment_repo=InMemoryEnrollmentRepository(),
        log_repo=InMemoryChallengeLogRepository(),
        phone_repo=InMemoryPhoneMappingRepository(),
        fail_window_seconds=3600,
    )


def _create(service, **overrides):
    kwargs = dict(
        user_ref="u1",
        home_id="scott_home",
        automation_name="Decorations On",
        ha_service="scene",
        ha_entity="decorations_on",
        cooldown_seconds=30,
        max_attempts=3,
    )
    kwargs.update(overrides)
    return service.create_enrollment(**kwargs)


# ---------- slug / normalize ------------------------------------------------


class TestHelpers:
    @pytest.mark.parametrize("raw,expected", [
        ("Decorations On", "decorations_on"),
        ("  Night Scene  ", "night_scene"),
        ("main-lights-on", "main_lights_on"),
        ("ALLCAPS", "allcaps"),
        ("", ""),
    ])
    def test_slug(self, raw, expected):
        assert _slug(raw) == expected

    def test_normalize_phone_accepts_valid(self):
        assert _normalize_phone("+1 (555) 123-4567") == "+15551234567"
        assert _normalize_phone("5551234567") == "+5551234567"
        assert _normalize_phone("+447911123456") == "+447911123456"

    @pytest.mark.parametrize("bad", ["", None, "abc", "1", "+"])
    def test_normalize_phone_rejects_garbage(self, bad):
        with pytest.raises(ValueError):
            _normalize_phone(bad)


# ---------- create_enrollment validation + idempotency ---------------------


class TestCreateEnrollment:
    def test_happy_path(self, service):
        e = _create(service)
        assert e.id
        assert e.user_ref == "u1"
        assert e.automation_id == "decorations_on"
        assert e.status == EnrollmentStatus.ACTIVE
        assert e.ha_service == "scene" and e.ha_entity == "decorations_on"

    def test_idempotent_on_duplicate(self, service):
        a = _create(service)
        b = _create(service)
        assert a.id == b.id

    @pytest.mark.parametrize("field,value", [
        ("user_ref", ""),
        ("home_id", ""),
        ("automation_name", ""),
        ("ha_service", "fake_domain"),
        ("ha_entity", "has.a.dot"),
        ("ha_entity", ""),
    ])
    def test_validation_errors(self, service, field, value):
        with pytest.raises(ValueError):
            _create(service, **{field: value})

    @pytest.mark.parametrize("attempts", [0, -1, 11])
    def test_max_attempts_bounds(self, service, attempts):
        with pytest.raises(ValueError):
            _create(service, max_attempts=attempts)

    @pytest.mark.parametrize("cooldown", [-1, 86_401])
    def test_cooldown_bounds(self, service, cooldown):
        with pytest.raises(ValueError):
            _create(service, cooldown_seconds=cooldown)

    def test_explicit_automation_id_wins_over_name(self, service):
        e = _create(service, automation_name="Some Display", automation_id="my-stable-id")
        assert e.automation_id == "my_stable_id"


# ---------- status transitions ---------------------------------------------


class TestStatusTransitions:
    def test_pause_and_resume(self, service):
        e = _create(service)
        p = service.update_status(e.id, EnrollmentStatus.PAUSED)
        assert p.status == EnrollmentStatus.PAUSED
        r = service.update_status(e.id, EnrollmentStatus.ACTIVE)
        assert r.status == EnrollmentStatus.ACTIVE

    def test_revoke_is_terminal(self, service):
        e = _create(service)
        service.update_status(e.id, EnrollmentStatus.REVOKED)
        with pytest.raises(ValueError):
            service.update_status(e.id, EnrollmentStatus.ACTIVE)

    def test_update_nonexistent(self, service):
        assert service.update_status("nope", EnrollmentStatus.PAUSED) is None


# ---------- resolve_for_challenge ------------------------------------------


class TestResolve:
    def test_no_enrollment(self, service):
        out = service.resolve_for_challenge(user_ref="ghost", automation_id="x")
        assert out.denied()
        assert out.denial_reason == ChallengeResult.DENIED_NO_ENROLLMENT

    def test_missing_fields(self, service):
        out = service.resolve_for_challenge(user_ref="", automation_id="")
        assert out.denied()

    def test_paused_locks(self, service):
        e = _create(service)
        service.update_status(e.id, EnrollmentStatus.PAUSED)
        out = service.resolve_for_challenge(user_ref="u1", automation_id="decorations_on")
        assert out.denied()
        assert out.denial_reason == ChallengeResult.DENIED_LOCKED

    def test_happy_path_passes(self, service):
        _create(service)
        out = service.resolve_for_challenge(user_ref="u1", automation_id="decorations on")
        assert out.enrollment is not None
        assert not out.denied()

    def test_cooldown_after_success(self, service, monkeypatch):
        _create(service, cooldown_seconds=60)
        svc = service
        # Open + close a successful log — simulates a prior challenge completion
        l = svc.open_log(
            enrollment=svc._enrollments.get_by_user_and_automation("u1", "decorations_on"),
            user_ref="u1", automation_id="decorations_on",
            vapi_call_id="prior", initiated_by="TEST",
        )
        svc.close_log(l.id, result=ChallengeResult.SUCCESS)

        out = svc.resolve_for_challenge(user_ref="u1", automation_id="decorations_on")
        assert out.denied()
        assert out.denial_reason == ChallengeResult.DENIED_COOLDOWN
        assert 0 < out.cooldown_remaining_seconds <= 60

    def test_cooldown_zero_always_allows(self, service):
        _create(service, cooldown_seconds=0)
        e = service._enrollments.get_by_user_and_automation("u1", "decorations_on")
        l = service.open_log(enrollment=e, user_ref="u1", automation_id="decorations_on",
                             vapi_call_id="c", initiated_by="TEST")
        service.close_log(l.id, result=ChallengeResult.SUCCESS)
        out = service.resolve_for_challenge(user_ref="u1", automation_id="decorations_on")
        assert not out.denied()

    def test_max_attempts_exhausted(self, service):
        _create(service, max_attempts=2, cooldown_seconds=0)
        e = service._enrollments.get_by_user_and_automation("u1", "decorations_on")
        # record 2 fails inside the rolling fail window
        for _ in range(2):
            l = service.open_log(enrollment=e, user_ref="u1", automation_id="decorations_on",
                                 vapi_call_id="x", initiated_by="TEST")
            service.close_log(l.id, result=ChallengeResult.FAIL, failure_reason="mismatch")
        out = service.resolve_for_challenge(user_ref="u1", automation_id="decorations_on")
        assert out.denied()
        assert out.denial_reason == ChallengeResult.DENIED_LOCKED

    def test_fails_outside_window_dont_count(self, service):
        _create(service, max_attempts=2, cooldown_seconds=0)
        svc = VoiceAuthService(
            enrollment_repo=service._enrollments,
            log_repo=service._logs,
            phone_repo=service._phones,
            fail_window_seconds=1,  # 1 second window
        )
        e = svc._enrollments.get_by_user_and_automation("u1", "decorations_on")
        # insert two fails dated well in the past
        old_log = service.open_log(enrollment=e, user_ref="u1", automation_id="decorations_on",
                                   vapi_call_id="old1", initiated_by="TEST")
        l = service._logs.get_by_id(old_log.id)
        l.started_at = datetime.utcnow() - timedelta(hours=1)
        l.result = ChallengeResult.FAIL
        l.completed_at = l.started_at
        service._logs.update(l)

        out = svc.resolve_for_challenge(user_ref="u1", automation_id="decorations_on")
        assert not out.denied(), "ancient fails shouldn't count"


# ---------- check endpoint shape -------------------------------------------


class TestCheck:
    def test_exists_false(self, service):
        r = service.check("ghost", "foo")
        assert r.exists is False and r.enrollment_required is True

    def test_exists_true(self, service):
        _create(service)
        r = service.check("u1", "decorations_on")
        assert r.exists is True
        assert r.enrollment is not None
        assert r.attempts_remaining == 3


# ---------- phone mapping ---------------------------------------------------


class TestPhoneMapping:
    def test_create_and_lookup(self, service):
        p = service.map_phone(phone="+1 (555) 123-4567",
                              user_ref="u1", home_id="scott_home")
        assert p.phone_e164 == "+15551234567"
        # Lookup must use the same E.164-ish form (clients should always pass country code).
        found = service.lookup_phone("+15551234567")
        assert found and found.user_ref == "u1"
        found2 = service.lookup_phone("+1 (555) 123-4567")  # formatting tolerated
        assert found2 and found2.user_ref == "u1"

    def test_duplicate_same_user_idempotent(self, service):
        a = service.map_phone(phone="+15551234567", user_ref="u1", home_id="scott_home")
        b = service.map_phone(phone="+15551234567", user_ref="u1", home_id="scott_home")
        assert a.id == b.id

    def test_duplicate_different_user_rejected(self, service):
        service.map_phone(phone="+15551234567", user_ref="u1", home_id="scott_home")
        with pytest.raises(ValueError):
            service.map_phone(phone="+15551234567", user_ref="u2", home_id="scott_home")

    def test_lookup_invalid_returns_none(self, service):
        assert service.lookup_phone("garbage") is None
        assert service.lookup_phone("+15559999999") is None
