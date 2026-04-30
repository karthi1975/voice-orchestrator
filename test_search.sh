#!/bin/bash
# Search across all kinds (devices, entities, scenes, scripts, automations)
# in scott_home matching "bat", and flag which are already favorited by scott_mobile.

KEY=sk_ios_48b546d143dae04ec9d2c4396ae9155648e80a5ffbaf3377
BASE=https://voiceorchestrator.homeadapt.us/api/v1/voice-auth

echo "=== A. Search 'bat' across all kinds, with is_favorited flag ==="
curl -s -G "$BASE/items/search" \
  -H "Authorization: Bearer $KEY" \
  --data-urlencode "home_id=scott_home" \
  --data-urlencode "q=bat" \
  --data-urlencode "user_ref=scott_mobile"
echo
echo

echo "=== B. Search 'bat' filtered to devices only ==="
curl -s -G "$BASE/items/search" \
  -H "Authorization: Bearer $KEY" \
  --data-urlencode "home_id=scott_home" \
  --data-urlencode "q=bat" \
  --data-urlencode "kind=device" \
  --data-urlencode "user_ref=scott_mobile"
echo
echo

echo "=== C. List all scenes in scott_home (no q filter) ==="
curl -s -G "$BASE/items/search" \
  -H "Authorization: Bearer $KEY" \
  --data-urlencode "home_id=scott_home" \
  --data-urlencode "kind=scene" \
  --data-urlencode "user_ref=scott_mobile"
echo

echo "=== D. List all HA-configured automations in scott_home ==="
curl -s -G "$BASE/items/search" \
  -H "Authorization: Bearer $KEY" \
  --data-urlencode "home_id=scott_home" \
  --data-urlencode "kind=automation" \
  --data-urlencode "user_ref=scott_mobile"
echo
