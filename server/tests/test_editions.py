import base64
import json
from datetime import date, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import licensing
from app.config import settings

KEY = Ed25519PrivateKey.generate()
PUB = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def make_key(expires: date, devices: int = 50, signer=KEY) -> str:
    body = b64u(json.dumps({"customer": "Acme", "plan": "business", "max_devices": devices,
                            "expires": expires.isoformat()}).encode())
    return f"{body}.{b64u(signer.sign(body.encode()))}"


@pytest.fixture
def self_hosted(monkeypatch, owner):
    monkeypatch.setattr(settings, "deployment_mode", "self_hosted")
    monkeypatch.setattr(settings, "license_key", "")
    monkeypatch.setattr(licensing, "PUBLIC_KEY_B64", PUB)
    licensing._cache.clear()
    yield owner
    licensing._cache.clear()


def set_license(monkeypatch, key):
    monkeypatch.setattr(settings, "license_key", key)
    licensing._cache.clear()


def test_license_parsing():
    good = make_key(date.today() + timedelta(days=30))
    lic = licensing.parse_license(good, PUB)
    assert lic.customer == "Acme" and lic.max_devices == 50 and not lic.expired
    body, sig = good.split(".")
    tampered = b64u(json.dumps({"customer": "Acme", "plan": "business", "max_devices": 99999,
                                "expires": "2099-01-01"}).encode()) + "." + sig
    with pytest.raises(licensing.LicenseError):
        licensing.parse_license(tampered, PUB)
    with pytest.raises(licensing.LicenseError):
        licensing.parse_license(make_key(date.today(), signer=Ed25519PrivateKey.generate()), PUB)
    with pytest.raises(licensing.LicenseError):
        licensing.parse_license("garbage", PUB)


def test_community_edition_is_unlimited_and_has_slack(self_hosted):
    c = self_hosted
    org = c.get("/api/org").json()
    assert org["edition"] == {"mode": "self_hosted", "license_status": "none", "license": None, "license_error": None}
    assert org["plan_info"]["label"] == "Community"
    tok = org["enroll_token"]
    for i in range(6):  # more than cloud Free's 3
        assert c.post("/api/device/enroll", json={"enroll_token": tok, "hostname": f"d{i}"}).status_code == 200
    assert c.put("/api/org/slack", json={"slack_webhook_url": "https://hooks.slack.com/services/x"}).status_code == 200
    r = c.get("/api/audit/export.csv")
    assert r.status_code == 402 and "license key" in r.json()["detail"]
    assert c.get("/api/billing").json()["paddle"]["enabled"] is False


def test_business_license_unlocks_ee_and_caps_devices(self_hosted, monkeypatch):
    c = self_hosted
    set_license(monkeypatch, make_key(date.today() + timedelta(days=365), devices=2))
    org = c.get("/api/org").json()
    assert org["edition"]["license_status"] == "active" and org["plan_info"]["audit_export"] is True
    r = c.get("/api/audit/export.csv")
    assert r.status_code == 200 and r.text.startswith("timestamp_utc,actor")
    tok = org["enroll_token"]
    assert c.post("/api/device/enroll", json={"enroll_token": tok, "hostname": "a"}).status_code == 200
    assert c.post("/api/device/enroll", json={"enroll_token": tok, "hostname": "b"}).status_code == 200
    assert c.post("/api/device/enroll", json={"enroll_token": tok, "hostname": "c"}).status_code == 402


def test_expired_or_forged_license_falls_back_to_community(self_hosted, monkeypatch):
    c = self_hosted
    set_license(monkeypatch, make_key(date.today() - timedelta(days=1)))
    org = c.get("/api/org").json()
    assert org["edition"]["license_status"] == "expired" and org["plan_info"]["label"] == "Community"
    set_license(monkeypatch, make_key(date.today() + timedelta(days=9), signer=Ed25519PrivateKey.generate()))
    org = c.get("/api/org").json()
    assert org["edition"]["license_status"] == "invalid"
    assert c.get("/api/audit/export.csv").status_code == 402
