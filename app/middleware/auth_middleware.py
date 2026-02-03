"""
Authentication middleware

Protects admin routes and static files requiring authentication.
"""

import logging
from functools import wraps
from flask import session, redirect, url_for, request, jsonify


logger = logging.getLogger(__name__)


def require_admin_auth(f):
    """
    Decorator to require admin authentication for a route.

    Usage:
        @blueprint.route('/protected')
        @require_admin_auth
        def protected_route():
            return 'Protected content'
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session:
            logger.warning(f"Unauthorized access attempt to {request.path}")
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Admin authentication required'
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def setup_auth_middleware(app):
    """
    Setup authentication middleware for Flask app.

    Protects:
    - /admin/* routes
    - /static/admin*.html files

    Args:
        app: Flask application
    """

    @app.before_request
    def check_admin_auth():
        """Check authentication before each request."""

        # Skip auth check for login/logout endpoints
        if request.path.startswith('/auth/'):
            return None

        # Skip auth check for public endpoints
        public_paths = [
            '/alexa',
            '/futureproofhome',
            '/health',
            '/',
            '/static/privacy-policy.html',
            '/static/terms-of-use.html'
        ]

        for public_path in public_paths:
            if request.path.startswith(public_path):
                return None

        # Protect admin routes
        if request.path.startswith('/admin'):
            if 'admin_user' not in session:
                logger.warning(f"Unauthorized API access attempt: {request.path}")
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'Admin authentication required'
                }), 401

        # Protect admin static files
        if request.path.startswith('/static/admin'):
            if 'admin_user' not in session:
                logger.warning(f"Unauthorized admin page access attempt: {request.path}")
                # Redirect to login page
                return redirect('/static/login.html')

        return None

    logger.info("Authentication middleware configured")
