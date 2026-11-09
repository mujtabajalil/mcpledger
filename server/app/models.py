from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Org(Base):
    __tablename__ = "orgs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(20), default="free")
    policy_mode: Mapped[str] = mapped_column(String(20), default="monitor")  # monitor | enforce
    default_action: Mapped[str] = mapped_column(String(20), default="warn")  # warn | block (unapproved, enforce mode)
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alert_min_severity: Mapped[str] = mapped_column(String(20), default="medium")
    # Join token shown to admins so they can onboard developers. Rotating it does not
    # affect already-enrolled devices (each device has its own key).
    enroll_token: Mapped[str] = mapped_column(String(80), unique=True)
    paddle_customer_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    paddle_subscription_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    subscription_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="member")  # owner | admin | member
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship(back_populates="memberships")
    org: Mapped[Org] = relationship()


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20), default="member")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    hostname: Mapped[str] = mapped_column(String(255))
    os: Mapped[str] = mapped_column(String(120), default="")
    username: Mapped[str] = mapped_column(String(120), default="")
    owner_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    cli_version: Mapped[str] = mapped_column(String(40), default="")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Component(Base):
    """A distinct MCP server or skill, identified across machines and versions."""
    __tablename__ = "components"
    __table_args__ = (UniqueConstraint("org_id", "identity_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # mcp_server | skill
    identity_key: Mapped[str] = mapped_column(String(600))
    display_name: Mapped[str] = mapped_column(String(255))
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    versions: Mapped[list["ComponentVersion"]] = relationship(back_populates="component", cascade="all, delete-orphan",
                                                              order_by="ComponentVersion.first_seen_at")


class ComponentVersion(Base):
    """One exact fingerprint of a component. Approval pins a version."""
    __tablename__ = "component_versions"
    __table_args__ = (UniqueConstraint("component_id", "fingerprint"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    component_id: Mapped[str] = mapped_column(ForeignKey("components.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    launch_hash: Mapped[str] = mapped_column(String(64))
    tools_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSONType)
    findings: Mapped[list] = mapped_column(JSONType, default=list)
    max_severity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    component: Mapped[Component] = relationship(back_populates="versions")


class Observation(Base):
    """Where a component is currently installed: device + client + config file."""
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("device_id", "component_id", "location"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    component_id: Mapped[str] = mapped_column(ForeignKey("components.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("component_versions.id", ondelete="CASCADE"), index=True)
    client: Mapped[str] = mapped_column(String(60))
    scope: Mapped[str] = mapped_column(String(30))
    location: Mapped[str] = mapped_column(String(700))  # config path (+ project) or skill dir
    local_name: Mapped[str] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    device: Mapped[Device] = relationship()
    version: Mapped[ComponentVersion] = relationship()


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_org_created", "org_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10), default="info")
    title: Mapped[str] = mapped_column(String(400))
    detail: Mapped[str] = mapped_column(Text, default="")
    component_id: Mapped[Optional[str]] = mapped_column(ForeignKey("components.id", ondelete="CASCADE"), nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_org_created", "org_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    actor: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(600), default="")
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
