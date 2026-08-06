# Contacts Sync Staleness Fix

## Bug: Contacts sync stale ~8h — worker not being triggered

**Task**: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217176850096112

## Root Cause Analysis

Investigation of the scheduling path (EventBridge → Lambda → SQS → ECS worker):

1. **EventBridge rule**: ENABLED, `rate(1 day)`, firing correctly
2. **Lambda trigger**: Invoked at 19:xx UTC on 08-04 and 08-05, zero errors
3. **SQS**: Message delivered to `family-org-production-contacts-sync` queue
4. **ECS worker**: Running, picks up messages, but sync FAILS

**Failure**: Google OAuth token refresh returns `Unauthorized` (401).
The refresh token stored in the `oauth_tokens` table is invalid/revoked.

```
2026-08-05 19:24:45 - utils.oauth_manager - WARNING - Failed to refresh google token: Refresh failed: Unauthorized
2026-08-05 19:24:45 - database.base_sync - ERROR - OAuth token error: Refresh failed: Unauthorized
```

The message was retried 3 times (SQS maxReceiveCount=3) at 19:24, 20:29, and 21:34
before going to the DLQ. All 3 attempts failed with the same OAuth error.

## Contributing Factors

1. **Daily schedule**: `rate(1 day)` means one failed attempt = 24h outage
2. **Worker idle timeout bug**: Workers exit on idle only after processing ≥1 message,
   causing unnecessary ECS compute when the queue is empty

## Fix (in family-organization repo)

Branch: `task/1217176850096112` on `dmoskov/family-organization`
Commit: `83f52f5`

1. Increased contacts sync from `rate(1 day)` to `rate(4 hours)`
2. Updated monitoring thresholds (48h → 8h staleness, alarm descriptions)
3. Updated freshness monitor thresholds (30h → 8h)
4. Fixed worker idle timeout to exit even with 0 messages processed

## Manual Action Required

The Google OAuth refresh token needs to be re-authorized. This is a manual step
(re-running the OAuth flow to obtain a new refresh token). The code fix reduces
blast radius so future auth failures don't cause day-long outages.

Calendar and Drive syncs are also affected by the same OAuth issue.
