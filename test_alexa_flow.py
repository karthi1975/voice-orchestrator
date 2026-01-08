#!/usr/bin/env python3
"""
Interactive Python script to test Alexa Voice Authentication flow
"""

import requests
import json
import uuid
from datetime import datetime

# Configuration
NGROK_URL = "https://1eb143d2d314.ngrok-free.app"
ALEXA_ENDPOINT = f"{NGROK_URL}/alexa"
SESSION_ID = f"test-session-{uuid.uuid4()}"


def send_alexa_request(request_type, intent_name=None, slots=None):
    """Send a request to the Alexa endpoint"""

    payload = {
        "version": "1.0",
        "session": {
            "sessionId": SESSION_ID,
            "application": {
                "applicationId": "amzn1.ask.skill.test"
            },
            "user": {
                "userId": "test-user"
            }
        },
        "request": {
            "type": request_type,
            "requestId": f"test-request-{uuid.uuid4()}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "locale": "en-US"
        }
    }

    if intent_name:
        payload["request"]["intent"] = {
            "name": intent_name,
            "confirmationStatus": "NONE"
        }

        if slots:
            payload["request"]["intent"]["slots"] = slots

    try:
        response = requests.post(
            ALEXA_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error: Server returned status {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {ALEXA_ENDPOINT}")
        print("Make sure ngrok is running and the server is active!")
        return None
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


def print_alexa_response(response):
    """Print Alexa's response in a nice format"""
    if not response:
        return None

    output_speech = response.get("response", {}).get("outputSpeech", {})
    text = output_speech.get("text", "")

    print("\n" + "="*60)
    print("🗣️  ALEXA SAYS:")
    print("="*60)
    print(f"{text}")
    print("="*60)

    return text


def test_full_flow_interactive():
    """Run the complete interactive test flow"""

    print("\n" + "*"*60)
    print("🎤 ALEXA VOICE AUTHENTICATION - INTERACTIVE TEST")
    print("*"*60)
    print(f"\nEndpoint: {ALEXA_ENDPOINT}")
    print(f"Session ID: {SESSION_ID}\n")

    # Step 1: Launch Request
    print("\n[Step 1] Launching skill...")
    print('User: "Alexa, open security check"\n')

    response = send_alexa_request("LaunchRequest")
    alexa_text = print_alexa_response(response)

    if not alexa_text:
        return

    input("\nPress Enter to continue...")

    # Step 2: Night Scene Intent
    print("\n[Step 2] Requesting night scene...")
    print('User: "night scene"\n')

    response = send_alexa_request("IntentRequest", "NightSceneIntent")
    alexa_text = print_alexa_response(response)

    if not alexa_text:
        return

    # Extract the challenge phrase
    # Format: "Security check required. Please say: island two"
    challenge = None
    if "Please say:" in alexa_text:
        challenge = alexa_text.split("Please say:")[-1].strip()
        print(f"\n💡 Challenge phrase: '{challenge}'")

    # Step 3: Interactive Challenge Response
    print("\n[Step 3] Respond to the challenge")
    print("You can type:")
    print(f"  - Just the phrase: '{challenge}'")
    print(f"  - With carrier: 'it is {challenge}'")
    print(f"  - Or anything else to test failure\n")

    user_response = input("Your response: ").strip()

    if not user_response:
        user_response = challenge  # Default to correct answer

    print(f'\nUser: "{user_response}"\n')

    # Send challenge response
    slots = {
        "response": {
            "name": "response",
            "value": user_response
        }
    }

    response = send_alexa_request("IntentRequest", "ChallengeResponseIntent", slots)
    alexa_text = print_alexa_response(response)

    if not alexa_text:
        return

    # Check if successful
    if "verified" in alexa_text.lower() and "activated" in alexa_text.lower():
        print("\n✅ SUCCESS! Voice authentication completed!")
        print("\n📺 Check your server console for the scene trigger output!")
    else:
        print("\n❌ Authentication failed or incorrect response")

    print("\n" + "*"*60)
    print("TEST COMPLETE")
    print("*"*60 + "\n")


def test_automated_flow():
    """Run automated test with correct responses"""

    print("\n" + "*"*60)
    print("🤖 ALEXA VOICE AUTHENTICATION - AUTOMATED TEST")
    print("*"*60)
    print(f"\nEndpoint: {ALEXA_ENDPOINT}")
    print(f"Session ID: {SESSION_ID}\n")

    # Step 1: Launch
    print("[1/3] Launch Request...")
    response = send_alexa_request("LaunchRequest")
    print_alexa_response(response)

    # Step 2: Night Scene
    print("\n[2/3] Night Scene Intent...")
    response = send_alexa_request("IntentRequest", "NightSceneIntent")
    alexa_text = print_alexa_response(response)

    # Extract challenge
    challenge = None
    if "Please say:" in alexa_text:
        challenge = alexa_text.split("Please say:")[-1].strip()

    if not challenge:
        print("❌ Could not extract challenge phrase!")
        return

    # Step 3: Correct Response
    print(f"\n[3/3] Responding with: '{challenge}'...")
    slots = {
        "response": {
            "name": "response",
            "value": challenge
        }
    }

    response = send_alexa_request("IntentRequest", "ChallengeResponseIntent", slots)
    print_alexa_response(response)

    print("\n✅ Automated test complete!")
    print("📺 Check your server console for the scene trigger!\n")


def test_health():
    """Test the health endpoint"""
    print("\n🏥 Testing health endpoint...")

    try:
        response = requests.get(f"{NGROK_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✅ Server is healthy!")
            print(f"Status: {health.get('status')}")
            print(f"HA Connected: {health.get('home_assistant', {}).get('connected')}")
            print(f"Message: {health.get('home_assistant', {}).get('message')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")


def main():
    """Main menu"""

    print("\n" + "="*60)
    print("ALEXA VOICE AUTHENTICATION - COMMAND LINE TESTER")
    print("="*60)

    while True:
        print("\nSelect test mode:")
        print("1. Interactive Test (you respond to challenges)")
        print("2. Automated Test (auto-responds correctly)")
        print("3. Health Check")
        print("4. Exit")

        choice = input("\nEnter choice (1-4): ").strip()

        if choice == "1":
            test_full_flow_interactive()
        elif choice == "2":
            test_automated_flow()
        elif choice == "3":
            test_health()
        elif choice == "4":
            print("\n👋 Goodbye!\n")
            break
        else:
            print("Invalid choice. Please enter 1-4.")


if __name__ == "__main__":
    main()
