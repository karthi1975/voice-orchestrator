"""
Production configuration

Extends base configuration with production-specific settings.
"""

import os
from app.config.base_config import BaseConfig


class ProductionConfig(BaseConfig):
    """
    Production environment configuration.

    Optimized for production deployment with strict validation,
    minimal logging, and security hardening.
    """

    # Application
    DEBUG: bool = False
    TESTING: bool = False

    # Production-specific defaults
    TEST_MODE: bool = False  # Never use test mode in production
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_REQUEST_BODY: bool = False  # Security: don't log request bodies
    LOG_RESPONSE_BODY: bool = False  # Security: don't log response bodies
    LOG_FPH_REQUESTS: bool = False  # Minimize logging overhead

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")  # Must be set in production

    @classmethod
    def validate(cls) -> None:
        """
        Validate production configuration.

        Production has strict validation rules.
        All required settings must be present.
        """
        # Call base validation
        super().validate()

        # Additional production-specific validation
        if not cls.SECRET_KEY or cls.SECRET_KEY == "dev-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY must be set to a secure value in production. "
                "Generate with: openssl rand -hex 32"
            )

        if cls.DEBUG:
            raise ValueError("DEBUG must be False in production")

        if cls.TEST_MODE:
            raise ValueError("TEST_MODE must be False in production")

        # Warn if using default HA URL
        if cls.HA_URL == "http://homeassistant.local:8123":
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "Using default HA_URL in production. "
                "Set HA_URL environment variable to your Home Assistant URL."
            )

    @classmethod
    def __repr__(cls) -> str:
        """String representation of configuration."""
        return "<ProductionConfig environment>"
