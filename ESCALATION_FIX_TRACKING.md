# Escalation Pipeline Fix - CloudWatch OK State Handling

## Fix Branches (scaffold repo dmoskov/skof)

### Branch: task/1217176449720196 (this task)
Commit: 785f48c9

### Branch: task/1217176582892596 (sibling task)
Commit: 45baccd5

## Defects Fixed

1. **CloudWatch OK-state detection in algedonic agent loop**: Before routing
   alerts to triage agents, check if referenced CloudWatch alarms have returned
   to OK state and auto-resolve those alerts. Prevents stale alarm alerts from
   being escalated after recovery.

2. **Severity parsing for CloudWatch alerts**: Alerts with missing/unknown
   severity now get properly classified based on alarm count in context
   (1-2 alarms = urgent, 3+ = critical, OK state = warning). Prevents
   "[ESCALATION · unknown]" labels.

3. **CloudWatch recovery (OK) notification filtering in triage**: The triage
   system now detects NewStateValue=OK in alert context (including nested SNS
   message payloads) and auto-resolves those alerts instead of incrementing the
   debounce counter and creating tasks.

4. **vsm_get_active_alerts import resilience**: Added importlib fallback when
   the vsm package __init__.py fails to load (heavy transitive deps in Letta
   server sandbox). Fixes "No module named 'vsm.vsm_control_plane'" error.

5. **save_alert gate in DatabaseAlertDispatcher**: When an alert's context
   contains NewStateValue=OK, resolve matching open alerts instead of creating
   a new incident.

## Files Modified (scaffold repo)
- scripts/maintenance/algedonic/algedonic_agent_loop.py
- scripts/maintenance/algedonic/algedonic_channel.py
- scripts/maintenance/algedonic/triage_algedonic_alerts.py
- scripts/maintenance/letta_vsm_control_tools.py
- .claude/skills/letta-tools/vsm_control_tools.py
- scripts/maintenance/tests/unit/test_cloudwatch_ok_resolution.py (new)

## Test Results
21 tests pass covering all new CloudWatch OK detection logic.
