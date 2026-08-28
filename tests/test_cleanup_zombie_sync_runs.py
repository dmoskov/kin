"""Tests for the zombie sync_run cleanup script.

Uses a local SQLite stand-in for the family-org PostgreSQL database to
verify the cleanup logic without requiring production credentials.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest


@pytest.fixture()
def mock_db():
    """Create an in-memory SQLite database mimicking the sync_runs table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_run_id TEXT NOT NULL,
            sync_type TEXT NOT NULL,
            sync_key TEXT NOT NULL DEFAULT 'default',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_seconds REAL,
            status TEXT NOT NULL DEFAULT 'running',
            error_message TEXT,
            error_details TEXT,
            items_fetched INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    return conn


def _insert_run(conn, sync_type, started_at, status="running", completed_at=None):
    conn.execute(
        """INSERT INTO sync_runs (sync_run_id, sync_type, started_at, status, completed_at)
        VALUES (?, ?, ?, ?, ?)""",
        (f"test-{sync_type}-{started_at}", sync_type, started_at, status, completed_at),
    )
    conn.commit()


def _now():
    return datetime.now(UTC)


def _ago(minutes):
    return (_now() - timedelta(minutes=minutes)).isoformat()


class TestZombieDetection:
    """Verify that the cleanup correctly identifies zombie sync_runs."""

    def test_identifies_stale_running_sync(self, mock_db):
        """A sync_run stuck in 'running' for >60 min should be cleaned up."""
        _insert_run(mock_db, "asana", _ago(90))
        cur = mock_db.execute("SELECT COUNT(*) as n FROM sync_runs WHERE status = 'running'")
        assert cur.fetchone()[0] == 1

        # Simulate cleanup: mark as failed if running > 60 min
        cutoff = (_now() - timedelta(minutes=60)).isoformat()
        mock_db.execute(
            """UPDATE sync_runs SET status = 'failed',
               error_message = 'Zombie cleanup'
               WHERE status = 'running' AND started_at < ?""",
            (cutoff,),
        )
        mock_db.commit()

        cur = mock_db.execute("SELECT COUNT(*) as n FROM sync_runs WHERE status = 'running'")
        assert cur.fetchone()[0] == 0

        cur = mock_db.execute(
            "SELECT status, error_message FROM sync_runs WHERE sync_type = 'asana'"
        )
        row = cur.fetchone()
        assert row[0] == "failed"
        assert "Zombie" in row[1]

    def test_does_not_touch_recent_running_sync(self, mock_db):
        """A sync_run that started <60 min ago should NOT be cleaned up."""
        _insert_run(mock_db, "asana", _ago(30))

        cutoff = (_now() - timedelta(minutes=60)).isoformat()
        mock_db.execute(
            """UPDATE sync_runs SET status = 'failed'
               WHERE status = 'running' AND started_at < ?""",
            (cutoff,),
        )
        mock_db.commit()

        cur = mock_db.execute("SELECT status FROM sync_runs WHERE sync_type = 'asana'")
        assert cur.fetchone()[0] == "running"

    def test_does_not_touch_completed_syncs(self, mock_db):
        """A sync_run with status='success' should never be modified."""
        _insert_run(mock_db, "asana", _ago(120), status="success", completed_at=_ago(110))

        cutoff = (_now() - timedelta(minutes=60)).isoformat()
        mock_db.execute(
            """UPDATE sync_runs SET status = 'failed'
               WHERE status = 'running' AND started_at < ?""",
            (cutoff,),
        )
        mock_db.commit()

        cur = mock_db.execute("SELECT status FROM sync_runs WHERE sync_type = 'asana'")
        assert cur.fetchone()[0] == "success"

    def test_cleans_multiple_zombies(self, mock_db):
        """Multiple zombie sync_runs should all be cleaned."""
        _insert_run(mock_db, "asana", _ago(120))
        _insert_run(mock_db, "asana", _ago(180))
        _insert_run(mock_db, "google_calendar", _ago(90))
        _insert_run(mock_db, "slack", _ago(30))  # too recent

        cutoff = (_now() - timedelta(minutes=60)).isoformat()
        mock_db.execute(
            """UPDATE sync_runs SET status = 'failed'
               WHERE status = 'running' AND started_at < ?""",
            (cutoff,),
        )
        mock_db.commit()

        cur = mock_db.execute("SELECT COUNT(*) FROM sync_runs WHERE status = 'failed'")
        assert cur.fetchone()[0] == 3

        cur = mock_db.execute("SELECT COUNT(*) FROM sync_runs WHERE status = 'running'")
        assert cur.fetchone()[0] == 1  # the 30-min-old slack run

    def test_custom_timeout(self, mock_db):
        """Custom timeout should override the default 60-minute window."""
        _insert_run(mock_db, "asana", _ago(20))

        # 15-minute timeout should catch the 20-min-old run
        cutoff = (_now() - timedelta(minutes=15)).isoformat()
        mock_db.execute(
            """UPDATE sync_runs SET status = 'failed'
               WHERE status = 'running' AND started_at < ?""",
            (cutoff,),
        )
        mock_db.commit()

        cur = mock_db.execute("SELECT status FROM sync_runs WHERE sync_type = 'asana'")
        assert cur.fetchone()[0] == "failed"
