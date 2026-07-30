"""Per-entity tile metadata: name, icon, device class, category, state.

Joins the three HA sources a dashboard tile needs and hands back one flat
record per entity:

    entity registry (WebSocket)  platform, translation_key, entity_category,
                                 hidden_by — the bits REST omits
    icon translations (WebSocket) icons.json defaults, keyed by translation_key
    /api/states (REST)           friendly_name, live state, device_class, unit

Icon resolution itself lives in app/domain/entity_icons.py, which is pure and
unit-tested; this class only does the fetching and the join.

Cache split matters here: the registry and icon translations change only when
someone edits HA's configuration (10 min TTL, inside HADashboardClient), while
states go stale in seconds (10 s TTL, inside HADeviceRegistry). Reading them
through those two caches keeps a board refresh down to one small REST call in
the common case.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional

from app.domain.entity_icons import is_controllable, resolve_icon

logger = logging.getLogger(__name__)


class HAEntityMetadata:
    """Builds tile metadata for a home's entities."""

    def __init__(self, dashboard_client, device_registry):
        """
        dashboard_client: HADashboardClient — entity registry + icon translations.
        device_registry:  HADeviceRegistry  — /api/states.
        """
        self._dashboards = dashboard_client
        self._registry = device_registry

    def get(
        self, home_id: str, entity_ids: Optional[Iterable[str]] = None
    ) -> Dict[str, dict]:
        """Return {entity_id: metadata} for `entity_ids` (default: the whole home).

        Raises HomeUnreachableError if HA cannot be reached and nothing is
        cached. Callers on a rendering path should catch that and degrade to
        no metadata rather than failing the whole screen — a board with plain
        icons beats no board.
        """
        registry, icon_resources = self._dashboards.get_entity_registry_and_icons(home_id)
        states_by_id = {
            s.get("entity_id"): s
            for s in self._registry.get_states(home_id)
            if s.get("entity_id")
        }

        if entity_ids is None:
            wanted = list(dict.fromkeys(list(states_by_id) + list(registry)))
        else:
            wanted = list(dict.fromkeys(entity_ids))

        out: Dict[str, dict] = {}
        for entity_id in wanted:
            if "." not in entity_id:
                continue
            state_row = states_by_id.get(entity_id) or {}
            attributes = state_row.get("attributes") or {}
            state = state_row.get("state")
            entry = registry.get(entity_id) or {}

            icon, icon_source = resolve_icon(
                entity_id,
                state_attributes=attributes,
                state=state,
                registry_entry=entry,
                icon_resources=icon_resources,
            )
            out[entity_id] = {
                "name": attributes.get("friendly_name") or entity_id.split(".", 1)[1],
                "domain": entity_id.split(".", 1)[0],
                "icon": icon,
                "icon_source": icon_source,
                "device_class": (
                    attributes.get("device_class")
                    or entry.get("device_class")
                    or entry.get("original_device_class")
                ),
                "unit_of_measurement": attributes.get("unit_of_measurement"),
                # null = a primary entity, i.e. one HA shows on a dashboard.
                # "config"/"diagnostic" live behind the device page in HA.
                "entity_category": entry.get("entity_category"),
                "hidden": bool(entry.get("hidden_by")),
                "state": state,
                "controllable": is_controllable(entity_id),
            }
        return out
