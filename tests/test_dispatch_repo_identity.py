"""Integration test: end-to-end misdispatch prevention.

Simulates the exact failure scenario from the bug report: a code-quality
scanner scans a non-scaffold repo (stub), emits a task targeting a file in
that repo, and the dispatch layer is invoked.  Verifies:

  1. The task payload contains ``source_repo``.
  2. The executor is never called for mismatched repos.
  3. A warning/log entry is produced.

Also covers the positive path: a task with ``source_repo`` matching the
executor's authoritative repo is dispatched normally.

See parent bug: Dispatch layer lacks repo-identity tagging — 4th cross-project
misdispatch (eia_match).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from executor_registry import (
    EXECUTOR_CAPABILITIES,
    is_executor_authoritative,
)
from task_dispatcher import dispatch_task, get_capable_repos

# ── Helpers ─────────────────────────────────────────────────────────────


def _stub_scan_emit(source_repo: str | None, file_path: str, gid: str = "999") -> dict:
    """Simulate what internal_scanner._scan_code_quality would emit.

    After subtask 2, every InternalInsight carries source_repo.  This stub
    produces the task dict that would reach the dispatch layer after the
    insight → proposal → Asana-task → executor pipeline.
    """
    task: dict = {
        "gid": gid,
        "file_path": file_path,
        "evidence": {"file": file_path},
    }
    if source_repo is not None:
        task["source_repo"] = source_repo
    return task


# ── Bug-report scenario: analysis repo → scaffold executor ─────────────
# This is the exact misdispatch class from the bug report (4th instance).

BUG_REPORT_CASES = [
    ("analysis-repo", "analysis/build_stocks.py", "1217713196599997"),
    ("analysis-repo", "analysis/hormuz_round2.py", "prior-1"),
    ("analysis-repo", "analysis/implied_probability.py", "prior-2"),
    ("analysis-repo", "analysis/price_supply_curve.py", "prior-3"),
]


class TestMisdispatchPrevention:
    """End-to-end: scanner emits task for wrong repo → executor never runs."""

    @pytest.mark.parametrize("source_repo,file_path,gid", BUG_REPORT_CASES)
    def test_analysis_task_blocked_from_scaffold_executor(
        self, source_repo, file_path, gid, caplog
    ):
        """Reproduce the exact bug-report scenario: a task from analysis-repo
        targets a file that doesn't exist in claude-code-scaffold."""
        executor = MagicMock(return_value="should-never-run")
        task = _stub_scan_emit(source_repo, file_path, gid)

        assert "source_repo" in task

        with caplog.at_level(logging.WARNING):
            result = dispatch_task(task, "claude-code-scaffold", executor)

        assert result is None, "Mismatched task must be dropped"
        executor.assert_not_called()
        assert "misdispatch" in caplog.text
        assert source_repo in caplog.text

    @pytest.mark.parametrize("source_repo,file_path,gid", BUG_REPORT_CASES)
    def test_analysis_task_blocked_from_family_tree_executor(
        self, source_repo, file_path, gid, caplog
    ):
        """analysis-repo tasks should also not reach the family-tree executor."""
        executor = MagicMock()
        task = _stub_scan_emit(source_repo, file_path, gid)

        with caplog.at_level(logging.WARNING):
            result = dispatch_task(task, "family-tree", executor)

        assert result is None
        executor.assert_not_called()

    def test_registry_confirms_scaffold_cannot_handle_analysis(self):
        """The executor registry must agree that scaffold can't handle
        analysis-repo — this is the root-cause check."""
        assert not is_executor_authoritative("claude-code-scaffold", "analysis-repo")

    def test_registry_confirms_no_executor_for_analysis(self):
        """No registered executor should claim analysis-repo."""
        for cap in EXECUTOR_CAPABILITIES.values():
            assert not cap.can_handle("analysis-repo"), (
                f"Executor {cap.executor_id} unexpectedly claims analysis-repo"
            )


# ── Missing source_repo (legacy / unpatched scanner output) ────────────


class TestMissingSoureRepo:
    """Tasks emitted without source_repo (before subtask 2 fix) must be
    blocked unconditionally — this is the safety net."""

    def test_no_source_repo_drops_from_scaffold(self, caplog):
        executor = MagicMock()
        task = _stub_scan_emit(None, "analysis/build_stocks.py", "no-repo-1")

        assert "source_repo" not in task

        with caplog.at_level(logging.WARNING):
            result = dispatch_task(task, "claude-code-scaffold", executor)

        assert result is None
        executor.assert_not_called()
        assert "no source_repo" in caplog.text

    def test_no_source_repo_drops_from_family_tree(self, caplog):
        executor = MagicMock()
        task = _stub_scan_emit(None, "some/file.py", "no-repo-2")

        with caplog.at_level(logging.WARNING):
            result = dispatch_task(task, "family-tree", executor)

        assert result is None
        executor.assert_not_called()


# ── Positive path: correctly-tagged task dispatched normally ────────────


