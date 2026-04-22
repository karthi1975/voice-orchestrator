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

  POST   /vapi/call-start          webhook VAPI hits on inbound phone calls;
                                   returns assistantOverrides.variableValues
                                   pre-populated with user_ref + home_id
                                   (looked up from the caller number).

Error envelope: { "error": "...", "code": "OPTIONAL_CODE" }
"""

import json
import logging
from typing import Optional

from flask import jsonify, request

from app.controllers.base_controller import BaseController
from app.domain.voice_auth_enums import (
    ChallengeResult,
    ChallengeType,
    EnrollmentStatus,
)
from app.domain.voice_auth_models import Enrollment, PhoneMapping
from app.services.voice_auth_service import VoiceAuthService
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher

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
        url_prefix: str = "/api/v1/voice-auth",
    ):
        super().__init__("voice_auth_api", url_prefix)
        self._svc = service
        self._dispatcher = dispatcher
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

        bp.add_url_rule("/vapi/call-start", "vapi_call_start", self.vapi_call_start, methods=["POST"])

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

    # ------- VAPI phone inbound webhook --------------------------------------

    def vapi_call_start(self):
        """VAPI calls this when a phone call begins. We return assistantOverrides
        so the assistant knows who is calling without asking.

        VAPI payload shape (abbreviated):
          { "message": { "type": "assistant-request",
                         "call": { "id": "...", "customer": { "number": "+15551234567" },
                                   "phoneNumber": { "id": "..." } } } }

        Response shape VAPI expects:
          {
            "assistant": {...}            # optional inline override
            "assistantId": "..."          # or reuse static assistant
            "assistantOverrides": {
              "variableValues": { "home_id": "...", "user_ref": "...",
                                  "caller_label": "...", "automation_id": null }
            }
          }
        """
        import os
        body = request.get_json(silent=True) or {}
        msg = body.get("message", {}) or {}
        call = msg.get("call", {}) or {}
        customer = call.get("customer", {}) or {}
        phone_num = (customer.get("number") or "").strip()

        overrides: dict = {"variableValues": {}}
        if phone_num:
            m = self._svc.lookup_phone(phone_num)
            if m:
                overrides["variableValues"] = {
                    "home_id": m.home_id,
                    "user_ref": m.user_ref,
                    "caller_label": m.label or "",
                }
                logger.info(
                    f"VAPI call-start matched phone={phone_num} "
                    f"-> user_ref={m.user_ref} home_id={m.home_id}"
                )
            else:
                logger.info(f"VAPI call-start unmapped phone={phone_num}")

        assistant_id = os.environ.get("VAPI_ASSISTANT_ID", "")
        response = {"assistantOverrides": overrides}
        if assistant_id:
            response["assistantId"] = assistant_id
        return jsonify(response), 200
