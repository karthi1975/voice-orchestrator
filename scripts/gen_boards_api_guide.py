#!/usr/bin/env python3
"""Regenerate docs/boards_api_guide.pdf.

The guide used to be hand-generated, so corrections drifted from the code.
Keeping the source here means the doc is rebuilt, not patched:

    venv/bin/python scripts/gen_boards_api_guide.py

Anything asserted about status codes or payload shapes here should be
traceable to app/controllers/voice_auth_controller.py or a test.
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

VERSION = "1.3"
DATE = "July 30, 2026"
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "boards_api_guide.pdf",
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


def build():
    story = []
    add = story.extend
    one = story.append

    # ---- cover block -------------------------------------------------------
    one(para("Boards API — Mobile Developer Guide", "title"))
    one(para("Everything needed to build the Boards feature: the boards list screen, the "
             "board detail screen, and tapping a tile to control a device.", "subtitle"))
    one(para(f"Version {VERSION} &nbsp;|&nbsp; {DATE} &nbsp;|&nbsp; Tetradapt", "meta"))
    add(note(
        "<b>What changed in 1.3.</b> New §8 is a run book: every call you need, with real output captured from production, including how to prove the 409 path without touching the house. <b>1.2:</b> "
        "<font face='Courier' size='8'>/dashboards/config</font> now returns "
        "<font face='Courier' size='8'>entity_meta</font> — a per-entity record with the "
        "real Home Assistant icon, display name, category, live state and whether the tile is "
        "tappable — so you no longer derive icons or names from the entity ID. Three query "
        "parameters trim the board to what HA itself treats as dashboard tiles, and "
        "<b>voice-gated entities are now withheld from boards</b>, so every tile is a plain "
        "button click with no 409 to design around (§4). The new "
        "<font face='Courier' size='8'>GET /voice-gated</font> answers “which entities "
        "return 409?” in one read-only call instead of firing commands to find out (§5). §4 "
        "also corrects the status code for an unknown "
        "<font face='Courier' size='8'>url_path</font>."))

    # ---- 1. Basics ---------------------------------------------------------
    add(h1("1. Basics"))
    one(h2("Base URL"))
    add(code("https://voiceorchestrator.homeadapt.us/api/v1/voice-auth"))
    one(h2("Authentication"))
    one(para("Every request carries the device API key as a Bearer token. Keys are issued per "
             "device (prefix <font face='Courier' size='8'>sk_ios_</font>). Never embed a key "
             "in the app binary; store it in Keychain/Keystore after provisioning."))
    add(code("Authorization: Bearer sk_ios_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"))
    one(h2("Identity parameters"))
    one(para("All Boards calls identify the caller with two values the app already holds after "
             "login: <font face='Courier' size='8'>user_ref</font> (e.g. "
             "<font face='Courier' size='8'>scott_mobile</font>) and "
             "<font face='Courier' size='8'>home_id</font> (e.g. "
             "<font face='Courier' size='8'>scott_home</font>). Dashboards are home-level in "
             "Home Assistant, so every user of a home sees the same board list; "
             "<font face='Courier' size='8'>user_ref</font> is required for auth and audit "
             "parity."))
    one(h2("Error envelope"))
    one(para("Every non-2xx response has the same shape:"))
    add(code('{ "error": "human readable message", "code": "MACHINE_CODE" }'))

    # ---- 2. Data model -----------------------------------------------------
    add(h1("2. Data model in one paragraph"))
    one(para("A home has <b>dashboards</b> (we call them boards). Each board has <b>views</b> "
             "— the rooms/tabs. Each view has <b>entities</b> — the devices, "
             "identified by Home Assistant entity IDs like "
             "<font face='Courier' size='8'>light.desk_lamp</font>. The part before the dot is "
             "the <b>domain</b>. All of this is configured in the home's Home Assistant; the "
             "API reads it live. The app never stores room structure. Alongside the entity IDs, "
             "<font face='Courier' size='8'>/dashboards/config</font> returns "
             "<font face='Courier' size='8'>entity_meta</font>: everything needed to draw the "
             "tile, resolved server-side against HA."))

    # ---- 3. Boards list ----------------------------------------------------
    add(h1("3. Screen 1 — Boards list (overall view)"))
    one(para("One call populates the whole screen. The default whole-home board "
             "(<font face='Courier' size='8'>url_path = null</font>) is always first."))
    one(h2("Request"))
    add(code("GET /dashboards?user_ref=scott_mobile&home_id=scott_home\n"
             "Authorization: Bearer <API_KEY>"))
    one(h2("Response — 200"))
    add(code("""
{
  "home_id": "scott_home",
  "count": 6,
  "items": [
    { "url_path": null,           "title": "Overview",       "icon": "mdi:view-dashboard",
      "mode": "storage", "show_in_sidebar": true, "require_admin": false, "is_default": true },
    { "url_path": "map",          "title": "Map",            "icon": "mdi:map",
      "mode": "storage", "show_in_sidebar": true, "require_admin": false, "is_default": false },
    { "url_path": "scott-s-view", "title": "Scott's Office", "icon": "mdi:account-plus",
      "mode": "storage", "show_in_sidebar": true, "require_admin": false, "is_default": false }
  ]
}
"""))
    add(table([
        ["Field", "Type", "Meaning"],
        ["url_path", "string?", "Board identifier. <b>null</b> means the default whole-home "
                                "Overview. Pass this to the config endpoint."],
        ["title", "string?", "Display name. Fall back to “Overview” when null."],
        ["icon", "string?", "Material Design icon name (mdi:*). Use your own icon set if null."],
        ["mode", "string", "HA storage mode. Informational only."],
        ["show_in_sidebar", "bool", "Whether HA shows it in its own sidebar. You may use it to "
                                    "hide utility boards."],
        ["require_admin", "bool", "Admin-only board in HA. Hide from non-admin users."],
        ["is_default", "bool", "true only for the whole-home Overview (always the first item)."],
    ], widths=[1.4, 0.8, 4.7], code_cols=(0,)))

    one(h2("Rendering rules (match the prototype)"))
    one(para("One row per item: house icon when <font face='Courier' size='8'>is_default</font> "
             "is true, person icon otherwise. Title on top, "
             "<font face='Courier' size='8'>url_path</font> (or “whole home”) as the "
             "subtitle. Tapping a row opens Screen 2 with that item's "
             "<font face='Courier' size='8'>url_path</font>."))
    one(h2("Errors"))
    add(table([
        ["Status / code", "When", "App behavior"],
        ["400 VALIDATION", "user_ref or home_id missing", "Fix the request; not user-visible."],
        ["404 NOT_CONFIGURED", "home_id unknown to the platform", "Re-run provisioning / sign-in."],
        ["503 HOME_UNREACHABLE", "The house's HA is offline or unreachable",
         "Show the cached list with a “Home unreachable” banner (see §6)."],
        ["502 HA_ERROR", "HA answered with an error", "Show cached list + banner; retry later."],
        ["503 NOT_CONFIGURED", "Server has no dashboard client wired", "Treat as outage."],
    ], widths=[1.6, 2.4, 2.9], code_cols=(0,)))

    # ---- 4. One board ------------------------------------------------------
    one(CondPageBreak(3.2 * inch))
    add(h1("4. Screen 2 — One board (views + tiles)"))
    one(para("One call returns every view (room tab) of the board, the entity IDs each view "
             "shows, and a metadata record per entity. Omit "
             "<font face='Courier' size='8'>url_path</font> for the default Overview board."))
    one(h2("Request"))
    add(code("GET /dashboards/config?user_ref=scott_mobile&home_id=scott_home\n"
             "    &include_categories=primary&include_hidden=false\n"
             "Authorization: Bearer <API_KEY>"))
    one(h2("Query parameters"))
    add(table([
        ["Parameter", "Default", "Meaning"],
        ["url_path", "null", "Which board. Omit for the whole-home Overview."],
        ["include_categories", "all", "Comma list of <b>primary</b>, <b>config</b>, "
                                      "<b>diagnostic</b>. <b>A tile UI wants "
                                      "<font face='Courier' size='8'>primary</font>.</b> An "
                                      "unknown value is a 400, not a silent no-op."],
        ["include_hidden", "true", "Send <font face='Courier' size='8'>false</font> to drop "
                                   "entities the user hid in HA."],
        ["include_gated", "false", "Voice-gated entities are withheld by default so every "
                                   "tile is a plain button click. Send "
                                   "<font face='Courier' size='8'>true</font> only if you are "
                                   "building a screen that handles the voice flow."],
        ["include_config", "false", "Adds the raw Lovelace JSON. Large and frontend-specific; "
                                    "the prototype never needs it."],
    ], widths=[1.5, 0.8, 4.6], code_cols=(0,)))

    one(h2("Response — 200"))
    add(code("""
{
  "home_id": "scott_home",
  "url_path": null,
  "title": null,
  "strategy": "original-states",
  "view_count": 16,
  "views": [
    { "title": "Deck", "path": "deck", "icon": null, "entity_count": 1,
      "entities": ["switch.deck_light"] },
    { "title": "Den",  "path": "den",  "icon": null, "entity_count": 4,
      "entities": ["light.den_lamp", "media_player.den_tv", "..."] }
  ],
  "entities": ["switch.deck_light", "light.den_lamp", "..."],
  "entity_count": 108,
  "entity_meta_available": true,
  "gated_excluded": ["lock.yale_yrd226_tsdb"],
  "gate_check_available": true,
  "entity_meta": {
    "switch.deck_light": {
      "name": "Deck light",        "domain": "switch",
      "icon": "mdi:toggle-switch", "icon_source": "domain",
      "device_class": null,        "unit_of_measurement": null,
      "entity_category": null,     "hidden": false,
      "state": "off",              "controllable": true,
      "voice_gated": false,        "voice_auth_enrollment_id": null
    },
    "sensor.deck_light_signal_level": {
      "name": "Deck light Signal level", "domain": "sensor",
      "icon": "mdi:signal",              "icon_source": "translation",
      "device_class": null,              "unit_of_measurement": null,
      "entity_category": "diagnostic",   "hidden": false,
      "state": "2",                      "controllable": false,
      "voice_gated": false,              "voice_auth_enrollment_id": null
    }
  }
}
"""))
    add(table([
        ["Field", "Type", "Meaning"],
        ["title", "string?", "Board display name for the header."],
        ["strategy", "string?", "Set (e.g. “original-states”) when the board is "
                                "auto-generated by HA. The server already expands it into one "
                                "view per area — render exactly like a normal board."],
        ["views[].title", "string?", "Tab label. Fall back to path."],
        ["views[].path", "string?", "Stable view identifier. Persist it to reopen the same tab."],
        ["views[].entity_count", "int", "Post-filter count. Show in the tab chip, e.g. "
                                        "“Den · 4”."],
        ["views[].entities", "string[]", "HA entity IDs, in display order. One tile each."],
        ["entities", "string[]", "All unique entity IDs across views (deduplicated)."],
        ["entity_meta", "object", "entity_id → tile record. Keys match "
                                  "<font face='Courier' size='8'>entities</font> exactly."],
        ["entity_meta_available", "bool", "<b>false</b> means HA served the board but not the "
                                          "metadata — <font face='Courier' size='8'>"
                                          "entity_meta</font> is empty <b>and the filters were "
                                          "not applied</b>. Fall back to the domain table below."],
        ["gated_excluded", "string[]", "Entities held back because they need voice auth. "
                                       "Usually empty. They are not tiles — reach them "
                                       "through Favorites."],
        ["gate_check_available", "bool", "<b>false</b> means the enrollment lookup failed, so "
                                         "gated entities could not be held back and a tap may "
                                         "still 409. Keep the handler for this case."],
    ], widths=[1.5, 0.9, 4.5], code_cols=(0,)))

    one(h2("A board tile is always a button click"))
    one(para("Voice-gated entities are withheld from a board by default, so every tile "
             "<font face='Courier' size='8'>/dashboards/config</font> returns can be tapped "
             "and will fire. There is no voice badge to render on this screen and no 409 to "
             "design around: tap → §5 → 200. Anything held back is named in "
             "<font face='Courier' size='8'>gated_excluded</font> so the screen can say “1 "
             "device needs voice authentication” if it wants to, and it stays reachable "
             "through Favorites, which runs the voice flow."))
    one(para("This does not weaken the gate — a withheld device still requires the spoken "
             "challenge everywhere it IS offered. On the reference home exactly one entity is "
             "affected, the front-door lock, which is why the Entry view shows one tile rather "
             "than two. Keep your 409 handler for the "
             "<font face='Courier' size='8'>gate_check_available: false</font> case and for "
             "someone enrolling a device between your fetch and the tap."))

    one(h2("The entity_meta record"))
    add(table([
        ["Field", "Meaning"],
        ["name", "Display name, straight from HA. Use it verbatim — do not title-case the "
                 "entity ID."],
        ["icon", "Material Design icon name, always populated. Resolved against HA itself "
                 "(see below)."],
        ["icon_source", "Which rung of the chain produced the icon: state, registry, "
                        "integration, translation, device_class, unit, domain. Diagnostic "
                        "only — do not branch on it."],
        ["device_class", "HA device class when there is one (temperature, door, tv…). "
                         "Useful for choosing a value format."],
        ["unit_of_measurement", "Unit to append when showing state, e.g. “°F”."],
        ["entity_category", "null (a primary dashboard entity), <b>config</b>, or "
                            "<b>diagnostic</b>."],
        ["hidden", "true when the user hid the entity in HA."],
        ["state", "Live state at request time. Server caches HA state for 10 seconds."],
        ["controllable", "true when tapping can fire the entity through §5. false → "
                         "render read-only."],
        ["voice_gated", "Always <b>false</b> on a default board — gated entities are "
                        "withheld, so this only ever reads true when you asked for "
                        "<font face='Courier' size='8'>include_gated=true</font>. When it is "
                        "true, a tap WILL return 409; route it to the VAPI session (§5)."],
        ["voice_auth_enrollment_id", "The enrollment doing the gating, or null. Useful for "
                                     "logs and for “manage voice authentication”."],
    ], widths=[1.5, 5.4], code_cols=(0,)))

    one(h2("Why the icon cannot come from the entity ID"))
    one(para("Home Assistant stopped putting icons on entities. Since HA 2024.2 an integration "
             "declares them in an icon-translation file keyed by an internal translation key, "
             "which the HA REST API does not expose at all. On a real home, 62% of the entities "
             "on the default board carry neither an icon nor a device class over REST — "
             "<font face='Courier' size='8'>sensor.deck_light_signal_level</font> is one of "
             "them, yet HA shows <font face='Courier' size='8'>mdi:signal</font> for it. The "
             "server now reads the entity registry and the icon translations over HA's "
             "WebSocket API and resolves each entity through the chain below, so a tile matches "
             "what the user sees in Home Assistant. Every entity gets an icon; there is no null "
             "case to handle."))
    add(table([
        ["#", "Source", "What it is"],
        ["1", "state", "The entity's live <font face='Courier' size='8'>icon</font> attribute."],
        ["2", "registry", "An icon the user set by hand in HA."],
        ["3", "integration", "A static icon shipped by the integration."],
        ["4", "translation", "The icons.json entry — the modern path, and the largest "
                             "single source."],
        ["5", "device_class", "Our map, e.g. temperature → mdi:thermometer."],
        ["6", "unit", "Our map for unit-only sensors, e.g. min → mdi:timer-outline."],
        ["7", "domain", "Our map, e.g. light → mdi:lightbulb."],
    ], widths=[0.3, 1.2, 5.4], code_cols=(1,)))

    one(h2("Why include_categories=primary matters"))
    one(para("HA's auto-generated boards list <i>every</i> entity a device exposes, most of "
             "which HA's own UI keeps behind the device page rather than on a dashboard. On the "
             "reference home the default board references 204 entities; 61 are "
             "<b>config</b> and 32 are <b>diagnostic</b>. The Deck view is nine entities, of "
             "which exactly one — <font face='Courier' size='8'>switch.deck_light</font> "
             "— is a thing a person would tap. The rest are the plug's LED toggle, "
             "auto-off timer, signal level and cloud-connection status."))
    one(para("Sending <font face='Courier' size='8'>include_categories=primary&amp;"
             "include_hidden=false</font> takes that board from 204 tiles to 109. Note this is "
             "HA's own classification, not our opinion: some appliance integrations genuinely "
             "mark dozens of sensors as primary, and those areas stay busy."))

    one(h2("Fallback tile rules (only when entity_meta_available is false)"))
    add(table([
        ["Domain", "Tile", "Tap"],
        ["light, switch, fan, cover, lock, climate, media_player, scene, script, automation, "
         "vacuum, button, input_boolean", "Normal (bright)", "Fires the device (§5)."],
        ["sensor, binary_sensor, number, select, camera, device_tracker, update, event, sun, "
         "zone, person, weather", "Dimmed, read-only", "Not tappable."],
    ], widths=[4.0, 1.5, 1.4], code_cols=(0,)))

    one(h2("Errors — same as Screen 1, plus:"))
    add(table([
        ["Status / code", "When", "App behavior"],
        ["409 DASHBOARD_NOT_CONFIGURED",
         "Board has no stored config — either it is still auto-generated, <b>or the "
         "url_path does not exist</b>. HA reports both the same way, so this is the code you "
         "get for a deleted board too.",
         "Re-fetch <font face='Courier' size='8'>/dashboards</font> first. If the url_path is "
         "gone, treat it as deleted and go back to the list. If it is still listed, show "
         "“This board has no views yet — open it in Home Assistant, edit and save "
         "once.”"],
        ["404 DASHBOARD_NOT_FOUND", "Reserved. HA does not currently produce it — do not "
                                    "build the deleted-board path on this code.", "—"],
        ["400 VALIDATION", "Unknown include_categories value.", "Fix the request."],
    ], widths=[1.9, 2.5, 2.5], code_cols=(0,), highlight_rows=(1, 2)))

    # ---- 5. Tap a tile -----------------------------------------------------
    one(CondPageBreak(3.2 * inch))
    add(h1("5. Action — Tap a tile"))
    one(para("Tapping fires the entity's default action. Send the entity ID split into domain "
             "and suffix — <font face='Courier' size='8'>ha_entity</font> must NOT contain "
             "the dot."))
    one(h2("Request"))
    add(code("""
