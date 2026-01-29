"""
Error handling middleware

Provides global exception handling with structured error responses.
"""

import logging
import traceback
from typing import Tuple, Any
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException
from app.dto.base import ValidationError


logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware:
    """
    Error handling middleware for Flask.

    Catches all exceptions and returns structured error responses.
    Logs errors with context for debugging.
    """

    def __init__(self, app: Flask):
        """
        Initialize error handler middleware.

        Args:
            app: Flask application
        """
        self.app = app
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register error handlers on Flask app."""

        @self.app.errorhandler(ValidationError)
        def handle_validation_error(error: ValidationError) -> Tuple[Any, int]:
            """
            Handle DTO validation errors.

            Returns 400 Bad Request with error details.
            """
            logger.warning(
                f"Validation error: {str(error)}",
                extra={
                    'error_type': 'ValidationError',
                    'path': request.path,
                    'method': request.method
                }
            )

            return jsonify({
                'error': {
                    'type': 'validation_error',
                    'message': str(error)
                }
            }), 400

        @self.app.errorhandler(HTTPException)
        def handle_http_exception(error: HTTPException) -> Tuple[Any, int]:
            """
            Handle HTTP exceptions (404, 405, etc.).

            Returns appropriate HTTP status with error details.
            """
            logger.warning(
                f"HTTP exception: {error.code} - {error.description}",
                extra={
                    'error_type': 'HTTPException',
                    'status_code': error.code,
                    'path': request.path,
                    'method': request.method
                }
            )

            return jsonify({
                'error': {
                    'type': 'http_error',
                    'message': error.description,
                    'status_code': error.code
                }
            }), error.code

        @self.app.errorhandler(Exception)
        def handle_generic_exception(error: Exception) -> Tuple[Any, int]:
            """
            Handle unexpected exceptions.

            Returns 500 Internal Server Error with generic message.
            Logs full traceback for debugging.
            """
            # Log full error with traceback
            logger.error(
                f"Unhandled exception: {str(error)}",
                extra={
                    'error_type': type(error).__name__,
                    'path': request.path,
                    'method': request.method,
                    'traceback': traceback.format_exc()
                },
                exc_info=True
            )

            # Return generic error to client (don't expose internals)
            return jsonify({
                'error': {
                    'type': 'internal_error',
                    'message': 'An internal error occurred. Please try again later.'
                }
            }), 500

    @staticmethod
    def format_error_response(
        error_type: str,
        message: str,
        status_code: int = 500,
        details: dict = None
    ) -> Tuple[Any, int]:
        """
        Format error response.

        Args:
            error_type: Type of error (e.g., 'validation_error')
            message: Human-readable error message
            status_code: HTTP status code
            details: Optional additional error details

        Returns:
            Tuple of (response, status_code)
        """
        response = {
            'error': {
                'type': error_type,
                'message': message
            }
        }

        if details:
            response['error']['details'] = details

        return jsonify(response), status_code
