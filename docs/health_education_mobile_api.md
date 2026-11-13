# Health Education in the Smart Home App: API Guide

For the mobile developer. This adds SCI Companion patient education (library,
example questions, chat, videos, source pages) to the smart home app with no
second login.

## How it works

1. The user logs in to the smart home app as today.
2. The app asks the smart home backend for a health education session.
3. The backend signs the user in to the health educator portal behind the
   scenes. The portal account is created automatically the first time.
4. The app calls the portal directly with the tokens it received.

Every active smart home user is eligible. Users are plain members: they can
read and ask, never upload or administer.

## Step 1: get a session

```
POST https://voiceorchestrator.homeadapt.us/api/v1/voice-auth/health-educator/session
Authorization: Bearer <smart home login token>
```

No body. Response `200`:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 1800,
  "base_url": "https://patienteducation.homeadapt.us/api",
  "api_prefix": "/api/mobile/v1",
  "user": {
    "username": "sh-8ee3028672b5cb52",
    "full_name": "Scott Example",
    "email": "scott@example.com",
    "gender": "male",
    "service_line": "sci-companion"
  }
}
```

Do not hardcode the portal address. Build every portal URL from `base_url`:

- API calls: `{base_url}{api_prefix}/...`
- Media paths returned in responses (they start with `/api/v2/...`):
  `{base_url}{path}`

| Status | `code` | Meaning | What to show |
| --- | --- | --- | --- |
| 401 | `UNAUTHORIZED` | Smart home token missing, expired or user inactive | Send the user to login |
| 403 | `FORBIDDEN` | Portal refused this account | "Contact support" |
| 502 | `PORTAL_UNAVAILABLE` | Portal is down or unreachable | "Try again shortly" |
| 503 | `NOT_CONFIGURED` | Feature is not switched on for this server | Hide the feature |

## Step 2: call the portal

Every call below carries `Authorization: Bearer <access_token>`.

### Library

```
GET {base_url}/api/mobile/v1/library
```

```json
{
  "service_line": "sci-companion",
  "starter_questions": ["How do I manage my bowel program?"],
  "youtube_playlist_url": "https://www.youtube.com/playlist?list=...",
  "total": 17,
  "documents": [
    {
      "document": "NRH SCI Managing Your Bladder.pdf",
      "title": "NRH SCI Managing Your Bladder",
      "audience": "all",
      "questions": [
        "What is a bladder management program?",
        "How do I do clean intermittent catheterization?"
      ],
      "youtube": { "title": "Bladder Management", "url": "https://www.youtube.com/watch?v=..." },
      "ai_video_url": "/api/v2/documents/NRH%20SCI%20Managing%20Your%20Bladder.pdf/overview?kind=video",
      "first_page_image_url": "/api/v2/documents/NRH%20SCI%20Managing%20Your%20Bladder.pdf/pages/0"
    }
  ]
}
```

- `starter_questions`: suggestions for an empty chat screen. May be empty.
- `questions`: example questions answered by that document. Send one as a
  chat question when tapped.
- `youtube`: the care team's original video. Open the `url` in the YouTube
  app or a web view. `null` when the document has none.
- `ai_video_url`: an AI-generated explainer of that one document. `null` when
  there is none. See "Media" below.
- `audience`: `all`, `female` or `male`. The list is already filtered to the
  user's gender, so there is nothing to hide on the client.

### Chat

```
POST {base_url}/api/mobile/v1/chat
Content-Type: application/json