POST /automations/trigger
Authorization: Bearer <API_KEY>
Content-Type: application/json

{
    "home_id":       "scott_home",
    "ha_service":    "light",       // domain (before the dot)
    "ha_entity":     "desk_lamp",   // suffix only (after the dot)
    "user_ref":      "scott_mobile",
    "automation_id": "desk_lamp"    // same as ha_entity; enables the voice-gate check
}
"""))
    one(h2("Response — 200"))
    add(code('{ "success": true, "message": "toggled light.desk_lamp",\n'
             '  "status_code": 200, "latency_ms": 184 }'))

    one(h2("Response — 409, the voice gate"))
    one(para("409 is not a failure. It means this entity is voice-gated for this user: the "
             "action is real, but it has to be authorized by speaking to the assistant. Mark "
             "the tile as gated and launch the VAPI session; never retry the trigger."))
    add(code("""
{ "error": "this automation requires voice authentication",
  "code":  "ENROLLMENT_REQUIRED",
  "enrollment_id": "21e86f28-0037-40a9-94fe-cbdfa9fc6d07" }
"""))
    add(note(
        "<b>The two 409 bodies are not the same.</b> "
        "<font face='Courier' size='8'>POST /automations/trigger</font> returns only "
        "<font face='Courier' size='8'>error</font>, <font face='Courier' size='8'>code</font> "
        "and <font face='Courier' size='8'>enrollment_id</font>. "
        "<font face='Courier' size='8'>POST /favorites/{id}/fire</font> additionally returns "
        "<font face='Courier' size='8'>automation_id</font>, "
        "<font face='Courier' size='8'>automation_name</font> and "
        "<font face='Courier' size='8'>home_id</font>. The VAPI session needs "
        "<font face='Courier' size='8'>automation_id</font> and "
        "<font face='Courier' size='8'>home_id</font> — from the trigger path you already "
        "hold both (you just sent them), so use your own values rather than reading them off "
        "the response."))

    one(h2("Never send a command to find out — ask"))
    one(para("<font face='Courier' size='8'>GET /voice-gated</font> lists every entity that "
             "will answer 409 for a user. It is read-only, it fires nothing, and it runs the "
             "same lookup the fire path runs, so the two cannot disagree. Anything it lists "
             "will 409; anything it does not list will not."))
    add(code("""
