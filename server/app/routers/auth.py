from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import SESSION_COOKIE, audit, check_origin, client_ip, current_user
from ..models import Invite, Membership, Org, User, UserSession
from ..schemas import LoginIn, SignupIn
from ..security import auth_limiter, hash_password, new_token, token_hash, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(check_origin)])


def _start_session(db: Session, response: Response, user: User) -> None:
    token = new_token("mls")
    db.add(UserSession(token_hash=token_hash(token), user_id=user.id,
                       expires_at=datetime.now(timezone.utc) + timedelta(days=settings.session_days)))
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.session_days * 86400, httponly=True,
                        secure=settings.secure_cookies, samesite="lax", path="/")


def _limit(request: Request) -> None:
    if not auth_limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")


def _accept_invite(db: Session, user: User, token: str) -> Org:
    inv = db.scalars(select(Invite).where(Invite.token_hash == token_hash(token))).first()
    if not inv or inv.accepted_at:
        raise HTTPException(400, "This invite link is invalid or already used")
    if inv.email.lower() != user.email.lower():
        raise HTTPException(400, f"This invite was sent to {inv.email}")
    exists = db.scalars(select(Membership).where(Membership.user_id == user.id, Membership.org_id == inv.org_id)).first()
    if not exists:
        db.add(Membership(user_id=user.id, org_id=inv.org_id, role=inv.role))
    inv.accepted_at = datetime.now(timezone.utc)
    audit(db, inv.org_id, user.email, "member.joined", user.email, {"role": inv.role})
    return db.get(Org, inv.org_id)


@router.post("/signup")
def signup(body: SignupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    _limit(request)
    email = body.email.lower()
    if not settings.signups_open and not body.invite_token:
        raise HTTPException(403, "Sign-ups are invite-only right now")
    if db.scalars(select(User).where(func.lower(User.email) == email)).first():
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    if body.invite_token:
        _accept_invite(db, user, body.invite_token)
    else:
        org = Org(name=(body.org_name or f"{email.split('@')[1].split('.')[0].title()} team").strip()[:200],
                  enroll_token=new_token("mle"))
        db.add(org)
        db.flush()
        db.add(Membership(user_id=user.id, org_id=org.id, role="owner"))
        audit(db, org.id, email, "org.created", org.name, ip=client_ip(request))
    _start_session(db, response, user)
    db.commit()
    return {"ok": True}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    _limit(request)
    user = db.scalars(select(User).where(func.lower(User.email) == body.email.lower())).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    _start_session(db, response, user)
    db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        sess = db.get(UserSession, token_hash(token))
        if sess:
            db.delete(sess)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ms = db.scalars(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)).all()
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "orgs": [{"id": m.org_id, "name": m.org.name, "role": m.role, "plan": m.org.plan} for m in ms],
    }


@router.get("/invite/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    inv = db.scalars(select(Invite).where(Invite.token_hash == token_hash(token))).first()
    if not inv or inv.accepted_at:
        raise HTTPException(404, "This invite link is invalid or already used")
    org = db.get(Org, inv.org_id)
    has_account = db.scalars(select(User).where(func.lower(User.email) == inv.email.lower())).first() is not None
    return {"email": inv.email, "org_name": org.name, "invited_by": inv.invited_by, "has_account": has_account}


@router.post("/invite/{token}/accept")
def invite_accept(token: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org = _accept_invite(db, user, token)
    db.commit()
    return {"ok": True, "org_id": org.id}
