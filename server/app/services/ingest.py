"""Turn a device report into components, versions, observations, events and verdicts."""
from __future__ import annotations

from datetime import datetime, timezone

from mcpledger import fingerprint as fp
from mcpledger import rules
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Component, ComponentVersion, Device, Event, Observation, Org
from ..schemas import ReportIn, ServerIn, SkillIn
from . import policy

SEV_RANK = rules.SEV_RANK


def _server_snapshot(s: ServerIn) -> dict:
    snap = {
        "name": s.name,
        "transport": s.transport or ("http" if s.url else "stdio"),
        "command": fp.tilde(s.command) if s.command else None,
        "args": list(s.args),
        "url": s.url,
        "env_keys": sorted(s.env_keys),
        "header_keys": sorted(s.header_keys),
        "inline_secret_keys": sorted(s.inline_secret_keys),
        "package": fp.package_of(s.command, list(s.args)),
        "tools": fp.normalize_tools([t.model_dump() for t in s.tools]) if s.tools is not None else None,
    }
    return snap


def _skill_snapshot(k: SkillIn) -> dict:
    return {
        "name": k.name,
        "description": k.description,
        "files": [f.model_dump(exclude_none=True) for f in sorted(k.files, key=lambda f: f.path)],
        "truncated": k.truncated,
    }


def _findings_for_skill(k: SkillIn, snap: dict) -> list[dict]:
    if any(f.get("content") is not None for f in snap["files"]):
        return rules.scan_skill(snap)
    # Hashes-only upload: trust the client's local scan (we cannot see the content).
    return rules.dedupe([f.model_dump(exclude_none=True) for f in k.findings])


def _severity_for_new(findings: list[dict]) -> str:
    worst = rules.max_severity(findings)
    return worst if worst and SEV_RANK[worst] >= SEV_RANK["low"] else "low"


def _kind_label(kind: str) -> str:
    return "MCP server" if kind == "mcp_server" else "skill"


