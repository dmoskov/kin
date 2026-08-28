# REPO-IDENTITY-AUDIT: internal_scanner repo identity availability

Audit date: 2026-08-21
Task: https://app.asana.com/1/19421316985/project/1211710875848660/task/1217714375065501
Parent bug: Dispatch layer lacks repo-identity tagging — 4th cross-project misdispatch (eia_match)

## Summary

The `internal_scanner` module (in `skof/claude-code-scaffold/scripts/maintenance/vsm/internal_scanner.py`)
**does** have repo identity available at scan time via two fields on the `InternalScanner` class.
However, the `InternalInsight` dataclass and the evidence dicts attached to insights do **not**
carry a `source_repo` field, creating a gap that causes misdispatches when the system-level
scan path is used.

## Where repo identity IS available

### 1. `InternalScanner.__init__` (line 75-84)

```python
def __init__(self, lookback_days=7, db=None, repo_path=None, project_id=None):
    self._repo_path = Path(repo_path) if repo_path else None
    self.project_id = project_id
```

Both `repo_path` (filesystem path to the cloned repo) and `project_id` (logical project name
like "family-tree", "pan", etc.) are set at construction time.

### 2. Per-project fan-out path (`project_proactive_cycle.py`, line 67-73)

```python
scanner = InternalScanner(
    lookback_days=lookback_days,
    repo_path=repo_path,  # <-- cloned repo path, e.g. /tmp/proactive/kin
    project_id=project_name,  # <-- e.g. "family-tree"
)
```

In this path, repo identity is correctly scoped — the scanner only sees files from one repo.

### 3. `_get_repo_root()` (line 95-141)

Returns the filesystem root used by all file-scanning methods (`_scan_code_quality`,
`_scan_dead_code`, `_scan_stale_docs`, etc.). When `self._repo_path` is set (per-project
mode), it returns that path directly.

### 4. `create_proposals_from_insights()` (line 5286-5362)

Accepts `project_id` parameter and passes it through to `S4Intelligence.create_proposal()`,
which stores it on the `Proposal` object. This propagates to the Asana task's "Project"
custom field via `_get_project_enum_gid()`.

### 5. Project registry (`common/project_config.py`, line 23-53)

`PROJECT_REPOS` maps all 22+ project names to `(owner, repo, branch)` tuples.
This is the canonical mapping between project names and GitHub repos.

## Where tasks are emitted WITHOUT repo tagging

### CRITICAL GAP 1: `InternalInsight` dataclass (line 43-59)

```python
# REPO-IDENTITY-AUDIT: Missing source_repo field
@dataclass
class InternalInsight:
    insight_type: str
    title: str
    description: str
    evidence: dict[str, Any]
    recommended_agents: list[str]
    estimated_tokens: int
    urgency: str
    impact: str
    needs_llm_development: bool = False
    # ❌ No source_repo field
```

The dataclass has no `source_repo` (or equivalent) field. All downstream consumers
inherit this gap.

### CRITICAL GAP 2: `_scan_code_quality()` evidence dicts (line 956-1016)

When `_scan_code_quality()` creates insights, it includes `evidence["file"]` with a
path relative to `_get_repo_root()`, but does **not** include the repo name:

```python
# Line 846-854 (_check_bare_excepts):
evidence={"file": file_path, "line": i, "issue": "bare_except", ...}
# ❌ No "source_repo" key

# Line 888-901 (_check_large_functions):
evidence={"file": file_path, "function": largest_func.name, ...}
# ❌ No "source_repo" key

# Line 934-952 (_check_hardcoded_secrets):
evidence={"file": file_path, "line": i, "issue": "hardcoded_secret", ...}
# ❌ No "source_repo" key
```

### CRITICAL GAP 3: `_scan_dead_code()` evidence dicts

The dead code scanner (`_identify_dead_code_candidates`, line 2396-2424) produces
candidates with `(func_name, file_path, line_no, external_refs)` but no repo identifier.
This is the exact scanner that produced the "Potential dead code: function eia_match"
misdispatch targeting `analysis/build_stocks.py`.

### CRITICAL GAP 4: Other repo-scoped scanners

All the following scanners produce `InternalInsight` objects without a `source_repo` field:
- `_scan_stale_docs()` — evidence contains `"file"` but no repo
- `_scan_test_coverage_gaps()` — evidence contains `"file"` but no repo
- `_scan_excused_debt()` — evidence contains `"file"` but no repo
- `_insights_from_inline_suppressions()` — evidence contains `"file"` but no repo

### GAP 5: `create_proposals_from_insights()` context dict (line 5311-5315)

