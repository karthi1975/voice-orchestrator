"""
OAuth controller for Alexa account linking

Handles the OAuth2 authorization flow for linking Alexa
accounts to Voice Guardian MCS homes.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Tuple, Any, Dict

from flask import request, redirect, send_from_directory
from app.controllers.base_controller import BaseController
from app.services.oauth_service import OAuthService
from app.services.home_service import HomeService


logger = logging.getLogger(__name__)

# Temporary storage for authorization codes.
# Maps auth_code -> {"home_id": str, "expires_at": datetime}
_auth_codes: Dict[str, dict] = {}

# Valid PIN for account linking (will be made configurable later)
_VALID_PIN = "1234"

# Authorization code TTL
_AUTH_CODE_TTL = timedelta(minutes=5)


class OAuthController(BaseController):
    """
    Controller for OAuth2 account linking endpoints.

    Handles:
    - Authorization page (GET /oauth/authorize)
    - Login form submission (POST /oauth/authorize)
    - Token exchange (POST /oauth/token)
    """

    def __init__(self, oauth_service: OAuthService, home_service: HomeService):
        """
        Initialize OAuth controller.

        Args:
            oauth_service: Service for OAuth token management
            home_service: Service for home lookup/validation
        """
        super().__init__(blueprint_name='oauth', url_prefix='/oauth')
        self._oauth_service = oauth_service
        self._home_service = home_service
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all OAuth routes."""
        self.blueprint.add_url_rule(
            '/authorize',
            'authorize',
            self.authorize,
            methods=['GET', 'POST']
        )
        self.blueprint.add_url_rule(
            '/token',
            'token',
            self.token,
            methods=['POST']
        )

    def authorize(self) -> Any:
        """
        GET/POST /oauth/authorize - Account linking authorization.

        GET: Render login form with Amazon redirect params as hidden fields.
        POST: Validate credentials and redirect back to Amazon with auth code.
        """
        self.log_request('authorize')

        if request.method == 'GET':
            return self._render_login_page()
        else:
            return self._process_login()

    def _render_login_page(self) -> Any:
        """
        Serve the OAuth login page, passing Amazon's query params.

        Query params from Amazon:
            client_id, redirect_uri, state, response_type
        """
        redirect_uri = request.args.get('redirect_uri', '')
        state = request.args.get('state', '')

        logger.info(
            f"Rendering OAuth login page "
            f"(redirect_uri={redirect_uri[:50]}..., state={state[:20]}...)"
        )

        static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'static'
        )
        return send_from_directory(static_dir, 'oauth_login.html')

    def _process_login(self) -> Any:
        """
        Process login form submission and redirect to Amazon.

        Form data: home_id, pin, redirect_uri, state
        """
        home_id = request.form.get('home_id', '').strip().lower()
        pin = request.form.get('pin', '')
        redirect_uri = request.form.get('redirect_uri', '')
        state = request.form.get('state', '')

        # Validate required fields
        if not home_id or not pin:
            logger.warning("OAuth login: missing home_id or pin")
            return self.error_response("Home ID and PIN are required", 400)

        if not redirect_uri:
            logger.warning("OAuth login: missing redirect_uri")
            return self.error_response("Missing redirect_uri", 400)

        # Validate PIN
        if pin != _VALID_PIN:
            logger.warning(f"OAuth login: invalid PIN for home_id={home_id}")
            return self.error_response("Invalid PIN", 401)

        # Validate home exists
        try:
            self._home_service.get_home(home_id)
        except ValueError:
            logger.warning(f"OAuth login: home not found: {home_id}")
            return self.error_response("Home not found", 404)

        # Generate authorization code
        auth_code = str(uuid.uuid4())
        _auth_codes[auth_code] = {
            "home_id": home_id,
            "expires_at": datetime.now() + _AUTH_CODE_TTL
        }

        logger.info(f"OAuth login: generated auth code for home_id={home_id}")

        # Redirect back to Amazon with code and state
        separator = '&' if '?' in redirect_uri else '?'
        target_url = f"{redirect_uri}{separator}code={auth_code}&state={state}"
        return redirect(target_url)

    def token(self) -> Tuple[Any, int]:
        """
        POST /oauth/token - Token exchange endpoint.

        Handles authorization_code and refresh_token grant types.
        """
        self.log_request('token')

        # Accept both form data and JSON
        if request.is_json:
            data = request.get_json(force=True)
        else:
            data = request.form.to_dict()

        grant_type = data.get('grant_type', '')

        if grant_type == 'authorization_code':
            return self._handle_authorization_code(data)
        elif grant_type == 'refresh_token':
            return self._handle_refresh_token(data)
        else:
            logger.warning(f"OAuth token: unsupported grant_type={grant_type}")
            return self.error_response("Unsupported grant_type", 400)

    def _handle_authorization_code(self, data: dict) -> Tuple[Any, int]:
        """Exchange authorization code for tokens."""
        code = data.get('code', '')

        if not code:
            return self.error_response("Missing authorization code", 400)

        # Look up and validate the auth code
        code_data = _auth_codes.get(code)
        if code_data is None:
            logger.warning("OAuth token: invalid authorization code")
            return self.error_response("Invalid authorization code", 400)

        # Check expiry
        if datetime.now() > code_data["expires_at"]:
            del _auth_codes[code]
            logger.warning("OAuth token: expired authorization code")
            return self.error_response("Authorization code expired", 400)

        # Consume the code (one-time use)
        home_id = code_data["home_id"]
        del _auth_codes[code]

        # Create OAuth token
        token = self._oauth_service.create_token(home_id)

        logger.info(f"OAuth token: issued tokens for home_id={home_id}")

        return self.json_response({
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "token_type": "bearer",
            "expires_in": 31536000
        })

    def _handle_refresh_token(self, data: dict) -> Tuple[Any, int]:
        """Refresh an expired access token."""
        refresh_token = data.get('refresh_token', '')

        if not refresh_token:
            return self.error_response("Missing refresh_token", 400)

        token = self._oauth_service.refresh_access_token(refresh_token)

        if token is None:
            logger.warning("OAuth token: invalid refresh_token")
            return self.error_response("Invalid refresh_token", 400)

        logger.info(f"OAuth token: refreshed tokens for home_id={token.home_id}")

        return self.json_response({
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "token_type": "bearer",
            "expires_in": 31536000
        })
