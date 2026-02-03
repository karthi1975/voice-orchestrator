"""
Admin user domain model

Represents an admin user who can access the admin dashboard.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AdminUser:
    """
    Admin user entity for dashboard authentication.

    Attributes:
        username: Unique username for login
        password_hash: Bcrypt hashed password
        full_name: Admin's full name
        email: Admin's email address
        is_active: Whether the admin account is active
        created_at: When the admin was created
        last_login: Last login timestamp
    """
    username: str
    password_hash: str
    full_name: str
    email: str
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None

    def check_password(self, password: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password to check

        Returns:
            True if password matches
        """
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password, method='pbkdf2:sha256')
