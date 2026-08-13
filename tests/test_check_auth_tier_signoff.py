"""Tests for scripts/check_auth_tier_signoff.py.

This is the gate .github/workflows/auto-merge.yml runs before auto-merging a
task/** branch: auth-tier paths (see governance/auth-tier-allowlist.md) must
have a matching human sign-off entry, or the branch is left for manual merge.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_auth_tier_signoff import approved_branches, auth_tier_files, check  # noqa: E402

ALLOWLIST_WITH_ENTRY = """\
# Auth-tier allowlist

## Approved auth-tier tasks

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| task/1217440437698313 | 1217440437698313 | dustin | 2026-08-13 | reviewed diff |

## How the gate works
"""

ALLOWLIST_EMPTY = """\
# Auth-tier allowlist

## Approved auth-tier tasks

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| _(none yet)_ | | | | |
"""


def test_auth_tier_files_matches_auth_route():
    changed = ["src/routes/auth.py", "web/js/99-main.js"]
    assert auth_tier_files(changed) == ["src/routes/auth.py"]


def test_auth_tier_files_matches_database_prefix():
    changed = ["src/database/connection.py", "docs/TESTING.md"]
    assert auth_tier_files(changed) == ["src/database/connection.py"]


def test_auth_tier_files_empty_for_unrelated_change():
    changed = ["src/routes/people.py", "web/js/40-timeline.js"]
    assert auth_tier_files(changed) == []


def test_approved_branches_parses_table():
    assert approved_branches(ALLOWLIST_WITH_ENTRY) == {"task/1217440437698313"}


def test_approved_branches_ignores_placeholder_row():
    assert approved_branches(ALLOWLIST_EMPTY) == set()


def test_check_allows_non_auth_tier_change_regardless_of_allowlist():
    ok, _ = check("task/999", ["src/routes/people.py"], ALLOWLIST_EMPTY)
    assert ok is True


def test_check_blocks_unapproved_auth_tier_change():
    ok, message = check("task/999", ["src/routes/auth.py"], ALLOWLIST_EMPTY)
    assert ok is False
    assert "task/999" in message
    assert "governance/auth-tier-allowlist.md" in message


def test_check_allows_approved_auth_tier_change():
    ok, _ = check("task/1217440437698313", ["src/routes/auth.py"], ALLOWLIST_WITH_ENTRY)
    assert ok is True


def test_check_blocks_auth_tier_change_even_if_a_different_branch_is_approved():
    ok, _ = check("task/some-other-branch", ["src/database/connection.py"], ALLOWLIST_WITH_ENTRY)
    assert ok is False
