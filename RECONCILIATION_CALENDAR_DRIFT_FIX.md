# Reconciliation Lambda: Calendar Drift False Alarms — Staleness Calibration Fix

## Bug: reconciliation_lambda reports permanent ~24% calendar drift

**Filed**: 2026-08-23 by Sequoia (Letta agent)
**Asana**: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217754656030865

### Signal

The `cross-platform-reconciliation` Lambda reported `overall_status=critical_drift`
on every 6h run. Last four runs (Aug 22 19:24 -> Aug 23 13:24) showed 780-793
calendar events flagged `stale_data`, drift rate pinned at 23.8-24.2%.

Google Calendar sync was running successfully every ~2h throughout this window
(verified via `sync_status`; zero failures).

### Root Cause

`reconcile_calendar_staleness()` in `cross-platform-reconciliation.py` queried:

```sql
SELECT COUNT(*) as total_events,
       SUM(CASE WHEN updated_at < %s THEN 1 ELSE 0 END) as stale_events
FROM calendar_events
WHERE start_time > NOW() - INTERVAL '30 days'
```

with `%s` = `NOW() - 24 hours`.

This counted any event with `updated_at` older than 24 hours as "stale." But the
calendar sync uses incremental mode — it only fetches events that have been
*modified* in Google Calendar since the last sync. Events that haven't changed
(old meetings, recurring events that aren't edited) are correctly unchanged in
RDS; their `updated_at` reflects when they were last *modified*, not when they
were last *verified by the sync*.

~780 of 3254 events in the 30-day window simply hadn't been modified in Google
in the last 24 hours. They were permanently "stale" by this definition, producing
a fixed ~24% drift rate that never changed regardless of sync health.

### Effect

1. `overall_status` permanently `critical_drift` — desensitizes monitoring
2. Real drift signals buried — the one genuinely useful finding (Asana task
   1217733071080803 `missing_in_rds`) was a needle in a static haystack of
   780 false `stale_data` records
3. Same failure family as the Aug 4-12 health-check threshold miscalibrations:
   monitors calibrated against assumptions, not actual system cadences

### Fix

**Repo**: `dmoskov/family-organization`
**PR**: https://github.com/dmoskov/family-organization/pull/273
**Branch**: `task/1217754656030865`

Replaced the per-event `updated_at` staleness query with a sync pipeline health
check using `sync_status`:

1. Query `sync_status WHERE sync_type='google_calendar' AND sync_subtype='events'`
   to get `last_successful_sync` per calendar
2. Compare against `CALENDAR_SYNC_STALENESS_HOURS = 6` (~3x the 2h sync cadence)
3. Report stale *sync pipelines* (not stale events), with severity based on how
   far past the threshold the sync is
4. Still report total event count for context, but don't use it for drift calculation

This matches the approach already used by `sync-freshness-monitor.py`, which
correctly checks sync pipeline health rather than individual entity ages.

### Tests

60 tests passing (11 rewritten for new calendar logic):
- `test_healthy_sync_no_drift` — recent sync = no drift
- `test_stale_sync_detected` — sync > 6h old = flagged
- `test_mixed_healthy_and_stale_calendars` — per-calendar granularity
- `test_very_stale_sync_high_severity` — >2x threshold = HIGH
- `test_moderately_stale_medium_severity` — >1x threshold = MEDIUM
- `test_no_sync_status_returns_error` — missing sync_status handled
- `test_naive_timestamp_handled` — timezone-naive timestamps work
- Handler integration tests updated for new mock format
