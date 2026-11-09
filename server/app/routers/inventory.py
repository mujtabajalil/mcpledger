from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select

from ..deps import OrgContext, admin_context, audit, check_origin, client_ip, org_context
from ..models import AuditLog, Component, ComponentVersion, Device, Event, Observation
from ..schemas import DecisionIn
from ..services import policy
from .org import _event_dict

router = APIRouter(prefix="/api", tags=["inventory"], dependencies=[Depends(check_origin)])
SEV_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _component_or_404(ctx: OrgContext, component_id: str) -> Component:
    c = ctx.db.get(Component, component_id)
    if not c or c.org_id != ctx.org.id:
        raise HTTPException(404, "Not found")
    return c


def _version_summary(v: ComponentVersion, approved: list[ComponentVersion]) -> dict:
    snap = v.snapshot or {}
    pkg = snap.get("package") or {}
    return {
        "id": v.id,
        "fingerprint": v.fingerprint,
        "launch_hash": v.launch_hash,
        "tools_hash": v.tools_hash,
        "version_label": pkg.get("version") or (v.fingerprint[:10]),
        "max_severity": v.max_severity,
        "findings": v.findings,
        "approved": v.approved,
        "trusted": policy.version_allowed(v, approved),
        "approved_by": v.approved_by,
        "approved_at": v.approved_at,
        "first_seen_at": v.first_seen_at,
        "snapshot": snap,
    }


@router.get("/components")
def list_components(
    ctx: OrgContext = Depends(org_context),
    status: Optional[str] = None,
    kind: Optional[str] = None,
    q: Optional[str] = None,
):
    db = ctx.db
    query = select(Component).where(Component.org_id == ctx.org.id)
    if kind in ("mcp_server", "skill"):
        query = query.where(Component.kind == kind)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(func.lower(Component.display_name).like(like) | func.lower(Component.identity_key).like(like))
    comps = db.scalars(query.order_by(Component.last_seen_at.desc())).all()
    obs = db.scalars(select(Observation).where(Observation.org_id == ctx.org.id)).all()
    by_comp: dict[str, list[Observation]] = defaultdict(list)
    for o in obs:
        by_comp[o.component_id].append(o)
    out = []
    for c in comps:
        cur = by_comp.get(c.id, [])
        st = policy.component_status(c, [o.version_id for o in cur])
        if status and st != status:
            continue
        cur_ids = {o.version_id for o in cur}
        worst = max((v.max_severity for v in c.versions if v.id in cur_ids and v.max_severity),
                    key=lambda s: SEV_RANK[s], default=None)
        latest = c.versions[-1] if c.versions else None
        out.append({
            "id": c.id,
            "kind": c.kind,
            "name": c.display_name,
            "identity": c.identity_key,
            "status": st,
            "max_severity": worst,
            "installs": len(cur),
            "devices": len({o.device_id for o in cur}),
            "clients": sorted({o.client for o in cur}),
            "local_names": sorted({o.local_name for o in cur})[:5],
            "versions": len(c.versions),
            "introspected": any(v.tools_hash for v in c.versions),
            "tool_count": len((latest.snapshot or {}).get("tools") or []) if latest else 0,
            "last_seen_at": c.last_seen_at,
            "first_seen_at": c.first_seen_at,
        })
    return out


@router.get("/components/{component_id}")
def get_component(component_id: str, ctx: OrgContext = Depends(org_context)):
    c = _component_or_404(ctx, component_id)
    obs = ctx.db.scalars(select(Observation).where(Observation.component_id == c.id)).all()
    approved = policy.approved_versions(c)
    versions = [_version_summary(v, approved) for v in reversed(c.versions)]
    installs = defaultdict(int)
    for o in obs:
        installs[o.version_id] += 1
    for v in versions:
        v["installs"] = installs.get(v["id"], 0)
    events = ctx.db.scalars(select(Event).where(Event.component_id == c.id).order_by(Event.created_at.desc()).limit(20)).all()
    return {
        "id": c.id,
        "kind": c.kind,
        "name": c.display_name,
        "identity": c.identity_key,
        "status": policy.component_status(c, [o.version_id for o in obs]),
        "blocked_reason": c.blocked_reason,
        "notes": c.notes,
        "first_seen_at": c.first_seen_at,
        "last_seen_at": c.last_seen_at,
        "versions": versions,
        "installs": [{
            "device_id": o.device_id,
            "hostname": o.device.hostname,
            "owner": o.device.owner_email or o.device.username,
            "client": o.client,
            "scope": o.scope,
            "location": o.location,
            "local_name": o.local_name,
            "version_id": o.version_id,
            "trusted": policy.version_allowed(o.version, approved) if not c.blocked else False,
            "last_seen_at": o.last_seen_at,
        } for o in obs],
        "events": [_event_dict(e) for e in events],
    }


@router.post("/components/{component_id}/approve")
def approve(component_id: str, body: DecisionIn, request: Request, ctx: OrgContext = Depends(admin_context)):
    c = _component_or_404(ctx, component_id)
    if not c.versions:
        raise HTTPException(400, "Nothing to approve")
    v = next((x for x in c.versions if x.id == body.version_id), None) if body.version_id else c.versions[-1]
    if v is None:
        raise HTTPException(404, "Version not found")
    v.approved = True
    v.approved_by = ctx.user.email
    v.approved_at = datetime.now(timezone.utc)
    c.blocked, c.blocked_reason = False, None
    if body.note:
        c.notes = body.note
    ctx.db.query(Event).filter(Event.component_id == c.id, Event.acknowledged.is_(False)).update({"acknowledged": True})
    audit(ctx.db, ctx.org.id, ctx.user.email, "component.approved", c.identity_key,
          {"version": v.fingerprint[:12], "note": body.note, "max_severity": v.max_severity}, client_ip(request))
    ctx.db.commit()
    return get_component(component_id, ctx)


