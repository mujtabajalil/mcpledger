"""Slack notifications for new events."""
from __future__ import annotations

import logging

import httpx

from ..config import settings

log = logging.getLogger("mcpledger.alerts")
SEV_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
EMOJI = {"critical": ":rotating_light:", "high": ":red_circle:", "medium": ":large_orange_circle:",
         "low": ":large_blue_circle:", "info": ":white_circle:"}


def is_valid_webhook(url: str) -> bool:
    return url.startswith("https://hooks.slack.com/") or url.startswith("https://hooks.slack-gov.com/")


def build_message(org_name: str, device: str, events: list[dict]) -> dict:
    lines = []
    for e in events[:15]:
        link = f"{settings.public_url}/inventory/{e['component_id']}" if e.get("component_id") else settings.public_url
        lines.append(f"{EMOJI.get(e['severity'], '')} *{e['title']}*\n{e['detail']} <{link}|Review>")
    more = f"\n…and {len(events) - 15} more" if len(events) > 15 else ""
    text = f"MCPLedger · {org_name} · {device}: {len(events)} new alert(s)"
    return {"text": text, "blocks": [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{text}*"}},
        *[{"type": "section", "text": {"type": "mrkdwn", "text": l[:2900]}} for l in lines],
        *([{"type": "context", "elements": [{"type": "mrkdwn", "text": more}]}] if more else []),
    ]}


def send_slack(webhook: str, payload: dict) -> bool:
    try:
        r = httpx.post(webhook, json=payload, timeout=10)
        if r.status_code >= 300:
            log.warning("slack webhook returned %s", r.status_code)
            return False
        return True
    except httpx.HTTPError as exc:
        log.warning("slack webhook failed: %s", exc)
        return False


def notify(webhook: str | None, allowed: bool, min_severity: str, org_name: str, device: str, events: list[dict]) -> None:
    if not webhook or not allowed:
        return
    picked = [e for e in events if SEV_RANK.get(e["severity"], 0) >= SEV_RANK.get(min_severity, 2)]
    if picked:
        send_slack(webhook, build_message(org_name, device, picked))