GET /voice-gated?user_ref=scott_mobile&home_id=scott_home
Authorization: Bearer <API_KEY>

{
  "user_ref": "scott_mobile", "home_id": "scott_home", "count": 2,
  "items": [
    { "entity_id": "lock.yale_yrd226_tsdb", "automation_id": "yale_yrd226_tsdb",
      "name": "Yale Lock",      "domain": "lock",  "icon": "mdi:lock",
      "home_id": "scott_home",  "enrollment_id": "9c520ce7-bdb5-...",
      "challenge_type": "STEP_UP", "created_by": "favorite_auto_lock" },
    { "entity_id": "scene.decorations_on", "automation_id": "decorations_on",
      "name": "Decorations On", "domain": "scene", "icon": "mdi:string-lights",
      "home_id": "scott_home",  "enrollment_id": "21e86f28-0037-...",
      "challenge_type": "VERIFICATION", "created_by": "seed" }
  ]
}
"""))
    add(table([
        ["Field", "Meaning"],
        ["entity_id", "The entity that 409s. Compare against your tile's entity ID."],
        ["automation_id", "The suffix the gate actually matches on. Any entity ending in "
                          "<font face='Courier' size='8'>.&lt;automation_id&gt;</font> is "
                          "gated, whatever its domain."],
        ["challenge_type", "STEP_UP for locks, VERIFICATION otherwise. Informational."],
        ["enrollment_id", "Pass to <font face='Courier' size='8'>/enrollments/{id}/status</font> "
                          "to pause, or show in a “manage voice authentication” screen."],
        ["home_id", "Which home the enrollment belongs to. Omit the query param to see all "
                    "of the user's homes."],
    ], widths=[1.4, 5.5], code_cols=(0,)))
    one(para("Only ACTIVE enrollments appear. A paused one does not gate and is not listed, "
             "so the list is always exactly the set that 409s right now."))
    add(note(
        "<b>Gating is per user, not per home.</b> Two people in the same house get different "
        "answers, which is why <font face='Courier' size='8'>user_ref</font> is required here "
        "and matters on <font face='Courier' size='8'>/dashboards/config</font>. Always send "
        "the signed-in user's <font face='Courier' size='8'>user_ref</font>."))
    one(para("Where a gated entity can still appear, the row says so, so you never have to "
             "cross-reference by hand:"))
    add(table([
        ["Surface", "Gated entities", "Field"],
        ["GET /dashboards/config", "Withheld by default — every tile is a button click",
         "<font face='Courier' size='8'>gated_excluded</font> lists what was held back"],
        ["GET /items/search", "Included", "<font face='Courier' size='8'>voice_gated</font> "
                                          "on each row"],
        ["GET /favorites", "Included — this is where a lock lives",
         "<font face='Courier' size='8'>voice_auth_required</font> on each row"],
    ], widths=[1.7, 2.4, 2.8], code_cols=(0,)))

    one(h2("Which entities return 409"))
    one(para("A 409 comes from an <b>active enrollment</b> on "
             "<font face='Courier' size='8'>(user_ref, automation_id)</font>. Enrollments are "
             "created two ways: automatically for every "
             "<font face='Courier' size='8'>lock.*</font> entity the moment it is favorited "
             "(locks can never be fired without the spoken challenge), and explicitly via "
             "<font face='Courier' size='8'>POST /enrollments</font> for anything else. "
             "Nothing else gates. If you have not enrolled it and it is not a lock, it will "
             "not 409."))
    add(table([
        ["Rule", "Consequence for the app"],
        ["The gate key is the entity <b>suffix</b>, not the full entity ID.",
         "An enrollment on <font face='Courier' size='8'>decorations_on</font> gates both "
         "<font face='Courier' size='8'>scene.decorations_on</font> and "
         "<font face='Courier' size='8'>script.decorations_on</font>. Do not assume the domain "
         "narrows it."],
        ["The gate only runs when <b>both</b> user_ref and automation_id are sent.",
         "Always send them. Omitting either fires the action ungated and skips the audit trail."],
        ["Locks auto-enroll on favorite.",
         "Favoriting a <font face='Courier' size='8'>lock.*</font> entity always produces a "
         "gated <i>favorite</i> — and the lock stops being a board tile. The VAPI "
         "hand-off belongs on the Favorites screen, not the board."],
        ["Enrollments can be paused.",
         "A PAUSED enrollment does not gate and is absent from "
         "<font face='Courier' size='8'>/voice-gated</font>, so the entity becomes a normal "
         "tile again. Do not cache “this is gated” across sessions."],
    ], widths=[2.6, 4.3]))

    one(h2("Testing the 409 without touching the house"))
    one(para("You should not need to. Read "
             "<font face='Courier' size='8'>GET /voice-gated</font> to know what is gated, and "
             "a board never hands you a gated tile in the first place. To exercise the 409 "
             "handler itself, the gate is evaluated before the command is dispatched and does "
             "not read "
             "<font face='Courier' size='8'>home_id</font>, so sending a home that does not "
             "exist proves the 409 path while making it impossible for anything to reach a real "
             "device. A gated automation_id returns 409; an ungated one falls through to "
             "dispatch and fails with 502, which is how you know the 409 came from the gate."))
    add(code("""
