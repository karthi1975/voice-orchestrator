"""
Configuration settings loader

Loads appropriate configuration based on environment.
"""

import os
from typing import Type, Union

from app.config.base_config import BaseConfig
from app.config.development import DevelopmentConfig
from app.config.production import ProductionConfig


# Configuration mapping
CONFIG_MAP = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': DevelopmentConfig,  # Use dev config for testing
}


def get_config_class(env: str = None) -> Type[BaseConfig]:
    """
    Get configuration class for environment.

    Args:
        env: Environment name (development, production, testing).
             If None, reads from FLASK_ENV environment variable.
             Defaults to 'development' if not set.

    Returns:
        Configuration class for the environment

    Raises:
        ValueError: If environment is invalid

    Examples:
        >>> config_class = get_config_class('production')
        >>> print(config_class.DEBUG)
        False

        >>> config_class = get_config_class()  # Uses FLASK_ENV
        >>> print(config_class.APP_NAME)
        'Voice Orchestrator'
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')

    env = env.lower()

    if env not in CONFIG_MAP:
        raise ValueError(
            f"Invalid environment: {env}. "
            f"Must be one of: {', '.join(CONFIG_MAP.keys())}"
        )

    return CONFIG_MAP[env]


def get_settings(env: str = None) -> Type[BaseConfig]:
    """
    Get validated configuration settings.

    Alias for get_config_class() that also validates the configuration.

    Args:
        env: Environment name (development, production, testing).
             If None, reads from FLASK_ENV environment variable.

    Returns:
        Validated configuration class

    Raises:
        ValueError: If environment is invalid or configuration fails validation

    Examples:
        >>> settings = get_settings('production')
        >>> print(settings.PORT)
        6500
    """
    config_class = get_config_class(env)

    # Validate configuration
    config_class.validate()

    return config_class


def load_env_file(env_file: str = '.env') -> None:
    """
    Load environment variables from .env file.

    Args:
        env_file: Path to .env file (default: '.env')

    Examples:
        >>> load_env_file()  # Loads .env
        >>> load_env_file('.env.production')  # Loads specific env file
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # python-dotenv not installed, skip
        pass


# Auto-load .env file if present
if os.path.exists('.env'):
    load_env_file()
