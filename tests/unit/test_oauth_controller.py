"""
Tests for OAuth controller

Tests the OAuth2 account linking flow:
- GET /oauth/authorize (login page)
- POST /oauth/authorize (login submission)
- POST /oauth/token (authorization_code grant)
- POST /oauth/token (refresh_token grant)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from flask import Flask

from app.controllers.oauth_controller import OAuthController, _auth_codes
from app.domain.models import Home, OAuthToken
from app.services.oauth_service import OAuthService
from app.services.home_service import HomeService


@pytest.fixture
def mock_oauth_service():
    return MagicMock(spec=OAuthService)


@pytest.fixture
def mock_home_service():
    return MagicMock(spec=HomeService)


@pytest.fixture
def controller(mock_oauth_service, mock_home_service):
    return OAuthController(
        oauth_service=mock_oauth_service,
        home_service=mock_home_service
    )


@pytest.fixture
def app(controller):
    """Create a Flask test app with the OAuth blueprint."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(controller.blueprint)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clear_auth_codes():
    """Clear auth codes before each test."""
    _auth_codes.clear()
    yield
    _auth_codes.clear()


@pytest.fixture
def sample_home():
    return Home(
        home_id="home_1",
        user_id="user_123",
        name="Test Home",
        ha_url="https://ha1.homeadapt.us",
        ha_webhook_id="voice_auth_scene",
        is_active=True,
        created_at=datetime(2026, 1, 29, 12, 0, 0)
    )


@pytest.fixture
def sample_token():
    return OAuthToken(
        id="token-id-1",
        home_id="home_1",
        access_token="access-token-abc",
        refresh_token="refresh-token-xyz",
        token_type="bearer",
        expires_at=datetime.now() + timedelta(days=365),
        amazon_user_id=None,
        created_at=datetime.now(),
        updated_at=None
    )


class TestAuthorizeGet:
    """Tests for GET /oauth/authorize — login page rendering."""

    def test_returns_login_page(self, client):
        """GET /oauth/authorize should return the login HTML page."""
        response = client.get(
            '/oauth/authorize?client_id=amzn&redirect_uri=https://example.com/cb&state=abc&response_type=code'
        )
        assert response.status_code == 200
        assert b'Voice Guardian' in response.data
        assert b'Link Your Account' in response.data

    def test_login_page_contains_form(self, client):
        """Login page should contain the link form elements."""
        response = client.get('/oauth/authorize?redirect_uri=https://example.com&state=xyz')
        html = response.data.decode()
        assert 'name="home_id"' in html
        assert 'name="pin"' in html
        assert 'name="redirect_uri"' in html
        assert 'name="state"' in html
        assert 'Link Account' in html


