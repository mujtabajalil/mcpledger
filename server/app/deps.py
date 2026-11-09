from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import AuditLog, Device, Membership, Org, User, UserSession
from .security import token_hash

SESSION_COOKIE = "ml_session"
ROLE_RANK = {"member": 0, "admin": 1, "owner": 2}


def client_ip(request: Request) -> str:
    """The caller's IP as seen by our own proxy. Clients can prepend anything to
    X-Forwarded-For, so count from the right: Cloud Run's front end appends one hop,
    a load balancer in front adds another (TRUSTED_PROXY_HOPS=2)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        hops = max(1, int(os.environ.get("TRUSTED_PROXY_HOPS", "1")))
        if parts:
            return parts[-hops] if len(parts) >= hops else parts[0]
    return request.client.host if request.client else ""


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    sess = db.get(UserSession, token_hash(token))
    if not sess:
        raise HTTPException(401, "Session expired")
    exp = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        db.delete(sess)
        db.commit()
        raise HTTPException(401, "Session expired")
    user = db.get(User, sess.user_id)
    if not user:
        raise HTTPException(401, "Session expired")
    return user


@dataclass
class OrgContext:
    user: User
    org: Org
    role: str
    db: Session

    def require(self, role: str) -> None:
        if ROLE_RANK[self.role] < ROLE_RANK[role]:
            raise HTTPException(403, f"Requires {role} role")


def org_context(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    x_org_id: Optional[str] = Header(default=None),
) -> OrgContext:
    q = select(Membership).where(Membership.user_id == user.id)
    if x_org_id:
        q = q.where(Membership.org_id == x_org_id)
    m = db.scalars(q.order_by(Membership.created_at)).first()
    if not m:
        raise HTTPException(403, "No organization")
    return OrgContext(user=user, org=db.get(Org, m.org_id), role=m.role, db=db)


def admin_context(ctx: OrgContext = Depends(org_context)) -> OrgContext:
    ctx.require("admin")
    return ctx


def current_device(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)) -> Device:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing device key")
    key = authorization.split(" ", 1)[1].strip()
    dev = db.scalars(select(Device).where(Device.api_key_hash == token_hash(key))).first()
    if not dev or dev.revoked:
        raise HTTPException(401, "Unknown or revoked device key. Re-enroll with `mcpledger enroll`.")
    return dev


def check_origin(request: Request) -> None:
    """CSRF guard for cookie-authenticated writes: the Origin/Referer must be ours."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("origin") or ""
    if not origin:
        ref = request.headers.get("referer") or ""
        origin = "/".join(ref.split("/")[:3]) if ref else ""
    allowed = set(settings.allowed_origins) | {settings.public_url}
    if origin and origin.rstrip("/") not in allowed:
        raise HTTPException(403, "Cross-site request blocked")


def audit(db: Session, org_id: str, actor: str, action: str, target: str = "", details: Optional[dict] = None,
          ip: Optional[str] = None) -> None:
    db.add(AuditLog(org_id=org_id, actor=actor, action=action, target=target[:600], details=details or {}, ip=ip))
