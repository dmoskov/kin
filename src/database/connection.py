"""Database connection management.

Supports two backends:
  - **PostgreSQL** (production) — set DATABASE_URL env var
  - **SQLite** (local dev / tests) — set FAMILY_TREE_DB or use default data/family.db

Handles connection creation, path resolution, and schema initialization.
Supports schema migrations: on init_db(), any unapplied migrations are
automatically applied in order.
"""

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from .schema import (
    MIGRATIONS,
    PG_MIGRATIONS,
    PG_SCHEMA_SQL,
    SCHEMA_SQL,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)


# ── Backend detection ──────────────────────────────────────────────────

def _use_postgres() -> bool:
    """Return True if DATABASE_URL is set (PostgreSQL mode)."""
    return bool(os.environ.get("DATABASE_URL"))


# ── SQLite helpers ─────────────────────────────────────────────────────

def get_db_path() -> str:
    """Resolve the SQLite database file path.

    Priority:
    1. FAMILY_TREE_DB environment variable
    2. data/family.db relative to the project root
    """
    env_path = os.environ.get("FAMILY_TREE_DB")
    if env_path:
        return env_path

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            db_path = parent / "data" / "family.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return str(db_path)

    fallback = Path.cwd() / "data" / "family.db"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return str(fallback)


def _get_sqlite_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


# ── PostgreSQL helpers ─────────────────────────────────────────────────

def _get_pg_connection() -> Any:
    """Create a PostgreSQL connection using DATABASE_URL.

    Returns a psycopg2 connection with RealDictCursor as default cursor.
    Requires psycopg2 to be installed.
    """
    import psycopg2
    import psycopg2.extras

    dsn = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


# ── Public API ─────────────────────────────────────────────────────────

def get_connection(db_path: str | None = None) -> Any:
    """Create a database connection (PostgreSQL or SQLite).

    If DATABASE_URL is set → PostgreSQL (db_path is ignored).
    Otherwise → SQLite using db_path or the default location.
    """
    if _use_postgres():
        return _get_pg_connection()
    return _get_sqlite_connection(db_path)


def _current_version(conn: Any) -> int:
    """Get the current schema version from the database."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(version) as v FROM schema_version")
        row = cur.fetchone()
        if row is None:
            return 0
        # Works for both sqlite3.Row and RealDictRow
        v = row["v"] if isinstance(row, dict) else row[0]
        return v or 0
    except Exception:
        if _use_postgres():
            conn.rollback()
        return 0


def init_db(db_path: str | None = None) -> str:
    """Initialize the database schema, applying any pending migrations.

    Returns the connection string / path used.
    """
    if _use_postgres():
        return _init_pg()

    return _init_sqlite(db_path)





def _migrate_photos_data(conn: Any, is_pg: bool) -> None:
    """Migrate photo_paths/photo_captions from people table into photos + person_photos.

    Idempotent: skips if person_photos already has rows.
    """
    ph = "%s" if is_pg else "?"

    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM person_photos")
        row = cur.fetchone()
        count = row["n"] if isinstance(row, dict) else row[0]
        if count > 0:
            return
    except Exception:
        if is_pg:
            conn.rollback()
        return

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, photo_paths, photo_captions FROM people")
        rows = cur.fetchall()

        for row in rows:
            if isinstance(row, dict):
                person_id = row["id"]
                raw_paths = row["photo_paths"]
                raw_captions = row["photo_captions"]
            else:
                person_id = row[0]
                raw_paths = row[1]
                raw_captions = row[2]

            paths = json.loads(raw_paths or "[]")
            captions = json.loads(raw_captions or "{}")

            if not paths:
                continue

            for idx, file_path in enumerate(paths):
                if is_pg:
                    cur.execute(
                        "INSERT INTO photos (file_path) VALUES (%s) ON CONFLICT (file_path) DO NOTHING",
                        (file_path,),
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO photos (file_path) VALUES (?)",
                        (file_path,),
                    )

                cur.execute(
                    f"SELECT id FROM photos WHERE file_path = {ph}",
                    (file_path,),
                )
                photo_row = cur.fetchone()
                photo_id = photo_row["id"] if isinstance(photo_row, dict) else photo_row[0]

                caption = captions.get(file_path, "")
                is_profile = 1 if idx == 0 else 0

                if is_pg:
                    cur.execute(
                        "INSERT INTO person_photos (person_id, photo_id, is_profile, display_order, caption) "
                        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (person_id, photo_id) DO NOTHING",
                        (person_id, photo_id, bool(is_profile), idx, caption),
                    )
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO person_photos (person_id, photo_id, is_profile, display_order, caption) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (person_id, photo_id, is_profile, idx, caption),
                    )

        conn.commit()
        logger.info("Migrated photo data for %d people into photos/person_photos tables", len(rows))
    except Exception as e:
        logger.error("Photo data migration failed: %s", e)
        if is_pg:
            conn.rollback()
        raise


def _init_sqlite(db_path: str | None = None) -> str:
    path = db_path or get_db_path()
    conn = _get_sqlite_connection(path)
    try:
        current = _current_version(conn)

        if current == 0:
            conn.executescript(SCHEMA_SQL)
        else:
            for version in sorted(MIGRATIONS.keys()):
                if version > current:
                    conn.executescript(MIGRATIONS[version])

        existing = conn.execute(
            "SELECT version FROM schema_version WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            conn.commit()

        _migrate_photos_data(conn, is_pg=False)
    finally:
        conn.close()

    return path


def _init_pg() -> str:
    dsn = os.environ["DATABASE_URL"]
    conn = _get_pg_connection()
    try:
        cur = conn.cursor()
        current = _current_version(conn)

        if current == 0:
            cur.execute(PG_SCHEMA_SQL)
        else:
            for version in sorted(PG_MIGRATIONS.keys()):
                if version > current:
                    cur.execute(PG_MIGRATIONS[version])

        cur.execute(
            "SELECT version FROM schema_version WHERE version = %s",
            (SCHEMA_VERSION,),
        )
        existing = cur.fetchone()
        if not existing:
            cur.execute(
                "INSERT INTO schema_version (version) VALUES (%s)",
                (SCHEMA_VERSION,),
            )
        conn.commit()

        _migrate_photos_data(conn, is_pg=True)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return dsn
