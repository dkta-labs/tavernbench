"""Fail-closed TavernBench Behavior Lab HTTP v1 client."""
from __future__ import annotations

import hashlib
import json
import re
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PROTOCOL_VERSION = "tavernbench.behavior/v1"
CANONICALIZATION = "tavernbench-canonical-json/v1"
SUPPORTED_ACTIONS = frozenset({"observe", "move", "enter", "speak", "reply", "examine", "pickup", "attack", "flee", "inventory", "quests"})


class TavernBenchError(RuntimeError):
    """Base SDK failure. No SDK failure is converted to plausible run state."""


class ConfigurationError(TavernBenchError):
    pass


class TransportError(TavernBenchError):
    pass


class ProtocolError(TavernBenchError):
    pass


class TypedError(TavernBenchError):
    def __init__(self, failure: Mapping[str, Any], status: int | None = None):
        self.failure = dict(failure)
        self.code = str(self.failure.get("code", "unknown_error"))
        self.status = status
        super().__init__(f"{self.code}: {self.failure.get('message', 'request failed')}")


@dataclass(frozen=True)
class Run:
    id: str
    status: str
    observation: dict[str, Any]
    reset_proof: dict[str, Any]
    raw: dict[str, Any]


class Client:
    """One persistent logical client for account-owned Behavior Lab runs."""

    def __init__(self, host: str, api_key: str, *, timeout: float = 15.0):
        host = host.rstrip("/")
        parsed = urllib.parse.urlparse(host)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ConfigurationError("TAVERNBENCH_HOST must use http:// or https://")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ConfigurationError("TAVERNBENCH_HOST must be an origin without userinfo, path, query, or fragment")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ConfigurationError("Bearer API keys require HTTPS except on explicit loopback hosts")
        if not re.fullmatch(r"tb_[0-9a-f]{32}", api_key):
            raise ConfigurationError("a valid account-owned TavernBench API key is required")
        self.host = host
        self._api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_env(cls, *, timeout: float = 15.0) -> "Client":
        api_key = os.environ.get("TAVERNBENCH_API_KEY", "")
        host = os.environ.get("TAVERNBENCH_HOST", "https://tavernbench.dkta.dev")
        return cls(host, api_key, timeout=timeout)

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        """The stdlib transport holds no background connection or process."""

    def start_run(
        self,
        *,
        participant_code: str | None = None,
        episode_kind: str = "initial",
        agent_metadata: Mapping[str, Any] | None = None,
    ) -> Run:
        body: dict[str, Any] = {
            "scenario_id": "missing_apprentice",
            "episode_kind": episode_kind,
            "agent_metadata": dict(agent_metadata or {}),
        }
        if participant_code is not None:
            body["participant_code"] = participant_code
        data = self._request("POST", "/api/v1/research-runs", body)
        run = _mapping(data.get("run"), "start response run")
        observation = _mapping(data.get("observation"), "start response observation")
        reset_proof = _mapping(data.get("reset_proof"), "start response reset_proof")
        if run.get("protocol_version") != PROTOCOL_VERSION:
            raise ProtocolError("server run protocol_version does not match the SDK")
        if not isinstance(run.get("id"), str) or not isinstance(run.get("status"), str):
            raise ProtocolError("start response is missing run identity or status")
        return Run(run["id"], run["status"], observation, reset_proof, data)

    def act(
        self,
        run_id: str,
        *,
        action: str,
        direction: str | None = None,
        target: str | None = None,
        choice: int | None = None,
    ) -> dict[str, Any]:
        if action not in SUPPORTED_ACTIONS:
            raise ProtocolError(f"unsupported action {action!r}")
        body: dict[str, Any] = {"action": action}
        if direction is not None:
            body["direction"] = direction
        if target is not None:
            body["target"] = target
        if choice is not None:
            body["choice"] = choice
        return self._request("POST", f"/api/v1/research-runs/{run_id}/actions", body)

    def annotate(self, run_id: str, *, label: str, note: str, action_sequence: int) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/research-runs/{run_id}/annotations", {"label": label, "note": note, "action_sequence": action_sequence})

    def abort(self, run_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/research-runs/{run_id}/abort", {})

    def evidence(self, run_id: str) -> dict[str, Any]:
        evidence = self._request("GET", f"/api/v1/research-runs/{run_id}/evidence")
        run = _mapping(evidence.get("run"), "evidence run")
        integrity = _mapping(evidence.get("integrity"), "evidence integrity")
        trace = evidence.get("trace")
        if run.get("protocol_version") != PROTOCOL_VERSION:
            raise ProtocolError("evidence protocol_version does not match the SDK")
        if not isinstance(trace, list) or not all(isinstance(entry, dict) for entry in trace):
            raise ProtocolError("evidence trace must be an array of objects")
        if not isinstance(integrity.get("status"), str):
            raise ProtocolError("evidence integrity status is missing")
        return evidence

    def export(self, run_id: str, path: str | os.PathLike[str]) -> dict[str, Any]:
        evidence = self.evidence(run_id)
        if not verify_evidence(evidence):
            raise ProtocolError("evidence seal verification failed")
        target = Path(path)
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if nofollow == 0 and target.is_symlink():
            raise ProtocolError("evidence export path must not be a symlink")
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | nofollow, 0o600)
        except OSError as error:
            raise ProtocolError("evidence export path could not be opened safely") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
        return evidence

    def list_runs(self) -> list[dict[str, Any]]:
        runs = self._request("GET", "/api/v1/research-runs").get("runs")
        if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
            raise ProtocolError("run list response is invalid")
        return runs

    def list_scenarios(self) -> list[dict[str, Any]]:
        value = self._request_value("GET", "/api/scenarios")
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise ProtocolError("Phase 1 requires exactly one scenario object")
        scenario = value[0]
        if scenario.get("id") != "missing_apprentice" or scenario.get("schema_version") != "tavernbench-scenario/v1" or scenario.get("protocol_version") != PROTOCOL_VERSION:
            raise ProtocolError("scenario inventory does not match the Phase 1 contract")
        return value

    def _request(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
        value = self._request_value(method, path, body)
        if not isinstance(value, dict):
            raise ProtocolError("server returned a non-object JSON response")
        return value

    def _request_value(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.host + path,
            data=payload,
            method=method,
            headers={"Accept": "application/json", "Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return _decode_json_value(response.read())
        except urllib.error.HTTPError as error:
            try:
                data = _decode_json_value(error.read())
            except ProtocolError as invalid:
                raise ProtocolError("HTTP failure body is not valid JSON") from invalid
            if not isinstance(data, dict) or "error" not in data:
                raise TransportError(f"HTTP {error.code} without a typed TavernBench failure") from error
            failure = _validated_failure(data["error"])
            raise TypedError(failure, error.code) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise TransportError(f"TavernBench request failed: {type(error).__name__}") from error


def canonical_trace_sha256(evidence: Mapping[str, Any]) -> str:
    integrity = _mapping(evidence.get("integrity"), "evidence integrity")
    if integrity.get("canonicalization") != CANONICALIZATION:
        raise ProtocolError("unsupported evidence canonicalization")
    trace = evidence.get("trace")
    if not isinstance(trace, list):
        raise ProtocolError("evidence trace must be an array")
    projection = []
    for entry in trace:
        if not isinstance(entry, dict):
            raise ProtocolError("evidence trace entry must be an object")
        try:
            projection.append({key: entry[key] for key in ("sequence", "kind", "schema_version", "occurred_at", "payload")})
        except KeyError as error:
            raise ProtocolError("evidence trace entry is missing a sealed field") from error
    encoded = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_evidence(evidence: Mapping[str, Any]) -> bool:
    integrity = _mapping(evidence.get("integrity"), "evidence integrity")
    sealed = integrity.get("sealed_sha256")
    return isinstance(sealed, str) and sealed == canonical_trace_sha256(evidence)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError(f"{label} must be an object")
    return value


def _validated_failure(value: Any) -> dict[str, Any]:
    failure = _mapping(value, "failure envelope")
    if failure.get("schema_version") != "tavernbench-failure/v1":
        raise ProtocolError("failure envelope has an unsupported schema_version")
    if not all(isinstance(failure.get(field), str) and failure[field] for field in ("code", "category", "message")):
        raise ProtocolError("failure envelope is missing typed string fields")
    if not isinstance(failure.get("retryable"), bool) or not isinstance(failure.get("details"), dict):
        raise ProtocolError("failure envelope retryable/details types are invalid")
    return failure


def _decode_json_value(payload: bytes) -> Any:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("server returned invalid JSON") from error
