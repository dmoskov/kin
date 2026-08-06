# Sync Metric Emission Fix — CloudWatch Alarm Period/Missing-Data Mismatch

## Bug: SyncIsRed metric emission "stopped" — false alarms for healthy syncs

**Filed**: 2026-08-05 03:11 UTC by VSM S5 Policy
**Asana**: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217176850102642

### Root Cause

The sync-freshness-monitor Lambda in `family-organization` runs every **1 hour**
(EventBridge `rate(1 hour)`), emitting `SyncIsRed` and `SyncStalenessHours`
metrics to the `FamilyOrg/Pipeline` CloudWatch namespace.

All 12 CloudWatch alarms for these metrics were configured with:
- `period = 900` (15 minutes)
- `treat_missing_data = "breaching"`

This meant 3 out of every 4 evaluation windows had **zero datapoints** and were
treated as threshold breaches. When the Lambda's run timing shifted (normal
jitter) or the Lambda had a single delayed invocation, every alarm fired —
including for sync sources that were verifiably healthy.

Specifically at ~03:10 UTC on 2026-08-05:
- `asana-sync-red` fired with "no datapoints were received... treated as Breaching"
- Asana sync had last succeeded at 02:52 UTC (perfectly healthy)
- The Lambda's hourly run hadn't emitted in the current 15-minute window → breaching

### Fix

**Repo**: `dmoskov/family-organization`
**PR**: https://github.com/dmoskov/family-organization/pull/218
**Branch**: `task/1217176850102642`

Changed all 12 SyncIsRed + SyncStalenessHours alarms:
- `period`: 900 → 3600 (match 1-hour Lambda schedule)
- `treat_missing_data`: "breaching" → "notBreaching"

This ensures:
1. Each evaluation window contains exactly one Lambda run's worth of data
2. Gaps between Lambda runs don't trigger false alarms
3. Alarms still fire when the Lambda reports actual staleness (SyncIsRed=1)
4. Lambda failures are caught separately by the `freshness-monitor-error` alarm

### Sync Staleness (Separate Issue)

The actual Google sync staleness (contacts ~8h, sheets/drive ~4h) is a real
worker issue being addressed by sibling task `task/1217176850096112` — the
contacts/sheets/drive workers weren't being triggered. This fix addresses
only the metric emission / false alarm issue to prevent the monitoring system
from crying wolf.

### ConsecutiveFailures Alarms

The `ConsecutiveFailures` alarms already correctly used
`treat_missing_data = "notBreaching"` — they were not affected by this bug.
