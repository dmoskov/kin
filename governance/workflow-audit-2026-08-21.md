# Workflow security audit: auto-merge and sync-task-branches

**Date**: 2026-08-21
**Auditor**: DevOps agent (Asana task 1217384055294079)
**Scope**: `.github/workflows/auto-merge.yml`, `.github/workflows/sync-task-branches.yml`
**Origin**: Filed by S5 during 2026-06-12 post-merge review of task/1215643829127576;
open two months unverified.

## Executive summary

Both workflows meet their security requirements. The auto-merge workflow gates
on CI success and enforces two-tier protected-path review (substrate-tier and
auth-tier) before merging any `task/**` branch. The sync-task-branches workflow
uses minimal permissions and triggers only on infrastructure-file changes.

**No dependabot auto-merge workflow exists in this repo.** The original Asana
task references "dependabot-auto-merge" — this appears to be a label mismatch.
The relevant workflow is `auto-merge.yml`, which auto-merges task branches, not
dependabot PRs. There is no `.github/dependabot.yml` configuration file either.

## auto-merge.yml

### Purpose
Merges `task/**` branches into main automatically when CI passes, then triggers
deploy. Uses direct merge commits (no PR required). Conflicting branches are
left for a human.

### Findings

| Control | Status | Detail |
|---|---|---|
| CI gate | PASS | `github.event.workflow_run.conclusion == 'success'` (line 25) — only triggers on CI workflow completion with success status |
| Branch scope | PASS | `startsWith(github.event.workflow_run.head_branch, 'task/')` (line 26) — only merges task branches, not arbitrary branches |
| Permissions | PASS | `permissions: contents: write` (line 19-20) — minimal, only what's needed for merge API |
| Token | PASS | Uses `secrets.GITHUB_TOKEN` (line 35, 64) — default workflow token, not a PAT with elevated privileges |
| Protected-path gate | PASS | Runs `scripts/check_auth_tier_signoff.py` (line 51) — blocks merge of branches touching substrate-tier or auth-tier paths without human sign-off in governance files |
| Conflict handling | PASS | gh API merge returns 409 on conflict (line 71) — exits gracefully, leaves for human |
| Branch cleanup | PASS | Deletes merged branch after successful merge (line 76) — prevents stale branch accumulation |
| Deploy trigger | PASS | Only deploys when merge succeeds (line 85) — `needs.merge.outputs.merged == 'true'` |

### Semver / dependabot scope
**Not applicable.** This workflow does not interact with dependabot. It merges
task branches produced by the agent pipeline. There is no semver filtering
because the scope filter is branch-name-based (`task/**`), not dependency-based.

### Risk notes
- The `workflow_run` trigger means this workflow runs with the **default branch's
  workflow definition**, not the task branch's version. This is correct — a task
  branch cannot modify its own merge criteria and have those changes take effect.
- Deploy runs in the same workflow invocation (via `deploy-reusable.yml`). This
  is intentional: a `GITHUB_TOKEN` merge does not re-trigger `on: push` events,
  so deploy must be called explicitly.

## sync-task-branches.yml

### Purpose
Keeps `task/**` branches up to date with main when infrastructure files change
(CI workflows, dependency manifests, Dockerfile). Merges main into each task
branch; conflict branches are skipped.

### Findings

| Control | Status | Detail |
|---|---|---|
| Trigger scope | PASS | `on.push.branches: [main]` with path filters — only fires when infrastructure files change on main |
| Path filters | PASS | `.github/workflows/**`, `requirements*.txt`, `package*.json`, `Dockerfile*`, `pyproject.toml` — limited to files that affect CI reproducibility |
| Manual dispatch | PASS | `workflow_dispatch: {}` — allows manual trigger for ad-hoc syncs |
| Permissions | PASS | `permissions: contents: write` at job level (line 20-21) — minimal |
| Token | PASS | `secrets.GITHUB_TOKEN` (line 27) — standard token, no elevated privileges |
| Conflict handling | PASS | `git merge --abort` on failure (line 68) — safe rollback, logs failure |
| Git identity | PASS | Uses `github-actions[bot]` identity (line 31-32) — standard, auditable |

### Risk notes
- The workflow iterates all `origin/task/*` branches. If the task branch count
  grows very large, this could hit GitHub API rate limits or runner timeouts.
  Current branch count is low; monitor if the pipeline scales up.
- Uses `shell: bash {0}` (line 35) which disables `set -e`. This is intentional:
  individual branch sync failures should not abort the entire run.

## deploy-reusable.yml (supporting context)

| Control | Status | Detail |
|---|---|---|
| Permissions | PASS | `permissions: contents: read` — read-only, deploy uses SSH secrets |
| Concurrency | PASS | `concurrency: group: deploy-production, cancel-in-progress: false` — prevents parallel deploys |
| Ref | PASS | Checks out `ref: main` explicitly — deploys from main, not from a stale ref |
| Health check | PASS | Verifies service is active and `/healthz` returns 200 before succeeding |

## Dependabot assessment

This repo has **no dependabot configuration**. If dependency auto-update is
desired in the future, a `.github/dependabot.yml` should be added with:

1. **Semver scope**: `allow: [dependency-type: direct]` with updates limited to
   `patch` and `minor` via `ignore` rules for major bumps.
2. **CI gate**: Dependabot PRs would go through the normal CI workflow (`ci.yml`)
   which runs lint, type checks, Python tests, JS tests, and smoke tests.
3. **Auto-merge**: A separate workflow (or `gh pr merge --auto`) could be added
   for dependabot PRs that pass CI, scoped to patch/minor only. This would be
   distinct from the task-branch auto-merge.
4. **Permissions**: Any dependabot auto-merge workflow should use minimal
   `permissions: contents: write, pull-requests: write` and nothing else.

This is a recommendation for future work, not a current gap — the repo does not
use dependabot today.

## S5 reviewer access gap

The S5 reviewer agent currently cannot perform post-merge diff reviews because:
- No GitHub API token configured in its sandbox
- No SSH binary available
- API token (if any) returns 401

This means post-merge reviews are inferred from task titles rather than actual
diffs. See `governance/s5-reviewer-access-policy.md` for the access requirements
and credential provisioning process.
