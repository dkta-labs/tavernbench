import contextlib
import hashlib
import io
import json
import os
import urllib.error
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk"))

import tavernbench.__main__ as cli
from tavernbench import Client, ConfigurationError, ProtocolError, TransportError, TypedError, verify_evidence

TEST_KEY = "tb_" + "1" * 32

class Response:
    def __init__(self, data):
        self.payload = json.dumps(data).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return None
    def read(self): return self.payload


class BehaviorLabClientTest(unittest.TestCase):
    def test_start_action_and_key_header_match_http_v1(self):
        responses = [
            Response({"run": {"id": "run-1", "status": "active", "protocol_version": "tavernbench.behavior/v1"}, "observation": {"run_status": "active"}, "reset_proof": {"shared_mutable_world": False}}),
            Response({"receipt_id": "receipt-1", "response": {"ok": True}, "trace_sequence": [2, 3]}),
        ]
        requests = []
        def open_request(request, timeout):
            requests.append(request)
            return responses.pop(0)
        with patch("urllib.request.urlopen", side_effect=open_request):
            client = Client("https://example.test", TEST_KEY)
            run = client.start_run(participant_code="builder-1", agent_metadata={"agent_name": "agent"})
            receipt = client.act(run.id, action="observe")
        self.assertEqual(run.id, "run-1")
        self.assertEqual(receipt["trace_sequence"], [2, 3])
        self.assertEqual(requests[0].full_url, "https://example.test/api/v1/research-runs")
        self.assertEqual(requests[0].headers["Authorization"], f"Bearer {TEST_KEY}")
        body = json.loads(requests[0].data)
        self.assertEqual(body["scenario_id"], "missing_apprentice")
        self.assertNotIn("api_key", json.dumps(body))

    def test_transport_failure_has_no_fallback_state(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            with self.assertRaises(TransportError):
                Client("https://example.test", TEST_KEY).start_run()

    def test_configuration_and_unsupported_actions_fail_closed(self):
        with self.assertRaises(ConfigurationError):
            Client("ws://example.test", TEST_KEY)
        with self.assertRaises(ConfigurationError):
            Client("https://example.test", "")
        with self.assertRaises(ConfigurationError):
            Client("http://example.test", TEST_KEY)
        Client("http://127.0.0.1:4100", TEST_KEY)
        Client("http://localhost:4100", TEST_KEY)
        for malformed_host in ("https://user@example.test", "https://example.test/path", "https://example.test?query=1", "https://example.test#fragment"):
            with self.assertRaises(ConfigurationError):
                Client(malformed_host, TEST_KEY)
        supplied = TEST_KEY + "\nInjected: value"
        with self.assertRaises(ConfigurationError) as rejected:
            Client("https://example.test", supplied)
        self.assertNotIn(supplied, str(rejected.exception))
        with self.assertRaises(ProtocolError):
            Client("https://example.test", TEST_KEY).act("run", action="drop")

    def test_export_seal_is_recomputed_from_canonical_json(self):
        trace = [{"id": "ignored", "sequence": 1, "kind": "episode_cleanup", "schema_version": "tavernbench-trace-entry/v1", "occurred_at": "2026-08-28T00:00:00.000000Z", "payload": {"z": 1, "a": True}}]
        projection = [{key: trace[0][key] for key in ("sequence", "kind", "schema_version", "occurred_at", "payload")}]
        digest = hashlib.sha256(json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        evidence = {"integrity": {"canonicalization": "tavernbench-canonical-json/v1", "sealed_sha256": digest}, "trace": trace}
        self.assertTrue(verify_evidence(evidence))

    def test_export_omits_key_and_forces_mode_0600(self):
        digest = hashlib.sha256(b"[]").hexdigest()
        evidence = {"run": {"id": "run-1", "status": "aborted", "protocol_version": "tavernbench.behavior/v1", "scenario": {"revision": "r", "build": "b"}}, "integrity": {"canonicalization": "tavernbench-canonical-json/v1", "status": "verified", "sealed_sha256": digest}, "trace": []}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "evidence.json"
            with patch.object(Client, "evidence", return_value=evidence):
                Client("https://example.test", TEST_KEY).export("run-1", target)
            self.assertNotIn(TEST_KEY, target.read_text())
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            target.chmod(0o644)
            with patch.object(Client, "evidence", return_value=evidence):
                Client("https://example.test", TEST_KEY).export("run-1", target)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_tampered_evidence_is_not_exported(self):
        evidence = {"run": {"protocol_version": "tavernbench.behavior/v1"}, "integrity": {"canonicalization": "tavernbench-canonical-json/v1", "status": "failed", "sealed_sha256": "0" * 64}, "trace": []}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "evidence.json"
            with patch.object(Client, "evidence", return_value=evidence):
                with self.assertRaises(ProtocolError):
                    Client("https://example.test", TEST_KEY).export("run-1", target)
            self.assertFalse(target.exists())
    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "POSIX symlink protection")
    def test_export_rejects_existing_symlink(self):
        digest = hashlib.sha256(b"[]").hexdigest()
        evidence = {"run": {"protocol_version": "tavernbench.behavior/v1"}, "integrity": {"canonicalization": "tavernbench-canonical-json/v1", "status": "verified", "sealed_sha256": digest}, "trace": []}
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.json"
            target.write_text("unchanged")
            link = Path(directory) / "evidence.json"
            link.symlink_to(target)
            with patch.object(Client, "evidence", return_value=evidence):
                with self.assertRaises(ProtocolError):
                    Client("https://example.test", TEST_KEY).export("run-1", link)
            self.assertEqual(target.read_text(), "unchanged")

    def test_versioned_http_failure_envelope_is_required(self):
        valid = {"error": {"schema_version": "tavernbench-failure/v1", "code": "authentication_failed", "category": "authentication", "message": "A valid key is required.", "retryable": False, "details": {}}}
        valid_error = urllib.error.HTTPError("https://example.test", 401, "Unauthorized", {}, io.BytesIO(json.dumps(valid).encode()))
        with patch("urllib.request.urlopen", side_effect=valid_error):
            with self.assertRaises(TypedError) as typed:
                Client("https://example.test", TEST_KEY).list_runs()
        self.assertEqual(typed.exception.code, "authentication_failed")

        malformed = {"error": {"schema_version": "wrong", "code": "authentication_failed"}}
        malformed_error = urllib.error.HTTPError("https://example.test", 401, "Unauthorized", {}, io.BytesIO(json.dumps(malformed).encode()))
        with patch("urllib.request.urlopen", side_effect=malformed_error):
            with self.assertRaises(ProtocolError):
                Client("https://example.test", TEST_KEY).list_runs()

    def test_concierge_cli_never_prints_plaintext_key(self):
        digest = hashlib.sha256(b"[]").hexdigest()
        evidence = {"run": {"id": "run-1", "status": "aborted", "protocol_version": "tavernbench.behavior/v1", "scenario": {"revision": "r", "build": "b"}}, "integrity": {"canonicalization": "tavernbench-canonical-json/v1", "status": "verified", "sealed_sha256": digest}, "trace": []}

        class FakeClient:
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def start_run(self, **_kwargs): return SimpleNamespace(id="run-1")
            def act(self, *_args, **_kwargs): return {"receipt_id": "receipt-1"}
            def abort(self, *_args): return {}
            def export(self, *_args): return evidence

        args = SimpleNamespace(participant_code="p", episode_kind="initial", config_label="baseline", agent_name="agent", export=Path("unused.json"))
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"TAVERNBENCH_API_KEY": TEST_KEY}, clear=False), patch.object(cli.Client, "from_env", return_value=FakeClient()), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(cli.concierge_main(args), 0)
        self.assertNotIn(TEST_KEY, stdout.getvalue() + stderr.getvalue())

        with patch.dict(os.environ, {"TAVERNBENCH_API_KEY": TEST_KEY}, clear=False), patch.object(cli.Client, "from_env", side_effect=ConfigurationError("invalid key")), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(cli.concierge_main(args), 1)
        self.assertNotIn(TEST_KEY, stdout.getvalue() + stderr.getvalue())


    def test_protocol_mismatch_fails_closed(self):
        response = Response({"run": {"id": "run-1", "status": "active", "protocol_version": "other"}, "observation": {}, "reset_proof": {}})
        with patch("urllib.request.urlopen", return_value=response):
            with self.assertRaises(ProtocolError):
                Client("https://example.test", TEST_KEY).start_run()

    def test_evidence_protocol_mismatch_fails_closed(self):
        evidence = {"run": {"protocol_version": "other"}, "integrity": {"status": "active_unsealed"}, "trace": []}
        with patch.object(Client, "_request", return_value=evidence):
            with self.assertRaises(ProtocolError):
                Client("https://example.test", TEST_KEY).evidence("run-1")


if __name__ == "__main__":
    unittest.main()
