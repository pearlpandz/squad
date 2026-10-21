"""Read callable Codex CLI apps and their read-only tools from app-server."""

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ReadApp:
    id: str
    name: str
    slug: str
    tools: tuple[str, ...]
    blocked_tools: tuple[str, ...]


_cache: tuple[ReadApp, ...] = ()
_cache_until = 0.0
_lock = threading.Lock()


def _catalog_request() -> tuple[ReadApp, ...]:
    executable = shutil.which("codex.exe" if os.name == "nt" else "codex")
    if not executable and os.name == "nt":
        executable = shutil.which("codex.cmd")
    if not executable:
        raise RuntimeError("Codex CLI is not on the backend PATH")
    child_env = os.environ.copy()
    child_env.pop("CODEX_APP_TOOLS_PIPE_PATH", None)
    process = subprocess.Popen(
        [executable, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        env=child_env,
    )
    output: queue.Queue[str] = queue.Queue()
    threading.Thread(target=lambda: [output.put(line) for line in process.stdout], daemon=True).start()

    def request(request_id: int, method: str, params: dict) -> dict:
        process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                line = output.get(timeout=min(1, max(0.01, deadline - time.monotonic())))
                response = json.loads(line)
            except (queue.Empty, ValueError):
                continue
            if response.get("id") == request_id:
                if response.get("error"):
                    raise RuntimeError(f"Codex app catalog rejected {method}")
                return response.get("result") or {}
        raise RuntimeError(f"Codex app catalog timed out during {method}")

    try:
        request(1, "initialize", {
            "clientInfo": {"name": "multi-agent-team", "version": "1"},
            "capabilities": {"experimentalApi": True},
        })
        process.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
        process.stdin.flush()
        installed = request(2, "app/installed", {"forceRefresh": True})
        ids = [app["id"] for app in installed.get("apps", [])
               if app.get("enabled") and app.get("callable") and isinstance(app.get("id"), str)]
        if not ids:
            return ()
        metadata = request(3, "app/read", {"appIds": ids, "includeTools": True})
        apps = []
        for app in metadata.get("apps", []):
            if app.get("id") not in ids:
                continue
            tools = tuple(tool["name"] for tool in app.get("toolSummaries", [])
                          if tool.get("isEnabled") and tool.get("isReadOnly") is True
                          and isinstance(tool.get("name"), str))
            blocked = tuple(tool["name"] for tool in app.get("toolSummaries", [])
                            if not (tool.get("isEnabled") and tool.get("isReadOnly") is True)
                            and isinstance(tool.get("name"), str))
            install_path = urlparse(app.get("installUrl") or "").path.strip("/").split("/")
            slug = install_path[1] if len(install_path) == 3 and install_path[0] == "apps" \
                and install_path[2] == app["id"] else ""
            if tools and re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
                apps.append(ReadApp(app["id"], app.get("name") or app["id"], slug, tools, blocked))
        return tuple(apps)
    finally:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def connected_read_apps() -> tuple[ReadApp, ...]:
    """Refresh the read-only app catalog at most once per minute."""
    global _cache, _cache_until
    with _lock:
        if time.monotonic() >= _cache_until:
            try:
                _cache = _catalog_request()
            except OSError as exc:
                raise RuntimeError("Codex app catalog is unavailable") from exc
            _cache_until = time.monotonic() + 60
        return _cache