@router.post("/components/{component_id}/revoke-version")
def revoke_version(component_id: str, body: DecisionIn, request: Request, ctx: OrgContext = Depends(admin_context)):
    c = _component_or_404(ctx, component_id)
    v = next((x for x in c.versions if x.id == body.version_id), None)
    if v is None:
        raise HTTPException(404, "Version not found")
    v.approved, v.approved_by, v.approved_at = False, None, None
    audit(ctx.db, ctx.org.id, ctx.user.email, "component.approval_revoked", c.identity_key,
          {"version": v.fingerprint[:12]}, client_ip(request))
    ctx.db.commit()
    return get_component(component_id, ctx)


@router.post("/components/{component_id}/block")
def block(component_id: str, body: DecisionIn, request: Request, ctx: OrgContext = Depends(admin_context)):
    c = _component_or_404(ctx, component_id)
    c.blocked = True
    c.blocked_reason = body.note
    ctx.db.query(Event).filter(Event.component_id == c.id, Event.acknowledged.is_(False)).update({"acknowledged": True})
    audit(ctx.db, ctx.org.id, ctx.user.email, "component.blocked", c.identity_key, {"note": body.note}, client_ip(request))
    ctx.db.commit()
    return get_component(component_id, ctx)


@router.post("/components/{component_id}/unblock")
def unblock(component_id: str, request: Request, ctx: OrgContext = Depends(admin_context)):
    c = _component_or_404(ctx, component_id)
    c.blocked, c.blocked_reason = False, None
    audit(ctx.db, ctx.org.id, ctx.user.email, "component.unblocked", c.identity_key, {}, client_ip(request))
    ctx.db.commit()
    return get_component(component_id, ctx)


# --------------------------------------------------------------------------- devices

@router.get("/devices")
def list_devices(ctx: OrgContext = Depends(org_context)):
    devices = ctx.db.scalars(select(Device).where(Device.org_id == ctx.org.id).order_by(Device.created_at.desc())).all()
    counts = dict(ctx.db.execute(select(Observation.device_id, func.count()).where(
        Observation.org_id == ctx.org.id).group_by(Observation.device_id)).all())
    return [{
        "id": d.id, "hostname": d.hostname, "os": d.os, "username": d.username, "owner_email": d.owner_email,
        "cli_version": d.cli_version, "revoked": d.revoked, "last_seen_at": d.last_seen_at, "created_at": d.created_at,
        "installs": counts.get(d.id, 0),
    } for d in devices]


@router.delete("/devices/{device_id}")
def revoke_device(device_id: str, request: Request, ctx: OrgContext = Depends(admin_context)):
    d = ctx.db.get(Device, device_id)
    if not d or d.org_id != ctx.org.id:
        raise HTTPException(404, "Not found")
    d.revoked = True
    ctx.db.query(Observation).filter(Observation.device_id == d.id).delete()
    audit(ctx.db, ctx.org.id, ctx.user.email, "device.revoked", d.hostname, {}, client_ip(request))
    ctx.db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- events

@router.get("/events")
def list_events(ctx: OrgContext = Depends(org_context), unacked: bool = False, limit: int = Query(100, le=500)):
    q = select(Event).where(Event.org_id == ctx.org.id)
    if unacked:
        q = q.where(Event.acknowledged.is_(False))
    events = ctx.db.scalars(q.order_by(Event.created_at.desc()).limit(limit)).all()
    hosts = {d.id: d.hostname for d in ctx.db.scalars(select(Device).where(Device.org_id == ctx.org.id))}
    return [dict(_event_dict(e), hostname=hosts.get(e.device_id)) for e in events]


@router.post("/events/{event_id}/ack")
def ack_event(event_id: str, ctx: OrgContext = Depends(org_context)):
    e = ctx.db.get(Event, event_id)
    if not e or e.org_id != ctx.org.id:
        raise HTTPException(404, "Not found")
    e.acknowledged = True
    ctx.db.commit()
    return {"ok": True}


@router.post("/events/ack-all")
def ack_all(ctx: OrgContext = Depends(org_context)):
    ctx.db.query(Event).filter(Event.org_id == ctx.org.id, Event.acknowledged.is_(False)).update({"acknowledged": True})
    audit(ctx.db, ctx.org.id, ctx.user.email, "alerts.acknowledged_all", "events")
    ctx.db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- audit

def _audit_rows(ctx: OrgContext, limit: int):
    return ctx.db.scalars(select(AuditLog).where(AuditLog.org_id == ctx.org.id)
                          .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)).all()


@router.get("/audit")
def list_audit(ctx: OrgContext = Depends(org_context), limit: int = Query(200, le=1000)):
    return [{"id": a.id, "actor": a.actor, "action": a.action, "target": a.target, "details": a.details,
             "ip": a.ip, "created_at": a.created_at} for a in _audit_rows(ctx, limit)]
