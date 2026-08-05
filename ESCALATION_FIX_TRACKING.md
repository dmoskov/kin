# Escalation Pipeline Fix - CloudWatch OK State Handling

## Bug 1: Escalation Logic — CloudWatch OK notifications treated as incidents

**Root cause**: The algedonic escalation pipeline had no check for CloudWatch
`NewStateValue=OK` in alert context. Recovery (ALARM→OK) notifications were
processed identically to active alarms, incrementing the debounce counter and
re-escalating to S5 Policy. The alarm "family-org-production-asana-sync-red"
was escalated 7 times with severity "unknown" despite having recovered at
2026-08-05T02:25:16Z.

**Fix** (scaffold branch `task/1217176582892596`, commit 45baccd5):
- `algedonic_agent_loop.py`: Before routing alerts to triage agents, query
  CloudWatch for alarm state and auto-resolve alerts whose alarms returned to OK.
  Also parse severity from alarm context to prevent "unknown" severity labels.
- `algedonic_channel.py`: Gate `save_alert` — when `NewStateValue=OK` in context,
  resolve matching open alerts instead of creating a new incident.
- `triage_algedonic_alerts.py`: Detect `NewStateValue=OK` in alert context
  (including nested SNS payloads) and auto-resolve instead of escalating.

**Fix** (scaffold branch `task/1217176582901797`, commit 631ddee5):
- `vsm/internal_scanner.py`: `_scan_project_alarms` auto-resolves proposals and
  algedonic alerts when all CloudWatch alarms recover. Added cooldown dedup.

## Bug 2: VSM Control Plane Module Missing

**Root cause**: `from vsm.vsm_control_plane import ...` fails inside the Letta
server sandbox because `vsm/__init__.py` imports heavy transitive dependencies
(Letta server packages) that aren't available in the tool execution sandbox.

**Fix**: Added `importlib.util` fallback that loads `vsm_control_plane.py` directly
by file path, bypassing the package `__init__.py`. Applied to both
`letta_vsm_control_tools.py` (registered tools) and `vsm_control_tools.py` (skill).

## PRs

- Scaffold PR #381: https://github.com/dmoskov/skof/pull/381 — **MERGED** 2026-08-05
  (branch task/1217176582892596 — escalation pipeline + import fix)
- Scaffold PR #382: https://github.com/dmoskov/skof/pull/382 — **MERGED** 2026-08-05
  (branch task/1217176582901797 — internal scanner + import fix)

## Tests

29 new unit tests in `test_cloudwatch_ok_resolution.py` — all passing.
Covers alarm name extraction, severity parsing, recovery detection, and
OK-state auto-resolution.

## Follow-up: Asana Sync Recovery Delay

The underlying Asana sync alarm was legitimately red >4h before self-recovering
(7 escalation reports between alarm and recovery). The automated recovery
eventually worked, but the delay warrants investigation into why the sync
worker took that long to recover. This is a separate concern from the
escalation pipeline bug.
