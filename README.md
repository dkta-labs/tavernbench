# TavernBench Behavior Lab

TavernBench is a synthetic agent-behavior research lab for diagnosing why an agent failed in a multi-step interactive task. Phase 1 supports descriptive evidence under one named scenario/configuration only.

It is **not** a rigorous benchmark, model ranking, public leaderboard, public submission service, broad long-horizon proof, or production-adoption claim.

## Supported Phase 1 path

- Scenario: `missing_apprentice`
- Scenario schema/revision: `tavernbench-scenario/v1` / `missing-apprentice/2026-08-28`
- Protocol: `tavernbench.behavior/v1` over account-owned HTTP
- Auth: account-owned browser session and a dedicated account API key; OAuth is not required and broad activation is outside Phase 1
- Integration: Python `Client` and the MCP tools in `mcp/server.py`
- Evidence: ordered observation → action request → receipt/outcome entries, annotations, provenance, cleanup proof, and a canonical JSON SHA-256 seal
- Privacy: key-scoped bearer access; account-owner browser review; no anonymous persistence; 45-day retention (30-day study plus 15-day analysis/export buffer)

## Concierge quickstart

```sh
./install.sh
export TAVERNBENCH_API_KEY="$(python3 -c 'import getpass; print(getpass.getpass("TavernBench API key: "))')"
export TAVERNBENCH_HOST=https://tavernbench.dkta.dev
"$HOME/.local/bin/tavernbench" concierge \
  --participant-code builder-01 \
  --config-label baseline \
  --export tavernbench-evidence.json
```

## MCP configuration

Install the same Client-backed path with `./install.sh --mcp`, then configure:

- command: `$HOME/.tavernbench/.venv/bin/python`
- args: `$HOME/.tavernbench/mcp/server.py`
- transport: `stdio`

The command starts a clean episode, records one `observe` action, seals the handshake run as `aborted`, retrieves the trace, independently verifies its seal, writes the export, and prints a credential-safe JSON summary. It never prints the API key.

For an own-agent integration:

```python
from tavernbench import Client

with Client.from_env() as lab:
    run = lab.start_run(
        participant_code="builder-01",
        agent_metadata={
            "agent_name": "my-agent",
            "client_name": "python-sdk",
            "client_version": "0.2.0",
            "config_label": "baseline",
        },
    )
    observation = run.observation
    receipt = lab.act(run.id, action="observe")
    lab.abort(run.id)
```

Transport, authentication, and server failures raise typed SDK errors. There is no fallback observation or fallback success.

## Research evidence

The owner-authenticated site exposes **Research Runs** with timeline, decisions, typed failures, outcome, annotations, protocol/environment/scenario provenance, retention, export, and trace integrity. `annotation.action_sequence` is a one-based action ordinal, not a trace sequence, and must reference an existing action.

## Validation runway

The operator workflow is six qualified, consented builders × three isolated episodes each: at least two `initial` episodes and one `rerun` per builder. Proceed only if:

- at least 4/6 identify an actionable failure;
- at least 3/6 commit their own agent to a follow-up;
- at least 1/6 pays or makes an equivalent concrete commercial commitment.

If any gate is missed after valid collection, stop platform investment and retain the research/portfolio artifact. No participants or results are preloaded.

## Limitations

- one canonical scenario and a concierge validation study;
- descriptive behavior evidence only; no comparative validity or ranking;
- no public submissions, leaderboard, anonymous persistence, user-authored scenarios, or unsupported commands;
- API keys can access only runs created by the same exact key; the browser session can review all runs owned by the account;
- study outcome mutation is browser-session + CSRF owner authority only, never bearer-key authority;
- Phase 1 episode ownership is single-node; multi-node execution is unsupported;
- prompts are not captured automatically; free-text annotations may contain participant-supplied text; credential-like values are rejected and credentials are not intentionally collected.

See [`docs/protocol.md`](docs/protocol.md) for the exact contract.
