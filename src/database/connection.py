"""Database connection management.

Handles SQLite connection creation, path resolution, and initialization.
Supports schema migrations: on init_db(), any unapplied migrations are
automatically applied in order.
"""

import os
import sqlite3
from pathlib import Path

from .schema import SCHEMA_SQL, SCHEMA_VERSION, MIGRATIONS


def get_db_path() -> str:
    """Resolve the database file path.

    Priority:
    1. FAMILY_TREE_DB environment variable
    2. data/family.db relative to the project root
    """
    env_path = os.environ.get("FAMILY_TREE_DB")
    if env_path:
        return env_path

    # Walk up from this file to find the project root (where pyproject.toml lives)
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            db_path = parent / "data" / "family.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return str(db_path)

    # Fallback: current working directory
    fallback = Path.cwd() / "data" / "family.db"
    fallback.parent.mkdir(parents=True, exist_ok=True)
    return str(fallback)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Create a SQLite connection with recommended settings.

    Args:
        db_path: Path to the database file. If None, uses get_db_path().

    Returns:
        A configured sqlite3.Connection with WAL mode and foreign keys enabled.
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _current_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version from the database.

    Returns 0 if the schema_version table doesn't exist yet.
    """
    try:
        row = conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        ).fetchone()
        return row["v"] or 0
    except sqlite3.OperationalError:
        return 0


def init_db(db_path: str | None = None) -> str:
    """Initialize the database schema, applying any pending migrations.

    For fresh databases: creates all tables at the latest version.
    For existing databases: applies only the migrations needed to reach
    the current SCHEMA_VERSION.

    Args:
        db_path: Path to the database file. If None, uses get_db_path().

    Returns:
        The path to the initialized database file.
    """
    path = db_path or get_db_path()
    conn = get_connection(path)
    try:
        current = _current_version(conn)

        if current == 0:
            # Fresh database — apply full schema
            conn.executescript(SCHEMA_SQL)
        else:
            # Existing database — apply only missing migrations
            for version in sorted(MIGRATIONS.keys()):
                if version > current:
                    conn.executescript(MIGRATIONS[version])

        # Record schema version if not already present
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
    finally:
        conn.close()

    return path
