"""Static checks for MCP server configs, tool definitions and agent skills.

These are heuristics, not proof. They exist to put the right things in front of a
human reviewer before a component is approved. Every finding has:
  rule, severity (info|low|medium|high|critical), title, detail, location
"""
from __future__ import annotations

import re
from typing import Iterable, Optional
from urllib.parse import urlsplit

SEVERITIES = ["info", "low", "medium", "high", "critical"]
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}

INVISIBLE_RE = re.compile(
    "[​-‏‪-‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]"
)
HIDDEN_TAG_RE = re.compile(r"<\s*/?\s*(important|system|instructions?|secret|hidden|admin)\b[^>]*>", re.I)
SENSITIVE_PATH = (
    r"(~/\.ssh|\.ssh/|id_rsa|id_ed25519|\.aws/credentials|\.config/gcloud|\.kube/config|"
    r"\.netrc|\.npmrc|\.pypirc|\.git-credentials|\.docker/config\.json|mcp\.json|"
    r"claude_desktop_config|\.claude\.json|\.env\b|keychain|login\.keychain)"
)
SENSITIVE_RE = re.compile(SENSITIVE_PATH, re.I)
READ_SENSITIVE_RE = re.compile(
    r"\b(read|cat|open|include|send|upload|pass|attach|copy|extract|exfiltrat\w*)\b.{0,80}" + SENSITIVE_PATH,
    re.I | re.S,
)

DESTINATION_RE = re.compile(
    r"\b(always\s+)?(send|forward|bcc|cc|copy|upload|exfiltrate)\b[^.\n]{0,60}?"
    r"([\w.+-]+@[\w-]+\.[\w.-]+|https?://[^\s\"'<>)]+)",
    re.I,
)

TEXT_RULES = [
    (
        "SG101",
        "high",
        "Instruction-override phrase",
        re.compile(r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier|other)\s+(instructions|prompts|rules|guidelines)", re.I),
        "Text tells the model to disregard earlier instructions, a classic prompt-injection pattern.",
    ),
    (
        "SG102",
        "high",
        "Asks the agent to hide actions from the user",
        re.compile(
            r"(do\s+not|don't|dont|never|without)\s+(tell(ing)?|inform(ing)?|mention(ing)?|reveal(ing)?|notify(ing)?|"
            r"alert(ing)?|show(ing)?|disclos(e|ing))\b[^.\n]{0,50}?\b(the\s+)?users?\b",
            re.I,
        ),
        "Legitimate tools rarely need the model to keep something from the user.",
    ),
    (
        "SG103",
        "medium",
        "Hidden-instruction markup",
        HIDDEN_TAG_RE,
        "Tags like <IMPORTANT> or <SYSTEM> inside a description are used to smuggle instructions into the model's context.",
    ),
    (
        "SG104",
        "medium",
        "Tries to steer use of other tools",
        re.compile(
            r"((instead\s+of|rather\s+than)\s+(using|calling)\s+(the\s+)?[\w\-]+(\s+tool)?)|(\b(all|every|any)\s+other\s+tools?\b)|(when\s+(using|calling)\s+(the\s+)?[\w\-]+\s+tool\b)",
            re.I,
        ),
        "Descriptions that talk about other tools can shadow or hijack them (tool shadowing).",
    ),
    (
        "SG105",
        "low",
        "Pre-call instruction",
        re.compile(r"before\s+(using|calling|invoking|running)\s+(this|any|the)\b.{0,40}\btools?\b", re.I),
        "Often benign, but worth a look: it tells the model to do something before any call.",
    ),
]

