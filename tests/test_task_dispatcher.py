"""Tests for the pre-dispatch misdispatch filter in task_dispatcher."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from task_dispatcher import (
    dispatch_task,
    get_capable_repos,
)

# ── Registry helpers ─────────────────────────────────────────────────


def test_get_capable_repos_known_executor():
    repos = get_capable_repos("claude-code-scaffold")
    assert repos == {"claude-code-scaffold"}


def test_get_capable_repos_unknown_executor():
    assert get_capable_repos("nonexistent-executor") == set()


# ── Misdispatch: source_repo does not match executor ─────────────────


def test_mismatched_source_repo_drops_task():
    """A task with source_repo='analysis-repo' dispatched to claude-code-scaffold
    must be intercepted — executor is never called."""
    executor = MagicMock(return_value="should not run")
    task = {
        "gid": "1217713196599997",
        "source_repo": "analysis-repo",
        "file_path": "analysis/build_stocks.py",
    }

    result = dispatch_task(task, "claude-code-scaffold", executor)

    assert result is None
    executor.assert_not_called()


def test_mismatched_source_repo_logs_warning(caplog):
    """The warning must contain 'misdispatch' and 'source_repo'."""
    executor = MagicMock()
    task = {
        "gid": "123",
        "source_repo": "analysis-repo",
        "file_path": "analysis/build_stocks.py",
    }

    with caplog.at_level(logging.WARNING):
        dispatch_task(task, "claude-code-scaffold", executor)

    log_text = caplog.text
    assert "misdispatch" in log_text
    assert "source_repo" in log_text
    assert "analysis-repo" in log_text


# ── Missing source_repo ──────────────────────────────────────────────


def test_missing_source_repo_drops_task():
    executor = MagicMock()
    task = {"gid": "456", "file_path": "some/file.py"}

    result = dispatch_task(task, "claude-code-scaffold", executor)

    assert result is None
    executor.assert_not_called()


def test_missing_source_repo_logs_warning(caplog):
    executor = MagicMock()
    task = {"gid": "456"}

    with caplog.at_level(logging.WARNING):
        dispatch_task(task, "claude-code-scaffold", executor)

    assert "misdispatch" in caplog.text
    assert "no source_repo" in caplog.text


# ── Unknown executor ─────────────────────────────────────────────────


def test_unknown_executor_drops_task():
    executor = MagicMock()
    task = {"gid": "789", "source_repo": "family-tree"}

    result = dispatch_task(task, "unknown-executor", executor)

    assert result is None
    executor.assert_not_called()


# ── Happy path: matching source_repo ─────────────────────────────────


def test_matching_source_repo_calls_executor():
    executor = MagicMock(return_value="executed")
    task = {"gid": "100", "source_repo": "claude-code-scaffold"}

    result = dispatch_task(task, "claude-code-scaffold", executor)

    assert result == "executed"
    executor.assert_called_once_with(task)


def test_family_tree_executor_accepts_family_tree():
    executor = MagicMock(return_value="ok")
    task = {"gid": "101", "source_repo": "family-tree"}

    result = dispatch_task(task, "family-tree", executor)

    assert result == "ok"
    executor.assert_called_once_with(task)


def test_family_tree_executor_accepts_kin_alias():
    executor = MagicMock(return_value="ok")
    task = {"gid": "102", "source_repo": "kin"}

    result = dispatch_task(task, "family-tree", executor)

    assert result == "ok"
    executor.assert_called_once_with(task)


# ── Evidence file path extraction ────────────────────────────────────


def test_evidence_file_path_in_log(caplog):
    """Structured warning must include the file path from the task."""
    executor = MagicMock()
    task = {
        "gid": "200",
        "source_repo": "analysis-repo",
        "evidence": {"file": "analysis/build_stocks.py"},
    }

    with caplog.at_level(logging.WARNING):
        dispatch_task(task, "claude-code-scaffold", executor)

    assert "analysis/build_stocks.py" in caplog.text


def test_task_gid_in_log(caplog):
    executor = MagicMock()
    task = {"gid": "1217713196599997", "source_repo": "wrong-repo"}

    with caplog.at_level(logging.WARNING):
        dispatch_task(task, "claude-code-scaffold", executor)

    assert "1217713196599997" in caplog.text
