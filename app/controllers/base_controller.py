"""
Base controller with common functionality

Provides shared utilities for all controllers.
"""

import logging
from typing import Tuple, Any
from flask import Blueprint, request, jsonify
from app.dto.base import ValidationError


logger = logging.getLogger(__name__)


class BaseController:
    """
    Base controller class.

    Provides:
    - Blueprint creation
    - Common error handling
    - Request/response helpers
    """

    def __init__(self, blueprint_name: str, url_prefix: str):
        """
        Initialize base controller.

        Args:
            blueprint_name: Name for Flask blueprint
            url_prefix: URL prefix for routes
        """
        self.blueprint = Blueprint(blueprint_name, __name__, url_prefix=url_prefix)
        self._register_error_handlers()

    def _register_error_handlers(self) -> None:
        """Register common error handlers on blueprint."""

        @self.blueprint.errorhandler(ValidationError)
        def handle_validation_error(error: ValidationError) -> Tuple[Any, int]:
            """Handle DTO validation errors."""
            logger.warning(f"Validation error: {str(error)}")
            return jsonify({"error": str(error)}), 400

        @self.blueprint.errorhandler(Exception)
        def handle_generic_error(error: Exception) -> Tuple[Any, int]:
            """Handle unexpected errors."""
            logger.error(f"Unexpected error: {str(error)}", exc_info=True)
            return jsonify({"error": "Internal server error"}), 500

    @staticmethod
    def get_request_json() -> dict:
        """
        Get JSON from request.

        Returns:
            Request JSON data

        Raises:
            ValidationError: If request has no JSON
        """
        data = request.get_json()
        if data is None:
            raise ValidationError("Request body required")
        return data

    @staticmethod
    def json_response(data: dict, status_code: int = 200) -> Tuple[Any, int]:
        """
        Create JSON response.

        Args:
            data: Response data
            status_code: HTTP status code

        Returns:
            Tuple of (response, status_code)
        """
        return jsonify(data), status_code

    @staticmethod
    def error_response(message: str, status_code: int = 400) -> Tuple[Any, int]:
        """
        Create error response.

        Args:
            message: Error message
            status_code: HTTP status code

        Returns:
            Tuple of (response, status_code)
        """
        return jsonify({"error": message}), status_code

    def log_request(self, endpoint: str) -> None:
        """
        Log incoming request.

        Args:
            endpoint: Endpoint name
        """
        logger.info(f"Request received: {endpoint}")
