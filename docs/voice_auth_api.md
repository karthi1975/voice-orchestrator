# Voice Authentication API — Mobile Integration Guide

Audience: iOS / Android engineers integrating voice-gated Home Assistant
actions into the SmartHome app.

Base URL (production): `https://voiceorchestrator.homeadapt.us`
Base path:              `/api/v1/voice-auth`
Content-Type:           `application/json`
Auth:                   `Authorization: Bearer <app-issued-token>` (enforcement
                        is planned — today the orchestrator trusts the caller.
                        Keep sending the header; it will start being validated).

---

## Overview — The flow your app implements

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Setup (one-time per automation the user wants to protect)              │
└──────────────────────────────────────────────────────────────────────────┘
  user toggles "require voice auth" on an HA automation in the app
          │
          │  POST /enrollments
          ▼
  orchestrator stores enrollment
          │
          │  201 Created
          ▼
  app shows toggle as ON

┌──────────────────────────────────────────────────────────────────────────┐
│  Every time the user triggers a protected automation                     │
└──────────────────────────────────────────────────────────────────────────┘
  user taps a protected scene in the app
          │
          │  (optional) GET /check  → confirm enrollment + cooldown state
          │
          ▼
  app starts VAPI voice session with the VAPI iOS/Android SDK,
  passing assistantOverrides.variableValues = {
      home_id, user_ref, automation_id, automation_name
  }
          │
          ▼
  VAPI assistant speaks: "To confirm <Automation>, please say: <phrase>"
          │
          │  (VAPI → orchestrator /vapi/auth/request)
          │
  user repeats phrase → VAPI → orchestrator /vapi/auth/verify
          │
          ▼
  orchestrator dispatches Home Assistant scene.turn_on / script.turn_on / ...
  VAPI speaks "<Automation> activated." and ends the call
          │
          │  (optional) GET /challenges?user_ref=…&limit=1
          │     → latest log row with result=SUCCESS and confirmed HA fire
          ▼
  app shows success toast
```

Critical: **your app never issues voice phrases or fires HA itself.** Your app's
jobs are (a) tell the orchestrator "this user+automation needs voice auth", and
(b) start the VAPI session and let VAPI talk to the user.

---

## 1. `POST /enrollments` — enroll an automation

User toggles "require voice auth" on a scene/script/light/etc.

### Request
```json
{
  "user_ref": "scott_mobile",
  "home_id":  "scott_home",
  "automation_name": "Decorations On",
  "ha_service": "scene",
  "ha_entity":  "decorations_on",
  "automation_id":    "decorations_on",   // optional — auto-slugged from name
  "challenge_type":   "VERIFICATION",     // VERIFICATION | STEP_UP | CONFIRMATION
  "max_attempts":     3,
  "cooldown_seconds": 30,
  "metadata":         { "locale": "en-US", "channel": "mobile" },
  "created_by":       "ios-app"
}
```

### Response — 201 Created
```json
{
  "id": "21e86f28-0037-40a9-94fe-cbdfa9fc6d07",
  "user_ref": "scott_mobile",
  "home_id":  "scott_home",
  "automation_id":   "decorations_on",
  "automation_name": "Decorations On",
  "ha_service": "scene",
  "ha_entity":  "decorations_on",
  "status": "ACTIVE",
  "challenge_type": "VERIFICATION",
  "max_attempts": 3,
  "cooldown_seconds": 30,
  "metadata": null,
  "created_at": "2026-04-22T23:41:52.678619",
  "updated_at": null,
  "created_by": "seed"
}
```

### Error envelope — 400 Validation
```json
{ "error": "ha_service must be one of [...]", "code": "VALIDATION" }
```

### Notes
- Idempotent on `(user_ref, automation_id)`. Calling twice with the same pair
  returns the existing row, **not an error**.
- `automation_id` is slug-normalized (lowercase, spaces → `_`, `-` → `_`).
- `ha_service` must be one of: `scene, script, switch, light, lock, cover,
  media_player, climate, input_boolean, fan`.
- `ha_entity` is the entity suffix only — pass `decorations_on`, not
  `scene.decorations_on`.

### curl
```bash
curl -X POST https://voiceorchestrator.homeadapt.us/api/v1/voice-auth/enrollments \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{
    "user_ref": "scott_mobile",
    "home_id": "scott_home",
    "automation_name": "Decorations On",
    "ha_service": "scene",
    "ha_entity": "decorations_on"
  }'