# 409 ENROLLMENT_REQUIRED — nothing is dispatched
curl -s -X POST "$BASE/automations/trigger" -H "Authorization: Bearer $KEY" \\
  -H "Content-Type: application/json" -d '{
    "home_id": "__no_such_home__", "ha_service": "scene", "ha_entity": "decorations_on",
    "user_ref": "scott_mobile", "automation_id": "decorations_on" }'

# control: an ungated automation_id reaches dispatch and 502s on the fake home
curl -s -X POST "$BASE/automations/trigger" -H "Authorization: Bearer $KEY" \\
  -H "Content-Type: application/json" -d '{
    "home_id": "__no_such_home__", "ha_service": "scene", "ha_entity": "good_night",
    "user_ref": "scott_mobile", "automation_id": "good_night" }'
"""))
    one(para("To see the richer favorites 409 body, favorite the home's lock "
             "(<font face='Courier' size='8'>POST /favorites</font> with "
             "<font face='Courier' size='8'>{\"entity_id\": \"lock.&lt;suffix&gt;\"}</font>), "
             "then <font face='Courier' size='8'>POST /favorites/{id}/fire</font>. That also "
             "refuses before dispatch, so the lock never actuates."))
    one(para("Related read-only calls: "
             "<font face='Courier' size='8'>GET /voice-gated?user_ref=&lt;user&gt;</font> for "
             "the entity list (start here), "
             "<font face='Courier' size='8'>GET /enrollments?user_ref=&lt;user&gt;</font> for "
             "the raw enrollment rows including paused ones, and "
             "<font face='Courier' size='8'>GET /check?user_ref=&lt;user&gt;"
             "&amp;automation_id=&lt;suffix&gt;</font> for one entity plus its cooldown and "
             "attempts-remaining."))

    one(h2("Errors"))
    add(table([
        ["Status / code", "When", "App behavior"],
        ["400 VALIDATION", "Missing field, or ha_entity contains a dot", "Fix the request."],
        ["409 ENROLLMENT_REQUIRED", "Entity is voice-gated for this user",
         "Show “needs voice authentication”; launch the VAPI session."],
        ["502 (success: false)", "HA rejected the command or the device is unreachable",
         "Toast “Could not reach the device”; keep the tile enabled."],
    ], widths=[1.9, 2.4, 2.6], code_cols=(0,)))

    # ---- 6. Caching --------------------------------------------------------
    add(h1("6. Caching and offline behavior"))
    one(para("The server caches HA reads and serves stale data through brief outages, so the "
             "app does not need aggressive polling. Dashboard configs are cached 30 seconds, "
             "entity state 10 seconds, and the entity registry and icon translations 10 minutes "
             "— the last two only change when someone edits the home's HA. The app adds "
             "one layer:"))
    add(bullets([
        "Cache the last good response of <font face='Courier' size='8'>/dashboards</font> and "
        "of each <font face='Courier' size='8'>/dashboards/config</font> (key: url_path), on disk.",
        "On <font face='Courier' size='8'>HOME_UNREACHABLE</font> (or any network error): render "
        "the cached copy, dim the grid, disable taps, and show a banner “Home unreachable "
        "— showing last known view.”",
        "On <font face='Courier' size='8'>entity_meta_available: false</font>: render the board, "
        "fall back to the domain icon table, and do <i>not</i> assume the category filter was "
        "applied.",
        "With no cache: show an empty state with a retry.",
        "Persist the last opened (board, view). On launch, open it directly and skip the boards "
        "list — the app opens on your own board.",
    ]))

    # ---- 7. Build order ----------------------------------------------------
    add(h1("7. Build order — step by step"))
    add(table([
        ["Step", "Build", "Done when"],
        ["1", "HTTP client: base URL, Bearer header, error-envelope parsing into {error, code}",
         "Any endpoint returns parsed JSON or a typed error."],
        ["2", "Boards list screen from GET /dashboards",
         "Rows match the home's HA sidebar; Overview first."],
        ["3", "Board screen from GET /dashboards/config with "
              "<font face='Courier' size='8'>include_categories=primary&amp;include_hidden=false</font>: "
              "tabs from views[], tile grid from entities",
         "Tabs show “title · count”; the Deck tab shows one tile, not nine."],
        ["4", "Tiles rendered from entity_meta: icon, name, state; controllable=false renders "
              "read-only. Keep the domain table as the entity_meta_available=false fallback.",
         "Signal-level and cloud-connection tiles are gone; the ones left look like HA."],
        ["5", "Tile tap → POST /automations/trigger with split entity ID",
         "A real light turns on; success toast shows."],
        ["6", "Nothing to build on the board — gated entities are not tiles. Keep a 409 "
              "handler as the backstop, and use "
              "<font face='Courier' size='8'>GET /voice-gated</font> if a screen needs to "
              "name the voice-protected devices.",
         "Every board tile fires. The 409 path is verified with the fake-home probe in §5, "
         "not by tapping real devices."],
        ["7", "Disk cache + HOME_UNREACHABLE stale mode",
         "Airplane-mode HA still shows last known screens."],
        ["8", "Persist last (board, view); open on it at launch",
         "Relaunch lands on the user's own room."],
    ], widths=[0.4, 3.3, 3.2]))

    one(para("Live tile state now ships in "
             "<font face='Courier' size='8'>entity_meta[].state</font>, so the tile model "
             "should carry it from the start. Still out of scope for this milestone: per-user "
             "board memory synced across devices."))

    # ---- 8. Run book -------------------------------------------------------
    one(CondPageBreak(3.2 * inch))
    add(h1("8. Run book — verified curl calls"))
    one(para("Every call in this section was run against production on 30 July 2026 and the "
             "output below is copied verbatim, not illustrative. Paste the exports first; "
             "everything after reuses them."))
    add(code("""
