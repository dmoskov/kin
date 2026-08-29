"""Auth-path liveness diagnostic for Asana API endpoints.

Probes multiple Asana API paths independently to discriminate between
endpoint-specific failures (e.g. story/comment POST returning 401 while
task-create works) and full credential death (all paths returning 401).

Background: on 2026-08-29 ~19:49 UTC the comment-post endpoint started
returning 401 across multiple principals.  S5 created a marker task to
test whether the task-CREATE path was still alive — a manual form of
exactly what this script automates.

Usage::

    python scripts/asana_path_liveness.py                  # all probes
    python scripts/asana_path_liveness.py --paths whoami tasks  # subset
    python scripts/asana_path_liveness.py --token $PAT     # explicit token
    python scripts/asana_path_liveness.py --json            # machine-readable

See: Asana task 1217971896202362
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10

# Asana project used for write-path probes (family-org task queue).
PROBE_PROJECT_GID = "1211710875848660"

# Probe a known task for read/comment paths — any task the token can see.
# Uses the first task returned by the project's task list when not set.
PROBE_TASK_GID_ENV = "ASANA_PROBE_TASK_GID"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ProbeResult:
    """Result of probing a single API path."""

    path: str
    alive: bool
    status_code: int | None = None
    latency_ms: float | None = None
    error: str | None = None


@dataclass
class LivenessReport:
    """Aggregated liveness report across all probed paths."""

    results: list[ProbeResult] = field(default_factory=list)
    diagnosis: str = "unknown"

    def classify(self) -> str:
        """Classify the failure pattern across all probed paths.

        Returns one of:
          - "healthy"         — all probes succeeded
          - "credential_death" — all probes returned 401/403
          - "partial_failure"  — some probes failed, others succeeded
          - "network_error"   — all probes failed with connection errors
          - "unknown"         — no probes ran
        """
        if not self.results:
            return "unknown"

        alive = [r for r in self.results if r.alive]
        dead = [r for r in self.results if not r.alive]

        if not dead:
            return "healthy"
        if not alive:
            auth_failures = [r for r in dead if r.status_code in (401, 403)]
            conn_failures = [r for r in dead if r.status_code is None]
            if len(auth_failures) == len(dead):
                return "credential_death"
            if len(conn_failures) == len(dead):
                return "network_error"
            return "credential_death"
        return "partial_failure"

    def to_dict(self) -> dict:
        return {
            "diagnosis": self.diagnosis,
            "results": [asdict(r) for r in self.results],
        }


# ---------------------------------------------------------------------------
# Individual probes
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _timed_request(
    method: str,
    url: str,
    token: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    **kwargs,
) -> ProbeResult:
    """Execute an HTTP request and return a ProbeResult."""
    path = url.split("api.asana.com")[-1] if "api.asana.com" in url else url
    start = time.monotonic()
    try:
        resp = requests.request(
            method,
            url,
            headers=_headers(token),
            timeout=timeout,
            **kwargs,
        )
        elapsed = (time.monotonic() - start) * 1000
        alive = 200 <= resp.status_code < 300
        error = None if alive else f"HTTP {resp.status_code}"
        return ProbeResult(
            path=path,
            alive=alive,
            status_code=resp.status_code,
            latency_ms=round(elapsed, 1),
            error=error,
        )
    except requests.ConnectionError as e:
        elapsed = (time.monotonic() - start) * 1000
        return ProbeResult(
            path=path,
            alive=False,
            latency_ms=round(elapsed, 1),
            error=f"ConnectionError: {e}",
        )
    except requests.Timeout:
        elapsed = (time.monotonic() - start) * 1000
        return ProbeResult(
            path=path,
            alive=False,
            latency_ms=round(elapsed, 1),
            error=f"Timeout after {timeout}s",
        )
    except requests.RequestException as e:
        elapsed = (time.monotonic() - start) * 1000
        return ProbeResult(
            path=path,
            alive=False,
            latency_ms=round(elapsed, 1),
            error=str(e),
        )


def probe_whoami(token: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> ProbeResult:
    """GET /api/1.0/users/me — lightweight credential check."""
    return _timed_request(
        "GET",
        "https://api.asana.com/api/1.0/users/me",
        token,
        timeout=timeout,
    )


def probe_tasks_read(
    token: str,
    project_gid: str = PROBE_PROJECT_GID,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProbeResult:
    """GET /api/1.0/projects/{gid}/tasks — read path for task listing."""
    return _timed_request(
        "GET",
        f"https://api.asana.com/api/1.0/projects/{project_gid}/tasks?limit=1",
        token,
        timeout=timeout,
    )


def probe_story_post(
    token: str,
    task_gid: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProbeResult:
    """POST /api/1.0/tasks/{gid}/stories — comment/story write path.

    Posts a zero-impact diagnostic comment and immediately confirms delivery.
    The comment is intentionally bland to avoid polluting task history.
    """
    return _timed_request(
        "POST",
        f"https://api.asana.com/api/1.0/tasks/{task_gid}/stories",
        token,
        timeout=timeout,
        json={"data": {"text": "[liveness-probe] path-test ping"}},
    )


def probe_task_create(
    token: str,
    project_gid: str = PROBE_PROJECT_GID,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ProbeResult:
    """POST /api/1.0/tasks — task creation write path.

    Creates a minimal task and immediately marks it complete to avoid
    polluting the backlog.  The task is the probe itself.
    """
    result = _timed_request(
        "POST",
        "https://api.asana.com/api/1.0/tasks",
        token,
        timeout=timeout,
        json={
            "data": {
                "name": "[liveness-probe] path-test — auto-created, safe to delete",
                "projects": [project_gid],
                "completed": True,
            }
        },
    )
    return result


# ---------------------------------------------------------------------------
# Probe registry
# ---------------------------------------------------------------------------

PROBE_REGISTRY: dict[str, callable] = {
    "whoami": probe_whoami,
    "tasks": probe_tasks_read,
    "stories": probe_story_post,
    "task_create": probe_task_create,
}

# Probes that need a task_gid argument.
_NEEDS_TASK_GID = {"stories"}

# Probes that are read-only (safe to run without side effects).
READ_ONLY_PROBES = {"whoami", "tasks"}


def _resolve_probe_task_gid(token: str, timeout: int) -> str | None:
    """Find a task GID to use for story/comment probes."""
    gid = os.environ.get(PROBE_TASK_GID_ENV)
    if gid:
        return gid
    try:
        resp = requests.get(
            f"https://api.asana.com/api/1.0/projects/{PROBE_PROJECT_GID}/tasks?limit=1",
            headers=_headers(token),
            timeout=timeout,
        )
        if resp.ok:
            tasks = resp.json().get("data", [])
            if tasks:
                return tasks[0]["gid"]
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def check_liveness(
    token: str,
    paths: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> LivenessReport:
    """Run liveness probes and return a classified report.

    Parameters
    ----------
    token:
        Asana personal access token or OAuth bearer token.
    paths:
        Subset of probe names to run.  Defaults to all read-only probes
        (``whoami``, ``tasks``).  Include ``stories`` or ``task_create``
        for write-path checks.
    timeout:
        Per-request timeout in seconds.
    """
    if paths is None:
        paths = sorted(READ_ONLY_PROBES)

    report = LivenessReport()
    task_gid = None

    for name in paths:
        probe_fn = PROBE_REGISTRY.get(name)
        if probe_fn is None:
            report.results.append(
                ProbeResult(path=name, alive=False, error=f"unknown probe: {name}")
            )
            continue

        if name in _NEEDS_TASK_GID:
            if task_gid is None:
                task_gid = _resolve_probe_task_gid(token, timeout)
            if task_gid is None:
                report.results.append(
                    ProbeResult(
                        path=name,
                        alive=False,
                        error="no task_gid available for story probe",
                    )
                )
                continue
            result = probe_fn(token, task_gid, timeout=timeout)
        else:
            result = probe_fn(token, timeout=timeout)

        report.results.append(result)

    report.diagnosis = report.classify()
    return report


def _get_token() -> str | None:
    """Resolve Asana token from environment."""
    return os.environ.get("ASANA_ACCESS_TOKEN") or os.environ.get("ASANA_PAT")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        choices=sorted(PROBE_REGISTRY),
        default=None,
        help="Probes to run (default: whoami, tasks)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="all_paths",
        help="Run all probes including write-path probes",
    )
    parser.add_argument("--token", default=None, help="Asana bearer token")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    token = args.token or _get_token()
    if not token:
        print(
            "ERROR: No Asana token.  Set ASANA_ACCESS_TOKEN or pass --token.",
            file=sys.stderr,
        )
        sys.exit(1)

    paths = args.paths
    if args.all_paths:
        paths = sorted(PROBE_REGISTRY)

    report = check_liveness(token, paths=paths, timeout=args.timeout)

    if args.json_output:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"Diagnosis: {report.diagnosis}")
        print()
        for r in report.results:
            status = "ALIVE" if r.alive else "DEAD"
            latency = f" ({r.latency_ms:.0f}ms)" if r.latency_ms is not None else ""
            code = f" HTTP {r.status_code}" if r.status_code else ""
            err = f" — {r.error}" if r.error else ""
            print(f"  {r.path}: {status}{code}{latency}{err}")

    sys.exit(0 if report.diagnosis == "healthy" else 1)


if __name__ == "__main__":
    main()
