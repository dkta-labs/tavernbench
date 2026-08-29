"""TavernBench Behavior Lab MCP tools over the supported HTTP v1 contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SDK = str(_REPO / "sdk")
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)

from mcp.server.fastmcp import FastMCP
from tavernbench.client import Client, TavernBenchError

mcp = FastMCP("tavernbench-behavior-lab")


def _client() -> Client:
    return Client.from_env()


def _result(callable_) -> str:
    try:
        return json.dumps(callable_(), sort_keys=True)
    except TavernBenchError as error:
        return json.dumps({"error": {"type": type(error).__name__, "message": str(error)}})


@mcp.tool()
def tavernbench_list_scenarios() -> str:
    """Return the exact validated Phase 1 scenario identity or a typed client error."""
    return _result(lambda: _client().list_scenarios())


@mcp.tool()
def tavernbench_start_run(participant_code: str = "", episode_kind: str = "initial", config_label: str = "baseline", agent_name: str = "mcp-agent") -> str:
    """Start the canonical clean-reset research episode with credential-safe metadata."""
    return _result(lambda: _client().start_run(participant_code=participant_code or None, episode_kind=episode_kind, agent_metadata={"agent_name": agent_name, "client_name": "mcp", "client_version": "0.2.0", "config_label": config_label, "tools": ["tavernbench-http-v1"]}).raw)


@mcp.tool()
def tavernbench_act(run_id: str, action: str, target: str = "", direction: str = "", choice: int | None = None) -> str:
    """Apply one supported typed action to a server-held run; no local fallback state."""
    return _result(lambda: _client().act(run_id, action=action, target=target or None, direction=direction or None, choice=choice))


@mcp.tool()
def tavernbench_observe(run_id: str) -> str:
    """Record and return an observe action for an existing research run."""
    return _result(lambda: _client().act(run_id, action="observe"))


@mcp.tool()
def tavernbench_annotate(run_id: str, label: str, note: str, action_sequence: int) -> str:
    """Attach a credential-safe note to an existing one-based action ordinal."""
    return _result(lambda: _client().annotate(run_id, label=label, note=note, action_sequence=action_sequence))


@mcp.tool()
def tavernbench_evidence(run_id: str) -> str:
    """Retrieve owner-key-scoped ordered trace evidence."""
    return _result(lambda: _client().evidence(run_id))


@mcp.tool()
def tavernbench_abort(run_id: str) -> str:
    """Seal an unfinished episode as aborted and record cleanup proof."""
    return _result(lambda: _client().abort(run_id))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
