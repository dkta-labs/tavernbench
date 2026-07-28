"""
tavernbench doctor — health check CLI

Checks:
  1. Server reachable  (HTTP GET /health)
  2. API key valid     (WebSocket connect attempt)
  3. MCP server registered with detected client(s)

Usage:
    tavernbench doctor
    tavernbench doctor --server ws://localhost:4100 --api-key tb-xxxx
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ANSI colours (fallback to plain when not a tty)
_tty = sys.stdout.isatty()
GREEN  = "\033[32m" if _tty else ""
RED    = "\033[31m" if _tty else ""
YELLOW = "\033[33m" if _tty else ""
RESET  = "\033[0m"  if _tty else ""
BOLD   = "\033[1m"  if _tty else ""

PASS  = f"{GREEN}PASS{RESET}"
FAIL  = f"{RED}FAIL{RESET}"
WARN  = f"{YELLOW}WARN{RESET}"
SKIP  = f"{YELLOW}SKIP{RESET}"


def _print_check(label: str, status: str, detail: str = "") -> None:
    line = f"  [{status}] {label}"
    if detail:
        line += f"  — {detail}"
    print(line)


# ---------------------------------------------------------------------------
# Check 1: server reachable
# ---------------------------------------------------------------------------

def check_server_reachable(server: str) -> tuple[bool, str]:
    """
    Convert ws(s):// → http(s):// and hit /health.
    Returns (ok, detail_message).
    """
    http_base = server.replace("ws://", "http://").replace("wss://", "https://")
    url = http_base.rstrip("/") + "/health"
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            if resp.status == 200:
                return True, f"HTTP 200 from {url}"
            return False, f"HTTP {resp.status} from {url}: {body[:80]}"
    except urllib.error.URLError as e:
        return False, f"Cannot reach {url}: {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


# ---------------------------------------------------------------------------
# Check 2: API key valid
# ---------------------------------------------------------------------------

def check_api_key(server: str, api_key: Optional[str]) -> tuple[bool, str]:
    """
    Attempt a WebSocket upgrade. The server rejects invalid keys with HTTP 403
    before the upgrade completes.
    Returns (ok, detail_message).
    """
    if not api_key:
        return False, "No API key provided (set TAVERNBENCH_API_KEY or pass --api-key)"

    try:
        import websockets.sync.client as wssync  # type: ignore
    except ImportError:
        # websockets < 12 doesn't have sync client — fall back to HTTP trick
        return _check_api_key_http(server, api_key)

    uri = (
        server.rstrip("/")
        + f"/socket/websocket?api_key={api_key}&protocol_version=1.0&vsn=2.0.0"
    )
    try:
        with wssync.connect(uri, open_timeout=5) as ws:
            ws.close()
        return True, f"WebSocket upgrade accepted for key prefix {api_key[:6]}…"
    except Exception as exc:
        msg = str(exc)
        if "403" in msg or "Forbidden" in msg or "forbidden" in msg.lower():
            return False, "Server rejected key (HTTP 403) — key may be invalid or revoked"
        if "404" in msg:
            return False, f"WebSocket endpoint not found (HTTP 404) — wrong server? ({msg[:80]})"
        if "refused" in msg.lower():
            return False, f"Connection refused — is the server up? ({msg[:80]})"
        return False, f"WS error: {msg[:120]}"


def _check_api_key_http(server: str, api_key: str) -> tuple[bool, str]:
    """
    Fallback: send an HTTP request with Upgrade headers and inspect the 403/101.
    The Phoenix WS endpoint responds 403 immediately for bad keys before upgrade.
    """
    import http.client
    import urllib.parse

    base = server.replace("ws://", "http://").replace("wss://", "https://")
    parsed = urllib.parse.urlparse(base)
    path = f"/socket/websocket?api_key={api_key}&protocol_version=1.0&vsn=2.0.0"

    use_ssl = parsed.scheme == "https"
    host = parsed.hostname
    port = parsed.port or (443 if use_ssl else 80)

    try:
        if use_ssl:
            conn = http.client.HTTPSConnection(host, port, timeout=5)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=5)
        conn.request(
            "GET",
            path,
            headers={
                "Host": f"{host}:{port}",
                "Upgrade": "websocket",
                "Connection": "Upgrade",
                "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                "Sec-WebSocket-Version": "13",
            },
        )
        resp = conn.getresponse()
        if resp.status == 403:
            return False, "Server returned HTTP 403 — key is invalid or revoked"
        if resp.status in (101, 200):
            return True, f"Server accepted key prefix {api_key[:6]}… (HTTP {resp.status})"
        return False, f"Unexpected HTTP {resp.status} during WS handshake"
    except Exception as e:
        return False, f"HTTP probe error: {e}"


# ---------------------------------------------------------------------------
# Check 3: MCP registration
# ---------------------------------------------------------------------------

_MCP_CANDIDATES: list[tuple[str, Path]] = [
    # (client_name, config_path)
    ("Claude Desktop (macOS)",   Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"),
    ("Claude Desktop (Linux)",   Path.home() / ".config/Claude/claude_desktop_config.json"),
    ("Claude Code (~/.claude.json)", Path.home() / ".claude.json"),
    ("Cursor",                   Path.home() / ".cursor/mcp.json"),
    ("VS Code (Insiders)",       Path.home() / ".config/Code - Insiders/User/settings.json"),
    ("VS Code",                  Path.home() / ".config/Code/User/settings.json"),
    ("Hermes config",            Path.home() / ".hermes/config.yaml"),
    ("opencode (project)",       Path("opencode.json")),
    ("opencode (.config)",       Path.home() / ".config/opencode/config.json"),
    ("project .mcp.json",        Path(".mcp.json")),
]

def _load_json_safe(path: Path) -> Optional[dict]:
    try:
        text = path.read_text(encoding="utf-8")
        # strip JS-style // comments (opencode.json uses them)
        import re
        text = re.sub(r'//.*', '', text)
        return json.loads(text)
    except Exception:
        return None


def _has_tavernbench_mcp(data: dict) -> bool:
    """Return True if any MCP server entry looks like tavernbench."""
    servers: dict = {}

    # Claude Desktop / .mcp.json / Cursor style
    if "mcpServers" in data:
        servers.update(data["mcpServers"])

    # opencode style: {"mcp": {"<name>": {...}}}
    if "mcp" in data and isinstance(data["mcp"], dict):
        servers.update(data["mcp"])

    # VS Code user settings
    if "mcp" in data and isinstance(data.get("mcp"), dict):
        servers.update(data["mcp"].get("servers", {}))

    for name, cfg in servers.items():
        name_lc = name.lower()
        if "tavern" in name_lc or "tavernbench" in name_lc:
            return True
        # check command/args for the module name
        cmd = cfg.get("command", "")
        args = cfg.get("args", [])
        full = " ".join([str(cmd)] + [str(a) for a in args]).lower()
        if "tavernbench" in full or "tavern_bench" in full:
            return True

    return False


def check_mcp_registration() -> list[tuple[str, bool, str]]:
    """
    Returns a list of (client_name, found, detail) for each detected client.
    A client is "detected" if its config file exists.
    """
    results = []
    for client_name, cfg_path in _MCP_CANDIDATES:
        if not cfg_path.exists():
            continue  # client not installed / config missing — skip silently

        data = _load_json_safe(cfg_path)
        if data is None:
            results.append((client_name, False, f"Could not parse {cfg_path}"))
            continue

        found = _has_tavernbench_mcp(data)
        detail = str(cfg_path)
        results.append((client_name, found, detail))

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="tavernbench doctor",
        description="Check TavernBench server, API key, and MCP registration.",
    )
    parser.add_argument(
        "--server",
        default=os.environ.get("TAVERNBENCH_SERVER", "ws://localhost:4100"),
        help="Server URL (default: $TAVERNBENCH_SERVER or ws://localhost:4100)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("TAVERNBENCH_API_KEY", ""),
        dest="api_key",
        help="API key (default: $TAVERNBENCH_API_KEY)",
    )
    args = parser.parse_args(argv)

    print(f"\n{BOLD}tavernbench doctor{RESET}  {args.server}\n")

    all_ok = True

    # --- Check 1: server reachable ---
    ok, detail = check_server_reachable(args.server)
    _print_check("server reachable", PASS if ok else FAIL, detail)
    if not ok:
        all_ok = False

    # --- Check 2: API key valid ---
    ok, detail = check_api_key(args.server, args.api_key or None)
    _print_check("api key valid", PASS if ok else FAIL, detail)
    if not ok:
        all_ok = False

    # --- Check 3: MCP registration ---
    mcp_results = check_mcp_registration()
    if not mcp_results:
        _print_check("MCP registration", SKIP, "No MCP-capable clients detected on this machine")
    else:
        mcp_any_ok = False
        for client_name, found, detail in mcp_results:
            status = PASS if found else WARN
            if found:
                mcp_any_ok = True
            _print_check(f"MCP: {client_name}", status, detail)
        if not mcp_any_ok:
            print(
                f"\n  {YELLOW}hint:{RESET} Add tavernbench to an MCP client config to use it as a tool.\n"
                f"  Example entry for claude_desktop_config.json:\n"
                f"    \"tavernbench\": {{\"command\": \"tavernbench-mcp\"}}"
            )

    print()
    if all_ok:
        print(f"{GREEN}All checks passed.{RESET}")
        return 0
    else:
        print(f"{RED}Some checks failed.{RESET}  Fix the issues above and re-run.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
