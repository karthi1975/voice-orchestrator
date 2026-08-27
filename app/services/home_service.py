"""
Home service for multi-tenant home management

Business logic for home registration, updates, and lifecycle management.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from app.domain.models import Home
from app.repositories.home_repository import IHomeRepository
from app.repositories.user_repository import IUserRepository


class HomeService:
    """
    Service for managing homes in multi-tenant system.

    Handles:
    - Home registration with user validation
    - Home retrieval by various criteria
    - Home updates including HA configuration
    - Home activation/deactivation

    Dependencies:
    - IHomeRepository: Storage abstraction for homes
    - IUserRepository: Storage abstraction for users (validation)
    """

    def __init__(
        self,
        home_repository: IHomeRepository,
        user_repository: IUserRepository,
        token_vault=None
    ):
        """
        Initialize home service.

        Args:
            home_repository: Repository for home storage
            user_repository: Repository for user validation
        """
        self._home_repository = home_repository
        self._user_repository = user_repository
        if token_vault is None:
            from app.infrastructure.security.token_vault import TokenVault
            token_vault = TokenVault()
        self._vault = token_vault

    def register_home(
        self,
        home_id: str,
        user_id: str,
        name: str,
        ha_url: str,
        ha_webhook_id: str
    ) -> Home:
        """
        Register a new home.

        Args:
            home_id: Unique home identifier
            user_id: Owner user ID
            name: Home name
            ha_url: Home Assistant URL
            ha_webhook_id: HA webhook ID for voice auth

        Returns:
            Created home

        Raises:
            ValueError: If home_id already exists or user not found
        """
        # Validate user exists
        if not self._user_repository.exists(user_id):
            raise ValueError(f"User with ID '{user_id}' not found")

        # Create home domain model
        home = Home(
            home_id=home_id,
            user_id=user_id,
            name=name,
            ha_url=ha_url,
            ha_webhook_id=ha_webhook_id,
            is_active=True,
            created_at=datetime.now()
        )

        # Persist to repository
        return self._home_repository.add(home)

    def get_home(self, home_id: str) -> Home:
        """
        Get home by ID.

        Args:
            home_id: Home ID

        Returns:
            Home

        Raises:
            ValueError: If home not found
        """
        home = self._home_repository.get_by_id(home_id)
        if not home:
            raise ValueError(f"Home with ID '{home_id}' not found")
        return home

    def get_user_homes(self, user_id: str, active_only: bool = True) -> List[Home]:
        """
        Get all homes for a user.

        Args:
            user_id: User ID
            active_only: If True, only return active homes

        Returns:
            List of homes
        """
        return self._home_repository.list_by_user(user_id, active_only=active_only)

    def list_homes(self, active_only: bool = False) -> List[Home]:
        """
        List all homes.

        Args:
            active_only: If True, only return active homes

        Returns:
            List of homes
        """
        if active_only:
            return self._home_repository.list_active()
        return self._home_repository.list_all()

    def update_home(
        self,
        home_id: str,
        name: Optional[str] = None,
        ha_url: Optional[str] = None,
        ha_webhook_id: Optional[str] = None,
        test_mode: Optional[bool] = None
    ) -> Home:
        """
        Update home details.

        Args:
            home_id: Home ID
            name: New name (optional)
            ha_url: New HA URL (optional)
            ha_webhook_id: New webhook ID (optional)
            test_mode: Test mode flag (optional) - skips HA integration if True

        Returns:
            Updated home

        Raises:
            ValueError: If home not found
        """
        # Get existing home
        home = self.get_home(home_id)

        # Update fields if provided
        updated_home = Home(
            home_id=home.home_id,
            user_id=home.user_id,
            name=name if name is not None else home.name,
            ha_url=ha_url if ha_url is not None else home.ha_url,
            ha_webhook_id=ha_webhook_id if ha_webhook_id is not None else home.ha_webhook_id,
            is_active=home.is_active,
            test_mode=test_mode if test_mode is not None else home.test_mode,
            created_at=home.created_at,
            updated_at=datetime.now()
        )

        return self._home_repository.update(updated_home)

    def deactivate_home(self, home_id: str) -> Home:
        """
        Deactivate a home (soft delete).

        Args:
            home_id: Home ID

        Returns:
            Deactivated home

        Raises:
            ValueError: If home not found
        """
        if not self._home_repository.deactivate(home_id):
            raise ValueError(f"Home with ID '{home_id}' not found")

        return self.get_home(home_id)

    def activate_home(self, home_id: str) -> Home:
        """
        Activate a previously deactivated home.

        Args:
            home_id: Home ID

        Returns:
            Activated home

        Raises:
            ValueError: If home not found
        """
        if not self._home_repository.activate(home_id):
            raise ValueError(f"Home with ID '{home_id}' not found")

        return self.get_home(home_id)

    def delete_home(self, home_id: str) -> bool:
        """
        Permanently delete a home.

        Args:
            home_id: Home ID

        Returns:
            True if deleted, False if not found
        """
        return self._home_repository.delete(home_id)


    # ------------------------------------------------------------------
    # Encrypted per-home HA tokens (portal-managed; replaces the SSH-only
    # HOME_CONFIGS_JSON workflow — env JSON remains a legacy fallback).
    # ------------------------------------------------------------------

    def set_ha_token(self, home_id: str, plain_token: Optional[str]) -> bool:
        """Encrypt and store a home's HA long-lived token.

        Empty/None clears the stored token (dispatcher then falls back to
        the legacy HOME_CONFIGS_JSON env var, if the home is listed there).

        Returns True when stored/cleared; raises ValueError if home missing.
        """
        home = self._home_repository.get_by_home_id(home_id)
        if home is None:
            raise ValueError(f"Home '{home_id}' not found")
        encrypted = self._vault.encrypt(plain_token)
        return self._home_repository.set_ha_token(home_id, encrypted)

    def get_ha_credentials(self, home_id: str) -> Optional[Tuple[str, str]]:
        """(ha_url, decrypted token) for an ACTIVE home with a DB token.

        Returns None when the home is missing, inactive, or has no stored
        token — callers (the dispatcher) fall back to legacy env config.
        Never raises: this sits on the hot dispatch path.
        """
        try:
            home = self._home_repository.get_by_home_id(home_id)
        except Exception:
            return None
        if home is None or not home.is_active or not home.ha_token_encrypted:
            return None
        token = self._vault.decrypt(home.ha_token_encrypted)
        if not token or not home.ha_url:
            return None
        return (home.ha_url.strip(), token)

    def get_stored_ha_token(self, home_id: str) -> Optional[str]:
        """Decrypted stored token regardless of active flag (admin tests)."""
        home = self._home_repository.get_by_home_id(home_id)
        if home is None or not home.ha_token_encrypted:
            return None
        return self._vault.decrypt(home.ha_token_encrypted)

    def token_status(self, home_id: str) -> dict:
        """Non-secret token metadata for admin UI: presence + display hint."""
        home = self._home_repository.get_by_home_id(home_id)
        if home is None or not home.ha_token_encrypted:
            return {"has_token": False, "token_hint": None}
        from app.infrastructure.security.token_vault import TokenVault
        token = self._vault.decrypt(home.ha_token_encrypted)
        return {"has_token": token is not None,
                "token_hint": TokenVault.hint(token)}

    def get_ha_config(self, home_id: str) -> Tuple[str, str]:
        """
        Get Home Assistant configuration for a home.

        Args:
            home_id: Home ID

        Returns:
            Tuple of (ha_url, ha_webhook_id)

        Raises:
            ValueError: If home not found or inactive
        """
        home = self.get_home(home_id)

        if not home.is_active:
            raise ValueError(f"Home '{home_id}' is not active")

        return (home.ha_url, home.ha_webhook_id)

    def update_ha_config(
        self,
        home_id: str,
        ha_url: Optional[str] = None,
        ha_webhook_id: Optional[str] = None
    ) -> Home:
        """
        Update Home Assistant configuration.

        Args:
            home_id: Home ID
            ha_url: New HA URL (optional)
            ha_webhook_id: New webhook ID (optional)

        Returns:
            Updated home

        Raises:
            ValueError: If home not found
        """
        if not self._home_repository.update_ha_config(home_id, ha_url, ha_webhook_id):
            raise ValueError(f"Home with ID '{home_id}' not found")

        return self.get_home(home_id)

    def home_exists(self, home_id: str) -> bool:
        """
        Check if home exists.

        Args:
            home_id: Home ID

        Returns:
            True if home exists, False otherwise
        """
        return self._home_repository.exists(home_id)

    def validate_home_access(self, user_id: str, home_id: str) -> bool:
        """
        Validate that a user has access to a home.

        Args:
            user_id: User ID
            home_id: Home ID

        Returns:
            True if user owns the home, False otherwise
        """
        return self._home_repository.exists_for_user(user_id, home_id)
