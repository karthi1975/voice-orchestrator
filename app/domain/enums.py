"""
Domain enums for voice orchestrator

Defines core business enums used across the application.
"""

from enum import Enum


class ClientType(str, Enum):
    """
    Type of client making authentication requests.

    Attributes:
        ALEXA: Amazon Alexa skill integration (session-based)
        FUTUREPROOFHOME: FutureProof Homes integration (home_id-based)
    """
    ALEXA = "alexa"
    FUTUREPROOFHOME = "futureproofhome"


class ChallengeStatus(str, Enum):
    """
    Status of a voice authentication challenge.

    Attributes:
        PENDING: Challenge issued, awaiting response
        VALIDATED: Challenge successfully validated
        EXPIRED: Challenge expired before validation
        FAILED: Challenge validation failed (wrong response or max attempts)
    """
    PENDING = "pending"
    VALIDATED = "validated"
    EXPIRED = "expired"
    FAILED = "failed"
