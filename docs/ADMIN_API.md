# Admin API Documentation

REST API for managing users and homes in the Voice Orchestrator multi-tenant system.

## Base URL

```
http://localhost:6500/admin
```

## Authentication

All `/admin/*` requests require ONE of:

1. **Admin session** — log in via `POST /auth/login` (the admin dashboard does
   this); the session cookie authorizes subsequent calls.
2. **Admin API token** — set the `ADMIN_API_TOKEN` env var on the server, then
   send `Authorization: Bearer <token>` (for curl/scripts):

```bash
curl -H "Authorization: Bearer $ADMIN_API_TOKEN" http://localhost:6500/admin/users
```

Unauthenticated requests → `401`. For local dev only, `ADMIN_AUTH_OPEN=true`
disables the check (logged loudly).

Related security env vars:

| Env var | Purpose |
|---|---|
| `SECRET_KEY` | Flask session signing. Unset → ephemeral (sessions reset on restart). |
| `ADMIN_API_TOKEN` | Enables bearer-token access to `/admin/*`. |
| `ADMIN_PASSWORD_<USERNAME>` | Overrides a default admin password (e.g. `ADMIN_PASSWORD_KARTHI`). Defaults are committed to git — override them in production. |
| `MOBILE_JWT_SECRET` | Signs mobile login tokens. Unset → ephemeral (mobile re-login after restart). |

---

## User Management

### Create User

Create a new user account.

**Endpoint:** `POST /admin/users`

**Request Body:**
```json
{
  "username": "john_doe",
  "full_name": "John Doe",
  "email": "john@example.com",   // optional
  "user_id": "john_mobile",      // optional — align with an existing mobile
                                 // user_ref so historical data stays attached
  "password": "min-8-chars"      // optional — enables mobile app login
}
```

**Response:** `201 Created`
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "full_name": "John Doe",
  "email": "john@example.com",
  "is_active": true,
  "created_at": "2026-01-29T12:00:00"
}
```

**Example:**
```bash
curl -X POST http://localhost:6500/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "full_name": "John Doe",
    "email": "john@example.com"
  }'
```

---

### List Pending Signups

Mobile sign-ups awaiting activation (`POST /auth/signup` creates them inactive).

**Endpoint:** `GET /admin/users/pending`

**Response:** `200 OK` — `{"users": [...], "count": n}`

---

### Activate a Pending Signup

**Endpoint:** `POST /admin/users/{user_id}/activate`

After activating, attach the user's home (`POST /admin/homes/{home_id}/members`,
`POST /admin/homes` for a brand-new home, or
`scripts/provision_mobile_login.py --home <home_id>`) so `GET /me` returns it.

**Shortcut — skip manual approval entirely:** generate an
[invite code](#home-invite-codes-otp-style) for the home and give it to the
user *before* they sign up. Entering it on the sign-up screen creates the
account already active and attached to that home.

---

### Set / Reset User Password

Set or reset a user's mobile-login password (8–256 chars).

**Endpoint:** `PUT /admin/users/{user_id}/password`

**Request Body:**
```json
{ "password": "new-password" }
```

**Response:** `200 OK`
```json
{ "user_id": "john_mobile", "password_set": true }
```

---

### List Users

Get all users.

**Endpoint:** `GET /admin/users?active_only=false`

**Query Parameters:**
- `active_only` (boolean, default: false) - Filter to only active users

**Response:** `200 OK`
```json
{
  "users": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "username": "john_doe",
      "full_name": "John Doe",
      "email": "john@example.com",
      "is_active": true,
      "created_at": "2026-01-29T12:00:00"
    }
  ],
  "total": 1
}
```

---

### Get User

Get specific user details.

**Endpoint:** `GET /admin/users/{user_id}`

**Response:** `200 OK` or `404 Not Found`

---

### Update User

Update user details.

**Endpoint:** `PUT /admin/users/{user_id}`

**Request Body:** (all fields optional)
```json
{
  "username": "new_username",
  "full_name": "New Name",
  "email": "new@example.com"
}
```

**Response:** `200 OK` or `404 Not Found`

---

### Delete User

Deactivate a user (soft delete).

**Endpoint:** `DELETE /admin/users/{user_id}`

**Response:** `200 OK` or `404 Not Found`

---

## Home Management

### Register Home

Register a new home for a user.

**Endpoint:** `POST /admin/homes`

**Request Body:**
```json
{
  "home_id": "main_house",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Main House",
  "ha_url": "https://ha1.homeadapt.us",
  "ha_webhook_id": "voice_auth_scene"
}
```

**Response:** `201 Created`
```json
{
  "home_id": "main_house",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Main House",
  "ha_url": "https://ha1.homeadapt.us",
  "ha_webhook_id": "voice_auth_scene",
  "is_active": true,
  "created_at": "2026-01-29T12:00:00",
  "updated_at": null
}
```

**Example:**
```bash
curl -X POST http://localhost:6500/admin/homes \
  -H "Content-Type: application/json" \
  -d '{
    "home_id": "main_house",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Main House",
    "ha_url": "https://ha1.homeadapt.us",
    "ha_webhook_id": "voice_auth_scene"
  }'
