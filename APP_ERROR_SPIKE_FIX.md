# App Error Rate Spike — Metric Filter False Positive Fix

## Bug: 18 errors/5min for 2+ consecutive periods (16:12-16:17 UTC on 2026-08-05)

**Task**: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217197432939325

## Root Cause Analysis

### Signal

CloudWatch alarm `family-org-production-app-errors-high` entered ALARM at 16:22 UTC.
The `AppErrors` metric (namespace `family-org-production/Application`) showed SUM=18
per 5-min period for 2 consecutive evaluation periods, exceeding the threshold of 10.

### Investigation

Checked CloudWatch Logs for `/ecs/family-org-production/web` during the 16:10-16:20 UTC
window. Found **zero actual ERROR-level log messages**. All 36 log events were
normal startup logs (gunicorn INFO, alembic migrations, database pool init).

The web container was being redeployed at 16:16:50 and 16:17:26 UTC (two fresh
ECS task starts visible in log streams). Each restart emitted ~18 INFO-level log lines.

### Root cause: Misconfigured CloudWatch metric filter

The metric filter `family-org-production-app-errors` had pattern `[ERROR]` (unquoted
brackets). In CloudWatch Logs filter syntax, `[column_name]` defines a **space-delimited
column variable** — it matches *every single log line* regardless of content, binding
the entire line to `$ERROR`.

Verified with `aws logs test-metric-filter`:
- Pattern `[ERROR]` matched ALL log messages (INFO, WARNING, startup messages, etc.)
- Pattern `?"[ERROR]" ?"ERROR:"` matched only actual error messages

This means every log line emitted by the web container was counted as an "error."
During normal low-traffic periods the rate stayed under threshold, but container
restarts (many startup log lines in quick succession) caused spikes above the
threshold of 10 errors per 5-min period.

The recurring "36 errors" pattern in the metric data corresponds to the ~18 startup
log lines per container x 2 containers (the service runs desiredCount=2).

Larger spikes (106, 204, 247, 326) visible later in the day correspond to periods
of higher request traffic generating more log lines.

## Fixes Applied

### 1. Fixed metric filter pattern (AWS CLI)

Changed the CloudWatch Logs metric filter from:
```
[ERROR]  (matches ALL log lines)
```
to:
```
?"[ERROR]" ?"ERROR:"  (matches gunicorn [ERROR] logs OR Python ERROR: logs)
```

The `?` operator is an OR — this catches both gunicorn-style `[ERROR]` log lines
and Python logging `ERROR:module:message` format.

### 2. Added OKActions to alarm

The alarm had `OKActions: []`, meaning no recovery notification would be sent.
Added the same SNS topic (`family-org-production-alerts`) to OKActions so the
alert pipeline receives recovery notifications.

### 3. VSM task role permissions (documented, not applied)

The `letta-task-role` used by VSM agents has:
- `logs:GetLogEvents` (can read specific log streams)
- `logs:CreateLogStream`, `logs:PutLogEvents` (can write logs)

Missing for triage capability:
- `logs:FilterLogEvents` — search across log streams
- `logs:DescribeLogGroups` — discover log groups
- `logs:DescribeLogStreams` — list log streams
- `logs:DescribeMetricFilters` — inspect metric filter config
- `cloudwatch:GetMetricStatistics` — read metric data
- `cloudwatch:GetMetricData` — read metric data (newer API)
- `cloudwatch:DescribeAlarms` — inspect alarm config
- `cloudwatch:DescribeAlarmHistory` — alarm state history

Could not apply: the execution role (`crucible-remote-agent-analysis-task-role`)
lacks `iam:PutRolePolicy`. Recommend adding an inline policy
`letta-task-cloudwatch-readonly` with these read-only actions.

## Verification

After the fix, the metric filter correctly discriminates:
- `[INFO] Starting gunicorn` -> NOT matched (correct)
- `INFO:core.config:Configuration loaded` -> NOT matched (correct)
- `[ERROR] Something went wrong` -> MATCHED (correct)
- `ERROR:database:Connection failed` -> MATCHED (correct)
- `Connection pool stats: errors=0` -> NOT matched (correct, `errors` in body != ERROR level)

## Current alarm state

As of investigation: `OK` (transitioned at 23:23 UTC on 2026-08-05).
The alarm self-resolved when log output rate dropped below 10 per 5-min period.
