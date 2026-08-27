"""
Home Assistant direct dispatcher.

Single dispatch point for all homes and all scenes. Called from any ingress
(VAPI, Alexa, FPH, future web/mobile) with a (home_id, scene_name) pair.

Resolves:
  - home_id -> (ha_url, ha_token)                 from HOME_CONFIGS_JSON
  - scene_name -> (service, entity_id)            from SCENE_CATALOG_JSON
  - per-home overrides                            from HOME_SCENE_OVERRIDES_JSON

Calls HA's REST API directly; no HA-side webhooks required.

Config format (env vars, JSON strings):

  HOME_CONFIGS_JSON='{
    "scott_home": { "ha_url": "https://x.y/", "ha_token": "eyJ..." }
  }'

  SCENE_CATALOG_JSON='{
    "decorations on": { "service": "script", "entity": "decorations_on" },
    "night scene":    { "service": "scene",  "entity": "night_mode"     }
  }'

  HOME_SCENE_OVERRIDES_JSON='{
    "scott_home": {
      "decorations on": { "service": "script", "entity": "christmas_lights" }
    }
  }'
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import requests


logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    success: bool
    message: str
    status_code: Optional[int] = None
    latency_ms: Optional[int] = None


@dataclass
class SceneTarget:
    service: str   # e.g. "scene", "script", "light", "switch"
    entity: str    # the HA entity name suffix, e.g. "night_mode"

    @property
    def entity_id(self) -> str:
        return f"{self.service}.{self.entity}"


@dataclass
class HomeConfig:
    home_id: str
    ha_url: str
    ha_token: str


class HADirectDispatcher:
    """
    Dispatches scene activations straight to each home's HA REST API.

    Thread-safe for read paths (all config is loaded at __init__ and not
    mutated afterwards). Replace the instance to reload config.
    """

    def __init__(
        self,
        home_configs: Dict[str, HomeConfig],
        scene_catalog: Dict[str, SceneTarget],
        home_overrides: Optional[Dict[str, Dict[str, SceneTarget]]] = None,
        request_timeout_seconds: float = 8.0,
    ):
        self._homes = home_configs
        self._scenes = scene_catalog
        self._overrides = home_overrides or {}
        self._timeout = request_timeout_seconds
        # Optional DB-backed credential resolver: home_id -> (ha_url, token)
        # or None. Consulted BEFORE the env-config map so portal-managed
        # tokens win; env JSON remains the legacy fallback. Results are
        # cached briefly so the hot dispatch path stays cheap.
        self._resolver = None
        self._resolver_cache = {}  # home_id -> (expires_monotonic, HomeConfig|None)
        self._resolver_ttl_hit = 60.0
        self._resolver_ttl_miss = 10.0

    @classmethod
    def from_env(cls, request_timeout_seconds: float = 8.0) -> "HADirectDispatcher":
        homes = _parse_home_configs(os.environ.get("HOME_CONFIGS_JSON", "{}"))
        scenes = _parse_scene_catalog(os.environ.get("SCENE_CATALOG_JSON", "{}"))
        overrides = _parse_home_overrides(os.environ.get("HOME_SCENE_OVERRIDES_JSON", "{}"))
        logger.info(
            f"HADirectDispatcher loaded: homes={list(homes.keys())} "
            f"scenes={list(scenes.keys())} overrides_for={list(overrides.keys())}"
        )
        return cls(homes, scenes, overrides, request_timeout_seconds)

    def set_credentials_resolver(self, resolver) -> None:
        """Install a DB-backed credential resolver.

        `resolver(home_id)` returns (ha_url, ha_token) or None. Portal-stored
        tokens then take precedence over HOME_CONFIGS_JSON; homes only present
        in the env JSON keep working unchanged (legacy fallback).
        """
        self._resolver = resolver
        self._resolver_cache = {}

    def invalidate_home(self, home_id: str) -> None:
        """Drop one home's cached credentials (call after a token update)."""
        self._resolver_cache.pop(home_id, None)

    def _resolve_home(self, home_id: str) -> Optional[HomeConfig]:
        """DB-stored credentials first (cached), env config as fallback."""
        if not home_id:
            return None
        if self._resolver is not None:
            cached = self._resolver_cache.get(home_id)
            if cached is not None and cached[0] > time.monotonic():
                if cached[1] is not None:
                    return cached[1]
            else:
                cfg = None
                try:
                    creds = self._resolver(home_id)
                except Exception as e:  # never let DB trouble break dispatch
                    logger.error(f"credential resolver failed for {home_id}: {e}")
                    creds = None
                if creds:
                    cfg = HomeConfig(home_id=home_id, ha_url=creds[0], ha_token=creds[1])
                ttl = self._resolver_ttl_hit if cfg else self._resolver_ttl_miss
                self._resolver_cache[home_id] = (time.monotonic() + ttl, cfg)
                if cfg is not None:
                    return cfg
        return self._homes.get(home_id)

    def has_home(self, home_id: str) -> bool:
        """Return True if the orchestrator can dispatch to this home — i.e.
        it has credentials from either the portal-managed DB token or the
        legacy HOME_CONFIGS_JSON env var.

        Authoritative for "is this a home the orchestrator can dispatch to?".
        Other services (favorites, voice-enable provisioning) should use this
        rather than checking the `homes` Postgres table directly.
        """
        return self._resolve_home(home_id) is not None

    def resolve_scene(self, home_id: str, scene_name: str) -> Optional[SceneTarget]:
        key = _normalize(scene_name)
        override = self._overrides.get(home_id, {}).get(key)
        if override:
            return override
        return self._scenes.get(key)

    # Per-domain default HA service action.
    # Used when the caller doesn't supply an explicit `action`.
    #   - `automation` must be `trigger` (turn_on only ENABLES the automation)
    #   - `lock` defaults to `unlock` (the canonical "let me in" use case);
    #     the favorites-lock flow always voice-gates this
    #   - everything else uses `turn_on` (scenes, scripts, lights, switches, ...)
    DEFAULT_ACTIONS: Dict[str, str] = {
        "automation": "trigger",
        "lock": "unlock",
    }

    def dispatch_direct(
        self,
        home_id: str,
        service: str,
        entity: str,
        action: Optional[str] = None,
    ) -> DispatchResult:
        """Fire a known (service, entity) pair for a home. Used by the voice-auth
        enrollment flow where the target is already resolved from the DB, so we
        bypass the scene-catalog lookup.

        `action` defaults to the domain-appropriate value (see DEFAULT_ACTIONS):
          - automation -> trigger
          - lock       -> unlock
          - everything -> turn_on
        Pass an explicit action to override (e.g. action="lock" to lock instead
        of unlock, or action="turn_off").
        """
        home = self._resolve_home(home_id)
        if not home:
            msg = f"Unknown home_id: {home_id}"
            logger.warning(f"DISPATCH reject {msg}")
            return DispatchResult(False, msg)
        target = SceneTarget(service=service, entity=entity)
        resolved_action = action or self.DEFAULT_ACTIONS.get(service, "turn_on")
        return self._do_post(home, target, source_label=f"{service}.{entity}", action=resolved_action)

    def dispatch(self, home_id: str, scene_name: str) -> DispatchResult:
        home = self._resolve_home(home_id)
        if not home:
            msg = f"Unknown home_id: {home_id}"
            logger.warning(f"DISPATCH reject {msg}")
            return DispatchResult(False, msg)

        target = self.resolve_scene(home_id, scene_name)
        if not target:
            msg = f"Unknown scene '{scene_name}' for home {home_id}"
            logger.warning(f"DISPATCH reject {msg}")
            return DispatchResult(False, msg)

        return self._do_post(home, target, source_label=scene_name, action="turn_on")

    def _do_post(
        self,
        home: "HomeConfig",
        target: "SceneTarget",
        source_label: str,
        action: str = "turn_on",
    ) -> DispatchResult:
        url = f"{home.ha_url.rstrip('/')}/api/services/{target.service}/{action}"
        headers = {
            "Authorization": f"Bearer {home.ha_token}",
            "Content-Type": "application/json",
        }
        payload = {"entity_id": target.entity_id}

        t0 = time.monotonic()
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self._timeout)
        except requests.exceptions.Timeout:
            logger.error(f"DISPATCH timeout home={home.home_id} target={source_label} url={url}")
            return DispatchResult(False, "Home Assistant timed out.")
        except requests.exceptions.ConnectionError:
            logger.error(f"DISPATCH unreachable home={home.home_id} target={source_label} url={url}")
            return DispatchResult(False, "Home Assistant unreachable.")
        except Exception as e:
            logger.error(f"DISPATCH error home={home.home_id} target={source_label}: {e}", exc_info=True)
            return DispatchResult(False, f"Dispatch error: {e}")

        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            f"DISPATCH home={home.home_id} target=\"{source_label}\" entity={target.entity_id} "
            f"status={resp.status_code} took={latency_ms}ms"
        )

        if 200 <= resp.status_code < 300:
            return DispatchResult(True, "ok", resp.status_code, latency_ms)

        body_snippet = (resp.text or "")[:200].replace("\n", " ")
        return DispatchResult(
            False,
            f"HA returned {resp.status_code}: {body_snippet}",
            resp.status_code,
            latency_ms,
        )


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _parse_home_configs(raw: str) -> Dict[str, HomeConfig]:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        logger.error(f"HOME_CONFIGS_JSON parse error: {e}")
        return {}

    result: Dict[str, HomeConfig] = {}
    for home_id, cfg in data.items():
        url = (cfg or {}).get("ha_url")
        token = (cfg or {}).get("ha_token")
        if not url or not token:
            logger.warning(f"HOME_CONFIGS_JSON skipping {home_id}: missing ha_url or ha_token")
            continue
        result[home_id] = HomeConfig(home_id=home_id, ha_url=url, ha_token=token)
    return result