class TestAuthorizePost:
    """Tests for POST /oauth/authorize — login form submission."""

    def test_successful_login_redirects(self, client, mock_home_service, sample_home):
        """Valid credentials should redirect to Amazon with auth code."""
        mock_home_service.get_home.return_value = sample_home

        response = client.post('/oauth/authorize', data={
            'home_id': 'home_1',
            'pin': '1234',
            'redirect_uri': 'https://layla.amazon.com/api/skill/link/callback',
            'state': 'amazon-state-123'
        })

        assert response.status_code == 302
        location = response.headers['Location']
        assert 'code=' in location
        assert 'state=amazon-state-123' in location
        assert 'layla.amazon.com' in location

    def test_successful_login_stores_auth_code(self, client, mock_home_service, sample_home):
        """Auth code should be stored with home_id and expiry."""
        mock_home_service.get_home.return_value = sample_home

        client.post('/oauth/authorize', data={
            'home_id': 'home_1',
            'pin': '1234',
            'redirect_uri': 'https://example.com/cb',
            'state': 'state1'
        })

        assert len(_auth_codes) == 1
        code_data = list(_auth_codes.values())[0]
        assert code_data['home_id'] == 'home_1'
        assert code_data['expires_at'] > datetime.now()

    def test_missing_home_id_returns_400(self, client):
        """Missing home_id should return 400."""
        response = client.post('/oauth/authorize', data={
            'home_id': '',
            'pin': '1234',
            'redirect_uri': 'https://example.com/cb',
            'state': 'state1'
        })
        assert response.status_code == 400

    def test_missing_pin_returns_400(self, client):
        """Missing pin should return 400."""
        response = client.post('/oauth/authorize', data={
            'home_id': 'home_1',
            'pin': '',
            'redirect_uri': 'https://example.com/cb',
            'state': 'state1'
        })
        assert response.status_code == 400

    def test_missing_redirect_uri_returns_400(self, client, mock_home_service):
        """Missing redirect_uri should return 400."""
        response = client.post('/oauth/authorize', data={
            'home_id': 'home_1',
            'pin': '1234',
            'redirect_uri': '',
            'state': 'state1'
        })
        assert response.status_code == 400

    def test_invalid_pin_returns_401(self, client):
        """Wrong PIN should return 401."""
        response = client.post('/oauth/authorize', data={
            'home_id': 'home_1',
            'pin': '9999',
            'redirect_uri': 'https://example.com/cb',
            'state': 'state1'
        })
        assert response.status_code == 401

    def test_home_not_found_returns_404(self, client, mock_home_service):
        """Non-existent home should return 404."""
        mock_home_service.get_home.side_effect = ValueError("Home not found")

        response = client.post('/oauth/authorize', data={
            'home_id': 'nonexistent',
            'pin': '1234',
            'redirect_uri': 'https://example.com/cb',
            'state': 'state1'
        })
        assert response.status_code == 404

    def test_redirect_uri_with_existing_query_params(self, client, mock_home_service, sample_home):
        """Should use & separator if redirect_uri already has query params."""
        mock_home_service.get_home.return_value = sample_home

        response = client.post('/oauth/authorize', data={
            'home_id': 'home_1',
            'pin': '1234',
            'redirect_uri': 'https://example.com/cb?foo=bar',
            'state': 'state1'
        })

        location = response.headers['Location']
        assert '?foo=bar&code=' in location


class TestTokenAuthorizationCode:
    """Tests for POST /oauth/token with grant_type=authorization_code."""

    def test_valid_code_returns_tokens(self, client, mock_oauth_service, sample_token):
        """Valid auth code should return access and refresh tokens."""
        auth_code = "test-auth-code-123"
        _auth_codes[auth_code] = {
            "home_id": "home_1",
            "expires_at": datetime.now() + timedelta(minutes=5)
        }
        mock_oauth_service.create_token.return_value = sample_token

        response = client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': 'amzn-client',
            'client_secret': 'amzn-secret'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['access_token'] == 'access-token-abc'
        assert data['refresh_token'] == 'refresh-token-xyz'
        assert data['token_type'] == 'bearer'
        assert data['expires_in'] == 31536000

    def test_valid_code_consumed_after_use(self, client, mock_oauth_service, sample_token):
        """Auth code should be deleted after successful exchange."""
        auth_code = "one-time-code"
        _auth_codes[auth_code] = {
            "home_id": "home_1",
            "expires_at": datetime.now() + timedelta(minutes=5)
        }
        mock_oauth_service.create_token.return_value = sample_token

        client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'code': auth_code
        })

        assert auth_code not in _auth_codes

    def test_invalid_code_returns_400(self, client):
        """Invalid auth code should return 400."""
        response = client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'code': 'bad-code'
        })
        assert response.status_code == 400
        assert 'Invalid authorization code' in response.get_json()['error']

    def test_expired_code_returns_400(self, client):
        """Expired auth code should return 400."""
        auth_code = "expired-code"
        _auth_codes[auth_code] = {
            "home_id": "home_1",
            "expires_at": datetime.now() - timedelta(minutes=1)
        }

        response = client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'code': auth_code
        })
        assert response.status_code == 400
        assert 'expired' in response.get_json()['error'].lower()

    def test_expired_code_is_cleaned_up(self, client):
        """Expired code should be removed from the store."""
        auth_code = "expired-code"
        _auth_codes[auth_code] = {
            "home_id": "home_1",
            "expires_at": datetime.now() - timedelta(minutes=1)
        }

        client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'code': auth_code
        })

        assert auth_code not in _auth_codes

    def test_missing_code_returns_400(self, client):
        """Missing code parameter should return 400."""
        response = client.post('/oauth/token', data={
            'grant_type': 'authorization_code'
        })
        assert response.status_code == 400

    def test_token_exchange_calls_create_token(self, client, mock_oauth_service, sample_token):
        """Token exchange should call oauth_service.create_token with correct home_id."""
        auth_code = "code-for-home-1"
        _auth_codes[auth_code] = {
            "home_id": "home_1",
            "expires_at": datetime.now() + timedelta(minutes=5)
        }
        mock_oauth_service.create_token.return_value = sample_token

        client.post('/oauth/token', data={
            'grant_type': 'authorization_code',
            'code': auth_code
        })

        mock_oauth_service.create_token.assert_called_once_with("home_1")

    def test_json_body_also_accepted(self, client, mock_oauth_service, sample_token):
        """Token endpoint should accept JSON body as well as form data."""
        auth_code = "json-code"
        _auth_codes[auth_code] = {
            "home_id": "home_1",
            "expires_at": datetime.now() + timedelta(minutes=5)
        }
        mock_oauth_service.create_token.return_value = sample_token

        response = client.post('/oauth/token',
                               json={
                                   'grant_type': 'authorization_code',
                                   'code': auth_code
                               })

        assert response.status_code == 200
        assert response.get_json()['access_token'] == 'access-token-abc'


