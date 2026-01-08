#!/bin/bash

# Test script for Alexa endpoint
NGROK_URL="https://5fddf8830eee.ngrok-free.app"
ENDPOINT="${NGROK_URL}/alexa"

echo "🧪 Testing Alexa Voice Authentication Endpoint"
echo "============================================================"
echo ""

# Test 1: Launch Request
echo "Test 1: Launch Request"
echo "----------------------"
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0",
    "session": {
      "sessionId": "test-session-123"
    },
    "request": {
      "type": "LaunchRequest",
      "requestId": "test-request-1"
    }
  }'
echo -e "\n\n"

# Test 2: Night Scene Intent
echo "Test 2: Night Scene Intent (Trigger Challenge)"
echo "-----------------------------------------------"
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0",
    "session": {
      "sessionId": "test-session-456"
    },
    "request": {
      "type": "IntentRequest",
      "requestId": "test-request-2",
      "intent": {
        "name": "NightSceneIntent"
      }
    }
  }'
echo -e "\n\n"

echo "============================================================"
echo "✓ Tests Complete!"
echo ""
echo "IMPORTANT: Copy the challenge phrase from Test 2 output"
echo "Then run Test 3 manually with that phrase"
echo ""
echo "Example:"
echo "curl -X POST \"$ENDPOINT\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{"
echo "    \"version\": \"1.0\","
echo "    \"session\": {"
echo "      \"sessionId\": \"test-session-456\""
echo "    },"
echo "    \"request\": {"
echo "      \"type\": \"IntentRequest\","
echo "      \"requestId\": \"test-request-3\","
echo "      \"intent\": {"
echo "        \"name\": \"ChallengeResponseIntent\","
echo "        \"slots\": {"
echo "          \"response\": {"
echo "            \"name\": \"response\","
echo "            \"value\": \"ocean four\""
echo "          }"
echo "        }"
echo "      }"
echo "    }"
echo "  }'"
echo ""
