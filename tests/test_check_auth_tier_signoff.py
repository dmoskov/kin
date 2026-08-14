"""Tests for scripts/check_auth_tier_signoff.py.

This is the gate .github/workflows/auto-merge.yml runs before auto-merging a
task/** branch: protected-tier paths (see governance/auth-tier-allowlist.md and
governance/substrate-tier-policy.md) must have a matching human sign-off entry,
or the branch is left for manual merge.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_auth_tier_signoff import TIERS, approved_branches, check, tier_files  # noqa: E402

AUTH_ALLOWLIST_WITH_ENTRY = """\
# Auth-tier allowlist

## Approved auth-tier tasks

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| task/1217440437698313 | 1217440437698313 | dustin | 2026-08-13 | reviewed diff |

## How the gate works
"""

AUTH_ALLOWLIST_EMPTY = """\
# Auth-tier allowlist

## Approved auth-tier tasks

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| _(none yet)_ | | | | |
"""

SUBSTRATE_ALLOWLIST_WITH_ENTRY = """\
# Substrate-tier policy

## Approved substrate-tier tasks

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| task/reviewed-infra | 9999999 | dustin | 2026-08-14 | reviewed diff |
"""

SUBSTRATE_ALLOWLIST_EMPTY = """\
# Substrate-tier policy

## Approved substrate-tier tasks

| Branch | Asana Task GID | Reviewer | Date | Notes |
|---|---|---|---|---|
| _(none yet)_ | | | | |
"""

AUTH_TIER = next(t for t in TIERS if t["name"] == "auth")
SUBSTRATE_TIER = next(t for t in TIERS if t["name"] == "substrate")


def _allowlist_texts(auth="", substrate=""):
    return {
        AUTH_TIER["allowlist"]: auth,
        SUBSTRATE_TIER["allowlist"]: substrate,
    }


# ── tier_files ──────────────────────────────────────────────────────────


def test_tier_files_matches_auth_route():
    changed = ["src/routes/auth.py", "web/js/99-main.js"]
    assert tier_files(changed, AUTH_TIER["prefixes"]) == ["src/routes/auth.py"]


def test_tier_files_matches_database_prefix():
    changed = ["src/database/connection.py", "docs/TESTING.md"]
    assert tier_files(changed, AUTH_TIER["prefixes"]) == ["src/database/connection.py"]


def test_tier_files_empty_for_unrelated_change():
    changed = ["src/routes/people.py", "web/js/40-timeline.js"]
    assert tier_files(changed, AUTH_TIER["prefixes"]) == []


def test_tier_files_matches_dockerfile():
    changed = ["Dockerfile", "src/routes/people.py"]
    assert tier_files(changed, SUBSTRATE_TIER["prefixes"]) == ["Dockerfile"]


def test_tier_files_matches_workflow():
    changed = [".github/workflows/ci.yml", "tests/test_foo.py"]
    assert tier_files(changed, SUBSTRATE_TIER["prefixes"]) == [".github/workflows/ci.yml"]


def test_tier_files_matches_docker_compose():
    changed = ["docker-compose.yml"]
    assert tier_files(changed, SUBSTRATE_TIER["prefixes"]) == ["docker-compose.yml"]


# ── approved_branches ───────────────────────────────────────────────────


def test_approved_branches_parses_auth_table():
    assert approved_branches(AUTH_ALLOWLIST_WITH_ENTRY, AUTH_TIER["header"]) == {
        "task/1217440437698313"
    }


def test_approved_branches_ignores_placeholder_row():
    assert approved_branches(AUTH_ALLOWLIST_EMPTY, AUTH_TIER["header"]) == set()


def test_approved_branches_parses_substrate_table():
    assert approved_branches(SUBSTRATE_ALLOWLIST_WITH_ENTRY, SUBSTRATE_TIER["header"]) == {
        "task/reviewed-infra"
    }


# ── check: auth-tier ───────────────────────────────────────────────────


def test_check_allows_non_protected_change():
    ok, _ = check("task/999", ["src/routes/people.py"], _allowlist_texts(AUTH_ALLOWLIST_EMPTY))
    assert ok is True


def test_check_blocks_unapproved_auth_tier_change():
    ok, message = check("task/999", ["src/routes/auth.py"], _allowlist_texts(AUTH_ALLOWLIST_EMPTY))
    assert ok is False
    assert "task/999" in message
    assert "auth-tier-allowlist.md" in message


def test_check_allows_approved_auth_tier_change():
    ok, _ = check(
        "task/1217440437698313",
        ["src/routes/auth.py"],
        _allowlist_texts(AUTH_ALLOWLIST_WITH_ENTRY),
    )
    assert ok is True


def test_check_blocks_auth_tier_change_even_if_a_different_branch_is_approved():
    ok, _ = check(
        "task/some-other-branch",
        ["src/database/connection.py"],
        _allowlist_texts(AUTH_ALLOWLIST_WITH_ENTRY),
    )
    assert ok is False


# ── check: substrate-tier ──────────────────────────────────────────────


def test_check_blocks_unapproved_dockerfile_change():
    ok, message = check(
        "task/999", ["Dockerfile"], _allowlist_texts(substrate=SUBSTRATE_ALLOWLIST_EMPTY)
    )
    assert ok is False
    assert "substrate-tier" in message
    assert "substrate-tier-policy.md" in message


def test_check_blocks_unapproved_workflow_change():
    ok, message = check(
        "task/999",
        [".github/workflows/deploy.yml"],
        _allowlist_texts(substrate=SUBSTRATE_ALLOWLIST_EMPTY),
    )
    assert ok is False
    assert "substrate-tier" in message


def test_check_allows_approved_substrate_change():
    ok, _ = check(
        "task/reviewed-infra",
        ["Dockerfile"],
        _allowlist_texts(substrate=SUBSTRATE_ALLOWLIST_WITH_ENTRY),
    )
    assert ok is True


def test_check_blocks_docker_compose_change():
    ok, message = check(
        "task/999",
        ["docker-compose.yml"],
        _allowlist_texts(substrate=SUBSTRATE_ALLOWLIST_EMPTY),
    )
    assert ok is False
    assert "substrate-tier" in message


# ── check: tier precedence ─────────────────────────────────────────────


def test_substrate_tier_takes_precedence_over_auth_tier():
    ok, message = check(
        "task/999",
        [".github/workflows/auto-merge.yml", "src/routes/auth.py"],
        _allowlist_texts(
            auth=AUTH_ALLOWLIST_EMPTY,
            substrate=SUBSTRATE_ALLOWLIST_EMPTY,
        ),
    )
    assert ok is False
    assert "substrate-tier" in message


def test_substrate_approved_but_auth_not_still_passes_if_substrate_checked_first():
    ok, _ = check(
        "task/reviewed-infra",
        [".github/workflows/ci.yml", "src/routes/auth.py"],
        _allowlist_texts(
            auth=AUTH_ALLOWLIST_EMPTY,
            substrate=SUBSTRATE_ALLOWLIST_WITH_ENTRY,
        ),
    )
    assert ok is True
