# App Error Rate Spike Investigation — 2026-08-05 16:12–16:17 UTC

## Signal

`family-org-production-app-errors-high` entered ALARM at 16:22 UTC.
`AppErrors` metric: 18 errors at 16:12 AND 18 at 16:17 (threshold 10, 2 eval periods).
Steady 18/period suggests a repeating error loop, not a one-off burst.

## What the Alarm Monitors

The `AppErrors` metric is derived from a CloudWatch log metric filter
(`monitoring.tf` line 205) with pattern `[ERROR]` against the ECS web
container log group (`/ecs/family-org-production/web`).

This matches any log line containing the literal substring `[ERROR]` —
primarily gunicorn's error log format (`[ERROR] Worker failed to boot`)
and Python logging's default format when it includes bracketed level names.

## Investigation — What Was Ruled Out

| Suspect | Status | Evidence |
|---------|--------|----------|
| Sync pipeline failure | **Ruled out** | All sync workers healthy: calendar 15:52, slack 15:51, asana 15:31, sheets/drive 15:24 |
| sync_log errors | **Ruled out** | Zero error rows in last 45 min |
| Contacts sync outage | **Unlikely trigger** | Down 21h without triggering this alarm |
| OAuth refresh retry | **Unlikely** | Retry fix deployed (commit 7b49880), only affects token refresh |
| Health check Lambda | **Wrong log group** | Lambda logs to `/aws/lambda/*`, not `/ecs/*/web` |

## What Could Not Be Checked

**Blocked by missing IAM permissions**: The letta-task-role lacked
`cloudwatch:GetMetricStatistics` and `logs:FilterLogEvents`. Without
log access, the specific error messages causing the 18 errors/5min
pattern could not be identified.

## Fixes Applied

### 1. CloudWatch Read-Only IAM Policy (family-organization PR)

Created `aws_iam_policy.cloudwatch_read_only` in `monitoring.tf` with:
- `cloudwatch:GetMetricStatistics`, `GetMetricData`, `ListMetrics`,
  `DescribeAlarms`, `DescribeAlarmHistory`, `GetDashboard`, `ListDashboards`
- `logs:FilterLogEvents`, `GetLogEvents`, `DescribeLogGroups`,
  `DescribeLogStreams`, `StartQuery`, `GetQueryResults`, `StopQuery`
- Scoped to production ECS and Lambda log groups

Attached to `lambda_vsm_alert_bridge` role so the bridge Lambda can
enrich alerts with log context during triage.

Policy ARN exported as `cloudwatch_read_only_policy_arn` for attachment
to external roles (e.g. letta-task-role on the Letta infrastructure).

### 2. OKActions on App Errors Alarm

Added `ok_actions = [aws_sns_topic.alerts.arn]` to the `app_errors_high`
alarm. Previously, no recovery notification was sent when the alarm
cleared — investigators had to check alarm state manually.

### 3. Improved Alarm Description

Updated `alarm_description` to include threshold details for quick
reference during triage.

## Follow-up Required

1. **Attach policy to letta-task-role**: The Letta server infrastructure
   is managed separately. Run:
   ```
   aws iam attach-role-policy \
     --role-name <letta-task-role-name> \
     --policy-arn $(terraform output -raw cloudwatch_read_only_policy_arn)
   ```

2. **Investigate actual log content**: Once CloudWatch access is granted,
   query the web container logs for the 16:10–16:20 UTC window:
   ```
   aws logs filter-log-events \
     --log-group-name /ecs/family-org-production/web \
     --start-time 1722873000000 \
     --end-time 1722873600000 \
     --filter-pattern "[ERROR]"
   ```

3. **Consider refining the log metric filter**: The current `[ERROR]`
   pattern is broad — it matches any line containing that substring.
   A more precise filter could reduce noise from expected errors
   (e.g. gunicorn worker recycling, transient DB connection errors).

## Candidate Error Sources (from code analysis)

Based on the steady 18/period cadence, likely candidates include:
- **Gunicorn worker timeout/recycling**: 2 workers × 4 threads = 8 max
  concurrent requests; timeout=120s could produce `[ERROR]` on overload
- **Database connection errors**: `_handle_db_errors` decorator on
  monitoring endpoints logs `logger.error()` on any DB exception
- **Flask teardown handler**: `core/flask_logging.py` logs `logger.error()`
  on unhandled request exceptions
- **External service polling**: HTMX auto-refresh endpoints polling
  every 30–60s could accumulate errors if the DB pool is exhausted