```

---

## 2. `GET /enrollments?user_ref={ref}&status={STATUS}` — list

### Response — 200
```json
{
  "count": 2,
  "items": [
    { "id": "…", "automation_id": "decorations_on",  "status": "ACTIVE", … },
    { "id": "…", "automation_id": "decorations_off", "status": "ACTIVE", … }
  ]
}
```

`status` query param is optional; valid values: `ACTIVE`, `PAUSED`, `REVOKED`.

---

## 3. `GET /enrollments/{id}` — fetch one

Returns the enrollment record, or `404 {"error": "not found"}`.

---

## 4. `PATCH /enrollments/{id}/status` — pause / resume / revoke

### Request
```json
{ "status": "PAUSED" }
```

### Semantics
- `PAUSED`  ←→ `ACTIVE`: freely reversible.
- `REVOKED`: **terminal.** Attempting to move out of REVOKED returns
  `409 Conflict`. The user must delete and re-create the enrollment.

### Errors
- `404` — enrollment not found
- `409` — attempting to move out of `REVOKED`
- `400` — unknown status value

---

## 5. `DELETE /enrollments/{id}` — remove

`204 No Content` on success. The enrollment row is hard-deleted; challenge
logs are preserved (the log's `enrollment_id` becomes NULL but `user_ref` and
`automation_id` remain intact for audit).

---

## 6. `GET /check?user_ref={ref}&automation_id={id}` — pre-flight

Used by the app right before starting a VAPI session, to show the user
appropriate UI (spinner vs "set up voice auth first" vs "wait N seconds").

### Response — 200 (enrolled)
```json
{
  "exists": true,
  "enrollment_id": "21e86f28-…",
  "automation_id": "decorations_on",
  "status": "ACTIVE",
  "challenge_type": "VERIFICATION",
  "enrollment_required": false,
  "cooldown_remaining_seconds": 0,
  "attempts_remaining": 3
}
```

### Response — 404 (not enrolled)
```json
{ "exists": false, "enrollment_required": true }
```

App action: if `enrollment_required` → open the "enable voice auth" screen;
else if `cooldown_remaining_seconds > 0` → show a timer; else start the VAPI
session.

---

## 7. `GET /challenges?user_ref={ref}&limit={n}` — audit log

Most recent challenge attempts (default 50, max 500). Useful for:
- Showing a "last authenticated" timestamp in the app
- Debugging failed attempts

### Response — 200
```json
{
  "count": 1,
  "items": [{
    "id": "8f6a6733-…",
    "enrollment_id": "21e86f28-…",
    "user_ref": "scott_mobile",
    "automation_id": "decorations_on",
    "home_id": "scott_home",
    "vapi_call_id": "call_abc",
    "result": "SUCCESS",
    "failure_reason": null,
    "confidence_score": null,
    "started_at": "2026-04-23T00:57:10.866060",
    "completed_at": "2026-04-23T00:57:11.380137"
  }]
}
```

### Result values
| Value | Meaning |
|---|---|
| `PENDING` | In flight — challenge issued, waiting for user's verify response |
| `SUCCESS` | Phrase matched; HA automation dispatched |
| `FAIL` | Phrase mismatch (within max_attempts) |
| `TIMEOUT` | Challenge TTL expired before verify |
| `ERROR` | Upstream failure (HA unreachable, misconfig, etc.) |
| `ABANDONED` | User hung up / ended call mid-flow |
| `DENIED_COOLDOWN` | Request rejected before issuing: cooldown window active |
| `DENIED_LOCKED` | Rejected: enrollment status ≠ ACTIVE or attempts exhausted |
| `DENIED_NO_ENROLLMENT` | Rejected: no matching enrollment for (user_ref, automation_id) |

---

## 8. `GET /challenges/{id}` — fetch one log row

Single row by id. Same shape as items in #7.

---

## 9. Phone mappings (for inbound VAPI phone calls — Scott's case)

When VAPI has a phone number attached and someone calls it, the orchestrator
looks up the caller by phone number → `(user_ref, home_id)` and injects them
into the assistant's `variableValues`. Scott's SmartHome app registers his
phone number once; after that, "Call VoiceGuard" from his phone just works
without him identifying himself.

### `POST /phone-mappings`
```json
{
  "phone": "+15551234567",          // or "+1 (555) 123-4567" — formatting tolerated
  "user_ref": "scott_mobile",
  "home_id":  "scott_home",
  "vapi_phone_number_id": "optional-vapi-number-id",
  "label": "Scott's iPhone"
}
```
Response: `201`, normalized `phone_e164`.

Errors:
- `400` — invalid phone format
- `400` — number already mapped to a **different** user (same user is idempotent)

### `GET /phone-mappings?user_ref={ref}` — list
### `DELETE /phone-mappings/{id}` — remove
### `GET /phone-lookup?phone={e164}` — reverse lookup (used by VAPI webhook)

---

## 10. `POST /vapi/call-start` — VAPI inbound phone webhook

You don't call this. **VAPI calls this** when a phone call begins. Configure
it in the VAPI dashboard → your phone number → "Server URL" →
`https://voiceorchestrator.homeadapt.us/api/v1/voice-auth/vapi/call-start`.

