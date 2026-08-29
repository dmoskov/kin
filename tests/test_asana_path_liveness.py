"""Tests for the Asana auth-path liveness diagnostic.

Verifies classification logic, individual probe wrappers, and the
check_liveness orchestrator — all against mocked HTTP responses.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from asana_path_liveness import (
    READ_ONLY_PROBES,
    LivenessReport,
    ProbeResult,
    check_liveness,
    probe_tasks_read,
    probe_whoami,
)

# ---------------------------------------------------------------------------
# ProbeResult basics
# ---------------------------------------------------------------------------


class TestProbeResult:
    def test_alive_probe(self):
        r = ProbeResult(path="/users/me", alive=True, status_code=200, latency_ms=42.0)
        assert r.alive
        assert r.error is None

    def test_dead_probe(self):
        r = ProbeResult(path="/users/me", alive=False, status_code=401, error="HTTP 401")
        assert not r.alive


# ---------------------------------------------------------------------------
# LivenessReport.classify
# ---------------------------------------------------------------------------


class TestClassify:
    def test_empty_report(self):
        report = LivenessReport()
        assert report.classify() == "unknown"

    def test_all_alive(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=True, status_code=200),
                ProbeResult(path="/b", alive=True, status_code=200),
            ]
        )
        assert report.classify() == "healthy"

    def test_all_401(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=False, status_code=401),
                ProbeResult(path="/b", alive=False, status_code=401),
            ]
        )
        assert report.classify() == "credential_death"

    def test_all_403(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=False, status_code=403),
                ProbeResult(path="/b", alive=False, status_code=403),
            ]
        )
        assert report.classify() == "credential_death"

    def test_mixed_auth_failures(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=False, status_code=401),
                ProbeResult(path="/b", alive=False, status_code=403),
            ]
        )
        assert report.classify() == "credential_death"

    def test_partial_failure(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=True, status_code=200),
                ProbeResult(path="/b", alive=False, status_code=401),
            ]
        )
        assert report.classify() == "partial_failure"

    def test_network_error(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=False, status_code=None, error="ConnectionError"),
                ProbeResult(path="/b", alive=False, status_code=None, error="Timeout"),
            ]
        )
        assert report.classify() == "network_error"

    def test_single_alive(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=True, status_code=200),
            ]
        )
        assert report.classify() == "healthy"

    def test_single_dead(self):
        report = LivenessReport(
            results=[
                ProbeResult(path="/a", alive=False, status_code=500),
            ]
        )
        assert report.classify() == "credential_death"


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------


def test_report_to_dict():
    report = LivenessReport(
        results=[ProbeResult(path="/a", alive=True, status_code=200)],
        diagnosis="healthy",
    )
    d = report.to_dict()
    assert d["diagnosis"] == "healthy"
    assert len(d["results"]) == 1
    assert d["results"][0]["path"] == "/a"
    assert d["results"][0]["alive"] is True


# ---------------------------------------------------------------------------
# Individual probes (mock HTTP)
# ---------------------------------------------------------------------------


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    return resp


class TestProbeWhoami:
    @patch("asana_path_liveness.requests.request")
    def test_success(self, mock_req):
        mock_req.return_value = _mock_response(200, {"data": {"gid": "123"}})
        result = probe_whoami("test-token")
        assert result.alive
        assert result.status_code == 200
        assert result.latency_ms is not None

    @patch("asana_path_liveness.requests.request")
    def test_unauthorized(self, mock_req):
        mock_req.return_value = _mock_response(401)
        result = probe_whoami("bad-token")
        assert not result.alive
        assert result.status_code == 401


class TestProbeTasksRead:
    @patch("asana_path_liveness.requests.request")
    def test_success(self, mock_req):
        mock_req.return_value = _mock_response(200, {"data": []})
        result = probe_tasks_read("test-token")
        assert result.alive
        assert result.status_code == 200

    @patch("asana_path_liveness.requests.request")
    def test_forbidden(self, mock_req):
        mock_req.return_value = _mock_response(403)
        result = probe_tasks_read("test-token")
        assert not result.alive
        assert result.status_code == 403


# ---------------------------------------------------------------------------
# check_liveness orchestrator
# ---------------------------------------------------------------------------


class TestCheckLiveness:
    @patch("asana_path_liveness.requests.request")
    def test_defaults_to_read_only_probes(self, mock_req):
        mock_req.return_value = _mock_response(200)
        report = check_liveness("test-token")
        probe_paths = {r.path for r in report.results}
        assert len(probe_paths) == len(READ_ONLY_PROBES)
        assert report.diagnosis == "healthy"

    @patch("asana_path_liveness.requests.request")
    def test_all_401_classified_as_credential_death(self, mock_req):
        mock_req.return_value = _mock_response(401)
        report = check_liveness("bad-token", paths=["whoami", "tasks"])
        assert report.diagnosis == "credential_death"
        assert all(not r.alive for r in report.results)

    @patch("asana_path_liveness.requests.request")
    def test_partial_failure_when_one_path_down(self, mock_req):
        def side_effect(method, url, **kwargs):
            if "users/me" in url:
                return _mock_response(200)
            return _mock_response(401)

        mock_req.side_effect = side_effect
        report = check_liveness("token", paths=["whoami", "tasks"])
        assert report.diagnosis == "partial_failure"

    def test_unknown_probe_name(self):
        report = check_liveness("token", paths=["nonexistent"])
        assert len(report.results) == 1
        assert not report.results[0].alive
        assert "unknown probe" in report.results[0].error

    @patch("asana_path_liveness.requests.request")
    @patch("asana_path_liveness._resolve_probe_task_gid", return_value="999")
    def test_story_probe_with_resolved_task_gid(self, mock_resolve, mock_req):
        mock_req.return_value = _mock_response(200)
        report = check_liveness("token", paths=["stories"])
        assert report.results[0].alive
        mock_resolve.assert_called_once()

    @patch("asana_path_liveness._resolve_probe_task_gid", return_value=None)
    def test_story_probe_without_task_gid_fails_gracefully(self, mock_resolve):
        report = check_liveness("token", paths=["stories"])
        assert not report.results[0].alive
        assert "no task_gid" in report.results[0].error


# ---------------------------------------------------------------------------
# Connection/timeout error handling
# ---------------------------------------------------------------------------


class TestConnectionErrors:
    @patch("asana_path_liveness.requests.request")
    def test_connection_error(self, mock_req):
        import requests as req_lib

        mock_req.side_effect = req_lib.ConnectionError("DNS failed")
        result = probe_whoami("token")
        assert not result.alive
        assert result.status_code is None
        assert "ConnectionError" in result.error

    @patch("asana_path_liveness.requests.request")
    def test_timeout_error(self, mock_req):
        import requests as req_lib

        mock_req.side_effect = req_lib.Timeout("timed out")
        result = probe_whoami("token", timeout=5)
        assert not result.alive
        assert "Timeout" in result.error
