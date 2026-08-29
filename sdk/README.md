# TavernBench Python SDK 0.2.0

The SDK implements the single supported `tavernbench.behavior/v1` account-owned HTTP path. It does not implement `Session`, ranked runs, leaderboard submission, reconnect-per-action WebSockets, fallback observations, or fallback success.

## Install and concierge check

```sh
python -m pip install ./sdk
export TAVERNBENCH_API_KEY="$(python3 -c 'import getpass; print(getpass.getpass("TavernBench API key: "))')"
export TAVERNBENCH_HOST=https://tavernbench.dkta.dev
python -m tavernbench concierge \
  --participant-code builder-01 \
  --config-label baseline \
  --export tavernbench-evidence.json
```

## MCP configuration

From the repository root, run `./install.sh --mcp`, then configure command `$HOME/.tavernbench/.venv/bin/python`, args `$HOME/.tavernbench/mcp/server.py`, and transport `stdio`. The MCP tools call this same SDK client; they keep no fallback run registry.

The API key is used only in the Authorization header and is never added to metadata, output, or the evidence export.

## Client

```python
from tavernbench import Client

with Client.from_env() as lab:
    run = lab.start_run(
        participant_code="builder-01",
        episode_kind="initial",
        agent_metadata={
            "agent_name": "my-agent",
            "client_name": "python-sdk",
            "client_version": "0.2.0",
            "config_label": "baseline",
        },
    )
    receipt = lab.act(run.id, action="observe")
    lab.annotate(run.id, label="observation_use", note="Agent did not inspect the visible exit.", action_sequence=1)
    lab.abort(run.id)
    evidence = lab.export(run.id, "evidence.json")
```

Allowed actions are `observe`, `move`, `enter`, `speak`, `reply`, `examine`, `pickup`, `attack`, `flee`, `inventory`, and `quests`. Required parameters are enforced locally and server-side. `annotation.action_sequence` means one-based action ordinal.

`TypedError` carries the server `tavernbench-failure/v1` object. `TransportError` means no truthful server result was received. Neither becomes plausible game state.

## Evidence seal

`verify_evidence(evidence)` recomputes the `tavernbench-canonical-json/v1` SHA-256 seal from exported ordered entries: UTF-8 JSON, recursively lexicographically sorted keys, compact separators, and strings/integers/booleans/null/arrays/objects only.

Bearer access is exact-key scoped. Study outcome mutation is not available to the SDK/MCP; it requires owner browser session + CSRF. Phase 1 is single-node and retains evidence for 45 days.
