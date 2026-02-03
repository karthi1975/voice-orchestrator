"""
Admin authentication service

Handles admin user authentication and session management.
"""

import logging
from typing import Optional
from app.repositories.admin_user_repository import AdminUserRepository
from app.domain.admin_user import AdminUser


logger = logging.getLogger(__name__)


class AdminAuthService:
    """
    Service for admin authentication.

    Handles:
    - User login validation
    - Session management
    """

    def __init__(self, admin_user_repository: AdminUserRepository):
        """
        Initialize authentication service.

        Args:
            admin_user_repository: Repository for admin users
        """
        self._admin_repo = admin_user_repository

    def authenticate(self, username: str, password: str) -> Optional[AdminUser]:
        """
        Authenticate admin user with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            AdminUser if authentication successful, None otherwise
        """
        try:
            admin = self._admin_repo.authenticate(username, password)
            if admin:
                logger.info(f"Admin user '{username}' logged in successfully")
                return admin
            else:
                logger.warning(f"Failed login attempt for username: {username}")
                return None
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}", exc_info=True)
            return None

    def get_admin_user(self, username: str) -> Optional[AdminUser]:
        """
        Get admin user by username.

        Args:
            username: Username

        Returns:
            AdminUser if found, None otherwise
        """
        return self._admin_repo.get_by_username(username)
