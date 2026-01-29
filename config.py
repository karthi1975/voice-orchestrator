"""
Configuration for Alexa Voice Authentication System

LEGACY MODULE - Redirects to new configuration system.

This module is maintained for backward compatibility with existing code.
New code should use: from app.config.settings import get_settings

All configuration is now loaded from environment variables and .env files.
See .env.example for available configuration options.
"""

import warnings
from app.config.settings import get_settings

# Show deprecation warning once
warnings.warn(
    "config.py is deprecated. Use 'from app.config.settings import get_settings' instead. "
    "This legacy module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

# Load configuration from new system
_settings = get_settings()

# ============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# ============================================================================
# Expose old variable names for existing code

# Word and number options for challenge generation
WORDS = _settings.WORDS
NUMBERS = _settings.NUMBERS

# Challenge settings
CHALLENGE_EXPIRY_SECONDS = _settings.CHALLENGE_EXPIRY_SECONDS
MAX_ATTEMPTS = _settings.MAX_ATTEMPTS

# Home Assistant configuration
HA_URL = _settings.HA_URL
HA_WEBHOOK_ID = _settings.HA_WEBHOOK_ID
TEST_MODE = _settings.TEST_MODE

# Server configuration
PORT = _settings.PORT
DEBUG = _settings.DEBUG

# FutureProof Homes configuration
FUTUREPROOFHOME_ENABLED = _settings.FUTUREPROOFHOME_ENABLED
DEFAULT_HOME_ID = _settings.DEFAULT_HOME_ID
LOG_FPH_REQUESTS = _settings.LOG_FPH_REQUESTS
