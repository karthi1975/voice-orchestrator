"""
Authentication controller

Handles admin login/logout for the dashboard.
"""

import logging
from typing import Tuple, Any
from flask import request, session, redirect, url_for
from app.controllers.base_controller import BaseController
from app.services.admin_auth_service import AdminAuthService


logger = logging.getLogger(__name__)


class AuthController(BaseController):
    """
    Controller for authentication endpoints.

    Handles:
    - Admin login
    - Admin logout
    - Session management
    """

    def __init__(self, admin_auth_service: AdminAuthService):
        """
        Initialize auth controller.

        Args:
            admin_auth_service: Service for admin authentication
        """
        super().__init__(blueprint_name='auth', url_prefix='/auth')
        self._auth_service = admin_auth_service
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all auth routes."""
        self.blueprint.add_url_rule(
            '/login',
            'login',
            self.login,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/logout',
            'logout',
            self.logout,
            methods=['POST', 'GET']
        )
        self.blueprint.add_url_rule(
            '/check',
            'check',
            self.check_auth,
            methods=['GET']
        )

    def login(self) -> Tuple[Any, int]:
        """
        POST /auth/login - Authenticate admin user.

        Request body:
            {
                "username": "admin",
                "password": "Admin@2024"
            }

        Returns:
            200: Login successful, session created
            401: Invalid credentials
        """
        self.log_request('login')

        try:
            data = self.get_request_json()
            username = data.get('username', '').strip()
            password = data.get('password', '')

            if not username or not password:
                return self.json_response({
                    'success': False,
                    'message': 'Username and password required'
                }, 400)

            # Authenticate
            admin = self._auth_service.authenticate(username, password)

            if admin:
                # Create session
                session['admin_user'] = username
                session['admin_name'] = admin.full_name
                session.permanent = True  # Session persists across browser restarts

                logger.info(f"Admin '{username}' logged in successfully")

                return self.json_response({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'username': admin.username,
                        'full_name': admin.full_name,
                        'email': admin.email
                    }
                }, 200)
            else:
                return self.json_response({
                    'success': False,
                    'message': 'Invalid username or password'
                }, 401)

        except Exception as e:
            logger.error(f"Login error: {str(e)}", exc_info=True)
            return self.json_response({
                'success': False,
                'message': 'Login failed'
            }, 500)

    def logout(self) -> Tuple[Any, int]:
        """
        POST/GET /auth/logout - Logout admin user.

        Returns:
            200: Logout successful
        """
        self.log_request('logout')

        username = session.get('admin_user')
        if username:
            logger.info(f"Admin '{username}' logged out")

        # Clear session
        session.clear()

        return self.json_response({
            'success': True,
            'message': 'Logout successful'
        }, 200)

    def check_auth(self) -> Tuple[Any, int]:
        """
        GET /auth/check - Check if user is authenticated.

        Returns:
            200: User info if authenticated
            401: Not authenticated
        """
        username = session.get('admin_user')

        if username:
            admin = self._auth_service.get_admin_user(username)
            if admin and admin.is_active:
                return self.json_response({
                    'authenticated': True,
                    'user': {
                        'username': admin.username,
                        'full_name': admin.full_name,
                        'email': admin.email
                    }
                }, 200)

        return self.json_response({
            'authenticated': False
        }, 401)
