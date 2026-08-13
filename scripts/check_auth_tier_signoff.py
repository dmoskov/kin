#!/usr/bin/env python3
"""Block auto-merge of task branches that touch auth-tier code without sign-off.

Companion to governance/auth-tier-allowlist.md. .github/workflows/auto-merge.yml
runs this before merging any task/** branch; a nonzero exit means the branch
touches an auth-tier path with no matching entry in the allowlist's approvals
table, and the workflow leaves it for a human to merge by hand instead.
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

ALLOWLIST_PATH = "governance/auth-tier-allowlist.md"
APPROVALS_HEADER = "## Approved auth-tier tasks"


def auth_tier_files(changed_files):
    """Changed files that fall under an auth-tier path prefix."""
    return [f for f in changed_files if any(f.startswith(p) for p in AUTH_TIER_PATH_PREFIXES)]


def approved_branches(allowlist_text):
    """Branch names listed in the first column of the approvals table."""
    if APPROVALS_HEADER not in allowlist_text:
        return set()
    _, _, after_header = allowlist_text.partition(APPROVALS_HEADER)
    branches = set()
    for line in after_header.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if branches:
                break  # table ended
            continue
        cell = stripped.strip("|").split("|")[0].strip()
        if not cell or cell.startswith("-") or cell == "Branch":
            continue
        if cell.startswith("_("):
            continue  # placeholder row, e.g. "_(none yet)_"
        branches.add(cell)
    return branches


def check(branch, changed_files, allowlist_text):
    """Return (ok, message) for whether `branch` may auto-merge."""
    touched = auth_tier_files(changed_files)
    if not touched:
        return True, "no auth-tier files touched"
    if branch in approved_branches(allowlist_text):
        return True, (
            f"auth-tier files touched ({', '.join(touched)}) but '{branch}' "
            f"has a signed-off entry in {ALLOWLIST_PATH}"
        )
    return False, (
        f"'{branch}' touches auth-tier path(s) {touched} with no human "
        f"sign-off entry in {ALLOWLIST_PATH} — see that file for the review "
        f"criteria and process"
    )


def _git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main(argv):
    if len(argv) != 4:
        print(f"usage: {argv[0]} <branch> <base-ref> <head-ref>", file=sys.stderr)
        return 2
    _, branch, base_ref, head_ref = argv
    changed = [f for f in _git("diff", "--name-only", f"{base_ref}...{head_ref}").splitlines() if f]
    allowlist_text = _git("show", f"{base_ref}:{ALLOWLIST_PATH}")
    ok, message = check(branch, changed, allowlist_text)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
