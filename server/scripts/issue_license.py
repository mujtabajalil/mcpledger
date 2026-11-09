"""Issue a self-hosted Business license key (founder-only: needs the private signing key).

    python scripts/issue_license.py --key ~/secure/mcpledger-license-signing-key.pem \\
        --customer "Acme Inc" --devices 200 --expires 2027-12-31

The customer sets the printed key as MCPLEDGER_LICENSE_KEY and restarts the server.
Keep the .pem out of git and out of shared drives: anyone holding it can mint licenses.
"""
from __future__ import annotations

import argparse
import base64
import json
import uuid
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import serialization


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--key", required=True, help="path to the Ed25519 private key (.pem)")
    p.add_argument("--customer", required=True)
    p.add_argument("--devices", type=int, default=1_000_000)
    p.add_argument("--expires", required=True, help="YYYY-MM-DD")
    p.add_argument("--plan", default="business")
    a = p.parse_args()
    date.fromisoformat(a.expires)
    priv = serialization.load_pem_private_key(Path(a.key).expanduser().read_bytes(), password=None)
    payload = {"customer": a.customer, "plan": a.plan, "max_devices": a.devices, "expires": a.expires,
               "issued": date.today().isoformat(), "license_id": uuid.uuid4().hex[:12]}
    body = b64u(json.dumps(payload, separators=(",", ":")).encode())
    print(f"{body}.{b64u(priv.sign(body.encode()))}")


if __name__ == "__main__":
    main()