```

---

### List Homes

Get all homes.

**Endpoint:** `GET /admin/homes?active_only=false`

**Query Parameters:**
- `active_only` (boolean, default: false) - Filter to only active homes

**Response:** `200 OK`
```json
{
  "homes": [
    {
      "home_id": "main_house",
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Main House",
      "ha_url": "https://ha1.homeadapt.us",
      "ha_webhook_id": "voice_auth_scene",
      "is_active": true,
      "created_at": "2026-01-29T12:00:00",
      "updated_at": null
    }
  ],
  "total": 1
}
```

---

### Get Home

Get specific home details.

**Endpoint:** `GET /admin/homes/{home_id}`

**Response:** `200 OK` or `404 Not Found`

---

### Update Home

Update home configuration.

**Endpoint:** `PUT /admin/homes/{home_id}`

**Request Body:** (all fields optional)
```json
{
  "name": "Updated House Name",
  "ha_url": "https://new-ha-url.com",
  "ha_webhook_id": "new_webhook_id",
  "is_active": true
}
```

**Response:** `200 OK` or `404 Not Found`

---

### Delete Home

Deactivate a home (soft delete).

**Endpoint:** `DELETE /admin/homes/{home_id}`

**Response:** `200 OK` or `404 Not Found`

---

### Get User's Homes

Get all homes for a specific user.

**Endpoint:** `GET /admin/users/{user_id}/homes?active_only=true`

Returns every home the user is a **member** of (owned or shared).

**Query Parameters:**
- `active_only` (boolean, default: true) - Filter to only active homes

**Response:** `200 OK`

---

## Home Members (shared homes)

A home can be listed for **several users at once** — a family, or two
testers sharing a demo home. Membership lives in the `home_members` table;
the user who registered the home is its `owner` member, anyone added later
is a `member`. Both roles see the home at login and may use it from the app.
Ownership is never transferred — adding a member never removes anyone.

The mobile login token only allows access to homes the user is a member of
(`403` otherwise), so membership is the access-control list for a home.

### List Members

**Endpoint:** `GET /admin/homes/{home_id}/members`

**Response:** `200 OK`
```json
{
  "home_id": "scott_home",
  "count": 2,
  "members": [
    { "home_id": "scott_home", "user_id": "scott_mobile", "role": "owner",
      "username": "scottmeyers", "email": "smeyersne@gmail.com",
      "full_name": "Scott Meyers", "created_at": "2026-02-05T22:22:44" },
    { "home_id": "scott_home", "user_id": "c31c3594-4721-43e0-9dd5-77f6c0dde4b5",
      "role": "member", "username": "u0450254@umail.utah.edu",
      "email": "u0450254@umail.utah.edu", "full_name": "u0450254",
      "created_at": "2026-09-17T17:11:54" }
  ]
}
```

`404` — home not found.

**Example:**
```bash
curl -s https://voiceorchestrator.homeadapt.us/admin/homes/scott_home/members \
  -H "Authorization: Bearer $ADMIN_API_TOKEN"
```

---

### Add a Member

**Endpoint:** `POST /admin/homes/{home_id}/members`

Idempotent — re-adding an existing member just updates their role.

**Request Body:**
```json
{ "user_id": "scott_mobile", "role": "member" }
```

- `user_id` (required) — an existing user
- `role` (optional) — `member` (default) or `owner`

**Response:** `201 Created` — the membership row (same shape as in List Members)

Errors: `400` unknown user / bad role, `404` home not found.

**Example — give Scott and Aaron the same two test homes:**
```bash
ADMIN_API_TOKEN=...   # from the server .env
BASE=https://voiceorchestrator.homeadapt.us

for HOME in scott_home ne_qli_1; do
  for USER in scott_mobile c31c3594-4721-43e0-9dd5-77f6c0dde4b5; do
    curl -s -X POST "$BASE/admin/homes/$HOME/members" \
      -H "Authorization: Bearer $ADMIN_API_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"user_id\": \"$USER\"}"
    echo
  done
