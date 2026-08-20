#!/usr/bin/env python3
"""Regenerate docs/api_reference_complete.pdf.

Same convention as gen_boards_api_guide.py: the doc is rebuilt from this
source, not patched, so corrections cannot drift from the code. Anything
asserted about status codes or payload shapes should be traceable to
app/controllers/voice_auth_controller.py or a test.

    venv/bin/python scripts/gen_api_reference.py
"""

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

VERSION = "1.1"
DATE = "August 20, 2026"
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "api_reference_complete.pdf",
)

INK = colors.HexColor("#1a1a2e")
ACCENT = colors.HexColor("#2b5797")
MUTED = colors.HexColor("#5a5a6e")
RULE = colors.HexColor("#d4d4dd")
CODE_BG = colors.HexColor("#f4f5f7")
HEAD_BG = colors.HexColor("#eceef2")
WARN_BG = colors.HexColor("#fdf6e3")

_ss = getSampleStyleSheet()

S = {
    "title": ParagraphStyle("title", parent=_ss["Title"], fontName="Helvetica-Bold",
                            fontSize=22, leading=26, textColor=INK, alignment=TA_LEFT,
                            spaceAfter=6),
    "subtitle": ParagraphStyle("subtitle", parent=_ss["Normal"], fontName="Helvetica",
                               fontSize=11, leading=15, textColor=MUTED, spaceAfter=2),
    "meta": ParagraphStyle("meta", parent=_ss["Normal"], fontName="Helvetica",
                           fontSize=9, leading=12, textColor=MUTED, spaceAfter=14),
    "h1": ParagraphStyle("h1", parent=_ss["Heading1"], fontName="Helvetica-Bold",
                         fontSize=15, leading=19, textColor=ACCENT,
                         spaceBefore=18, spaceAfter=8),
    "h2": ParagraphStyle("h2", parent=_ss["Heading2"], fontName="Helvetica-Bold",
                         fontSize=11, leading=14, textColor=INK,
                         spaceBefore=12, spaceAfter=5),
    "body": ParagraphStyle("body", parent=_ss["Normal"], fontName="Helvetica",
                           fontSize=9.5, leading=13.5, textColor=INK, spaceAfter=7),
    "bullet": ParagraphStyle("bullet", parent=_ss["Normal"], fontName="Helvetica",
                             fontSize=9.5, leading=13.5, textColor=INK,
                             leftIndent=14, bulletIndent=4, spaceAfter=4),
    "code": ParagraphStyle("code", parent=_ss["Code"], fontName="Courier",
                           fontSize=7.8, leading=10.5, textColor=INK),
    "cell": ParagraphStyle("cell", parent=_ss["Normal"], fontName="Helvetica",
                           fontSize=8, leading=10.5, textColor=INK),
    "cellcode": ParagraphStyle("cellcode", parent=_ss["Normal"], fontName="Courier",
                               fontSize=7.6, leading=10.5, textColor=INK),
    "cellhead": ParagraphStyle("cellhead", parent=_ss["Normal"], fontName="Helvetica-Bold",
                               fontSize=8, leading=10.5, textColor=INK),
}


def para(text, style="body"):
    return Paragraph(text, S[style])


def h1(text):
    return [Paragraph(text, S["h1"]),
            HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=6)]


def h2(text):
    return Paragraph(text, S["h2"])


def code(text):
    """Fixed-width block on a tinted background."""
    lines = [Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                       .replace(" ", "&nbsp;") or "&nbsp;", S["code"])
             for line in text.strip("\n").split("\n")]
    t = Table([[l] for l in lines], colWidths=[6.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
    ]))
    return [Spacer(1, 4), t, Spacer(1, 9)]


def table(rows, widths, code_cols=(), highlight_rows=()):
    """rows[0] is the header. `code_cols` render monospace."""
    data = []
    for r_index, row in enumerate(rows):
        out = []
        for c_index, cell in enumerate(row):
            if r_index == 0:
                style = "cellhead"
            elif c_index in code_cols:
                style = "cellcode"
            else:
                style = "cell"
            out.append(Paragraph(str(cell), S[style]))
        data.append(out)
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for r in highlight_rows:
        style.append(("BACKGROUND", (0, r), (-1, r), WARN_BG))
    t.setStyle(TableStyle(style))
    return [Spacer(1, 3), t, Spacer(1, 10)]


