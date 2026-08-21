"""Executor-capability registry: maps executors to their authoritative repos.

The dispatch layer consults this registry to verify that a task's source_repo
matches the executor it would be routed to, preventing cross-project
misdispatches (e.g. a task targeting analysis/build_stocks.py being sent to
the claude-code-scaffold executor).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutorCapability:
    """Describes what a single executor can act on."""

    executor_id: str
    authoritative_repos: frozenset[str]
    description: str = ""

    def can_handle(self, source_repo: str | None) -> bool:
        """Return True if this executor is authoritative for *source_repo*.

        Returns False for None/empty source_repo — unknown origin is never
        considered a match, forcing callers to handle the ambiguity explicitly.
        """
        if not source_repo:
            return False
        return source_repo in self.authoritative_repos


# ---------------------------------------------------------------------------
# Registry data
#
# Each entry maps an executor_id to the set of project-ids (matching the keys
# used in common/project_config.PROJECT_REPOS on the scaffold side) that the
# executor is authoritative for.
#
# Convention:
#   - executor_id  : the Asana project tag / ECS task-family name
#   - project-ids  : values that appear in InternalInsight.source_repo
#
# Extend this as new executors come online.  Not every project needs an
# executor on day 1 — unmatched source_repos will be caught by the
# pre-dispatch filter (subtask 4) and dropped/logged rather than misdispatched.
# ---------------------------------------------------------------------------

EXECUTOR_CAPABILITIES: dict[str, ExecutorCapability] = {
    "claude-code-scaffold": ExecutorCapability(
        executor_id="claude-code-scaffold",
        authoritative_repos=frozenset({"claude-code-scaffold"}),
        description="Infrastructure executor — handles only the scaffold repo itself.",
    ),
    "family-tree": ExecutorCapability(
        executor_id="family-tree",
        authoritative_repos=frozenset({"family-tree"}),
        description="Family-tree app executor — handles dmoskov/kin.",
    ),
}


def get_executor_for_repo(source_repo: str) -> ExecutorCapability | None:
    """Find the executor authoritative for *source_repo*, or None."""
    for cap in EXECUTOR_CAPABILITIES.values():
        if cap.can_handle(source_repo):
            return cap
    return None


def is_executor_authoritative(executor_id: str, source_repo: str | None) -> bool:
    """Check whether *executor_id* is authoritative for *source_repo*.

    Returns False if the executor is unknown or source_repo is None/empty.
    This is the primary check the pre-dispatch filter should call.
    """
    cap = EXECUTOR_CAPABILITIES.get(executor_id)
    if cap is None:
        return False
    return cap.can_handle(source_repo)


def list_executors() -> list[ExecutorCapability]:
    """Return all registered executors."""
    return list(EXECUTOR_CAPABILITIES.values())
