"""
Flask app factory and dependency injection container

Creates Flask app with proper dependency injection.
"""

import logging
from flask import Flask
from typing import Optional

# Domain
from app.domain.enums import ClientType

# Repositories
from app.repositories.implementations.in_memory_challenge_repo import InMemoryChallengeRepository

# Services
from app.services.challenge_service import ChallengeService, ChallengeSettings
from app.services.authentication_service import AuthenticationService
from app.services.home_automation_service import HomeAutomationService

# Controllers
from app.controllers.alexa_controller import AlexaController
from app.controllers.fph_controller import FutureProofHomesController

# Utils
from app.utils.text_normalizer import TextNormalizer

# Infrastructure
from app.infrastructure.home_assistant.webhook_client import WebhookHomeAssistantClient

# Middleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware


logger = logging.getLogger(__name__)


class DependencyContainer:
    """
    Dependency injection container.

    Wires up all dependencies:
    - Repositories
    - Services
    - Controllers

    Follows Dependency Inversion Principle - high-level modules
    depend on abstractions (interfaces), not concrete implementations.
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize dependency container.

        Args:
            config: Optional configuration dict (uses defaults if not provided)
        """
        self.config = config or self._load_default_config()

        # Initialize components in dependency order
        self._init_infrastructure()
        self._init_repositories()
        self._init_services()
        self._init_controllers()

    def _load_default_config(self) -> dict:
        """
        Load default configuration.

        Loads configuration from new settings system (app/config).
        Configuration is loaded from environment variables and .env files.

        Returns:
            Configuration dictionary

        Examples:
            >>> container = DependencyContainer()
            >>> print(container.config['ha_url'])
            'http://homeassistant.local:8123'
        """
        from app.config.settings import get_settings

        # Load settings from environment-based config
        settings = get_settings()

        return {
            'words': settings.WORDS,
            'numbers': settings.NUMBERS,
            'expiry_seconds': settings.CHALLENGE_EXPIRY_SECONDS,
            'max_attempts': settings.MAX_ATTEMPTS,
            'ha_url': settings.HA_URL,
            'ha_webhook_id': settings.HA_WEBHOOK_ID,
            'test_mode': settings.TEST_MODE
        }

    def _init_infrastructure(self) -> None:
        """Initialize infrastructure layer (external integrations)."""
        from app.infrastructure.home_assistant.client_factory import HomeAssistantClientFactory

        # Legacy single Home Assistant client (backward compatibility)
        self.ha_client = WebhookHomeAssistantClient(
            base_url=self.config['ha_url'],
            webhook_id=self.config['ha_webhook_id'],
            test_mode=self.config.get('test_mode', False)
        )

        # Multi-tenant: Home Assistant client factory
        self.ha_client_factory = HomeAssistantClientFactory(
            test_mode=self.config.get('test_mode', False)
        )

        logger.info("Infrastructure initialized (HA webhook client + factory)")

    def _init_repositories(self) -> None:
        """Initialize repository layer."""
        from app.config.settings import get_settings
        settings = get_settings()

        # Multi-tenant: Switch between in-memory and database storage
        if settings.USE_DATABASE and settings.DATABASE_URL:
            # Use SQLAlchemy repositories with PostgreSQL
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from app.repositories.implementations.sqlalchemy_challenge_repo import SQLAlchemyChallengeRepository
            from app.repositories.implementations.sqlalchemy_user_repo import SQLAlchemyUserRepository
            from app.repositories.implementations.sqlalchemy_home_repo import SQLAlchemyHomeRepository
            from app.repositories.implementations.sqlalchemy_models import Base

            # Create database engine
            engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20
            )

            # Create tables if they don't exist
            Base.metadata.create_all(engine)

            # Create session factory
            SessionLocal = sessionmaker(bind=engine)
            self._db_session = SessionLocal()

            # Create repositories with session
            self.challenge_repository = SQLAlchemyChallengeRepository(self._db_session)
            self.user_repository = SQLAlchemyUserRepository(self._db_session)
            self.home_repository = SQLAlchemyHomeRepository(self._db_session)

            logger.info("Repositories initialized (SQLAlchemy/PostgreSQL)")
        else:
            # Use in-memory repositories (default)
            from app.repositories.implementations.in_memory_user_repo import InMemoryUserRepository
            from app.repositories.implementations.in_memory_home_repo import InMemoryHomeRepository

            self.challenge_repository = InMemoryChallengeRepository()
            self.user_repository = InMemoryUserRepository()
            self.home_repository = InMemoryHomeRepository()
            self._db_session = None

            logger.info("Repositories initialized (in-memory)")

    def _init_services(self) -> None:
        """Initialize service layer."""
        from app.services.user_service import UserService
        from app.services.home_service import HomeService
        from app.config.settings import get_settings
        settings = get_settings()

        # Challenge settings
        self.challenge_settings = ChallengeSettings(
            words=self.config['words'],
            numbers=self.config['numbers'],
            expiry_seconds=self.config['expiry_seconds'],
            max_attempts=self.config['max_attempts']
        )

        # Text normalizer
        text_normalizer = TextNormalizer()

        # Multi-tenant: User and Home services
        self.user_service = UserService(
            user_repository=self.user_repository
        )

        self.home_service = HomeService(
            home_repository=self.home_repository,
            user_repository=self.user_repository
        )

        # Challenge service (depends on repository)
        self.challenge_service = ChallengeService(
            challenge_repository=self.challenge_repository,
            settings=self.challenge_settings,
            text_normalizer=text_normalizer
        )

        # Authentication service (depends on challenge service)
        self.auth_service = AuthenticationService(
            challenge_service=self.challenge_service
        )

        # Home automation service with multi-tenant support
        if settings.USE_DATABASE:
            # Multi-tenant mode: use factory and home service
            self.ha_service = HomeAutomationService(
                home_service=self.home_service,
                client_factory=self.ha_client_factory
            )
            logger.info("Services initialized (multi-tenant mode)")
        else:
            # Legacy mode: use single client
            self.ha_service = HomeAutomationService(
                legacy_client=self.ha_client
            )
            logger.info("Services initialized (legacy mode)")

    def _init_controllers(self) -> None:
        """Initialize controller layer."""
        from app.controllers.admin_controller import AdminController

        # Alexa controller (depends on services)
        self.alexa_controller = AlexaController(
            auth_service=self.auth_service,
            ha_service=self.ha_service,
            url_prefix='/alexa'  # Will be registered as /alexa/v2 in server.py
        )

        # FutureProof Homes controller (depends on services)
        self.fph_controller = FutureProofHomesController(
            auth_service=self.auth_service,
            challenge_settings=self.challenge_settings,
            url_prefix='/futureproofhome'  # Will be registered as /futureproofhome/v2
        )

        # Admin controller for multi-tenant management
        self.admin_controller = AdminController(
            user_service=self.user_service,
            home_service=self.home_service
        )

        logger.info("Controllers initialized (Alexa, FPH, Admin)")


def create_app(config: Optional[dict] = None) -> Flask:
    """
    Flask application factory.

    Creates Flask app with dependency injection.

    Args:
        config: Optional configuration dict

    Returns:
        Configured Flask application

    Examples:
        >>> app = create_app()
        >>> # Or with custom config
        >>> app = create_app({'test_mode': True})
    """
    # Create Flask app
    app = Flask(__name__)

    # Create dependency container
    container = DependencyContainer(config=config)

    # Store container on app for access in routes
    app.container = container

    # Register cleanup handler for database session
    @app.teardown_appcontext
    def cleanup_db_session(exception=None):
        """Close database session on app teardown."""
        if hasattr(container, '_db_session') and container._db_session:
            container._db_session.close()

    # Register middleware (Phase 5)
    RequestLoggerMiddleware(app, log_request_body=False, log_response_body=False)
    ErrorHandlerMiddleware(app)

    # Register blueprints from controllers
    app.register_blueprint(container.alexa_controller.blueprint)
    app.register_blueprint(container.fph_controller.blueprint)
    app.register_blueprint(container.admin_controller.blueprint)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Flask app created with dependency injection and middleware")
    logger.info(f"Registered blueprints: {[bp.name for bp in app.blueprints.values()]}")

    return app
