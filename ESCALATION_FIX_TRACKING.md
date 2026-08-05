# Escalation Pipeline Fix - CloudWatch OK State Handling

## Fix attempt 2 (2026-08-05, task/1217176449770755)

Changes committed to dmoskov/skof (claude-code-scaffold) branch task/1217176449770755
Commit: 911eb5c3

### Bug 1: CloudWatch OK notifications treated as incidents

Three-layer fix to prevent ALARM→OK transitions from incrementing escalation counters:

1. **internal_scanner.py** — `_scan_project_alarms` now also queries OK-state alarms
   and auto-resolves corresponding algedonic_alerts via `_auto_resolve_cleared_alarms`
2. **algedonic_channel.py** — `save_alert` detects CloudWatch OK transitions via
   `_is_cloudwatch_ok_transition` and resolves existing alerts instead of creating new ones
3. **triage_algedonic_alerts.py** — `is_cloudwatch_ok_transition` skips OK-state
   notifications during triage

### Bug 2: VSM control plane module missing

**letta_vsm_control_tools.py** — replaced single hardcoded path
(`/workspace/claude-code-scaffold/scripts/maintenance`) with fallback path
resolution trying multiple known checkout locations.

### Files modified in scaffold repo:
- scripts/maintenance/algedonic/algedonic_channel.py
- scripts/maintenance/algedonic/triage_algedonic_alerts.py
- scripts/maintenance/vsm/internal_scanner.py
- scripts/maintenance/letta_vsm_control_tools.py
- scripts/maintenance/tests/unit/test_cloudwatch_ok_resolution.py (new)

---

## Fix attempt 1 (2026-08-04, task/1217176582892596) — never merged

Changes committed to dmoskov/skof branch task/1217176582892596 (commit 45baccd5)
but the branch was never merged to main. The fix below supersedes it.
