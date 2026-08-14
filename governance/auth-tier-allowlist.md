# Auth-tier allowlist: reviewed path for security-remediation tasks

## Background

Asana alert `d262fbc3-9fd0-44d5-a40d-18681acb910f` (source: `auto_approval_engine`)
blocked a task titled "Fix vulnerability in auth module" on the `vulnerability`
keyword. The escalating agent asked to loosen the pattern so security-remediation
tasks could flow automatically. S5's disposition (task GID `1217440437698313`'s
parent, `1217420...` chain) **upheld the block** and asked for something
different: a *reviewed allowlist path with human sign-off*, not a weaker keyword
filter.

The reasoning still applies here:

- A task title is not a diff. "Fix vulnerability" tells you nothing about
  whether the change actually reduces risk.
- Labels like "trusted agent" come from the same unreviewed pipeline the gate
  exists to check — they can't be used to justify skipping the check.
- The auth module was, at the time, the sickest subsystem in the fleet
  (recurring `auth_error` task GID `1217436332322156`; an Aug 9 self-patch,
  `#233`, that didn't hold; an Aug 13 credential-provisioning refactor, `#245`).
  Auto-merging an unreviewed "fix" into that module during an active incident
  is exactly the failure mode the keyword gate is there to catch.

This document defines the allowlist: the one path by which an auth-tier or
credential-tier change can still land without a human manually pulling the
branch and merging by hand, while keeping the keyword gate intact for everyone
who hasn't gone through it.

## What counts as auth-tier

A task/branch is auth-tier if its diff touches any of:

- `src/routes/auth.py` — session/login endpoints
- `src/database/` — connection handling, repository layer (credential and
  session storage)
- `src/ratelimit.py` — brute-force throttling for auth endpoints
- `deploy/` — service units, nginx config, deploy scripts (credential
  provisioning surface)
- `.githooks/` — the PII/secret pre-commit guard

This list is intentionally broader than "files containing the word password" —
it's about *where* code runs relative to credentials and sessions, not what a
grep happens to match.

## Allowlist criteria

A human reviewer may add an auth-tier task/branch to the approvals table below
only if **all** of the following hold:

1. **The reviewer read the actual diff**, not just the task title or
   description. Title-based trust ("says fix, so it's a fix") is explicitly
   disallowed — see Background.
2. **The change is a genuine remediation**, not a policy loosening. A PR that
   edits `auto_approval_engine` configuration, this file's criteria, or removes
   a blocked pattern does **not** qualify for self-allowlisting — that class of
   change needs its own separate human sign-off in the repo that owns the
   engine, never a same-PR allowlist entry.
3. **No new credential, token, or secret exposure** is introduced (logged in
   plaintext, written to a client-visible response, committed to the repo,
   etc.).
4. **Tests cover the change** — an auth-tier fix without a regression test is
   not reviewable as "done," it's reviewable as "unverified."
5. **The reviewer is a human**, not the agent that authored or escalated the
   task. Self-sign-off does not satisfy this list.

## Approved auth-tier tasks

Reviewers add a row here — via a direct commit or a normal reviewed PR into
`main`, never from the task branch being approved — once the criteria above are
met. The auto-merge check (`scripts/check_auth_tier_signoff.py`) reads this
table from `main` and only allows an auth-tier branch to auto-merge if its
branch name appears in the first column.

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| _(none yet)_ | | | | |

## How the gate works

1. The upstream `auto_approval_engine` keyword filter (`blocked_patterns`
   including `vulnerability`, `password`, `credential`, `secret key`, `CVE-`,
   etc.) still runs first, on every incoming task, regardless of this file.
   That filter decides whether a task is even allowed to become a branch and
   run through the pipeline. **This document does not change that filter and
   does not grant it any exception** — it lives in a separate infrastructure
   repository outside this project, and loosening it is explicitly out of
   scope for a same-project change (see criteria #2 above).
2. Once a task/branch exists in *this* repo, `.github/workflows/auto-merge.yml`
   normally auto-merges any branch whose CI passes, with no content review at
   all. That workflow now runs `scripts/check_auth_tier_signoff.py` first,
   which checks two tiers in severity order:
   - **Substrate-tier** (governance/substrate-tier-policy.md) — server image,
     container, and CI/deploy workflows. This is the higher-severity tier.
   - **Auth-tier** (this file) — credential, session, and auth-related code.
   If the branch touches a protected path and isn't listed in the relevant
   tier's approvals table, the merge is skipped and left for a human, with a
   `::warning` annotation explaining why.
3. Non-protected branches are unaffected — the check is a no-op for them.

This means: the keyword block stays exactly as strict as it is today for
everyone. The only thing these governance files add is a *documented, auditable*
way for a human who has actually reviewed a protected-tier diff to let that
specific, already-reviewed branch through this repo's own auto-merge, instead
of having to merge it by hand outside of CI.