Returns `assistantOverrides.variableValues` pre-populated if the caller is
recognized via phone-mapping lookup.

---

## 11. `GET /automations/discover?home_id={home_id}` — list candidates

Live query a home's HA for voice-eligible entities. Use this in your admin UI
when presenting "pick which automations to protect with voice auth."

### Response — 200
```json
{
  "home_id": "scott_home",
  "count": 13,
  "items": [
    { "entity_id": "scene.decorations_on", "domain": "scene",
      "entity": "decorations_on", "friendly_name": "Decorations On",
      "state": "2026-04-21T01:09:58+00:00" },
    { "entity_id": "script.main_lights_on", "domain": "script",
      "entity": "main_lights_on", "friendly_name": "Main Lights On",
      "state": "off" },
    …
  ]
}
```

Errors:
- `404 { "code": "NOT_CONFIGURED" }` — home isn't in HOME_CONFIGS_JSON
- `502` — HA unreachable or non-200

---

# Mobile SDK integration

## iOS (Swift) — Vapi iOS SDK

```swift
import Vapi

// Inject once at app start or from DI
let vapi = Vapi(publicKey: "0145170b-662c-4db1-983d-b3bf8aeee1b4")

// When user taps a protected automation
func triggerProtectedAutomation(_ automation: ProtectedAutomation, for user: User) async throws {
    // 1. Pre-flight
    let check = try await checkEnrollment(userRef: user.ref, automationId: automation.id)
    guard check.exists, check.cooldownRemainingSeconds == 0 else {
        // Show "not enrolled" or "wait N seconds" UI
        return
    }

    // 2. Start VAPI session — VAPI handles mic, voice, transcription, TTS
    try await vapi.start(
        assistantId: "1a2904b1-61cf-49da-a804-199d8d39fb9f",
        assistantOverrides: [
            "variableValues": [
                "home_id":         user.homeId,
                "user_ref":        user.ref,
                "automation_id":   automation.id,
                "automation_name": automation.displayName,
                "initiated_by":    "MOBILE_IOS"
            ]
        ]
    )

    // VAPI UI takes over; your app shows a "listening…" overlay.
    // Result bubbles back via vapi.on("call-end") + GET /challenges audit.
}

// Observe outcomes
vapi.on("call-end") { [weak self] _ in
    Task { [weak self] in
        let latest = try? await self?.latestChallenge(userRef: user.ref)
        if latest?.result == "SUCCESS" {
            self?.showToast("\(automation.displayName) activated")
        } else if latest?.result == "FAIL" {
            self?.showToast("Voice check failed")
        }
    }
}
```

