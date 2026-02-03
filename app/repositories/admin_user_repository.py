"""
Admin user repository with pre-configured users

Simple in-memory repository with 5 default admin users.
"""

from typing import Optional, Dict
from datetime import datetime
from app.domain.admin_user import AdminUser


class AdminUserRepository:
    """
    In-memory repository for admin users.

    Pre-configured with 5 admin users:
    1. admin / Admin@2024
    2. karthi / Karthi@2024
    3. operations / Ops@2024
    4. support / Support@2024
    5. developer / Dev@2024
    """

    def __init__(self):
        """Initialize with default admin users."""
        self._users: Dict[str, AdminUser] = {}
        self._create_default_users()

    def _create_default_users(self):
        """Create 5 default admin users."""
        default_admins = [
            {
                'username': 'admin',
                'password': 'Admin@2024',
                'full_name': 'System Administrator',
                'email': 'admin@voiceorchestrator.com'
            },
            {
                'username': 'karthi',
                'password': 'Karthi@2024',
                'full_name': 'Karthikeyan Jeyabalan',
                'email': 'karthi.jeyabalan@gmail.com'
            },
            {
                'username': 'operations',
                'password': 'Ops@2024',
                'full_name': 'Operations Manager',
                'email': 'ops@voiceorchestrator.com'
            },
            {
                'username': 'support',
                'password': 'Support@2024',
                'full_name': 'Support Team',
                'email': 'support@voiceorchestrator.com'
            },
            {
                'username': 'developer',
                'password': 'Dev@2024',
                'full_name': 'Developer Access',
                'email': 'dev@voiceorchestrator.com'
            }
        ]

        for admin_data in default_admins:
            admin = AdminUser(
                username=admin_data['username'],
                password_hash=AdminUser.hash_password(admin_data['password']),
                full_name=admin_data['full_name'],
                email=admin_data['email'],
                is_active=True,
                created_at=datetime.now()
            )
            self._users[admin.username] = admin

    def get_by_username(self, username: str) -> Optional[AdminUser]:
        """
        Get admin user by username.

        Args:
            username: Username to search for

        Returns:
            AdminUser if found, None otherwise
        """
        return self._users.get(username)

    def update_last_login(self, username: str) -> None:
        """
        Update last login timestamp.

        Args:
            username: Username to update
        """
        if username in self._users:
            self._users[username].last_login = datetime.now()

    def authenticate(self, username: str, password: str) -> Optional[AdminUser]:
        """
        Authenticate admin user.

        Args:
            username: Username
            password: Plain text password

        Returns:
            AdminUser if authentication successful, None otherwise
        """
        user = self.get_by_username(username)
        if user and user.is_active and user.check_password(password):
            self.update_last_login(username)
            return user
        return None
