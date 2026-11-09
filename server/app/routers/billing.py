from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import PLANS, settings
from ..db import get_db
from ..deps import OrgContext, audit, org_context
from ..models import Org
from ..services.billing import plan_from_subscription, verify_signature

router = APIRouter(prefix="/api/billing", tags=["billing"])
log = logging.getLogger("mcpledger.billing")


@router.get("")
def billing_info(ctx: OrgContext = Depends(org_context)):
    return {
        "plan": ctx.org.plan,
        "subscription_status": ctx.org.subscription_status,
        "plans": PLANS,
        "paddle": {
            "enabled": bool(settings.paddle_client_token and settings.paddle_price_team),
            "environment": settings.paddle_env,
            "client_token": settings.paddle_client_token,
            "prices": {"team": settings.paddle_price_team, "business": settings.paddle_price_business},
        },
        "customer_email": ctx.user.email,
        "org_id": ctx.org.id,
    }


@router.post("/webhook")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("paddle-signature"), settings.paddle_webhook_secret):
        raise HTTPException(401, "Bad signature")
    payload = json.loads(raw)
    etype = payload.get("event_type", "")
    data = payload.get("data") or {}
    if not etype.startswith("subscription."):
        return {"ok": True, "ignored": etype}
    org_id = (data.get("custom_data") or {}).get("org_id")
    org = db.get(Org, org_id) if org_id else None
    if org is None and data.get("id"):
        org = db.scalars(select(Org).where(Org.paddle_subscription_id == data["id"])).first()
    if org is None:
        log.warning("paddle webhook for unknown org: %s", data.get("id"))
        return {"ok": True, "ignored": "unknown org"}
    plan, status = plan_from_subscription(data)
    old = org.plan
    org.plan = plan
    org.subscription_status = status
    org.paddle_subscription_id = data.get("id") or org.paddle_subscription_id
    org.paddle_customer_id = data.get("customer_id") or org.paddle_customer_id
    if plan == "free" and org.slack_webhook_url and not PLANS["free"]["slack"]:
        pass  # keep the URL so it comes back on upgrade; alerts.notify checks the plan
    audit(db, org.id, "billing:paddle", "billing.plan_changed", org.name, {"from": old, "to": plan, "status": status,
                                                                          "event": etype})
    db.commit()
    return {"ok": True}
