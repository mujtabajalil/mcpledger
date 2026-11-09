# Copyright (c) MCPLedger. Licensed under the MCPLedger Enterprise License (see server/ee/LICENSE).
"""Audit-log export for compliance evidence (SOC 2, ISO 27001, customer questionnaires)."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import OrgContext, admin_context, audit, check_origin, client_ip
from app.editions import require
from app.models import AuditLog
from fastapi import Request

router = APIRouter(prefix="/api", tags=["enterprise"], dependencies=[Depends(check_origin)])


@router.get("/audit/export.csv")
def export_audit(request: Request, ctx: OrgContext = Depends(admin_context)):
    require(ctx.org, "audit_export", "Audit export")
    rows = ctx.db.scalars(select(AuditLog).where(AuditLog.org_id == ctx.org.id)
                          .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp_utc", "actor", "action", "target", "details", "ip"])
    for a in rows:
        w.writerow([a.created_at.isoformat(), a.actor, a.action, a.target, json.dumps(a.details), a.ip or ""])
    audit(ctx.db, ctx.org.id, ctx.user.email, "audit.exported", "audit_log", {"rows": len(rows)}, client_ip(request))
    ctx.db.commit()
    name = f"mcpledger-audit-{datetime.now(timezone.utc):%Y%m%d}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
