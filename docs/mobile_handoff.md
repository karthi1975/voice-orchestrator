# Voice Auth — Mobile Developer Quick Start

Everything you need to ship voice-auth in the SmartHome app. Simple, straight.

Full reference: [`docs/voice_auth_api.md`](voice_auth_api.md)

---

## Credentials

| Item | Value |
|---|---|
| **API base URL** | `https://voiceorchestrator.homeadapt.us/api/v1/voice-auth` |
| **VAPI assistant id** | `1a2904b1-61cf-49da-a804-199d8d39fb9f` |
| **VAPI public key** (safe in app; scoped to assistant) | `0145170b-662c-4db1-983d-b3bf8aeee1b4` |
| **Mobile API key — iOS** | `sk_ios_48b546d143dae04ec9d2c4396ae9155648e80a5ffbaf3377` |
| **Mobile API key — Android** | `sk_and_a4680b4e40ffe9b5133e8118b7d41cf753fa062688bc05a0` |
| **Mobile API key — Web** | `sk_web_37ceccf66f52a679b34ce1ba53eca44d7f67f2c281d15bc1` |

> 🔐 Mobile API keys are **static for v1** — compile into the app via your CI secret store (do NOT commit to git). Tomorrow we switch to short-lived per-user JWTs. **Header shape stays identical**, only the token value changes — your request code won't move.

---

## Every REST call needs this header

```
Authorization: Bearer <your-platform-key>
```

Missing/wrong → `401 { "error": "...", "code": "UNAUTHORIZED" }`.

VAPI SDK calls (voice session) use the **VAPI public key**, not the mobile API key.

---

## The three things the app does

### 1. Enroll an automation (user toggles "Voice Protect" on a scene)

```
POST /enrollments
Authorization: Bearer <key>
Content-Type: application/json

{
  "user_ref": "scott_mobile",
  "home_id":  "scott_home",
  "automation_name": "Main Lights On",
  "ha_service": "script",          // scene | script | switch | light | lock | cover | media_player | climate | input_boolean | fan
  "ha_entity":  "main_lights_on"   // entity SUFFIX only — NOT "script.main_lights_on"
}
```

Response `201`:
```json
{ "id": "a8100373-…", "automation_id": "main_lights_on", "status": "ACTIVE", ... }
```

Idempotent on `(user_ref, automation_id)`.

### 2. List enrollments (show the "Voice Protected" section)

```
GET /enrollments?user_ref=scott_mobile
Authorization: Bearer <key>
```

Response `200`:
```json
{ "count": 2, "items": [ { "id": "...", "automation_id": "main_lights_on",
                           "automation_name": "Main Lights On", "status": "ACTIVE", ... } ] }
```

### 3. Start a voice challenge (user taps a protected automation)

**No REST call** — just start the VAPI SDK with these `variableValues`:

```
assistantId:        "1a2904b1-61cf-49da-a804-199d8d39fb9f"
assistantOverrides.variableValues:
  home_id:         user.homeId                 // e.g. "scott_home"
  user_ref:        user.externalRef            // e.g. "scott_mobile"
  automation_id:   selectedAutomation.id       // e.g. "main_lights_on"
  automation_name: selectedAutomation.name     // e.g. "Main Lights On"
  initiated_by:    "MOBILE_IOS" | "MOBILE_ANDROID"
```

The assistant will speak "Confirm Main Lights On? Say the security phrase." — user repeats — HA fires. VAPI's `on("call-end")` event tells you when it's done.

---

## Full iOS example

