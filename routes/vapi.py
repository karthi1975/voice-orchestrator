"""
VAPI (Voice AI) integration routes.

Handles VAPI tool-call webhooks. Two flows coexist:

1. LEGACY SCENE-CATALOG FLOW (existing): variableValues carry scene_name,
   the dispatcher looks up (service, entity) in SCENE_CATALOG_JSON/overrides
   and fires. Nothing in voice_auth_enrollments is consulted.

2. ENROLLMENT FLOW (new for voice-auth): variableValues carry user_ref +
   automation_id (and optionally home_id). The orchestrator:
     - resolves the enrollment via VoiceAuthService
     - checks cooldown + max-attempts
     - issues a phrase challenge
     - on verify, dispatches via (enrollment.ha_service, enrollment.ha_entity)
     - writes to voice_auth_challenge_logs at each step

The VAPI system prompt decides which flow by whether automation_id is set.
"""

import json
import logging
import os
from flask import Blueprint, current_app, request, jsonify

from challenge import (
    generate_challenge,
    store_challenge,
    validate_challenge,
    get_challenge_data,
)
from config import MAX_ATTEMPTS
from app.domain.voice_auth_enums import ChallengeResult
from app.infrastructure.home_assistant.direct_dispatcher import HADirectDispatcher

logger = logging.getLogger(__name__)
vapi_bp = Blueprint("vapi", __name__)

CLIENT_TYPE = "vapi"
VAPI_SECRET = os.environ.get("VAPI_WEBHOOK_SECRET")

_dispatcher: HADirectDispatcher | None = None


def _get_dispatcher() -> HADirectDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = HADirectDispatcher.from_env()
    return _dispatcher


def _get_voice_auth_service():
    """Return the VoiceAuthService attached to the app, or None if not wired."""
    return getattr(current_app, "voice_auth_service", None)


def _unwrap(req):
    """Extract call_id, tool_id, tool_name, args, and assistantOverrides from a VAPI payload."""
    body = req.get_json(silent=True) or {}
    msg = body.get("message", {}) or {}
    call = msg.get("call", {}) or body.get("call", {}) or {}
    tool_list = msg.get("toolCallList") or msg.get("toolCalls") or []
    tool = tool_list[0] if tool_list else {}
    fn = tool.get("function", {}) or {}
    args = fn.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}

    # VAPI also passes assistant.metadata and assistantOverrides.variableValues
    # on each tool call. Read variableValues as a secondary source so an app can
    # set home_id/user_ref/automation_id at call start without adding them to
    # every tool signature.
    assistant = msg.get("assistant", {}) or {}
    overrides = msg.get("assistantOverrides", {}) or {}
    vvalues = overrides.get("variableValues") or assistant.get("variableValues") or {}

    return {
        "call_id": call.get("id") or tool.get("id") or "unknown",
        "tool_id": tool.get("id") or "unknown",
        "tool_name": fn.get("name"),
        "args": args,
        "variable_values": vvalues,
    }


