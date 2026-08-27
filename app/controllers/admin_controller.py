"""
Admin controller for user and home management

REST API endpoints for administrative operations.
"""

import json
import logging
import os
import time as _time
from typing import Tuple, Any, Optional

import requests as _requests
from flask import request
from app.controllers.base_controller import BaseController
from app.services.user_service import UserService
from app.services.home_service import HomeService
from app.services.alexa_mapping_service import AlexaMappingService
from app.services.scene_webhook_mapping_service import SceneWebhookMappingService
from app.dto.requests.admin_request import (
    CreateUserRequest,
    UpdateUserRequest,
    CreateHomeRequest,
    UpdateHomeRequest,
    CreateAlexaMappingRequest,
    UpdateAlexaMappingRequest,
    CreateSceneWebhookMappingRequest,
    UpdateSceneWebhookMappingRequest
)
from app.dto.responses.admin_response import (
    UserResponse,
    HomeResponse,
    UserListResponse,
    HomeListResponse,
    AlexaMappingResponse,
    AlexaMappingListResponse,
    SceneWebhookMappingResponse,
    SceneWebhookMappingListResponse,
    ErrorResponse
)


logger = logging.getLogger(__name__)


class AdminController(BaseController):
    """
    Controller for admin API endpoints.

    Provides CRUD operations for:
    - User management
    - Home management
    """

    def __init__(
        self,
        user_service: UserService,
        home_service: HomeService,
        alexa_mapping_service: AlexaMappingService,
        scene_mapping_service: SceneWebhookMappingService = None
    ):
        """
        Initialize admin controller.

        Args:
            user_service: Service for user operations
            home_service: Service for home operations
            alexa_mapping_service: Service for Alexa mapping operations
            scene_mapping_service: Service for scene webhook mapping operations
        """
        super().__init__(blueprint_name='admin', url_prefix='/admin')
        self._user_service = user_service
        self._home_service = home_service
        self._alexa_mapping_service = alexa_mapping_service
        self._scene_mapping_service = scene_mapping_service
        self._register_routes()

    def _register_routes(self) -> None:
        """Register all admin routes."""

        # User endpoints
        self.blueprint.add_url_rule(
            '/users',
            'create_user',
            self.create_user,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/users',
            'list_users',
            self.list_users,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/users/<user_id>',
            'get_user',
            self.get_user,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/users/<user_id>',
            'update_user',
            self.update_user,
            methods=['PUT']
        )
        self.blueprint.add_url_rule(
            '/users/<user_id>',
            'delete_user',
            self.delete_user,
            methods=['DELETE']
        )
        self.blueprint.add_url_rule(
            '/users/<user_id>/password',
            'set_user_password',
            self.set_user_password,
            methods=['PUT']
        )
        self.blueprint.add_url_rule(
            '/users/pending',
            'list_pending_users',
            self.list_pending_users,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/users/<user_id>/activate',
            'activate_user',
            self.activate_user,
            methods=['POST']
        )

        # Home endpoints
        self.blueprint.add_url_rule(
            '/homes',
            'create_home',
            self.create_home,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/homes',
            'list_homes',
            self.list_homes,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>',
            'get_home',
            self.get_home,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>',
            'update_home',
            self.update_home,
            methods=['PUT']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>',
            'delete_home',
            self.delete_home,
            methods=['DELETE']
        )
        self.blueprint.add_url_rule(
            '/users/<user_id>/homes',
            'get_user_homes',
            self.get_user_homes,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>/token',
            'set_home_token',
            self.set_home_token,
            methods=['PUT']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>/test-connection',
            'test_home_connection',
            self.test_home_connection,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>/test-webhook',
            'test_home_webhook',
            self.test_home_webhook,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>/test-mode',
            'toggle_test_mode',
            self.toggle_test_mode,
            methods=['POST']
        )

        # Alexa mapping endpoints
        self.blueprint.add_url_rule(
            '/alexa-mappings',
            'create_alexa_mapping',
            self.create_alexa_mapping,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/alexa-mappings',
            'list_alexa_mappings',
            self.list_alexa_mappings,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/alexa-mappings/<path:alexa_user_id>',
            'get_alexa_mapping',
            self.get_alexa_mapping,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/alexa-mappings/<path:alexa_user_id>',
            'update_alexa_mapping',
            self.update_alexa_mapping,
            methods=['PUT']
        )
        self.blueprint.add_url_rule(
            '/alexa-mappings/<path:alexa_user_id>',
            'delete_alexa_mapping',
            self.delete_alexa_mapping,
            methods=['DELETE']
        )
        self.blueprint.add_url_rule(
            '/unmapped-users',
            'get_unmapped_users',
            self.get_unmapped_users,
            methods=['GET']
        )

        # Scene webhook mapping endpoints
        self.blueprint.add_url_rule(
            '/scene-mappings',
            'create_scene_mapping',
            self.create_scene_mapping,
            methods=['POST']
        )
        self.blueprint.add_url_rule(
            '/scene-mappings',
            'list_scene_mappings',
            self.list_scene_mappings,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/homes/<home_id>/scenes',
            'list_home_scenes',
            self.list_home_scenes,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/scene-mappings/<mapping_id>',
            'get_scene_mapping',
            self.get_scene_mapping,
            methods=['GET']
        )
        self.blueprint.add_url_rule(
            '/scene-mappings/<mapping_id>',
            'update_scene_mapping',
            self.update_scene_mapping,
            methods=['PUT']
        )
        self.blueprint.add_url_rule(
            '/scene-mappings/<mapping_id>',
            'delete_scene_mapping',
            self.delete_scene_mapping,
            methods=['DELETE']
        )

    # ========== User Endpoints ==========

    def create_user(self) -> Tuple[Any, int]:
        """
        POST /admin/users - Create new user.

        Request body:
            {
                "username": "john_doe",
                "full_name": "John Doe",
                "email": "john@example.com"  # optional
            }

        Returns:
            201: User created
            400: Validation error
        """
        self.log_request('create_user')

        try:
            data = self.get_request_json()
            req = CreateUserRequest.from_dict(data)
            req.validate()

            user = self._user_service.create_user(
                username=req.username,
                full_name=req.full_name,
                email=req.email,
                user_id=req.user_id,
                password=req.password
            )

            response = UserResponse.from_model(user)
            logger.info(f"User created: {user.user_id}")
            return self.json_response(response.to_dict(), 201)

        except ValueError as e:
            logger.warning(f"Failed to create user: {str(e)}")
            return self.error_response(str(e), 400)

    def list_users(self) -> Tuple[Any, int]:
        """
        GET /admin/users - List all users.

        Query parameters:
            active_only: boolean (default: false)

        Returns:
            200: List of users
        """
        self.log_request('list_users')

        active_only = request.args.get('active_only', 'false').lower() == 'true'
        users = self._user_service.list_users(active_only=active_only)

        response = UserListResponse.from_models(users)
        return self.json_response(response.to_dict(), 200)

    def get_user(self, user_id: str) -> Tuple[Any, int]:
        """
        GET /admin/users/{user_id} - Get user details.

        Args:
            user_id: User ID

        Returns:
            200: User details
            404: User not found
        """
        self.log_request(f'get_user:{user_id}')

        try:
            user = self._user_service.get_user(user_id)
            response = UserResponse.from_model(user)
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            return self.error_response(str(e), 404)

    def update_user(self, user_id: str) -> Tuple[Any, int]:
        """
        PUT /admin/users/{user_id} - Update user.

        Args:
            user_id: User ID

        Request body:
            {
                "username": "new_username",  # optional
                "full_name": "New Name",      # optional
                "email": "new@example.com"    # optional
            }

        Returns:
            200: User updated
            404: User not found
            400: Validation error
        """
        self.log_request(f'update_user:{user_id}')

        try:
            data = self.get_request_json()
            req = UpdateUserRequest.from_dict(data)

            user = self._user_service.update_user(
                user_id=user_id,
                username=req.username,
                full_name=req.full_name,
                email=req.email
            )

            response = UserResponse.from_model(user)
            logger.info(f"User updated: {user_id}")
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            logger.warning(f"Failed to update user {user_id}: {str(e)}")
            return self.error_response(str(e), 404)

    def set_user_password(self, user_id: str) -> Tuple[Any, int]:
        """
        PUT /admin/users/{user_id}/password - Set or reset mobile-login password.

        Request body:
            {
                "password": "new-password"
            }

        Returns:
            200: Password set
            400: Validation error
            404: User not found
        """
        self.log_request(f'set_user_password:{user_id}')

        try:
            data = self.get_request_json()
            password = (data.get('password') or '').strip()
            if not password:
                return self.error_response("password cannot be empty", 400)

            self._user_service.set_password(user_id, password)
            logger.info(f"Password set for user: {user_id}")
            return self.json_response({"user_id": user_id, "password_set": True}, 200)

        except ValueError as e:
            logger.warning(f"Failed to set password for {user_id}: {str(e)}")
            return self.error_response(str(e), 404)

    def list_pending_users(self) -> Tuple[Any, int]:
        """
        GET /admin/users/pending - List signups awaiting activation.

        Returns:
            200: {"users": [...], "count": n}
        """
        self.log_request('list_pending_users')

        pending = [u for u in self._user_service.list_users() if not u.is_active]
        users = [UserResponse.from_model(u).to_dict() for u in pending]
        return self.json_response({"users": users, "count": len(users)}, 200)

    def activate_user(self, user_id: str) -> Tuple[Any, int]:
        """
        POST /admin/users/{user_id}/activate - Activate a pending signup.

        After activating, attach the user's home via POST /admin/homes
        (or scripts/provision_mobile_login.py --home) so GET /me returns it.

        Returns:
            200: User activated
            404: User not found
        """
        self.log_request(f'activate_user:{user_id}')

        try:
            user = self._user_service.activate_user(user_id)
            response = UserResponse.from_model(user)
            logger.info(f"User activated: {user_id}")
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            return self.error_response(str(e), 404)

    def delete_user(self, user_id: str) -> Tuple[Any, int]:
        """
        DELETE /admin/users/{user_id} - Deactivate user.

        Args:
            user_id: User ID

        Returns:
            200: User deactivated
            404: User not found
        """
        self.log_request(f'delete_user:{user_id}')

        try:
            user = self._user_service.deactivate_user(user_id)
            response = UserResponse.from_model(user)
            logger.info(f"User deactivated: {user_id}")
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            return self.error_response(str(e), 404)

    # ========== Home Endpoints ==========

    def create_home(self) -> Tuple[Any, int]:
        """
        POST /admin/homes - Register new home.

        Request body:
            {
                "home_id": "main_house",
                "user_id": "user_123",
                "name": "Main House",
                "ha_url": "https://ha1.homeadapt.us",
                "ha_webhook_id": "voice_auth_scene"
            }

        Returns:
            201: Home created
            400: Validation error
        """
        self.log_request('create_home')

        try:
            data = self.get_request_json()
            req = CreateHomeRequest.from_dict(data)
            req.validate()

            home = self._home_service.register_home(
                home_id=req.home_id,
                user_id=req.user_id,
                name=req.name,
                ha_url=req.ha_url,
                ha_webhook_id=req.ha_webhook_id
            )

            provided_token = (data.get('ha_token') or '').strip()
            if provided_token:
                self._home_service.set_ha_token(home.home_id, provided_token)

            d = self._with_token_info(HomeResponse.from_model(home).to_dict())
            logger.info(f"Home created: {home.home_id}")
            return self.json_response(d, 201)

        except ValueError as e:
            logger.warning(f"Failed to create home: {str(e)}")
            return self.error_response(str(e), 400)


    # ------------------------------------------------------------------
    # Portal-managed HA tokens + onboarding checks (Phase 1/2)
    # ------------------------------------------------------------------

    # Set by server.py so token updates invalidate the dispatcher's
    # credential cache immediately (otherwise the 60s TTL applies).
    _dispatcher = None

    def set_dispatcher(self, dispatcher) -> None:
        self._dispatcher = dispatcher

    @staticmethod
    def _env_home_ids() -> set:
        try:
            return set(json.loads(os.environ.get('HOME_CONFIGS_JSON', '{}')).keys())
        except (ValueError, AttributeError):
            return set()

    def _with_token_info(self, home_dict: dict) -> dict:
        """Augment a home response dict with non-secret token metadata."""
        home_id = home_dict.get('home_id', '')
        try:
            status = self._home_service.token_status(home_id)
        except Exception:
            status = {'has_token': False, 'token_hint': None}
        if status['has_token']:
            source = 'portal'
        elif home_id in self._env_home_ids():
            source = 'env'
        else:
            source = None
        home_dict.update(status)
        home_dict['token_source'] = source
        home_dict['dispatchable'] = source is not None
        return home_dict

    def _resolve_test_token(self, home_id: str, body: dict) -> Optional[str]:
        """Token for connectivity tests: request body > portal DB > env JSON."""
        provided = (body.get('ha_token') or '').strip()
        if provided:
            return provided
        stored = self._home_service.get_stored_ha_token(home_id)
        if stored:
            return stored
        try:
            cfg = json.loads(os.environ.get('HOME_CONFIGS_JSON', '{}')).get(home_id) or {}
            return (cfg.get('ha_token') or '').strip() or None
        except ValueError:
            return None

    def set_home_token(self, home_id: str) -> Tuple[Any, int]:
        """PUT /admin/homes/{home_id}/token — store/rotate/clear the HA token.

        Body: {"ha_token": "eyJ..."}; empty string or null clears the stored
        token (dispatch then falls back to legacy env config, if present).
        The token is encrypted at rest and never returned by any endpoint.
        """
        self.log_request(f'set_home_token:{home_id}')
        try:
            data = self.get_request_json()
            token = (data.get('ha_token') or '').strip()
            self._home_service.set_ha_token(home_id, token or None)
            if self._dispatcher is not None:
                try:
                    self._dispatcher.invalidate_home(home_id)
                except Exception:
                    pass
            home = self._home_service.get_home(home_id)
            d = self._with_token_info(HomeResponse.from_model(home).to_dict())
            logger.info(f"HA token {'stored' if token else 'cleared'} for home {home_id}")
            return self.json_response(d, 200)
        except ValueError as e:
            return self.error_response(str(e), 404)

    def test_home_connection(self, home_id: str) -> Tuple[Any, int]:
        """POST /admin/homes/{home_id}/test-connection — live HA API check.

        Optional body {"ha_token": "..."} tests a token BEFORE saving it;
        otherwise uses the stored portal token, then the legacy env token.
        """
        self.log_request(f'test_home_connection:{home_id}')
        try:
            home = self._home_service.get_home(home_id)
        except ValueError as e:
            return self.error_response(str(e), 404)
        body = request.get_json(silent=True) or {}
        token = self._resolve_test_token(home_id, body)
        if not token:
            return self.json_response({
                'ok': False, 'stage': 'token',
                'message': 'No HA token available — provide one or store one first.',
            }, 200)
        base = home.ha_url.strip().rstrip('/')
        headers = {'Authorization': f'Bearer {token}'}
        try:
            r = _requests.get(f'{base}/api/config', headers=headers, timeout=10)
            if r.status_code == 200:
                cfg = r.json()
                return self.json_response({
                    'ok': True, 'stage': 'connected',
                    'message': 'Connected to Home Assistant.',
                    'ha_name': cfg.get('location_name'),
                    'ha_version': cfg.get('version'),
                }, 200)
            if r.status_code == 401:
                return self.json_response({'ok': False, 'stage': 'auth',
                                           'message': 'HA rejected the token (401). Create a new long-lived token.'}, 200)
            return self.json_response({'ok': False, 'stage': 'http',
                                       'message': f'HA returned {r.status_code}.'}, 200)
        except _requests.exceptions.Timeout:
            return self.json_response({'ok': False, 'stage': 'network',
                                       'message': f'Timed out reaching {base}.'}, 200)
        except _requests.exceptions.RequestException as e:
            return self.json_response({'ok': False, 'stage': 'network',
                                       'message': f'Could not reach {base}: {type(e).__name__}'}, 200)

    def test_home_webhook(self, home_id: str) -> Tuple[Any, int]:
        """POST /admin/homes/{home_id}/test-webhook — fire the voice-auth webhook.

        Body (all optional): {"scene": "night_scene",
                              "automation_entity": "automation.voice_auth_night_scene"}
        HA answers 200 even for unknown/blocked webhooks, so when an
        automation entity (and a usable token) is available we prove the
        trigger by comparing its last_triggered before/after.
        """
        self.log_request(f'test_home_webhook:{home_id}')
        try:
            home = self._home_service.get_home(home_id)
        except ValueError as e:
            return self.error_response(str(e), 404)
        body = request.get_json(silent=True) or {}
        scene = (body.get('scene') or 'night_scene').strip()
        automation = (body.get('automation_entity') or '').strip()
        token = self._resolve_test_token(home_id, body)
        base = home.ha_url.strip().rstrip('/')
        webhook_url = f"{base}/api/webhook/{home.ha_webhook_id.strip()}"

        def last_triggered():
            if not (automation and token):
                return None
            try:
                r = _requests.get(f'{base}/api/states/{automation}',
                                  headers={'Authorization': f'Bearer {token}'}, timeout=10)
                if r.status_code != 200:
                    return None
                st = r.json()
                return {'state': st.get('state'),
                        'last_triggered': (st.get('attributes') or {}).get('last_triggered')}
            except _requests.exceptions.RequestException:
                return None

        before = last_triggered()
        if before and before.get('state') == 'off':
            return self.json_response({
                'ok': False, 'stage': 'automation_disabled',
                'message': f'{automation} is disabled in HA — enable it, then retest.',
            }, 200)
        try:
            r = _requests.post(webhook_url, json={'scene': scene}, timeout=10)
        except _requests.exceptions.RequestException as e:
            return self.json_response({'ok': False, 'stage': 'network',
                                       'message': f'Could not reach {webhook_url}: {type(e).__name__}'}, 200)
        if r.status_code >= 400:
            return self.json_response({'ok': False, 'stage': 'http',
                                       'message': f'Webhook POST returned {r.status_code}.'}, 200)
        if before is None:
            return self.json_response({
                'ok': True, 'stage': 'sent_unverified',
                'message': ('Webhook accepted (HTTP 200). NOTE: HA returns 200 even for '
                            'unknown webhook IDs — pass automation_entity (with a token) '
                            'to verify the automation really ran.'),
            }, 200)
        _time.sleep(1.5)
        after = last_triggered()
        triggered = bool(after and after.get('last_triggered')
                         and after.get('last_triggered') != (before or {}).get('last_triggered'))
        return self.json_response({
            'ok': triggered,
            'stage': 'verified' if triggered else 'not_triggered',
            'message': (f'{automation} triggered — webhook path fully working.' if triggered else
                        f'Webhook accepted but {automation} did not trigger — check the webhook ID '
                        f'on the automation, its "local network only" setting, and its condition.'),
            'last_triggered': (after or {}).get('last_triggered'),
        }, 200)

    def list_homes(self) -> Tuple[Any, int]:
        """
        GET /admin/homes - List all homes.

        Query parameters:
            active_only: boolean (default: false)

        Returns:
            200: List of homes
        """
        self.log_request('list_homes')

        active_only = request.args.get('active_only', 'false').lower() == 'true'
        homes = self._home_service.list_homes(active_only=active_only)

        response = HomeListResponse.from_models(homes)
        d = response.to_dict()
        d['homes'] = [self._with_token_info(h) for h in d.get('homes', [])]
        return self.json_response(d, 200)

    def get_home(self, home_id: str) -> Tuple[Any, int]:
        """
        GET /admin/homes/{home_id} - Get home details.

        Args:
            home_id: Home ID

        Returns:
            200: Home details
            404: Home not found
        """
        self.log_request(f'get_home:{home_id}')

        try:
            home = self._home_service.get_home(home_id)
            d = self._with_token_info(HomeResponse.from_model(home).to_dict())
            return self.json_response(d, 200)

        except ValueError as e:
            return self.error_response(str(e), 404)

    def update_home(self, home_id: str) -> Tuple[Any, int]:
        """
        PUT /admin/homes/{home_id} - Update home.

        Args:
            home_id: Home ID

        Request body:
            {
                "name": "New Name",           # optional
                "ha_url": "https://new.url",  # optional
                "ha_webhook_id": "new_id",    # optional
                "is_active": true             # optional
            }

        Returns:
            200: Home updated
            404: Home not found
        """
        self.log_request(f'update_home:{home_id}')

        try:
            data = self.get_request_json()
            req = UpdateHomeRequest.from_dict(data)

            home = self._home_service.update_home(
                home_id=home_id,
                name=req.name,
                ha_url=req.ha_url,
                ha_webhook_id=req.ha_webhook_id
            )

            d = self._with_token_info(HomeResponse.from_model(home).to_dict())
            logger.info(f"Home updated: {home_id}")
            return self.json_response(d, 200)

        except ValueError as e:
            logger.warning(f"Failed to update home {home_id}: {str(e)}")
            return self.error_response(str(e), 404)

    def delete_home(self, home_id: str) -> Tuple[Any, int]:
        """
        DELETE /admin/homes/{home_id} - Deactivate home.

        Args:
            home_id: Home ID

        Returns:
            200: Home deactivated
            404: Home not found
        """
        self.log_request(f'delete_home:{home_id}')

        try:
            home = self._home_service.deactivate_home(home_id)
            response = HomeResponse.from_model(home)
            logger.info(f"Home deactivated: {home_id}")
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            return self.error_response(str(e), 404)

    def get_user_homes(self, user_id: str) -> Tuple[Any, int]:
        """
        GET /admin/users/{user_id}/homes - Get user's homes.

        Args:
            user_id: User ID

        Query parameters:
            active_only: boolean (default: true)

        Returns:
            200: List of user's homes
        """
        self.log_request(f'get_user_homes:{user_id}')

        active_only = request.args.get('active_only', 'true').lower() == 'true'
        homes = self._home_service.get_user_homes(user_id, active_only=active_only)

        response = HomeListResponse.from_models(homes)
        return self.json_response(response.to_dict(), 200)

    def toggle_test_mode(self, home_id: str) -> Tuple[Any, int]:
        """
        POST /admin/homes/{home_id}/test-mode - Toggle test mode for a home.

        Request body:
            {
                "enabled": true  # true to enable test mode, false to disable
            }

        Returns:
            200: Test mode toggled successfully
            404: Home not found
            400: Validation error
        """
        self.log_request(f'toggle_test_mode:{home_id}')

        try:
            data = self.get_request_json()
            enabled = data.get('enabled', True)

            # Update home's test_mode
            home = self._home_service.update_home(
                home_id=home_id,
                test_mode=enabled
            )

            response = HomeResponse.from_model(home)
            logger.info(f"Test mode {'enabled' if enabled else 'disabled'} for home: {home_id}")
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            logger.warning(f"Failed to toggle test mode for {home_id}: {str(e)}")
            return self.error_response(str(e), 404)

    # ========== Alexa Mapping Endpoints ==========

    def create_alexa_mapping(self) -> Tuple[Any, int]:
        """
        POST /admin/alexa-mappings - Create new Alexa user mapping.

        Request body:
            {
                "alexa_user_id": "amzn1.ask.account.ABC...",
                "home_id": "karthi_test_home"
            }

        Returns:
            201: Mapping created
            400: Validation error
        """
        self.log_request('create_alexa_mapping')

        unavailable = self._alexa_mappings_unavailable()
        if unavailable:
            return unavailable

        try:
            data = self.get_request_json()
            req = CreateAlexaMappingRequest.from_dict(data)
            req.validate()

            mapping = self._alexa_mapping_service.create_mapping(
                alexa_user_id=req.alexa_user_id,
                home_id=req.home_id
            )

            # Remove from unmapped users list
            tracker.remove_unmapped_user(req.alexa_user_id)

            response = AlexaMappingResponse.from_model(mapping)
            logger.info(f"Alexa mapping created: {req.alexa_user_id} -> {req.home_id}")
            return self.json_response(response.to_dict(), 201)

        except ValueError as e:
            logger.warning(f"Failed to create Alexa mapping: {str(e)}")
            return self.error_response(str(e), 400)

    def list_alexa_mappings(self) -> Tuple[Any, int]:
        """
        GET /admin/alexa-mappings - List all Alexa user mappings.

        Returns:
            200: List of mappings
        """
        self.log_request('list_alexa_mappings')

        # In-memory mode has no Alexa mapping storage: return an empty list
        # (not an error) so dashboard stats keep working in local dev.
        if self._alexa_mapping_service is None:
            return self.json_response({
                'mappings': [], 'total': 0,
                'note': 'Alexa mappings require database mode (USE_DATABASE=true + DATABASE_URL)',
            }, 200)

        mappings = self._alexa_mapping_service.list_all_mappings()
        response = AlexaMappingListResponse.from_models(mappings)
        return self.json_response(response.to_dict(), 200)

    def _alexa_mappings_unavailable(self) -> Optional[Tuple[Any, int]]:
        """503 response when running without a database, else None."""
        if self._alexa_mapping_service is None:
            return self.error_response(
                "Alexa mappings are unavailable: server is running in-memory. "
                "Set USE_DATABASE=true and DATABASE_URL to enable them.", 503)
        return None

    def get_alexa_mapping(self, alexa_user_id: str) -> Tuple[Any, int]:
        """
        GET /admin/alexa-mappings/{alexa_user_id} - Get Alexa mapping details.

        Args:
            alexa_user_id: Amazon user ID

        Returns:
            200: Mapping details
            404: Mapping not found
        """
        self.log_request(f'get_alexa_mapping:{alexa_user_id[:20]}...')

        unavailable = self._alexa_mappings_unavailable()
        if unavailable:
            return unavailable

        mapping = self._alexa_mapping_service.get_mapping(alexa_user_id)
        if not mapping:
            return self.error_response(f"Mapping for Alexa user not found", 404)

        response = AlexaMappingResponse.from_model(mapping)
        return self.json_response(response.to_dict(), 200)

    def update_alexa_mapping(self, alexa_user_id: str) -> Tuple[Any, int]:
        """
        PUT /admin/alexa-mappings/{alexa_user_id} - Update Alexa mapping.

        Args:
            alexa_user_id: Amazon user ID

        Request body:
            {
                "home_id": "new_home_id"
            }

        Returns:
            200: Mapping updated
            404: Mapping not found
            400: Validation error
        """
        self.log_request(f'update_alexa_mapping:{alexa_user_id[:20]}...')

        unavailable = self._alexa_mappings_unavailable()
        if unavailable:
            return unavailable

        try:
            data = self.get_request_json()
            req = UpdateAlexaMappingRequest.from_dict(data)
            req.validate()

            mapping = self._alexa_mapping_service.update_mapping(
                alexa_user_id=alexa_user_id,
                new_home_id=req.home_id
            )

            response = AlexaMappingResponse.from_model(mapping)
            logger.info(f"Alexa mapping updated: {alexa_user_id[:20]}... -> {req.home_id}")
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            logger.warning(f"Failed to update Alexa mapping: {str(e)}")
            return self.error_response(str(e), 404)

    def delete_alexa_mapping(self, alexa_user_id: str) -> Tuple[Any, int]:
        """
        DELETE /admin/alexa-mappings/{alexa_user_id} - Delete Alexa mapping.

        Args:
            alexa_user_id: Amazon user ID

        Returns:
            200: Mapping deleted
            404: Mapping not found
        """
        self.log_request(f'delete_alexa_mapping:{alexa_user_id[:20]}...')

        unavailable = self._alexa_mappings_unavailable()
        if unavailable:
            return unavailable

        try:
            self._alexa_mapping_service.delete_mapping(alexa_user_id)
            logger.info(f"Alexa mapping deleted for user: {alexa_user_id[:20]}...")
            return self.json_response({'message': 'Mapping deleted successfully'}, 200)

        except ValueError as e:
            return self.error_response(str(e), 404)

    def get_unmapped_users(self) -> Tuple[Any, int]:
        """
        GET /admin/unmapped-users - Get list of unmapped Alexa users.

        Returns list of Alexa users who tried to use the skill but aren't
        mapped to any home yet. Makes it easy to assign them.

        Returns:
            200: List of unmapped users
        """
        self.log_request('get_unmapped_users')

        try:
            from app.services.unmapped_user_tracker import get_tracker

            tracker = get_tracker()
            unmapped_users = tracker.get_unmapped_users()

            return self.json_response({
                'unmapped_users': [
                    {
                        'alexa_user_id': user.alexa_user_id,
                        'first_seen': user.first_seen.isoformat(),
                        'last_seen': user.last_seen.isoformat(),
                        'attempt_count': user.attempt_count
                    }
                    for user in unmapped_users
                ],
                'total': len(unmapped_users)
            }, 200)

        except Exception as e:
            logger.error(f"Error getting unmapped users: {str(e)}", exc_info=True)
            return self.error_response(str(e), 500)

    # ========== Scene Webhook Mapping Endpoints ==========

    def create_scene_mapping(self) -> Tuple[Any, int]:
        """
        POST /admin/scene-mappings - Create new scene webhook mapping.

        Request body:
            {
                "home_id": "scott_home",
                "scene_name": "decorations on",
                "webhook_id": "decorations_on_1751404299018"
            }

        Returns:
            201: Mapping created
            400: Validation error
        """
        self.log_request('create_scene_mapping')

        try:
            data = self.get_request_json()
            req = CreateSceneWebhookMappingRequest.from_dict(data)
            req.validate()

            mapping = self._scene_mapping_service.create_mapping(
                home_id=req.home_id,
                scene_name=req.scene_name,
                webhook_id=req.webhook_id
            )

            response = SceneWebhookMappingResponse.from_model(mapping)
            logger.info(f"Scene mapping created: {req.scene_name} -> {req.webhook_id}")
            return self.json_response(response.to_dict(), 201)

        except ValueError as e:
            logger.warning(f"Failed to create scene mapping: {str(e)}")
            return self.error_response(str(e), 400)

    def list_scene_mappings(self) -> Tuple[Any, int]:
        """
        GET /admin/scene-mappings - List all scene webhook mappings.

        Returns:
            200: List of mappings
        """
        self.log_request('list_scene_mappings')

        mappings = self._scene_mapping_service.list_all()
        response = SceneWebhookMappingListResponse.from_models(mappings)
        return self.json_response(response.to_dict(), 200)

    def list_home_scenes(self, home_id: str) -> Tuple[Any, int]:
        """
        GET /admin/homes/{home_id}/scenes - List scenes for a home.

        Args:
            home_id: Home ID

        Returns:
            200: List of scene mappings for the home
        """
        self.log_request(f'list_home_scenes:{home_id}')

        mappings = self._scene_mapping_service.list_scenes_for_home(home_id)
        response = SceneWebhookMappingListResponse.from_models(mappings)
        return self.json_response(response.to_dict(), 200)

    def get_scene_mapping(self, mapping_id: str) -> Tuple[Any, int]:
        """
        GET /admin/scene-mappings/{mapping_id} - Get scene mapping details.

        Args:
            mapping_id: Mapping ID

        Returns:
            200: Mapping details
            404: Mapping not found
        """
        self.log_request(f'get_scene_mapping:{mapping_id}')

        mapping = self._scene_mapping_service.get_mapping(mapping_id)
        if not mapping:
            return self.error_response("Scene mapping not found", 404)

        response = SceneWebhookMappingResponse.from_model(mapping)
        return self.json_response(response.to_dict(), 200)

    def update_scene_mapping(self, mapping_id: str) -> Tuple[Any, int]:
        """
        PUT /admin/scene-mappings/{mapping_id} - Update scene mapping.

        Args:
            mapping_id: Mapping ID

        Request body:
            {
                "scene_name": "new name",    # optional
                "webhook_id": "new_id",      # optional
                "is_active": true            # optional
            }

        Returns:
            200: Mapping updated
            404: Mapping not found
        """
        self.log_request(f'update_scene_mapping:{mapping_id}')

        try:
            data = self.get_request_json()
            req = UpdateSceneWebhookMappingRequest.from_dict(data)

            mapping = self._scene_mapping_service.update_mapping(
                mapping_id=mapping_id,
                scene_name=req.scene_name,
                webhook_id=req.webhook_id,
                is_active=req.is_active
            )

            response = SceneWebhookMappingResponse.from_model(mapping)
            logger.info(f"Scene mapping updated: {mapping_id}")
            return self.json_response(response.to_dict(), 200)

        except ValueError as e:
            logger.warning(f"Failed to update scene mapping {mapping_id}: {str(e)}")
            return self.error_response(str(e), 404)

    def delete_scene_mapping(self, mapping_id: str) -> Tuple[Any, int]:
        """
        DELETE /admin/scene-mappings/{mapping_id} - Delete scene mapping.

        Args:
            mapping_id: Mapping ID

        Returns:
            200: Mapping deleted
            404: Mapping not found
        """
        self.log_request(f'delete_scene_mapping:{mapping_id}')

        result = self._scene_mapping_service.delete_mapping(mapping_id)
        if not result:
            return self.error_response("Scene mapping not found", 404)

        logger.info(f"Scene mapping deleted: {mapping_id}")
        return self.json_response({'message': 'Scene mapping deleted successfully'}, 200)
