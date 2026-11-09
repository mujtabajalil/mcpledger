"""mcpledger command-line interface."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from . import __version__, discovery, rules
from . import fingerprint as fpmod
from .introspect import IntrospectError, introspect

DEFAULT_SERVER = "https://app.mcpledger.dev"
CONFIG_DIR = Path(os.environ.get("MCPLEDGER_HOME") or Path.home() / ".mcpledger")
CONFIG_FILE = CONFIG_DIR / "config.json"

EXIT_OK, EXIT_BLOCKED, EXIT_ERROR = 0, 1, 2


# --------------------------------------------------------------------------- output

def _color(code: str, text: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


SEV_COLOR = {"critical": "1;31", "high": "31", "medium": "33", "low": "36", "info": "2"}
VERDICT_COLOR = {"allow": "32", "warn": "33", "block": "1;31"}


def say(msg: str = "") -> None:
    print(msg)


def err(msg: str) -> None:
    print(_color("31", f"mcpledger: {msg}"), file=sys.stderr)


# --------------------------------------------------------------------------- config

def load_config() -> dict:
    cfg: dict = {}
    if CONFIG_FILE.is_file():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
        except ValueError:
            cfg = {}
    if os.environ.get("MCPLEDGER_SERVER"):
        cfg["server"] = os.environ["MCPLEDGER_SERVER"]
    if os.environ.get("MCPLEDGER_DEVICE_KEY"):
        cfg["device_key"] = os.environ["MCPLEDGER_DEVICE_KEY"]
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(CONFIG_FILE)


# --------------------------------------------------------------------------- api

class ApiError(Exception):
    pass


def api(server: str, path: str, body: dict, key: Optional[str] = None, timeout: float = 30) -> dict:
    url = server.rstrip("/") + path
    headers = {"Content-Type": "application/json", "User-Agent": f"mcpledger-cli/{__version__}"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("detail")
        except Exception:
            detail = None
        raise ApiError(f"{exc.code} {detail or exc.reason}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ApiError(f"cannot reach {server}: {exc}") from exc


# --------------------------------------------------------------------------- scanning

def collect(args) -> dict:
    projects = [Path(p).expanduser() for p in (args.project or [])] or [Path.cwd()]
    inv = discovery.discover(projects=projects, include_content=not args.hashes_only)
    if args.introspect:
        servers = [s for s in inv["mcp_servers"] if not s.get("disabled")]
        if servers and not args.quiet and not args.json:
            say(_color("2", f"Introspecting {len(servers)} MCP server(s) (starts each one, as your editor would)..."))
        for s in servers:
            try:
                s["tools"] = introspect(s, timeout=args.timeout)
            except IntrospectError as exc:
                s["introspect_error"] = str(exc)
    for s in inv["mcp_servers"]:
        s["findings"] = rules.scan_server(s)
        s["launch_hash"], s["tools_hash"], s["fingerprint"] = fpmod.server_hashes(s)
    for k in inv["skills"]:
        local = dict(k)
        local["files"] = [dict(f, content=f.get("content", f.get("_content"))) for f in k["files"]]
        k["findings"] = rules.scan_skill(local)
        k["launch_hash"], k["tools_hash"], k["fingerprint"] = fpmod.skill_hashes(k)
    return inv


def payload(inv: dict) -> dict:
    def clean(d: dict) -> dict:
        out = {k: v for k, v in d.items() if not k.startswith("_")}
        if "files" in out:
            out["files"] = [{k: v for k, v in f.items() if not k.startswith("_")} for f in out["files"]]
        return out

    return {
        "cli_version": __version__,
        "host": inv["host"],
        "mcp_servers": [clean(s) for s in inv["mcp_servers"]],
        "skills": [clean(s) for s in inv["skills"]],
    }


def print_local(inv: dict, verbose: bool) -> None:
    servers, skills = inv["mcp_servers"], inv["skills"]
    say(_color("1", f"MCP servers ({len(servers)})"))
    if not servers:
        say("  none found")
    for s in servers:
        _print_component(s["name"], f"{s['client']} · {s['scope']}", s, verbose,
                         extra=(f"{len(s['tools'])} tools" if s.get("tools") is not None else s.get("introspect_error")))
    say()
    say(_color("1", f"Agent skills ({len(skills)})"))
    if not skills:
        say("  none found")
    for k in skills:
        _print_component(k["name"], f"{k['client']} · {k['scope']}", k, verbose, extra=f"{len(k['files'])} files")
    total = [f for c in servers + skills for f in c["findings"]]
    worst = rules.max_severity(total)
    say()
    say(f"{len(total)} finding(s)" + (f", worst: {_color(SEV_COLOR[worst], worst)}" if worst else "."))


def _print_component(name, where, comp, verbose, extra=None, verdict=None, reason=None):
    sev = rules.max_severity(comp.get("findings") or [])
    tag = _color(SEV_COLOR[sev], f"[{sev}]") if sev else _color("32", "[clean]")
    v = f" {_color(VERDICT_COLOR[verdict], verdict.upper())}" if verdict else ""
    say(f"  {tag}{v} {_color('1', name)}  {_color('2', where)}" + (f"  {_color('2', extra)}" if extra else ""))
    if reason:
        say(f"      {reason}")
    show = comp.get("findings") or []
    if not verbose:
        show = [f for f in show if rules.SEV_RANK[f["severity"]] >= rules.SEV_RANK["medium"]]
    for f in show:
        say(f"      {_color(SEV_COLOR[f['severity']], f['rule'])} {f['title']}  {_color('2', f['location'])}")


def print_verdicts(inv: dict, res: dict, verbose: bool) -> None:
    by_key = {}
    for v in res.get("verdicts", []):
        by_key[(v["kind"], v["identity"], v.get("config_path") or v.get("path"))] = v
    say(_color("2", f"Org: {res.get('org', '?')} · policy: {res.get('policy_mode', '?')}"))
    say()
    for title, items, kind in (("MCP servers", inv["mcp_servers"], "mcp_server"), ("Agent skills", inv["skills"], "skill")):
        say(_color("1", f"{title} ({len(items)})"))
        if not items:
            say("  none found")
        for c in items:
            v = by_key.get((kind, c["identity"], c.get("config_path") or c.get("path"))) or {}
            _print_component(c["name"], f"{c['client']} · {c['scope']}", c, verbose,
                             verdict=v.get("verdict"), reason=v.get("reason") if v.get("verdict") != "allow" else None)
        say()
    counts = res.get("summary") or {}
    say(f"allow {counts.get('allow', 0)} · warn {counts.get('warn', 0)} · block {counts.get('block', 0)}")
    if res.get("dashboard_url"):
        say(_color("2", f"Review in the dashboard: {res['dashboard_url']}"))


# --------------------------------------------------------------------------- commands

def cmd_enroll(args) -> int:
    cfg = load_config()
    server = args.server or cfg.get("server") or DEFAULT_SERVER
    host = discovery.host_info()
    try:
        res = api(server, "/api/device/enroll", {
            "enroll_token": args.token,
            "hostname": host["hostname"],
            "os": host["os"],
            "username": host["username"],
            "owner_email": args.email,
            "cli_version": __version__,
        })
    except ApiError as exc:
        err(f"enrollment failed: {exc}")
        return EXIT_ERROR
    cfg.update({"server": server, "device_key": res["api_key"], "device_id": res["device_id"], "org": res.get("org_name")})
    save_config(cfg)
    say(_color("32", f"Enrolled {host['hostname']} in {res.get('org_name')}."))
    say(f"Config saved to {CONFIG_FILE}. Next: run `mcpledger scan`.")
    return EXIT_OK


def _report(args, inv) -> Optional[dict]:
    cfg = load_config()
    if not cfg.get("device_key"):
        return None
    return api(cfg.get("server") or DEFAULT_SERVER, "/api/device/report", payload(inv), key=cfg["device_key"], timeout=60)


def cmd_scan(args, enforce: bool = False) -> int:
    inv = collect(args)
    if args.local:
        res = None
    else:
        try:
            res = _report(args, inv)
        except ApiError as exc:
            err(f"could not report to server: {exc}")
            if enforce:
                return EXIT_ERROR if not args.fail_open else EXIT_OK
            res = None
    if args.json:
        out = {"inventory": payload(inv), "server": res}
        print(json.dumps(out, indent=2))
    elif not args.quiet:
        if res is None:
            if not args.local and not load_config().get("device_key"):
                say(_color("2", "Not enrolled: showing local results only. Run `mcpledger enroll <token>` to join your team."))
                say()
            print_local(inv, args.verbose)
        else:
            print_verdicts(inv, res, args.verbose)
    if enforce:
        if res is None:
            worst = rules.max_severity(f for c in inv["mcp_servers"] + inv["skills"] for f in c["findings"])
            threshold = args.fail_on
            if worst and rules.SEV_RANK[worst] >= rules.SEV_RANK[threshold]:
                return EXIT_BLOCKED
            return EXIT_OK
        verdicts = [v["verdict"] for v in res.get("verdicts", [])]
        if "block" in verdicts or (args.strict and "warn" in verdicts):
            return EXIT_BLOCKED
    return EXIT_OK


def cmd_check(args) -> int:
    return cmd_scan(args, enforce=True)


def cmd_fix(args) -> int:
    args.json, args.quiet = False, True
    inv = collect(args)
    try:
        res = _report(args, inv)
    except ApiError as exc:
        err(str(exc))
        return EXIT_ERROR
    if res is None:
        err("not enrolled; `fix` applies your team's blocklist, so enroll first")
        return EXIT_ERROR
    blocked = [v for v in res.get("verdicts", []) if v["verdict"] == "block"]
    if not blocked:
        say(_color("32", "Nothing blocked on this machine."))
        return EXIT_OK
    stamp = time.strftime("%Y%m%d-%H%M%S")
    qdir = CONFIG_DIR / "quarantine" / stamp
    for v in blocked:
        target = os.path.expanduser(v.get("config_path") or v.get("path") or "")
        label = f"{v['kind']} '{v['name']}' ({target})"
        if not args.yes:
            say(f"would remove {label}: {v.get('reason')}")
            continue
        if v["kind"] == "skill":
            qdir.mkdir(parents=True, exist_ok=True)
            dest = qdir / Path(target).name
            shutil.move(target, dest)
            say(f"quarantined {label} -> {dest}")
        elif target.endswith(".json"):
            if _remove_server_from_json(Path(target), v["name"], qdir):
                say(f"removed {label} (backup in {qdir})")
            else:
                say(f"could not edit {target}; remove '{v['name']}' by hand")
        else:
            say(f"remove '{v['name']}' from {target} by hand (only JSON configs are edited automatically)")
    if not args.yes:
        say("\nRe-run with --yes to apply.")
    return EXIT_OK


def _remove_server_from_json(path: Path, name: str, backup_dir: Path) -> bool:
    data = discovery.load_json(path)
    if data is None:
        return False
    changed = False
    containers = [data.get("mcpServers"), data.get("servers"), (data.get("mcp") or {}).get("servers")
                  if isinstance(data.get("mcp"), dict) else None, data.get("context_servers"), data.get("mcp.servers")]
    for proj in (data.get("projects") or {}).values() if isinstance(data.get("projects"), dict) else []:
        if isinstance(proj, dict):
            containers.append(proj.get("mcpServers"))
    for c in containers:
        if isinstance(c, dict) and name in c:
            del c[name]
            changed = True
    if not changed:
        return False
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / (path.name + ".bak"))
    path.write_text(json.dumps(data, indent=2) + "\n")
    return True


def cmd_status(args) -> int:
    cfg = load_config()
    if not cfg.get("device_key"):
        say("Not enrolled. Run `mcpledger enroll <token> --server <url>`.")
        return EXIT_OK
    say(f"Enrolled in {cfg.get('org', '?')} at {cfg.get('server')} (device {cfg.get('device_id', '?')}).")
    return EXIT_OK


def cmd_schedule(args) -> int:
    exe = shutil.which("mcpledger") or f"{sys.executable} -m mcpledger"
    if sys.platform == "darwin":
        plist = Path.home() / "Library" / "LaunchAgents" / "dev.mcpledger.scan.plist"
        prog = "".join(f"<string>{p}</string>" for p in exe.split() + ["scan", "--quiet"])
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>dev.mcpledger.scan</string>
<key>ProgramArguments</key><array>{prog}</array>
<key>StartInterval</key><integer>{args.every * 3600}</integer>
<key>RunAtLoad</key><true/>
<key>WorkingDirectory</key><string>{Path.home()}</string>
</dict></plist>
""")
        os.system(f"launchctl unload '{plist}' 2>/dev/null; launchctl load '{plist}'")
        say(f"Scheduled a scan every {args.every}h via launchd ({plist}).")
    elif os.name == "nt":
        say("Run this in PowerShell to scan on a schedule:")
        say(f'  schtasks /Create /SC HOURLY /MO {args.every} /TN MCPLedgerScan /TR "{exe} scan --quiet"')
    else:
        say("Add this line with `crontab -e`:")
        say(f"  0 */{args.every} * * * {exe} scan --quiet >/dev/null 2>&1")
    return EXIT_OK


