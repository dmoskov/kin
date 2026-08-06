# SyncIsRed Metric Emitter Fix — False OKs for Genuinely Stale Contacts

## Bug: contacts-sync-red alarm went OK despite ~7.8h staleness

**Filed**: 2026-08-05 03:12 UTC by VSM S5 Policy
**Asana**: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217176850014985

### Investigation

At 02:25 UTC on 2026-08-05, the `contacts-sync-red` CloudWatch alarm flipped
to OK even though `sync_status.last_successful_sync` for google_contacts was
2026-08-04 19:24 UTC (~7.8 hours stale). The alarm should have been in ALARM
state — contacts were genuinely stale, not a false alarm.

### Root Cause

Two independent bugs in the sync freshness monitoring stack:

**Bug 1: Lambda contacts thresholds not updated after schedule change**

The contacts sync schedule was changed from `rate(1 day)` to `rate(4 hours)`
(sibling task `1217176850096112`), but the freshness-monitor Lambda still used
the old daily-cadence thresholds:

```python
SYNC_FRESHNESS_THRESHOLDS = {
    "google_contacts": 30,  # ~daily cadence (STALE)
    "contacts": 30,
}
```

This made `red_threshold_hours("google_contacts")` return `max(12, 30 * 1.5)`
= **45 hours**. The Lambda emitted `SyncIsRed=0` for contacts at 7.8h staleness
because 7.8 < 45, producing a false OK.

**Bug 2: Alarm period / missing-data mismatch (overlaps sibling task)**

All 12 SyncIsRed + SyncStalenessHours alarms had:
- `period = 900` (15 minutes)
- `treat_missing_data = "breaching"`

The Lambda runs hourly, so 3 of 4 evaluation windows had zero datapoints,
treated as breaching. This caused false ALARMs for healthy sync sources
(the inverse direction — same root cause, opposite symptom).

### Fix

**Repo**: `dmoskov/family-organization`
**PR**: https://github.com/dmoskov/family-organization/pull/219
**Branch**: `task/1217176850014985`

#### Lambda (`sync-freshness-monitor.py`)
- `google_contacts` / `contacts` thresholds: 30h -> 8h (2x the new 4h cadence)
- After fix: `red_threshold_hours("google_contacts")` = `max(12, 8 * 1.5)` = 12h
- Contacts at 7.8h would still not be RED (correct — 7.8h is within 2x cadence)
- Contacts at 12+ hours would correctly go RED (catches the real outage scenario)

#### Terraform (`monitoring.tf`)
- All 12 SyncIsRed + SyncStalenessHours alarms: `period` 900 -> 3600,
  `treat_missing_data` "breaching" -> "notBreaching"
- `contacts_sync_stale` threshold: 48h -> 8h
- Alarm descriptions updated to reflect actual thresholds

### Relationship to Sibling Tasks

| Task | What it fixed | Status |
|------|---------------|--------|
| `1217176850096112` | Contacts sync scheduling (daily -> 4h), OAuth failure investigation | Merged |
| `1217176850102642` | Alarm period/missing-data false alarms (tracking doc only) | Merged |
| `1217176850014985` (this) | Lambda threshold mismatch + Terraform alarm config fixes | PR #219 |

The sibling tasks documented the issues but the actual Lambda threshold fix
and Terraform config changes were not applied. This task applies both.

### Why the Alarm Flipped to OK

Timeline reconstruction:
1. 2026-08-04 19:24 UTC — Last successful contacts sync
2. ~02:00 UTC — Lambda runs, queries `last_successful_sync` for contacts
3. Lambda computes staleness = ~6.6h, compares against `red_threshold_hours` = 45h
4. Emits `SyncIsRed=0` (6.6 < 45) — **incorrect** given the intent was ~12h
5. 02:25 UTC — Alarm evaluates `SyncIsRed=0`, transitions ALARM -> OK
6. Result: genuine staleness masked by overly permissive threshold
