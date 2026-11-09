"""Offline license keys for self-hosted installs.

A key is `<base64url(payload json)>.<base64url(ed25519 signature)>`, signed with the
MCPLedger signing key (kept off this repo; see scripts/issue_license.py). The public key
below verifies it, so no network call is needed and air-gapped installs work.

Removing this check is technically easy, as in any open-core product; using the
features in `server/ee/` without a valid key is a breach of the MCPLedger
Enterprise License (server/ee/LICENSE).
"""
from __future__ import annotations

import base64
import json
import threading
from dataclasses import dataclass
from datetime import date
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Public half of the MCPLedger license signing key. Replace only together with the
# private key (scripts/license_keygen.py prints a new pair).
PUBLIC_KEY_B64 = "AOMA7kIB6sevrYUVn/tjBnRpyI/cv7lbYF+6yvfmDR4="


class LicenseError(ValueError):
    pass


@dataclass(frozen=True)
class License:
    customer: str
    plan: str
    max_devices: int
    expires: date
    issued: Optional[date] = None
    license_id: str = ""

    @property
    def expired(self) -> bool:
        return date.today() > self.expires

    def as_dict(self) -> dict:
        return {"customer": self.customer, "plan": self.plan, "max_devices": self.max_devices,
                "expires": self.expires.isoformat(), "license_id": self.license_id, "expired": self.expired}


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def parse_license(key: str, public_key_b64: Optional[str] = None) -> License:
    key = (key or "").strip()
    if "." not in key:
        raise LicenseError("License key is malformed")
    body, sig = key.split(".", 1)
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64 or PUBLIC_KEY_B64))
        pub.verify(_b64d(sig), body.encode())
    except (InvalidSignature, ValueError) as exc:
        raise LicenseError("License key signature is not valid") from exc
    try:
        data = json.loads(_b64d(body))
        return License(
            customer=str(data["customer"]),
            plan=str(data.get("plan", "business")),
            max_devices=int(data.get("max_devices", 1_000_000)),
            expires=date.fromisoformat(data["expires"]),
            issued=date.fromisoformat(data["issued"]) if data.get("issued") else None,
            license_id=str(data.get("license_id", "")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise LicenseError("License key payload is not valid") from exc


_cache: dict[str, tuple[Optional[License], Optional[str]]] = {}
_lock = threading.Lock()


def current(key: str) -> tuple[Optional[License], Optional[str]]:
    """(license, error) for the configured key, cached per key string."""
    if not key:
        return None, None
    with _lock:
        if key not in _cache:
            try:
                _cache[key] = (parse_license(key), None)
            except LicenseError as exc:
                _cache[key] = (None, str(exc))
        return _cache[key]
