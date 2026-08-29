import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FastMCP:
    def __init__(self, name): self.name = name
    def tool(self): return lambda function: function
    def run(self, **_kwargs): pass


mcp_module = types.ModuleType("mcp")
mcp_server_module = types.ModuleType("mcp.server")
mcp_fast_module = types.ModuleType("mcp.server.fastmcp")
mcp_fast_module.FastMCP = FastMCP
sys.modules.update({"mcp": mcp_module, "mcp.server": mcp_server_module, "mcp.server.fastmcp": mcp_fast_module})

path = Path(__file__).resolve().parents[1] / "mcp" / "server.py"
spec = importlib.util.spec_from_file_location("tavernbench_mcp_server", path)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class FakeRun:
    raw = {"run": {"id": "run-1"}, "observation": {"run_status": "active"}}


class FakeClient:
    def __init__(self): self.calls = []
    def start_run(self, **kwargs): self.calls.append(("start", kwargs)); return FakeRun()
    def act(self, run_id, **kwargs): self.calls.append(("act", run_id, kwargs)); return {"receipt_id": "r", "response": {"ok": True}}
    def annotate(self, run_id, **kwargs): self.calls.append(("annotate", run_id, kwargs)); return {"annotation_id": "a"}
    def evidence(self, run_id): self.calls.append(("evidence", run_id)); return {"run": {"id": run_id}}
    def abort(self, run_id): self.calls.append(("abort", run_id)); return {"outcome": {"status": "aborted"}}


class MCPContractTest(unittest.TestCase):
    def setUp(self): self.client = FakeClient(); self.patcher = patch.object(server, "_client", return_value=self.client); self.patcher.start()
    def tearDown(self): self.patcher.stop()

    def test_start_uses_canonical_server_run_without_local_registry(self):
        result = json.loads(server.tavernbench_start_run("builder-1", "rerun", "changed", "agent"))
        self.assertEqual(result["run"]["id"], "run-1")
        self.assertFalse(hasattr(server, "RUN_REGISTRY"))
        self.assertEqual(self.client.calls[0][1]["episode_kind"], "rerun")

    def test_exact_supported_tools_share_server_run_id(self):
        self.assertTrue(json.loads(server.tavernbench_act("run-1", "move", direction="north"))["response"]["ok"])
        json.loads(server.tavernbench_observe("run-1"))
        json.loads(server.tavernbench_annotate("run-1", "planning", "missed exit", 1))
        json.loads(server.tavernbench_evidence("run-1"))
        json.loads(server.tavernbench_abort("run-1"))
        self.assertEqual([call[0] for call in self.client.calls], ["act", "act", "annotate", "evidence", "abort"])

    def test_client_failure_is_returned_as_error_not_fallback_success(self):
        with patch.object(server, "_client", side_effect=server.TavernBenchError("offline")):
            result = json.loads(server.tavernbench_observe("run-1"))
        self.assertIn("error", result)
        self.assertNotIn("observation", result)


if __name__ == "__main__":
    unittest.main()
