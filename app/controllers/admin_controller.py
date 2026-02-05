"""
Admin controller for user and home management

REST API endpoints for administrative operations.
"""

import logging
from typing import Tuple, Any
from flask import request
from app.controllers.base_controller import BaseController
from app.services.user_service import UserService
from app.services.home_service import HomeService
from app.services.alexa_mapping_service import AlexaMappingService
from app.dto.requests.admin_request import (
    CreateUserRequest,
    UpdateUserRequest,
    CreateHomeRequest,
    UpdateHomeRequest,
    CreateAlexaMappingRequest,
    UpdateAlexaMappingRequest
)
from app.dto.responses.admin_response import (
    UserResponse,
    HomeResponse,
    UserListResponse,
    HomeListResponse,
    AlexaMappingResponse,
    AlexaMappingListResponse,
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
        alexa_mapping_service: AlexaMappingService
    ):
        """
        Initialize admin controller.

        Args:
            user_service: Service for user operations
            home_service: Service for home operations
            alexa_mapping_service: Service for Alexa mapping operations
        """
        super().__init__(blueprint_name='admin', url_prefix='/admin')
        self._user_service = user_service
        self._home_service = home_service
        self._alexa_mapping_service = alexa_mapping_service
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
                email=req.email
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

            response = HomeResponse.from_model(home)
            logger.info(f"Home created: {home.home_id}")
            return self.json_response(response.to_dict(), 201)

        except ValueError as e:
            logger.warning(f"Failed to create home: {str(e)}")
            return self.error_response(str(e), 400)

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
        return self.json_response(response.to_dict(), 200)

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
            response = HomeResponse.from_model(home)
            return self.json_response(response.to_dict(), 200)

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

            response = HomeResponse.from_model(home)
            logger.info(f"Home updated: {home_id}")
            return self.json_response(response.to_dict(), 200)

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

        mappings = self._alexa_mapping_service.list_all_mappings()
        response = AlexaMappingListResponse.from_models(mappings)
        return self.json_response(response.to_dict(), 200)

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
