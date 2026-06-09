"""Tests for the db_transaction context manager: commit on success,
rollback on exception, and real integrity-error types (no string matching)."""

from __future__ import annotations

import pytest

from database.connection import INTEGRITY_ERRORS, db_transaction, init_db
from database.repository import _execute, _fetchone, _ph


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", path)
    init_db(path)
    return path


def _editor_count(db_path) -> int:
    with db_transaction(db_path) as conn:
        row = _fetchone(conn, "SELECT COUNT(*) AS n FROM tree_editors")
    assert row is not None
    return row["n"]


def test_commits_on_success(db_path):
    with db_transaction(db_path) as conn:
        _execute(
            conn,
            f"INSERT INTO tree_editors (email, role) VALUES ({_ph(2)})",
            ("a@example.com", "editor"),
        )
    assert _editor_count(db_path) == 1


def test_rolls_back_on_exception(db_path):
    with pytest.raises(RuntimeError, match="boom"):
        with db_transaction(db_path) as conn:
            _execute(
                conn,
                f"INSERT INTO tree_editors (email, role) VALUES ({_ph(2)})",
                ("a@example.com", "editor"),
            )
            raise RuntimeError("boom")
    assert _editor_count(db_path) == 0


def test_duplicate_insert_raises_integrity_error(db_path):
    """Duplicate keys surface as a typed exception both backends share —
    what routes catch to return 409, instead of matching message strings."""
    with db_transaction(db_path) as conn:
        _execute(
            conn,
            f"INSERT INTO tree_editors (email, role) VALUES ({_ph(2)})",
            ("a@example.com", "editor"),
        )
    with pytest.raises(INTEGRITY_ERRORS):
        with db_transaction(db_path) as conn:
            _execute(
                conn,
                f"INSERT INTO tree_editors (email, role) VALUES ({_ph(2)})",
                ("a@example.com", "editor"),
            )
    assert _editor_count(db_path) == 1