def bullets(items):
    return [Paragraph(f"• {i}", S["bullet"]) for i in items]


def note(text):
    """Called-out paragraph on a warm background — for the gotchas."""
    t = Table([[Paragraph(text, S["cell"])]], colWidths=[6.9 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0d5b0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [Spacer(1, 2), t, Spacer(1, 10)]


def mono(text):
    return f"<font face='Courier' size='8'>{text}</font>"


def build():
    story = []
    add = story.extend
    one = story.append

    # ---- cover block -------------------------------------------------------
    one(para("Voice Orchestrator — Complete API Reference", "title"))
    one(para("All mobile-facing endpoints: identity, enrollments, devices &amp; search, "
             "favorites, scene mappings, automations, boards, voice enable, VAPI.", "subtitle"))
    one(para(f"Version {VERSION} &nbsp;|&nbsp; {DATE} &nbsp;|&nbsp; Tetradapt "
             "&nbsp;|&nbsp; everything verified in production", "meta"))
    add(note(
        "<b>What changed in 1.1 (August 2026).</b> New §6: "
        f"{mono('GET /automations')} lists every Home Assistant automation in a home "
        "(name, enabled, last_triggered, gate + favorite flags) — this is the automations "
        f"pull for the mobile app. {mono('POST /automations/trigger')} now takes an optional "
        f"{mono('action')} — {mono('toggle')} / {mono('turn_on')} / {mono('turn_off')} — so "
        "on/off devices can actually be turned OFF (a bare trigger always meant turn_on "
        "before; this was the boards-page “can't turn the lamp off” bug). "
        f"{mono('POST /favorites/{id}/fire')} accepts the same override. New §7 indexes the "
        "boards endpoints, which v1.0 predated — the deep dive stays in "
        "boards_api_guide.pdf."))

    # ---- basics ------------------------------------------------------------
    add(h1("Basics"))
    add(table([
        ["Item", "Value"],
        ["Base URL ($BASE)", "https://voiceorchestrator.homeadapt.us/api/v1/voice-auth"],
        ["Auth", "Authorization: Bearer &lt;login token (JWT) or static platform key&gt;"],
        ["Login token", "from POST /auth/login; 30-day expiry; identifies the USER; "
                        "sending a foreign user_ref or home_id → 403"],
        ["Static keys", "sk_ios_/sk_and_/sk_web_ — identify only the platform; legacy, "
                        "still work during the transition"],
        ["Error envelope", '{"error": "&lt;message&gt;", "code": "&lt;CODE&gt;"} on every non-2xx'],
    ], [1.5, 5.4], code_cols=(1,)))
    one(para("Session model: login once with email+password → get a signed token → send it "
             "as the bearer on every call → any 401 means re-login. Logout = delete the "
             "stored token. Passwords are never stored on the device or re-sent."))

    # ---- index -------------------------------------------------------------
    add(h1("Endpoint index"))
    add(table([
        ["Group", "Endpoints"],
        ["Identity", "POST /auth/signup · POST /auth/login · GET /me · POST /auth/change-password"],
        ["Enrollments (voice-gate)", "POST/GET /enrollments · GET/DELETE /enrollments/{id} · "
         "PATCH /enrollments/{id}/status · GET /check · GET /voice-gated · "
         "GET /challenges · GET /challenges/{id}"],
        ["Devices & search", "GET /devices/discover · GET /items/search · GET /automations/discover"],
        ["Favorites", "POST/GET /favorites · DELETE /favorites/{ref} · PATCH /favorites/reorder · "
         "POST /favorites/{id}/fire"],
        ["Scene mappings", "POST/GET /scene-mappings · GET/PATCH/DELETE /scene-mappings/{id}"],
        ["Automations", "GET /automations · POST /automations/trigger"],
        ["Boards (dashboards)", "GET /dashboards · GET /dashboards/config"],
        ["Voice enable (VAPI)", "POST/GET/DELETE /voice-enable"],
        ["Phone mappings (server/VAPI internal)",
         "POST/GET /phone-mappings · DELETE /phone-mappings/{id} · GET /phone-lookup"],
    ], [1.7, 5.2], code_cols=(1,), highlight_rows=(6, 7)))

    # ---- 1 identity --------------------------------------------------------
    add(h1("1 · Identity"))
    one(h2("POST /auth/signup — create account (pending approval)"))
    add(code('curl -s -X POST "$BASE/auth/signup" -H "Content-Type: application/json" \\\n'
             '  -d \'{"email":"new@example.com","password":"min-8-chars","full_name":"New User"}\''))
    one(para("201 pending_approval (admin activates + attaches home before login works) · "
             "409 EMAIL_EXISTS · 400 VALIDATION · 429 RATE_LIMITED (5/15 min/IP). "
             "Login before activation → 403 PENDING_APPROVAL."))

    one(h2("POST /auth/login — get token + identity in one call"))
    add(code('curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \\\n'
             '  -d \'{"email":"scott@example.com","password":"********"}\''))
    add(code('200: { "token": "eyJ...", "token_type": "Bearer", "expires_in": 2592000,\n'
             '       "user_ref": "scott_mobile",  "user_id": "scott_mobile",\n'
             '       "username": "scottmeyers",   "email": "smeyersne@gmail.com",\n'
             '       "full_name": "scott meyers",\n'
             '       "homes": [ { "home_id": "scott_home", "name": "scott_home" } ],\n'
             '       "default_home_id": "scott_home" }'))
    one(para("Cache user_ref + default_home_id — use them everywhere the app previously "
             "hardcoded scott_mobile/scott_home. user_id + email are for feedback reports. "
             "401 wrong credentials · 403 PENDING_APPROVAL · 429 after 5 failures (15-min lock)."))

    one(h2("GET /me — refresh identity on startup"))
    add(code('curl -s "$BASE/me" -H "Authorization: Bearer $TOKEN"'))
    one(para("Same payload minus token fields. 401 → token expired → login screen. Requires "
             "a login token (static keys are rejected — they carry no identity)."))

    one(h2("POST /auth/change-password"))
    add(code('curl -s -X POST "$BASE/auth/change-password" -H "Authorization: Bearer $TOKEN" \\\n'
             '  -H "Content-Type: application/json" \\\n'
             '  -d \'{"current_password":"old-one","new_password":"new-min-8-chars"}\''))
    one(para("204 changed (token stays valid) · 403 wrong current password · 400 policy · "
             "429 lockout. Forgotten password: admin reset only (for now)."))

    # ---- 2 enrollments -----------------------------------------------------
    add(h1("2 · Voice-auth enrollments (gate an automation behind a spoken phrase)"))
    one(h2("POST /enrollments — enable “Voice Protect” on an automation"))
    add(code('curl -s -X POST "$BASE/enrollments" -H "Authorization: Bearer $TOKEN" \\\n'
             '  -H "Content-Type: application/json" -d \'{\n'
             '    "user_ref": "scott_mobile", "home_id": "scott_home",\n'
             '    "automation_name": "Main Lights On",\n'
             '    "ha_service": "script", "ha_entity": "main_lights_on" }\''))
    one(para("ha_service ∈ scene/script/switch/light/lock/cover/media_player/climate/"
             "input_boolean/fan; ha_entity is the suffix only (main_lights_on, not "
             "script.main_lights_on). 201 with id, status ACTIVE, max_attempts 3, cooldown "
             "30s. Idempotent on (user_ref, automation_id). The gate matches on the entity "
             "SUFFIX across domains — an enrollment on main_lights_on gates "
             "script.main_lights_on and automation.main_lights_on alike."))
    one(h2("The rest of the group"))
    add(table([
        ["Call", "What it does"],
        ["GET /enrollments?user_ref=…[&amp;status=…]", "list a user's enrollments → {count, items}"],
        ["GET /enrollments/{id}", "one enrollment's detail"],
        ['PATCH /enrollments/{id}/status {"status":"PAUSED"|"ACTIVE"}', "pause / resume"],
        ["DELETE /enrollments/{id}", "revoke permanently → 204"],
        ["GET /check?user_ref=…&amp;automation_id=…",
         "pre-flight before a VAPI session → exists, status, attempts_remaining, "
         "cooldown_remaining_seconds"],
        ["GET /voice-gated?user_ref=…[&amp;home_id=…]",
         "read-only list of every entity that would answer 409 for this user"],
        ["GET /challenges?user_ref=…&amp;limit=10",
         "audit log of attempts (PASS/FAIL/TIMEOUT + vapi_call_id)"],
        ["GET /challenges/{log_id}", "one attempt's detail"],
    ], [3.1, 3.8], code_cols=(0,)))

    # ---- 3 devices & search ------------------------------------------------
    add(h1("3 · Devices &amp; search"))
    one(h2("GET /devices/discover?home_id=… — physical devices"))
    one(para("One row per HA device: device_id, name, manufacturer, model, area, "
             "primary_entity_id (the controllable surface), is_controllable, all_entities. "
             "Cached 60s server-side. Sensor-only devices have is_controllable:false and "
             "cannot be favorited."))
    one(h2("GET /items/search — the “Add favorite” picker (devices + scenes + scripts + automations)"))
    add(code('curl -s -G "$BASE/items/search" -H "Authorization: Bearer $TOKEN" \\\n'
             '  --data-urlencode "home_id=$HOME" --data-urlencode "q=bat" \\\n'
             '  --data-urlencode "user_ref=$USER"'))
    add(table([
        ["Param", "Req", "Notes"],
        ["home_id", "yes", "which home to search"],
        ["q", "no", "case-insensitive substring on name + entity_id + device_id"],
        ["kind", "no", "comma-filter: device,scene,script,automation,entity"],
        ["user_ref", "no", "populates is_favorited + favorite_id per row"],
        ["limit", "no", "default 200, max 500"],
    ], [1.1, 0.6, 5.2], code_cols=(0,)))
    one(para("GET /automations/discover?home_id=… — voice-ELIGIBLE candidates for the "
             "Voice-Protect enrollment picker (scenes/scripts/devices). Despite the name it "
             "does NOT return automation.* entities — for those use GET /automations (§6)."))

    # ---- 4 favorites -------------------------------------------------------
    add(h1("4 · Favorites (home-screen tiles)"))
    one(h2("POST /favorites — add by device OR entity"))
    add(code('# by device (server resolves entity, domain, friendly_name from HA):\n'
             'curl -s -X POST "$BASE/favorites" -H "Authorization: Bearer $TOKEN" \\\n'
             '  -H "Content-Type: application/json" \\\n'
             '  -d \'{"user_ref":"$USER","home_id":"$HOME","device_id":"6b86cd8c..."}\'\n'
             '\n'
             '# by entity (scenes/scripts/automations; friendly_name recommended):\n'
             '  -d \'{"user_ref":"$USER","home_id":"$HOME",\n'
             '       "entity_id":"scene.good_morning","friendly_name":"Good Morning"}\''))
    one(para("Exactly ONE of device_id / entity_id (both or neither → 400). 201 returns the "
             "favorite incl. its <b>id</b> (UUID — store it). Duplicates → 400. Sensor-only "
             "device → 400 NO_CONTROLLABLE_ENTITY. <b>Locks auto-enroll</b>: lock.* "
             "favorites return voice_auth_required:true + voice_auth_enrollment_id — firing "
             "them always requires the voice challenge."))
    one(para("GET /favorites?user_ref=…&amp;home_id=… — ordered list; each row carries "
             "voice_auth_required for the lock badge."))
    one(h2("DELETE /favorites/{ref} — two forms"))
    add(code('# by favorite id (from create response / list):\n'
             'curl -s -X DELETE -H "Authorization: Bearer $TOKEN" "$BASE/favorites/<uuid>"   # 204\n'
             '\n'
             '# ONE-STEP by device_id or entity_id (no lookup):\n'
             'curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \\\n'
             '  "$BASE/favorites/6b86cd8c...?home_id=$HOME"                                  # 204\n'
             '# user_ref inferred from token; static-key callers add &user_ref=$USER'))
    one(h2("PATCH /favorites/reorder — drag-and-drop"))
    add(code('curl -s -X PATCH "$BASE/favorites/reorder" -H "Authorization: Bearer $TOKEN" \\\n'
             '  -H "Content-Type: application/json" \\\n'
             '  -d \'{"items":[{"id":"<id-1>","position":0},{"id":"<id-2>","position":1}]}\''))
    one(h2("POST /favorites/{id}/fire — one-tap activation"))
    one(para("Server picks the HA action by domain: scene/script/light/switch → turn_on; "
             "automation → trigger; lock → unlock. Body (optional): "
             '{"action":"toggle"|"turn_on"|"turn_off"|…} overrides the default — same '
             "contract as /automations/trigger (§6). 200 {success, latency_ms}. "
             "<b>409 ENROLLMENT_REQUIRED</b> when voice-gated (always for locks) — launch "
             "the VAPI session with the returned automation_id + home_id instead of retrying."))

    # ---- 5 scene mappings --------------------------------------------------
    add(h1("5 · Scene mappings (spoken name → HA webhook)"))
    add(code('curl -s -X POST "$BASE/scene-mappings" -H "Authorization: Bearer $TOKEN" \\\n'
             '  -H "Content-Type: application/json" -d \'{\n'
             '    "home_id": "scott_home", "scene_name": "Movie Night",\n'
             '    "webhook_id": "movie_night_1751404299018" }\''))
    add(table([
        ["Call", "What it does"],
        ["POST /scene-mappings", "create (names normalized to lowercase) → 201"],
        ["GET /scene-mappings?home_id=…", "list a home's scenes"],
        ["GET /scene-mappings/{id}", "detail"],
        ["PATCH /scene-mappings/{id}", "update scene_name / webhook_id / is_active (all optional)"],
        ["DELETE /scene-mappings/{id}", "remove → 204"],
    ], [2.6, 4.3], code_cols=(0,)))

    # ---- 6 automations -----------------------------------------------------
    one(CondPageBreak(2.6 * inch))
    add(h1("6 · Automations — list, run, toggle (NEW in 1.1)"))

    one(h2("GET /automations — every HA automation in a home"))
    one(para("The automations pull for the mobile app: one row per automation.* entity, "
             "sorted by name, read from the home's Home Assistant with the orchestrator's "
             "stored token (the app never holds HA credentials). Served through a ~10s "
             "state cache; a brief HA outage returns the last known list."))
    add(code('curl -s -G "$BASE/automations" -H "Authorization: Bearer $TOKEN" \\\n'
             '  --data-urlencode "user_ref=$USER" --data-urlencode "home_id=$HOME"'))
    add(code('200 (verified on scott_home, 54 automations — abridged):\n'
             '{ "home_id": "scott_home", "count": 54, "gate_check_available": true,\n'
             '  "items": [ {\n'
             '    "entity_id":       "automation.lights_off_at_night",\n'
             '    "automation_id":   "lights_off_at_night",\n'
             '    "ha_automation_id":"1751405011005",\n'
             '    "name":            "Lights Off at Night",\n'
             '    "enabled":         true,  "state": "on",\n'
             '    "last_triggered":  "2026-08-20T04:00:00+00:00",\n'
             '    "mode": "single",  "is_running": false,\n'
             '    "icon": "mdi:robot",\n'
             '    "voice_gated": false, "voice_auth_enrollment_id": null,\n'
             '    "is_favorited": false, "favorite_id": null }, … ] }'))
    add(table([
        ["Param", "Req", "Notes"],
        ["user_ref", "yes", "resolves the per-user bits: voice_gated + is_favorited "
                            "(the automation list itself is home-scoped)"],
        ["home_id", "yes", "which home's HA to read"],
        ["q", "no", "case-insensitive substring on name + entity_id"],
        ["enabled", "no", "true → only enabled; false → only disabled"],
        ["limit", "no", "default 200, max 500"],
    ], [1.1, 0.6, 5.2], code_cols=(0,)))
    add(table([
        ["Field", "Meaning"],
        ["automation_id", "entity suffix — the id the voice-gate / enrollment APIs key on"],
        ["ha_automation_id", "HA's own config id (editor/trace URLs). Null for YAML-defined automations"],
        ["enabled", 'state == "on". Toggle it with action turn_on / turn_off (below)'],
        ["last_triggered / mode / is_running", "straight from HA; is_running = an instance is executing right now"],
        ["voice_gated", "true → running it answers 409; voice_auth_enrollment_id names the enrollment"],
        ["gate_check_available", "top-level; false = enrollment lookup failed, voice_gated flags "
                                 "defaulted to false and a run may still 409"],
    ], [1.9, 5.0], code_cols=(0,)))
    one(para("Errors: 400 VALIDATION (missing params) · 404 NOT_CONFIGURED (unknown home) · "
             "503 HOME_UNREACHABLE (HA down, nothing cached)."))

    one(h2("POST /automations/trigger — run / toggle / turn on / turn off"))
    one(para("Fires POST /api/services/{ha_service}/{action} on the home's HA. "
             f"{mono('action')} is optional — omitted, the server picks the per-domain "
             "default. If an ACTIVE enrollment exists for (user_ref, automation_id) the "
             "call refuses with 409 ENROLLMENT_REQUIRED regardless of action — route to "
             "VAPI. user_ref + automation_id are required for that gate check; omitting "
             "them bypasses it (only for clearly unprotected items)."))
    add(code('# run an automation now (automation domain default = trigger):\n'
             'curl -s -X POST "$BASE/automations/trigger" -H "Authorization: Bearer $TOKEN" \\\n'
             '  -H "Content-Type: application/json" -d \'{\n'
             '    "home_id": "scott_home", "ha_service": "automation",\n'
             '    "ha_entity": "lights_off_at_night",\n'
             '    "user_ref": "scott_mobile", "automation_id": "lights_off_at_night" }\'\n'
             '\n'
             '# toggle a light — what a boards-page tile tap sends:\n'
             '  -d \'{ "home_id": "scott_home", "ha_service": "light",\n'
             '        "ha_entity": "man_land_lamp",\n'
             '        "user_ref": "scott_mobile", "automation_id": "man_land_lamp",\n'
             '        "action": "toggle" }\'\n'
             '\n'
             '# disable / re-enable an automation:\n'
             '        "ha_service": "automation", "ha_entity": "lights_off_at_night",\n'
             '        "action": "turn_off"   # or "turn_on"\n'
             '\n'
             '200: {"success": true, "message": "ok", "status_code": 200, "latency_ms": 214}'))
    add(table([
        ["Domain", "Default action (no `action` sent)", "Toggle supported?"],
        ["automation", "trigger (runs it; turn_on only ENABLES it)", "turn_on/turn_off = enable/disable"],
        ["lock", "unlock (always voice-gated via favorites)", "no — use lock / unlock"],
        ["light, switch, fan, cover, media_player, input_boolean", "turn_on", "yes — send toggle"],
        ["scene, script, everything else", "turn_on", "n/a"],
    ], [1.9, 2.7, 2.3], code_cols=(0,)))
    add(note(
        "<b>Why toggle exists.</b> The default for a light is turn_on, so a bare trigger "
        "call can never turn anything OFF — that was the boards-page “Man Land Lamp won't "
        "turn off” bug. On/off tiles must send "
        f"{mono('action:&nbsp;toggle')} and let HA resolve the flip from its own live "
        "state (immune to a stale UI). Verified in production on light.man_land_lamp: "
        "on → toggle → off → toggle → on. When checking the result, remember reads go "
        "through a ~10s state cache."))

    # ---- 7 boards ----------------------------------------------------------
    add(h1("7 · Boards (HA dashboards as tap-to-control tiles)"))
    one(para("Summarized here for completeness — the full contract (entity_meta, icon "
             "resolution, strategy boards, run book) is in <b>boards_api_guide.pdf</b> v1.3."))
    add(code('# the home\'s dashboards (default "Overview" always first, url_path null):\n'
             'curl -s -G "$BASE/dashboards" -H "Authorization: Bearer $TOKEN" \\\n'
             '  --data-urlencode "user_ref=$USER" --data-urlencode "home_id=$HOME"\n'
             '\n'
             '# one board\'s views + entities + per-entity tile metadata:\n'
             'curl -s -G "$BASE/dashboards/config" -H "Authorization: Bearer $TOKEN" \\\n'
             '  --data-urlencode "user_ref=$USER" --data-urlencode "home_id=$HOME" \\\n'
             '  --data-urlencode "url_path=tablet"        # omit for Overview\n'
             '  # tile UIs add: include_categories=primary&include_hidden=false'))
    add(bullets([
        "Each entity in entity_meta carries name, real HA icon, category, live state, "
        "controllable — no deriving names from entity IDs.",
        "Voice-gated entities are withheld from boards by default (listed in "
        "gated_excluded), so every returned tile is a plain button click: on/off domains "
        "send action toggle (§6), scenes/scripts a bare trigger call.",
        "409 DASHBOARD_NOT_CONFIGURED = the board was never saved in HA (open it there, "
        "edit, save once) · 404 DASHBOARD_NOT_FOUND = unknown url_path.",
    ]))

    # ---- 8 voice enable ----------------------------------------------------
    add(h1("8 · Voice enable (provision a VAPI phone number)"))
    add(code('curl -s -X POST "$BASE/voice-enable" -H "Authorization: Bearer $TOKEN" \\\n'
             '  -H "Content-Type: application/json" \\\n'
             '  -d \'{"user_ref":"scott_mobile","home_id":"scott_home","area_code":"415"}\''))
    one(para("201 {phone_e164, vapi_phone_number_id, is_active}. Idempotent per (user_ref, "
             "home_id) — no double purchase; first call is billable on VAPI. "
             "GET /voice-enable?user_ref=… → {enabled, is_dry_run, mapping}. "
             "DELETE /voice-enable?user_ref=… releases the number → 204."))
    one(para("<font size='8' color='#5a5a6e'>Phone mappings (server/VAPI internal): POST/GET "
             "/phone-mappings, DELETE /phone-mappings/{id}, GET /phone-lookup — used by the "
             "inbound VAPI webhook to resolve caller → (user_ref, home_id). The app "
             "normally doesn't call these.</font>"))

    # ---- 9 VAPI SDK --------------------------------------------------------
    add(h1("9 · VAPI SDK — the spoken challenge"))
    one(para("On 409 ENROLLMENT_REQUIRED (from trigger or favorite-fire), launch the VAPI "
             "SDK (iOS: github.com/VapiAI/ios, Android: /android, Web: /web) with the "
             "<b>VAPI public key</b> (not the API key):"))
    add(code('assistantId: "1a2904b1-61cf-49da-a804-199d8d39fb9f"\n'
             'assistantOverrides.variableValues:\n'
             '  home_id:         "scott_home"\n'
             '  user_ref:        "scott_mobile"\n'
             '  automation_id:   "main_lights_on"\n'
             '  automation_name: "Main Lights On"\n'
             '  initiated_by:    "MOBILE_IOS" | "MOBILE_ANDROID"'))
    one(para("Assistant prompts the security phrase; on pass, HA fires. Subscribe to the "
             "call-end event, then refresh with GET /check."))

    # ---- 10 errors ---------------------------------------------------------
    add(h1("10 · Error reference (all endpoints)"))
    add(table([
        ["HTTP", "Code", "Meaning", "App action"],
        ["400", "VALIDATION", "bad body/params", "fix input, inline error"],
        ["400", "NO_CONTROLLABLE_ENTITY", "sensor-only device", "exclude from picker"],
        ["401", "UNAUTHORIZED", "missing/expired token or bad key", "re-login (token) / config bug (key)"],
        ["403", "FORBIDDEN", "foreign user_ref or home_id with a token", "app bug — use own identity"],
        ["403", "PENDING_APPROVAL", "account awaiting activation", "show “awaiting activation”"],
        ["404", "NOT_FOUND", "unknown id/ref", "varies; delete-by-ref hint included"],
        ["404", "DASHBOARD_NOT_FOUND", "unknown board url_path", "refresh the boards list"],
        ["404", "NOT_CONFIGURED", "unknown home_id", "check home_id from login payload"],
        ["409", "ENROLLMENT_REQUIRED", "voice-gated (always locks)", "launch VAPI session"],
        ["409", "EMAIL_EXISTS", "signup email taken", "offer login"],
        ["409", "DASHBOARD_NOT_CONFIGURED", "board never saved in HA", "tell user to save it once in HA"],
        ["429", "RATE_LIMITED", "login/signup lockout (15 min)", "“try later”, no auto-retry"],
        ["502", "— / VAPI_ERROR", "HA or VAPI upstream failure", "retry once with backoff"],
        ["503", "HOME_UNREACHABLE", "home's HA down or token lapsed", "“home offline, retry later”"],
        ["503", "NOT_CONFIGURED", "feature not wired", "report to backend"],
    ], [0.55, 1.75, 2.4, 2.2], code_cols=(1,)))

    one(para("<font size='8' color='#5a5a6e'>Support: send user_ref, the HTTP "
             "request+response (curl -i), and a vapi_call_id from GET /challenges for voice "
             "flows. Companion docs: boards_api_guide.pdf (boards deep dive + run book) · "
             "identity_api_guide.pdf (login/sign-up deep dive) · mobile_handoff.md "
             "(narrative walkthroughs).</font>"))

    doc = SimpleDocTemplate(
        OUT, pagesize=letter,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        title="Voice Orchestrator — Complete API Reference",
        author="Tetradapt",
    )
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
