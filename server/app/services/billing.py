"""Paddle Billing webhooks. Paddle is the merchant of record, so it handles tax and
payouts (Payoneer / bank) for a seller based in Pakistan."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Optional

from ..config import settings

ACTIVE_STATUSES = {"active", "trialing", "past_due"}


def verify_signature(raw_body: bytes, header: Optional[str], secret: str, tolerance_s: int = 300) -> bool:
    """Paddle-Signature: ts=1671552777;h1=<hex hmac_sha256(secret, f'{ts}:{body}')>"""
    if not header or not secret:
        return False
    parts = dict(p.split("=", 1) for p in header.split(";") if "=" in p)
    ts, sigs = parts.get("ts"), [v for k, v in (p.split("=", 1) for p in header.split(";") if "=" in p) if k == "h1"]
    if not ts or not sigs:
        return False
    try:
        if abs(time.time() - int(ts)) > tolerance_s:
            return False
    except ValueError:
        return False
    expected = hmac.new(secret.encode(), f"{ts}:".encode() + raw_body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


def plan_for_price(price_id: Optional[str]) -> Optional[str]:
    if not price_id:
        return None
    if price_id == settings.paddle_price_business:
        return "business"
    if price_id == settings.paddle_price_team:
        return "team"
    return None


def plan_from_subscription(data: dict) -> tuple[str, Optional[str]]:
    """Return (plan, status) for a subscription.* webhook payload's `data`."""
    status = data.get("status")
    plan = None
    for item in data.get("items") or []:
        plan = plan_for_price((item.get("price") or {}).get("id")) or plan
    if status not in ACTIVE_STATUSES or plan is None:
        return "free", status
    return plan, status
