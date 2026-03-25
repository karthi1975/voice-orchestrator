"""
Tests for Smart Home controller.

Tests directive routing, discovery, activation, deactivation, and accept grant.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from datetime import datetime
from flask import Flask

from app.controllers.smarthome_controller import SmartHomeController
from app.services.oauth_service import OAuthService
from app.services.scene_webhook_mapping_service import SceneWebhookMappingService
from app.services.home_automation_service import HomeAutomationService, SceneTriggerResult
from app.domain.models import SceneWebhookMapping


# --- Helpers ---

def make_discovery_directive(bearer_token='valid-token'):
    """Build an Alexa Discovery directive dict."""
    return {
        'directive': {
            'header': {
                'namespace': 'Alexa.Discovery',
                'name': 'Discover',
                'messageId': 'msg-123',
                'payloadVersion': '3'
            },
            'payload': {
                'scope': {
                    'type': 'BearerToken',
                    'token': bearer_token
                }
            }
        }
    }


def make_activate_directive(endpoint_id='home1:decorations on', bearer_token='valid-token', correlation_token='corr-123'):
    """Build an Alexa SceneController Activate directive dict."""
    return {
        'directive': {
            'header': {
                'namespace': 'Alexa.SceneController',
                'name': 'Activate',
                'messageId': 'msg-456',
                'payloadVersion': '3',
                'correlationToken': correlation_token
            },
            'endpoint': {
                'scope': {
                    'type': 'BearerToken',
                    'token': bearer_token
                },
                'endpointId': endpoint_id
            },
            'payload': {}
        }
    }


def make_deactivate_directive(endpoint_id='home1:decorations on', bearer_token='valid-token', correlation_token='corr-789'):
    """Build an Alexa SceneController Deactivate directive dict."""
    return {
        'directive': {
            'header': {
                'namespace': 'Alexa.SceneController',
                'name': 'Deactivate',
                'messageId': 'msg-789',
                'payloadVersion': '3',
                'correlationToken': correlation_token
            },
            'endpoint': {
                'scope': {
                    'type': 'BearerToken',
                    'token': bearer_token
                },
                'endpointId': endpoint_id
            },
            'payload': {}
        }
    }


def make_accept_grant_directive():
    """Build an Alexa Authorization AcceptGrant directive dict."""
    return {
        'directive': {
            'header': {
                'namespace': 'Alexa.Authorization',
                'name': 'AcceptGrant',
                'messageId': 'msg-grant-1',
                'payloadVersion': '3'
            },
            'payload': {
                'grant': {
                    'type': 'OAuth2.AuthorizationCode',
                    'code': 'auth-code-123'
                },
                'grantee': {
                    'type': 'BearerToken',
                    'token': 'access-token'
                }
            }
        }
    }


def make_unknown_directive():
    """Build an unsupported directive dict."""
    return {
        'directive': {
            'header': {
                'namespace': 'Alexa.Unknown',
                'name': 'DoSomething',
                'messageId': 'msg-unknown',
                'payloadVersion': '3'
            },
            'payload': {}
        }
    }


def make_scene_mapping(home_id, scene_name, webhook_id, is_active=True, smarthome_enabled=True):
    """Create a SceneWebhookMapping domain object."""
    return SceneWebhookMapping(
        id=f'mapping-{scene_name}',
        home_id=home_id,
        scene_name=scene_name,
        webhook_id=webhook_id,
        is_active=is_active,
        smarthome_enabled=smarthome_enabled,
        created_at=datetime.now()
    )


# --- Fixtures ---

@pytest.fixture
def app():
    """Create a Flask test application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def mock_oauth_service():
    return MagicMock(spec=OAuthService)


@pytest.fixture
def mock_scene_mapping_service():
    return MagicMock(spec=SceneWebhookMappingService)


@pytest.fixture
def mock_ha_service():
    return MagicMock(spec=HomeAutomationService)


