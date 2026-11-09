from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from ..config import PLANS, settings
from ..deps import OrgContext, admin_context, audit, check_origin, client_ip, org_context
from ..models import Component, Device, Event, Invite, Membership, Observation, User
from ..schemas import InviteIn, PolicyIn, RoleIn, SlackIn
from ..security import new_token, token_hash
from ..services import alerts, policy

router = APIRouter(prefix="/api/org", tags=["org"], dependencies=[Depends(check_origin)])


def _device_count(ctx: OrgContext) -> int:
    return ctx.db.scalar(select(func.count()).select_from(Device).where(
        Device.org_id == ctx.org.id, Device.revoked.is_(False))) or 0


def org_dict(ctx: OrgContext) -> dict:
    o = ctx.org
    plan = PLANS.get(o.plan, PLANS["free"])
    is_admin = ctx.role in ("admin", "owner")
    server = settings.public_url
    return {
        "id": o.id,
        "name": o.name,
        "role": ctx.role,
        "plan": o.plan,
        "plan_info": plan,
        "subscription_status": o.subscription_status,
        "policy_mode": o.policy_mode,
        "default_action": o.default_action,
        "alert_min_severity": o.alert_min_severity,
        "slack_configured": bool(o.slack_webhook_url),
        "device_count": _device_count(ctx),
        "enroll_token": o.enroll_token if is_admin else None,
        "enroll_command": f"mcpledger enroll {o.enroll_token} --server {server}" if is_admin else None,
        "server_url": server,
    }


@router.get("")
def get_org(ctx: OrgContext = Depends(org_context)):
    return org_dict(ctx)


@router.patch("/policy")
def update_policy(body: PolicyIn, request: Request, ctx: OrgContext = Depends(admin_context)):
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(ctx.org, k, v.strip() if isinstance(v, str) and k == "name" else v)
    audit(ctx.db, ctx.org.id, ctx.user.email, "policy.updated", "org", changes, client_ip(request))
    ctx.db.commit()
    return org_dict(ctx)


@router.put("/slack")
def set_slack(body: SlackIn, request: Request, ctx: OrgContext = Depends(admin_context)):
    url = (body.slack_webhook_url or "").strip() or None
    if url and not alerts.is_valid_webhook(url):
        raise HTTPException(400, "Use a Slack incoming-webhook URL (https://hooks.slack.com/...)")
    if url and not alerts.slack_allowed(ctx.org.plan):
        raise HTTPException(402, "Slack alerts are on the Team plan and above")
    ctx.org.slack_webhook_url = url
    audit(ctx.db, ctx.org.id, ctx.user.email, "slack.updated" if url else "slack.removed", "org", {}, client_ip(request))
    ctx.db.commit()
    return org_dict(ctx)


@router.post("/slack/test")
def test_slack(ctx: OrgContext = Depends(admin_context)):
    if not ctx.org.slack_webhook_url:
        raise HTTPException(400, "No Slack webhook configured")
    ok = alerts.send_slack(ctx.org.slack_webhook_url, {"text": f"MCPLedger test alert for {ctx.org.name}. Alerts are wired up."})
    if not ok:
        raise HTTPException(502, "Slack rejected the message. Check the webhook URL.")
    return {"ok": True}


@router.post("/enroll-token/rotate")
def rotate_token(request: Request, ctx: OrgContext = Depends(admin_context)):
    ctx.org.enroll_token = new_token("mle")
    audit(ctx.db, ctx.org.id, ctx.user.email, "enroll_token.rotated", "org", {}, client_ip(request))
    ctx.db.commit()
    return org_dict(ctx)


@router.get("/members")
def members(ctx: OrgContext = Depends(org_context)):
    ms = ctx.db.scalars(select(Membership).where(Membership.org_id == ctx.org.id).order_by(Membership.created_at)).all()
    invites = ctx.db.scalars(select(Invite).where(Invite.org_id == ctx.org.id, Invite.accepted_at.is_(None))
                             .order_by(Invite.created_at.desc())).all()
    return {
        "members": [{"user_id": m.user_id, "email": m.user.email, "name": m.user.name, "role": m.role,
                     "joined_at": m.created_at} for m in ms],
        "invites": [{"id": i.id, "email": i.email, "role": i.role, "created_at": i.created_at} for i in invites],
    }


@router.post("/invites")
def create_invite(body: InviteIn, request: Request, ctx: OrgContext = Depends(admin_context)):
    email = body.email.lower()
    exists = ctx.db.scalars(select(Membership).join(User).where(Membership.org_id == ctx.org.id,
                                                                func.lower(User.email) == email)).first()
    if exists:
        raise HTTPException(409, "Already a member")
    token = new_token("mli")
    inv = Invite(org_id=ctx.org.id, email=email, role=body.role, token_hash=token_hash(token), invited_by=ctx.user.email)
    ctx.db.add(inv)
    audit(ctx.db, ctx.org.id, ctx.user.email, "member.invited", email, {"role": body.role}, client_ip(request))
    ctx.db.commit()
    return {"id": inv.id, "email": email, "link": f"{settings.public_url}/invite/{token}"}


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: str, ctx: OrgContext = Depends(admin_context)):
    inv = ctx.db.get(Invite, invite_id)
    if not inv or inv.org_id != ctx.org.id:
        raise HTTPException(404, "Not found")
    ctx.db.delete(inv)
    audit(ctx.db, ctx.org.id, ctx.user.email, "invite.revoked", inv.email)
    ctx.db.commit()
    return {"ok": True}


