"""Voice-enable provisioning: bind a VAPI phone number to a (user_ref, home_id).

Composes VapiClient (HTTP to api.vapi.ai) with VoiceAuthService's existing
phone-mapping persistence. The split keeps the HTTP surface mockable and
the local DB transactional integrity in one place.

Idempotency contract:
  - If the user already has an active phone mapping with a vapi_phone_number_id,
    `enable()` returns it unchanged. No second VAPI purchase.
  - If a VAPI purchase succeeds but the local persist fails, we attempt to
    release the VAPI number (best-effort) so we don't leak a paid resource.

Billing note:
  - `enable()` is a billable side effect on VAPI when running live. The
    controller layer should be behind authn (bearer-key middleware) and
    rate-limited per user_ref. This service does not enforce rate limits.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from app.domain.voice_auth_models import PhoneMapping
from app.infrastructure.vapi.vapi_client import VapiClient, VapiClientError
from app.repositories.home_repository import IHomeRepository
from app.services.voice_auth_service import VoiceAuthService

logger = logging.getLogger(__name__)


@dataclass
class VoiceEnableStatus:
    enabled: bool
    mapping: Optional[PhoneMapping] = None
    is_dry_run: bool = False


class VapiProvisioningService:
    def __init__(
        self,
        *,
        vapi_client: VapiClient,
        voice_auth_service: VoiceAuthService,
        default_assistant_id: Optional[str] = None,
        home_repository: Optional[IHomeRepository] = None,
    ):
        self._vapi = vapi_client
        self._va = voice_auth_service
        self._default_assistant_id = default_assistant_id
        self._homes = home_repository

    # ---- enable ------------------------------------------------------------

    def enable(
        self,
        *,
        user_ref: str,
        home_id: str,
        area_code: Optional[str] = None,
        label: Optional[str] = None,
        assistant_id: Optional[str] = None,
    ) -> PhoneMapping:
        """Provision a VAPI phone number for (user_ref, home_id) or return the existing one."""
        if not user_ref or not user_ref.strip():
            raise ValueError("user_ref is required")
        if not home_id or not home_id.strip():
            raise ValueError("home_id is required")

        if self._homes is not None and not self._homes.exists(home_id):
            raise ValueError(f"home '{home_id}' not found")

        # Idempotency: existing active mapping with a vapi_phone_number_id wins.
        existing = self._existing_for(user_ref, home_id)
        if existing:
            logger.info(
                f"VOICE_ENABLE idempotent hit user={user_ref} home={home_id} "
                f"mapping_id={existing.id} vapi_id={existing.vapi_phone_number_id}"
            )
            return existing

        aid = assistant_id or self._default_assistant_id

        # 1) Purchase a number on VAPI side
        purchased = self._vapi.buy_phone_number(
            assistant_id=aid,
            area_code=area_code,
            name=label or f"voice-auth-{user_ref}",
        )
        logger.info(
            f"VOICE_ENABLE purchased vapi_id={purchased.vapi_id} phone={purchased.phone_e164} "
            f"user={user_ref} home={home_id}"
        )

        # 2) Persist the mapping locally; on failure, release the VAPI resource.
        try:
            mapping = self._va.map_phone(
                phone=purchased.phone_e164,
                user_ref=user_ref,
                home_id=home_id,
                vapi_phone_number_id=purchased.vapi_id,
                label=label,
            )
        except Exception as persist_err:
            logger.error(
                f"VOICE_ENABLE persist failed user={user_ref} vapi_id={purchased.vapi_id}: {persist_err}",
                exc_info=True,
            )
            # Best-effort rollback on VAPI side. Don't mask the persist error.
            try:
                self._vapi.release_phone_number(purchased.vapi_id)
                logger.warning(
                    f"VOICE_ENABLE rolled back VAPI purchase vapi_id={purchased.vapi_id}"
                )
            except VapiClientError as rb_err:
                logger.error(
                    f"VOICE_ENABLE rollback FAILED — orphan VAPI resource vapi_id={purchased.vapi_id}: {rb_err}"
                )
            raise

        return mapping

    # ---- status ------------------------------------------------------------

    def status(self, user_ref: str) -> VoiceEnableStatus:
        if not user_ref or not user_ref.strip():
            raise ValueError("user_ref is required")
        for m in self._va.list_phones_for_user(user_ref):
            if m.is_active and m.vapi_phone_number_id:
                return VoiceEnableStatus(enabled=True, mapping=m, is_dry_run=not self._vapi.is_live)
        return VoiceEnableStatus(enabled=False, mapping=None, is_dry_run=not self._vapi.is_live)

    def list_for_user(self, user_ref: str) -> List[PhoneMapping]:
        return [
            m for m in self._va.list_phones_for_user(user_ref)
            if m.is_active and m.vapi_phone_number_id
        ]

    # ---- disable -----------------------------------------------------------

    def disable(self, user_ref: str) -> bool:
        """Release the VAPI number AND remove the local mapping. Returns True if anything was removed."""
        active = self.list_for_user(user_ref)
        if not active:
            return False

        any_removed = False
        for m in active:
            # Try VAPI release first; if VAPI says "gone", we still remove local row.
            try:
                self._vapi.release_phone_number(m.vapi_phone_number_id)
                logger.info(
                    f"VOICE_ENABLE released vapi_id={m.vapi_phone_number_id} user={user_ref}"
                )
            except VapiClientError as e:
                logger.error(
                    f"VOICE_ENABLE release FAILED vapi_id={m.vapi_phone_number_id} user={user_ref}: {e}. "
                    "Local mapping NOT removed — manual cleanup required."
                )
                continue
            if self._va.delete_phone(m.id):
                any_removed = True
        return any_removed

    # ---- internals ---------------------------------------------------------

    def _existing_for(self, user_ref: str, home_id: str) -> Optional[PhoneMapping]:
        for m in self._va.list_phones_for_user(user_ref):
            if m.is_active and m.home_id == home_id and m.vapi_phone_number_id:
                return m
        return None
