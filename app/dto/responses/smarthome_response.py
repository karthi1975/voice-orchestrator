"""
Smart Home response builder.

Builds Alexa Smart Home Skill API v3 responses.
"""

import uuid
from datetime import datetime, timezone


class SmartHomeResponse:
    """Builds Alexa Smart Home API v3 response payloads."""

    @staticmethod
    def discovery_response(endpoints: list) -> dict:
        """Build Discover.Response with list of endpoints/scenes."""
        return {
            "event": {
                "header": {
                    "namespace": "Alexa.Discovery",
                    "name": "Discover.Response",
                    "payloadVersion": "3",
                    "messageId": str(uuid.uuid4())
                },
                "payload": {
                    "endpoints": endpoints
                }
            }
        }

    @staticmethod
    def build_scene_endpoint(endpoint_id: str, friendly_name: str, description: str = "", manufacturer: str = "Voice Guardian", supports_deactivation: bool = True) -> dict:
        """Build a single scene endpoint for discovery."""
        return {
            "endpointId": endpoint_id,
            "manufacturerName": manufacturer,
            "friendlyName": friendly_name,
            "description": description or f"Voice Guardian scene: {friendly_name}",
            "displayCategories": ["SCENE_TRIGGER"],
            "cookie": {},
            "capabilities": [
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa.SceneController",
                    "version": "3",
                    "supportsDeactivation": supports_deactivation
                },
                {
                    "type": "AlexaInterface",
                    "interface": "Alexa",
                    "version": "3"
                }
            ]
        }

    @staticmethod
    def activation_started(message_id: str, correlation_token: str, endpoint_id: str) -> dict:
        """Build ActivationStarted response for scene activation."""
        return {
            "event": {
                "header": {
                    "namespace": "Alexa.SceneController",
                    "name": "ActivationStarted",
                    "payloadVersion": "3",
                    "messageId": str(uuid.uuid4()),
                    "correlationToken": correlation_token
                },
                "endpoint": {
                    "endpointId": endpoint_id
                },
                "payload": {
                    "cause": {
                        "type": "VOICE_INTERACTION"
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    @staticmethod
    def deactivation_started(message_id: str, correlation_token: str, endpoint_id: str) -> dict:
        """Build DeactivationStarted response for scene deactivation."""
        return {
            "event": {
                "header": {
                    "namespace": "Alexa.SceneController",
                    "name": "DeactivationStarted",
                    "payloadVersion": "3",
                    "messageId": str(uuid.uuid4()),
                    "correlationToken": correlation_token
                },
                "endpoint": {
                    "endpointId": endpoint_id
                },
                "payload": {
                    "cause": {
                        "type": "VOICE_INTERACTION"
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        }

    @staticmethod
    def accept_grant_response() -> dict:
        """Build AcceptGrant.Response for account linking."""
        return {
            "event": {
                "header": {
                    "namespace": "Alexa.Authorization",
                    "name": "AcceptGrant.Response",
                    "payloadVersion": "3",
                    "messageId": str(uuid.uuid4())
                },
                "payload": {}
            }
        }

    @staticmethod
    def error_response(message_id: str, error_type: str, message: str) -> dict:
        """Build error response.

        Common error types:
        - INVALID_AUTHORIZATION_CREDENTIAL
        - EXPIRED_AUTHORIZATION_CREDENTIAL
        - INTERNAL_ERROR
        - NO_SUCH_ENDPOINT
        """
        return {
            "event": {
                "header": {
                    "namespace": "Alexa",
                    "name": "ErrorResponse",
                    "payloadVersion": "3",
                    "messageId": str(uuid.uuid4())
                },
                "payload": {
                    "type": error_type,
                    "message": message
                }
            }
        }
