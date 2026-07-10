"""REST API for voice authentication automation.

Base path: /api/v1/voice-auth
Auth:      Bearer token (future: JWT with user_ref claim). Today: accepted as-is.

Endpoints:
  POST   /enrollments              create enrollment (app: "require voice auth for X")
  GET    /enrollments              list enrollments for a user_ref (query param)
  GET    /enrollments/{id}         fetch one
  DELETE /enrollments/{id}         revoke (soft — sets REVOKED then deletes row)
  PATCH  /enrollments/{id}/status  pause / resume
  GET    /check                    convenience: exists + cooldown + attempts

  GET    /challenges               recent challenge log for a user_ref
  GET    /challenges/{id}          single log row

  POST   /phone-mappings           bind a phone number to user_ref/home
  GET    /phone-mappings           list for user_ref
  DELETE /phone-mappings/{id}      remove
  GET    /phone-lookup             return metadata for a phone number (used by VAPI phone webhook)

  GET    /automations/discover     query a home's HA live and list candidates
  POST   /automations/trigger      fire (home_id, ha_service, ha_entity) directly;
                                   refuses if an active enrollment gates the automation

  POST   /scene-mappings           create scene -> webhook mapping (mobile-facing)
  GET    /scene-mappings           list mappings for a home_id
  GET    /scene-mappings/{id}      fetch one
  PATCH  /scene-mappings/{id}      update name / webhook_id / is_active
  DELETE /scene-mappings/{id}      remove

  POST   /favorites                pin a device or entity for a user in a home
                                   body: {device_id} OR {entity_id}; locks auto-enroll
  GET    /favorites                list favorites for (user_ref, home_id)
  DELETE /favorites/{id}           remove a pinned device/entity
  PATCH  /favorites/reorder        bulk-update positions (body: [{id, position}, ...])
  POST   /favorites/{id}/fire      activate a favorite; refuses 409 if voice-gated

  GET    /devices/discover         enumerate physical HA devices for a home
  GET    /items/search             unified search across devices/entities/scenes/scripts/automations

  POST   /voice-enable             provision a VAPI phone number for (user_ref, home_id)
  GET    /voice-enable             status check by user_ref query param
  DELETE /voice-enable             release VAPI number for ?user_ref=...

  POST   /vapi/call-start          webhook VAPI hits on inbound phone calls;
                                   returns assistantOverrides.variableValues
                                   pre-populated with user_ref + home_id
                                   (looked up from the caller number).

Error envelope: { "error": "...", "code": "OPTIONAL_CODE" }
"""

import json
import logging
from typing import Optional

from flask import g, jsonify, request

from app.controllers.base_controller import BaseController
from app.domain.models import FavoriteDevice, SceneWebhookMapping
from app.domain.voice_auth_enums import (
    ChallengeResult,
    ChallengeType,
    EnrollmentStatus,
)
from app.domain.voice_auth_models import Enrollment, PhoneMapping
from app.services.favorite_device_service import (
    ConflictingArgumentsError,
    FavoriteDeviceService,
    NoControllableEntityError,
)
from app.services.scene_webhook_mapping_service import SceneWebhookMappingService
from app.services.vapi_provisioning_service import VapiProvisioningService
from app.services.voice_auth_service import VoiceAuthService
from app.infrastructure.home_assistant.device_registry import (
    HADeviceRegistry,
    HomeUnreachableError,
)
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher
from app.infrastructure.vapi.vapi_client import VapiClientError

logger = logging.getLogger(__name__)


# ---- JSON helpers ----------------------------------------------------------

def enrollment_to_dict(e: Enrollment) -> dict:
    return {
        "id": e.id,
        "user_ref": e.user_ref,
        "home_id": e.home_id,
        "automation_id": e.automation_id,
        "automation_name": e.automation_name,
        "ha_service": e.ha_service,
        "ha_entity": e.ha_entity,
        "status": e.status.value,
        "challenge_type": e.challenge_type.value,
        "max_attempts": e.max_attempts,
        "cooldown_seconds": e.cooldown_seconds,
        "metadata": json.loads(e.metadata_json) if e.metadata_json else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
        "created_by": e.created_by,
    }


