"""Home Assistant dashboard (Lovelace) client.

Pulls dashboard definitions from a home's HA over the WebSocket API — the
only surface HA exposes them on (there is no REST endpoint):

    {"type": "lovelace/dashboards/list"}                 -> extra dashboards
    {"type": "lovelace/config", "url_path": <or null>}   -> one dashboard's config

Constraints worth knowing:

  - Dashboards are HOME-scoped in HA. We authenticate with the home's
    long-lived token, so every orchestrator user of a home sees the same
    dashboards. HA has no per-user dashboard API for third parties; the
    per-user list an app shows must come from our own favorites table.
  - The default "Overview" dashboard (url_path null) is NOT included in
    lovelace/dashboards/list; we synthesize an entry for it.
  - A dashboard nobody has "taken control" of has no stored config — the
    HA frontend generates it on the fly. lovelace/config then errors with
    code `config_not_found`, surfaced here as DashboardNotConfiguredError.
    The fix is one-time: edit and save the dashboard in the HA UI.
  - These are the frontend's internal WebSocket commands, not a documented
    public API. Behaviour is pinned by tests; expect breakage risk on HA
    upgrades.

Caching mirrors HADeviceRegistry: per-key TTL cache, stale entries served
through brief HA outages.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import websocket

from app.infrastructure.home_assistant.device_registry import HomeUnreachableError
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher

logger = logging.getLogger(__name__)


class DashboardError(RuntimeError):
    """HA answered the WebSocket command with an error result."""

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class DashboardNotFoundError(DashboardError):
    """No dashboard exists at the requested url_path."""


class DashboardNotConfiguredError(DashboardError):
    """Dashboard exists but is auto-generated — HA has no stored config."""


# entity_ids look like "light.man_land_lamp"
_ENTITY_ID_RE = re.compile(r"^[a-z0-9_]+\.[A-Za-z0-9_]+$")

# Card/view keys whose string value is an entity_id.
_ENTITY_KEYS = {"entity", "entity_id", "camera_image"}

# Card/view keys holding lists whose items are entity_ids or {entity: ...} dicts.
_ENTITY_LIST_KEYS = {"entities", "badges"}


def extract_entity_ids(node: Any) -> List[str]:
    """Collect every entity_id referenced anywhere in a Lovelace config
    fragment (view, card, or whole dashboard), deduped, in encounter order.

    Walks the structure generically so nested layouts (grid/stack cards,
    the sections view type, conditional cards) all work without knowing
    each card schema.
    """
    found: List[str] = []
    seen = set()

    def _add(value: Any) -> None:
        if isinstance(value, str) and _ENTITY_ID_RE.match(value) and value not in seen:
            seen.add(value)
            found.append(value)

    def _walk(n: Any) -> None:
        if isinstance(n, dict):
            for key, value in n.items():
                if key in _ENTITY_KEYS and isinstance(value, str):
                    _add(value)
                elif key in _ENTITY_LIST_KEYS and isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            _add(item)
                        else:
                            _walk(item)
                else:
                    _walk(value)
        elif isinstance(n, list):
            for item in n:
                _walk(item)

    _walk(node)
    return found


class HADashboardClient:
    """Per-home cache of HA dashboards, fetched over the WebSocket API."""

    def __init__(
        self,
        dispatcher: HADirectDispatcher,
        cache_ttl_seconds: int = 30,
        request_timeout_seconds: float = 10.0,
    ):
        self._dispatcher = dispatcher
        self._ttl = cache_ttl_seconds
        self._timeout = request_timeout_seconds
        self._cache: Dict[Tuple[str, ...], Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------

    def list_dashboards(self, home_id: str, force_refresh: bool = False) -> List[dict]:
        """All dashboards for a home, default 'Overview' first."""
        raw = self._cached(
            ("list", home_id),
            force_refresh,
            lambda: self._ws_command(home_id, {"type": "lovelace/dashboards/list"}),
        )
        items = [{
            "url_path": None,
            "title": "Overview",
            "icon": "mdi:view-dashboard",
            "mode": "storage",
            "show_in_sidebar": True,
            "require_admin": False,
            "is_default": True,
        }]
        for d in raw or []:
            items.append({
                "url_path": d.get("url_path"),
                "title": d.get("title"),
                "icon": d.get("icon"),
                "mode": d.get("mode"),
                "show_in_sidebar": d.get("show_in_sidebar", True),
                "require_admin": d.get("require_admin", False),
                "is_default": False,
            })
        return items

    def get_config(
        self, home_id: str, url_path: Optional[str] = None, force_refresh: bool = False
    ) -> dict:
        """One dashboard's stored config. url_path None = default Overview."""
        payload: Dict[str, Any] = {"type": "lovelace/config", "url_path": url_path}
        return self._cached(
            ("config", home_id, url_path or ""),
            force_refresh,
            lambda: self._ws_command(home_id, payload),
        )

    # ------------------------------------------------------------------

    def _cached(self, key: Tuple[str, ...], force_refresh: bool, fetch: Callable[[], Any]) -> Any:
        with self._lock:
            cached = self._cache.get(key)
            now = time.monotonic()
            if not force_refresh and cached and (now - cached[0]) < self._ttl:
                return cached[1]
        try:
            value = fetch()
        except HomeUnreachableError:
            # Serve a stale cache through brief HA outages; with nothing
            # cached, surface the outage.
            if cached:
                logger.warning(
                    f"HADashboardClient: HA unreachable for key={key}; serving stale cache"
                )
                return cached[1]
            raise
        with self._lock:
            self._cache[key] = (time.monotonic(), value)
        return value

    def _ws_command(self, home_id: str, payload: Dict[str, Any]) -> Any:
        """Open a WebSocket to the home's HA, authenticate, run one command,
        return its `result`. Raises HomeUnreachableError on transport/auth
        failure, Dashboard*Error on an HA-reported command error."""
        cfg = self._dispatcher._homes.get(home_id)
        if not cfg:
            raise HomeUnreachableError(f"no HA config for home '{home_id}'")

        ws_url = re.sub(r"^http", "ws", cfg.ha_url.rstrip("/")) + "/api/websocket"
        ws = None
        try:
            try:
                ws = websocket.create_connection(ws_url, timeout=self._timeout)
                json.loads(ws.recv())  # {"type": "auth_required"}
                ws.send(json.dumps({"type": "auth", "access_token": cfg.ha_token}))
                reply = json.loads(ws.recv())
            except (websocket.WebSocketException, OSError, ValueError) as e:
                logger.error(f"HADashboardClient: connect/auth failed home={home_id}: {e}")
                raise HomeUnreachableError(
                    f"Home Assistant for home '{home_id}' is unreachable"
                ) from e

            if reply.get("type") != "auth_ok":
                logger.error(f"HADashboardClient: auth rejected home={home_id}: {reply}")
                raise HomeUnreachableError(
                    f"Home Assistant for home '{home_id}' is rejecting the "
                    f"orchestrator's access token — the home's token needs to be renewed"
                )

            msg = dict(payload, id=1)
            try:
                ws.send(json.dumps(msg))
                while True:
                    frame = json.loads(ws.recv())
                    if frame.get("id") == 1 and frame.get("type") == "result":
                        break
            except (websocket.WebSocketException, OSError, ValueError) as e:
                logger.error(f"HADashboardClient: command failed home={home_id}: {e}")
                raise HomeUnreachableError(
                    f"Home Assistant for home '{home_id}' is unreachable"
                ) from e
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

        if frame.get("success"):
            return frame.get("result")

        error = frame.get("error") or {}
        code = error.get("code")
        message = error.get("message") or f"HA command failed (code={code})"
        if code == "config_not_found":
            raise DashboardNotConfiguredError(
                "dashboard has no stored config (it is auto-generated); "
                "open it in Home Assistant, enter edit mode and save once to take control",
                code=code,
            )
        if code == "not_found":
            raise DashboardNotFoundError(message, code=code)
        raise DashboardError(message, code=code)
