"""Tests for Smart Home request and response DTOs."""

import uuid
import pytest
from app.dto.base import ValidationError
from app.dto.requests.smarthome_request import SmartHomeDirective
from app.dto.responses.smarthome_response import SmartHomeResponse


# ── SmartHomeDirective (request) tests ──────────────────────────────────────

class TestSmartHomeDirective:

    def _discovery_request(self):
        return {
            "directive": {
                "header": {
                    "namespace": "Alexa.Discovery",
                    "name": "Discover",
                    "payloadVersion": "3",
                    "messageId": "msg-001"
                },
                "payload": {
                    "scope": {
                        "type": "BearerToken",
                        "token": "discovery-token-xyz"
                    }
                }
            }
        }

    def _activation_request(self):
        return {
            "directive": {
                "header": {
                    "namespace": "Alexa.SceneController",
                    "name": "Activate",
                    "payloadVersion": "3",
                    "messageId": "msg-002",
                    "correlationToken": "corr-abc"
                },
                "endpoint": {
                    "scope": {
                        "type": "BearerToken",
                        "token": "endpoint-token-xyz"
                    },
                    "endpointId": "scene-holidays-on"
                },
                "payload": {}
            }
        }

    def test_from_dict_discovery(self):
        directive = SmartHomeDirective.from_dict(self._discovery_request())
        assert directive.namespace == "Alexa.Discovery"
        assert directive.name == "Discover"
        assert directive.message_id == "msg-001"
        assert directive.payload_version == "3"
        assert directive.bearer_token == "discovery-token-xyz"
        assert directive.endpoint_id is None
        assert directive.correlation_token is None

    def test_from_dict_activation(self):
        directive = SmartHomeDirective.from_dict(self._activation_request())
        assert directive.namespace == "Alexa.SceneController"
        assert directive.name == "Activate"
        assert directive.message_id == "msg-002"
        assert directive.correlation_token == "corr-abc"
        assert directive.endpoint_id == "scene-holidays-on"
        assert directive.bearer_token == "endpoint-token-xyz"

    def test_from_dict_missing_directive_key(self):
        with pytest.raises(ValidationError, match="Missing 'directive'"):
            SmartHomeDirective.from_dict({"something": "else"})

    def test_from_dict_empty_directive(self):
        data = {"directive": {}}
        directive = SmartHomeDirective.from_dict(data)
        assert directive.namespace == ""
        assert directive.name == ""
        assert directive.message_id == ""
        assert directive.endpoint_id is None
        assert directive.bearer_token is None

    def test_from_dict_preserves_raw_data(self):
        raw = self._discovery_request()
        directive = SmartHomeDirective.from_dict(raw)
        assert directive.raw_data is raw

    def test_bearer_token_from_endpoint_scope_preferred(self):
        """When both endpoint and payload have scope, endpoint wins."""
        data = {
            "directive": {
                "header": {"namespace": "X", "name": "Y", "messageId": "m1"},
                "endpoint": {
                    "scope": {"token": "endpoint-tok"},
                    "endpointId": "ep1"
                },
                "payload": {
                    "scope": {"token": "payload-tok"}
                }
            }
        }
        directive = SmartHomeDirective.from_dict(data)
        assert directive.bearer_token == "endpoint-tok"

    def test_bearer_token_falls_back_to_payload_scope(self):
        data = {
            "directive": {
                "header": {"namespace": "X", "name": "Y", "messageId": "m1"},
                "payload": {
                    "scope": {"token": "payload-tok"}
                }
            }
        }
        directive = SmartHomeDirective.from_dict(data)
        assert directive.bearer_token == "payload-tok"

    def test_default_payload_version(self):
        data = {
            "directive": {
                "header": {"namespace": "X", "name": "Y", "messageId": "m1"},
                "payload": {}
            }
        }
        directive = SmartHomeDirective.from_dict(data)
        assert directive.payload_version == "3"


