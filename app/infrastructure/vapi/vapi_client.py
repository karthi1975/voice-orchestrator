"""Thin HTTP client for the VAPI cloud REST API.

This is the only place we talk to api.vapi.ai over HTTP. The provisioning
service (app/services/vapi_provisioning_service.py) calls into this client
and is responsible for transactional integrity with our own DB.

Two modes:

  - LIVE (default when VAPI_API_KEY is set): real HTTPS calls to api.vapi.ai.
  - DRY-RUN (VAPI_DRY_RUN=1 or VAPI_API_KEY missing): synthesizes a fake
    `vapi_phone_number_id` and a 555 area-code phone number; useful for local
    development and CI where real billing is undesirable.

NOTE on the API surface: VAPI's HTTP API is documented at https://docs.vapi.ai.
The endpoint paths and request/response shapes used here reflect the v1 spec
at the time of writing. If VAPI changes their API, update _BUY_PATH /
_DELETE_PATH / response parsing here.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


_BASE_URL = os.environ.get("VAPI_API_BASE_URL", "https://api.vapi.ai").rstrip("/")
_BUY_PATH = "/phone-number"            # POST: create a new phone number resource
_DELETE_PATH = "/phone-number/{id}"    # DELETE: release a phone number
_GET_PATH = "/phone-number/{id}"       # GET:    fetch a phone number resource


@dataclass(frozen=True)
class VapiPhoneNumber:
    """A phone number resource as returned by VAPI."""
    vapi_id: str
    phone_e164: str
    assistant_id: Optional[str]
    raw: dict  # full body from VAPI for audit / future-proofing


class VapiClientError(RuntimeError):
    """Raised when VAPI returns a non-2xx response."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class VapiClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = _BASE_URL,
        dry_run: Optional[bool] = None,
        timeout_seconds: float = 15.0,
    ):
        self._api_key = api_key or os.environ.get("VAPI_API_KEY", "").strip() or None
        self._base_url = base_url
        self._timeout = timeout_seconds
        # Dry-run if explicitly requested OR if no API key is configured.
        if dry_run is None:
            dry_run = os.environ.get("VAPI_DRY_RUN", "").strip() in ("1", "true", "TRUE", "yes")
        self._dry_run = bool(dry_run) or self._api_key is None

        if self._dry_run:
            logger.warning(
                "VapiClient running in DRY-RUN mode (no real VAPI calls; phone numbers are synthesized). "
                "Set VAPI_API_KEY and unset VAPI_DRY_RUN to enable live provisioning."
            )

    @property
    def is_live(self) -> bool:
        return not self._dry_run

    # ---- public API --------------------------------------------------------

    def buy_phone_number(
        self,
        *,
        assistant_id: Optional[str],
        area_code: Optional[str] = None,
        name: Optional[str] = None,
    ) -> VapiPhoneNumber:
        """Create (purchase) a new VAPI-managed phone number and attach it to assistant_id.

        VAPI's request body keys vary by provider (Vapi-managed vs Twilio BYO).
        This call uses the Vapi-managed flow. To use BYO Twilio, supply the
        twilio creds via separate env wiring and adjust the body here.
        """
        if self._dry_run:
            return self._fake_phone_number(assistant_id=assistant_id, area_code=area_code, name=name)

        body = {
            "provider": "vapi",
            "assistantId": assistant_id,
            "name": name or "voice-auth-line",
        }
        if area_code:
            body["numberDesiredAreaCode"] = area_code

        resp = self._post(_BUY_PATH, json=body)
        return self._parse_phone_number(resp)

    def get_phone_number(self, vapi_id: str) -> Optional[VapiPhoneNumber]:
        if self._dry_run:
            # In dry-run we can't recover state — return None to signal "not found"
            return None
        resp = self._get(_GET_PATH.format(id=vapi_id))
        if resp is None:
            return None
        return self._parse_phone_number(resp)

    def release_phone_number(self, vapi_id: str) -> bool:
        """Delete the VAPI phone-number resource. Returns True on success."""
        if self._dry_run:
            logger.info(f"VapiClient[dry-run] release_phone_number id={vapi_id}")
            return True
        url = self._url(_DELETE_PATH.format(id=vapi_id))
        try:
            r = requests.delete(url, headers=self._headers(), timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            raise VapiClientError(f"VAPI DELETE network error: {e}") from e
        if r.status_code in (200, 204):
            return True
        if r.status_code == 404:
            return False
        raise VapiClientError(
            f"VAPI DELETE phone-number/{vapi_id} returned {r.status_code}",
            status_code=r.status_code,
            body=r.text[:500],
        )

    # ---- internals ---------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path if path.startswith('/') else '/' + path}"

    def _post(self, path: str, *, json: dict) -> dict:
        url = self._url(path)
        try:
            r = requests.post(url, json=json, headers=self._headers(), timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            raise VapiClientError(f"VAPI POST network error: {e}") from e
        if not (200 <= r.status_code < 300):
            raise VapiClientError(
                f"VAPI POST {path} returned {r.status_code}",
                status_code=r.status_code,
                body=r.text[:500],
            )
        try:
            return r.json()
        except ValueError as e:
            raise VapiClientError(f"VAPI POST {path}: non-JSON response: {e}") from e

    def _get(self, path: str) -> Optional[dict]:
        url = self._url(path)
        try:
            r = requests.get(url, headers=self._headers(), timeout=self._timeout)
        except requests.exceptions.RequestException as e:
            raise VapiClientError(f"VAPI GET network error: {e}") from e
        if r.status_code == 404:
            return None
        if not (200 <= r.status_code < 300):
            raise VapiClientError(
                f"VAPI GET {path} returned {r.status_code}",
                status_code=r.status_code,
                body=r.text[:500],
            )
        try:
            return r.json()
        except ValueError as e:
            raise VapiClientError(f"VAPI GET {path}: non-JSON response: {e}") from e

    @staticmethod
    def _parse_phone_number(body: dict) -> VapiPhoneNumber:
        # VAPI returns the resource id as 'id' and the e164 number as 'number'.
        # If their schema diverges, change the keys here in one place.
        vid = body.get("id") or body.get("phoneNumberId")
        number = body.get("number") or body.get("phoneNumber") or body.get("e164")
        if not vid or not number:
            raise VapiClientError(
                f"VAPI response missing id/number; got keys={list(body.keys())}"
            )
        return VapiPhoneNumber(
            vapi_id=str(vid),
            phone_e164=str(number),
            assistant_id=body.get("assistantId"),
            raw=body,
        )

    @staticmethod
    def _fake_phone_number(
        *, assistant_id: Optional[str], area_code: Optional[str], name: Optional[str]
    ) -> VapiPhoneNumber:
        # Use 555-prefixed numbers to make it obvious in logs/UI that this is a stub.
        ac = (area_code or "555")[:3].rjust(3, "5")
        rest = f"{secrets.randbelow(900) + 100:03d}{int(time.time()) % 10000:04d}"
        e164 = f"+1{ac}{rest}"
        fake_id = f"vpn_dryrun_{secrets.token_hex(6)}"
        return VapiPhoneNumber(
            vapi_id=fake_id,
            phone_e164=e164,
            assistant_id=assistant_id,
            raw={"_dry_run": True, "name": name},
        )
