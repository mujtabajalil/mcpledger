"""Create a new license signing key pair (only if the old private key is lost or leaked).

    python scripts/license_keygen.py ~/secure/mcpledger-license-signing-key.pem

Then paste the printed public key into PUBLIC_KEY_B64 in app/licensing.py and release.
Every license issued with the old key stops working, so re-issue them.
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

out = Path(sys.argv[1] if len(sys.argv) > 1 else "mcpledger-license-signing-key.pem").expanduser()
if out.exists():
    sys.exit(f"{out} already exists; refusing to overwrite")
key = Ed25519PrivateKey.generate()
out.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
out.chmod(0o600)
pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
print(f"Private key written to {out}")
print(f"PUBLIC_KEY_B64 = \"{base64.b64encode(pub).decode()}\"")
