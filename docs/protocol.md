# TavernBench Behavior Lab protocol

## Identity and claim boundary

- Protocol: `tavernbench.behavior/v1`
- Run schema: `tavernbench-research-run/v1`
- Trace entry: `tavernbench-trace-entry/v1`
- Failure: `tavernbench-failure/v1`
- Observation: `tavernbench-observation/v1`
- Outcome: `tavernbench-outcome/v1`
- Evidence export: `tavernbench-evidence-export/v1`
- Canonical scenario: `missing_apprentice`, revision `missing-apprentice/2026-08-28`

The protocol records descriptive behavior under named conditions. It supplies no benchmark validity, comparison, ranking, leaderboard, or broad long-horizon inference.

## Access boundary

Research API requests require `Authorization: Bearer <account-owned-key>`. Never put the key in a URL, metadata, annotation, log, or export.

Bearer access matches both account owner and exact API-key ID. A second key on the same account cannot act on or retrieve another key's runs. The browser session can review all account-owned runs. Study participant/outcome mutation exists only behind the owner browser session and CSRF; no bearer study mutation route exists. Anonymous key issuance, caller-supplied result persistence, public submissions, and leaderboard routes are unavailable.

## HTTP endpoints

Public:

- `GET /health` — scenario plus migrated research-storage readiness; sanitized `503` on failure
- `GET /api/scenarios` — one validated scenario identity

Exact-key bearer:

- `GET /api/v1/research-runs`
- `POST /api/v1/research-runs`
- `POST /api/v1/research-runs/{run_id}/actions`
- `POST /api/v1/research-runs/{run_id}/annotations`
- `POST /api/v1/research-runs/{run_id}/abort`
- `GET /api/v1/research-runs/{run_id}/evidence`
- `GET /api/v1/research-runs/{run_id}/export`

## Start request

```json
{
  "scenario_id": "missing_apprentice",
  "participant_code": "builder-01",
  "episode_kind": "initial",
  "agent_metadata": {
    "agent_name": "my-agent",
    "provider": "named-provider",
    "model": "named-model",
    "model_version": "named-version",
    "client_name": "python-sdk",
    "client_version": "0.2.0",
    "config_label": "baseline",
    "tools": ["http"]
  }
}
```

Only those metadata keys are accepted. Scalar values are bounded; `tools` is a bounded string list. Unknown fields and credential-like values are rejected. Prompts, headers, tokens, and arbitrary configuration blobs are not metadata fields.

The response binds run ID, protocol, environment release/source revision, scenario schema/revision/build SHA-256, deterministic movement/combat/action-limit inputs, initial observation, and reset proof. Every run constructs private episode state from the scenario build; no shared mutable world is used.

## Actions and geometry

Supported actions: `observe`, `move`, `enter`, `speak`, `reply`, `examine`, `pickup`, `attack`, `flee`, `inventory`, `quests`.

Movement is four-directional. Interaction adjacency is Manhattan distance ≤1 and explicitly includes the same cell. Exit, NPC, dialogue, item, and enemy IDs must exist in the current episode/zone with the required type; geometry and dialogue state are enforced. Combat damage/counterattack is deterministic. Zone transitions are explicit `enter` actions; movement does not silently transition.

Examples:

```json
{"action":"move","direction":"north"}
{"action":"speak","target":"npc_barkeep"}
{"action":"reply","target":"npc_barkeep","choice":1}
{"action":"enter","target":"exit_north"}
{"action":"attack","target":"enemy_wolf"}
```

Every processed action receives an immutable request entry and result entry. Typed action failure is evidence and may leave the episode active. Terminal states are `completed`, `failed`, and `aborted`; terminal runs reject further trace writes.

## Ordered evidence

Sequence 1 is `episode_started` with initial observation/reset proof. Each action adds `action_requested` then `action_result` with receipt ID, before/after observation, state digests, typed result/failure, and current outcome. An active annotation adds `annotation`. Terminal transition adds `episode_cleanup` with final digest and clean-reset proof.

`annotation.action_sequence` is the one-based action ordinal, not trace sequence. It must reference an already persisted action. Free-text annotations may contain participant-supplied text; credential-like values are rejected, but absence of every possible secret is not claimed.

Terminal traces are sealed over ordered projections containing `sequence`, `kind`, `schema_version`, `occurred_at`, and `payload`. `tavernbench-canonical-json/v1` is compact UTF-8 JSON with recursively lexicographically sorted object keys and values restricted to strings, integers, booleans, null, arrays, and objects. SHA-256 is lowercase hexadecimal.

## Retention and study

Evidence is owner-authenticated and deleted after 45 days: the 30-day validation window plus 15 days for final analysis/export. A minute reconciliation seals missing episode processes older than the 30-second startup grace as `episode_interrupted`. Phase 1 is single-node; multi-node episode ownership is unsupported.

Study completion requires six qualified, consented, completed participant codes, each with at least two terminal `initial` episodes and one terminal `rerun`. Only then evaluate ≥4 actionable failures, ≥3 own-agent follow-ups, and ≥1 commercial commitment. If any gate is missed, stop platform investment.
