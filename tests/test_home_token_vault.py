"""Tests for portal-managed encrypted HA tokens (vault, service, dispatcher)."""
import os

import pytest

from app.domain.models import Home
from app.infrastructure.home_assistant.direct_dispatcher import (
    HADirectDispatcher, HomeConfig)
from app.infrastructure.security.token_vault import TokenVault
from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository
from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository
from app.services.home_service import HomeService


def _svc():
    repo = InMemoryHomeRepository()
    svc = HomeService(repo, InMemoryUserRepository(), token_vault=TokenVault())
    repo.add(Home(home_id="h1", user_id="u1", name="H1",
                  ha_url="https://h1.example.com", ha_webhook_id="wh"))
    return svc, repo


class TestTokenVault:
    def test_roundtrip(self):
        v = TokenVault()
        c = v.encrypt("eyJsecret")
        assert c.startswith("fv1:") and "eyJsecret" not in c
        assert v.decrypt(c) == "eyJsecret"

    def test_empty_and_none(self):
        v = TokenVault()
        assert v.encrypt(None) is None
        assert v.encrypt("   ") is None
        assert v.decrypt(None) is None
        assert v.decrypt("garbage") is None

    def test_wrong_key_is_absent_not_crash(self):
        from cryptography.fernet import Fernet
        a = TokenVault(Fernet.generate_key().decode())
        b = TokenVault(Fernet.generate_key().decode())
        assert b.decrypt(a.encrypt("tok")) is None

    def test_hint(self):
        assert TokenVault.hint("eyJabcdef1234") == "…1234"
        assert TokenVault.hint("short") is None


class TestHomeServiceTokens:
    def test_set_get_clear(self):
        svc, _ = _svc()
        assert svc.set_ha_token("h1", "eyJtok")
        assert svc.get_ha_credentials("h1") == ("https://h1.example.com", "eyJtok")
        assert svc.token_status("h1") == {"has_token": True, "token_hint": None} or \
               svc.token_status("h1")["has_token"] is True
        svc.set_ha_token("h1", None)
        assert svc.get_ha_credentials("h1") is None

    def test_missing_home_raises(self):
        svc, _ = _svc()
        with pytest.raises(ValueError):
            svc.set_ha_token("ghost", "tok")

    def test_inactive_home_not_dispatchable(self):
        svc, repo = _svc()
        svc.set_ha_token("h1", "eyJtok")
        repo.deactivate("h1")
        assert svc.get_ha_credentials("h1") is None
        # but admin tests can still read it
        assert svc.get_stored_ha_token("h1") == "eyJtok"


class TestDispatcherResolver:
    def test_db_wins_over_env_and_falls_back(self):
        d = HADirectDispatcher(
            {"both": HomeConfig("both", "https://env", "envtok"),
             "envonly": HomeConfig("envonly", "https://env2", "envtok2")}, {})
        d.set_credentials_resolver(
            lambda h: ("https://db", "dbtok") if h in ("both", "dbonly") else None)
        assert d._resolve_home("both").ha_token == "dbtok"      # DB wins
        assert d._resolve_home("envonly").ha_token == "envtok2"  # fallback
        assert d._resolve_home("dbonly").ha_token == "dbtok"
        assert d._resolve_home("ghost") is None
        assert d.has_home("dbonly") and not d.has_home("ghost")

    def test_resolver_errors_fall_back_to_env(self):
        d = HADirectDispatcher({"h": HomeConfig("h", "https://env", "envtok")}, {})
        def boom(_):
            raise RuntimeError("db down")
        d.set_credentials_resolver(boom)
        assert d._resolve_home("h").ha_token == "envtok"

    def test_cache_and_invalidation(self):
        calls = []
        d = HADirectDispatcher({}, {})
        d.set_credentials_resolver(
            lambda h: (calls.append(h), ("https://db", "tok"))[1])
        d.has_home("x"); d.has_home("x")
        assert calls == ["x"]
        d.invalidate_home("x"); d.has_home("x")
        assert calls == ["x", "x"]
