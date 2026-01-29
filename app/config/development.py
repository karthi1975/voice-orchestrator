"""
Development configuration

Extends base configuration with development-specific settings.
"""

from app.config.base_config import BaseConfig


class DevelopmentConfig(BaseConfig):
    """
    Development environment configuration.

    Optimized for local development with verbose logging,
    test mode enabled, and relaxed validation.
    """

    # Application
    DEBUG: bool = True
    TESTING: bool = False

    # Development-specific defaults
    TEST_MODE: bool = True  # Always use test mode in development
    LOG_LEVEL: str = "DEBUG"
    LOG_REQUEST_BODY: bool = True
    LOG_RESPONSE_BODY: bool = True
    LOG_FPH_REQUESTS: bool = True

    # Relaxed validation for development
    @classmethod
    def validate(cls) -> None:
        """
        Validate development configuration.

        Development has relaxed validation rules.
        Database and Redis not required.
        """
        # Only validate HA settings
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
        return "<DevelopmentConfig environment>"
