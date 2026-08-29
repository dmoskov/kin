# Changelog

## 2026-08-29 — S4 auth-path liveness test (credential diagnostic)

**Context:** Asana comment-post returned 401 at 20:30:12 UTC; task-create had
succeeded at 19:52:40 UTC. S4 filed this diagnostic task to discriminate
comment-path-specific failure from full credential death.

**Result:** This task was created successfully in Asana, confirming:
- Task-create API path: **alive**
- 401 is **comment-path-specific**, not full credential death
- OAuth token refresh (documented in `ASANA_OAUTH_REFRESH_FIX.md`) is functioning
  for task-create operations; comment-post may require different scope or has a
  transient issue on Asana's side

No code changes required — this entry documents the diagnostic finding.

## 2026-08-21 — Fix cross-project misdispatch in task dispatch layer

**Bug class:** The internal scanner (`internal_scanner.py` on the scaffold side)
scans all 13+ project repos for code quality issues, dead code, stale docs, etc.
The resulting `InternalInsight` objects were emitted without a `source_repo` field,
so the dispatch layer could not distinguish which repo a task originated from.
Tasks targeting files in unrelated repos (e.g. `analysis/build_stocks.py`) were
routed to the claude-code-scaffold executor, which cloned the wrong repo, failed
to find the file, and wasted ~$1.64 per attempt.

Four confirmed instances of this class:
- `analysis/build_stocks.py` → function `eia_match` (task 1217713196599997)
- `analysis/hormuz_round2.py`
- `analysis/implied_probability.py`
- `analysis/price_supply_curve.py`

**Fix applied (subtasks 1–5):**

1. **Audit** (`docs/REPO_IDENTITY_AUDIT.md`): Identified that `InternalScanner`
   has `project_id` available at construction time but does not propagate it into
   `InternalInsight` objects or proposal context dicts.

2. **`source_repo` field**: Added `source_repo: str | None` to `InternalInsight`
   and populated it from `self.project_id` in all scanner methods on the scaffold
   side. Every task payload now carries the originating repo identity.

3. **Executor-capability registry** (`scripts/executor_registry.py`): Maps each
   executor to the set of repos it is authoritative for. The `ExecutorCapability`
   dataclass exposes `can_handle(source_repo)` for dispatch decisions.

4. **Pre-dispatch filter** (`scripts/task_dispatcher.py`): `dispatch_task()`
   checks `task["source_repo"]` against the executor's capabilities before
   invoking the executor function. Mismatched or missing `source_repo` tasks are
   dropped with a structured warning log.

5. **Integration tests** (`tests/test_dispatch_repo_identity.py`): End-to-end
   tests covering the exact bug-report scenarios, missing-source_repo safety net,
   positive dispatch path, cross-executor matrix, and registry/dispatcher
   agreement checks.

**Dead branch cleanup:** Branch `task/1217713196599997` (the wasted execution
from the 4th misdispatch instance) has been deleted from the remote.

### How to extend the executor registry for new projects

When a new project executor comes online:

1. **`scripts/executor_registry.py`** — Add an entry to `EXECUTOR_CAPABILITIES`:

   ```python
   "my-new-project": ExecutorCapability(
       executor_id="my-new-project",
       authoritative_repos=frozenset({"my-new-project", "optional-alias"}),
       description="Description of what this executor handles.",
   ),
   ```

   The `authoritative_repos` values must match the `source_repo` strings that
   `InternalInsight` objects carry (these come from the `project_id` parameter
   passed to `InternalScanner.__init__` on the scaffold side — see
   `common/project_config.PROJECT_REPOS` for the canonical list).

2. **`scripts/task_dispatcher.py`** — Add a matching entry to the dispatcher's
   `EXECUTOR_CAPABILITIES` dict so both modules agree:

   ```python
   "my-new-project": {"my-new-project", "optional-alias"},
   ```

3. **Verify agreement** — Run the test suite to confirm the registry and
   dispatcher are in sync:

   ```bash
   pytest tests/test_executor_registry.py tests/test_dispatch_repo_identity.py -v
   ```

   The `TestRegistryDispatcherAgreement` class will catch any divergence between
   the two modules.

Projects without a registered executor are safe: tasks targeting unregistered
repos are dropped by the pre-dispatch filter with a warning log rather than
misdispatched.