```python
context = {
    "insight": insight.evidence,
    "source": "s3_star_audit",
}
# ❌ No "source_repo" or "repository" key in context
```

The context dict passed to `S4Intelligence.create_proposal()` does NOT include a
`source_repo` or `repository` field. This means `_get_project_enum_gid()` strategy 1
(`context.repository`) will never match for scanner-generated proposals. Routing
falls back to `proposal.project_id`, which IS set correctly in per-project fan-out
mode but may be None or incorrect in system-level scans.

## Root cause of misdispatches

The misdispatch chain:

1. **System-level scan** (not per-project fan-out) runs `_scan_code_quality()` or
   `_scan_dead_code()` from the monorepo root (`skof/`)
2. Git log finds files like `analysis/build_stocks.py` (which lives in the `analysis/`
   subdirectory of the monorepo, NOT in `claude-code-scaffold/`)
3. An `InternalInsight` is created with `evidence["file"] = "analysis/build_stocks.py"`
   but no `source_repo` field
4. `create_proposals_from_insights()` is called without `project_id` (or with the
   scaffold project_id)
5. The Asana task gets the "claude-code-scaffold" project tag
6. `meta_orchestrator` dispatches to the scaffold executor
7. Executor clones the scaffold repo, can't find `analysis/build_stocks.py`, wastes ~$1.64

## Recommended fix locations

### Fix A: Add `source_repo` to `InternalInsight` (line 43-59)

Add an optional `source_repo: str | None = None` field to the dataclass.

### Fix B: Populate `source_repo` in all repo-scoped scanners

In `_scan_code_quality()` (line 970), the scanner already calls `self._get_repo_root()`.
`self.project_id` is available. Add `source_repo=self.project_id` to every
`InternalInsight(...)` constructor call in:
- `_check_bare_excepts()` (line 835)
- `_check_large_functions()` (line 880)
- `_check_hardcoded_secrets()` (line 934)
- `_build_coverage_insight()` (line 1085)
- `_identify_dead_code_candidates()` → insight builder (wherever dead code insights are created)
- `_build_suppression_insight()` (line 2033)
- `_scan_stale_docs()` insight constructors
- `_insight_for_deleted_test()` (line 1521)
- `_insight_for_probed_test()` (line 1553)

### Fix C: Include `source_repo` in proposal context (line 5311-5315)

```python
context = {
    "insight": insight.evidence,
    "source": "s3_star_audit",
    "repository": f"{owner}/{repo}",  # from PROJECT_REPOS[insight.source_repo]
}
```

This enables `_get_project_enum_gid()` strategy 1 to work for scanner proposals.

### Fix D: Pre-dispatch filter (subtask 4)

Even with correct tagging, a pre-dispatch filter in `execute_batch()` or
`meta_orchestrator._dispatch_single_task()` should verify that the target file
exists in the executor's repo before dispatching.

## Call sites that need patching (for subtask 2)

| File | Line | Method | What to add |
|------|------|--------|------------|
| `vsm/internal_scanner.py` | 43-59 | `InternalInsight` dataclass | `source_repo: str \| None = None` field |
| `vsm/internal_scanner.py` | 835 | `_check_bare_excepts()` | Pass `source_repo=self.project_id` |
| `vsm/internal_scanner.py` | 880 | `_check_large_functions()` | Pass `source_repo=self.project_id` |
| `vsm/internal_scanner.py` | 934 | `_check_hardcoded_secrets()` | Pass `source_repo=self.project_id` |
| `vsm/internal_scanner.py` | 1085 | `_build_coverage_insight()` | Pass `source_repo=self.project_id` |
| `vsm/internal_scanner.py` | 2033 | `_build_suppression_insight()` | Pass `source_repo` param |
| `vsm/internal_scanner.py` | 1521 | `_insight_for_deleted_test()` | Pass `source_repo=self.project_id` |
| `vsm/internal_scanner.py` | 1553 | `_insight_for_probed_test()` | Pass `source_repo=self.project_id` |
| `vsm/internal_scanner.py` | 5311 | `create_proposals_from_insights()` | Add `"repository"` to context dict |
| `vsm/proactive_coordination.py` | 2486 | `_build_custom_fields()` | Use `source_repo` for project GID if `project_id` is missing |

## Verification

```bash
# After fix is applied, grep for the audit marker:
grep -n "REPO-IDENTITY-AUDIT" vsm/internal_scanner.py

# Verify all InternalInsight constructors pass source_repo:
grep -n "InternalInsight(" vsm/internal_scanner.py | grep -v "source_repo"
# (should return zero lines after fix)
```