def ingest_report(db: Session, org: Org, device: Device, report: ReportIn) -> tuple[dict, list[dict]]:
    now = datetime.now(timezone.utc)
    new_events: list[dict] = []
    verdicts: list[dict] = []
    seen_obs: set[str] = set()

    existing_obs = {(o.component_id, o.location): o for o in db.scalars(
        select(Observation).where(Observation.device_id == device.id))}
    comp_cache: dict[str, Component] = {}

    def get_component(kind: str, identity: str, name: str) -> Component:
        if identity in comp_cache:
            return comp_cache[identity]
        c = db.scalars(select(Component).where(Component.org_id == org.id, Component.identity_key == identity)).first()
        if c is None:
            c = Component(org_id=org.id, kind=kind, identity_key=identity, display_name=name, first_seen_at=now,
                          last_seen_at=now)
            c.versions = []
            db.add(c)
            db.flush()
            c._is_new = True  # type: ignore[attr-defined]
        comp_cache[identity] = c
        return c

    def event(type_: str, severity: str, title: str, detail: str, component: Component | None):
        e = Event(org_id=org.id, type=type_, severity=severity, title=title[:400], detail=detail,
                  component_id=component.id if component else None, device_id=device.id, created_at=now)
        db.add(e)
        new_events.append({"type": type_, "severity": severity, "title": e.title, "detail": detail,
                           "component_id": e.component_id})

    items: list[tuple[str, object]] = [("mcp_server", s) for s in report.mcp_servers] + \
                                      [("skill", k) for k in report.skills]
    for kind, item in items:
        if kind == "mcp_server":
            s: ServerIn = item  # type: ignore[assignment]
            snap = _server_snapshot(s)
            identity = fp.server_identity(snap)
            launch_hash, tools_hash, fprint = fp.server_hashes(snap)
            findings = rules.scan_server(snap)
            location = f"{s.config_path}{'#' + s.project if s.project else ''}::{s.name}"
            local_name, client, scope = s.name, s.client, s.scope
            cfg_path, skill_path = s.config_path, None
            display = (snap["package"] or {}).get("name") or s.url or s.name
        else:
            k: SkillIn = item  # type: ignore[assignment]
            snap = _skill_snapshot(k)
            identity = fp.skill_identity({"name": k.name})
            launch_hash, tools_hash, fprint = fp.skill_hashes(snap)
            findings = _findings_for_skill(k, snap)
            location = k.path or k.name
            local_name, client, scope = k.name, k.client, k.scope
            cfg_path, skill_path = None, k.path
            display = k.name

        comp = get_component(kind, identity, display)
        comp.last_seen_at = now
        is_new_comp = getattr(comp, "_is_new", False)

        version = next((v for v in comp.versions if v.fingerprint == fprint), None)
        is_new_version = version is None
        if version is None:
            version = ComponentVersion(component_id=comp.id, fingerprint=fprint, launch_hash=launch_hash,
                                       tools_hash=tools_hash, snapshot=snap, findings=findings,
                                       max_severity=rules.max_severity(findings), first_seen_at=now)
            comp.versions.append(version)
            db.flush()

        if is_new_comp and is_new_version and len(comp.versions) == 1:
            sev = _severity_for_new(findings)
            n = len([f for f in findings if SEV_RANK[f["severity"]] >= SEV_RANK["medium"]])
            detail = f"First seen on {device.hostname} ({client})."
            if n:
                detail += f" {n} medium+ finding(s): " + "; ".join(
                    f["title"] for f in findings if SEV_RANK[f["severity"]] >= SEV_RANK["medium"])[:300]
            event("new_component", sev, f"New {_kind_label(kind)}: {comp.display_name}", detail, comp)
        elif is_new_version and not comp.blocked:
            approved = policy.approved_versions(comp)
            if approved and not policy.version_allowed(version, approved):
                dk = policy.drift_kind(version, approved)
                if dk == "tools":
                    event("drift", "critical", f"Tool definitions changed: {comp.display_name}",
                          f"Same package/URL as the approved version, but the tools it advertises changed. "
                          f"Seen on {device.hostname}. Review the diff before re-approving.", comp)
                else:
                    event("drift", "high", f"Unapproved version: {comp.display_name}",
                          f"{'Config/version' if kind == 'mcp_server' else 'Files'} differ from the approved version "
                          f"on {device.hostname} ({client}).", comp)

        obs = existing_obs.get((comp.id, location))
        if obs is None:
            obs = Observation(org_id=org.id, device_id=device.id, component_id=comp.id, version_id=version.id,
                              client=client[:60], scope=scope[:30], location=location[:700], local_name=local_name,
                              first_seen_at=now, last_seen_at=now)
            db.add(obs)
            db.flush()
            existing_obs[(comp.id, location)] = obs
            if comp.blocked:
                event("blocked_in_use", "high", f"Blocked {_kind_label(kind)} installed: {comp.display_name}",
                      f"Found on {device.hostname} ({client}). Run `mcpledger fix --yes` on that machine.", comp)
        else:
            obs.version_id = version.id
            obs.last_seen_at = now
            obs.client, obs.scope, obs.local_name = client[:60], scope[:30], local_name
        seen_obs.add(obs.id)

        v, status, reason = policy.verdict(org, comp, version)
        verdicts.append({
            "kind": kind,
            "identity": identity,
            "name": local_name,
            "client": client,
            "config_path": cfg_path,
            "path": skill_path,
            "component_id": comp.id,
            "verdict": v,
            "status": status,
            "reason": reason,
            "max_severity": version.max_severity,
        })

    for obs in list(existing_obs.values()):
        if obs.id not in seen_obs:
            db.delete(obs)

    device.last_seen_at = now
    summary = {"allow": 0, "warn": 0, "block": 0}
    for v in verdicts:
        summary[v["verdict"]] += 1
    db.commit()
    return {
        "org": org.name,
        "policy_mode": org.policy_mode,
        "summary": summary,
        "verdicts": verdicts,
        "dashboard_url": f"{settings.public_url}/inventory",
    }, new_events
