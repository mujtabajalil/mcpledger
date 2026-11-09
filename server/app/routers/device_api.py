from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..editions import effective_plan
from ..db import get_db
from ..deps import audit, client_ip, current_device
from ..models import Device, Event, Org
from ..schemas import EnrollIn, ReportIn
from ..security import enroll_limiter, new_token, token_hash
from ..services import alerts
from ..services.ingest import ingest_report

router = APIRouter(prefix="/api/device", tags=["device"])


@router.post("/enroll")
def enroll(body: EnrollIn, request: Request, db: Session = Depends(get_db)):
    if not enroll_limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many enrollments from this address")
    org = db.scalars(select(Org).where(Org.enroll_token == body.enroll_token.strip())).first()
    if not org:
        raise HTTPException(401, "Invalid enrollment token. Copy it again from Settings > Enroll devices.")
    plan = effective_plan(org)
    limit = plan["max_devices"]
    count = db.scalar(select(func.count()).select_from(Device).where(Device.org_id == org.id, Device.revoked.is_(False)))
    if count >= limit:
        raise HTTPException(402, f"Your {plan['label']} plan allows {limit} devices. "
                                 "Upgrade or revoke an old device in the dashboard.")
    key = new_token("mld")
    dev = Device(org_id=org.id, hostname=body.hostname[:255], os=body.os, username=body.username,
                 owner_email=(body.owner_email or None), cli_version=body.cli_version, api_key_hash=token_hash(key))
    db.add(dev)
    db.flush()
    db.add(Event(org_id=org.id, type="device_enrolled", severity="info", title=f"Device enrolled: {dev.hostname}",
                 detail=f"{dev.owner_email or dev.username or 'unknown user'} · {dev.os}", device_id=dev.id))
    audit(db, org.id, f"device:{dev.hostname}", "device.enrolled", dev.hostname,
          {"owner": dev.owner_email, "os": dev.os}, client_ip(request))
    db.commit()
    return {"device_id": dev.id, "api_key": key, "org_name": org.name}


@router.post("/report")
async def report(request: Request, background: BackgroundTasks, device: Device = Depends(current_device),
                 db: Session = Depends(get_db)):
    from ..config import settings
    raw = await request.body()
    if len(raw) > settings.max_report_bytes:
        raise HTTPException(413, "Report too large; try --hashes-only")
    body = ReportIn.model_validate_json(raw)
    org = db.get(Org, device.org_id)
    if body.cli_version:
        device.cli_version = body.cli_version[:40]
    result, new_events = ingest_report(db, org, device, body)
    if new_events:
        background.add_task(alerts.notify, org.slack_webhook_url, effective_plan(org)["slack"], org.alert_min_severity, org.name,
                            device.hostname, new_events)
    return result
