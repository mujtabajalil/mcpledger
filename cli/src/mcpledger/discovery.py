"""Find MCP server configs and agent skills on this machine.

Nothing here executes anything. Secret *values* never leave this module: only the
names of env vars / headers and whether a literal secret is present.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from pathlib import Path
from typing import Iterator, Optional

from . import fingerprint as fpmod

try:  # Python 3.11+
    import tomllib  # type: ignore
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

MAX_FILE_BYTES = 64 * 1024
MAX_SKILL_FILES = 60
TEXT_EXT = (".md", ".txt", ".sh", ".bash", ".zsh", ".py", ".js", ".mjs", ".cjs", ".ts", ".json", ".yaml",
            ".yml", ".toml", ".ps1", ".rb", ".pl", ".bat", ".cmd", ".html", ".css", ".xml", ".csv")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


# --------------------------------------------------------------------------- utils

def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments and trailing commas, leaving strings intact."""
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_json(path: Path) -> Optional[dict]:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    for candidate in (raw, strip_jsonc(raw)):
        try:
            data = json.loads(candidate)
            return data if isinstance(data, dict) else None
        except ValueError:
            continue
    return None


def load_toml(path: Path) -> Optional[dict]:
    try:
        if tomllib is None:
            return parse_toml_subset(path.read_text(encoding="utf-8"))
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return None


_TOML_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", '"': '"', "\\": "\\"}
_TOML_BARE = re.compile(r"[A-Za-z0-9_-]+")
_TOML_NUM = re.compile(r"[+-]?[0-9_]+(\.[0-9_]+)?([eE][+-]?[0-9]+)?")


def parse_toml_subset(s: str) -> dict:
    """Stdlib-only TOML reader for Python < 3.11. Raises on anything it does not understand."""
    # shortcut: no dates, multi-line strings, hex/inf/nan, and [[array of tables]] are skipped; drop this when the minimum Python becomes 3.11
    i = 0

    def ws(nl: bool = False) -> None:  # skip blanks and comments, and newlines if nl
        nonlocal i
        while i < len(s) and (s[i] in " \t\r#" or (nl and s[i] == "\n")):
            if s[i] == "#":
                j = s.find("\n", i)
                i = len(s) if j < 0 else j
            else:
                i += 1

    def string() -> str:
        nonlocal i
        q, out, i = s[i], [], i + 1
        while s[i] != q:
            if s[i] == "\n":
                raise ValueError("newline in string")
            if s[i] == "\\" and q == '"':
                e = s[i + 1]
                n = {"u": 4, "U": 8}.get(e, 0)
                out.append(chr(int(s[i + 2:i + 2 + n], 16)) if n else _TOML_ESC[e])
                i += 2 + n
            else:
                out.append(s[i])
                i += 1
        i += 1
        return "".join(out)

    def key() -> list:
        nonlocal i
        parts = []
        while True:
            ws()
            if s[i] in "\"'":
                parts.append(string())
            else:
                m = _TOML_BARE.match(s, i)
                if not m:
                    raise ValueError("bad key")
                parts.append(m.group())
                i = m.end()
            ws()
            if s[i:i + 1] != ".":
                return parts
            i += 1

    def seq(close: str, item) -> None:  # comma-separated items up to `close`, trailing comma allowed
        nonlocal i
        i += 1
        while True:
            ws(True)
            if s[i] == close:
                i += 1
                return
            item()
            ws(True)
            if s[i] == ",":
                i += 1
            elif s[i] != close:
                raise ValueError("expected , or " + close)

    def value():
        nonlocal i
        if s[i] in "\"'":
            return string()
        if s[i] == "[":
            arr: list = []
            seq("]", lambda: arr.append(value()))
            return arr
        if s[i] == "{":
            tbl: dict = {}
            seq("}", lambda: assign(tbl))
            return tbl
        for word, v in (("true", True), ("false", False)):
            if s.startswith(word, i):
                i += len(word)
                return v
        m = _TOML_NUM.match(s, i)
        if not m:
            raise ValueError("bad value")
        i, t = m.end(), m.group().replace("_", "")
        return float(t) if m.group(1) or m.group(2) else int(t)

    def descend(d: dict, path: list) -> dict:
        for p in path:
            d = d.setdefault(p, {})
            if not isinstance(d, dict):
                raise ValueError("key is not a table")
        return d

    def assign(table: dict) -> None:
        nonlocal i
        *path, last = key()
        if s[i] != "=":
            raise ValueError("expected =")
        i += 1
        ws()
        d = descend(table, path)
        if last in d:
            raise ValueError("duplicate key")
        d[last] = value()

    root = cur = {}
    while True:
        ws(True)
        if i >= len(s):
            return root
        if s[i] == "[":
            aot = s.startswith("[[", i)
            i += 2 if aot else 1
            path = key()
            if s[i:i + (2 if aot else 1)] != ("]]" if aot else "]"):
                raise ValueError("bad table header")
            i += 2 if aot else 1
            cur = {} if aot else descend(root, path)  # [[...]] contents are parsed then dropped
        else:
            assign(cur)
        ws()
        if i < len(s) and s[i] != "\n":
            raise ValueError("expected end of line")


