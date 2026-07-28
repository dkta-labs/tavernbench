"""
Tests for tavernbench doctor.

Run: pytest tests/test_doctor.py -v
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tavernbench.doctor import (
    check_server_reachable,
    check_api_key,
    check_mcp_registration,
    _has_tavernbench_mcp,
    _MCP_CANDIDATES,
)


# ---------------------------------------------------------------------------
# check_server_reachable
# ---------------------------------------------------------------------------

class TestCheckServerReachable:
    def test_pass_on_200(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            mock_resp.read.return_value = b'{"status":"ok"}'
            ok, detail = check_server_reachable("ws://localhost:4100")
        assert ok
        assert "200" in detail

    def test_fail_on_connection_refused(self):
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            ok, detail = check_server_reachable("ws://localhost:4100")
        assert not ok
        assert "Cannot reach" in detail

    def test_converts_ws_to_http(self):
        calls = []

        class FakeResp:
            status = 200
            def read(self): return b'ok'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout=None):
            calls.append(req.full_url)
            return FakeResp()

        with patch("urllib.request.urlopen", fake_urlopen):
            check_server_reachable("ws://localhost:4100")

        assert calls[0].startswith("http://")

    def test_converts_wss_to_https(self):
        calls = []

        class FakeResp:
            status = 200
            def read(self): return b'ok'
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout=None):
            calls.append(req.full_url)
            return FakeResp()

        with patch("urllib.request.urlopen", fake_urlopen):
            check_server_reachable("wss://tavernbench.dkta.dev")

        assert calls[0].startswith("https://")


# ---------------------------------------------------------------------------
# check_api_key
# ---------------------------------------------------------------------------

class TestCheckApiKey:
    def test_no_key_returns_fail(self):
        ok, detail = check_api_key("ws://localhost:4100", None)
        assert not ok
        assert "API key" in detail

    def test_403_detected(self):
        import websockets.sync.client as wssync
        with patch("websockets.sync.client.connect", side_effect=Exception("server rejected WebSocket connection: HTTP 403")):
            ok, detail = check_api_key("ws://localhost:4100", "tb-badkey")
        assert not ok
        assert "403" in detail

    def test_connection_refused(self):
        with patch("websockets.sync.client.connect", side_effect=Exception("Connection refused")):
            ok, detail = check_api_key("ws://localhost:4100", "tb-somekey")
        assert not ok
        assert "refused" in detail.lower()

    def test_successful_connect(self):
        mock_ws = MagicMock()
        mock_ws.__enter__ = lambda s: s
        mock_ws.__exit__ = MagicMock(return_value=False)
        with patch("websockets.sync.client.connect", return_value=mock_ws):
            ok, detail = check_api_key("ws://localhost:4100", "tb-validkey")
        assert ok
        assert "tb-val" in detail  # first 6 chars of key


# ---------------------------------------------------------------------------
# _has_tavernbench_mcp
# ---------------------------------------------------------------------------

class TestHasTavernbenchMcp:
    def test_claude_desktop_style(self):
        data = {"mcpServers": {"tavernbench": {"command": "tavernbench-mcp"}}}
        assert _has_tavernbench_mcp(data)

    def test_opencode_style(self):
        data = {"mcp": {"tavernbench": {"type": "local", "command": ["tavernbench-mcp"]}}}
        assert _has_tavernbench_mcp(data)

    def test_name_partial_match(self):
        data = {"mcpServers": {"my-tavernbench-server": {"command": "something"}}}
        assert _has_tavernbench_mcp(data)

    def test_command_match(self):
        data = {"mcpServers": {"game": {"command": "tavernbench-mcp", "args": []}}}
        assert _has_tavernbench_mcp(data)

    def test_empty_servers(self):
        data = {"mcpServers": {}}
        assert not _has_tavernbench_mcp(data)

    def test_no_mcp_key(self):
        data = {"something": "else"}
        assert not _has_tavernbench_mcp(data)

    def test_unrelated_server(self):
        data = {"mcpServers": {"github": {"command": "github-mcp"}}}
        assert not _has_tavernbench_mcp(data)


# ---------------------------------------------------------------------------
# check_mcp_registration
# ---------------------------------------------------------------------------

class TestCheckMcpRegistration:
    def test_no_clients_returns_empty(self):
        # Patch all candidates to non-existent paths
        fake_candidates = [
            ("Fake Client", Path("/nonexistent/path/config.json")),
        ]
        with patch("tavernbench.doctor._MCP_CANDIDATES", fake_candidates):
            results = check_mcp_registration()
        assert results == []

    def test_detects_registered(self, tmp_path):
        cfg = tmp_path / "claude_desktop_config.json"
        cfg.write_text(json.dumps({
            "mcpServers": {"tavernbench": {"command": "tavernbench-mcp"}}
        }))
        fake_candidates = [("Claude Desktop (test)", cfg)]
        with patch("tavernbench.doctor._MCP_CANDIDATES", fake_candidates):
            results = check_mcp_registration()
        assert len(results) == 1
        client, found, path_str = results[0]
        assert found
        assert client == "Claude Desktop (test)"

    def test_detects_not_registered(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"mcpServers": {"github": {"command": "gh-mcp"}}}))
        fake_candidates = [("Test Client", cfg)]
        with patch("tavernbench.doctor._MCP_CANDIDATES", fake_candidates):
            results = check_mcp_registration()
        assert len(results) == 1
        _, found, _ = results[0]
        assert not found

    def test_skips_missing_files(self, tmp_path):
        fake_candidates = [
            ("Missing Client", tmp_path / "doesnotexist.json"),
        ]
        with patch("tavernbench.doctor._MCP_CANDIDATES", fake_candidates):
            results = check_mcp_registration()
        assert results == []

    def test_handles_unparseable_json(self, tmp_path):
        cfg = tmp_path / "bad.json"
        cfg.write_text("{this is not valid json")
        fake_candidates = [("Bad Config Client", cfg)]
        with patch("tavernbench.doctor._MCP_CANDIDATES", fake_candidates):
            results = check_mcp_registration()
        assert len(results) == 1
        _, found, detail = results[0]
        assert not found
        assert "Could not parse" in detail
