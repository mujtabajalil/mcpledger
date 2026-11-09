"""Ask a configured MCP server which tools it advertises (tools/list).

This starts the server exactly as your editor would, so it only runs with
--introspect. It is what lets MCPLedger notice a "rug pull": the same package or URL
silently changing its tool descriptions after you approved it.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

from . import __version__

PROTOCOL_VERSION = "2025-06-18"
MAX_PAGES = 20


class IntrospectError(Exception):
    pass


def _init_msg(i: int) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": i,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcpledger", "version": __version__},
        },
    }


# --------------------------------------------------------------------------- stdio

class _StdioClient:
    def __init__(self, command: str, args: list[str], env: dict, cwd: Optional[str], timeout: float):
        full_env = dict(os.environ)
        full_env.update({k: v for k, v in env.items() if isinstance(v, str)})
        self.timeout = timeout
        try:
            self.proc = subprocess.Popen(
                [command, *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=full_env,
                cwd=os.path.expanduser(cwd) if cwd else None,
                shell=False,
            )
        except (OSError, ValueError) as exc:
            raise IntrospectError(f"could not start: {exc}") from exc
        self.q: "queue.Queue[Optional[dict]]" = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        assert self.proc.stdout
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self.q.put(json.loads(line))
            except ValueError:
                continue  # servers sometimes log to stdout
        self.q.put(None)

    def send(self, msg: dict):
        assert self.proc.stdin
        try:
            self.proc.stdin.write((json.dumps(msg) + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise IntrospectError("server exited early") from exc

    def request(self, msg: dict) -> dict:
        self.send(msg)
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise IntrospectError(f"timed out after {self.timeout:.0f}s")
            try:
                item = self.q.get(timeout=remaining)
            except queue.Empty:
                continue
            if item is None:
                raise IntrospectError("server closed the connection")
            if item.get("id") == msg["id"]:
                if "error" in item:
                    raise IntrospectError(str(item["error"].get("message", item["error"]))[:200])
                return item.get("result") or {}

    def close(self):
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def list_tools_stdio(command: str, args: list[str], env: dict, cwd: Optional[str] = None, timeout: float = 20) -> list[dict]:
    c = _StdioClient(command, args, env, cwd, timeout)
    try:
        c.request(_init_msg(1))
        c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return _paginate(c.request)
    finally:
        c.close()


def _paginate(request) -> list[dict]:
    tools: list[dict] = []
    cursor = None
    for page in range(MAX_PAGES):
        params = {"cursor": cursor} if cursor else {}
        res = request({"jsonrpc": "2.0", "id": 100 + page, "method": "tools/list", "params": params})
        tools.extend(res.get("tools") or [])
        cursor = res.get("nextCursor")
        if not cursor:
            break
    return tools


# --------------------------------------------------------------------------- http

class _HttpClient:
    def __init__(self, url: str, headers: dict, timeout: float):
        self.url = url
        self.headers = {k: v for k, v in headers.items() if isinstance(v, str)}
        self.timeout = timeout
        self.session: Optional[str] = None

    def _post(self, msg: dict) -> Optional[dict]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
            "User-Agent": f"mcpledger/{__version__}",
            **self.headers,
        }
        if self.session:
            h["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.url, data=json.dumps(msg).encode(), headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session = sid
                body = resp.read().decode("utf-8", errors="replace")
                ctype = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise IntrospectError(f"HTTP {exc.code}: needs authentication (OAuth servers are inventoried by config only)")
            raise IntrospectError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise IntrospectError(f"connection failed: {exc}") from exc
        if "id" not in msg:
            return None
        return _parse_body(body, ctype, msg["id"])

    def request(self, msg: dict) -> dict:
        item = self._post(msg)
        if item is None:
            raise IntrospectError("empty response")
        if "error" in item:
            raise IntrospectError(str(item["error"].get("message", item["error"]))[:200])
        return item.get("result") or {}


def _parse_body(body: str, ctype: str, want_id) -> Optional[dict]:
    if "text/event-stream" in ctype:
        for block in body.split("\n\n"):
            data = "\n".join(l[5:].lstrip() for l in block.splitlines() if l.startswith("data:"))
            if not data:
                continue
            try:
                item = json.loads(data)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("id") == want_id:
                return item
        return None
    try:
        item = json.loads(body)
    except ValueError:
        return None
    if isinstance(item, list):
        for it in item:
            if isinstance(it, dict) and it.get("id") == want_id:
                return it
        return None
    return item


def list_tools_http(url: str, headers: dict, timeout: float = 20) -> list[dict]:
    c = _HttpClient(url, headers, timeout)
    c.request(_init_msg(1))
    c._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return _paginate(c.request)


def introspect(entry: dict, timeout: float = 20) -> list[dict]:
    if entry.get("transport") == "stdio":
        if not entry.get("command"):
            raise IntrospectError("no command")
        return list_tools_stdio(entry["command"], entry.get("args") or [], entry.get("_env") or {},
                                entry.get("_cwd"), timeout)
    if entry.get("transport") == "sse":
        raise IntrospectError("legacy SSE transport is inventoried by config only")
    if entry.get("url"):
        return list_tools_http(entry["url"], entry.get("_headers") or {}, timeout)
    raise IntrospectError("unknown transport")
