"""Shared SQL helper functions for all repository mixin modules."""

from typing import Any

from ..connection import _use_postgres as _is_pg


def _ph(n: int = 1) -> str:
    """Return n placeholder(s) for the current backend."""
    p = "%s" if _is_pg() else "?"
    return ", ".join([p] * n)


def _now() -> str:
    """SQL expression for 'current timestamp'."""
    return "NOW()" if _is_pg() else "datetime('now')"


def _execute(conn: Any, sql: str, params: tuple = ()) -> Any:
    """Execute SQL on either backend. Returns cursor."""
    if _is_pg():
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)


def _fetchone(conn: Any, sql: str, params: tuple = ()) -> dict | None:
    """Execute and fetch one row as a dict."""
    cur = _execute(conn, sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    # sqlite3.Row supports dict-style access; psycopg2 RealDictRow is already dict
    return dict(row)


def _scalar(conn: Any, sql: str, params: tuple = ()) -> dict:
    """Like ``_fetchone`` but for queries guaranteed to return exactly one row.

    Used for COUNT/aggregate and identity (``lastval()``/``last_insert_rowid()``)
    lookups, which always yield a row. Asserts non-None so callers can index the
    result directly without a redundant guard.
    """
    row = _fetchone(conn, sql, params)
    assert row is not None, f"expected exactly one row from: {sql}"
    return row


def _fetchall(conn: Any, sql: str, params: tuple = ()) -> list[dict]:
    """Execute and fetch all rows as dicts."""
    cur = _execute(conn, sql, params)
    return [dict(r) for r in cur.fetchall()]


def _upsert(
    conn: Any,
    table: str,
    columns: list[str],
    values: tuple,
    conflict_columns: list[str],
    *,
    update: bool = True,
    extra_columns: list[str] | None = None,
    extra_values: list[str] | None = None,
) -> None:
    """Insert a row with conflict handling for both SQLite and PostgreSQL.

    Args:
        conn: Database connection.
        table: Target table name.
        columns: Column names corresponding to parameterised *values*.
        values: Parameter values (len must match *columns*).
        conflict_columns: Columns that form the conflict/uniqueness constraint.
        update: If True, update non-conflict columns on conflict, in place
                (``ON CONFLICT DO UPDATE`` on both backends).
                If False, silently skip duplicates
                (PG ``ON CONFLICT DO NOTHING`` / SQLite ``INSERT OR IGNORE``).
        extra_columns: Additional columns whose values are raw SQL expressions
                       (e.g. ``["updated_at"]``).
        extra_values: Raw SQL for each *extra_column* (e.g. ``["NOW()"]``).
    """
    all_cols = list(columns)
    if extra_columns:
        all_cols.extend(extra_columns)

    col_list = ", ".join(all_cols)
    ph = _ph(len(columns))
    if extra_values:
        ph += ", " + ", ".join(extra_values)

    if _is_pg():
        conflict = ", ".join(conflict_columns)
        if update:
            conflict_set = set(conflict_columns)
            sets = [f"{c}=EXCLUDED.{c}" for c in columns if c not in conflict_set]
            if extra_columns and extra_values:
                sets.extend(f"{c}={v}" for c, v in zip(extra_columns, extra_values, strict=False))
            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES ({ph}) "
                f"ON CONFLICT ({conflict}) DO UPDATE SET {', '.join(sets)}"
            )
        else:
            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES ({ph}) "
                f"ON CONFLICT ({conflict}) DO NOTHING"
            )
    else:
        # SQLite: use a real upsert (ON CONFLICT DO UPDATE) rather than
        # INSERT OR REPLACE. INSERT OR REPLACE deletes the conflicting row and
        # re-inserts it, which (with PRAGMA foreign_keys=ON) cascade-deletes
        # child rows and resets columns not in the supplied list. ON CONFLICT
        # DO UPDATE updates in place, matching the PostgreSQL branch.
        if update:
            conflict = ", ".join(conflict_columns)
            conflict_set = set(conflict_columns)
            sets = [f"{c}=excluded.{c}" for c in columns if c not in conflict_set]
            if extra_columns and extra_values:
                sets.extend(f"{c}={v}" for c, v in zip(extra_columns, extra_values, strict=False))
            sql = (
                f"INSERT INTO {table} ({col_list}) VALUES ({ph}) "
                f"ON CONFLICT ({conflict}) DO UPDATE SET {', '.join(sets)}"
            )
        else:
            sql = f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({ph})"

    _execute(conn, sql, values)


def _ensure_photo_id(conn: Any, file_path: str) -> int:
    """Return the ``photos.id`` for *file_path* on *conn*, inserting if absent.

    Operates on the caller's connection without committing, so it can take part
    in a larger transaction. Callers that own the connection commit/close it.
    """
    _upsert(conn, "photos", ["file_path"], (file_path,), ["file_path"], update=False)
    return _scalar(conn, f"SELECT id FROM photos WHERE file_path = {_ph()}", (file_path,))["id"]
