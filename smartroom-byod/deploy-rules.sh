#!/bin/bash
# Adds the roomJoins block to the LIVE Firestore ruleset (everything else kept
# byte-identical, including the current debug relaxation). Idempotent: exits if
# roomJoins is already present. Needs a fresh `gcloud auth login`.
set -euo pipefail
P="smarthomeadapt-broadcast"
TOKEN=$(gcloud auth print-access-token)
AUTH="Authorization: Bearer $TOKEN"
QP="x-goog-user-project: $P"
API="https://firebaserules.googleapis.com/v1"

RS=$(curl -sf -H "$AUTH" -H "$QP" "$API/projects/$P/releases/cloud.firestore" | python3 -c 'import sys,json;print(json.load(sys.stdin)["rulesetName"])')
echo "live ruleset: $RS"
curl -sf -H "$AUTH" -H "$QP" "$API/$RS" > /tmp/ruleset.json

python3 - <<'PY'
import json
src = json.load(open("/tmp/ruleset.json"))["source"]["files"][0]["content"]
if "roomJoins" in src:
    print("roomJoins already in live rules — nothing to do"); raise SystemExit(2)
anchor = "    // Room bindings"
assert anchor in src, "anchor comment not found in live rules"
block = """    // BYOD join requests (relatives' phones, anonymous auth). Phone writes one
    // pending doc {uid, roomNo, code}; the joinRoom function validates the
    // room's current join code and mints a 7-day subscription. Same create-only
    // shape as roomRegistrations.
    match /roomJoins/{id} {
      allow create: if signedIn()
                    && request.auth.token.firebase.sign_in_provider == 'anonymous'
                    && request.resource.data.uid == request.auth.uid
                    && request.resource.data.roomNo is string
                    && request.resource.data.code is string
                    && request.resource.data.status == 'pending';
      allow read: if signedIn() && resource.data.uid == request.auth.uid;
      allow update, delete: if false;
    }

"""
new = src.replace(anchor, block + anchor, 1)
json.dump({"source": {"files": [{"name": "firestore.rules", "content": new}]}}, open("/tmp/newruleset.json", "w"))
print("new source prepared (+%d chars)" % (len(new) - len(src)))
PY

NEW=$(curl -sf -H "$AUTH" -H "$QP" -H "Content-Type: application/json" -X POST "$API/projects/$P/rulesets" -d @/tmp/newruleset.json | python3 -c 'import sys,json;print(json.load(sys.stdin)["name"])')
echo "created ruleset: $NEW"
curl -sf -H "$AUTH" -H "$QP" -H "Content-Type: application/json" -X PATCH \
  "$API/projects/$P/releases/cloud.firestore" \
  -d "{\"release\":{\"name\":\"projects/$P/releases/cloud.firestore\",\"rulesetName\":\"$NEW\"}}" >/dev/null
echo "released. previous ruleset (rollback): $RS"
