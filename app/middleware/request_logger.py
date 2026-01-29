"""
Request logging middleware

Provides structured logging for all HTTP requests and responses.
"""

import logging
import time
import uuid
from typing import Any
from flask import Flask, request, g
from functools import wraps


logger = logging.getLogger(__name__)


class RequestLoggerMiddleware:
    """
    Request logging middleware for Flask.

    Logs all incoming requests and outgoing responses with:
    - Request ID for tracing
    - Performance metrics (duration)
    - Request/response details
    """

    def __init__(self, app: Flask, log_request_body: bool = False, log_response_body: bool = False):
        """
        Initialize request logger middleware.

        Args:
            app: Flask application
            log_request_body: Whether to log request bodies (may contain sensitive data)
            log_response_body: Whether to log response bodies (verbose)
        """
        self.app = app
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register before/after request handlers."""

        @self.app.before_request
        def before_request():
            """Log incoming request and start timer."""
            # Generate unique request ID
            g.request_id = str(uuid.uuid4())
            g.start_time = time.time()

            # Build log context
            log_data = {
                'request_id': g.request_id,
                'method': request.method,
                'path': request.path,
                'remote_addr': request.remote_addr,
                'user_agent': request.user_agent.string if request.user_agent else None
            }

            # Optionally log request body
            if self.log_request_body and request.is_json:
                log_data['request_body'] = request.get_json()

            logger.info(
                f"Incoming request: {request.method} {request.path}",
                extra=log_data
            )

        @self.app.after_request
        def after_request(response):
            """Log outgoing response with performance metrics."""
            # Calculate request duration
            if hasattr(g, 'start_time'):
                duration_ms = (time.time() - g.start_time) * 1000
            else:
                duration_ms = 0

            # Build log context
            log_data = {
                'request_id': getattr(g, 'request_id', 'unknown'),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': round(duration_ms, 2)
            }

            # Optionally log response body
            if self.log_response_body and response.is_json:
                log_data['response_body'] = response.get_json()

            # Log level based on status code
            if response.status_code >= 500:
                log_level = logging.ERROR
            elif response.status_code >= 400:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO

            logger.log(
                log_level,
                f"Response: {request.method} {request.path} -> {response.status_code} ({duration_ms:.2f}ms)",
                extra=log_data
            )

            # Add request ID to response headers for tracing
            response.headers['X-Request-ID'] = log_data['request_id']

            return response

    @staticmethod
    def get_request_id() -> str:
        """
        Get current request ID.

        Returns:
            Request ID string or 'unknown' if not set
        """
        return getattr(g, 'request_id', 'unknown')

    @staticmethod
    def log_with_request_context(message: str, level: int = logging.INFO, **kwargs):
        """
        Log message with request context.

        Args:
            message: Log message
            level: Log level
            **kwargs: Additional log context
        """
        context = {
            'request_id': RequestLoggerMiddleware.get_request_id(),
            **kwargs
        }

        logger.log(level, message, extra=context)


def with_request_logging(func):
    """
    Decorator to add request logging to a function.

    Logs function entry/exit with request context.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        request_id = RequestLoggerMiddleware.get_request_id()

        logger.debug(
            f"Entering {func.__name__}",
            extra={'request_id': request_id, 'function': func.__name__}
        )

        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000

            logger.debug(
                f"Exiting {func.__name__} ({duration_ms:.2f}ms)",
                extra={
                    'request_id': request_id,
                    'function': func.__name__,
                    'duration_ms': round(duration_ms, 2)
                }
            )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            logger.error(
                f"Error in {func.__name__}: {str(e)}",
                extra={
                    'request_id': request_id,
                    'function': func.__name__,
                    'duration_ms': round(duration_ms, 2),
                    'error': str(e)
                },
                exc_info=True
            )

            raise

    return wrapper
