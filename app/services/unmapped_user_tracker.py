"""
Unmapped user tracker service

Tracks Alexa users who try to use the skill but aren't mapped to a home yet.
Provides easy admin interface to assign them.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class UnmappedUser:
    """
    Represents an unmapped Alexa user.

    Attributes:
        alexa_user_id: Amazon user ID
        first_seen: When we first saw this user
        last_seen: Most recent attempt
        attempt_count: Number of times they tried to use the skill
    """
    alexa_user_id: str
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    attempt_count: int = 1


class UnmappedUserTracker:
    """
    Singleton service to track unmapped Alexa users.

    Uses in-memory storage for simplicity. Survives until server restart.
    """

    _instance = None
    _unmapped_users: Dict[str, UnmappedUser] = {}

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(UnmappedUserTracker, cls).__new__(cls)
            cls._unmapped_users = {}
        return cls._instance

    def record_unmapped_user(self, alexa_user_id: str) -> None:
        """
        Record an unmapped Alexa user attempt.

        Args:
            alexa_user_id: Amazon user ID that attempted to use the skill
        """
        if alexa_user_id in self._unmapped_users:
            # Update existing record
            user = self._unmapped_users[alexa_user_id]
            user.last_seen = datetime.now()
            user.attempt_count += 1
            logger.info(f"Unmapped user {alexa_user_id[:20]}... attempted again (total: {user.attempt_count})")
        else:
            # New unmapped user
            self._unmapped_users[alexa_user_id] = UnmappedUser(
                alexa_user_id=alexa_user_id
            )
            logger.warning(f"NEW unmapped Alexa user detected: {alexa_user_id[:20]}... (total unmapped: {len(self._unmapped_users)})")

    def get_unmapped_users(self) -> List[UnmappedUser]:
        """
        Get all unmapped users, sorted by most recent.

        Returns:
            List of UnmappedUser objects, sorted by last_seen desc
        """
        users = list(self._unmapped_users.values())
        users.sort(key=lambda u: u.last_seen, reverse=True)
        return users

    def remove_unmapped_user(self, alexa_user_id: str) -> None:
        """
        Remove a user from unmapped list (after they've been mapped).

        Args:
            alexa_user_id: Amazon user ID that was just mapped
        """
        if alexa_user_id in self._unmapped_users:
            del self._unmapped_users[alexa_user_id]
            logger.info(f"Removed {alexa_user_id[:20]}... from unmapped list")

    def clear_all(self) -> None:
        """Clear all unmapped users (for testing)."""
        count = len(self._unmapped_users)
        self._unmapped_users.clear()
        logger.info(f"Cleared {count} unmapped users")


# Global singleton instance
_tracker = UnmappedUserTracker()


def get_tracker() -> UnmappedUserTracker:
    """Get the global unmapped user tracker instance."""
    return _tracker
