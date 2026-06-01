"""Undo-log domain mixin for TreeRepository.

Provides a DB-backed undo stack (undo_log table) that is safe across
multiple gunicorn workers because every operation is a committed DB write.

Only the most recent ~20 entries are kept; older ones are pruned on each
push to avoid unbounded growth.
"""

import json
from typing import Any

from ._sql import _execute, _fetchone, _ph, _scalar

_UNDO_STACK_LIMIT = 20


class UndoRepoMixin:
    """CRUD operations for the undo_log table."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

    # ── Stack operations ─────────────────────────────────────────────────

    def push_undo(self, kind: str, payload: dict) -> None:
        """Append an entry to the undo log and prune old entries.

        Keeps at most ``_UNDO_STACK_LIMIT`` rows so the table stays small.
        """
        conn = self._conn()
        try:
            _execute(
                conn,
                f"INSERT INTO undo_log (kind, payload) VALUES ({_ph(2)})",
                (kind, json.dumps(payload)),
            )
            # Prune: delete all but the most recent LIMIT rows.
            # We identify the cutoff id so the DELETE is a single index seek.
            ph = _ph()
            cutoff = _fetchone(
                conn,
                f"""
                SELECT id FROM undo_log
                ORDER BY id DESC
                LIMIT 1 OFFSET {_UNDO_STACK_LIMIT - 1}
                """,
            )
            if cutoff:
                _execute(
                    conn,
                    f"DELETE FROM undo_log WHERE id < {ph}",
                    (cutoff["id"],),
                )
            conn.commit()
        finally:
            conn.close()

    def pop_undo(self) -> dict | None:
        """Remove and return the most recent undo entry, or None if empty.

        Returns ``{"kind": str, "payload": dict}`` on success.
        """
        conn = self._conn()
        try:
            row = _fetchone(
                conn,
                "SELECT id, kind, payload FROM undo_log ORDER BY id DESC LIMIT 1",
            )
            if row is None:
                return None
            _execute(conn, f"DELETE FROM undo_log WHERE id = {_ph()}", (row["id"],))
            conn.commit()
            return {"kind": row["kind"], "payload": json.loads(row["payload"])}
        finally:
            conn.close()

    def peek_undo(self) -> dict | None:
        """Return the most recent undo entry without removing it, or None."""
        conn = self._conn()
        try:
            row = _fetchone(
                conn,
                "SELECT kind, payload FROM undo_log ORDER BY id DESC LIMIT 1",
            )
            if row is None:
                return None
            return {"kind": row["kind"], "payload": json.loads(row["payload"])}
        finally:
            conn.close()

    def undo_count(self) -> int:
        """Return the number of entries currently in the undo log."""
        conn = self._conn()
        try:
            row = _scalar(conn, "SELECT COUNT(*) AS n FROM undo_log")
            return row["n"]
        finally:
            conn.close()