# --------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mcpledger", description="Inventory and allowlist MCP servers and agent skills.")
    p.add_argument("--version", action="version", version=f"mcpledger {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def scan_opts(sp):
        sp.add_argument("--project", action="append", metavar="DIR",
                        help="project directory to include (repeatable; default: current directory)")
        sp.add_argument("--introspect", action="store_true",
                        help="start each MCP server and record its tool definitions (detects rug pulls)")
        sp.add_argument("--timeout", type=float, default=20, help="seconds per server when introspecting")
        sp.add_argument("--hashes-only", action="store_true", help="send file hashes but not skill file contents")
        sp.add_argument("--local", action="store_true", help="do not contact the server")
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        sp.add_argument("--quiet", action="store_true")
        sp.add_argument("-v", "--verbose", action="store_true", help="show low/info findings too")

    e = sub.add_parser("enroll", help="join this machine to your team")
    e.add_argument("token", help="enrollment token from the dashboard")
    e.add_argument("--server", help=f"MCPLedger server URL (default {DEFAULT_SERVER})")
    e.add_argument("--email", help="your work email, shown next to this device")
    e.set_defaults(func=cmd_enroll)

    s = sub.add_parser("scan", help="inventory this machine and report to your team")
    scan_opts(s)
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("check", help="like scan, but exits 1 if anything is blocked (for CI and git hooks)")
    scan_opts(c)
    c.add_argument("--strict", action="store_true", help="also fail on warnings (unapproved components)")
    c.add_argument("--fail-on", default="high", choices=rules.SEVERITIES,
                   help="when not enrolled, fail if a local finding is at least this severe")
    c.add_argument("--fail-open", action="store_true", help="exit 0 if the server is unreachable")
    c.set_defaults(func=cmd_check)

    f = sub.add_parser("fix", help="remove blocked servers from configs and quarantine blocked skills")
    scan_opts(f)
    f.add_argument("--yes", action="store_true", help="apply changes (default is a dry run)")
    f.set_defaults(func=cmd_fix)

    st = sub.add_parser("status", help="show enrollment")
    st.set_defaults(func=cmd_status)

    sc = sub.add_parser("schedule", help="scan automatically in the background")
    sc.add_argument("--every", type=int, default=6, help="hours between scans")
    sc.set_defaults(func=cmd_schedule)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
