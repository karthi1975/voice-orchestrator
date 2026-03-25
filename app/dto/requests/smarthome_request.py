"""
Smart Home directive request parser.

Parses Alexa Smart Home Skill API v3 directives.
"""

from dataclasses import dataclass
from typing import Optional, Dict
from app.dto.base import BaseDTO, ValidationError


@dataclass
class SmartHomeDirective(BaseDTO):
    """Parsed Alexa Smart Home directive."""
    namespace: str
    name: str
    message_id: str
    payload_version: str = "3"
    correlation_token: Optional[str] = None
    endpoint_id: Optional[str] = None
    bearer_token: Optional[str] = None
    payload: Optional[Dict] = None
    raw_data: Optional[Dict] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'SmartHomeDirective':
        """Parse Smart Home directive from Alexa JSON."""
        if 'directive' not in data:
            raise ValidationError("Missing 'directive' in request")

        directive = data['directive']
        header = directive.get('header', {})
        endpoint = directive.get('endpoint', {})
        payload = directive.get('payload', {})

        # Extract bearer token from endpoint scope or payload scope
        bearer_token = None
        if endpoint and 'scope' in endpoint:
            bearer_token = endpoint['scope'].get('token')
        elif payload and 'scope' in payload:
            bearer_token = payload['scope'].get('token')

        return cls(
            namespace=header.get('namespace', ''),
            name=header.get('name', ''),
            message_id=header.get('messageId', ''),
            payload_version=header.get('payloadVersion', '3'),
            correlation_token=header.get('correlationToken'),
            endpoint_id=endpoint.get('endpointId') if endpoint else None,
            bearer_token=bearer_token,
            payload=payload,
            raw_data=data
        )
