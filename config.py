"""
Configuration for Alexa Voice Authentication System
"""

# Word and number options for challenge generation
WORDS = [
    "apple", "banana", "dolphin", "elephant", "flower",
    "garden", "island", "jungle", "kitchen", "lemon",
    "mountain", "ocean", "piano", "rainbow", "sunset",
    "thunder", "umbrella", "village", "window", "zebra"
]

NUMBERS = [
    "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "zero"
]

# Challenge settings
CHALLENGE_EXPIRY_SECONDS = 60
MAX_ATTEMPTS = 3

# Home Assistant configuration
HA_URL = "http://homeassistant.local:8123"
HA_WEBHOOK_ID = "voice_auth_scene"

# Server configuration
PORT = 6500
DEBUG = True

# Test mode (set to True to test without Home Assistant)
TEST_MODE = True  # Set to False when you have Home Assistant running

# ============================================================================
# FUTUREPROOFHOME CONFIGURATION
# ============================================================================

# Enable/disable FutureProof Homes integration
FUTUREPROOFHOME_ENABLED = True

# Default home_id if not provided in requests
DEFAULT_HOME_ID = "home_1"

# Logging for FutureProof Homes requests
LOG_FPH_REQUESTS = True
