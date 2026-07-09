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

After activating, attach the user's home (`POST /admin/homes` or
`scripts/provision_mobile_login.py --home <home_id>`) so `GET /me` returns it.

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

**Query Parameters:**
- `active_only` (boolean, default: true) - Filter to only active homes

**Response:** `200 OK`

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
