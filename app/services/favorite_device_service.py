"""Business logic for FavoriteDevice management.

A favorite is a user-pinned HA item — device, scene, script, automation,
or raw entity — within one of the user's homes. The service:

  - validates home_id against the dispatcher's HOME_CONFIGS_JSON
  - resolves device_id -> primary controllable entity via the device registry
  - rejects sensor-only devices with NO_CONTROLLABLE_ENTITY
  - infers `kind` from entity_id prefix (scene/script/automation/entity)
  - auto-creates a voice-auth enrollment for any `lock.*` entity, since
    locks must always go through the spoken phrase challenge
  - assigns the next position; caller can override

Inputs to add_favorite are mutually exclusive: pass `device_id` OR
`entity_id`, never both, never neither.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from app.domain.models import FavoriteDevice
from app.domain.voice_auth_enums import ChallengeType
from app.infrastructure.home_assistant.device_registry import HADeviceRegistry, PRIMARY_DOMAINS
from app.repositories.favorite_device_repository import IFavoriteDeviceRepository

logger = logging.getLogger(__name__)


# Domains that produce specific `kind` values when favorited as raw entities.
ACTIVATION_DOMAINS = {"scene", "script", "automation"}


class NoControllableEntityError(ValueError):
    """Device has no entity in PRIMARY_DOMAINS — can't be triggered."""


class ConflictingArgumentsError(ValueError):
    """Both device_id and entity_id supplied, or neither."""


@dataclass
class AddFavoriteResult:
    favorite: FavoriteDevice
    voice_auth_enrollment_id: Optional[str] = None  # set when a lock auto-enrolled