def _looks_like_reference(value: str) -> bool:
    v = value.strip()
    return (v.startswith("${") or v.startswith("$") or v.startswith("{{") or v.startswith("env:")
            or v.startswith("op://") or v.lower() in ("", "true", "false"))


def _inline_secrets(mapping: dict) -> list[str]:
    keys = []
    for k, v in (mapping or {}).items():
        if not isinstance(v, str):
            continue
        if k.lower() == "authorization" or re.search(r"(key|token|secret|password|passwd|pat|credential)", k, re.I):
            val = v.split(" ", 1)[-1] if k.lower() == "authorization" else v
            if len(val) >= 8 and not _looks_like_reference(val):
                keys.append(k)
    return keys


# --------------------------------------------------------------------------- servers

def normalize_server(name: str, raw: dict, client: str, scope: str, config_path: Path) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    if raw.get("disabled") is True or raw.get("enabled") is False:
        disabled = True
    else:
        disabled = False
    command = raw.get("command")
    args = raw.get("args") or []
    # Zed-style {"command": {"path": ..., "args": [...]}}
    if isinstance(command, dict):
        args = command.get("args") or []
        command = command.get("path")
    if isinstance(command, list):
        command, args = (command[0] if command else None), command[1:] + list(args)
    url = raw.get("url") or raw.get("httpUrl") or raw.get("serverUrl")
    transport = (raw.get("type") or raw.get("transport") or "").lower()
    if not transport:
        transport = "http" if url else "stdio"
    if transport in ("streamable-http", "streamablehttp", "http"):
        transport = "http"
    env = raw.get("env") or raw.get("environment") or {}
    headers = raw.get("headers") or {}
    if not isinstance(env, dict):
        env = {}
    if not isinstance(headers, dict):
        headers = {}
    args = [str(a) for a in args if a is not None]
    entry = {
        "name": name,
        "client": client,
        "scope": scope,
        "config_path": fpmod.tilde(str(config_path)),
        "transport": transport,
        "command": str(command) if command else None,
        "args": args,
        "url": url,
        "env_keys": sorted(env.keys()),
        "header_keys": sorted(headers.keys()),
        "inline_secret_keys": sorted(_inline_secrets(env) + _inline_secrets(headers)),
        "disabled": disabled,
    }
    entry["package"] = fpmod.package_of(entry["command"], args)
    entry["identity"] = fpmod.server_identity(entry)
    # Kept locally only (for --introspect); stripped before upload.
    entry["_env"] = {k: str(v) for k, v in env.items()}
    entry["_headers"] = {k: str(v) for k, v in headers.items()}
    entry["_cwd"] = raw.get("cwd")
    return entry


def _servers_from_map(mapping, client, scope, path) -> Iterator[dict]:
    if isinstance(mapping, dict):
        for name, raw in mapping.items():
            e = normalize_server(str(name), raw, client, scope, path)
            if e:
                yield e


