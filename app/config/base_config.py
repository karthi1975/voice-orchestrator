"""
Base configuration class

Defines common configuration settings for all environments.
"""

import os
from typing import List


class BaseConfig:
    """
    Base configuration class.

    Contains settings common to all environments.
    Subclasses override for environment-specific settings.
    """

    # Application
    APP_NAME: str = "Voice Orchestrator"
    DEBUG: bool = False
    TESTING: bool = False

    # Server
    PORT: int = int(os.getenv("PORT", "6500"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # Challenge settings
    WORDS: List[str] = [
        "apple", "banana", "dolphin", "elephant", "flower",
        "garden", "island", "jungle", "kitchen", "lemon",
        "mountain", "ocean", "piano", "rainbow", "sunset",
        "thunder", "umbrella", "village", "window", "zebra"
    ]

    NUMBERS: List[str] = [
        "one", "two", "three", "four", "five",
        "six", "seven", "eight", "nine", "zero"
    ]

    CHALLENGE_EXPIRY_SECONDS: int = int(os.getenv("CHALLENGE_EXPIRY_SECONDS", "60"))
    MAX_ATTEMPTS: int = int(os.getenv("MAX_ATTEMPTS", "3"))

    # Home Assistant
    HA_URL: str = os.getenv("HA_URL", "http://homeassistant.local:8123")
    HA_WEBHOOK_ID: str = os.getenv("HA_WEBHOOK_ID", "voice_auth_scene")
    TEST_MODE: bool = os.getenv("TEST_MODE", "true").lower() in ("true", "1", "yes")

    # FutureProof Homes
    FUTUREPROOFHOME_ENABLED: bool = os.getenv("FUTUREPROOFHOME_ENABLED", "true").lower() in ("true", "1", "yes")
    DEFAULT_HOME_ID: str = os.getenv("DEFAULT_HOME_ID", "home_1")
    LOG_FPH_REQUESTS: bool = os.getenv("LOG_FPH_REQUESTS", "true").lower() in ("true", "1", "yes")

    # Database (Phase 7)
    USE_DATABASE: bool = os.getenv("USE_DATABASE", "false").lower() in ("true", "1", "yes")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Redis (Phase 7)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_REQUEST_BODY: bool = os.getenv("LOG_REQUEST_BODY", "false").lower() in ("true", "1", "yes")
    LOG_RESPONSE_BODY: bool = os.getenv("LOG_RESPONSE_BODY", "false").lower() in ("true", "1", "yes")

    # Security (future)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    @classmethod
    def get_config_dict(cls) -> dict:
        """
        Get configuration as dictionary.

        Returns:
            Dictionary of configuration values

        Examples:
            >>> config = BaseConfig.get_config_dict()
            >>> print(config['APP_NAME'])
            'Voice Orchestrator'
        """
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if key.isupper() and not key.startswith('_')
        }

    @classmethod
    def validate(cls) -> None:
        """
        Validate configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate required settings
        if cls.USE_DATABASE and not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required when USE_DATABASE is True")

        if not cls.HA_URL:
            raise ValueError("HA_URL is required")

        if not cls.HA_WEBHOOK_ID:
            raise ValueError("HA_WEBHOOK_ID is required")

        # Validate ranges
        if cls.CHALLENGE_EXPIRY_SECONDS < 10:
            raise ValueError("CHALLENGE_EXPIRY_SECONDS must be at least 10 seconds")

        if cls.MAX_ATTEMPTS < 1:
            raise ValueError("MAX_ATTEMPTS must be at least 1")

        if cls.PORT < 1 or cls.PORT > 65535:
            raise ValueError("PORT must be between 1 and 65535")

    @classmethod
    def __repr__(cls) -> str:
        """String representation of configuration."""
        return f"<{cls.__name__} environment>"
