"""Approval logic: which versions are trusted, component status, per-install verdicts."""
from __future__ import annotations

from typing import Iterable, Optional

from ..models import Component, ComponentVersion, Org


def approved_versions(component: Component) -> list[ComponentVersion]:
    return [v for v in component.versions if v.approved]


def version_allowed(v: ComponentVersion, approved: Iterable[ComponentVersion]) -> bool:
    """A version is trusted if it matches an approved one. When either side was not
    introspected (no tool hash), the launch spec alone decides."""
    for a in approved:
        if a.id == v.id:
            return True
        if a.launch_hash == v.launch_hash and (v.tools_hash is None or a.tools_hash is None or a.tools_hash == v.tools_hash):
            return True
    return False


def drift_kind(v: ComponentVersion, approved: Iterable[ComponentVersion]) -> str:
    """'tools' when the launch spec matches an approved version but tool definitions changed."""
    for a in approved:
        if a.launch_hash == v.launch_hash and a.tools_hash and v.tools_hash and a.tools_hash != v.tools_hash:
            return "tools"
    return "config" if v.component.kind == "mcp_server" else "content"


def component_status(component: Component, current_version_ids: Iterable[str]) -> str:
    if component.blocked:
        return "blocked"
    approved = approved_versions(component)
    if not approved:
        return "pending"
    by_id = {v.id: v for v in component.versions}
    for vid in set(current_version_ids):
        v = by_id.get(vid)
        if v is not None and not version_allowed(v, approved):
            return "drift"
    return "approved"


def verdict(org: Org, component: Component, version: ComponentVersion) -> tuple[str, str, str]:
    """Return (verdict, status, reason) for one installed copy."""
    if component.blocked:
        return "block", "blocked", f"Blocked by your team{': ' + component.blocked_reason if component.blocked_reason else ''}"
    approved = approved_versions(component)
    enforce = org.policy_mode == "enforce"
    if approved and version_allowed(version, approved):
        return "allow", "approved", "Approved"
    if approved:
        kind = drift_kind(version, approved)
        reason = {
            "tools": "Tool definitions changed since approval (possible rug pull)",
            "config": "Launch config or version differs from the approved one",
            "content": "Skill files differ from the approved version",
        }[kind]
        return ("block" if enforce else "warn"), "drift", reason
    action: Optional[str] = "block" if (enforce and org.default_action == "block") else "warn"
    return action, "pending", "Not reviewed yet"