def favorite_to_dict(f: FavoriteDevice, *, voice_auth_required: bool = False) -> dict:
    return {
        "id": f.id,
        "user_ref": f.user_ref,
        "home_id": f.home_id,
        "entity_id": f.entity_id,
        "friendly_name": f.friendly_name,
        "domain": f.domain,
        "kind": f.kind,
        "device_id": f.device_id,
        "primary_entity_id": f.primary_entity_id,
        "position": f.position,
        "voice_auth_required": voice_auth_required,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def scene_mapping_to_dict(m: SceneWebhookMapping) -> dict:
    return {
        "id": m.id,
        "home_id": m.home_id,
        "scene_name": m.scene_name,
        "webhook_id": m.webhook_id,
        "is_active": m.is_active,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def phone_to_dict(p: PhoneMapping) -> dict:
    return {
        "id": p.id,
        "phone_e164": p.phone_e164,
        "user_ref": p.user_ref,
        "home_id": p.home_id,
        "vapi_phone_number_id": p.vapi_phone_number_id,
        "label": p.label,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ---- Controller ------------------------------------------------------------


class VoiceAuthController(BaseController):
    def __init__(
        self,
        *,
        service: VoiceAuthService,
        dispatcher: HADirectDispatcher,
        scene_mapping_service: Optional[SceneWebhookMappingService] = None,
        favorite_service: Optional[FavoriteDeviceService] = None,
        vapi_provisioning_service: Optional[VapiProvisioningService] = None,
        device_registry: Optional[HADeviceRegistry] = None,
        url_prefix: str = "/api/v1/voice-auth",
    ):
        super().__init__("voice_auth_api", url_prefix)
        self._svc = service
        self._dispatcher = dispatcher
        self._scenes = scene_mapping_service
        self._favorites = favorite_service
        self._vapi_prov = vapi_provisioning_service
        self._registry = device_registry
        self._register_routes()

    def _register_routes(self) -> None:
        bp = self.blueprint
        bp.add_url_rule("/enrollments", "create_enrollment", self.create_enrollment, methods=["POST"])
        bp.add_url_rule("/enrollments", "list_enrollments", self.list_enrollments, methods=["GET"])
        bp.add_url_rule("/enrollments/<enrollment_id>", "get_enrollment", self.get_enrollment, methods=["GET"])
        bp.add_url_rule("/enrollments/<enrollment_id>", "delete_enrollment", self.delete_enrollment, methods=["DELETE"])
        bp.add_url_rule("/enrollments/<enrollment_id>/status", "update_status", self.update_status, methods=["PATCH"])
        bp.add_url_rule("/check", "check", self.check, methods=["GET"])

        bp.add_url_rule("/challenges", "list_challenges", self.list_challenges, methods=["GET"])
        bp.add_url_rule("/challenges/<log_id>", "get_challenge", self.get_challenge, methods=["GET"])

        bp.add_url_rule("/phone-mappings", "create_phone_mapping", self.create_phone_mapping, methods=["POST"])
        bp.add_url_rule("/phone-mappings", "list_phone_mappings", self.list_phone_mappings, methods=["GET"])
        bp.add_url_rule("/phone-mappings/<mapping_id>", "delete_phone_mapping", self.delete_phone_mapping, methods=["DELETE"])
        bp.add_url_rule("/phone-lookup", "phone_lookup", self.phone_lookup, methods=["GET"])

        bp.add_url_rule("/automations/discover", "discover_automations", self.discover_automations, methods=["GET"])
        bp.add_url_rule("/automations/trigger", "trigger_automation", self.trigger_automation, methods=["POST"])

        bp.add_url_rule("/scene-mappings", "create_scene_mapping", self.create_scene_mapping, methods=["POST"])
        bp.add_url_rule("/scene-mappings", "list_scene_mappings", self.list_scene_mappings, methods=["GET"])
        bp.add_url_rule("/scene-mappings/<mapping_id>", "get_scene_mapping", self.get_scene_mapping, methods=["GET"])
        bp.add_url_rule("/scene-mappings/<mapping_id>", "update_scene_mapping", self.update_scene_mapping, methods=["PATCH"])
        bp.add_url_rule("/scene-mappings/<mapping_id>", "delete_scene_mapping", self.delete_scene_mapping, methods=["DELETE"])

        bp.add_url_rule("/favorites", "create_favorite", self.create_favorite, methods=["POST"])
        bp.add_url_rule("/favorites", "list_favorites", self.list_favorites, methods=["GET"])
        bp.add_url_rule("/favorites/reorder", "reorder_favorites", self.reorder_favorites, methods=["PATCH"])
        bp.add_url_rule("/favorites/<favorite_id>", "delete_favorite", self.delete_favorite, methods=["DELETE"])
        bp.add_url_rule("/favorites/<favorite_id>/fire", "fire_favorite", self.fire_favorite, methods=["POST"])

        bp.add_url_rule("/devices/discover", "discover_devices", self.discover_devices, methods=["GET"])
        bp.add_url_rule("/items/search", "search_items", self.search_items, methods=["GET"])

        bp.add_url_rule("/voice-enable", "voice_enable", self.voice_enable, methods=["POST"])
        bp.add_url_rule("/voice-enable", "voice_enable_status", self.voice_enable_status, methods=["GET"])
        bp.add_url_rule("/voice-enable", "voice_disable", self.voice_disable, methods=["DELETE"])

        # NOTE: /vapi/call-start lives on the /vapi blueprint (routes/vapi.py)
        # to reuse X-Vapi-Secret auth; it is NOT part of the mobile-API surface.

    # ------- Enrollment CRUD ------------------------------------------------

    def create_enrollment(self):
        body = request.get_json(silent=True) or {}
        try:
            e = self._svc.create_enrollment(
                user_ref=body.get("user_ref") or "",
                home_id=body.get("home_id") or "",
                automation_name=body.get("automation_name") or "",
                ha_service=body.get("ha_service") or "",
                ha_entity=body.get("ha_entity") or "",
                automation_id=body.get("automation_id"),
                challenge_type=ChallengeType(body.get("challenge_type", "VERIFICATION")),
                max_attempts=int(body.get("max_attempts", 3)),
                cooldown_seconds=int(body.get("cooldown_seconds", 30)),
                metadata_json=json.dumps(body["metadata"]) if body.get("metadata") is not None else None,
                created_by=body.get("created_by"),
            )
            return jsonify(enrollment_to_dict(e)), 201
        except ValueError as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400

    def list_enrollments(self):
        user_ref = request.args.get("user_ref", "").strip()
        status_raw = request.args.get("status")
        if not user_ref:
            return jsonify({"error": "user_ref query param is required", "code": "VALIDATION"}), 400
        status = None
        if status_raw:
            try:
                status = EnrollmentStatus(status_raw.upper())
            except ValueError:
                return jsonify({"error": f"invalid status: {status_raw}"}), 400
        items = self._svc.list_enrollments(user_ref, status)
        return jsonify({"items": [enrollment_to_dict(e) for e in items], "count": len(items)}), 200

    def get_enrollment(self, enrollment_id: str):
        e = self._svc.get_enrollment(enrollment_id)
        if not e:
            return jsonify({"error": "not found"}), 404
        return jsonify(enrollment_to_dict(e)), 200

    def delete_enrollment(self, enrollment_id: str):
        ok = self._svc.delete_enrollment(enrollment_id)
        if not ok:
            return jsonify({"error": "not found"}), 404
        return "", 204

    def update_status(self, enrollment_id: str):
        body = request.get_json(silent=True) or {}
        raw = body.get("status")
        if not raw:
            return jsonify({"error": "status required", "code": "VALIDATION"}), 400
        try:
            new_status = EnrollmentStatus(raw.upper())
        except ValueError:
            return jsonify({"error": f"invalid status: {raw}"}), 400
        try:
            e = self._svc.update_status(enrollment_id, new_status)
        except ValueError as ex:
            return jsonify({"error": str(ex), "code": "CONFLICT"}), 409
        if not e:
            return jsonify({"error": "not found"}), 404
        return jsonify(enrollment_to_dict(e)), 200

    # ------- check -----------------------------------------------------------

    def check(self):
        user_ref = request.args.get("user_ref", "").strip()
        automation_id = request.args.get("automation_id", "").strip()
        if not user_ref or not automation_id:
            return jsonify({
                "error": "user_ref and automation_id query params are required",
                "code": "VALIDATION",
            }), 400
        result = self._svc.check(user_ref, automation_id)
        if not result.exists:
            return jsonify({"exists": False, "enrollment_required": True}), 404
        e = result.enrollment
        return jsonify({
            "exists": True,
            "automation_id": e.automation_id,
            "enrollment_id": e.id,
            "status": e.status.value,
            "challenge_type": e.challenge_type.value,
            "enrollment_required": False,
            "cooldown_remaining_seconds": result.cooldown_remaining_seconds,
            "attempts_remaining": result.attempts_remaining,
        }), 200

    # ------- challenge log ---------------------------------------------------

    def list_challenges(self):
        user_ref = request.args.get("user_ref", "").strip()
        if not user_ref:
            return jsonify({"error": "user_ref query param is required", "code": "VALIDATION"}), 400
        limit = int(request.args.get("limit", 50))
        logs = self._svc.recent_logs(user_ref, limit=limit)
        return jsonify({
            "items": [
                {
                    "id": l.id,
                    "enrollment_id": l.enrollment_id,
                    "user_ref": l.user_ref,
                    "automation_id": l.automation_id,
                    "home_id": l.home_id,
                    "vapi_call_id": l.vapi_call_id,
                    "result": l.result.value,
                    "failure_reason": l.failure_reason,
                    "confidence_score": l.confidence_score,
                    "started_at": l.started_at.isoformat() if l.started_at else None,
                    "completed_at": l.completed_at.isoformat() if l.completed_at else None,
                }
                for l in logs
            ],
            "count": len(logs),
        }), 200

    def get_challenge(self, log_id: str):
        l = self._svc._logs.get_by_id(log_id)  # direct access; no domain method needed
        if not l:
            return jsonify({"error": "not found"}), 404
        return jsonify({
            "id": l.id,
            "enrollment_id": l.enrollment_id,
            "user_ref": l.user_ref,
            "automation_id": l.automation_id,
            "home_id": l.home_id,
            "vapi_call_id": l.vapi_call_id,
            "result": l.result.value,
            "failure_reason": l.failure_reason,
            "confidence_score": l.confidence_score,
            "started_at": l.started_at.isoformat() if l.started_at else None,
            "completed_at": l.completed_at.isoformat() if l.completed_at else None,
        }), 200

    # ------- phone mappings --------------------------------------------------

    def create_phone_mapping(self):
        body = request.get_json(silent=True) or {}
        try:
            p = self._svc.map_phone(
                phone=body.get("phone") or body.get("phone_e164") or "",
                user_ref=body.get("user_ref") or "",
                home_id=body.get("home_id") or "",
                vapi_phone_number_id=body.get("vapi_phone_number_id"),
                label=body.get("label"),
            )
            return jsonify(phone_to_dict(p)), 201
        except ValueError as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400

    def list_phone_mappings(self):
        user_ref = request.args.get("user_ref", "").strip()
        if not user_ref:
            return jsonify({"error": "user_ref query param is required", "code": "VALIDATION"}), 400
        items = self._svc.list_phones_for_user(user_ref)
        return jsonify({"items": [phone_to_dict(p) for p in items], "count": len(items)}), 200

    def delete_phone_mapping(self, mapping_id: str):
        ok = self._svc.delete_phone(mapping_id)
        if not ok:
            return jsonify({"error": "not found"}), 404
        return "", 204

    def phone_lookup(self):
        phone = request.args.get("phone", "").strip()
        if not phone:
            return jsonify({"error": "phone query param is required", "code": "VALIDATION"}), 400
        m = self._svc.lookup_phone(phone)
        if not m:
            return jsonify({"error": "not found"}), 404
        return jsonify(phone_to_dict(m)), 200

    # ------- discover HA items -----------------------------------------------

    def discover_automations(self):
        """Query a home's HA REST API and return voice-eligible candidates.

        Uses the bearer token already configured in HADirectDispatcher's
        HOME_CONFIGS_JSON — the caller doesn't supply credentials.
        """
        home_id = request.args.get("home_id", "").strip()
        if not home_id:
            return jsonify({"error": "home_id query param is required", "code": "VALIDATION"}), 400
        cfg = self._dispatcher._homes.get(home_id)
        if not cfg:
            return jsonify({"error": f"home {home_id} not configured", "code": "NOT_CONFIGURED"}), 404

        import requests
        try:
            resp = requests.get(
                f"{cfg.ha_url.rstrip('/')}/api/states",
                headers={"Authorization": f"Bearer {cfg.ha_token}"},
                timeout=8,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"discover_automations HA error: {e}")
            return jsonify({"error": "upstream HA unreachable"}), 502
        if resp.status_code != 200:
            return jsonify({"error": f"HA returned {resp.status_code}"}), 502

        keep_domains = {"scene", "script", "switch", "light", "lock", "cover",
                        "media_player", "climate", "input_boolean", "fan"}
        entities = []
        for s in resp.json():
            eid = s.get("entity_id", "")
            if "." not in eid:
                continue
            dom, suffix = eid.split(".", 1)
            if dom not in keep_domains:
                continue
            entities.append({
                "entity_id": eid,
                "domain": dom,
                "entity": suffix,
                "friendly_name": s.get("attributes", {}).get("friendly_name") or suffix,
                "state": s.get("state"),
            })
        entities.sort(key=lambda x: (x["domain"], x["entity_id"]))
        return jsonify({"home_id": home_id, "count": len(entities), "items": entities}), 200

    # ------- direct trigger --------------------------------------------------

    def trigger_automation(self):
        """Fire an HA (service, entity) directly without a voice gate.

        If an active enrollment exists for (user_ref, automation_id), refuses with
        409 ENROLLMENT_REQUIRED — voice-gated automations cannot be bypassed via
        this endpoint. The caller must take the VAPI challenge path instead.
        """
        body = request.get_json(silent=True) or {}
        home_id = (body.get("home_id") or "").strip()
        ha_service = (body.get("ha_service") or "").strip()
        ha_entity = (body.get("ha_entity") or "").strip()
        user_ref = (body.get("user_ref") or "").strip()
        automation_id = (body.get("automation_id") or "").strip()

        if not home_id or not ha_service or not ha_entity:
            return jsonify({
                "error": "home_id, ha_service, and ha_entity are required",
                "code": "VALIDATION",
            }), 400
        if "." in ha_entity:
            return jsonify({
                "error": "ha_entity is the entity suffix only (e.g. 'decorations_on'), not 'script.decorations_on'",
                "code": "VALIDATION",
            }), 400

        # Voice-gate guard: if (user_ref, automation_id) supplied AND an active
        # enrollment exists, refuse — caller must use the VAPI flow.
        if user_ref and automation_id:
            check = self._svc.check(user_ref, automation_id)
            if check.exists and check.enrollment and check.enrollment.status == EnrollmentStatus.ACTIVE:
                return jsonify({
                    "error": "this automation requires voice authentication",
                    "code": "ENROLLMENT_REQUIRED",
                    "enrollment_id": check.enrollment.id,
                }), 409

        result = self._dispatcher.dispatch_direct(home_id, ha_service, ha_entity)
        status = 200 if result.success else 502
        return jsonify({
            "success": result.success,
            "message": result.message,
            "status_code": result.status_code,
            "latency_ms": result.latency_ms,
        }), status

    # ------- scene-mapping CRUD (mobile-facing) ------------------------------

    def _require_scenes(self):
        if self._scenes is None:
            return jsonify({
                "error": "scene mapping service not configured",
                "code": "NOT_CONFIGURED",
            }), 503
        return None

    def create_scene_mapping(self):
        err = self._require_scenes()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        home_id = (body.get("home_id") or "").strip()
        scene_name = (body.get("scene_name") or "").strip()
        webhook_id = (body.get("webhook_id") or "").strip()
        if not home_id or not scene_name or not webhook_id:
            return jsonify({
                "error": "home_id, scene_name, and webhook_id are required",
                "code": "VALIDATION",
            }), 400
        try:
            m = self._scenes.create_mapping(
                home_id=home_id, scene_name=scene_name, webhook_id=webhook_id,
            )
            return jsonify(scene_mapping_to_dict(m)), 201
        except ValueError as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400

    def list_scene_mappings(self):
        err = self._require_scenes()
        if err:
            return err
        home_id = request.args.get("home_id", "").strip()
        if not home_id:
            return jsonify({"error": "home_id query param is required", "code": "VALIDATION"}), 400
        items = self._scenes.list_scenes_for_home(home_id)
        return jsonify({
            "items": [scene_mapping_to_dict(m) for m in items],
            "count": len(items),
        }), 200

    def get_scene_mapping(self, mapping_id: str):
        err = self._require_scenes()
        if err:
            return err
        m = self._scenes.get_mapping(mapping_id)
        if not m:
            return jsonify({"error": "not found"}), 404
        return jsonify(scene_mapping_to_dict(m)), 200

    def update_scene_mapping(self, mapping_id: str):
        err = self._require_scenes()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            m = self._scenes.update_mapping(
                mapping_id=mapping_id,
                scene_name=body.get("scene_name"),
                webhook_id=body.get("webhook_id"),
                is_active=body.get("is_active"),
            )
            return jsonify(scene_mapping_to_dict(m)), 200
        except ValueError as ex:
            return jsonify({"error": str(ex)}), 404

    def delete_scene_mapping(self, mapping_id: str):
        err = self._require_scenes()
        if err:
            return err
        ok = self._scenes.delete_mapping(mapping_id)
        if not ok:
            return jsonify({"error": "not found"}), 404
        return "", 204

    # ------- favorites -------------------------------------------------------

    def _require_favorites(self):
        if self._favorites is None:
            return jsonify({
                "error": "favorite device service not configured",
                "code": "NOT_CONFIGURED",
            }), 503
        return None

    def _is_voice_gated(self, user_ref: str, entity_id: str) -> tuple[bool, Optional[str]]:
        """Return (is_gated, enrollment_id). True if an active enrollment exists
        for (user_ref, automation_id derived from entity suffix)."""
        if not entity_id or "." not in entity_id:
            return False, None
        suffix = entity_id.split(".", 1)[1]
        check = self._svc.check(user_ref, suffix)
        if check.exists and check.enrollment and check.enrollment.status == EnrollmentStatus.ACTIVE:
            return True, check.enrollment.id
        return False, None

    def create_favorite(self):
        err = self._require_favorites()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            result = self._favorites.add_favorite(
                user_ref=body.get("user_ref") or "",
                home_id=body.get("home_id") or "",
                entity_id=(body.get("entity_id") or None),
                device_id=(body.get("device_id") or None),
                friendly_name=body.get("friendly_name"),
                position=body.get("position"),
            )
        except NoControllableEntityError as ex:
            return jsonify({"error": str(ex), "code": "NO_CONTROLLABLE_ENTITY"}), 400
        except ConflictingArgumentsError as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400
        except ValueError as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400
        except HomeUnreachableError as ex:
            return jsonify({"error": str(ex), "code": "HOME_UNREACHABLE"}), 503
        except RuntimeError as ex:
            return jsonify({"error": str(ex), "code": "DEPENDENCY_UNAVAILABLE"}), 503

        f = result.favorite
        gated = result.voice_auth_enrollment_id is not None
        body_out = favorite_to_dict(f, voice_auth_required=gated)
        if gated:
            body_out["voice_auth_enrollment_id"] = result.voice_auth_enrollment_id
        return jsonify(body_out), 201

    def list_favorites(self):
        err = self._require_favorites()
        if err:
            return err
        user_ref = request.args.get("user_ref", "").strip()
        home_id = request.args.get("home_id", "").strip()
        if not user_ref or not home_id:
            return jsonify({
                "error": "user_ref and home_id query params are required",
                "code": "VALIDATION",
            }), 400
        items = self._favorites.list_favorites(user_ref, home_id)
        # Annotate each with voice_auth_required (computed via enrollments)
        out = []
        for f in items:
            gated, _ = self._is_voice_gated(user_ref, f.entity_id)
            out.append(favorite_to_dict(f, voice_auth_required=gated))
        return jsonify({
            "items": out,
            "count": len(out),
        }), 200

    def delete_favorite(self, favorite_id: str):
        """DELETE /favorites/{ref} — ref may be the favorite's id, OR its
        device_id / entity_id (one-step delete, no list lookup needed).

        The device/entity form needs (user_ref, home_id) to know whose
        favorite to remove: pass them as query params, or just user_ref is
        inferred from a login token.
        """
        err = self._require_favorites()
        if err:
            return err

        # 1. Exact favorite id (original behavior, unchanged)
        if self._favorites.remove_favorite(favorite_id):
            return "", 204

        # 2. Fallback: treat the ref as a device_id / entity_id
        user_ref = (request.args.get("user_ref") or "").strip() \
            or (getattr(g, "user_ref", None) or "")
        home_id = (request.args.get("home_id") or "").strip()
        if user_ref and home_id:
            if self._favorites.remove_by_device_or_entity(user_ref, home_id, favorite_id):
                return "", 204
            return jsonify({
                "error": f"no favorite with id, device_id or entity_id "
                         f"'{favorite_id}' for user '{user_ref}' in home '{home_id}'",
                "code": "NOT_FOUND",
            }), 404

        return jsonify({
            "error": f"no favorite with id '{favorite_id}'. If that is a "
                     f"device_id or entity_id, add ?user_ref=...&home_id=... "
                     f"to delete by device/entity in one step.",
            "code": "NOT_FOUND",
        }), 404

    def reorder_favorites(self):
        err = self._require_favorites()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        items = body.get("items") if isinstance(body, dict) else body
        if not isinstance(items, list):
            return jsonify({
                "error": "body must be {\"items\": [{\"id\":..., \"position\":...}]} or a JSON array",
                "code": "VALIDATION",
            }), 400
        try:
            updated = self._favorites.reorder(items)
        except (ValueError, TypeError) as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400
        return jsonify({
            "items": [favorite_to_dict(f) for f in updated],
            "count": len(updated),
        }), 200

    # ------- voice-enable (VAPI provisioning) --------------------------------

    def _require_vapi_prov(self):
        if self._vapi_prov is None:
            return jsonify({
                "error": "VAPI provisioning service not configured",
                "code": "NOT_CONFIGURED",
            }), 503
        return None

    def voice_enable(self):
        err = self._require_vapi_prov()
        if err:
            return err
        body = request.get_json(silent=True) or {}
        try:
            mapping = self._vapi_prov.enable(
                user_ref=body.get("user_ref") or "",
                home_id=body.get("home_id") or "",
                area_code=body.get("area_code"),
                label=body.get("label"),
                assistant_id=body.get("assistant_id"),
            )
        except ValueError as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400
        except VapiClientError as ex:
            logger.error(f"voice_enable VAPI error: {ex}")
            return jsonify({
                "error": f"VAPI provisioning failed: {ex}",
                "code": "VAPI_ERROR",
                "vapi_status": ex.status_code,
            }), 502
        return jsonify(phone_to_dict(mapping)), 201

    def voice_enable_status(self):
        err = self._require_vapi_prov()
        if err:
            return err
        user_ref = request.args.get("user_ref", "").strip()
        if not user_ref:
            return jsonify({"error": "user_ref query param is required", "code": "VALIDATION"}), 400
        try:
            status = self._vapi_prov.status(user_ref)
        except ValueError as ex:
            return jsonify({"error": str(ex), "code": "VALIDATION"}), 400
        return jsonify({
            "enabled": status.enabled,
            "is_dry_run": status.is_dry_run,
            "mapping": phone_to_dict(status.mapping) if status.mapping else None,
        }), 200

    def voice_disable(self):
        err = self._require_vapi_prov()
        if err:
            return err
        user_ref = request.args.get("user_ref", "").strip()
        if not user_ref:
            return jsonify({"error": "user_ref query param is required", "code": "VALIDATION"}), 400
        try:
            removed = self._vapi_prov.disable(user_ref)
        except VapiClientError as ex:
            logger.error(f"voice_disable VAPI error: {ex}")
            return jsonify({
                "error": f"VAPI release failed: {ex}",
                "code": "VAPI_ERROR",
                "vapi_status": ex.status_code,
            }), 502
        if not removed:
            return jsonify({"error": "no active VAPI mapping to release"}), 404
        return "", 204

    # ------- devices/discover -----------------------------------------------

    def discover_devices(self):
        if self._registry is None:
            return jsonify({
                "error": "device registry not configured",
                "code": "NOT_CONFIGURED",
            }), 503
        home_id = request.args.get("home_id", "").strip()
        if not home_id:
            return jsonify({"error": "home_id query param is required", "code": "VALIDATION"}), 400
        if not self._dispatcher.has_home(home_id):
            return jsonify({"error": f"home '{home_id}' not configured", "code": "NOT_CONFIGURED"}), 404
        try:
            devices = self._registry.list_devices(home_id)
        except HomeUnreachableError as ex:
            return jsonify({"error": str(ex), "code": "HOME_UNREACHABLE"}), 503
        return jsonify({
            "home_id": home_id,
            "count": len(devices),
            "items": [
                {
                    "device_id": d.device_id,
                    "name": d.name,
                    "manufacturer": d.manufacturer,
                    "model": d.model,
                    "area": d.area,
                    "primary_entity_id": d.primary_entity_id,
                    "primary_domain": d.primary_domain,
                    "is_controllable": d.is_controllable,
                    "all_entities": d.all_entities,
                }
                for d in devices
            ],
        }), 200

    # ------- items/search ---------------------------------------------------

    def search_items(self):
        """Unified search across devices, entities, scenes, scripts, automations.

        Query params:
          home_id  (required)   — which home's HA to search
          q        (optional)   — case-insensitive substring on name + entity_id + device_id
          kind     (optional)   — comma-separated subset of {device,entity,scene,script,automation}
          user_ref (optional)   — when present, populate is_favorited + favorite_id flags per row
          limit    (default 200, max 500)
        """
        if self._registry is None or self._favorites is None:
            return jsonify({"error": "search not configured", "code": "NOT_CONFIGURED"}), 503

        home_id = request.args.get("home_id", "").strip()
        if not home_id:
            return jsonify({"error": "home_id query param is required", "code": "VALIDATION"}), 400
        if not self._dispatcher.has_home(home_id):
            return jsonify({"error": f"home '{home_id}' not configured", "code": "NOT_CONFIGURED"}), 404

        q = (request.args.get("q") or "").strip().lower()
        kinds_raw = (request.args.get("kind") or "").strip().lower()
        kind_filter = {k.strip() for k in kinds_raw.split(",") if k.strip()} if kinds_raw else None
        user_ref = (request.args.get("user_ref") or "").strip()
        try:
            limit = min(int(request.args.get("limit", "200")), 500)
        except ValueError:
            limit = 200

        # 1. Build per-user favorite lookup (entity_id -> favorite_id) for fast annotation
        fav_by_entity: dict = {}
        if user_ref:
            for f in self._favorites.list_favorites(user_ref, home_id):
                fav_by_entity[f.entity_id] = f.id

        # 2. Pull devices and the raw HA states (for scenes/scripts/automations + orphan entities)
        try:
            devices = self._registry.list_devices(home_id)
        except HomeUnreachableError as ex:
            return jsonify({"error": str(ex), "code": "HOME_UNREACHABLE"}), 503

        # State map for adding `state` field to results
        cfg = self._dispatcher._homes.get(home_id)
        states_by_entity: dict = {}
        try:
            import requests as _rq
            r = _rq.get(
                f"{cfg.ha_url.rstrip('/')}/api/states",
                headers={"Authorization": f"Bearer {cfg.ha_token}"},
                timeout=8,
            )
            if r.status_code == 200:
                for s in r.json():
                    states_by_entity[s.get("entity_id", "")] = {
                        "state": s.get("state"),
                        "friendly_name": (s.get("attributes") or {}).get("friendly_name"),
                    }
        except Exception as e:
            logger.warning(f"search_items: states fetch failed home={home_id}: {e}")

        # 3. Build candidate items
        items: list = []

        # Devices
        if kind_filter is None or "device" in kind_filter:
            for d in devices:
                if not d.is_controllable:
                    continue
                primary = d.primary_entity_id or ""
                state_info = states_by_entity.get(primary, {})
                items.append({
                    "kind": "device",
                    "device_id": d.device_id,
                    "entity_id": primary,
                    "name": d.name,
                    "domain": d.primary_domain,
                    "manufacturer": d.manufacturer,
                    "model": d.model,
                    "area": d.area,
                    "state": state_info.get("state"),
                    "is_favorited": primary in fav_by_entity,
                    "favorite_id": fav_by_entity.get(primary),
                    "_match_blob": " ".join(filter(None, [
                        d.name or "", d.device_id or "", primary,
                        d.manufacturer or "", d.model or "",
                    ])).lower(),
                })

        # Activations (scene/script/automation) and orphan controllable entities
        ACTIVATION = {"scene", "script", "automation"}
        ALLOWED_ENTITY_DOMS = {"input_boolean"}  # raw entities — narrow allowlist
        # Entities that belong to a device are surfaced via the device row above,
        # so skip them here to avoid duplicates.
        device_entities = {e for d in devices for e in d.all_entities}

        for entity_id, info in states_by_entity.items():
            if "." not in entity_id:
                continue
            dom = entity_id.split(".", 1)[0]
            if dom in ACTIVATION:
                k = dom
            elif entity_id in device_entities:
                continue
            elif dom in ALLOWED_ENTITY_DOMS:
                k = "entity"
            else:
                continue
            if kind_filter is not None and k not in kind_filter:
                continue
            name = info.get("friendly_name") or entity_id.split(".", 1)[1]
            items.append({
                "kind": k,
                "device_id": None,
                "entity_id": entity_id,
                "name": name,
                "domain": dom,
                "manufacturer": None,
                "model": None,
                "area": None,
                "state": info.get("state"),
                "is_favorited": entity_id in fav_by_entity,
                "favorite_id": fav_by_entity.get(entity_id),
                "_match_blob": (name + " " + entity_id).lower(),
            })

        # 4. Apply q substring filter
        if q:
            items = [i for i in items if q in i["_match_blob"]]

        # 5. Sort: kind priority (devices first, then activations, then entities), then alphabetical
        kind_order = {"device": 0, "scene": 1, "script": 2, "automation": 3, "entity": 4}
        items.sort(key=lambda i: (kind_order.get(i["kind"], 9), (i["name"] or "").lower()))

        # 6. Strip helper field, apply limit
        for i in items:
            i.pop("_match_blob", None)
        items = items[:limit]

        return jsonify({
            "home_id": home_id,
            "count": len(items),
            "items": items,
        }), 200

    # ------- favorites/{id}/fire --------------------------------------------

    def fire_favorite(self, favorite_id: str):
        """Activate a favorite. Refuses 409 if voice-gated.

        Body (optional): { "action": "<turn_on|turn_off|trigger|lock|unlock>" }
        Default action is per-domain (see HADirectDispatcher.DEFAULT_ACTIONS).
        """
        err = self._require_favorites()
        if err:
            return err
        f = self._favorites.get(favorite_id)
        if not f:
            return jsonify({"error": "favorite not found"}), 404

        # Voice-gate check — locks always end up here
        gated, enroll_id = self._is_voice_gated(f.user_ref, f.entity_id)
        if gated:
            return jsonify({
                "error": "this favorite requires voice authentication",
                "code": "ENROLLMENT_REQUIRED",
                "enrollment_id": enroll_id,
                "automation_name": f.friendly_name,
                "automation_id": f.entity_id.split(".", 1)[1] if "." in f.entity_id else None,
                "home_id": f.home_id,
            }), 409

        body = request.get_json(silent=True) or {}
        action = (body.get("action") or "").strip() or None
        if "." not in f.entity_id:
            return jsonify({"error": "favorite has malformed entity_id"}), 500
        ha_service, ha_entity = f.entity_id.split(".", 1)
        result = self._dispatcher.dispatch_direct(f.home_id, ha_service, ha_entity, action=action)
        status = 200 if result.success else 502
        return jsonify({
            "success": result.success,
            "message": result.message,
            "status_code": result.status_code,
            "latency_ms": result.latency_ms,
            "favorite_id": f.id,
            "entity_id": f.entity_id,
        }), status