@pytest.fixture
def controller(mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
    return SmartHomeController(
        oauth_service=mock_oauth_service,
        scene_mapping_service=mock_scene_mapping_service,
        ha_service=mock_ha_service
    )


@pytest.fixture
def client(app, controller):
    """Create a Flask test client with the controller blueprint registered."""
    app.register_blueprint(controller.blueprint)
    return app.test_client()


# --- Directive Routing Tests ---

class TestDirectiveRouting:

    def test_discovery_routes_correctly(self, client, mock_oauth_service, mock_scene_mapping_service):
        """Discovery directive should route to discovery handler."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.list_scenes_for_home.return_value = []

        resp = client.post('/alexa/smarthome', json=make_discovery_directive())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['event']['header']['name'] == 'Discover.Response'

    def test_activate_routes_correctly(self, client, mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
        """Activate directive should route to activate handler."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.get_webhook_for_scene.return_value = 'webhook-123'
        mock_ha_service.trigger_scene.return_value = SceneTriggerResult(
            success=True, message='ok', scene_id='decorations on'
        )

        resp = client.post('/alexa/smarthome', json=make_activate_directive())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['event']['header']['name'] == 'ActivationStarted'

    def test_deactivate_routes_correctly(self, client, mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
        """Deactivate directive should route to deactivate handler."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.get_webhook_for_scene.return_value = None
        mock_ha_service.trigger_scene.return_value = SceneTriggerResult(
            success=True, message='ok', scene_id='deactivate_decorations on'
        )

        resp = client.post('/alexa/smarthome', json=make_deactivate_directive())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['event']['header']['name'] == 'DeactivationStarted'

    def test_accept_grant_routes_correctly(self, client):
        """AcceptGrant directive should route to accept grant handler."""
        resp = client.post('/alexa/smarthome', json=make_accept_grant_directive())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['event']['header']['name'] == 'AcceptGrant.Response'

    def test_unknown_directive_returns_error(self, client):
        """Unknown directive should return INTERNAL_ERROR."""
        resp = client.post('/alexa/smarthome', json=make_unknown_directive())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['event']['header']['name'] == 'ErrorResponse'
        assert data['event']['payload']['type'] == 'INTERNAL_ERROR'

    def test_invalid_json_returns_error(self, client):
        """Request without 'directive' key should return error."""
        resp = client.post('/alexa/smarthome', json={'not_a_directive': True})
        assert resp.status_code in (400, 500)


# --- Discovery Tests ---

class TestDiscovery:

    def test_discovery_returns_all_enabled_scenes(self, client, mock_oauth_service, mock_scene_mapping_service):
        """Discovery should return all active, smarthome-enabled scenes."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.list_scenes_for_home.return_value = [
            make_scene_mapping('home1', 'decorations on', 'wh-dec-on'),
            make_scene_mapping('home1', 'night scene', 'wh-night'),
            make_scene_mapping('home1', 'inactive scene', 'wh-inactive', is_active=False),
            make_scene_mapping('home1', 'hidden scene', 'wh-hidden', smarthome_enabled=False),
        ]

        resp = client.post('/alexa/smarthome', json=make_discovery_directive())
        data = resp.get_json()

        endpoints = data['event']['payload']['endpoints']
        assert len(endpoints) == 2

        endpoint_ids = [ep['endpointId'] for ep in endpoints]
        assert 'home1:decorations on' in endpoint_ids
        assert 'home1:night scene' in endpoint_ids

    def test_discovery_endpoint_format(self, client, mock_oauth_service, mock_scene_mapping_service):
        """Each endpoint should have correct format and capabilities."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.list_scenes_for_home.return_value = [
            make_scene_mapping('home1', 'decorations on', 'wh-dec-on'),
        ]

        resp = client.post('/alexa/smarthome', json=make_discovery_directive())
        data = resp.get_json()

        ep = data['event']['payload']['endpoints'][0]
        assert ep['endpointId'] == 'home1:decorations on'
        assert ep['friendlyName'] == 'Decorations On'
        assert ep['manufacturerName'] == 'Voice Guardian'
        assert ep['displayCategories'] == ['SCENE_TRIGGER']
        assert len(ep['capabilities']) == 2

        # SceneController capability
        scene_cap = [c for c in ep['capabilities'] if c['interface'] == 'Alexa.SceneController'][0]
        assert scene_cap['supportsDeactivation'] is True

    def test_discovery_no_scenes_returns_empty(self, client, mock_oauth_service, mock_scene_mapping_service):
        """Discovery with no scenes should return empty endpoints list."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.list_scenes_for_home.return_value = []

        resp = client.post('/alexa/smarthome', json=make_discovery_directive())
        data = resp.get_json()
        assert data['event']['payload']['endpoints'] == []

    def test_discovery_invalid_token_returns_error(self, client, mock_oauth_service):
        """Discovery with invalid token should return auth error."""
        mock_oauth_service.validate_token.return_value = None

        resp = client.post('/alexa/smarthome', json=make_discovery_directive('bad-token'))
        data = resp.get_json()
        assert data['event']['header']['name'] == 'ErrorResponse'
        assert data['event']['payload']['type'] == 'INVALID_AUTHORIZATION_CREDENTIAL'


# --- Activate Tests ---

class TestActivate:

    def test_activate_triggers_scene(self, client, mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
        """Activate should trigger the correct scene via HA service."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.get_webhook_for_scene.return_value = 'wh-dec-on'
        mock_ha_service.trigger_scene.return_value = SceneTriggerResult(
            success=True, message='ok', scene_id='decorations on'
        )

        resp = client.post('/alexa/smarthome', json=make_activate_directive('home1:decorations on'))
        assert resp.status_code == 200

        mock_ha_service.trigger_scene.assert_called_once_with(
            scene_id='decorations on',
            home_id='home1',
            source='Alexa Smart Home',
            webhook_id='wh-dec-on'
        )

    def test_activate_response_format(self, client, mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
        """Activate response should have ActivationStarted format."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.get_webhook_for_scene.return_value = 'wh-dec-on'
        mock_ha_service.trigger_scene.return_value = SceneTriggerResult(
            success=True, message='ok', scene_id='decorations on'
        )

        resp = client.post('/alexa/smarthome', json=make_activate_directive('home1:decorations on'))
        data = resp.get_json()

        assert data['event']['header']['namespace'] == 'Alexa.SceneController'
        assert data['event']['header']['name'] == 'ActivationStarted'
        assert data['event']['header']['correlationToken'] == 'corr-123'
        assert data['event']['endpoint']['endpointId'] == 'home1:decorations on'
        assert data['event']['payload']['cause']['type'] == 'VOICE_INTERACTION'

    def test_activate_invalid_token(self, client, mock_oauth_service):
        """Activate with invalid token should return auth error."""
        mock_oauth_service.validate_token.return_value = None

        resp = client.post('/alexa/smarthome', json=make_activate_directive())
        data = resp.get_json()
        assert data['event']['payload']['type'] == 'INVALID_AUTHORIZATION_CREDENTIAL'

    def test_activate_invalid_endpoint_id(self, client, mock_oauth_service):
        """Activate with malformed endpoint_id should return NO_SUCH_ENDPOINT."""
        mock_oauth_service.validate_token.return_value = 'home1'

        directive = make_activate_directive(endpoint_id='no-colon-here')
        resp = client.post('/alexa/smarthome', json=directive)
        data = resp.get_json()
        assert data['event']['payload']['type'] == 'NO_SUCH_ENDPOINT'


# --- Deactivate Tests ---

class TestDeactivate:

    def test_deactivate_finds_off_scene(self, client, mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
        """Deactivate 'decorations on' should try 'decorations off'."""
        mock_oauth_service.validate_token.return_value = 'home1'
        # First call for 'decorations off' returns a webhook (found)
        mock_scene_mapping_service.get_webhook_for_scene.side_effect = [
            'wh-dec-off',   # _find_deactivation_scene check for 'decorations off'
            'wh-dec-off',   # actual get_webhook_for_scene call in _handle_deactivate
        ]
        mock_ha_service.trigger_scene.return_value = SceneTriggerResult(
            success=True, message='ok', scene_id='decorations off'
        )

        resp = client.post('/alexa/smarthome', json=make_deactivate_directive('home1:decorations on'))
        assert resp.status_code == 200

        # Should trigger the "off" scene
        mock_ha_service.trigger_scene.assert_called_once_with(
            scene_id='decorations off',
            home_id='home1',
            source='Alexa Smart Home',
            webhook_id='wh-dec-off'
        )

    def test_deactivate_falls_back_to_prefix(self, client, mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
        """Deactivate with no matching off scene should use deactivate_ prefix."""
        mock_oauth_service.validate_token.return_value = 'home1'
        # No deactivation scene found for any candidate
        mock_scene_mapping_service.get_webhook_for_scene.return_value = None
        mock_ha_service.trigger_scene.return_value = SceneTriggerResult(
            success=True, message='ok', scene_id='deactivate_night scene'
        )

        resp = client.post('/alexa/smarthome', json=make_deactivate_directive('home1:night scene'))
        assert resp.status_code == 200

        mock_ha_service.trigger_scene.assert_called_once_with(
            scene_id='deactivate_night scene',
            home_id='home1',
            source='Alexa Smart Home',
            webhook_id=None
        )

    def test_deactivate_response_format(self, client, mock_oauth_service, mock_scene_mapping_service, mock_ha_service):
        """Deactivate response should have DeactivationStarted format."""
        mock_oauth_service.validate_token.return_value = 'home1'
        mock_scene_mapping_service.get_webhook_for_scene.return_value = None
        mock_ha_service.trigger_scene.return_value = SceneTriggerResult(
            success=True, message='ok', scene_id='deactivate_test'
        )

        resp = client.post('/alexa/smarthome', json=make_deactivate_directive('home1:test'))
        data = resp.get_json()

        assert data['event']['header']['name'] == 'DeactivationStarted'
        assert data['event']['header']['correlationToken'] == 'corr-789'
        assert data['event']['endpoint']['endpointId'] == 'home1:test'

    def test_deactivate_invalid_token(self, client, mock_oauth_service):
        """Deactivate with invalid token should return auth error."""
        mock_oauth_service.validate_token.return_value = None

        resp = client.post('/alexa/smarthome', json=make_deactivate_directive())
        data = resp.get_json()
        assert data['event']['payload']['type'] == 'INVALID_AUTHORIZATION_CREDENTIAL'


# --- AcceptGrant Tests ---

class TestAcceptGrant:

    def test_accept_grant_returns_success(self, client):
        """AcceptGrant should return AcceptGrant.Response."""
        resp = client.post('/alexa/smarthome', json=make_accept_grant_directive())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['event']['header']['namespace'] == 'Alexa.Authorization'
        assert data['event']['header']['name'] == 'AcceptGrant.Response'
        assert data['event']['payload'] == {}


# --- Deactivation Scene Lookup Tests ---

class TestFindDeactivationScene:

    def test_on_to_off_pattern(self, controller, mock_scene_mapping_service):
        """'decorations on' should look for 'decorations off'."""
        mock_scene_mapping_service.get_webhook_for_scene.side_effect = lambda home_id, name: (
            'wh-off' if name == 'decorations off' else None
        )

        result = controller._find_deactivation_scene('home1', 'decorations on')
        assert result == 'decorations off'

    def test_no_pattern_found(self, controller, mock_scene_mapping_service):
        """Scene with no off variant should return None."""
        mock_scene_mapping_service.get_webhook_for_scene.return_value = None

        result = controller._find_deactivation_scene('home1', 'night scene')
        assert result is None

    def test_no_prefix_tries_no_variant(self, controller, mock_scene_mapping_service):
        """Scene without 'on' suffix should try 'no X' variant."""
        mock_scene_mapping_service.get_webhook_for_scene.side_effect = lambda home_id, name: (
            'wh-no' if name == 'no party mode' else None
        )

        result = controller._find_deactivation_scene('home1', 'party mode')
        assert result == 'no party mode'
