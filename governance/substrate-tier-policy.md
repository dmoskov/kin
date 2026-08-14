# Substrate-tier policy: server image, container, and CI/deploy governance

## Background

On 2026-08-14 (~13:00 UTC), the pipeline created task GID `1217497972703307`
(agent class: DEVOPS) titled "Rebuild and redeploy the Letta server image
(merged server patches are inert; cg S5 still 502)." The task attempted to
rebuild and redeploy the server hosting all 52 agents — including the
governance layer itself. The attempt failed (rc=1), but a live branch was
pushed.

This event exposed a class of change that the existing auth-tier gate
(governance/auth-tier-allowlist.md) does not cover: modifications to the
**substrate** — the server image, container orchestration, and CI/deploy
workflows that governance runs on. A successful unreviewed substrate change
would alter the runtime environment for every agent, including the policy and
intelligence agents that are supposed to oversee such changes. This is
self-referential risk: the system modifying the machinery it is governed by.

This document establishes the substrate tier — a higher-severity gate than
auth-tier — and defines the human-review requirements for substrate changes.

## What counts as substrate-tier

A task/branch is substrate-tier if its diff touches any of:

- `Dockerfile` — server image definition
- `docker-compose.yml` — container orchestration configuration
- `.github/workflows/` — CI pipelines, auto-merge logic, deploy workflows
- `.github/actions/` — reusable CI action definitions

This is deliberately scoped to files that define **how the system is built,
tested, deployed, and auto-governed**. Application code (even code that runs
on the server) is not substrate-tier — it goes through the existing auth-tier
or standard auto-merge path.

### Why these files and not others

- `Dockerfile` / `docker-compose.yml`: define the container image and runtime.
  An unreviewed change here can inject arbitrary code into the server that
  every agent and every governance check runs on.
- `.github/workflows/`: define CI, auto-merge, and deploy logic. An unreviewed
  change can disable gates, alter merge criteria, or deploy without checks.
- `.github/actions/`: reusable action definitions consumed by workflows. Same
  risk surface as workflows.

## Allowlist criteria

A human reviewer may add a substrate-tier task/branch to the approvals table
below only if **all** of the following hold:

1. **The reviewer read the actual diff** — every line, not a summary. Substrate
   diffs tend to be short; there is no excuse for title-based trust here.
2. **The change does not weaken any governance gate**. A PR that edits
   auto-merge criteria, removes a blocked-path check, or loosens CI
   requirements does NOT qualify for self-allowlisting — it requires a
   separate, out-of-band human decision.
3. **The change does not introduce new network exposure, credential access, or
   privilege escalation** in the server image or deploy pipeline.
4. **The change has been tested** — either by CI on the branch or by a local
   reproduction. "It looks right" is not a test.
5. **The reviewer is a human**, not the agent that authored or escalated the
   task. Self-sign-off does not satisfy this list.
6. **The reviewer understands the blast radius**: a substrate change affects
   the runtime for all agents and governance processes, not just the project
   that originated the branch.

## Approved substrate-tier tasks

Reviewers add a row here — via a direct commit or a normal reviewed PR into
`main`, never from the task branch being approved — once the criteria above
are met. The check script (`scripts/check_auth_tier_signoff.py`) reads this
table from `main` and only allows a substrate-tier branch to auto-merge if
its branch name appears in the first column.

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| _(none yet)_ | | | | |

## How the gate works

1. `.github/workflows/auto-merge.yml` runs `scripts/check_auth_tier_signoff.py`
   before merging any `task/**` branch.
2. The script checks changed files against two tiers, in severity order:
   **substrate-tier** (this document) first, then **auth-tier**
   (governance/auth-tier-allowlist.md).
3. If a branch touches substrate-tier paths and is not listed in the approvals
   table above, the auto-merge is blocked and left for a human, with a
   `::warning` annotation explaining why.
4. A branch that touches both substrate-tier and auth-tier paths is blocked
   under the substrate tier (the higher-severity gate applies).
5. Non-protected branches are unaffected — the check is a no-op for them.

## Cross-repo note

The event that prompted this policy involved a branch in a **separate
infrastructure repository** (task GID `1217497972703307`), not this repo.
This policy protects *this* repo's substrate surface. The same pattern should
be replicated in any repository that hosts infrastructure code (Letta server
configs, scaffold repos, Terraform/CDK definitions) — those repos need their
own substrate-tier gates. Until that is done, the pipeline's ability to push
substrate-level branches in other repos remains ungoverned.

## Incident record

| Date | Task GID | Description | Outcome |
|---|---|---|---|
| 2026-08-14 | 1217497972703307 | Pipeline (DEVOPS agent) attempted Letta server rebuild+redeploy; referenced "merged server patches" not in governance ledger; noted "cg S5 still 502" | Failed rc=1; branch pushed but not merged. Prompted creation of this policy. |
