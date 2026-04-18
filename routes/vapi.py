"""
VAPI (Voice AI) integration routes

Handles tool-call webhooks from a VAPI Assistant. VAPI performs ASR/NLU/TTS
in the cloud and invokes these endpoints as function tools to run the
challenge-response voice auth flow and trigger the Home Assistant scene.

Endpoints:
- POST /vapi/auth/request - Issue a voice challenge for a scene
- POST /vapi/auth/verify  - Verify spoken response and trigger HA scene

VAPI tool-call payload shape:
    {
        "message": {
            "type": "tool-calls",
            "call": { "id": "call_abc", ... },
            "toolCallList": [
                {
                    "id": "tc_xyz",
                    "function": {
                        "name": "request_scene_challenge",
                        "arguments": { "home_id": "home_1", "scene_name": "night scene" }
                    }
                }
            ]
        }
    }

VAPI response shape:
    { "results": [ { "toolCallId": "tc_xyz", "result": { ... } } ] }
"""

import logging
import os
from flask import Blueprint, request, jsonify, current_app
from challenge import (
    generate_challenge,
    store_challenge,
    validate_challenge,
    get_challenge_data,
)
from config import MAX_ATTEMPTS

logger = logging.getLogger(__name__)
vapi_bp = Blueprint("vapi", __name__)

CLIENT_TYPE = "vapi"
VAPI_SECRET = os.environ.get("VAPI_WEBHOOK_SECRET")


def _unwrap(req):
    """Extract call_id, tool_id, tool_name, and arguments from a VAPI payload."""
    body = req.get_json(silent=True) or {}
    msg = body.get("message", {}) or {}
    call = msg.get("call", {}) or body.get("call", {}) or {}
    tool_list = msg.get("toolCallList") or msg.get("toolCalls") or []
    tool = tool_list[0] if tool_list else {}
    fn = tool.get("function", {}) or {}
    args = fn.get("arguments") or {}
    if isinstance(args, str):
        import json
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    return {
        "call_id": call.get("id") or tool.get("id") or "unknown",
        "tool_id": tool.get("id") or "unknown",
        "tool_name": fn.get("name"),
        "args": args,
    }


def _ok(tool_id, result):
    return jsonify({"results": [{"toolCallId": tool_id, "result": result}]}), 200


def _authorized(req):
    if not VAPI_SECRET:
        return True
    return req.headers.get("X-Vapi-Secret") == VAPI_SECRET


@vapi_bp.route("/auth/request", methods=["POST"])
def vapi_request():
    """Issue a challenge phrase for a scene request."""
    if not _authorized(request):
        return jsonify({"error": "unauthorized"}), 401

    try:
        p = _unwrap(request)
        args = p["args"]
        home_id = args.get("home_id")
        scene_name = (args.get("scene_name") or "").strip().lower()

        if not home_id or not scene_name:
            return _ok(p["tool_id"], {
                "status": "error",
                "speech": "Missing home or scene.",
            })

        identifier = f"{home_id}:{p['call_id']}"
        phrase = generate_challenge()
        store_challenge(identifier, phrase, client_type=CLIENT_TYPE, intent=scene_name)

        logger.info(
            f"VAPI request - home={home_id} call={p['call_id']} "
            f"scene={scene_name} phrase={phrase}"
        )

        return _ok(p["tool_id"], {
            "status": "challenge",
            "speech": f"Security check. Please say: {phrase}",
            "challenge": phrase,
        })

    except Exception as e:
        logger.error(f"VAPI request error: {e}", exc_info=True)
        return jsonify({"error": "internal error"}), 500


@vapi_bp.route("/auth/verify", methods=["POST"])
def vapi_verify():
    """Verify spoken response; on success, trigger the Home Assistant scene."""
    if not _authorized(request):
        return jsonify({"error": "unauthorized"}), 401

    try:
        p = _unwrap(request)
        args = p["args"]
        home_id = args.get("home_id")
        spoken = args.get("spoken_response", "")

        if not home_id:
            return _ok(p["tool_id"], {
                "status": "error",
                "speech": "Missing home.",
            })

        identifier = f"{home_id}:{p['call_id']}"
        is_valid, message, intent = validate_challenge(
            identifier, spoken, client_type=CLIENT_TYPE
        )

        if is_valid:
            container = getattr(current_app, "container", None)
            scene_name = intent or ""
            webhook_id = None
            success = False
            fail_message = ""

            if container is not None:
                try:
                    webhook_id = container.scene_mapping_service.get_webhook_for_scene(
                        home_id, scene_name
                    )
                except Exception as e:
                    logger.warning(f"VAPI webhook lookup failed: {e}")

                try:
                    result = container.ha_service.trigger_scene(
                        scene_id=scene_name,
                        home_id=home_id,
                        source="VAPI Voice Authentication",
                        webhook_id=webhook_id,
                    )
                    success = result.success
                    fail_message = result.message
                except Exception as e:
                    logger.error(f"VAPI trigger failed: {e}", exc_info=True)
                    fail_message = str(e)
            else:
                fail_message = "Orchestrator not ready."

            display = scene_name.replace("_", " ").strip() or "Scene"
            speech = (
                f"{display} activated." if success
                else f"Scene activation failed. {fail_message}"
            )
            logger.info(
                f"VAPI verify approved - home={home_id} scene={scene_name} "
                f"success={success}"
            )
            return _ok(p["tool_id"], {
                "status": "approved" if success else "error",
                "speech": speech,
                "intent": scene_name,
                "end_call": True,
            })

        data = get_challenge_data(identifier, client_type=CLIENT_TYPE) or {}
        attempts = data.get("attempts", MAX_ATTEMPTS)
        remaining = max(0, MAX_ATTEMPTS - attempts)
        lower_msg = (message or "").lower()

        if not data:
            reason, speech, end = "no_challenge", "No active challenge.", True
        elif "expired" in lower_msg:
            reason, speech, end = "expired", "Challenge expired.", True
        elif "maximum" in lower_msg or remaining == 0:
            reason, speech, end = "max_attempts", "Verification failed.", True
        else:
            reason = "mismatch"
            speech = f"That didn't match. {remaining} left."
            end = False

        logger.info(
            f"VAPI verify denied - home={home_id} reason={reason} remaining={remaining}"
        )
        return _ok(p["tool_id"], {
            "status": "denied",
            "speech": speech,
            "reason": reason,
            "attempts_remaining": remaining,
            "end_call": end,
        })

    except Exception as e:
        logger.error(f"VAPI verify error: {e}", exc_info=True)
        return jsonify({"error": "internal error"}), 500
