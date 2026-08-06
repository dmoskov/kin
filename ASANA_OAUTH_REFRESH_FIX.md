# Asana OAuth Token Refresh — Intermittent Failure Fix

## Bug: Asana OAuth token refresh intermittently failing (2x on 2026-08-05)

**Task**: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217195284981262

## Root Cause Analysis

### Architecture

Three independent code paths refresh Asana OAuth tokens:
1. **Lambda `oauth-token-rotation.py`** — Runs daily at 06:00 UTC via EventBridge
2. **`core/secrets_manager.py` `SecretsManager._refresh_token()`** — Called when tokens are expiring (emits `TokenRefreshFailure` CloudWatch metric)
3. **`utils/oauth_manager.py` `OAuthManager._refresh_asana_token()`** — Called by sync workers pre-sync

### What happened on 2026-08-05

The `TokenRefreshFailure` metric (namespace `FamilyOrg/OAuth`) breached twice:
- **05:36 UTC** — refresh failed; next sync cycle succeeded at 05:40
- **15:20 UTC** — refresh failed; next sync cycle succeeded at 15:24:55

Both originated from `core/secrets_manager.py:_refresh_token()`. The "retries" that
succeeded were **not actual retries** — they were the next scheduled sync cycle
happening to call `_refresh_token()` again ~4 minutes later.

### Root cause: No retry logic on any refresh path

All three refresh paths made a **single HTTP POST** to `https://app.asana.com/-/oauth_token`.
Any transient failure (Asana API hiccup, network blip, 5xx, 429 rate limit) immediately
failed and emitted `TokenRefreshFailure`. No retry, no backoff.

Additionally, the Lambda's `requests.post()` had **no timeout parameter**, risking
the Lambda hanging until its 5-minute execution limit.

### Error type assessment

The code logged only `response.status_code` without the response body, making it
impossible to distinguish timeout vs 429 vs 5xx from existing logs. The fix adds
response body logging to all failure paths.

## Fix

**Repo**: `dmoskov/family-organization`
**Branch**: `task/1217195284981262`
**Commit**: `7b49880`

### Changes

1. **`core/secrets_manager.py`** — `_refresh_token()` now retries up to 3 times with
   exponential backoff (2s, 4s delays) on transient failures:
   - Retries on: 5xx server errors, 429 rate limits, timeouts, connection errors
   - Does NOT retry on: 401/403 auth errors (token revoked — retry won't help)
   - Logs response body on failure for better diagnostics

2. **`lambda/functions/oauth-token-rotation.py`** — `rotate_asana_token()`:
   - Added `timeout=30` to `requests.post()` (was missing entirely)
   - Added same 3-attempt retry with exponential backoff
   - Logs full error response body on failure

3. **`utils/oauth_manager.py`** — `_refresh_asana_token()`:
   - Added same retry pattern with exponential backoff
   - Improved error classification and logging

4. **`tests/test_lambda_handlers.py`** — 3 new tests:
   - `test_rotate_asana_token_retries_on_5xx` — verifies retry succeeds after 500
   - `test_rotate_asana_token_no_retry_on_401` — verifies auth errors abort immediately
   - `test_rotate_asana_token_retries_on_timeout` — verifies timeout recovery

### Impact

- **Before**: ~8% first-attempt failure rate (2 failures across ~24 hourly refresh cycles)
  with no retry meant each failure emitted an alarm and relied on the next cycle to recover.
- **After**: Transient failures are retried within seconds (2s + 4s backoff). Only
  persistent failures (3 consecutive attempts) emit `TokenRefreshFailure`. This should
  eliminate alarm noise from transient Asana API issues while preserving alerting for
  genuine token revocation or sustained API outages.

### Policy threshold (from task)

If failure frequency increases (>2/day) or any failure fails to self-heal within one
refresh cycle, escalate to high priority. The retry logic reduces the likelihood of
this threshold being hit by transient issues.