export KEY=sk_ios_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX      # your device key
export BASE=https://voiceorchestrator.homeadapt.us/api/v1/voice-auth
export U=scott_mobile
export H=scott_home
export Q="user_ref=$U&home_id=$H&include_categories=primary&include_hidden=false"
"""))
    add(table([
        ["#", "What it answers", "Expect", "Touches the house?"],
        ["1", "Which entities return 409", "200", "no"],
        ["2", "The board call for the tile screen", "200", "no"],
        ["3", "One view's tiles", "200", "no"],
        ["4", "What icon do I use for this entity", "200", "no"],
        ["5", "Search row shape", "200", "no"],
        ["6", "Favorites (where a lock appears)", "200", "no"],
        ["7", "Prove the 409 path", "<b>409</b>", "no — fake home_id"],
        ["8", "Control for #7", "<b>502</b>", "no — fake home_id"],
        ["9", "Fire a device for real", "200", "<b>YES — toggles a light</b>"],
    ], widths=[0.3, 3.1, 0.7, 2.8]))

    one(h2("1 · Which entities return 409"))
    add(code("""
curl -s "$BASE/voice-gated?user_ref=$U&home_id=$H" -H "Authorization: Bearer $KEY" | jq

{ "count": 5, "home_id": "scott_home", "user_ref": "scott_mobile", "items": [
    { "entity_id": "lock.yale_yrd226_tsdb",  "automation_id": "yale_yrd226_tsdb",
      "name": "Yale Lock",      "domain": "lock",  "icon": "mdi:lock",
      "challenge_type": "STEP_UP",      "created_by": "favorite_auto_lock",
      "enrollment_id": "9c520ce7-bdb5-4143-8e59-091b0626bdf5", "home_id": "scott_home" },
    { "entity_id": "scene.decorations_on",   "automation_id": "decorations_on",
      "name": "Decorations On", "domain": "scene", "icon": "mdi:string-lights",
      "challenge_type": "VERIFICATION", "created_by": "seed",
      "enrollment_id": "21e86f28-0037-40a9-94fe-cbdfa9fc6d07", "home_id": "scott_home" }
    ...  scene.decorations_off, script.main_lights_off, script.main_lights_on
] }
"""))

    one(h2("2 · The board call — use this for the tile screen"))
    add(code("""
