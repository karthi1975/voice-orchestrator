"""Home Assistant device registry abstraction.

Wraps HA's REST API to enumerate physical devices (as opposed to entities).
HA's REST API doesn't expose the device registry directly, so we synthesize
it via the template API: render a JSON dict mapping every entity_id -> its
device_id, then group entities by device.

Caching is critical — the template-render call is O(N entities) and takes
~1-2s for a home with 400 entities. We cache per home_id with a 60s TTL.

Domain priority for selecting a device's "primary" entity (the one tapped
to control the device in a one-tile-per-device UI):

    light > lock > cover > climate > fan > media_player > switch > input_boolean

Rationale: when a device has multiple controllable entities, the higher-
priority domain is what the user typically wants (e.g. an Echo Dot has both
`media_player.*` and `switch.*do_not_disturb` — media_player is the
primary action, do-not-disturb is configuration).

`switch` ranks below `media_player` deliberately: a Sonos Move appears as
`media_player` + `switch.*_loudness/crossfade` — the player is what to fire.

Devices whose ONLY entities are sensors / diagnostics / updates (no domain
in the priority list) are flagged controllable=False — they can't be
favorited.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests

from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher

logger = logging.getLogger(__name__)


class HomeUnreachableError(RuntimeError):
    """Home Assistant for a home is unreachable or rejecting our credentials.

    Distinct from "device not found" so API callers see the truth: a 503
    (fix the home link) instead of a misleading 400 (fix your request).
    Subclasses RuntimeError so existing generic handlers still catch it.
    """


PRIMARY_DOMAIN_PRIORITY: List[str] = [
    "light",
    "lock",
    "cover",
    "climate",
    "fan",
    "media_player",
    "switch",
    "input_boolean",
]
PRIMARY_DOMAINS = set(PRIMARY_DOMAIN_PRIORITY)


@dataclass
class HADevice:
    device_id: str
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    area: Optional[str] = None
    all_entities: List[str] = field(default_factory=list)
    primary_entity_id: Optional[str] = None
    primary_domain: Optional[str] = None

    @property
    def is_controllable(self) -> bool:
        return self.primary_entity_id is not None


class HADeviceRegistry:
    """Per-home cache of HA devices, derived from the template API."""

    def __init__(
        self,
        dispatcher: HADirectDispatcher,
        cache_ttl_seconds: int = 60,
        request_timeout_seconds: float = 30.0,
    ):
        self._dispatcher = dispatcher
        self._ttl = cache_ttl_seconds
        self._timeout = request_timeout_seconds
        self._cache: Dict[str, Tuple[float, List[HADevice]]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------

    def list_devices(self, home_id: str, force_refresh: bool = False) -> List[HADevice]:
        """Return all devices for a home. Cached for `cache_ttl_seconds`."""
        with self._lock:
            cached = self._cache.get(home_id)
            now = time.monotonic()
            if not force_refresh and cached and (now - cached[0]) < self._ttl:
                return cached[1]

        # Fetch outside the lock to avoid blocking concurrent reads
        try:
            devices = self._fetch_devices(home_id)
        except HomeUnreachableError:
            # Serve a stale cache through brief HA outages; with nothing
            # cached, surface the outage instead of pretending "no devices".
            if cached:
                logger.warning(
                    f"HADeviceRegistry: HA unreachable for home={home_id}; "
                    f"serving stale cache ({len(cached[1])} devices)"
                )
                return cached[1]
            raise
        with self._lock:
            self._cache[home_id] = (time.monotonic(), devices)
        return devices

    def get_device(self, home_id: str, device_id: str) -> Optional[HADevice]:
        for d in self.list_devices(home_id):
            if d.device_id == device_id:
                return d
        # Bust cache and try once more — registry may have changed
        for d in self.list_devices(home_id, force_refresh=True):
            if d.device_id == device_id:
                return d
        return None

    def device_id_for_entity(self, home_id: str, entity_id: str) -> Optional[str]:
        # Best-effort enrichment: entity favorites must keep working while
        # HA is down, so an outage degrades to "no device attached".
        try:
            devices = self.list_devices(home_id)
        except HomeUnreachableError:
            return None
        for d in devices:
            if entity_id in d.all_entities:
                return d.device_id
        return None

    # ------------------------------------------------------------------

    def _fetch_devices(self, home_id: str) -> List[HADevice]:
        cfg = self._dispatcher._homes.get(home_id)
        if not cfg:
            logger.warning(f"HADeviceRegistry: no HA config for home_id={home_id}")
            return []

        ha_url = cfg.ha_url.rstrip("/")
        headers = {"Authorization": f"Bearer {cfg.ha_token}"}

        # 1. Pull every entity. We need state for filtering and for the search response.
        try:
            r = requests.get(ha_url + "/api/states", headers=headers, timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            logger.error(f"HADeviceRegistry: /api/states failed home={home_id}: {e}")
            raise HomeUnreachableError(
                f"Home Assistant for home '{home_id}' is unreachable"
            ) from e
        if r.status_code != 200:
            logger.error(f"HADeviceRegistry: /api/states returned {r.status_code} home={home_id}")
            if r.status_code in (401, 403):
                raise HomeUnreachableError(
                    f"Home Assistant for home '{home_id}' is rejecting the "
                    f"orchestrator's access token (HTTP {r.status_code}) — "
                    f"the home's token needs to be renewed"
                )
            raise HomeUnreachableError(
                f"Home Assistant for home '{home_id}' returned HTTP {r.status_code}"
            )
        states = r.json()
        entity_ids = [s["entity_id"] for s in states]

        # 2. Map entity_id -> device_id via template API. One call, all entities.
        if not entity_ids:
            return []
        parts = ['"' + e + '": (device_id("' + e + '") or "")' for e in entity_ids]
        tmpl = "{{ {" + ", ".join(parts) + "} | tojson }}"
        try:
            r2 = requests.post(
                ha_url + "/api/template",
                json={"template": tmpl},
                headers=headers,
                timeout=self._timeout,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"HADeviceRegistry: template (entity->device) failed home={home_id}: {e}")
            raise HomeUnreachableError(
                f"Home Assistant for home '{home_id}' is unreachable"
            ) from e
        if r2.status_code != 200:
            logger.error(f"HADeviceRegistry: template returned {r2.status_code} home={home_id}")
            raise HomeUnreachableError(
                f"Home Assistant for home '{home_id}' returned HTTP {r2.status_code}"
            )
        ent_to_dev = json.loads(r2.text)

        # 3. Group entities by device_id; skip orphan entities (no device).
        groups: Dict[str, List[str]] = defaultdict(list)
        for ent, dev in ent_to_dev.items():
            if dev:
                groups[dev].append(ent)

        if not groups:
            return []

        # 4. Pull device attributes (name / manufacturer / model / area) for each device.
        dev_ids = list(groups.keys())
        parts2 = []
        for d in dev_ids:
            parts2.append(
                '"' + d + '": ['
                'device_attr("' + d + '","name_by_user") or device_attr("' + d + '","name"),'
                'device_attr("' + d + '","manufacturer") or "",'
                'device_attr("' + d + '","model") or "",'
                'area_name("' + d + '") or ""'
                ']'
            )
        tmpl2 = "{{ {" + ", ".join(parts2) + "} | tojson }}"
        try:
            r3 = requests.post(
                ha_url + "/api/template",
                json={"template": tmpl2},
                headers=headers,
                timeout=self._timeout,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"HADeviceRegistry: template (device attrs) failed home={home_id}: {e}")
            attrs_map: Dict[str, list] = {}
        else:
            try:
                attrs_map = json.loads(r3.text) if r3.status_code == 200 else {}
            except json.JSONDecodeError:
                attrs_map = {}

        # 5. Build HADevice records with primary entity resolution
        devices: List[HADevice] = []
        for dev_id, entities in groups.items():
            attrs = attrs_map.get(dev_id) or [None, "", "", ""]
            name = attrs[0] if attrs[0] else dev_id
            mfr = attrs[1] if len(attrs) > 1 and attrs[1] else None
            model = attrs[2] if len(attrs) > 2 and attrs[2] else None
            area = attrs[3] if len(attrs) > 3 and attrs[3] else None

            primary, primary_dom = self._pick_primary_entity(entities)

            devices.append(HADevice(
                device_id=dev_id,
                name=str(name),
                manufacturer=mfr,
                model=model,
                area=area,
                all_entities=sorted(entities),
                primary_entity_id=primary,
                primary_domain=primary_dom,
            ))

        # Stable sort by name for predictable client-side rendering
        devices.sort(key=lambda d: (d.name or "").lower())
        logger.info(
            f"HADeviceRegistry: refreshed home={home_id} devices={len(devices)} "
            f"controllable={sum(1 for d in devices if d.is_controllable)}"
        )
        return devices

    @staticmethod
    def _pick_primary_entity(entities: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """Return (primary_entity_id, primary_domain) per priority order."""
        by_domain: Dict[str, List[str]] = defaultdict(list)
        for e in entities:
            if "." in e:
                dom = e.split(".", 1)[0]
                by_domain[dom].append(e)

        for dom in PRIMARY_DOMAIN_PRIORITY:
            if dom in by_domain:
                # If multiple, prefer the shortest entity_id (typically the canonical one)
                candidates = sorted(by_domain[dom], key=lambda x: (len(x), x))
                return candidates[0], dom
        return None, None