def _first(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


def _ok(tool_id, result):
    return jsonify({"results": [{"toolCallId": tool_id, "result": result}]}), 200


def _authorized(req):
    if not VAPI_SECRET:
        return True
    return req.headers.get("X-Vapi-Secret") == VAPI_SECRET


@vapi_bp.route("/demo-config", methods=["GET"])
def vapi_demo_config():
    return jsonify({
        "publicKey": os.environ.get("VAPI_PUBLIC_KEY", ""),
        "assistantId": os.environ.get("VAPI_ASSISTANT_ID", ""),
        "homeId": os.environ.get("VAPI_DEMO_HOME_ID", "scott_home"),
    })


@vapi_bp.route("/auth/request", methods=["POST"])
def vapi_request():
    """Issue a challenge phrase.

    Picks enrollment or legacy flow based on which identifiers are present.
    """
    if not _authorized(request):
        return jsonify({"error": "unauthorized"}), 401

    try:
        p = _unwrap(request)
        args = p["args"]
        vv = p["variable_values"]

        # Collect identifiers from either tool args or variableValues
        home_id = _first(args.get("home_id"), vv.get("home_id"))
        scene_name = (args.get("scene_name") or "").strip().lower()
        user_ref = _first(args.get("user_ref"), vv.get("user_ref"))
        automation_id = _first(args.get("automation_id"), vv.get("automation_id"))

        use_enrollment = bool(user_ref and automation_id)
        svc = _get_voice_auth_service() if use_enrollment else None

        if use_enrollment and svc is None:
            logger.error("VAPI enrollment flow requested but VoiceAuthService not wired")
            return _ok(p["tool_id"], {
                "status": "error",
                "speech": "Voice authentication service is not available.",
                "end_call": True,
            })

        if use_enrollment:
            outcome = svc.resolve_for_challenge(
                user_ref=user_ref, automation_id=automation_id,
            )
            if outcome.denied():
                # log denial for audit
                svc.open_log(
                    enrollment=outcome.enrollment,
                    user_ref=user_ref,
                    automation_id=automation_id,
                    home_id=home_id,
                    vapi_call_id=p["call_id"],
                    initiated_by=vv.get("initiated_by") or "VAPI",
                    request_payload=json.dumps({"args": args, "vv": vv}),
                    initial_result=outcome.denial_reason,
                    failure_reason=outcome.detail,
                )
                reason = outcome.denial_reason.value
                speech = _denial_speech(outcome.denial_reason,
                                        cooldown=outcome.cooldown_remaining_seconds,
                                        detail=outcome.detail)
                logger.info(
                    f"VAPI request DENIED user={user_ref} automation={automation_id} "
                    f"reason={reason} detail={outcome.detail}"
                )
                return _ok(p["tool_id"], {
                    "status": "denied",
                    "speech": speech,
                    "reason": reason,
                    "cooldown_remaining_seconds": outcome.cooldown_remaining_seconds,
                    "end_call": True,
                })

            e = outcome.enrollment
            identifier = f"enroll:{e.id}:{p['call_id']}"
            phrase = generate_challenge()
            store_challenge(identifier, phrase, client_type=CLIENT_TYPE,
                            intent=e.automation_id)

            svc.open_log(
                enrollment=e,
                user_ref=user_ref,
                automation_id=e.automation_id,
                home_id=e.home_id,
                vapi_call_id=p["call_id"],
                initiated_by=vv.get("initiated_by") or "VAPI",
                request_payload=json.dumps({"args": args, "vv": vv}),
                initial_result=ChallengeResult.PENDING,
            )

            logger.info(
                f"VAPI enrollment request - user={user_ref} automation={e.automation_id} "
                f"call={p['call_id']} phrase={phrase}"
            )
            return _ok(p["tool_id"], {
                "status": "challenge",
                "speech": f"To confirm {e.automation_name}, please say: {phrase}",
                "challenge": phrase,
                "automation_name": e.automation_name,
            })

        # Legacy scene-catalog flow
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
    """Verify spoken response; on success, dispatch via the matching path."""
    if not _authorized(request):
        return jsonify({"error": "unauthorized"}), 401

    try:
        p = _unwrap(request)
        args = p["args"]
        vv = p["variable_values"]

        home_id = _first(args.get("home_id"), vv.get("home_id"))
        spoken = args.get("spoken_response", "")
        user_ref = _first(args.get("user_ref"), vv.get("user_ref"))
        automation_id = _first(args.get("automation_id"), vv.get("automation_id"))

        use_enrollment = bool(user_ref and automation_id)
        svc = _get_voice_auth_service() if use_enrollment else None

        if use_enrollment:
            if svc is None:
                return _ok(p["tool_id"], {
                    "status": "error",
                    "speech": "Voice authentication service is not available.",
                    "end_call": True,
                })
            return _verify_enrollment(p, svc, user_ref, automation_id, home_id, spoken)

        # Legacy
        if not home_id:
            return _ok(p["tool_id"], {"status": "error", "speech": "Missing home."})
        return _verify_legacy(p, home_id, spoken)

    except Exception as e:
        logger.error(f"VAPI verify error: {e}", exc_info=True)
        return jsonify({"error": "internal error"}), 500


# ---------- Enrollment verify ------------------------------------------------


def _verify_enrollment(p, svc, user_ref, automation_id, home_id, spoken):
    e = svc._enrollments.get_by_user_and_automation(user_ref, automation_id)
    if not e:
        _log_terminal(svc, user_ref, automation_id, home_id, p["call_id"],
                      ChallengeResult.DENIED_NO_ENROLLMENT, "enrollment disappeared mid-flight")
        return _ok(p["tool_id"], {
            "status": "denied",
            "speech": "Enrollment not found.",
            "reason": ChallengeResult.DENIED_NO_ENROLLMENT.value,
            "end_call": True,
        })

    identifier = f"enroll:{e.id}:{p['call_id']}"
    is_valid, message, _intent = validate_challenge(identifier, spoken, client_type=CLIENT_TYPE)

    if is_valid:
        # Dispatch via enrollment's stored (service, entity) — ignores any global catalog
        result = _get_dispatcher().dispatch_direct(e.home_id, e.ha_service, e.ha_entity)
        final_result = ChallengeResult.SUCCESS if result.success else ChallengeResult.ERROR
        _close_latest_log(svc, p["call_id"], final_result,
                          failure_reason=None if result.success else result.message,
                          response_payload=json.dumps({"dispatch": result.__dict__}))
        speech = (
            f"{e.automation_name} activated." if result.success
            else f"Verified, but activation failed. {result.message}"
        )
        logger.info(
            f"VAPI enrollment verify approved - user={user_ref} automation={automation_id} "
            f"success={result.success}"
        )
        return _ok(p["tool_id"], {
            "status": "approved" if result.success else "error",
            "speech": speech,
            "automation_id": e.automation_id,
            "automation_name": e.automation_name,
            "end_call": True,
        })

    data = get_challenge_data(identifier, client_type=CLIENT_TYPE) or {}
    attempts = data.get("attempts", MAX_ATTEMPTS)
    remaining = max(0, MAX_ATTEMPTS - attempts)
    lower_msg = (message or "").lower()

    if not data:
        reason, speech, end, result = "no_challenge", "No active challenge.", True, ChallengeResult.ABANDONED
    elif "expired" in lower_msg:
        reason, speech, end, result = "expired", "Challenge expired.", True, ChallengeResult.TIMEOUT
    elif "maximum" in lower_msg or remaining == 0:
        reason, speech, end, result = "max_attempts", "Verification failed.", True, ChallengeResult.FAIL
    else:
        reason, speech, end, result = "mismatch", f"That didn't match. {remaining} left.", False, ChallengeResult.FAIL

    # Close a log entry only when the challenge is truly over (mismatch-with-retries-left stays open)
    if end:
        _close_latest_log(svc, p["call_id"], result, failure_reason=reason)

    logger.info(
        f"VAPI enrollment verify denied - user={user_ref} automation={automation_id} "
        f"reason={reason} remaining={remaining}"
    )
    return _ok(p["tool_id"], {
        "status": "denied",
        "speech": speech,
        "reason": reason,
        "attempts_remaining": remaining,
        "end_call": end,
    })


# ---------- Legacy scene-catalog verify -------------------------------------


def _verify_legacy(p, home_id, spoken):
    identifier = f"{home_id}:{p['call_id']}"
    is_valid, message, intent = validate_challenge(identifier, spoken, client_type=CLIENT_TYPE)

    if is_valid:
        scene_name = intent or ""
        result = _get_dispatcher().dispatch(home_id, scene_name)
        display = scene_name.strip() or "Scene"
        speech = (
            f"{display} activated." if result.success
            else f"Scene activation failed. {result.message}"
        )
        logger.info(
            f"VAPI verify approved - home={home_id} scene={scene_name} "
            f"success={result.success} status={result.status_code}"
        )
        return _ok(p["tool_id"], {
            "status": "approved" if result.success else "error",
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
        reason, speech, end = "mismatch", f"That didn't match. {remaining} left.", False

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


# ---------- Helpers ---------------------------------------------------------


def _denial_speech(reason: ChallengeResult, cooldown: int, detail: str | None) -> str:
    if reason == ChallengeResult.DENIED_COOLDOWN:
        return f"Please try again in {cooldown} seconds."
    if reason == ChallengeResult.DENIED_LOCKED:
        return "This automation is locked. Contact support."
    if reason == ChallengeResult.DENIED_NO_ENROLLMENT:
        return "Voice authentication is not set up for that action."
    return "Unable to proceed. " + (detail or "")


def _close_latest_log(svc, vapi_call_id, result, failure_reason=None, response_payload=None):
    l = svc._logs.get_by_vapi_call_id(vapi_call_id)
    if not l:
        return
    if l.result != ChallengeResult.PENDING:
        return  # already terminal — don't overwrite
    svc.close_log(l.id, result=result, failure_reason=failure_reason,
                  response_payload=response_payload)


def _log_terminal(svc, user_ref, automation_id, home_id, vapi_call_id, result, detail):
    svc.open_log(
        enrollment=None,
        user_ref=user_ref,
        automation_id=automation_id,
        home_id=home_id,
        vapi_call_id=vapi_call_id,
        initiated_by="VAPI",
        initial_result=result,
        failure_reason=detail,
    )
