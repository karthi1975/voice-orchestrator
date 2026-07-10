#!/bin/bash
# Integration test for the voice-auth favorites API.
#
# Usage:
#   ./scripts/test_favorites_api.sh                          # test production
#   BASE=http://localhost:6500/api/v1/voice-auth ./scripts/test_favorites_api.sh   # test local server
#
# Env overrides: BASE, KEY (platform key), SCOTT_EMAIL, SCOTT_PW (JWT tests
# are skipped when SCOTT_PW is unset).
#
# Safe on production: read-only except one temp entity favorite (and, when
# the HA link is up, one temp device favorite) — both deleted afterwards.

BASE="${BASE:-https://voiceorchestrator.homeadapt.us/api/v1/voice-auth}"
KEY="${KEY:-sk_ios_48b546d143dae04ec9d2c4396ae9155648e80a5ffbaf3377}"
SCOTT_EMAIL="${SCOTT_EMAIL:-smeyersne@gmail.com}"
USER_REF="${USER_REF:-scott_mobile}"
HOME_ID="${HOME_ID:-scott_home}"
DEVICE_ID="${DEVICE_ID:-8b5b91fe90278f8d18cdb4659e99da92}"   # Man Land Lamp

PASS=0; FAIL=0
check() { if [ "$2" = "$3" ]; then PASS=$((PASS+1)); echo "PASS  $1 ($3)";
          else FAIL=$((FAIL+1)); echo "FAIL  $1 (expected $2, got $3)"; fi; }
code() { curl -s -o /tmp/fav_body.json -w "%{http_code}" "$@"; }
J()    { code -X POST "$BASE/favorites" -H "Authorization: Bearer $KEY" \
              -H "Content-Type: application/json" -d "$1"; }

echo "Target: $BASE"
echo ""
echo "=== Auth ==="
check "no auth -> 401"    401 "$(code "$BASE/favorites?user_ref=$USER_REF&home_id=$HOME_ID")"
check "bad key -> 401"    401 "$(code -H "Authorization: Bearer nope" "$BASE/favorites?user_ref=$USER_REF&home_id=$HOME_ID")"
check "good key -> 200"   200 "$(code -H "Authorization: Bearer $KEY" "$BASE/favorites?user_ref=$USER_REF&home_id=$HOME_ID")"
BASE_COUNT=$(python3 -c "import json;print(json.load(open('/tmp/fav_body.json'))['count'])")
echo "      baseline favorites: $BASE_COUNT"

echo ""
echo "=== Validation ==="
check "missing user_ref -> 400"    400 "$(J "{\"home_id\":\"$HOME_ID\",\"entity_id\":\"scene.x\"}")"
check "missing home_id -> 400"     400 "$(J "{\"user_ref\":\"$USER_REF\",\"entity_id\":\"scene.x\"}")"
check "no device/entity -> 400"    400 "$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"$HOME_ID\"}")"
check "unknown home -> 400"        400 "$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"no_such_home\",\"entity_id\":\"scene.x\"}")"
check "bad entity format -> 400"   400 "$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"$HOME_ID\",\"entity_id\":\"noDot\"}")"
check "empty body -> 400"          400 "$(J '{}')"

echo ""
echo "=== HA link (auto-detects up/down) ==="
DISC=$(code -H "Authorization: Bearer $KEY" "$BASE/devices/discover?home_id=$HOME_ID")
if [ "$DISC" = "200" ]; then
    N=$(python3 -c "import json;print(json.load(open('/tmp/fav_body.json'))['count'])")
    echo "HA link UP — $N devices visible; testing device favorites"
    check "unknown device -> 400"  400 "$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"$HOME_ID\",\"device_id\":\"deadbeef000000\"}")"
    STATUS=$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"$HOME_ID\",\"device_id\":\"$DEVICE_ID\"}")
    check "add device favorite -> 201" 201 "$STATUS"
    if [ "$STATUS" = "201" ]; then
        FID=$(python3 -c "import json;print(json.load(open('/tmp/fav_body.json'))['id'])")
        check "cleanup device favorite -> 204" 204 "$(code -X DELETE -H "Authorization: Bearer $KEY" "$BASE/favorites/$FID")"
    fi
elif [ "$DISC" = "503" ]; then
    echo "HA link DOWN — verifying honest 503s"
    check "discover -> 503 HOME_UNREACHABLE" ok "$(grep -q HOME_UNREACHABLE /tmp/fav_body.json && echo ok || echo bad)"
    check "device add -> 503"  503 "$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"$HOME_ID\",\"device_id\":\"$DEVICE_ID\"}")"
else
    check "discover -> 200 or 503" "200|503" "$DISC"
fi

echo ""
echo "=== Entity favorite lifecycle (works regardless of HA state) ==="
STATUS=$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"$HOME_ID\",\"entity_id\":\"scene.api_test_tmp\",\"friendly_name\":\"API Test Tmp\"}")
check "add entity favorite -> 201" 201 "$STATUS"
FID=$(python3 -c "import json;print(json.load(open('/tmp/fav_body.json')).get('id',''))")
check "duplicate -> 400"           400 "$(J "{\"user_ref\":\"$USER_REF\",\"home_id\":\"$HOME_ID\",\"entity_id\":\"scene.api_test_tmp\"}")"
check "delete -> 204"              204 "$(code -X DELETE -H "Authorization: Bearer $KEY" "$BASE/favorites/$FID")"
check "re-delete -> 404"           404 "$(code -X DELETE -H "Authorization: Bearer $KEY" "$BASE/favorites/$FID")"
CNT=$(curl -s -H "Authorization: Bearer $KEY" "$BASE/favorites?user_ref=$USER_REF&home_id=$HOME_ID" | python3 -c "import json,sys;print(json.load(sys.stdin)['count'])")
check "count restored"             "$BASE_COUNT" "$CNT"

if [ -n "$SCOTT_PW" ]; then
    echo ""
    echo "=== JWT identity (login as $SCOTT_EMAIL) ==="
    TOKEN=$(curl -s -X POST -H "Content-Type: application/json" \
        -d "{\"email\":\"$SCOTT_EMAIL\",\"password\":\"$SCOTT_PW\"}" "$BASE/auth/login" \
        | python3 -c "import json,sys;print(json.load(sys.stdin).get('token',''))")
    [ -n "$TOKEN" ] && check "login" ok ok || check "login" ok FAILED
    check "jwt list -> 200"          200 "$(code -H "Authorization: Bearer $TOKEN" "$BASE/favorites?user_ref=$USER_REF&home_id=$HOME_ID")"
    check "foreign user_ref -> 403"  403 "$(code -H "Authorization: Bearer $TOKEN" "$BASE/favorites?user_ref=someone_else&home_id=$HOME_ID")"
    check "GET /me -> 200"           200 "$(code -H "Authorization: Bearer $TOKEN" "$BASE/me")"
else
    echo ""
    echo "(JWT tests skipped — set SCOTT_PW to include them)"
fi

echo ""
echo "RESULT: $PASS passed, $FAIL failed"
exit $FAIL