class TestTokenRefresh:
    """Tests for POST /oauth/token with grant_type=refresh_token."""

    def test_valid_refresh_returns_new_tokens(self, client, mock_oauth_service, sample_token):
        """Valid refresh token should return new tokens."""
        mock_oauth_service.refresh_access_token.return_value = sample_token

        response = client.post('/oauth/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': 'old-refresh-token'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['access_token'] == 'access-token-abc'
        assert data['refresh_token'] == 'refresh-token-xyz'
        assert data['token_type'] == 'bearer'
        assert data['expires_in'] == 31536000

    def test_invalid_refresh_returns_400(self, client, mock_oauth_service):
        """Invalid refresh token should return 400."""
        mock_oauth_service.refresh_access_token.return_value = None

        response = client.post('/oauth/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': 'bad-refresh-token'
        })
        assert response.status_code == 400
        assert 'Invalid refresh_token' in response.get_json()['error']

    def test_missing_refresh_token_returns_400(self, client):
        """Missing refresh_token parameter should return 400."""
        response = client.post('/oauth/token', data={
            'grant_type': 'refresh_token'
        })
        assert response.status_code == 400

    def test_refresh_calls_service(self, client, mock_oauth_service, sample_token):
        """Refresh should call oauth_service.refresh_access_token."""
        mock_oauth_service.refresh_access_token.return_value = sample_token

        client.post('/oauth/token', data={
            'grant_type': 'refresh_token',
            'refresh_token': 'the-refresh-token'
        })

        mock_oauth_service.refresh_access_token.assert_called_once_with('the-refresh-token')


class TestTokenUnsupportedGrant:
    """Tests for unsupported grant types."""

    def test_unsupported_grant_type_returns_400(self, client):
        """Unsupported grant_type should return 400."""
        response = client.post('/oauth/token', data={
            'grant_type': 'client_credentials'
        })
        assert response.status_code == 400
        assert 'Unsupported grant_type' in response.get_json()['error']

    def test_missing_grant_type_returns_400(self, client):
        """Missing grant_type should return 400."""
        response = client.post('/oauth/token', data={})
        assert response.status_code == 400


class TestControllerSetup:
    """Tests for controller initialization and blueprint registration."""

    def test_blueprint_name(self, controller):
        """Blueprint should be named 'oauth'."""
        assert controller.blueprint.name == 'oauth'

    def test_blueprint_url_prefix(self, controller):
        """Blueprint URL prefix should be '/oauth'."""
        assert controller.blueprint.url_prefix == '/oauth'

    def test_routes_registered(self, app):
        """All expected routes should be registered."""
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert '/oauth/authorize' in rules
        assert '/oauth/token' in rules
