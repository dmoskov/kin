# Escalation Pipeline Fix - CloudWatch OK State Handling

Changes committed to dmoskov/skof (claude-code-scaffold) branch task/1217176582892596
Commit: 45baccd5
PR: https://github.com/dmoskov/skof/pull/381 (OPEN)

## Issues Fixed

1. **CloudWatch OK-state detection** (`algedonic_agent_loop.py`): Before routing
   alerts to triage agents, the loop now checks if referenced CloudWatch alarms
   have returned to OK state and auto-resolves those alerts. Prevents stale alarm
   alerts from being escalated after recovery.

2. **Severity parsing** (`algedonic_agent_loop.py`): Alerts with missing/unknown
   severity now get classified based on alarm count in context (1-2 alarms =
   urgent, 3+ = critical, OK state = warning). Fixes "[ESCALATION · unknown]".

3. **Recovery notification filtering** (`triage_algedonic_alerts.py`): Triage
   detects NewStateValue=OK in alert context (including nested SNS payloads) and
   auto-resolves those alerts instead of incrementing the debounce counter.

4. **vsm_control_plane import resilience** (`vsm_control_tools.py`,
   `letta_vsm_control_tools.py`): Added importlib fallback when the vsm package
   __init__.py fails to load in the Letta server sandbox. Fixes
   `No module named 'vsm.vsm_control_plane'` error.

5. **save_alert gate** (`algedonic_channel.py`): DatabaseAlertDispatcher.save_alert
   now checks for NewStateValue=OK and resolves matching open alerts instead of
   creating a new incident.

## Files Modified in Scaffold Repo

- scripts/maintenance/algedonic/algedonic_agent_loop.py
- scripts/maintenance/algedonic/algedonic_channel.py
- scripts/maintenance/algedonic/triage_algedonic_alerts.py
- scripts/maintenance/letta_vsm_control_tools.py
- .claude/skills/letta-tools/vsm_control_tools.py
- scripts/maintenance/tests/unit/test_cloudwatch_ok_resolution.py (new)

## Verification

Verified by task/1217176582772358 on 2026-08-05:
- All 4 defects from the task description are addressed by the fix
- Test coverage added for CloudWatch alarm name extraction, OK-state detection,
  severity parsing, and recovery notification filtering
- Fix branch rebased on scaffold main, PR #381 open and awaiting merge
