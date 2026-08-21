# S5 reviewer agent: repository access policy

**Created**: 2026-08-21
**Asana task**: 1217384055294079
**Status**: Defining requirements; credentials not yet provisioned

## Background

The VSM System 5 (policy) reviewer agent performs post-merge reviews of task
branches after they land on main. These reviews verify that merged changes align
with governance policies, including the substrate-tier and auth-tier gates
defined in this directory.

Since the 2026-06-12 post-merge review of task/1215643829127576, the S5 reviewer
has been unable to read actual diffs. Its sandbox lacks:

1. A GitHub API token with repo read access
2. SSH binary (for git clone/fetch)
3. Working API authentication (current token returns 401)

This means reviews are inferred from task titles and Asana metadata — not from
the code changes themselves. For a policy agent whose job is to verify that
changes comply with governance rules, this is a significant capability gap.

## Required access

The S5 reviewer needs **read-only** access to this repository. Specifically:

| Capability | GitHub scope | Purpose |
|---|---|---|
| Read repository contents | `repo:read` or fine-grained `contents: read` | Fetch diffs, read governance files from main |
| Read pull requests | `pull_requests: read` | Read PR metadata if PRs are used |
| Read commit status | `statuses: read` | Verify CI passed before reviewing |

**The reviewer does NOT need and MUST NOT have:**
- `contents: write` — it reviews, it does not merge or push
- `admin` — no repo settings access
- `actions: write` — no workflow dispatch capability
- Any token with access to other repositories (scope to `dmoskov/kin` only)

## Credential provisioning process

1. **Create a fine-grained personal access token** (GitHub Settings > Developer
   settings > Fine-grained tokens) scoped to:
   - Repository: `dmoskov/kin` only
   - Permissions: Contents (read), Pull requests (read), Commit statuses (read)
   - Expiration: 90 days (with calendar reminder to rotate)

2. **Store the token** in the S5 reviewer agent's environment as
   `GITHUB_TOKEN_KIN_READONLY`. Do not reuse the pipeline's write token.

3. **Verify access** by running from the reviewer sandbox:
   ```
   curl -H "Authorization: token $GITHUB_TOKEN_KIN_READONLY" \
     https://api.github.com/repos/dmoskov/kin/commits/main
   ```
   Expected: 200 with commit data. If 401/403, the token is misconfigured.

4. **Install git** (or a minimal HTTP client) in the reviewer sandbox so it can
   fetch diffs via:
   ```
   gh api repos/dmoskov/kin/compare/main...task/BRANCH --jq '.files[].patch'
   ```

## Audit trail

Token creation and rotation should be logged. The reviewer agent should include
the token's last-four characters in its review metadata so credential rotation
can be verified.

## Scope limitation

This policy covers read access to `dmoskov/kin` (the family-tree project) only.
If the S5 reviewer needs access to other repositories in the fleet, each repo
should have its own scoped token and access policy — a single broad-access token
across all repos is explicitly prohibited.

## Action items

| # | Action | Owner | Status |
|---|---|---|---|
| 1 | Create fine-grained read-only PAT for dmoskov/kin | Dustin (human) | Pending |
| 2 | Install git/gh CLI in S5 reviewer sandbox | Dustin (human) | Pending |
| 3 | Configure GITHUB_TOKEN_KIN_READONLY in reviewer env | Dustin (human) | Pending |
| 4 | Verify 200 response from commits API | S5 reviewer | Blocked on #1-3 |
| 5 | Run first real diff-based post-merge review | S5 reviewer | Blocked on #4 |