Package: https://github.com/VapiAI/ios

## Android (Kotlin) — Vapi Android SDK

```kotlin
val vapi = Vapi(
    context = this,
    publicKey = "0145170b-662c-4db1-983d-b3bf8aeee1b4"
)

suspend fun triggerProtectedAutomation(automation: ProtectedAutomation, user: User) {
    val check = VoiceAuthApi.check(userRef = user.ref, automationId = automation.id)
    if (!check.exists || check.cooldownRemainingSeconds > 0) {
        // show gated UI
        return
    }

    vapi.start(
        assistantId = "1a2904b1-61cf-49da-a804-199d8d39fb9f",
        assistantOverrides = mapOf(
            "variableValues" to mapOf(
                "home_id"         to user.homeId,
                "user_ref"        to user.ref,
                "automation_id"   to automation.id,
                "automation_name" to automation.displayName,
                "initiated_by"    to "MOBILE_ANDROID"
            )
        )
    )
}
```

Package: https://github.com/VapiAI/android

## Web (JS/React Native)

```js
import Vapi from "@vapi-ai/web";

const vapi = new Vapi("0145170b-662c-4db1-983d-b3bf8aeee1b4");

async function trigger(automation, user) {
  const check = await (await fetch(
    `/api/v1/voice-auth/check?user_ref=${user.ref}&automation_id=${automation.id}`
  )).json();
  if (!check.exists || check.cooldown_remaining_seconds > 0) return;

  await vapi.start("1a2904b1-61cf-49da-a804-199d8d39fb9f", {
    variableValues: {
      home_id: user.homeId,
      user_ref: user.ref,
      automation_id: automation.id,
      automation_name: automation.displayName,
      initiated_by: "WEB",
    },
  });
}
```

Package: `@vapi-ai/web`

---

# Error envelope reference

Every 4xx/5xx returns:
```json
{ "error": "human-readable message", "code": "OPTIONAL_MACHINE_CODE" }
```

Codes you'll see:
| Code | HTTP | When |
|---|---|---|
| `VALIDATION` | 400 | Missing/invalid request body or query params |
| `CONFLICT` | 409 | Illegal state transition (e.g., un-revoke) |
| `NOT_CONFIGURED` | 404 | `home_id` isn't in `HOME_CONFIGS_JSON` |
| (none) | 404 | Generic not-found |
| (none) | 502 | Upstream HA failure |
| (none) | 500 | Orchestrator bug — report to backend team |

---

# End-to-end smoke test (curl)

```bash
BASE=https://voiceorchestrator.homeadapt.us
USER=scott_mobile
AUTO=decorations_on

# 1. Enroll (idempotent)
curl -X POST $BASE/api/v1/voice-auth/enrollments -H 'Content-Type: application/json' -d '{
  "user_ref": "'$USER'", "home_id": "scott_home",
  "automation_name": "Decorations On",
  "ha_service": "scene", "ha_entity": "decorations_on"
}'

# 2. Check
curl "$BASE/api/v1/voice-auth/check?user_ref=$USER&automation_id=$AUTO"

# 3. Start a VAPI voice session from the demo page — mobile clients do this via SDK
open "$BASE/demo/scott"  # browser-based equivalent; real app uses native SDK

# 4. Audit
curl "$BASE/api/v1/voice-auth/challenges?user_ref=$USER&limit=5"
```

---

# Changelog

- 2026-04-22: v1 release. Phrase-challenge only; voiceprint biometrics reserved
  for a future migration with no API-shape change (the `confidence_score` and
  `voiceprint_ref` fields are already reserved in the schema).
