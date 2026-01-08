"""
Challenge generation and validation for voice authentication
"""

import random
import time
from typing import Optional, Tuple
from config import WORDS, NUMBERS, CHALLENGE_EXPIRY_SECONDS, MAX_ATTEMPTS

# In-memory storage for challenges
# Multi-client support: separate namespaces for different integration types
# In production, use Redis or a database
challenges = {
    'alexa': {},           # Alexa Skill integration (session-based)
    'futureproofhome': {}  # FutureProof Homes integration (home_id-based)
}


def generate_challenge() -> str:
    """
    Generate a random challenge phrase combining a word and number.

    Returns:
        str: Challenge phrase like "ocean four"
    """
    word = random.choice(WORDS)
    number = random.choice(NUMBERS)
    return f"{word} {number}"


def store_challenge(identifier: str, challenge: str, client_type: str = 'alexa', intent: Optional[str] = None) -> None:
    """
    Store a challenge for a session/home with timestamp and attempt count.

    Supports multiple client types with isolated storage namespaces.

    Args:
        identifier: Unique identifier (session_id for Alexa, home_id for FutureProof Homes)
        challenge: Challenge phrase to store
        client_type: Client type ('alexa' or 'futureproofhome'), defaults to 'alexa'
        intent: Optional intent to execute after verification (used by FutureProof Homes)
    """
    if client_type not in challenges:
        challenges[client_type] = {}

    challenges[client_type][identifier] = {
        'challenge': challenge.lower(),
        'timestamp': time.time(),
        'attempts': 0,
        'intent': intent
    }


def validate_challenge(identifier: str, spoken_response: str, client_type: str = 'alexa') -> Tuple[bool, str, Optional[str]]:
    """
    Validate the spoken response against the stored challenge.

    Supports multiple client types with isolated storage namespaces.

    Args:
        identifier: Unique identifier (session_id for Alexa, home_id for FutureProof Homes)
        spoken_response: User's spoken response
        client_type: Client type ('alexa' or 'futureproofhome'), defaults to 'alexa'

    Returns:
        Tuple of (is_valid, message, intent)
        - is_valid: True if challenge passed
        - message: Human-readable status message
        - intent: The stored intent (if any) for successful validation
    """
    if client_type not in challenges or identifier not in challenges[client_type]:
        return False, "No active challenge found. Please start over.", None

    challenge_data = challenges[client_type][identifier]

    # Check if challenge has expired
    elapsed = time.time() - challenge_data['timestamp']
    if elapsed > CHALLENGE_EXPIRY_SECONDS:
        del challenges[client_type][identifier]
        return False, "Challenge expired. Please start over.", None

    # Check attempt count
    challenge_data['attempts'] += 1
    if challenge_data['attempts'] > MAX_ATTEMPTS:
        del challenges[client_type][identifier]
        return False, "Maximum attempts exceeded. Please start over.", None

    # Normalize and compare
    normalized_response = normalize_response(spoken_response)
    expected = challenge_data['challenge']

    if normalized_response == expected:
        # Clean up successful challenge and return intent
        intent = challenge_data.get('intent')
        del challenges[client_type][identifier]
        return True, "Voice verified successfully", intent
    else:
        remaining = MAX_ATTEMPTS - challenge_data['attempts']
        if remaining > 0:
            return False, f"Incorrect response. {remaining} attempts remaining.", None
        else:
            del challenges[client_type][identifier]
            return False, "Maximum attempts exceeded. Please start over.", None


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


def clear_challenge(identifier: str, client_type: str = 'alexa') -> bool:
    """
    Clear a specific challenge from storage.

    Args:
        identifier: Unique identifier to clear
        client_type: Client type ('alexa' or 'futureproofhome'), defaults to 'alexa'

    Returns:
        True if challenge was found and cleared, False otherwise
    """
    if client_type in challenges and identifier in challenges[client_type]:
        del challenges[client_type][identifier]
        return True
    return False


def get_challenge_data(identifier: str, client_type: str = 'alexa') -> Optional[dict]:
    """
    Get challenge data for a specific identifier.

    Args:
        identifier: Unique identifier
        client_type: Client type ('alexa' or 'futureproofhome'), defaults to 'alexa'

    Returns:
        Challenge data dict or None if not found
    """
    if client_type in challenges and identifier in challenges[client_type]:
        return challenges[client_type][identifier].copy()
    return None


def get_all_challenges(client_type: Optional[str] = None) -> dict:
    """
    Get all challenges, optionally filtered by client type.

    Args:
        client_type: Optional client type filter ('alexa' or 'futureproofhome')

    Returns:
        Dict of challenges (all or filtered by client type)
    """
    if client_type:
        return challenges.get(client_type, {}).copy()
    return {k: v.copy() for k, v in challenges.items()}


def clear_expired_challenges(client_type: Optional[str] = None) -> int:
    """
    Clean up expired challenges from memory.

    Args:
        client_type: Optional client type to clean ('alexa' or 'futureproofhome')
                    If None, cleans all client types

    Returns:
        Number of challenges cleared
    """
    current_time = time.time()
    cleared_count = 0

    client_types_to_clean = [client_type] if client_type else challenges.keys()

    for ct in client_types_to_clean:
        if ct not in challenges:
            continue

        expired = [
            identifier for identifier, data in challenges[ct].items()
            if current_time - data['timestamp'] > CHALLENGE_EXPIRY_SECONDS
        ]

        for identifier in expired:
            del challenges[ct][identifier]
            cleared_count += 1

    return cleared_count