done
```

---

### Remove a Member

**Endpoint:** `DELETE /admin/homes/{home_id}/members/{user_id}`

The user stops seeing the home at login and their token can no longer act
on it. Their favorites/enrollments for that home are left in place.

**Response:** `200 OK`
```json
{ "removed": true, "home_id": "scott_home", "user_id": "scott_mobile" }
```

`404` — home not found, or the user was not a member.

---

## Home Invite Codes (OTP-style)

An invite code lets a user attach themselves to a home **without a manual
approval round-trip**. You generate a code for a specific home, send it to
the person (text, email, in person), and they either:

- enter it on the app **sign-up screen** → the account is created **active**
  and attached to the home in one step (no `PENDING_APPROVAL`), or
- enter it in the app's **"Join a home"** screen while logged in
  (`POST /auth/redeem-invite`) → the home is added to their existing account.

Code format: 8 characters shown as `XXXX-XXXX` (e.g. `K7QX-4MRP`). The
alphabet has no `0/O` or `1/I`, and the user may type it in any case with or
without the dash. Defaults: **single use, valid 7 days**. Guessing is
throttled — 5 bad codes from one IP (or one account) locks that source out
for 15 minutes.

### Generate an Invite Code

**Endpoint:** `POST /admin/homes/{home_id}/invites`

**Request Body** (all fields optional):
```json
{ "role": "member", "expires_in_hours": 168, "max_uses": 1 }
```

- `role` — role granted on redeem: `member` (default) or `owner`
- `expires_in_hours` — 1 to 8760 (default 168 = 7 days)
- `max_uses` — 1 to 100 (default 1). Use e.g. `4` for a family sharing one code.

Optional header `X-Admin-User: <your name>` is stored as `created_by`.

**Response:** `201 Created`
```json
{
  "code": "K7QX-4MRP",
  "home_id": "scott_home",
  "role": "member",
  "status": "active",
  "created_by": "karthi",
  "created_at": "2026-09-17T18:00:00",
  "expires_at": "2026-09-24T18:00:00",
  "max_uses": 1,
  "use_count": 0,
  "revoked_at": null
}
```

Errors: `400` out-of-range settings, `404` home not found,
`503` invite codes not enabled on this server.

**Example — code for Aaron to join `ne_qli_1`:**
```bash
curl -s -X POST "$BASE/admin/homes/ne_qli_1/invites" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN" \
  -H "X-Admin-User: karthi" \
  -H "Content-Type: application/json" \
  -d '{"max_uses": 1, "expires_in_hours": 72}'
```

**Admin dashboard:** on the *Homes* tab each row has an **Invite** button
that asks for uses + days, generates the code, copies it to the clipboard and
shows it in a copyable box. The **Members** button lists who sees the home
and lets you add (`user_id`) or remove (`-user_id`) a member.

---

### List Invite Codes for a Home

**Endpoint:** `GET /admin/homes/{home_id}/invites?status=active`

Newest first. `status` filter is optional: `active` | `expired` |
`exhausted` | `revoked`.

**Response:** `200 OK` — `{"home_id": "...", "invites": [...], "count": n}`
(each item has the shape shown under *Generate*).

---

### Revoke an Invite Code

**Endpoint:** `DELETE /admin/invites/{code}`

Cancels a code early (idempotent). Accepts the code with or without the dash.

**Response:** `200 OK` — the invite with `"status": "revoked"`. `404` unknown code.

```bash
curl -s -X DELETE "$BASE/admin/invites/K7QX-4MRP" \
  -H "Authorization: Bearer $ADMIN_API_TOKEN"
```

---

## Complete Enrollment Example

Here's a complete flow for enrolling a new user with a home:

```bash
# Step 1: Create user
USER_RESPONSE=$(curl -s -X POST http://localhost:6500/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "becca",
    "full_name": "Becca Smith",
    "email": "becca@example.com"
  }')

USER_ID=$(echo $USER_RESPONSE | jq -r '.user_id')
echo "Created user: $USER_ID"

# Step 2: Register home for user
curl -X POST http://localhost:6500/admin/homes \
  -H "Content-Type: application/json" \
  -d "{
    \"home_id\": \"becca_main\",
    \"user_id\": \"$USER_ID\",
    \"name\": \"Becca's Main House\",
    \"ha_url\": \"https://becca-ha.homeadapt.us\",
    \"ha_webhook_id\": \"voice_auth_scene\"
  }"

# Step 3: Verify
curl http://localhost:6500/admin/users/$USER_ID/homes
```

Now the user "becca" can use FutureProof Homes with `home_id: "becca_main"` and it will route to her specific Home Assistant instance.

---

## Error Responses

All endpoints return standard error responses:

**400 Bad Request:**
```json
{
  "error": "Missing required field: username"
}
```

**404 Not Found:**
```json
{
  "error": "User with ID '...' not found"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal server error"
}
```
