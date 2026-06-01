"""TreeRepository — CRUD operations for family tree data.

Supports both SQLite (local dev) and PostgreSQL (production).
The backend is determined by the DATABASE_URL environment variable:
  - Set → PostgreSQL with %s placeholders
  - Unset → SQLite with ? placeholders

Usage:
    from database import TreeRepository, init_db

    init_db()
    repo = TreeRepository()
    repo.save_person(person)
    tree = repo.load_tree()
"""

from typing import Any

from ..connection import get_connection
from ._articles import ArticlesRepoMixin
from ._events import EventsRepoMixin
from ._people import PeopleRepoMixin
from ._photos import PhotosRepoMixin
from ._relationships import RelationshipsRepoMixin
from ._sources import SourcesRepoMixin
from ._sql import (
    _ensure_photo_id,
    _execute,
    _fetchall,
    _fetchone,
    _now,
    _ph,
    _scalar,
    _upsert,
)
from ._tree import TreeRepoMixin

__all__ = [
    "TreeRepository",
    "_execute",
    "_ph",
    "_fetchone",
    "_fetchall",
    "_scalar",
    "_upsert",
    "_now",
    "_ensure_photo_id",
]


class TreeRepository(
    PeopleRepoMixin,
    RelationshipsRepoMixin,
    EventsRepoMixin,
    SourcesRepoMixin,
    PhotosRepoMixin,
    ArticlesRepoMixin,
    TreeRepoMixin,
):
    """Persistence layer for FamilyTree data (SQLite or PostgreSQL)."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self) -> Any:
        return get_connection(self._db_path)