class FavoriteDeviceService:
    def __init__(
        self,
        favorite_repository: IFavoriteDeviceRepository,
        home_validator: Optional[Callable[[str], bool]] = None,
        device_registry: Optional[HADeviceRegistry] = None,
        voice_auth_service=None,  # VoiceAuthService — late-bound to avoid circular import
    ):
        """
        home_validator: callable(home_id) -> bool. Wire to dispatcher.has_home.
        device_registry: required to resolve device_id -> primary entity.
        voice_auth_service: required to auto-enroll lock favorites.
        """
        self._repo = favorite_repository
        self._home_valid = home_validator
        self._registry = device_registry
        self._va = voice_auth_service

    # ---- public API --------------------------------------------------------

    def add_favorite(
        self,
        user_ref: str,
        home_id: str,
        entity_id: Optional[str] = None,
        device_id: Optional[str] = None,
        friendly_name: Optional[str] = None,
        position: Optional[int] = None,
    ) -> AddFavoriteResult:
        # ---- input validation -----------------------------------------
        if not user_ref or not user_ref.strip():
            raise ValueError("user_ref is required")
        if not home_id or not home_id.strip():
            raise ValueError("home_id is required")

        if entity_id and device_id:
            raise ConflictingArgumentsError(
                "send either device_id or entity_id, not both"
            )
        if not entity_id and not device_id:
            raise ConflictingArgumentsError(
                "one of device_id or entity_id is required"
            )

        if self._home_valid is not None and not self._home_valid(home_id):
            raise ValueError(f"home '{home_id}' not found")

        # ---- resolve to (entity_id, device_id, kind, friendly_name) ---
        resolved_device_id: Optional[str] = None
        resolved_primary: Optional[str] = None
        kind: str

        if device_id:
            if self._registry is None:
                raise RuntimeError("device_registry not configured; cannot favorite by device_id")
            dev = self._registry.get_device(home_id, device_id)
            if dev is None:
                raise ValueError(f"device '{device_id}' not found in home '{home_id}'")
            if not dev.is_controllable:
                raise NoControllableEntityError(
                    f"device '{dev.name}' has no controllable entity (sensors/diagnostics only)"
                )
            entity_id = dev.primary_entity_id  # type: ignore[assignment]
            resolved_device_id = dev.device_id
            resolved_primary = dev.primary_entity_id
            friendly_name = (friendly_name or dev.name or "").strip()
            kind = "device"
        else:
            # entity-style favorite
            if "." not in entity_id:
                raise ValueError("entity_id must be of the form '<domain>.<suffix>'")
            domain_check = entity_id.split(".", 1)[0]
            kind = domain_check if domain_check in ACTIVATION_DOMAINS else "entity"
            # Try to attach device_id transparently if the entity is bound to one
            if self._registry is not None:
                resolved_device_id = self._registry.device_id_for_entity(home_id, entity_id)

        # entity_id is now guaranteed populated
        domain, _, suffix = entity_id.partition(".")
        if not domain or not suffix:
            raise ValueError("entity_id must be of the form '<domain>.<suffix>'")

        label = (friendly_name or suffix).strip()
        if position is None:
            existing = self._repo.list_for_user_home(user_ref, home_id)
            position = (existing[-1].position + 1) if existing else 0

        # ---- lock voice-gating (auto-enroll BEFORE inserting favorite) -
        enrollment_id: Optional[str] = None
        if domain == "lock":
            enrollment_id = self._ensure_lock_enrollment(
                user_ref=user_ref.strip(),
                home_id=home_id.strip(),
                entity_suffix=suffix,
                friendly_name=label,
            )
            # If we couldn't enroll (service unavailable), refuse the favorite.
            if enrollment_id is None:
                raise RuntimeError(
                    "lock favorites require voice-auth enrollment, which is unavailable"
                )

        # ---- insert -----------------------------------------------------
        fav = FavoriteDevice(
            id=str(uuid.uuid4()),
            user_ref=user_ref.strip(),
            home_id=home_id.strip(),
            entity_id=entity_id.strip(),
            friendly_name=label,
            domain=domain,
            kind=kind,
            device_id=resolved_device_id,
            primary_entity_id=resolved_primary,
            position=int(position),
            created_at=datetime.utcnow(),
        )
        out = self._repo.add(fav)
        logger.info(
            f"FAVORITE add user={user_ref} home={home_id} entity={entity_id} "
            f"kind={kind} device={resolved_device_id} pos={out.position} "
            f"enrollment={enrollment_id or '-'}"
        )
        return AddFavoriteResult(favorite=out, voice_auth_enrollment_id=enrollment_id)

    def list_favorites(self, user_ref: str, home_id: str) -> List[FavoriteDevice]:
        if not user_ref or not home_id:
            raise ValueError("user_ref and home_id are required")
        return self._repo.list_for_user_home(user_ref, home_id)

    def get(self, favorite_id: str) -> Optional[FavoriteDevice]:
        return self._repo.get_by_id(favorite_id)

    def remove_favorite(self, favorite_id: str) -> bool:
        ok = self._repo.delete(favorite_id)
        if ok:
            logger.info(f"FAVORITE delete id={favorite_id}")
        return ok

    def reorder(self, items: List[dict]) -> List[FavoriteDevice]:
        updated: List[FavoriteDevice] = []
        for entry in items:
            fav_id = entry.get("id")
            position = entry.get("position")
            if not fav_id or position is None:
                continue
            row = self._repo.update_position(fav_id, int(position))
            if row:
                updated.append(row)
        logger.info(f"FAVORITE reorder updated_count={len(updated)} requested={len(items)}")
        return updated

    # ---- internals --------------------------------------------------------

    def _ensure_lock_enrollment(
        self,
        *,
        user_ref: str,
        home_id: str,
        entity_suffix: str,
        friendly_name: str,
    ) -> Optional[str]:
        """Idempotently ensure a voice-auth enrollment exists for this lock entity.

        Returns the enrollment id, or None if the voice-auth service is unwired.
        VoiceAuthService.create_enrollment is itself idempotent on
        (user_ref, automation_id), so re-calling on duplicate favorite attempts
        returns the existing enrollment.
        """
        if self._va is None:
            logger.error(
                f"LOCK_AUTO_ENROLL skipped — VoiceAuthService not wired "
                f"user={user_ref} entity=lock.{entity_suffix}"
            )
            return None
        try:
            enrollment = self._va.create_enrollment(
                user_ref=user_ref,
                home_id=home_id,
                automation_name=friendly_name,
                ha_service="lock",
                ha_entity=entity_suffix,
                challenge_type=ChallengeType.STEP_UP,  # locks require step-up
                max_attempts=3,
                cooldown_seconds=60,  # tighter cooldown for security devices
                created_by="favorite_auto_lock",
            )
            logger.info(
                f"LOCK_AUTO_ENROLL ok user={user_ref} entity=lock.{entity_suffix} "
                f"enrollment_id={enrollment.id}"
            )
            return enrollment.id
        except Exception as e:
            logger.error(
                f"LOCK_AUTO_ENROLL failed user={user_ref} entity=lock.{entity_suffix}: {e}",
                exc_info=True,
            )
            return None
