"""Pre-dispatch filter for task routing.

Checks ``task['source_repo']`` against the executor-capability registry
before invoking any executor.  Tasks targeting repos the executor cannot
reach are dropped with a structured warning — preventing wasted compute
from cross-project misdispatches (see parent bug: 4th misdispatch instance).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from executor_registry import EXECUTOR_CAPABILITIES as _REGISTRY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Executor-capability registry (derived from executor_registry module)
# ---------------------------------------------------------------------------
# Single source of truth is scripts/executor_registry.py.  This dict is a
# derived view mapping executor names → set of source_repo values, kept for
# backward-compatible use by get_capable_repos() and downstream tests.

EXECUTOR_CAPABILITIES: dict[str, set[str]] = {
    eid: set(cap.authoritative_repos) for eid, cap in _REGISTRY.items()
}

LOCAL_PROJECT = "family-tree"


def get_capable_repos(executor_name: str) -> set[str]:
    """Return the set of repos *executor_name* can operate on."""
    return EXECUTOR_CAPABILITIES.get(executor_name, set())


# ---------------------------------------------------------------------------
# Pre-dispatch filter
# ---------------------------------------------------------------------------


def dispatch_task(
    task: dict[str, Any],
    executor_name: str,
    executor_fn: Callable[[dict[str, Any]], Any],
) -> Any | None:
    """Dispatch *task* to *executor_fn* only if *source_repo* is compatible.

    Parameters
    ----------
    task:
        Task payload — must contain ``source_repo`` (str or ``None``).
    executor_name:
        Logical name of the target executor (key in ``EXECUTOR_CAPABILITIES``).
    executor_fn:
        Callable that actually runs the task.  Only invoked when the
        source-repo check passes.

    Returns
    -------
    The return value of *executor_fn* on success, or ``None`` when the task
    is dropped due to a mismatch.
    """
    source_repo = task.get("source_repo")
    task_gid = task.get("gid", task.get("id", "<unknown>"))
    file_path = task.get("evidence", {}).get("file") or task.get("file_path") or "<unknown>"

    if source_repo is None:
        logger.warning(
            "misdispatch_guard: task %s has no source_repo — dropping to "
            "prevent potential misdispatch | executor=%s file=%s",
            task_gid,
            executor_name,
            file_path,
        )
        return None

    capable_repos = get_capable_repos(executor_name)

    if not capable_repos:
        logger.warning(
            "misdispatch_guard: executor %s has no registered capabilities — "
            "dropping task %s | source_repo=%s file=%s",
            executor_name,
            task_gid,
            source_repo,
            file_path,
        )
        return None

    if source_repo not in capable_repos:
        logger.warning(
            "misdispatch_guard: task %s has source_repo=%s but executor %s "
            "only handles %s — dropping to prevent misdispatch | file=%s "
            "estimated_wasted_cost=$1.64",
            task_gid,
            source_repo,
            executor_name,
            sorted(capable_repos),
            file_path,
        )
        return None

    return executor_fn(task)
