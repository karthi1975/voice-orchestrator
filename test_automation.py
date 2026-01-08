#!/usr/bin/env python3
"""
Test script to simulate the full authentication flow without Alexa
"""

from challenge import generate_challenge, store_challenge, validate_challenge
from home_assistant import trigger_scene, test_connection
import uuid


def simulate_flow():
    """Simulate a complete voice authentication flow"""

    print("\n" + "="*60)
    print("🎤 SIMULATING ALEXA VOICE AUTHENTICATION FLOW")
    print("="*60)

    # Step 1: Test Home Assistant connection
    print("\n[Step 1] Testing Home Assistant connection...")
    success, message = test_connection()
    print(f"Result: {message}\n")

    # Step 2: User says "night scene"
    print("[Step 2] User: 'Alexa, open home security'")
    print("Alexa: 'Home security activated. Say night scene to begin.'\n")

    print("[Step 3] User: 'night scene'")
    session_id = str(uuid.uuid4())
    challenge = generate_challenge()
    store_challenge(session_id, challenge)
    print(f"Alexa: 'Security check required. Please say: {challenge}'\n")

    # Step 4: User repeats the challenge
    print(f"[Step 4] User: '{challenge}'")
    is_valid, validation_msg, _ = validate_challenge(session_id, challenge)
    print(f"Validation: {validation_msg}\n")

    # Step 5: If valid, trigger the scene
    if is_valid:
        print("[Step 5] Triggering Home Assistant scene...")
        success, scene_msg = trigger_scene("night_scene")

        if success:
            print(f"Alexa: 'Voice verified. {scene_msg}'")
        else:
            print(f"Alexa: 'Voice verified, but scene activation failed: {scene_msg}'")
    else:
        print(f"Alexa: '{validation_msg}'")

    print("\n" + "="*60)
    print("✓ SIMULATION COMPLETE")
    print("="*60 + "\n")


def test_wrong_response():
    """Test what happens with wrong response"""

    print("\n" + "="*60)
    print("❌ SIMULATING FAILED AUTHENTICATION")
    print("="*60 + "\n")

    session_id = str(uuid.uuid4())
    challenge = generate_challenge()
    store_challenge(session_id, challenge)

    print(f"Alexa: 'Security check required. Please say: {challenge}'")
    print("User: 'wrong phrase'\n")

    is_valid, validation_msg, _ = validate_challenge(session_id, "wrong phrase")
    print(f"Result: {validation_msg}")

    if not is_valid:
        print("Alexa: 'Incorrect response. Please try saying night scene again.'\n")

    print("="*60 + "\n")


def test_variations():
    """Test spoken variations"""

    print("\n" + "="*60)
    print("🔊 TESTING SPOKEN VARIATIONS")
    print("="*60 + "\n")

    test_cases = [
        ("ocean four", "ocean 4"),
        ("mountain two", "mountain to"),
        ("sunset seven", "sunset 7"),
    ]

    for expected, spoken in test_cases:
        session_id = str(uuid.uuid4())
        store_challenge(session_id, expected)

        print(f"Challenge: '{expected}'")
        print(f"User says: '{spoken}'")

        is_valid, msg, _ = validate_challenge(session_id, spoken)
        status = "✓" if is_valid else "✗"
        print(f"{status} {msg}\n")

    print("="*60 + "\n")


if __name__ == "__main__":
    print("\n" + "*"*60)
    print("ALEXA VOICE AUTHENTICATION - TEST SUITE")
    print("*"*60)

    # Test successful flow
    simulate_flow()

    # Test failed authentication
    test_wrong_response()

    # Test variations
    test_variations()

    print("*"*60)
    print("ALL TESTS COMPLETED")
    print("*"*60 + "\n")

    print("💡 TIP: The server will show these same messages when you")
    print("   interact with it through Alexa or the API.\n")