def _parse_scene_catalog(raw: str) -> Dict[str, SceneTarget]:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        logger.error(f"SCENE_CATALOG_JSON parse error: {e}")
        return {}

    result: Dict[str, SceneTarget] = {}
    for scene_name, cfg in data.items():
        svc = (cfg or {}).get("service")
        ent = (cfg or {}).get("entity")
        if not svc or not ent:
            logger.warning(f"SCENE_CATALOG_JSON skipping '{scene_name}': missing service or entity")
            continue
        result[_normalize(scene_name)] = SceneTarget(service=svc, entity=ent)
    return result


def _parse_home_overrides(raw: str) -> Dict[str, Dict[str, SceneTarget]]:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        logger.error(f"HOME_SCENE_OVERRIDES_JSON parse error: {e}")
        return {}

    result: Dict[str, Dict[str, SceneTarget]] = {}
    for home_id, scenes in data.items():
        home_map: Dict[str, SceneTarget] = {}
        for scene_name, cfg in (scenes or {}).items():
            svc = (cfg or {}).get("service")
            ent = (cfg or {}).get("entity")
            if not svc or not ent:
                continue
            home_map[_normalize(scene_name)] = SceneTarget(service=svc, entity=ent)
        if home_map:
            result[home_id] = home_map
    return result
