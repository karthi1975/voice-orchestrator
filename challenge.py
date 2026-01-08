"""
Challenge generation and validation for voice authentication
"""

import random
import time
from typing import Optional, Tuple
from config import WORDS, NUMBERS, CHALLENGE_EXPIRY_SECONDS, MAX_ATTEMPTS

# In-memory storage for challenges
# In production, use Redis or a database
challenges = {}


def generate_challenge() -> str:
    """
    Generate a random challenge phrase combining a word and number.

    Returns:
        str: Challenge phrase like "ocean four"
    """
    word = random.choice(WORDS)
    number = random.choice(NUMBERS)
    return f"{word} {number}"


def store_challenge(session_id: str, challenge: str) -> None:
    """
    Store a challenge for a session with timestamp and attempt count.

    Args:
        session_id: Unique session identifier
        challenge: Challenge phrase to store
    """
    challenges[session_id] = {
        'challenge': challenge.lower(),
        'timestamp': time.time(),
        'attempts': 0
    }


def validate_challenge(session_id: str, spoken_response: str) -> Tuple[bool, str]:
    """
    Validate the spoken response against the stored challenge.

    Args:
        session_id: Unique session identifier
        spoken_response: User's spoken response

    Returns:
        Tuple of (is_valid, message)
    """
    if session_id not in challenges:
        return False, "No active challenge found. Please start over."

    challenge_data = challenges[session_id]

    # Check if challenge has expired
    elapsed = time.time() - challenge_data['timestamp']
    if elapsed > CHALLENGE_EXPIRY_SECONDS:
        del challenges[session_id]
        return False, "Challenge expired. Please start over."

    # Check attempt count
    challenge_data['attempts'] += 1
    if challenge_data['attempts'] > MAX_ATTEMPTS:
        del challenges[session_id]
        return False, "Maximum attempts exceeded. Please start over."

    # Normalize and compare
    normalized_response = normalize_response(spoken_response)
    expected = challenge_data['challenge']

    if normalized_response == expected:
        # Clean up successful challenge
        del challenges[session_id]
        return True, "Voice verified successfully"
    else:
        remaining = MAX_ATTEMPTS - challenge_data['attempts']
        if remaining > 0:
            return False, f"Incorrect response. {remaining} attempts remaining."
        else:
            del challenges[session_id]
            return False, "Maximum attempts exceeded. Please start over."


def normalize_response(text: str) -> str:
    """
    Normalize spoken text to handle variations.

    Handles:
    - "4" → "four"
    - "for" → "four"
    - "to" → "two"
    - "too" → "two"
    - Lowercase conversion
    - Extra whitespace removal

    Args:
        text: Raw spoken text

    Returns:
        Normalized text
    """
    # Convert to lowercase and strip
    text = text.lower().strip()

    # Replace common spoken variations
    replacements = {
        ' for ': ' four ',
        ' to ': ' two ',
        ' too ': ' two ',
        ' won ': ' one ',
        ' ate ': ' eight ',
    }

    # Add spaces for replacements to work
    text = f" {text} "

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Handle digits to words
    digit_map = {
        '0': 'zero', '1': 'one', '2': 'two', '3': 'three',
        '4': 'four', '5': 'five', '6': 'six', '7': 'seven',
        '8': 'eight', '9': 'nine'
    }

    for digit, word in digit_map.items():
        text = text.replace(f' {digit} ', f' {word} ')

    # Clean up extra whitespace
    return ' '.join(text.split())


def clear_expired_challenges() -> int:
    """
    Clean up expired challenges from memory.

    Returns:
        Number of challenges cleared
    """
    current_time = time.time()
    expired = [
        session_id for session_id, data in challenges.items()
        if current_time - data['timestamp'] > CHALLENGE_EXPIRY_SECONDS
    ]

    for session_id in expired:
        del challenges[session_id]

    return len(expired)
