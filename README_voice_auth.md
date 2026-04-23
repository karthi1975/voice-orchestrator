# Voice Authentication module

Per-user, per-automation voice gate on top of Home Assistant. Mobile apps
(iOS/Android/Web) enroll automations that need confirmation, then start a
VAPI voice session at trigger time. On successful phrase challenge, the
orchestrator fires HA via its REST API.

Detailed API docs: [`docs/voice_auth_api.md`](docs/voice_auth_api.md)

---

## Files

| Path | Purpose |
|---|---|
| `migrations/versions/006_add_voice_auth_tables.py` | enrollment + challenge log + phone mapping tables |
| `app/domain/voice_auth_enums.py` | `EnrollmentStatus`, `ChallengeType`, `ChallengeResult` |
| `app/domain/voice_auth_models.py` | `Enrollment`, `ChallengeLog`, `PhoneMapping` dataclasses |
| `app/repositories/voice_auth_repository.py` | interfaces |
| `app/repositories/implementations/sqlalchemy_voice_auth_repo.py` | Postgres impl |
| `app/repositories/implementations/in_memory_voice_auth_repo.py` | in-memory impl (dev/tests) |
| `app/services/voice_auth_service.py` | all business logic |
| `app/controllers/voice_auth_controller.py` | `/api/v1/voice-auth/*` |
| `app/infrastructure/home_assistant/direct_dispatcher.py` | extended with `dispatch_direct()` |
| `routes/vapi.py` | extended with enrollment-flow branch |
| `server.py` | wires `VoiceAuthService` into Flask |
| `tests/unit/test_voice_auth_service.py` | 42 unit tests |
| `tests/integration/test_voice_auth_api.py` | 17 HTTP integration tests |

---

## Environment variables

Set in `.env.local` on the droplet (never in git). Deploy script merges
`.env.local` onto `.env` on every deploy.

### Required (when enabling voice auth)

```bash
# Postgres connection (voice_auth uses this even when USE_DATABASE=false)
DATABASE_URL=postgresql+psycopg2://voiceorch:voiceorch_password_2026@voice-orchestrator-db:5432/voice_orchestrator

# Per-home HA credentials (same as Architecture C's dispatcher)
HOME_CONFIGS_JSON={"scott_home":{"ha_url":"https://ne-demo-pioneercourage.homeadapt.us","ha_token":"eyJ…"}}

# VAPI
VAPI_WEBHOOK_SECRET=<random-32-byte-hex>
VAPI_PUBLIC_KEY=0145170b-662c-4db1-983d-b3bf8aeee1b4
VAPI_ASSISTANT_ID=1a2904b1-61cf-49da-a804-199d8d39fb9f
```

If `DATABASE_URL` is unset, the voice-auth service automatically falls back
to in-memory repositories with a loud warning in the logs — fine for dev,
data will NOT persist across restarts.

---

## Running migrations

### On the droplet (production)

```bash
# From the droplet shell, with the image already built:
docker exec voice-orchestrator alembic upgrade head
```

If you bootstrap a fresh DB, stamp your current schema state first:

```bash
docker exec voice-orchestrator alembic stamp 005     # if tables 001..005 already exist
docker exec voice-orchestrator alembic upgrade head  # applies 006 and anything newer
```

Verify with:
```bash
docker exec voice-orchestrator-db \
  psql -U voiceorch -d voice_orchestrator -c '\dt voice_auth_*'
```

### Locally (fresh dev DB)

```bash
source venv/bin/activate
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db alembic upgrade head
```

---

## Running tests

```bash
source venv/bin/activate
python -m pytest tests/unit/test_voice_auth_service.py tests/integration/test_voice_auth_api.py -v
```

Tests use in-memory repos only — no DB, no VAPI, no HA required.

---

## Smoke-testing against the live droplet

After deploy, a one-liner e2e:

```bash
BASE=https://voiceorchestrator.homeadapt.us
SECRET=<VAPI_WEBHOOK_SECRET value>
USER=scott_mobile

# Ensure enrollment exists (idempotent)
curl -sS -X POST $BASE/api/v1/voice-auth/enrollments \
  -H 'Content-Type: application/json' \
  -d '{"user_ref":"'$USER'","home_id":"scott_home","automation_name":"Decorations On","ha_service":"scene","ha_entity":"decorations_on"}'

# Simulate the VAPI flow end-to-end
CID="smoke_$(date +%s)"
RESP=$(curl -sS -X POST $BASE/vapi/auth/request \
  -H "X-Vapi-Secret: $SECRET" -H 'Content-Type: application/json' \
  -d "{\"message\":{\"call\":{\"id\":\"$CID\"},\"assistantOverrides\":{\"variableValues\":{\"user_ref\":\"$USER\",\"automation_id\":\"decorations_on\"}},\"toolCallList\":[{\"id\":\"tc1\",\"function\":{\"name\":\"request_scene_challenge\",\"arguments\":{}}}]}}")
PHRASE=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["results"][0]["result"]["challenge"])')

curl -sS -X POST $BASE/vapi/auth/verify \
  -H "X-Vapi-Secret: $SECRET" -H 'Content-Type: application/json' \
  -d "{\"message\":{\"call\":{\"id\":\"$CID\"},\"assistantOverrides\":{\"variableValues\":{\"user_ref\":\"$USER\",\"automation_id\":\"decorations_on\"}},\"toolCallList\":[{\"id\":\"tc2\",\"function\":{\"name\":\"verify_challenge_response\",\"arguments\":{\"spoken_response\":\"$PHRASE\"}}}]}}"
```

Expected speech in the final response: `"Decorations On activated."`
Audit check:
```bash
curl -s "$BASE/api/v1/voice-auth/challenges?user_ref=$USER&limit=1" | python3 -m json.tool
```
Should show the most recent log as `"result": "SUCCESS"`.

---

## Operational notes

- **DB session lifetime**: the service holds a single long-lived SQLAlchemy
  session (attached to the Flask app at startup). For multi-worker deployments
  (gunicorn, etc.), revisit this and move to per-request sessions or a
  scoped session factory.
- **Rate limiting**: not implemented at the HTTP layer. Challenge-level
  rate limit is enforced by `max_attempts` (rolling 1h fail window) +
  `cooldown_seconds` (after successful challenges).
- **Voiceprint**: schema has `confidence_score` as a reserved nullable field.
  When a biometric service (Pindrop/NICE/ID R&D) is wired later, that column
  starts getting populated; the API contract doesn't change.
- **Multi-worker DB**: when moving off Flask's dev server to a WSGI server
  with multiple workers, ensure each worker builds its own SQLAlchemy engine
  (`_build_voice_auth_service` already does, since workers get their own
  process; just confirm on first deploy).

---

## Known limitations / future work

- No JWT validation on the API yet — bearer tokens are accepted as-is.
  Add middleware that pins `user_ref` to the authenticated subject to
  prevent client-side forgery.
- No event emission. Hooks exist in the service logger; wiring to a real
  event bus (Redis pub/sub / Kafka) is a future addition.
- Phone normalization is E.164-ish but doesn't intelligently infer country
  code from locale. Mobile clients should always send full E.164 strings
  starting with `+`.
- Enrollment-delete is hard-delete on the `voice_auth_enrollments` row;
  challenge logs survive with `enrollment_id = NULL` for audit.
