"""Tests for the zombie sync_run cleanup script.

Tests the actual cleanup_zombies() function and its two code paths
(DB function vs. fallback SQL) using mock connections.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from cleanup_zombie_sync_runs import (
    DEFAULT_TIMEOUT_MINUTES,
    _cleanup_via_function,
    _cleanup_via_sql,
    cleanup_zombies,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conn(cursor_side_effects=None):
    """Build a mock DB connection whose cursor returns the given side effects."""
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    if cursor_side_effects is not None:
        cur.execute.side_effect = cursor_side_effects
    return conn, cur


# ---------------------------------------------------------------------------
# _cleanup_via_function
# ---------------------------------------------------------------------------


class TestCleanupViaFunction:
    def test_returns_count_and_ids(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"cleaned_count": 3, "cleaned_ids": [1, 2, 3]}
        count, ids = _cleanup_via_function(cur, 60)
        assert count == 3
        assert ids == [1, 2, 3]
        cur.execute.assert_called_once_with("SELECT * FROM cleanup_zombie_sync_runs(%s)", (60,))

    def test_none_ids_becomes_empty_list(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"cleaned_count": 0, "cleaned_ids": None}
        count, ids = _cleanup_via_function(cur, 30)
        assert count == 0
        assert ids == []

    def test_propagates_db_error(self):
        cur = MagicMock()
        cur.execute.side_effect = Exception("function does not exist")
        with pytest.raises(Exception, match="function does not exist"):
            _cleanup_via_function(cur, 60)


# ---------------------------------------------------------------------------
# _cleanup_via_sql
# ---------------------------------------------------------------------------


class TestCleanupViaSql:
    def test_returns_count_and_ids_from_returning(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": 10}, {"id": 20}]
        count, ids = _cleanup_via_sql(cur, 45)
        assert count == 2
        assert ids == [10, 20]

    def test_no_zombies_returns_zero(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        count, ids = _cleanup_via_sql(cur, 60)
        assert count == 0
        assert ids == []


# ---------------------------------------------------------------------------
# cleanup_zombies (integration of the two paths)
# ---------------------------------------------------------------------------


class TestCleanupZombies:
    def test_uses_db_function_when_available(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"cleaned_count": 2, "cleaned_ids": [5, 6]}

        result = cleanup_zombies(timeout_minutes=60, conn=conn)

        assert result == 2
        cur.execute.assert_called_once_with("SELECT * FROM cleanup_zombie_sync_runs(%s)", (60,))
        conn.commit.assert_called_once()
        conn.close.assert_not_called()

    def test_falls_back_to_sql_when_function_missing(self):
        conn = MagicMock()
        func_cur = MagicMock()
        func_cur.execute.side_effect = Exception("function does not exist")
        sql_cur = MagicMock()
        sql_cur.fetchall.return_value = [{"id": 7}]
        conn.cursor.side_effect = [func_cur, sql_cur]

        result = cleanup_zombies(timeout_minutes=30, conn=conn)

        assert result == 1
        conn.rollback.assert_called_once()
        conn.commit.assert_called_once()

    def test_no_zombies_found(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"cleaned_count": 0, "cleaned_ids": None}

        result = cleanup_zombies(timeout_minutes=60, conn=conn)

        assert result == 0
        conn.commit.assert_called_once()

    def test_default_timeout(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"cleaned_count": 0, "cleaned_ids": None}

        cleanup_zombies(conn=conn)

        cur.execute.assert_called_once_with(
            "SELECT * FROM cleanup_zombie_sync_runs(%s)",
            (DEFAULT_TIMEOUT_MINUTES,),
        )

    @patch("cleanup_zombie_sync_runs._get_family_org_connection")
    def test_creates_and_closes_conn_when_none_provided(self, mock_get_conn):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"cleaned_count": 0, "cleaned_ids": None}
        mock_get_conn.return_value = conn

        cleanup_zombies(timeout_minutes=60)

        mock_get_conn.assert_called_once()
        conn.close.assert_called_once()

    def test_does_not_close_caller_provided_conn(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"cleaned_count": 0, "cleaned_ids": None}

        cleanup_zombies(conn=conn)

        conn.close.assert_not_called()

    def test_custom_timeout_propagated(self):
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value = cur
        cur.fetchone.return_value = {"cleaned_count": 1, "cleaned_ids": [99]}

        result = cleanup_zombies(timeout_minutes=15, conn=conn)

        assert result == 1
        cur.execute.assert_called_once_with("SELECT * FROM cleanup_zombie_sync_runs(%s)", (15,))
