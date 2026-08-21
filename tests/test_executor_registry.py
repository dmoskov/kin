"""Tests for scripts/executor_registry.py."""

import importlib
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from executor_registry import (
    EXECUTOR_CAPABILITIES,
    ExecutorCapability,
    get_executor_for_repo,
    is_executor_authoritative,
    list_executors,
)


class TestExecutorCapability:
    def test_can_handle_matching_repo(self):
        cap = ExecutorCapability(
            executor_id="test-exec",
            authoritative_repos=frozenset({"repo-a", "repo-b"}),
        )
        assert cap.can_handle("repo-a") is True
        assert cap.can_handle("repo-b") is True

    def test_can_handle_non_matching_repo(self):
        cap = ExecutorCapability(
            executor_id="test-exec",
            authoritative_repos=frozenset({"repo-a"}),
        )
        assert cap.can_handle("repo-x") is False

    def test_can_handle_none(self):
        cap = ExecutorCapability(
            executor_id="test-exec",
            authoritative_repos=frozenset({"repo-a"}),
        )
        assert cap.can_handle(None) is False

    def test_can_handle_empty_string(self):
        cap = ExecutorCapability(
            executor_id="test-exec",
            authoritative_repos=frozenset({"repo-a"}),
        )
        assert cap.can_handle("") is False

    def test_frozen(self):
        cap = ExecutorCapability(
            executor_id="test-exec",
            authoritative_repos=frozenset({"repo-a"}),
        )
        with pytest.raises(AttributeError):
            cap.executor_id = "changed"


class TestRegistry:
    def test_scaffold_executor_exists(self):
        assert "claude-code-scaffold" in EXECUTOR_CAPABILITIES

    def test_scaffold_only_authoritative_for_scaffold(self):
        cap = EXECUTOR_CAPABILITIES["claude-code-scaffold"]
        assert cap.authoritative_repos == frozenset({"claude-code-scaffold"})

    def test_scaffold_rejects_other_repos(self):
        cap = EXECUTOR_CAPABILITIES["claude-code-scaffold"]
        assert cap.can_handle("family-tree") is False
        assert cap.can_handle("analysis") is False
        assert cap.can_handle("pan") is False

    def test_family_tree_executor_exists(self):
        assert "family-tree" in EXECUTOR_CAPABILITIES
        cap = EXECUTOR_CAPABILITIES["family-tree"]
        assert cap.can_handle("family-tree") is True
        assert cap.can_handle("claude-code-scaffold") is False


class TestGetExecutorForRepo:
    def test_known_repo(self):
        cap = get_executor_for_repo("claude-code-scaffold")
        assert cap is not None
        assert cap.executor_id == "claude-code-scaffold"

    def test_unknown_repo(self):
        assert get_executor_for_repo("unknown-repo") is None


class TestIsExecutorAuthoritative:
    def test_match(self):
        assert is_executor_authoritative("claude-code-scaffold", "claude-code-scaffold") is True

    def test_mismatch(self):
        assert is_executor_authoritative("claude-code-scaffold", "family-tree") is False

    def test_unknown_executor(self):
        assert is_executor_authoritative("nonexistent", "any-repo") is False

    def test_none_source_repo(self):
        assert is_executor_authoritative("claude-code-scaffold", None) is False


class TestListExecutors:
    def test_returns_all(self):
        executors = list_executors()
        ids = {e.executor_id for e in executors}
        assert "claude-code-scaffold" in ids
        assert "family-tree" in ids

    def test_returns_list(self):
        assert isinstance(list_executors(), list)


class TestSmokeImport:
    """Verify the module can be imported and parsed without error."""

    def test_importable(self):
        mod = importlib.import_module("executor_registry")
        assert hasattr(mod, "EXECUTOR_CAPABILITIES")
        assert hasattr(mod, "is_executor_authoritative")
        assert hasattr(mod, "get_executor_for_repo")