@router.patch("/members/{user_id}")
def change_role(user_id: str, body: RoleIn, ctx: OrgContext = Depends(admin_context)):
    m = ctx.db.scalars(select(Membership).where(Membership.org_id == ctx.org.id, Membership.user_id == user_id)).first()
    if not m:
        raise HTTPException(404, "Not found")
    if (body.role == "owner" or m.role == "owner") and ctx.role != "owner":
        raise HTTPException(403, "Only owners can change ownership")
    if m.role == "owner" and body.role != "owner":
        owners = ctx.db.scalar(select(func.count()).select_from(Membership).where(
            Membership.org_id == ctx.org.id, Membership.role == "owner"))
        if owners <= 1:
            raise HTTPException(400, "An organization needs at least one owner")
    m.role = body.role
    audit(ctx.db, ctx.org.id, ctx.user.email, "member.role_changed", m.user.email, {"role": body.role})
    ctx.db.commit()
    return {"ok": True}


@router.delete("/members/{user_id}")
def remove_member(user_id: str, ctx: OrgContext = Depends(admin_context)):
    m = ctx.db.scalars(select(Membership).where(Membership.org_id == ctx.org.id, Membership.user_id == user_id)).first()
    if not m:
        raise HTTPException(404, "Not found")
    if m.role == "owner":
        raise HTTPException(400, "Transfer ownership before removing an owner")
    email = m.user.email
    ctx.db.delete(m)
    audit(ctx.db, ctx.org.id, ctx.user.email, "member.removed", email)
    ctx.db.commit()
    return {"ok": True}


@router.get("/overview")
def overview(ctx: OrgContext = Depends(org_context)):
    db, org = ctx.db, ctx.org
    comps = db.scalars(select(Component).where(Component.org_id == org.id)).all()
    obs = db.scalars(select(Observation).where(Observation.org_id == org.id)).all()
    current: dict[str, list[str]] = {}
    installs: Counter = Counter()
    for o in obs:
        current.setdefault(o.component_id, []).append(o.version_id)
        installs[o.component_id] += 1
    status_counts: Counter = Counter()
    risky = []
    for c in comps:
        st = policy.component_status(c, current.get(c.id, []))
        status_counts[st] += 1
        cur_ids = set(current.get(c.id, []))
        sev_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        worst = max((v.max_severity for v in c.versions if v.id in cur_ids and v.max_severity),
                    key=lambda s: sev_rank[s], default=None)
        if worst in ("high", "critical") and st != "blocked":
            risky.append({"id": c.id, "name": c.display_name, "kind": c.kind, "status": st, "max_severity": worst,
                          "installs": installs[c.id]})
    risky.sort(key=lambda r: ({"critical": 0, "high": 1}[r["max_severity"]], -r["installs"]))
    week = datetime.now(timezone.utc) - timedelta(days=7)
    devices = db.scalars(select(Device).where(Device.org_id == org.id, Device.revoked.is_(False))).all()
    stale = [d for d in devices if not d.last_seen_at or
             (d.last_seen_at if d.last_seen_at.tzinfo else d.last_seen_at.replace(tzinfo=timezone.utc)) < week]
    events = db.scalars(select(Event).where(Event.org_id == org.id).order_by(Event.created_at.desc()).limit(8)).all()
    open_alerts = db.scalar(select(func.count()).select_from(Event).where(
        Event.org_id == org.id, Event.acknowledged.is_(False), Event.severity.in_(["medium", "high", "critical"]))) or 0
    return {
        "components": len(comps),
        "mcp_servers": sum(1 for c in comps if c.kind == "mcp_server"),
        "skills": sum(1 for c in comps if c.kind == "skill"),
        "status_counts": {k: status_counts.get(k, 0) for k in ("pending", "approved", "drift", "blocked")},
        "devices": len(devices),
        "stale_devices": len(stale),
        "installs": len(obs),
        "open_alerts": open_alerts,
        "risky": risky[:6],
        "recent_events": [_event_dict(e) for e in events],
        "policy_mode": org.policy_mode,
    }


def _event_dict(e: Event) -> dict:
    return {"id": e.id, "type": e.type, "severity": e.severity, "title": e.title, "detail": e.detail,
            "component_id": e.component_id, "device_id": e.device_id, "acknowledged": e.acknowledged,
            "created_at": e.created_at}