```swift
import Foundation
import Vapi

struct VoiceAuth {

    static let apiBase       = "https://voiceorchestrator.homeadapt.us/api/v1/voice-auth"
    static let apiKey        = "sk_ios_48b546d143dae04ec9d2c4396ae9155648e80a5ffbaf3377"
    static let vapiPublicKey = "0145170b-662c-4db1-983d-b3bf8aeee1b4"
    static let vapiAssistant = "1a2904b1-61cf-49da-a804-199d8d39fb9f"

    // Shared VAPI instance
    static let vapi = Vapi(publicKey: vapiPublicKey)

    // ---------- 1. Enroll ----------

    static func enroll(userRef: String, homeId: String,
                       name: String, haService: String, haEntity: String) async throws -> Enrollment {
        var req = URLRequest(url: URL(string: "\(apiBase)/enrollments")!)
        req.httpMethod = "POST"
        req.setValue("Bearer \(apiKey)",  forHTTPHeaderField: "Authorization")
        req.setValue("application/json",  forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: [
            "user_ref":        userRef,
            "home_id":         homeId,
            "automation_name": name,
            "ha_service":      haService,
            "ha_entity":       haEntity,
            "created_by":      "MOBILE_IOS"
        ])
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard (resp as? HTTPURLResponse)?.statusCode == 201 else {
            throw NSError(domain: "VoiceAuth", code: 1)
        }
        return try JSONDecoder().decode(Enrollment.self, from: data)
    }

    // ---------- 2. List ----------

    static func list(userRef: String) async throws -> [Enrollment] {
        var req = URLRequest(url: URL(string: "\(apiBase)/enrollments?user_ref=\(userRef)")!)
        req.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await URLSession.shared.data(for: req)
        struct Wrapper: Codable { let items: [Enrollment] }
        return try JSONDecoder().decode(Wrapper.self, from: data).items
    }

    // ---------- 3. Voice challenge via SDK ----------

    static func triggerProtected(userRef: String, homeId: String,
                                 automationId: String, automationName: String) async throws {
        try await vapi.start(
            assistantId: vapiAssistant,
            assistantOverrides: [
                "variableValues": [
                    "home_id":         homeId,
                    "user_ref":        userRef,
                    "automation_id":   automationId,
                    "automation_name": automationName,
                    "initiated_by":    "MOBILE_IOS"
                ]
            ]
        )
    }
}

struct Enrollment: Codable {
    let id: String
    let automation_id: String
    let automation_name: String
    let status: String
}
```

### Wire it up in your UI

```swift
// "Add to Voice Auth" button
Task {
    try await VoiceAuth.enroll(
        userRef: currentUser.externalRef,
        homeId:  currentUser.homeId,
        name:    selectedHAItem.friendlyName,
        haService: selectedHAItem.domain,    // "script"
        haEntity:  selectedHAItem.entitySuffix // "main_lights_on"
    )
}

// "Tap a protected scene"
Task {
    try await VoiceAuth.triggerProtected(
        userRef: currentUser.externalRef,
        homeId:  currentUser.homeId,
        automationId:  tapped.id,
        automationName: tapped.displayName
    )
}

// Observe end of call
VoiceAuth.vapi.on("call-end") { _ in
    // Show success toast, refresh UI state, etc.
}
```

---

## Full Android example

```kotlin
import kotlinx.coroutines.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

object VoiceAuth {
    private const val API_BASE        = "https://voiceorchestrator.homeadapt.us/api/v1/voice-auth"
    private const val API_KEY         = "sk_and_a4680b4e40ffe9b5133e8118b7d41cf753fa062688bc05a0"
    private const val VAPI_PUBLIC_KEY = "0145170b-662c-4db1-983d-b3bf8aeee1b4"
    private const val VAPI_ASSISTANT  = "1a2904b1-61cf-49da-a804-199d8d39fb9f"

    private val http = OkHttpClient()
    private val json = Json { ignoreUnknownKeys = true }

    @Serializable data class Enrollment(
        val id: String,
        val automation_id: String,
        val automation_name: String,
        val status: String
    )

    // 1. Enroll
    suspend fun enroll(userRef: String, homeId: String,
                       name: String, haService: String, haEntity: String): Enrollment {
        val body = """{
          "user_ref":"$userRef","home_id":"$homeId",
          "automation_name":"$name","ha_service":"$haService","ha_entity":"$haEntity",
          "created_by":"MOBILE_ANDROID"
        }""".toRequestBody("application/json".toMediaType())
        val req = Request.Builder()
            .url("$API_BASE/enrollments")
            .addHeader("Authorization", "Bearer $API_KEY")
            .post(body)
            .build()
        http.newCall(req).execute().use { r ->
            require(r.code == 201) { "enroll failed: ${r.code}" }
            return json.decodeFromString(r.body!!.string())
        }
    }

    // 2. List
    suspend fun list(userRef: String): List<Enrollment> {
        val req = Request.Builder()
            .url("$API_BASE/enrollments?user_ref=$userRef")
            .addHeader("Authorization", "Bearer $API_KEY")
            .build()
        http.newCall(req).execute().use { r ->
            @Serializable data class Wrapper(val items: List<Enrollment>)
            return json.decodeFromString<Wrapper>(r.body!!.string()).items
        }
    }

    // 3. Voice challenge via VAPI SDK (github.com/VapiAI/android)
    fun trigger(userRef: String, homeId: String, autoId: String, autoName: String, context: android.content.Context) {
        val vapi = com.vapiai.sdk.Vapi(context = context, publicKey = VAPI_PUBLIC_KEY)
        vapi.start(
            assistantId = VAPI_ASSISTANT,
            assistantOverrides = mapOf(
                "variableValues" to mapOf(
                    "home_id"         to homeId,
                    "user_ref"        to userRef,
                    "automation_id"   to autoId,
                    "automation_name" to autoName,
                    "initiated_by"    to "MOBILE_ANDROID"
                )
            )
        )
    }
}
```

