"""Request-scoped database sessions.

Why this exists: the app used to hand every repository ONE Session object
that lived for the whole process. SQLAlchemy begins a transaction on the
first query and keeps it open until commit()/rollback(), so that session sat
"idle in transaction" for days holding an ACCESS SHARE lock on every table it
had ever read. Any migration that ALTERs one of those tables (e.g. adding a
column to users) then blocks forever behind it.

Fix: repositories are given a `scoped_session` registry instead. It behaves
like a Session (get/execute/add/commit/...) but resolves to a *thread-local*
session, and `attach_db_session_cleanup()` removes that session at the end of
every request. Removing closes it, which rolls back any open read
transaction and returns the connection to the pool — no locks survive a
request.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def attach_db_session_cleanup(app: Any, *registries: Any) -> None:
    """Remove each scoped_session's thread-local session after every request.

    Safe to call with registries that are None (in-memory mode).
    """
    active = [r for r in registries if r is not None]
    if not active:
        return

    @app.teardown_appcontext
    def _release_db_sessions(exception=None):  # noqa: ANN001
        for registry in active:
            try:
                registry.remove()
            except Exception as e:  # never let cleanup break a response
                logger.warning(f"db session cleanup failed: {e}")

    logger.info(f"Request-scoped DB session cleanup attached ({len(active)} registries)")
