#!/bin/bash
# Remove from favorites.
#
# The mobile app already has the favorite_id in two places:
#   - GET /favorites returns the id of every row
#   - GET /items/search?user_ref=... returns favorite_id when is_favorited=true
#
# Pass the UUID as $1 to this script, or it will read it from the FAV_ID env var.

KEY=sk_ios_48b546d143dae04ec9d2c4396ae9155648e80a5ffbaf3377
BASE=https://voiceorchestrator.homeadapt.us/api/v1/voice-auth

FAV_ID="${1:-${FAV_ID:-}}"

if [ -z "$FAV_ID" ]; then
  echo "Usage: ./test_remove_favorite.sh <favorite_uuid>"
  echo
  echo "Or set FAV_ID env var. Example:"
  echo "  ./test_remove_favorite.sh 26260ec6-ccfb-4cfb-a84c-55a3b458dc23"
  echo
  echo "Tip — fetch the current list to find the UUID:"
  echo "  curl -s '$BASE/favorites?user_ref=scott_mobile&home_id=scott_home' \\"
  echo "    -H 'Authorization: Bearer \$KEY' | jq '.items[] | {id, entity_id, friendly_name}'"
  exit 1
fi

echo "=== Removing favorite $FAV_ID ==="
HTTP=$(curl -s -o /tmp/_resp.txt -w "%{http_code}" -X DELETE "$BASE/favorites/$FAV_ID" \
  -H "Authorization: Bearer $KEY")
echo "HTTP $HTTP"
[ -s /tmp/_resp.txt ] && cat /tmp/_resp.txt && echo

echo
echo "=== Verifying — current favorites for scott_mobile ==="
curl -s "$BASE/favorites?user_ref=scott_mobile&home_id=scott_home" \
  -H "Authorization: Bearer $KEY"
echo