def app_support_dirs(home: Path) -> list[Path]:
    """Per-OS 'application support' directories where desktop apps keep settings."""
    dirs = []
    if sys.platform == "darwin":
        dirs.append(home / "Library" / "Application Support")
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            dirs.append(Path(appdata))
    else:
        dirs.append(Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config"))
    return dirs


def user_config_files(home: Path) -> list[tuple[str, str, Path, str]]:
    """(client, format, path, key-spec) for user-level MCP configs."""
    files: list[tuple[str, str, Path, str]] = [
        ("claude-code", "json", home / ".claude.json", "claude-code"),
        ("claude-code", "json", home / ".claude" / "settings.json", "mcpServers"),
        ("cursor", "json", home / ".cursor" / "mcp.json", "mcpServers"),
        ("windsurf", "json", home / ".codeium" / "windsurf" / "mcp_config.json", "mcpServers"),
        ("gemini-cli", "json", home / ".gemini" / "settings.json", "mcpServers"),
        ("codex", "toml", home / ".codex" / "config.toml", "mcp_servers"),
        ("amazon-q", "json", home / ".aws" / "amazonq" / "mcp.json", "mcpServers"),
    ]
    for base in app_support_dirs(home):
        files.append(("claude-desktop", "json", base / "Claude" / "claude_desktop_config.json", "mcpServers"))
        for code in ("Code", "Code - Insiders", "VSCodium", "Cursor"):
            client = "vscode" if code != "Cursor" else "cursor"
            files.append((client, "json", base / code / "User" / "settings.json", "mcp.servers"))
            files.append((client, "json", base / code / "User" / "mcp.json", "servers"))
            files.append(("cline", "json", base / code / "User" / "globalStorage" / "saoudrizwan.claude-dev" /
                          "settings" / "cline_mcp_settings.json", "mcpServers"))
            files.append(("roo-code", "json", base / code / "User" / "globalStorage" / "rooveterinaryinc.roo-cline" /
                          "settings" / "mcp_settings.json", "mcpServers"))
        files.append(("zed", "json", base / "zed" / "settings.json", "context_servers"))
    files.append(("zed", "json", home / ".config" / "zed" / "settings.json", "context_servers"))
    return files


def project_config_files(project: Path) -> list[tuple[str, str, Path, str]]:
    return [
        ("claude-code", "json", project / ".mcp.json", "mcpServers"),
        ("cursor", "json", project / ".cursor" / "mcp.json", "mcpServers"),
        ("vscode", "json", project / ".vscode" / "mcp.json", "servers"),
        ("gemini-cli", "json", project / ".gemini" / "settings.json", "mcpServers"),
        ("windsurf", "json", project / ".windsurf" / "mcp.json", "mcpServers"),
        ("codex", "toml", project / ".codex" / "config.toml", "mcp_servers"),
    ]


def _dig(data: dict, dotted: str):
    if dotted in data:
        return data[dotted]
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def servers_from_file(client: str, fmt: str, path: Path, key: str, scope: str) -> list[dict]:
    if not path.is_file():
        return []
    data = load_toml(path) if fmt == "toml" else load_json(path)
    if not data:
        return []
    out: list[dict] = []
    if key == "claude-code":
        out.extend(_servers_from_map(data.get("mcpServers"), client, "user", path))
        projects = data.get("projects") or {}
        if isinstance(projects, dict):
            for proj_path, proj in projects.items():
                if isinstance(proj, dict):
                    for e in _servers_from_map(proj.get("mcpServers"), client, "local", path):
                        e["project"] = fpmod.tilde(proj_path)
                        out.append(e)
        return out
    out.extend(_servers_from_map(_dig(data, key), client, scope, path))
    return out


def discover_servers(home: Path, projects: list[Path]) -> list[dict]:
    seen = set()
    out = []
    candidates = [(c, f, p, k, "user") for c, f, p, k in user_config_files(home)]
    for proj in projects:
        candidates += [(c, f, p, k, "project") for c, f, p, k in project_config_files(proj)]
    for client, fmt, path, key, scope in candidates:
        try:
            rp = path.resolve()
        except OSError:
            rp = path
        sig = (str(rp), key)
        if sig in seen:
            continue
        seen.add(sig)
        for e in servers_from_file(client, fmt, path, key, scope):
            out.append(e)
    return out


# --------------------------------------------------------------------------- skills

def parse_frontmatter(text: str) -> dict:
    m = re.match(r"^﻿?---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    if not m:
        return {}
    meta: dict = {}
    key = None
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        if km:
            key = km.group(1)
            val = km.group(2).strip()
            if val in ("|", ">", "|-", ">-"):
                val = ""
            meta[key] = val.strip("\"'")
        elif key and line.startswith((" ", "\t")):
            meta[key] = (meta[key] + " " + line.strip()).strip()
    return meta


def skill_roots(home: Path, projects: list[Path]) -> list[tuple[str, str, Path]]:
    roots = [
        ("claude-code", "user", home / ".claude" / "skills"),
        ("codex", "user", home / ".codex" / "skills"),
        ("cursor", "user", home / ".cursor" / "skills"),
        ("agents", "user", home / ".agents" / "skills"),
        ("gemini-cli", "user", home / ".gemini" / "skills"),
    ]
    plugin_root = home / ".claude" / "plugins"
    if plugin_root.is_dir():
        for p in _walk_dirs(plugin_root, max_depth=6):
            if p.name == "skills":
                roots.append(("claude-plugin", "plugin", p))
    for proj in projects:
        roots += [
            ("claude-code", "project", proj / ".claude" / "skills"),
            ("codex", "project", proj / ".codex" / "skills"),
            ("cursor", "project", proj / ".cursor" / "skills"),
            ("agents", "project", proj / ".agents" / "skills"),
        ]
    return roots


def _walk_dirs(root: Path, max_depth: int) -> Iterator[Path]:
    stack = [(root, 0)]
    while stack:
        cur, d = stack.pop()
        try:
            children = [c for c in cur.iterdir() if c.is_dir() and c.name not in SKIP_DIRS]
        except OSError:
            continue
        for c in children:
            yield c
            if d + 1 < max_depth:
                stack.append((c, d + 1))


def read_skill(skill_dir: Path, client: str, scope: str, include_content: bool) -> Optional[dict]:
    skill_md = None
    for cand in ("SKILL.md", "skill.md", "Skill.md"):
        if (skill_dir / cand).is_file():
            skill_md = skill_dir / cand
            break
    if not skill_md:
        return None
    try:
        md_text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta = parse_frontmatter(md_text)
    files = []
    count = 0
    for path in sorted(_iter_files(skill_dir)):
        count += 1
        if count > MAX_SKILL_FILES:
            break
        rel = path.relative_to(skill_dir).as_posix()
        try:
            data = path.read_bytes()
        except OSError:
            continue
        rec = {"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        if include_content and len(data) <= MAX_FILE_BYTES and path.suffix.lower() in TEXT_EXT:
            rec["content"] = data.decode("utf-8", errors="replace")
        elif path.suffix.lower() in TEXT_EXT and len(data) <= MAX_FILE_BYTES:
            rec["_content"] = data.decode("utf-8", errors="replace")  # local scanning only
        files.append(rec)
    name = meta.get("name") or skill_dir.name
    skill = {
        "name": name,
        "description": meta.get("description", "")[:2000],
        "client": client,
        "scope": scope,
        "path": fpmod.tilde(str(skill_dir)),
        "files": files,
        "truncated": count > MAX_SKILL_FILES,
    }
    skill["identity"] = fpmod.skill_identity(skill)
    return skill


def _iter_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            p = Path(dirpath) / f
            if p.is_file() and not p.is_symlink():
                yield p


def discover_skills(home: Path, projects: list[Path], include_content: bool = True) -> list[dict]:
    out = []
    seen = set()
    for client, scope, root in skill_roots(home, projects):
        if not root.is_dir():
            continue
        try:
            children = sorted(c for c in root.iterdir() if c.is_dir())
        except OSError:
            continue
        for child in children:
            try:
                key = str(child.resolve())
            except OSError:
                key = str(child)
            if key in seen:
                continue
            seen.add(key)
            s = read_skill(child, client, scope, include_content)
            if s:
                out.append(s)
    return out


# --------------------------------------------------------------------------- top level

def host_info() -> dict:
    return {
        "hostname": platform.node() or "unknown",
        "os": f"{platform.system()} {platform.release()}".strip(),
        "username": os.environ.get("USER") or os.environ.get("USERNAME") or "",
        "python": platform.python_version(),
    }


def discover(home: Optional[Path] = None, projects: Optional[list[Path]] = None, include_content: bool = True) -> dict:
    home = home or Path.home()
    projects = projects if projects is not None else [Path.cwd()]
    projects = [p.resolve() for p in projects if p.is_dir() and p.resolve() != home.resolve()]
    return {
        "host": host_info(),
        "mcp_servers": discover_servers(home, projects),
        "skills": discover_skills(home, projects, include_content),
    }