SCRIPT_RULES = [
    ("SG201", "high", "Downloads and executes remote code",
     re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b|iex\s*\(\s*(iwr|irm|invoke-webrequest)|invoke-expression", re.I),
     "Piping a download straight into a shell runs code nobody reviewed."),
    ("SG202", "high", "Decodes and executes obfuscated payload",
     re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(ba|z)?sh|eval\s*\(\s*(atob|base64|b64decode)|exec\s*\(\s*(base64|b64decode|codecs\.decode)", re.I),
     "Base64-decoded code executed at runtime hides what actually runs."),
    ("SG203", "critical", "Reverse-shell pattern",
     re.compile(r"/dev/tcp/|\bnc\s+(-\w+\s+)*-e\b|\bncat\b.*-e\b|socat\s+.*exec:", re.I),
     "This pattern opens an interactive shell to a remote host."),
    ("SG204", "medium", "Uploads data to the network",
     re.compile(r"curl\b[^\n]*\s(-d|--data(-binary|-raw)?|-F|--form|-T|--upload-file)\b|wget\b[^\n]*--post-(data|file)", re.I),
     "Sends data off the machine. Check where it goes and what is sent."),
    ("SG205", "low", "Makes outbound HTTP POST requests",
     re.compile(r"requests\.(post|put)\(|httpx\.(post|put)\(|urllib\.request\.urlopen\(|fetch\([^)]*method\s*:\s*['\"](POST|PUT)", re.I),
     "Outbound writes are common in legitimate skills; confirm the destination."),
    ("SG206", "high", "Destructive filesystem command",
     re.compile(r"rm\s+-[a-z]*r[a-z]*f?\s+(~|/(\s|$)|\$HOME|/\*)|rm\s+-[a-z]*f[a-z]*r\s+(~|/(\s|$)|\$HOME)", re.I),
     "Recursive delete of the home or root directory."),
    ("SG207", "low", "Dynamic code execution",
     re.compile(r"\beval\s*\(|\bexec\s*\(|child_process|subprocess\.(Popen|run|call)\(.*shell\s*=\s*True", re.I),
     "Runs code or shell commands built at runtime."),
]

SECRET_KEY_RE = re.compile(r"(key|token|secret|password|passwd|pat|credential|auth)", re.I)


def finding(rule: str, severity: str, title: str, detail: str, location: str, evidence: Optional[str] = None) -> dict:
    f = {"rule": rule, "severity": severity, "title": title, "detail": detail, "location": location}
    if evidence:
        f["evidence"] = evidence[:160]
    return f


def _snippet(text: str, m: re.Match) -> str:
    start = max(0, m.start() - 40)
    end = min(len(text), m.end() + 40)
    return text[start:end].replace("\n", " ").strip()


def scan_text(text: str, location: str) -> list[dict]:
    """Prompt-injection checks for text the model will read (tool descriptions, SKILL.md)."""
    out: list[dict] = []
    if not text:
        return out
    inv = INVISIBLE_RE.findall(text)
    if inv:
        cps = sorted({f"U+{ord(c):04X}" for c in inv})[:6]
        out.append(finding("SG100", "critical", "Invisible Unicode characters",
                           "Zero-width, bidi-override or tag characters can hide instructions that humans cannot see "
                           f"but models read. Found: {', '.join(cps)}.", location))
    for rule, sev, title, rx, detail in TEXT_RULES:
        m = rx.search(text)
        if m:
            out.append(finding(rule, sev, title, detail, location, _snippet(text, m)))
    m = DESTINATION_RE.search(text)
    if m:
        out.append(finding("SG109", "high", "Sends data to a hard-coded destination",
                           "Tells the model to send, copy or forward data to a fixed address or URL. "
                           "This is how a poisoned email or HTTP tool quietly exfiltrates data.",
                           location, _snippet(text, m)))
    m = READ_SENSITIVE_RE.search(text)
    if m:
        out.append(finding("SG106", "high", "References credentials or agent config files",
                           "Asks the model to read or send files that hold secrets or other servers' configuration.",
                           location, _snippet(text, m)))
    elif (m := SENSITIVE_RE.search(text)):
        out.append(finding("SG107", "medium", "Mentions a sensitive file path",
                           "Mentions a credentials or config path. Check why a tool needs it.", location, _snippet(text, m)))
    if len(text) > 4000:
        out.append(finding("SG108", "low", "Very long description",
                           f"{len(text)} characters. Long descriptions are a common place to bury instructions.", location))
    return out


def scan_script(text: str, location: str) -> list[dict]:
    out = []
    for rule, sev, title, rx, detail in SCRIPT_RULES:
        m = rx.search(text)
        if m:
            line = text.count("\n", 0, m.start()) + 1
            out.append(finding(rule, sev, title, detail, f"{location}:{line}", _snippet(text, m)))
    m = READ_SENSITIVE_RE.search(text)
    if m:
        line = text.count("\n", 0, m.start()) + 1
        out.append(finding("SG208", "high", "Script touches credential files",
                           "Reads or sends files that hold secrets.", f"{location}:{line}", _snippet(text, m)))
    return out


def _is_local_host(host: str) -> bool:
    return host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".localhost")


def scan_server(entry: dict) -> list[dict]:
    """Checks on an MCP server entry (config + optional tool definitions)."""
    out: list[dict] = []
    loc = "config"
    pkg = entry.get("package")
    if pkg and pkg.get("ecosystem") in ("npm", "pypi"):
        ver = (pkg.get("version") or "").strip().lower()
        if not ver or ver in ("latest", "next", "*") or ver.startswith("^") or ver.startswith("~"):
            out.append(finding("SG001", "low", "Unpinned package version",
                               f"{pkg['name']} runs whatever version is newest at launch, so the code can change "
                               "under you without any config change. Pin an exact version.", loc))
    if pkg and pkg.get("ecosystem") == "docker":
        ver = pkg.get("version") or ""
        if not ver or ver == "latest":
            out.append(finding("SG001", "low", "Unpinned container image",
                               f"{pkg['name']} uses a moving tag. Pin a version or digest.", loc))
    for key in entry.get("inline_secret_keys") or []:
        out.append(finding("SG002", "medium", "Static secret stored in config",
                           f"'{key}' holds a literal credential in a plain-text config file. Prefer OAuth or an "
                           "environment/keychain reference. (The value is never sent to MCPLedger.)", loc))
    url = entry.get("url")
    if url:
        parts = urlsplit(url)
        if parts.scheme == "http" and not _is_local_host((parts.hostname or "").lower()):
            out.append(finding("SG003", "medium", "Remote server over plain HTTP",
                               "Traffic, including any auth headers, is unencrypted.", loc))
    cmdline = " ".join([entry.get("command") or ""] + list(entry.get("args") or []))
    if re.search(r"(curl|wget)[^|]*\|\s*(ba|z)?sh", cmdline):
        out.append(finding("SG004", "high", "Launch command pipes a download into a shell",
                           "The server is started by executing remote code.", loc, cmdline))
    base = (entry.get("command") or "").rsplit("/", 1)[-1].lower()
    if base == "sudo":
        out.append(finding("SG005", "high", "Server runs with sudo", "The MCP server would run as root.", loc))
    if base in ("docker", "podman"):
        if re.search(r"--privileged|/var/run/docker\.sock|-v\s+/:/|--volume\s+/:/|--pid[= ]host|--network[= ]host", cmdline):
            out.append(finding("SG006", "high", "Container escapes its sandbox",
                               "Privileged mode, host root mount, host network/pid or the Docker socket gives the "
                               "server broad access to the machine.", loc, cmdline))
    tools = entry.get("tools")
    if tools:
        names = [t.get("name") for t in tools]
        for t in tools:
            name = t.get("name") or "?"
            out.extend(scan_text(t.get("description") or "", f"tool:{name}"))
            out.extend(_scan_schema(t.get("inputSchema") or {}, f"tool:{name}"))
        if len(set(names)) != len(names):
            out.append(finding("SG007", "medium", "Duplicate tool names",
                               "The server advertises the same tool name twice.", "tools"))
    return out


def _scan_schema(schema: dict, location: str, depth: int = 0) -> list[dict]:
    out = []
    if depth > 4 or not isinstance(schema, dict):
        return out
    props = schema.get("properties") or {}
    if isinstance(props, dict):
        for pname, p in props.items():
            if isinstance(p, dict):
                desc = p.get("description")
                if isinstance(desc, str):
                    for f in scan_text(desc, f"{location}.{pname}"):
                        out.append(f)
                out.extend(_scan_schema(p, f"{location}.{pname}", depth + 1))
    return out


SCRIPT_EXT = (".sh", ".bash", ".zsh", ".py", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".rb", ".pl", ".bat", ".cmd")


def scan_skill(skill: dict) -> list[dict]:
    out: list[dict] = []
    files = skill.get("files") or []
    scripts = 0
    for f in files:
        path = f.get("path") or ""
        content = f.get("content")
        if path.lower().endswith(SCRIPT_EXT):
            scripts += 1
        if content is None:
            continue
        if path.upper().endswith("SKILL.MD") or path.lower().endswith((".md", ".txt")):
            out.extend(scan_text(content, f"file:{path}"))
            # Code blocks in markdown get the script checks too.
            for block in re.findall(r"```[\w-]*\n(.*?)```", content, re.S):
                out.extend(scan_script(block, f"file:{path}"))
        elif path.lower().endswith(SCRIPT_EXT):
            out.extend(scan_script(content, f"file:{path}"))
            if INVISIBLE_RE.search(content):
                out.append(finding("SG100", "critical", "Invisible Unicode characters",
                                   "Hidden characters inside a script.", f"file:{path}"))
    if scripts:
        out.append(finding("SG209", "info", "Skill ships executable scripts",
                           f"{scripts} script file(s). Agents may run these on the developer's machine.", "files"))
    if skill.get("description"):
        out.extend(scan_text(skill["description"], "frontmatter.description"))
    return dedupe(out)


def dedupe(findings: Iterable[dict]) -> list[dict]:
    seen = set()
    out = []
    for f in findings:
        key = (f["rule"], f["location"])
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


def max_severity(findings: Iterable[dict]) -> Optional[str]:
    best = None
    for f in findings:
        if best is None or SEV_RANK[f["severity"]] > SEV_RANK[best]:
            best = f["severity"]
    return best
