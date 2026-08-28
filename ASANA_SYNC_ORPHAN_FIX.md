# Asana Sync :24:55-Grid Crash — Root Cause & Fix

**Task**: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217968728475363
**Fix PR**: dmoskov/family-organization branch `task/1217968728475363`

## Root Cause

The `:24:55` timing is NOT a separate sync mode — it is the EventBridge
`rate(4 hours)` grid anchor. All scheduled Asana syncs (incremental by
default) use the identical code path through
`EnhancedAsanaSyncRDS.full_sync()`.

When the sync process dies mid-run (OOM kill at rc -9, subprocess
timeout, SIGTERM during ECS task shutdown), neither the Python exception
handler in `base_sync.full_sync()` nor `_complete_sync_run()` execute.
The `sync_runs` row stays in `status='running'` with `completed_at=NULL`
and `error_message=NULL` — a zombie.

### Why the error handler didn't fire

`full_sync()` wraps `_run_sync_operations()` in a try/except that calls
`_complete_sync_run(success=False)`. But when the worker kills the sync
subprocess (via `process.kill()` on timeout), the Python process receives
SIGKILL — there is no opportunity for `finally` or `except` blocks to
run. The sync_run row is left orphaned.

### Why the error count is fixed (~93+109)

The deterministic error profile (identical counts each occurrence)
indicates data-dependent failures — specific Asana tasks or projects that
consistently fail validation or API fetch. Because the sync processes
projects sequentially and crashes at the same point, the error count is
reproducible.

## Evidence (4 zombie rows)

| started_at | sync_run_id | status |
|---|---|---|
| 2026-08-04 23:24:56 | (unknown) | running |
| 2026-08-05 01:40:17 | (unknown) | running |
| 2026-08-27 19:24:55 | (unknown) | running |
| 2026-08-28 15:24:56 | (unknown) | running |

All share: `completed_at=NULL`, `error_message=NULL`.

## Fixes Applied (family-organization)

### 1. Orphaned sync_run cleanup (`SyncRunRepository.cleanup_orphaned_runs`)

New method marks any sync_run in `status='running'` with
`started_at` older than 2 hours as `status='failed'` with error message
`'Orphaned: process exited without completing the sync run'`.

### 2. Automatic cleanup on sync start (`BaseIntegrationSync._start_sync_run`)

Each sync now calls `cleanup_orphaned_runs()` for its sync type before
creating a new run record. This prevents zombie rows from accumulating.

### 3. Robust error handler (`BaseIntegrationSync.full_sync`)

The error handler's calls to `progress_emitter.fail_sync()` and
`_complete_sync_run()` are now individually wrapped in try/except, so a
secondary failure (e.g., lost DB connection) during error handling does
not mask the original exception. The orphan will be cleaned up on the
next run instead.

## Scheduling Architecture (for reference)

```
EventBridge rate(4h)
  → Lambda trigger-asana-sync (sends SQS message)
    → SQS family-org-production-asana-sync
      → ECS worker-asana (polls SQS, runs subprocess)
        → python -m integrations.asana.enhanced_asana_sync_rds
          → EnhancedAsanaSyncRDS.full_sync(force_full_sync=False)
```

No separate "deep sync" or "full sync" variant exists at the `:24:55`
grid — `FORCE_FULL_SYNC` defaults to `false` and is only set by explicit
environment override.
