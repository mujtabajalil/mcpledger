"""Which features an organization gets.

cloud        - the hosted service at app.mcpledger.dev: Free / Team / Business, billed by Paddle.
self_hosted  - anyone running the open-source server: the Community edition is free with no
               device limit; a license key unlocks the Business features in server/ee/.
"""
from __future__ import annotations

from typing import Any

from . import licensing
from .config import PLANS, settings
from .models import Org

COMMUNITY = {"label": "Community", "price": 0, "max_devices": 1_000_000, "slack": True, "audit_export": False,
             "history_days": 365}


def is_cloud() -> bool:
    return settings.deployment_mode == "cloud"


def effective_plan(org: Org) -> dict[str, Any]:
    if is_cloud():
        return PLANS.get(org.plan, PLANS["free"])
    lic, _ = licensing.current(settings.license_key)
    if lic and not lic.expired:
        plan = dict(PLANS["business"])
        plan.update(label="Business (self-hosted)", price=None, max_devices=lic.max_devices)
        return plan
    return COMMUNITY


def edition_info() -> dict[str, Any]:
    if is_cloud():
        return {"mode": "cloud"}
    lic, err = licensing.current(settings.license_key)
    status = "none"
    if err:
        status = "invalid"
    elif lic:
        status = "expired" if lic.expired else "active"
    return {"mode": "self_hosted", "license_status": status, "license": lic.as_dict() if lic else None,
            "license_error": err}


def require(org: Org, feature: str, what: str) -> None:
    from fastapi import HTTPException
    if not effective_plan(org).get(feature):
        if is_cloud():
            raise HTTPException(402, f"{what} is on the Business plan")
        raise HTTPException(402, f"{what} needs an MCPLedger Business license key (MCPLEDGER_LICENSE_KEY)")