curl -s "$BASE/dashboards/config?$Q" -H "Authorization: Bearer $KEY" \\
  | jq '{tiles:.entity_count, excluded:.gated_excluded}'

{ "tiles": 108, "excluded": [ "lock.yale_yrd226_tsdb" ] }
"""))
    one(para("Without the two parameters that board is 203 entities. The lock is withheld, so "
             "every one of the 108 tiles can be tapped and will fire."))

    one(h2("3 · One view's tiles"))
    add(code("""
curl -s "$BASE/dashboards/config?$Q" -H "Authorization: Bearer $KEY" \\
  | jq '.views[] | select(.title=="Deck")'

{ "title": "Deck", "path": "deck", "icon": null,
  "entity_count": 1, "entities": [ "switch.deck_light" ] }
"""))
    one(para("One tile, not the nine HA's auto-generated board lists for that plug."))

    one(h2("4 · What icon do I use for this entity"))
    add(code("""
curl -s "$BASE/dashboards/config?user_ref=$U&home_id=$H" \\
  -H "Authorization: Bearer $KEY" | jq '.entity_meta["sensor.deck_light_signal_level"]'

{ "name": "Deck light Signal level", "domain": "sensor",
  "icon": "mdi:signal",            "icon_source": "translation",
  "device_class": null,            "unit_of_measurement": null,
  "entity_category": "diagnostic", "hidden": false,
  "state": "2",                    "controllable": false,
  "voice_gated": false,            "voice_auth_enrollment_id": null }