# ── SmartHomeResponse (response builder) tests ─────────────────────────────

class TestSmartHomeResponse:

    def test_discovery_response_structure(self):
        endpoints = [{"endpointId": "ep1"}, {"endpointId": "ep2"}]
        resp = SmartHomeResponse.discovery_response(endpoints)

        header = resp["event"]["header"]
        assert header["namespace"] == "Alexa.Discovery"
        assert header["name"] == "Discover.Response"
        assert header["payloadVersion"] == "3"
        # messageId should be a valid UUID
        uuid.UUID(header["messageId"])

        assert resp["event"]["payload"]["endpoints"] == endpoints

    def test_discovery_response_empty_endpoints(self):
        resp = SmartHomeResponse.discovery_response([])
        assert resp["event"]["payload"]["endpoints"] == []

    def test_build_scene_endpoint_defaults(self):
        ep = SmartHomeResponse.build_scene_endpoint("scene-1", "Movie Night")
        assert ep["endpointId"] == "scene-1"
        assert ep["friendlyName"] == "Movie Night"
        assert ep["manufacturerName"] == "Voice Guardian"
        assert ep["description"] == "Voice Guardian scene: Movie Night"
        assert ep["displayCategories"] == ["SCENE_TRIGGER"]
        assert len(ep["capabilities"]) == 2
        scene_cap = ep["capabilities"][0]
        assert scene_cap["interface"] == "Alexa.SceneController"
        assert scene_cap["supportsDeactivation"] is True

    def test_build_scene_endpoint_custom_values(self):
        ep = SmartHomeResponse.build_scene_endpoint(
            "scene-2", "Party", description="Custom desc",
            manufacturer="Acme", supports_deactivation=False
        )
        assert ep["description"] == "Custom desc"
        assert ep["manufacturerName"] == "Acme"
        assert ep["capabilities"][0]["supportsDeactivation"] is False

    def test_activation_started(self):
        resp = SmartHomeResponse.activation_started("msg-1", "corr-1", "ep-1")
        header = resp["event"]["header"]
        assert header["namespace"] == "Alexa.SceneController"
        assert header["name"] == "ActivationStarted"
        assert header["correlationToken"] == "corr-1"
        assert resp["event"]["endpoint"]["endpointId"] == "ep-1"
        assert resp["event"]["payload"]["cause"]["type"] == "VOICE_INTERACTION"
        assert "timestamp" in resp["event"]["payload"]

    def test_deactivation_started(self):
        resp = SmartHomeResponse.deactivation_started("msg-2", "corr-2", "ep-2")
        header = resp["event"]["header"]
        assert header["name"] == "DeactivationStarted"
        assert header["correlationToken"] == "corr-2"
        assert resp["event"]["endpoint"]["endpointId"] == "ep-2"
        assert resp["event"]["payload"]["cause"]["type"] == "VOICE_INTERACTION"

    def test_accept_grant_response(self):
        resp = SmartHomeResponse.accept_grant_response()
        header = resp["event"]["header"]
        assert header["namespace"] == "Alexa.Authorization"
        assert header["name"] == "AcceptGrant.Response"
        assert resp["event"]["payload"] == {}

    def test_error_response(self):
        resp = SmartHomeResponse.error_response(
            "msg-err", "INTERNAL_ERROR", "Something broke"
        )
        header = resp["event"]["header"]
        assert header["namespace"] == "Alexa"
        assert header["name"] == "ErrorResponse"
        payload = resp["event"]["payload"]
        assert payload["type"] == "INTERNAL_ERROR"
        assert payload["message"] == "Something broke"

    def test_unique_message_ids(self):
        """Each call should generate a unique messageId."""
        r1 = SmartHomeResponse.accept_grant_response()
        r2 = SmartHomeResponse.accept_grant_response()
        assert r1["event"]["header"]["messageId"] != r2["event"]["header"]["messageId"]
