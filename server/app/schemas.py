from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ----------------------------------------------------------------------- device API

class EnrollIn(_Lenient):
    enroll_token: str = Field(max_length=200)
    hostname: str = Field(max_length=255)
    os: str = Field(default="", max_length=120)
    username: str = Field(default="", max_length=120)
    owner_email: Optional[str] = Field(default=None, max_length=320)
    cli_version: str = Field(default="", max_length=40)


class ToolIn(_Lenient):
    name: str = Field(max_length=300)
    description: Optional[str] = Field(default="", max_length=20000)
    inputSchema: Optional[dict[str, Any]] = None
    annotations: Optional[dict[str, Any]] = None


class ServerIn(_Lenient):
    name: str = Field(max_length=255)
    client: str = Field(default="unknown", max_length=60)
    scope: str = Field(default="user", max_length=30)
    config_path: str = Field(default="", max_length=600)
    project: Optional[str] = Field(default=None, max_length=600)
    transport: Optional[str] = Field(default="stdio", max_length=20)
    command: Optional[str] = Field(default=None, max_length=1000)
    args: list[str] = Field(default_factory=list, max_length=200)
    url: Optional[str] = Field(default=None, max_length=2000)
    env_keys: list[str] = Field(default_factory=list, max_length=200)
    header_keys: list[str] = Field(default_factory=list, max_length=100)
    inline_secret_keys: list[str] = Field(default_factory=list, max_length=100)
    disabled: bool = False
    tools: Optional[list[ToolIn]] = Field(default=None, max_length=500)
    introspect_error: Optional[str] = Field(default=None, max_length=500)


class SkillFileIn(_Lenient):
    path: str = Field(max_length=500)
    sha256: str = Field(min_length=64, max_length=64)
    size: int = 0
    content: Optional[str] = Field(default=None, max_length=70000)


class FindingIn(_Lenient):
    rule: str = Field(max_length=20)
    severity: Literal["info", "low", "medium", "high", "critical"]
    title: str = Field(max_length=200)
    detail: str = Field(default="", max_length=1000)
    location: str = Field(default="", max_length=300)
    evidence: Optional[str] = Field(default=None, max_length=200)


class SkillIn(_Lenient):
    name: str = Field(max_length=255)
    description: str = Field(default="", max_length=4000)
    client: str = Field(default="unknown", max_length=60)
    scope: str = Field(default="user", max_length=30)
    path: str = Field(default="", max_length=600)
    files: list[SkillFileIn] = Field(default_factory=list, max_length=100)
    truncated: bool = False
    findings: list[FindingIn] = Field(default_factory=list, max_length=200)


class ReportIn(_Lenient):
    cli_version: str = Field(default="", max_length=40)
    host: dict[str, Any] = Field(default_factory=dict)
    mcp_servers: list[ServerIn] = Field(default_factory=list, max_length=500)
    skills: list[SkillIn] = Field(default_factory=list, max_length=500)


# ----------------------------------------------------------------------- dashboard API

class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    name: str = Field(default="", max_length=200)
    org_name: Optional[str] = Field(default=None, max_length=200)
    invite_token: Optional[str] = Field(default=None, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class PolicyIn(BaseModel):
    policy_mode: Optional[Literal["monitor", "enforce"]] = None
    default_action: Optional[Literal["warn", "block"]] = None
    alert_min_severity: Optional[Literal["info", "low", "medium", "high", "critical"]] = None
    name: Optional[str] = Field(default=None, max_length=200)


class SlackIn(BaseModel):
    slack_webhook_url: Optional[str] = Field(default=None, max_length=500)


class InviteIn(BaseModel):
    email: EmailStr
    role: Literal["member", "admin"] = "member"


class RoleIn(BaseModel):
    role: Literal["member", "admin", "owner"]


class DecisionIn(BaseModel):
    version_id: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=1000)
