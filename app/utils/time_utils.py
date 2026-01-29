"""
Time and datetime utilities

Helper functions for working with timestamps and expiry logic.
"""

from datetime import datetime, timedelta
from typing import Optional


def get_current_time() -> datetime:
    """
    Get current datetime.

    Abstraction to make testing easier.

    Returns:
        Current datetime
    """
    return datetime.now()


def calculate_expiry_time(
    created_at: datetime,
    expiry_seconds: int
) -> datetime:
    """
    Calculate expiry time from creation time and duration.

    Args:
        created_at: When the item was created
        expiry_seconds: How many seconds until expiry

    Returns:
        Expiry datetime

    Examples:
        >>> created = datetime(2026, 1, 29, 12, 0, 0)
        >>> calculate_expiry_time(created, 60)
        datetime(2026, 1, 29, 12, 1, 0)
    """
    return created_at + timedelta(seconds=expiry_seconds)


def is_expired(
    expires_at: datetime,
    current_time: Optional[datetime] = None
) -> bool:
    """
    Check if something has expired.

    Args:
        expires_at: Expiry datetime
        current_time: Time to check against (defaults to now)

    Returns:
        True if expired, False otherwise

    Examples:
        >>> expires = datetime(2026, 1, 29, 12, 0, 0)
        >>> current = datetime(2026, 1, 29, 12, 1, 0)
        >>> is_expired(expires, current)
        True
    """
    if current_time is None:
        current_time = get_current_time()

    return current_time > expires_at


def seconds_until_expiry(
    expires_at: datetime,
    current_time: Optional[datetime] = None
) -> float:
    """
    Calculate how many seconds until expiry.

    Args:
        expires_at: Expiry datetime
        current_time: Time to check against (defaults to now)

    Returns:
        Seconds until expiry (negative if already expired)

    Examples:
        >>> expires = datetime(2026, 1, 29, 12, 1, 0)
        >>> current = datetime(2026, 1, 29, 12, 0, 30)
        >>> seconds_until_expiry(expires, current)
        30.0
    """
    if current_time is None:
        current_time = get_current_time()

    delta = expires_at - current_time
    return delta.total_seconds()


def seconds_since_creation(
    created_at: datetime,
    current_time: Optional[datetime] = None
) -> float:
    """
    Calculate how many seconds since creation.

    Args:
        created_at: Creation datetime
        current_time: Time to check against (defaults to now)

    Returns:
        Seconds since creation

    Examples:
        >>> created = datetime(2026, 1, 29, 12, 0, 0)
        >>> current = datetime(2026, 1, 29, 12, 0, 30)
        >>> seconds_since_creation(created, current)
        30.0
    """
    if current_time is None:
        current_time = get_current_time()

    delta = current_time - created_at
    return delta.total_seconds()