---

## Error handling — quick reference

| HTTP | Meaning | App action |
|---|---|---|
| `200` / `201` / `204` | OK | proceed |
| `400` | Validation error (bad body) | fix input; show inline error |
| `401` | Missing / wrong `Authorization` header | auth config bug — do NOT retry blindly |
| `404` | Not found (or not enrolled) | prompt user to enroll |
| `409` | Conflict (e.g., un-revoke attempt) | surface message |
| `500` / `502` | Orchestrator / HA upstream error | backoff + retry once, else notify |

Response body is always:
```json
{ "error": "<human message>", "code": "<OPTIONAL_CODE>" }
```

---

## Quick manual test (curl)

Replace the key with yours:

```bash
KEY=sk_ios_48b546d143dae04ec9d2c4396ae9155648e80a5ffbaf3377
BASE=https://voiceorchestrator.homeadapt.us/api/v1/voice-auth

# Missing auth → 401
curl -i "$BASE/enrollments?user_ref=demo_user"

# With auth → 200
curl -s -H "Authorization: Bearer $KEY" "$BASE/enrollments?user_ref=demo_user" | jq .

# Enroll (idempotent)
curl -s -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -X POST "$BASE/enrollments" \
  -d '{"user_ref":"demo_user","home_id":"scott_home","automation_name":"Test",
       "ha_service":"scene","ha_entity":"decorations_on"}' | jq .

# Pre-flight before voice session
curl -s -H "Authorization: Bearer $KEY" \
  "$BASE/check?user_ref=demo_user&automation_id=test" | jq .
```

---

## Acceptance checklist

- [ ] Enroll a new automation → 201 with `automation_id` returned
- [ ] List enrollments → the new one appears
- [ ] Start VAPI session with `variableValues` → assistant says "Confirm <name>? Say the security phrase."
- [ ] Repeat phrase → HA scene fires; assistant says "<name> activated."
- [ ] Immediate retry → assistant says "Please try again in N seconds." (cooldown works)
- [ ] Remove a bogus API key → requests 401

---

## What's coming tomorrow

1. **JWT auth (Tier 2).** Replace the static `sk_ios_…` strings with a short-lived JWT your backend mints at login time. Your `Authorization: Bearer <token>` code doesn't change — only the token source moves from "hardcoded string" to "fetch from auth endpoint." We'll send the JWT spec + signing secret separately.

2. **New enrollments for Scott.** We'll voice-protect `switch.bat_sign` and `light.man_land_lamp` for acceptance testing. You won't have to do anything — we'll enroll them server-side; they'll just appear in `GET /enrollments?user_ref=scott_mobile`.

---

## Contact

Ping the backend team with the `user_ref` you use + a sample `vapi_call_id` from `GET /challenges?user_ref=<you>` if anything misbehaves. All tool-call payloads are logged with redacted bodies — we can trace any specific call.
