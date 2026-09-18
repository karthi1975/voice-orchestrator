"""
Request-scoped DB sessions: no transaction survives a request.

Regression for the production incident where a process-lifetime Session sat
"idle in transaction" for 21 hours and blocked migration 012's ALTER TABLE.
"""

import os
import tempfile

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.domain.models import User
from app.infrastructure.db_session import attach_db_session_cleanup
from app.repositories.implementations.sqlalchemy_models import Base
from app.repositories.implementations.sqlalchemy_user_repo import SQLAlchemyUserRepository


def _app_with_repo():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    registry = scoped_session(sessionmaker(bind=engine))
    repo = SQLAlchemyUserRepository(registry)  # registry quacks like a Session
    app = Flask(__name__)

    @app.get("/count")
    def count():
        return {"n": len(repo.list_all())}

    @app.post("/add")
    def add():
        repo.add(User(user_id="u1", username="u1", full_name="U1"))
        return {"ok": True}

    return app, registry, repo


def test_read_leaves_no_open_transaction():
    app, registry, _ = _app_with_repo()
    attach_db_session_cleanup(app, registry)
    client = app.test_client()
    assert client.get("/count").get_json()["n"] == 0
    # After the request the thread-local session has been removed entirely,
    # so nothing is "idle in transaction".
    assert registry.registry.has() is False


def test_without_cleanup_transaction_stays_open():
    """Documents the bug the hook fixes: a bare session keeps a txn open."""
    app, registry, _ = _app_with_repo()
    client = app.test_client()
    client.get("/count")
    assert registry.registry.has() is True
    assert registry().in_transaction() is True  # the lock-holding state
    registry.remove()


def test_writes_are_committed_and_session_released():
    app, registry, repo = _app_with_repo()
    attach_db_session_cleanup(app, registry)
    client = app.test_client()
    assert client.post("/add").status_code == 200
    assert registry.registry.has() is False
    assert client.get("/count").get_json()["n"] == 1  # committed, visible to a fresh session
    assert registry.registry.has() is False


def test_none_registries_are_ignored():
    app = Flask(__name__)
    attach_db_session_cleanup(app, None, None)  # in-memory mode: no hook, no error
    assert not app.teardown_appcontext_funcs


def test_container_releases_scoped_session(monkeypatch):
    """DependencyContainer wires a scoped_session and can release it."""
    from cryptography.fernet import Fernet
    from app import DependencyContainer
    from app.config.settings import get_settings
    path = os.path.join(tempfile.mkdtemp(), "t.db")
    # Settings are a class whose attributes were read from the environment at
    # import time, so patch the class rather than the env.
    cfg = get_settings()
    monkeypatch.setattr(cfg, "USE_DATABASE", True)
    monkeypatch.setattr(cfg, "DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("HA_TOKEN_KEY", Fernet.generate_key().decode())
    container = DependencyContainer()
    assert container.db_session_registry is not None
    container.user_repository.list_all()
    assert container.db_session_registry.registry.has() is True
    container.release_db_session()
    assert container.db_session_registry.registry.has() is False
