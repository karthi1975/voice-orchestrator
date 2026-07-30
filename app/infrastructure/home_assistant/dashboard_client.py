"""Home Assistant frontend client (dashboards, entity registry, icons).

Pulls what the HA frontend uses to render a dashboard, over the WebSocket API
— the only surface HA exposes any of it on (there are no REST equivalents):

    {"type": "lovelace/dashboards/list"}                 -> extra dashboards
    {"type": "lovelace/config", "url_path": <or null>}   -> one dashboard's config
    {"type": "config/entity_registry/list"}              -> per-entity platform,
                                                            translation_key,
                                                            entity_category, …
    {"type": "frontend/get_icons", "category": "entity"} -> icons.json icon
                                                            translations

The last two exist because REST `/api/states` cannot icon a tile on its own:
since HA 2024.2 integrations declare icons in an `icons.json` translation file
keyed by the entity's `translation_key`, and REST omits both the key and the
translations. See app/domain/entity_icons.py for the resolution chain built on
top of these.

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


# Registry rows are fat (~700 bytes each; a 700-entity home ships ~480 KB of
# JSON, most of it `options` and `categories` we never read). We keep only the
# fields the icon/tile layer needs before caching.
_REGISTRY_FIELDS = (
    "entity_id",
    "platform",
    "translation_key",
    "icon",
    "original_icon",
    "device_class",
    "original_device_class",
    "entity_category",
    "hidden_by",
    "disabled_by",
    "device_id",
    "area_id",
)


class HADashboardClient:
    """Per-home cache of HA dashboards, fetched over the WebSocket API."""

    def __init__(
        self,
        dispatcher: HADirectDispatcher,
        cache_ttl_seconds: int = 30,
        request_timeout_seconds: float = 10.0,
        static_cache_ttl_seconds: int = 600,
    ):
        self._dispatcher = dispatcher
        self._ttl = cache_ttl_seconds
        # The entity registry and icon translations only change when someone
        # edits HA's configuration, so they get a much longer TTL than the
        # dashboard configs they decorate.
        self._static_ttl = static_cache_ttl_seconds
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

    def get_entity_registry_and_icons(
        self, home_id: str, force_refresh: bool = False
    ) -> Tuple[Dict[str, dict], Dict[str, Any]]:
        """Return (registry_by_entity_id, icon_resources) for a home.

        Both come back over a single WebSocket connection — connecting and
        authenticating costs more than either command does, so batching them
        halves the round trips. Cached together under the static TTL.

        `icon_resources` is keyed by integration, as HA returns it:
        resources[platform][domain][translation_key] -> {default, state?}.
        Requesting every loaded integration at once (no `integration` filter)
        is one small payload (~30 KB) and avoids a call per platform.
        """
        return self._cached(
            ("registry_icons", home_id),
            force_refresh,
            lambda: self._fetch_registry_and_icons(home_id),
            ttl=self._static_ttl,
        )

    def _fetch_registry_and_icons(self, home_id: str) -> Tuple[Dict[str, dict], Dict[str, Any]]:
        registry_rows, icons = self._ws_commands(home_id, [
            {"type": "config/entity_registry/list"},
            {"type": "frontend/get_icons", "category": "entity"},
        ])
        registry: Dict[str, dict] = {}
        for row in registry_rows or []:
            entity_id = row.get("entity_id")
            if entity_id:
                registry[entity_id] = {k: row.get(k) for k in _REGISTRY_FIELDS}
        resources = (icons or {}).get("resources") or {}
        logger.info(
            f"HADashboardClient: registry+icons home={home_id} "
            f"entities={len(registry)} integrations={len(resources)}"
        )
        return registry, resources

    # ------------------------------------------------------------------

    def _cached(
        self,
        key: Tuple[str, ...],
        force_refresh: bool,
        fetch: Callable[[], Any],
        ttl: Optional[int] = None,
    ) -> Any:
        ttl = self._ttl if ttl is None else ttl
        with self._lock:
            cached = self._cache.get(key)
            now = time.monotonic()
            if not force_refresh and cached and (now - cached[0]) < ttl:
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
        return self._ws_commands(home_id, [payload])[0]

    def _ws_commands(self, home_id: str, payloads: List[Dict[str, Any]]) -> List[Any]:
        """Run several commands over ONE connection, returning their `result`s
        in the order given.

        HA's WebSocket API multiplexes on the `id` field, so all commands are
        sent up front and the replies matched as they arrive — connecting and
        authenticating dominates the cost of a small command, so this is much
        cheaper than one connection per command. Errors are raised in command
        order, so the first failure wins regardless of reply order.
        """
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

            frames: Dict[int, dict] = {}
            try:
                for offset, payload in enumerate(payloads):
                    ws.send(json.dumps(dict(payload, id=offset + 1)))
                while len(frames) < len(payloads):
                    frame = json.loads(ws.recv())
                    # HA interleaves event frames from other subscriptions;
                    # only `result` frames for our ids count.
                    if frame.get("type") == "result" and frame.get("id") in range(1, len(payloads) + 1):
                        frames[frame["id"]] = frame
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

        return [self._unwrap(frames[i + 1]) for i in range(len(payloads))]

    @staticmethod
    def _unwrap(frame: dict) -> Any:
        """Return a result frame's payload, or raise the mapped HA error."""
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
