"""
Simple test script to verify challenge system functionality
Run this to test the challenge generation and validation without Alexa
"""

from challenge import (
    generate_challenge,
    store_challenge,
    validate_challenge,
    normalize_response
)
import uuid


def test_challenge_generation():
    """Test challenge generation"""
    print("Testing challenge generation...")
    for i in range(5):
        challenge = generate_challenge()
        print(f"  Generated challenge {i+1}: {challenge}")
    print("✓ Challenge generation working\n")


def test_normalization():
    """Test response normalization"""
    print("Testing response normalization...")
    test_cases = [
        ("ocean 4", "ocean four"),
        ("ocean for", "ocean four"),
        ("mountain to", "mountain two"),
        ("mountain too", "mountain two"),
        ("OCEAN FOUR", "ocean four"),
        ("  ocean   four  ", "ocean four"),
    ]

    all_passed = True
    for input_text, expected in test_cases:
        result = normalize_response(input_text)
        passed = result == expected
        status = "✓" if passed else "✗"
        print(f"  {status} '{input_text}' → '{result}' (expected '{expected}')")
        if not passed:
            all_passed = False

    if all_passed:
        print("✓ All normalization tests passed\n")
    else:
        print("✗ Some normalization tests failed\n")


def test_validation_flow():
    """Test complete validation flow"""
    print("Testing validation flow...")

    # Create a session
    session_id = str(uuid.uuid4())
    challenge = "ocean four"

    # Store challenge
    store_challenge(session_id, challenge)
    print(f"  Stored challenge: {challenge}")

    # Test correct response
    valid, message, intent = validate_challenge(session_id, "ocean four")
    print(f"  Correct response: {valid} - {message}")

    # Test with new session for wrong response
    session_id = str(uuid.uuid4())
    store_challenge(session_id, "mountain seven")

    valid, message, intent = validate_challenge(session_id, "ocean four")
    print(f"  Wrong response: {valid} - {message}")

    print("✓ Validation flow working\n")


def test_variation_handling():
    """Test handling of spoken variations"""
    print("Testing spoken variation handling...")

    session_id = str(uuid.uuid4())
    store_challenge(session_id, "ocean four")

    test_inputs = [
        "ocean four",
        "ocean 4",
        "ocean for",
        "OCEAN FOUR",
        "  ocean   four  "
    ]

    for test_input in test_inputs:
        session_id = str(uuid.uuid4())
        store_challenge(session_id, "ocean four")
        valid, message, intent = validate_challenge(session_id, test_input)
        status = "✓" if valid else "✗"
        print(f"  {status} '{test_input}' → {valid}")

    print()


def interactive_test():
    """Interactive test mode"""
    print("Interactive test mode")
    print("=" * 50)

    session_id = str(uuid.uuid4())
    challenge = generate_challenge()

    print(f"\nChallenge: {challenge}")
    print("Please type what you would say:\n")

    user_input = input("> ")
    valid, message, intent = validate_challenge(session_id, user_input)

    print(f"\nResult: {message}")
    print(f"Valid: {valid}\n")


if __name__ == "__main__":
    print("=" * 50)
    print("Alexa Voice Auth - Challenge System Tests")
    print("=" * 50)
    print()

    test_challenge_generation()
    test_normalization()
    test_validation_flow()
    test_variation_handling()

    # Uncomment to enable interactive testing
    # interactive_test()

    print("=" * 50)
    print("All tests completed!")
    print("=" * 50)