class TestPositivePath:
    """When source_repo matches the executor, the task MUST be dispatched."""

    def test_scaffold_task_to_scaffold_executor(self):
        executor = MagicMock(return_value="executed-ok")
        task = _stub_scan_emit("claude-code-scaffold", "scripts/analyze_modules.py")

        result = dispatch_task(task, "claude-code-scaffold", executor)

        assert result == "executed-ok"
        executor.assert_called_once_with(task)

    def test_family_tree_task_to_family_tree_executor(self):
        executor = MagicMock(return_value="ft-ok")
        task = _stub_scan_emit("family-tree", "src/models/person.py")

        result = dispatch_task(task, "family-tree", executor)

        assert result == "ft-ok"
        executor.assert_called_once_with(task)

    def test_kin_alias_to_family_tree_executor(self):
        """'kin' is an alias for family-tree in the dispatcher's capabilities."""
        executor = MagicMock(return_value="kin-ok")
        task = _stub_scan_emit("kin", "src/database/models.py")

        result = dispatch_task(task, "family-tree", executor)

        assert result == "kin-ok"
        executor.assert_called_once_with(task)

    def test_positive_path_no_warnings(self, caplog):
        """A correctly-matched dispatch must produce no warnings."""
        executor = MagicMock(return_value="ok")
        task = _stub_scan_emit("claude-code-scaffold", "scripts/task_dispatcher.py")

        with caplog.at_level(logging.WARNING):
            dispatch_task(task, "claude-code-scaffold", executor)

        assert "misdispatch" not in caplog.text


# ── Cross-executor misdispatch matrix ──────────────────────────────────
# Verify every registered executor rejects repos it doesn't own.


class TestCrossExecutorMatrix:
    """For each executor in the registry, verify it rejects tasks from every
    OTHER executor's repos."""

    def test_all_executors_reject_foreign_repos(self):
        all_repos: set[str] = set()
        for cap in EXECUTOR_CAPABILITIES.values():
            all_repos.update(cap.authoritative_repos)

        for executor_id, cap in EXECUTOR_CAPABILITIES.items():
            foreign = all_repos - cap.authoritative_repos
            for repo in foreign:
                executor_fn = MagicMock()
                task = _stub_scan_emit(repo, "some/file.py", f"matrix-{executor_id}-{repo}")

                result = dispatch_task(task, executor_id, executor_fn)

                assert result is None, f"Executor {executor_id} should reject source_repo={repo}"
                executor_fn.assert_not_called()


# ── End-to-end integration: scan → tag → dispatch ──────────────────────


class TestEndToEndScanDispatchCycle:
    """Simulates the full cycle: scanner scans multiple repos, emits tasks
    with source_repo tags, and the dispatch layer routes/blocks correctly."""

    SCANNED_REPOS = [
        ("family-tree", "src/models/person.py", "family-tree", True),
        ("claude-code-scaffold", "scripts/maintenance/vsm/ops.py", "claude-code-scaffold", True),
        ("analysis-repo", "analysis/build_stocks.py", "claude-code-scaffold", False),
        ("analysis-repo", "analysis/eia_match.py", "family-tree", False),
        ("pan", "src/main.py", "claude-code-scaffold", False),
        ("pan", "src/main.py", "family-tree", False),
    ]

    @pytest.mark.parametrize(
        "source_repo,file_path,target_executor,should_dispatch",
        SCANNED_REPOS,
        ids=[f"{sr}->{te}" for sr, _, te, _ in SCANNED_REPOS],
    )
    def test_scan_to_dispatch(self, source_repo, file_path, target_executor, should_dispatch):
        executor = MagicMock(return_value="dispatched")
        task = _stub_scan_emit(source_repo, file_path)

        result = dispatch_task(task, target_executor, executor)

        if should_dispatch:
            assert result == "dispatched"
            executor.assert_called_once_with(task)
        else:
            assert result is None
            executor.assert_not_called()

    def test_batch_scan_summary(self, caplog):
        """Simulate a batch scan of 6 repos. Only 2 should dispatch; 4 should
        be blocked with warnings."""
        dispatched = []
        blocked = []

        with caplog.at_level(logging.WARNING):
            for source_repo, file_path, target_executor, _should_dispatch in self.SCANNED_REPOS:
                executor = MagicMock(return_value="ok")
                task = _stub_scan_emit(source_repo, file_path)
                result = dispatch_task(task, target_executor, executor)

                if result is not None:
                    dispatched.append((source_repo, target_executor))
                else:
                    blocked.append((source_repo, target_executor))

        assert len(dispatched) == 2
        assert len(blocked) == 4
        warning_lines = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_lines) == 4


# ── Registry / dispatcher agreement ────────────────────────────────────


class TestRegistryDispatcherAgreement:
    """The executor_registry and task_dispatcher must agree on which repos
    each executor can handle — they should never diverge."""

    def test_dispatcher_capabilities_match_registry(self):
        """get_capable_repos() in the dispatcher must include all repos
        that the registry's is_executor_authoritative() accepts."""
        for executor_id, cap in EXECUTOR_CAPABILITIES.items():
            dispatcher_repos = get_capable_repos(executor_id)
            for repo in cap.authoritative_repos:
                assert repo in dispatcher_repos, (
                    f"Registry says {executor_id} handles {repo}, "
                    f"but dispatcher's get_capable_repos disagrees"
                )

    def test_registry_rejects_what_dispatcher_rejects(self):
        """If the dispatcher drops a task, the registry must also say the
        executor is not authoritative."""
        test_repos = ["analysis-repo", "unknown-repo", "pan", "benchmarks"]
        for executor_id in EXECUTOR_CAPABILITIES:
            for repo in test_repos:
                capable = repo in get_capable_repos(executor_id)
                authoritative = is_executor_authoritative(executor_id, repo)
                assert capable == authoritative, (
                    f"Disagreement for {executor_id}/{repo}: "
                    f"dispatcher={capable}, registry={authoritative}"
                )