"""))
    one(para("Note this call omits the filters on purpose — that entity is "
             "<font face='Courier' size='8'>diagnostic</font>, so the board in #2 does not "
             "return it. Its icon exists only in HA's icon translations, which is why it "
             "looks blank over REST."))

    one(h2("5 · Search row shape"))
    add(code("""
curl -s "$BASE/items/search?home_id=$H&user_ref=$U&limit=500" \\
  -H "Authorization: Bearer $KEY" | jq '.items[0]'

{ "entity_id": "media_player.lg_webos_tv_ut7000pua", "kind": "device",
  "name": "[LG] webOS TV UT7000PUA", "domain": "media_player",
  "icon": "mdi:television",  "state": "unavailable",  "voice_gated": false,
  "manufacturer": "LGE", "model": "43UT7000PUA.BUSFLJM", "area": null,
  "device_id": "b4a39663fb71d1d04c9ea9491c35cf6e",
  "is_favorited": false, "favorite_id": null }
"""))

    one(h2("6 · Favorites"))
    add(code("""
curl -s "$BASE/favorites?user_ref=$U&home_id=$H" -H "Authorization: Bearer $KEY" | jq

{ "count": 2, "items": [
    { "entity_id": "switch.bat_sign",     "friendly_name": "Bat Sign",
      "domain": "switch", "kind": "device", "position": 0,
      "voice_auth_required": false, "id": "de013682-b4c8-47fa-b409-34f16202955e" },
    { "entity_id": "light.man_land_lamp", "friendly_name": "Man Land Lamp",
      "domain": "light",  "kind": "device", "position": 1,
      "voice_auth_required": false, "id": "8f9e2b24-4be3-44cb-a248-572924ea04f2" }
] }
"""))

    one(h2("7 · Prove the 409 path — without touching the house"))
    one(para("The gate is evaluated before the command is dispatched and never reads "
             "<font face='Courier' size='8'>home_id</font>, so a home that does not exist "
             "proves the 409 while making it impossible for anything to reach a real device."))
    add(code("""
