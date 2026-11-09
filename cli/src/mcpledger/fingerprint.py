"""Identity and fingerprint helpers shared by the CLI and the server.

Identity answers "is this the same component?" (stable across versions).
Fingerprints answer "is this exactly what we approved?" (changes on any edit).

An MCP server has two hashes:
  launch_hash - how it is started (command, args incl. version, url, env/header *names*)
  tools_hash  - the tool definitions it advertises (names, descriptions, schemas),
                only known when the server was introspected.
A skill has one content hash over every file (path + sha256).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

NODE_RUNNERS = {"npx", "bunx", "pnpx"}
PY_RUNNERS = {"uvx", "pipx"}
_HOME = str(Path.home())


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tilde(value: Optional[str], home: Optional[str] = None) -> Optional[str]:
    """Replace the user's home directory with ~ so paths compare across machines."""
    if value is None:
        return None
    home = home if home is not None else _HOME
    if home and home != "/":
        value = value.replace(home, "~")
    return value


def _base(cmd: str) -> str:
    name = os.path.basename(cmd.replace("\\", "/")).lower()
    for ext in (".cmd", ".exe", ".bat"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    return name


def split_npm_spec(spec: str) -> tuple[str, Optional[str]]:
    """'@scope/pkg@1.2.3' -> ('@scope/pkg', '1.2.3'); 'pkg' -> ('pkg', None)."""
    if spec.startswith("@"):
        at = spec.find("@", 1)
    else:
        at = spec.find("@")
    if at > 0:
        return spec[:at], spec[at + 1 :] or None
    return spec, None


def split_py_spec(spec: str) -> tuple[str, Optional[str]]:
    m = re.match(r"^([A-Za-z0-9_.\-\[\],]+?)\s*(?:==|@|>=|~=)\s*(.+)$", spec)
    if m:
        return m.group(1), m.group(2)
    return spec, None


_DOCKER_VALUE_FLAGS = {
    "-e", "--env", "-v", "--volume", "--name", "-p", "--publish", "--network", "--net",
    "-w", "--workdir", "-u", "--user", "--env-file", "--mount", "--entrypoint", "--label",
    "-l", "--platform", "--add-host", "--cap-add", "--cap-drop", "--memory", "-m", "--cpus",
}


def package_of(command: Optional[str], args: list[str]) -> Optional[dict]:
    """Best-effort detection of the package a launch command runs."""
    if not command:
        return None
    base = _base(command)
    argv = list(args)
    if base in ("pnpm", "yarn", "bun") and argv[:1] == ["dlx"]:
        base, argv = "npx", argv[1:]
    if base in ("bun",) and argv[:1] == ["x"]:
        base, argv = "npx", argv[1:]
    if base in NODE_RUNNERS:
        i = 0
        while i < len(argv):
            a = argv[i]
            if a in ("-p", "--package"):
                i += 2
                continue
            if a.startswith("-"):
                i += 1
                continue
            name, ver = split_npm_spec(a)
            return {"ecosystem": "npm", "name": name, "version": ver}
        return None
    if base in PY_RUNNERS:
        if base == "pipx" and argv[:1] == ["run"]:
            argv = argv[1:]
        if "--from" in argv:
            idx = argv.index("--from")
            if idx + 1 < len(argv):
                name, ver = split_py_spec(argv[idx + 1])
                return {"ecosystem": "pypi", "name": name, "version": ver}
        for a in argv:
            if not a.startswith("-"):
                name, ver = split_py_spec(a)
                return {"ecosystem": "pypi", "name": name, "version": ver}
        return None
    if base in ("docker", "podman") and "run" in argv:
        i = argv.index("run") + 1
        while i < len(argv):
            a = argv[i]
            if a in _DOCKER_VALUE_FLAGS:
                i += 2
                continue
            if a.startswith("-"):
                i += 1
                continue
            image = a
            digest = None
            if "@" in image:
                image, digest = image.split("@", 1)
            tag = None
            last = image.rsplit("/", 1)[-1]
            if ":" in last:
                image, tag = image.rsplit(":", 1)
            return {"ecosystem": "docker", "name": image, "version": digest or tag}
        return None
    return None


def server_identity(entry: dict) -> str:
    """Stable identity for an MCP server across machines and versions."""
    url = entry.get("url")
    if url:
        parts = urlsplit(url)
        return f"mcp:url:{parts.netloc.lower()}{parts.path.rstrip('/')}"
    pkg = entry.get("package")
    if pkg:
        return f"mcp:{pkg['ecosystem']}:{pkg['name'].lower()}"
    command = entry.get("command") or ""
    args = entry.get("args") or []
    base = _base(command)
    if base in ("node", "python", "python3", "deno", "bun", "uv") and args:
        for a in args:
            if not a.startswith("-") and a not in ("run",):
                return f"mcp:local:{tilde(a)}"
    joined = " ".join([tilde(command) or ""] + [tilde(a) or "" for a in args]).strip()
    return f"mcp:cmd:{joined or entry.get('name', 'unknown')}"


def skill_identity(skill: dict) -> str:
    return f"skill:{skill['name'].strip().lower()}"


def launch_spec(entry: dict) -> dict:
    return {
        "transport": entry.get("transport"),
        "command": tilde(entry.get("command")),
        "args": [tilde(a) for a in (entry.get("args") or [])],
        "url": entry.get("url"),
        "env_keys": sorted(entry.get("env_keys") or []),
        "header_keys": sorted(k.lower() for k in (entry.get("header_keys") or [])),
    }


def normalize_tools(tools: list[dict]) -> list[dict]:
    out = []
    for t in tools:
        out.append(
            {
                "name": t.get("name"),
                "description": t.get("description") or "",
                "inputSchema": t.get("inputSchema") or {},
                "annotations": t.get("annotations") or {},
            }
        )
    return sorted(out, key=lambda t: str(t["name"]))


def server_hashes(entry: dict) -> tuple[str, Optional[str], str]:
    """Return (launch_hash, tools_hash, fingerprint)."""
    lh = sha256_text(canonical_json(launch_spec(entry)))
    tools = entry.get("tools")
    th = sha256_text(canonical_json(normalize_tools(tools))) if tools is not None else None
    fp = sha256_text(f"{lh}:{th or '-'}")
    return lh, th, fp


def skill_hashes(skill: dict) -> tuple[str, None, str]:
    files = sorted((f["path"], f["sha256"]) for f in skill.get("files") or [])
    h = sha256_text(canonical_json(files))
    return h, None, h
