#!/usr/bin/env python3
"""Quick one-shot test of the Alexa flow"""

import requests
import json

ENDPOINT = "https://1eb143d2d314.ngrok-free.app/alexa"

def test():
    print("\n🧪 Quick Alexa Flow Test\n")

    # 1. Launch
    print("1️⃣  Launch: ", end="")
    r1 = requests.post(ENDPOINT, json={
        "version": "1.0",
        "session": {"sessionId": "test-123"},
        "request": {"type": "LaunchRequest", "requestId": "req-1"}
    })
    print(f"✅ {r1.json()['response']['outputSpeech']['text']}")

    # 2. Night Scene
    print("2️⃣  Night Scene: ", end="")
    r2 = requests.post(ENDPOINT, json={
        "version": "1.0",
        "session": {"sessionId": "test-456"},
        "request": {
            "type": "IntentRequest",
            "requestId": "req-2",
            "intent": {"name": "NightSceneIntent"}
        }
    })
    response_text = r2.json()['response']['outputSpeech']['text']
    print(f"✅ {response_text}")

    # Extract challenge
    challenge = response_text.split("Please say:")[-1].strip()
    print(f"\n💡 Challenge: '{challenge}'")

    # 3. Respond
    print("3️⃣  Response: ", end="")
    r3 = requests.post(ENDPOINT, json={
        "version": "1.0",
        "session": {"sessionId": "test-456"},
        "request": {
            "type": "IntentRequest",
            "requestId": "req-3",
            "intent": {
                "name": "ChallengeResponseIntent",
                "slots": {
                    "response": {"name": "response", "value": challenge}
                }
            }
        }
    })
    print(f"✅ {r3.json()['response']['outputSpeech']['text']}")

    print("\n✅ Full flow completed successfully!")
    print("📺 Check server console for scene trigger\n")

if __name__ == "__main__":
    test()