{ "question": "How much water should I drink each day?" }
```

`question` is 1 to 1000 characters. Response `200`:

```json
{
  "message_id": "a4487ff27e2644529c26866a83ad81fd",
  "question": "How much water should I drink each day?",
  "answer": "Aim for ...",
  "voice_answer": "Aim for ...",
  "confidence": 0.81,
  "grounded": true,
  "sources": [
    {
      "document": "NRH SCI Managing Your Bladder.pdf",
      "title": "NRH SCI Managing Your Bladder",
      "page": 3,
      "page_image_url": "/api/v2/documents/NRH%20SCI%20Managing%20Your%20Bladder.pdf/pages/2",
      "excerpt": "The passage the answer was taken from ..."
    }
  ],
  "youtube": { "title": "Bladder Management", "url": "https://www.youtube.com/watch?v=..." },
  "ai_video": {
    "document": "NRH SCI Managing Your Bladder.pdf",
    "title": "NRH SCI Managing Your Bladder",
    "url": "/api/v2/documents/NRH%20SCI%20Managing%20Your%20Bladder.pdf/overview?kind=video"
  }
}
```

- `answer`: text to display. `voice_answer`: the same answer worded for
  text-to-speech.
- `sources`: the documents and pages the answer is grounded in. `page` is the
  page number as printed (first page is 1). `page_image_url` is a PNG of that
  page; `page` and `page_image_url` are `null` when the page is unknown.
- `grounded: false` with empty `sources` means the assistant found nothing in
  the materials and said so. Show the answer as is; there are no videos.
- `youtube` and `ai_video` are `null` when the cited document has none.
- The answer arrives whole (no streaming). Allow up to 60 seconds and show a
  progress indicator.

### Media

Page images and AI videos are private files. Request them with the same
`Authorization` header.

| What | URL | Notes |
| --- | --- | --- |
| Page image | `{base_url}{page_image_url}` | PNG. Add `?zoom=2` for a sharper image (0.5 to 3, default 1.5). |
| AI video | `{base_url}{ai_video_url}` | MP4, supports range requests. The player must send the header. |

Setting the header on a video player:

- iOS: `AVURLAsset(url:options:)` with
  `["AVURLAssetHTTPHeaderFieldsKey": ["Authorization": "Bearer ..."]]`
- Android (ExoPlayer / Media3):
  `DefaultHttpDataSource.Factory().setDefaultRequestProperties(...)`

YouTube links are ordinary public links and need no header.

## Step 3: keep the session alive

The access token lasts 30 minutes, the refresh token 7 days.

```
POST {base_url}/api/mobile/v1/session/refresh
Content-Type: application/json

{ "refresh_token": "<current refresh token>" }
```

Returns a new `access_token` and a new `refresh_token`. Each refresh token
works once: always store the new one.

Recommended handling of a `401` from any portal call:

1. Call refresh once and retry the request.
2. If refresh also returns `401`, call Step 1 again for a fresh session.
3. If Step 1 returns `401`, the smart home login has expired: go to login.

On logout, optionally end the portal session too:

```
POST {base_url}/api/mobile/v1/session/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{ "refresh_token": "<current refresh token>" }
```

Store both tokens in the device's secure storage (Keychain / Keystore).

## Gender on the profile

The portal shows men's or women's sexual health material according to the
user's gender. An admin can set it, and the app can too:

```
PATCH https://voiceorchestrator.homeadapt.us/api/v1/voice-auth/me
Authorization: Bearer <smart home login token>
Content-Type: application/json

{ "gender": "female" }
```

Values: `"female"`, `"male"` or `null` (not specified). `GET /me` and the
login response now include `gender`.

A change takes effect on the next Step 1 call, so request a new session after
changing it. While gender is not specified, the user sees both sets of
material; consider asking once before opening health education.

## Error format

- Smart home backend: `{ "error": "...", "code": "..." }`
- Portal: `{ "detail": "..." }` with the HTTP status (`401` not signed in,
  `403` not allowed, `422` invalid body, `500` server error).

## Quick test with curl

```bash
SH=https://voiceorchestrator.homeadapt.us/api/v1/voice-auth

LOGIN=$(curl -s $SH/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"..."}')
SH_TOKEN=$(echo "$LOGIN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

SESSION=$(curl -s -X POST $SH/health-educator/session -H "Authorization: Bearer $SH_TOKEN")
BASE=$(echo "$SESSION" | python3 -c 'import sys,json;print(json.load(sys.stdin)["base_url"])')
TOKEN=$(echo "$SESSION" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s $BASE/api/mobile/v1/library -H "Authorization: Bearer $TOKEN"
curl -s $BASE/api/mobile/v1/chat -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"question":"What is autonomic dysreflexia?"}'
```
