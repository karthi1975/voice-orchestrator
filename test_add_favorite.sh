#!/bin/bash
# Add to favorites — three flavors:
#   A. Favoriting a DEVICE (sends device_id only)
#   B. Favoriting a SCENE (sends entity_id only)
#   C. Favoriting an HA AUTOMATION (sends entity_id only)

KEY=sk_ios_48b546d143dae04ec9d2c4396ae9155648e80a5ffbaf3377
BASE=https://voiceorchestrator.homeadapt.us/api/v1/voice-auth

echo "=== A. Add device 'Bat Sign' to scott_mobile's favorites ==="
echo "    (server resolves primary_entity_id from HA device registry)"
curl -s -X POST "$BASE/favorites" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_ref":      "scott_mobile",
    "home_id":       "scott_home",
    "device_id":     "6b86cd8c539ad69b193a8ff2acbf3b4e",
    "friendly_name": "Bat Sign"
  }'
echo
echo

echo "=== B. Add scene 'Good Morning' to favorites (entity-style) ==="
curl -s -X POST "$BASE/favorites" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_ref":      "scott_mobile",
    "home_id":       "scott_home",
    "entity_id":     "scene.good_morning",
    "friendly_name": "Good Morning"
  }'
echo
echo

echo "=== C. Add HA-configured automation 'Lights Off at Night' to favorites ==="
curl -s -X POST "$BASE/favorites" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_ref":      "scott_mobile",
    "home_id":       "scott_home",
    "entity_id":     "automation.lights_off_at_night",
    "friendly_name": "Lights Off at Night"
  }'
echo
echo

echo "=== D. Verify by listing all of scott_mobile's favorites ==="
curl -s "$BASE/favorites?user_ref=scott_mobile&home_id=scott_home" \
  -H "Authorization: Bearer $KEY"
echo
