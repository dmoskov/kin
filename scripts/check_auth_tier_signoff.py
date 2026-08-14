#!/usr/bin/env python3
"""Block auto-merge of task branches that touch protected-tier code without sign-off.

Companion to governance/auth-tier-allowlist.md and governance/substrate-tier-policy.md.
.github/workflows/auto-merge.yml runs this before merging any task/** branch;
a nonzero exit means the branch touches a protected path with no matching entry
in the relevant allowlist's approvals table, and the workflow leaves it for a
human to merge by hand instead.

Two tiers exist, checked in order of severity (highest first):

  substrate-tier  — files that define the server image, container orchestration,
                    or CI/deploy workflows.  Changes here can alter the runtime
                    that governance itself runs on.
  auth-tier       — files that handle credentials, sessions, or auth logic.

A branch that touches both tiers is reported under the higher (substrate) tier.
"""

import subprocess
import sys

AUTH_TIER_PATH_PREFIXES = (
    "src/routes/auth.py",
    "src/database/",
    "src/ratelimit.py",
    "deploy/",
    ".githooks/",
)

SUBSTRATE_TIER_PATH_PREFIXES = (
    "Dockerfile",
    "docker-compose.yml",
    ".github/workflows/",
    ".github/actions/",
)

TIERS = [
    {
        "name": "substrate",
        "prefixes": SUBSTRATE_TIER_PATH_PREFIXES,
        "allowlist": "governance/substrate-tier-policy.md",
        "header": "## Approved substrate-tier tasks",
    },
    {
        "name": "auth",
        "prefixes": AUTH_TIER_PATH_PREFIXES,
        "allowlist": "governance/auth-tier-allowlist.md",
        "header": "## Approved auth-tier tasks",
    },
]


def tier_files(changed_files, prefixes):
    """Changed files that fall under any of the given path prefixes."""
    return [f for f in changed_files if any(f.startswith(p) for p in prefixes)]


def approved_branches(allowlist_text, header):
    """Branch names listed in the first column of the approvals table."""
    if header not in allowlist_text:
        return set()
    _, _, after_header = allowlist_text.partition(header)
    branches = set()
    for line in after_header.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if branches:
                break
            continue
        cell = stripped.strip("|").split("|")[0].strip()
        if not cell or cell.startswith("-") or cell == "Branch":
            continue
        if cell.startswith("_("):
            continue
        branches.add(cell)
    return branches


def check(branch, changed_files, allowlist_texts):
    """Return (ok, message) for whether `branch` may auto-merge.

    allowlist_texts maps allowlist path -> file contents.
    """
    for tier in TIERS:
        touched = tier_files(changed_files, tier["prefixes"])
        if not touched:
            continue
        al_text = allowlist_texts.get(tier["allowlist"], "")
        if branch in approved_branches(al_text, tier["header"]):
            return True, (
                f"{tier['name']}-tier files touched ({', '.join(touched)}) but "
                f"'{branch}' has a signed-off entry in {tier['allowlist']}"
            )
        return False, (
            f"'{branch}' touches {tier['name']}-tier path(s) {touched} with no "
            f"human sign-off entry in {tier['allowlist']} — see that file for "
            f"the review criteria and process"
        )
    return True, "no protected-tier files touched"


def _git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _read_allowlist(base_ref, path):
    """Read an allowlist file from `base_ref`; return empty string if missing."""
    try:
        return _git("show", f"{base_ref}:{path}")
    except subprocess.CalledProcessError:
        return ""


def main(argv):
    if len(argv) != 4:
        print(f"usage: {argv[0]} <branch> <base-ref> <head-ref>", file=sys.stderr)
        return 2
    _, branch, base_ref, head_ref = argv
    changed = [f for f in _git("diff", "--name-only", f"{base_ref}...{head_ref}").splitlines() if f]
    allowlist_texts = {
        tier["allowlist"]: _read_allowlist(base_ref, tier["allowlist"]) for tier in TIERS
    }
    ok, message = check(branch, changed, allowlist_texts)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