curl -s -X POST "$BASE/automations/trigger" \\
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \\
  -d '{"home_id":"__no_such_home__","ha_service":"lock","ha_entity":"yale_yrd226_tsdb",
       "user_ref":"scott_mobile","automation_id":"yale_yrd226_tsdb"}' \\
  -w "\\nHTTP %{http_code}\\n"

{"code":"ENROLLMENT_REQUIRED",
 "enrollment_id":"9c520ce7-bdb5-4143-8e59-091b0626bdf5",
 "error":"this automation requires voice authentication"}

HTTP 409
"""))

    one(h2("8 · Control — the same call on an ungated entity"))
    add(code("""
curl -s -X POST "$BASE/automations/trigger" \\
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \\
  -d '{"home_id":"__no_such_home__","ha_service":"scene","ha_entity":"good_night",
       "user_ref":"scott_mobile","automation_id":"good_night"}' \\
  -w "\\nHTTP %{http_code}\\n"

error code: 502

HTTP 502
"""))
    one(para("502, not 409 — the gate correctly declined to fire and the call fell through to "
             "dispatch against the nonexistent home. That is what proves the 409 in #7 came "
             "from the voice gate and not from the bad "
             "<font face='Courier' size='8'>home_id</font>. Swap in the real "
             "<font face='Courier' size='8'>home_id</font> when you want the live path; the "
             "gate result is identical because it does not read that field."))

    one(h2("9 · Fire a device for real"))
    add(note("<b>This one controls the house.</b> It toggles a light, not the lock. Run it "
             "when you are ready to see a tile tap work end to end."))
    add(code("""
curl -s -X POST "$BASE/automations/trigger" \\
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \\
  -d '{"home_id":"scott_home","ha_service":"switch","ha_entity":"deck_light",
       "user_ref":"scott_mobile","automation_id":"deck_light"}'

{"success":true,"message":"ok","status_code":200,"latency_ms":309}
"""))
    one(para("That is exactly what a tile tap sends: the entity ID split on the first dot into "
             "<font face='Courier' size='8'>ha_service</font> and "
             "<font face='Courier' size='8'>ha_entity</font>, with "
             "<font face='Courier' size='8'>user_ref</font> and "
             "<font face='Courier' size='8'>automation_id</font> so the gate can be enforced."))

    doc = SimpleDocTemplate(
        OUT, pagesize=letter,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title="Boards API — Mobile Developer Guide",
        author="Tetradapt",
    )
    doc.build(story)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    build()
