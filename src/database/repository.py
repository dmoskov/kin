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

import json
from typing import Any

from models.article import NewsArticle
from models.citation import Citation, Confidence, EntityType
from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, RelationshipType, Union
from models.source import Source, SourceType
from models.tree import FamilyTree

from .connection import _use_postgres as _is_pg
from .connection import get_connection


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
        update: If True, update non-conflict columns on conflict
                (PG ``ON CONFLICT DO UPDATE`` / SQLite ``INSERT OR REPLACE``).
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
        prefix = "INSERT OR REPLACE" if update else "INSERT OR IGNORE"
        sql = f"{prefix} INTO {table} ({col_list}) VALUES ({ph})"

    _execute(conn, sql, values)


class TreeRepository:
    """Persistence layer for FamilyTree data (SQLite or PostgreSQL)."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self) -> Any:
        return get_connection(self._db_path)

    # ── Internal save helpers (operate on a caller-provided connection) ──

    def _do_save_person(self, conn: Any, person: Person) -> None:
        params = (
            person.id,
            person.given_name,
            person.surname,
            person.gender.value,
            person.birth_date or None,
            person.birth_place or None,
            person.death_date or None,
            person.death_place or None,
            person.maiden_name or None,
            json.dumps(person.nicknames),
            person.notes,
            json.dumps(person.photo_paths),
            json.dumps(person.photo_captions),
            person.email or None,
        )
        _upsert(
            conn,
            "people",
            [
                "id",
                "given_name",
                "surname",
                "gender",
                "birth_date",
                "birth_place",
                "death_date",
                "death_place",
                "maiden_name",
                "nicknames",
                "notes",
                "photo_paths",
                "photo_captions",
                "email",
            ],
            params,
            ["id"],
            extra_columns=["updated_at"],
            extra_values=[_now()],
        )
        try:
            self._sync_person_photos(conn, person)
        except Exception:
            pass

    def _do_save_relationship(self, conn: Any, rel: Relationship) -> None:
        _upsert(
            conn,
            "relationships",
            ["parent_id", "child_id", "rel_type"],
            (rel.parent_id, rel.child_id, rel.rel_type.value),
            ["parent_id", "child_id"],
            update=False,
        )

    def _do_save_union(self, conn: Any, union: Union) -> None:
        _execute(
            conn,
            f"""
            INSERT INTO unions
                (partner1_id, partner2_id, union_date, union_place,
                 end_date, end_reason, notes)
            VALUES ({_ph(7)})
        """,
            (
                union.partner1_id,
                union.partner2_id,
                union.union_date,
                union.union_place,
                union.end_date,
                union.end_reason,
                union.notes,
            ),
        )

    def _do_save_event(self, conn: Any, event: LifeEvent) -> None:
        _execute(
            conn,
            f"""
            INSERT INTO events
                (person_id, event_type, date, end_date, place,
                 description, source)
            VALUES ({_ph(7)})
        """,
            (
                event.person_id,
                event.event_type.value,
                event.date,
                event.end_date,
                event.place,
                event.description,
                event.source,
            ),
        )

    def _do_save_source(self, conn: Any, source: Source) -> None:
        _upsert(
            conn,
            "sources",
            ["id", "name", "source_type", "author", "date", "description", "url"],
            (
                source.id,
                source.name,
                source.source_type.value,
                source.author,
                source.date,
                source.description,
                source.url,
            ),
            ["id"],
        )

    def _do_save_citation(self, conn: Any, citation: Citation) -> None:
        _execute(
            conn,
            f"""
            INSERT INTO citations
                (source_id, entity_type, entity_id, field_name,
                 excerpt, confidence, notes)
            VALUES ({_ph(7)})
        """,
            (
                citation.source_id,
                citation.entity_type.value,
                citation.entity_id,
                citation.field_name,
                citation.excerpt,
                citation.confidence.value,
                citation.notes,
            ),
        )

    # ── People ──────────────────────────────────────────────────────────

    def save_person(self, person: Person) -> None:
        """Insert or upsert a Person. Dual-writes to photos/person_photos tables."""
        conn = self._conn()
        try:
            self._do_save_person(conn, person)
            conn.commit()
        finally:
            conn.close()

    def get_person(self, person_id: str) -> Person | None:
        """Fetch a single Person by ID."""
        conn = self._conn()
        try:
            row = _fetchone(
                conn, f"SELECT * FROM people WHERE id = {_ph()}", (person_id,)
            )
            return self._row_to_person(row) if row else None
        finally:
            conn.close()

    def list_people(self) -> list[Person]:
        """Fetch all people, ordered by surname then given name."""
        conn = self._conn()
        try:
            rows = _fetchall(conn, "SELECT * FROM people ORDER BY surname, given_name")
            return [self._row_to_person(r) for r in rows]
        finally:
            conn.close()

    def search_people(self, query: str) -> list[Person]:
        """Search people by name (case-insensitive substring match)."""
        conn = self._conn()
        try:
            pattern = f"%{query}%"
            p = _ph()
            if _is_pg():
                rows = _fetchall(
                    conn,
                    f"""
                    SELECT * FROM people
                    WHERE given_name ILIKE {p} OR surname ILIKE {p}
                       OR maiden_name ILIKE {p} OR nicknames ILIKE {p}
                       OR notes ILIKE {p}
                    ORDER BY surname, given_name
                """,
                    (pattern,) * 5,
                )
            else:
                rows = _fetchall(
                    conn,
                    f"""
                    SELECT * FROM people
                    WHERE given_name LIKE {p} OR surname LIKE {p}
                       OR maiden_name LIKE {p} OR nicknames LIKE {p}
                       OR notes LIKE {p}
                    ORDER BY surname, given_name
                """,
                    (pattern,) * 5,
                )
            return [self._row_to_person(r) for r in rows]
        finally:
            conn.close()

    def delete_person(self, person_id: str) -> bool:
        """Delete a person and all their relationships/events (cascading)."""
        conn = self._conn()
        try:
            cur = _execute(conn, f"DELETE FROM people WHERE id = {_ph()}", (person_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    # ── Relationships ───────────────────────────────────────────────────

    def save_relationship(self, rel: Relationship) -> None:
        """Insert a parent-child relationship (ignore if duplicate)."""
        conn = self._conn()
        try:
            self._do_save_relationship(conn, rel)
            conn.commit()
        finally:
            conn.close()

    # ── Unions ──────────────────────────────────────────────────────────

    def save_union(self, union: Union) -> None:
        """Insert a marriage/partnership."""
        conn = self._conn()
        try:
            self._do_save_union(conn, union)
            conn.commit()
        finally:
            conn.close()

    # ── Events ──────────────────────────────────────────────────────────

    def save_event(self, event: LifeEvent) -> None:
        """Insert a life event."""
        conn = self._conn()
        try:
            self._do_save_event(conn, event)
            conn.commit()
        finally:
            conn.close()

    # ── Sources ─────────────────────────────────────────────────────────

    def save_source(self, source: Source) -> None:
        """Insert or upsert a Source."""
        conn = self._conn()
        try:
            self._do_save_source(conn, source)
            conn.commit()
        finally:
            conn.close()

    def get_source(self, source_id: str) -> Source | None:
        """Fetch a single Source by ID."""
        conn = self._conn()
        try:
            row = _fetchone(
                conn, f"SELECT * FROM sources WHERE id = {_ph()}", (source_id,)
            )
            return self._row_to_source(row) if row else None
        finally:
            conn.close()

    def list_sources(self) -> list[Source]:
        """Fetch all sources, ordered by name."""
        conn = self._conn()
        try:
            rows = _fetchall(conn, "SELECT * FROM sources ORDER BY name")
            return [self._row_to_source(r) for r in rows]
        finally:
            conn.close()

    # ── Citations ───────────────────────────────────────────────────────

    def save_citation(self, citation: Citation) -> None:
        """Insert a citation linking a source to an entity."""
        conn = self._conn()
        try:
            self._do_save_citation(conn, citation)
            conn.commit()
        finally:
            conn.close()

    def citations_for(
        self,
        entity_type: EntityType,
        entity_id: str,
        field_name: str | None = None,
    ) -> list[Citation]:
        """Fetch all citations for a given entity (optionally filtered by field)."""
        conn = self._conn()
        try:
            p = _ph()
            if field_name:
                rows = _fetchall(
                    conn,
                    f"""
                    SELECT * FROM citations
                    WHERE entity_type = {p} AND entity_id = {p} AND field_name = {p}
                    ORDER BY id
                """,
                    (entity_type.value, entity_id, field_name),
                )
            else:
                rows = _fetchall(
                    conn,
                    f"""
                    SELECT * FROM citations
                    WHERE entity_type = {p} AND entity_id = {p}
                    ORDER BY id
                """,
                    (entity_type.value, entity_id),
                )
            return [self._row_to_citation(r) for r in rows]
        finally:
            conn.close()

    def citations_by_source(self, source_id: str) -> list[Citation]:
        """Fetch all citations from a given source."""
        conn = self._conn()
        try:
            rows = _fetchall(
                conn,
                f"SELECT * FROM citations WHERE source_id = {_ph()} ORDER BY id",
                (source_id,),
            )
            return [self._row_to_citation(r) for r in rows]
        finally:
            conn.close()

    # ── News Articles ──────────────────────────────────────────────────

    def save_article(self, article: NewsArticle) -> None:
        """Insert or upsert a NewsArticle."""
        conn = self._conn()
        params = (
            article.id,
            article.title,
            article.url,
            article.publication,
            article.date,
            article.summary,
            article.photo_url,
        )
        try:
            if _is_pg():
                _execute(
                    conn,
                    f"""
                    INSERT INTO news_articles
                        (id, title, url, publication, date, summary, photo_url)
                    VALUES ({_ph(7)})
                    ON CONFLICT (id) DO UPDATE SET
                        title=EXCLUDED.title, url=EXCLUDED.url,
                        publication=EXCLUDED.publication, date=EXCLUDED.date,
                        summary=EXCLUDED.summary, photo_url=EXCLUDED.photo_url
                """,
                    params,
                )
            else:
                _execute(
                    conn,
                    f"""
                    INSERT OR REPLACE INTO news_articles
                        (id, title, url, publication, date, summary, photo_url)
                    VALUES ({_ph(7)})
                """,
                    params,
                )
            conn.commit()
        finally:
            conn.close()

    def get_article(self, article_id: str) -> NewsArticle | None:
        """Fetch a single NewsArticle by ID."""
        conn = self._conn()
        try:
            row = _fetchone(
                conn, f"SELECT * FROM news_articles WHERE id = {_ph()}", (article_id,)
            )
            return self._row_to_article(row) if row else None
        finally:
            conn.close()

    def list_articles(self) -> list[NewsArticle]:
        """Fetch all news articles, ordered by date descending."""
        conn = self._conn()
        try:
            rows = _fetchall(
                conn,
                "SELECT * FROM news_articles ORDER BY date DESC, title",
            )
            return [self._row_to_article(r) for r in rows]
        finally:
            conn.close()

    def delete_article(self, article_id: str) -> bool:
        """Delete an article (cascades to person_articles)."""
        conn = self._conn()
        try:
            cur = _execute(
                conn,
                f"DELETE FROM news_articles WHERE id = {_ph()}",
                (article_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def link_article_to_person(self, person_id: str, article_id: str) -> None:
        """Associate a news article with a person."""
        conn = self._conn()
        try:
            if _is_pg():
                _execute(
                    conn,
                    f"""
                    INSERT INTO person_articles (person_id, article_id)
                    VALUES ({_ph(2)})
                    ON CONFLICT (person_id, article_id) DO NOTHING
                """,
                    (person_id, article_id),
                )
            else:
                _execute(
                    conn,
                    f"""
                    INSERT OR IGNORE INTO person_articles (person_id, article_id)
                    VALUES ({_ph(2)})
                """,
                    (person_id, article_id),
                )
            conn.commit()
        finally:
            conn.close()

    def unlink_article_from_person(self, person_id: str, article_id: str) -> None:
        """Remove the association between a person and an article."""
        conn = self._conn()
        try:
            _execute(
                conn,
                f"DELETE FROM person_articles WHERE person_id = {_ph()} AND article_id = {_ph()}",
                (person_id, article_id),
            )
            conn.commit()
        finally:
            conn.close()

    def articles_for_person(self, person_id: str) -> list[NewsArticle]:
        """Fetch all articles linked to a person."""
        conn = self._conn()
        try:
            p = _ph()
            rows = _fetchall(
                conn,
                f"""
                SELECT a.* FROM news_articles a
                JOIN person_articles pa ON pa.article_id = a.id
                WHERE pa.person_id = {p}
                ORDER BY a.date DESC, a.title
            """,
                (person_id,),
            )
            return [self._row_to_article(r) for r in rows]
        finally:
            conn.close()

    def people_for_article(self, article_id: str) -> list[dict]:
        """Return all people linked to an article."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchall(
                conn,
                f"""
                SELECT ppl.id, ppl.given_name, ppl.surname
                FROM person_articles pa
                JOIN people ppl ON ppl.id = pa.person_id
                WHERE pa.article_id = {p}
                ORDER BY ppl.surname, ppl.given_name
            """,
                (article_id,),
            )
        finally:
            conn.close()

    # ── Bulk operations ─────────────────────────────────────────────────

    def save_tree(self, tree: FamilyTree) -> None:
        """Save an entire FamilyTree to the database in a single transaction."""
        conn = self._conn()
        try:
            for person in tree.people.values():
                self._do_save_person(conn, person)
            for rel in tree.relationships:
                self._do_save_relationship(conn, rel)
            for union in tree.unions:
                self._do_save_union(conn, union)
            for event in tree.events:
                self._do_save_event(conn, event)
            for source in tree.sources.values():
                self._do_save_source(conn, source)
            for citation in tree.citations:
                self._do_save_citation(conn, citation)

            for article in tree.articles.values():
                _upsert(
                    conn,
                    "news_articles",
                    ["id", "title", "url", "publication", "date", "summary", "photo_url"],
                    (article.id, article.title, article.url, article.publication,
                     article.date, article.summary, article.photo_url),
                    ["id"],
                )

            for person_id, article_ids in tree.person_article_links.items():
                for article_id in article_ids:
                    _upsert(
                        conn,
                        "person_articles",
                        ["person_id", "article_id"],
                        (person_id, article_id),
                        ["person_id", "article_id"],
                        update=False,
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def load_tree(self) -> FamilyTree:
        """Load the entire family tree from the database into memory."""
        conn = self._conn()
        try:
            tree = FamilyTree()

            for row in _fetchall(conn, "SELECT * FROM people"):
                tree.add_person(self._row_to_person(row))

            for row in _fetchall(conn, "SELECT * FROM relationships"):
                tree.add_relationship(
                    Relationship(
                        parent_id=row["parent_id"],
                        child_id=row["child_id"],
                        rel_type=RelationshipType(row["rel_type"]),
                    )
                )

            for row in _fetchall(conn, "SELECT * FROM unions"):
                tree.add_union(
                    Union(
                        partner1_id=row["partner1_id"],
                        partner2_id=row["partner2_id"],
                        union_date=row["union_date"],
                        union_place=row["union_place"],
                        end_date=row["end_date"],
                        end_reason=row["end_reason"],
                        notes=row["notes"] or "",
                    )
                )

            for row in _fetchall(conn, "SELECT * FROM events"):
                tree.add_event(
                    LifeEvent(
                        person_id=row["person_id"],
                        event_type=EventType(row["event_type"]),
                        date=row["date"],
                        end_date=row["end_date"],
                        place=row["place"],
                        description=row["description"] or "",
                        source=row["source"],
                    )
                )

            # Sources & citations (v2 — may not exist in old SQLite DBs)
            try:
                for row in _fetchall(conn, "SELECT * FROM sources"):
                    tree.add_source(self._row_to_source(row))
            except Exception:
                if _is_pg():
                    conn.rollback()

            try:
                for row in _fetchall(conn, "SELECT * FROM citations"):
                    tree.add_citation(self._row_to_citation(row))
            except Exception:
                if _is_pg():
                    conn.rollback()

            try:
                for row in _fetchall(conn, "SELECT * FROM news_articles"):
                    tree.add_article(self._row_to_article(row))
                for row in _fetchall(
                    conn, "SELECT person_id, article_id FROM person_articles"
                ):
                    tree.add_person_article_link(row["person_id"], row["article_id"])
            except Exception:
                if _is_pg():
                    conn.rollback()

            return tree
        finally:
            conn.close()

    # ── Stats ───────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return summary statistics about the database."""
        conn = self._conn()
        try:
            counts = {}
            for table in ("people", "relationships", "unions", "events"):
                row = _scalar(conn, f"SELECT COUNT(*) as n FROM {table}")
                counts[table] = row["n"]

            row = _scalar(
                conn, "SELECT COUNT(*) as n FROM people WHERE death_date IS NULL"
            )
            counts["living"] = row["n"]
            counts["deceased"] = counts["people"] - counts["living"]

            try:
                counts["sources"] = _scalar(
                    conn, "SELECT COUNT(*) as n FROM sources"
                )["n"]
                counts["citations"] = _scalar(
                    conn, "SELECT COUNT(*) as n FROM citations"
                )["n"]
            except Exception:
                if _is_pg():
                    conn.rollback()
                counts["sources"] = 0
                counts["citations"] = 0

            try:
                counts["articles"] = _scalar(
                    conn, "SELECT COUNT(*) as n FROM news_articles"
                )["n"]
            except Exception:
                if _is_pg():
                    conn.rollback()
                counts["articles"] = 0

            return counts
        finally:
            conn.close()

    # ── Photos ─────────────────────────────────────────────────────────

    def get_or_create_photo(self, file_path: str) -> int:
        """Return the photo id for a file_path, creating a row if needed."""
        conn = self._conn()
        try:
            row = _fetchone(
                conn, f"SELECT id FROM photos WHERE file_path = {_ph()}", (file_path,)
            )
            if row:
                return row["id"]
            _upsert(
                conn, "photos", ["file_path"], (file_path,), ["file_path"], update=False
            )
            conn.commit()
            row = _scalar(
                conn, f"SELECT id FROM photos WHERE file_path = {_ph()}", (file_path,)
            )
            return row["id"]
        finally:
            conn.close()

    def update_photo_metadata(self, photo_id: int, **kwargs) -> None:
        """Update metadata fields on a photo (date, date_circa, place, photo_type)."""
        allowed = {"date", "date_circa", "place", "photo_type", "lat", "lng"}
        sets = []
        params = []
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "date_circa":
                v = bool(v) if _is_pg() else (1 if v else 0)
            sets.append(f"{k} = {_ph()}")
            params.append(v)
        if not sets:
            return
        params.append(photo_id)
        sql = f"UPDATE photos SET {', '.join(sets)} WHERE id = {_ph()}"
        conn = self._conn()
        try:
            _execute(conn, sql, tuple(params))
            conn.commit()
        finally:
            conn.close()

    def get_photo(self, photo_id: int) -> dict | None:
        """Fetch a single photo by id."""
        conn = self._conn()
        try:
            return _fetchone(
                conn, f"SELECT * FROM photos WHERE id = {_ph()}", (photo_id,)
            )
        finally:
            conn.close()

    def photos_for_person(self, person_id: str) -> list[dict]:
        """Return all photos for a person, joined with person_photos metadata."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchall(
                conn,
                f"""
                SELECT p.*, pp.is_profile, pp.display_order, pp.caption, pp.person_id,
                       pp.crop_x, pp.crop_y, pp.crop_w, pp.crop_h
                FROM photos p
                JOIN person_photos pp ON pp.photo_id = p.id
                WHERE pp.person_id = {p}
                ORDER BY pp.display_order
            """,
                (person_id,),
            )
        finally:
            conn.close()

    def people_for_photo(self, photo_id: int) -> list[dict]:
        """Return all people tagged in a photo."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchall(
                conn,
                f"""
                SELECT pp.person_id, pp.is_profile, pp.display_order, pp.caption,
                       pp.crop_x, pp.crop_y, pp.crop_w, pp.crop_h,
                       ppl.given_name, ppl.surname
                FROM person_photos pp
                JOIN people ppl ON ppl.id = pp.person_id
                WHERE pp.photo_id = {p}
                ORDER BY pp.display_order
            """,
                (photo_id,),
            )
        finally:
            conn.close()

    def assign_photo_to_person(
        self,
        person_id: str,
        photo_id: int,
        caption: str = "",
        display_order: int = 0,
        is_profile: bool = False,
    ) -> None:
        """Link a photo to a person."""
        conn = self._conn()
        try:
            is_profile_val: int = is_profile  # bool is a subtype of int
            if not _is_pg():
                is_profile_val = 1 if is_profile else 0
            _upsert(
                conn,
                "person_photos",
                ["person_id", "photo_id", "is_profile", "display_order", "caption"],
                (person_id, photo_id, is_profile_val, display_order, caption),
                ["person_id", "photo_id"],
            )
            conn.commit()
        finally:
            conn.close()

    def unassign_photo_from_person(self, person_id: str, photo_id: int) -> None:
        """Remove a photo from a person."""
        conn = self._conn()
        try:
            _execute(
                conn,
                f"DELETE FROM person_photos WHERE person_id = {_ph()} AND photo_id = {_ph()}",
                (person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def set_profile_photo(self, person_id: str, photo_id: int) -> None:
        """Set a photo as the profile photo for a person, clearing others."""
        conn = self._conn()
        try:
            false_val = False if _is_pg() else 0
            true_val = True if _is_pg() else 1
            _execute(
                conn,
                f"UPDATE person_photos SET is_profile = {_ph()} WHERE person_id = {_ph()}",
                (false_val, person_id),
            )
            _execute(
                conn,
                f"UPDATE person_photos SET is_profile = {_ph()} WHERE person_id = {_ph()} AND photo_id = {_ph()}",
                (true_val, person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def set_photo_caption_new(
        self, person_id: str, photo_id: int, caption: str
    ) -> None:
        """Set the caption for a person-photo link."""
        conn = self._conn()
        try:
            _execute(
                conn,
                f"UPDATE person_photos SET caption = {_ph()} WHERE person_id = {_ph()} AND photo_id = {_ph()}",
                (caption, person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def list_all_photos(self) -> list[dict]:
        """Return all photos with their tagged people and face regions."""
        conn = self._conn()
        try:
            photos = _fetchall(conn, "SELECT * FROM photos ORDER BY id")
            p = _ph()
            for photo in photos:
                people = _fetchall(
                    conn,
                    f"""
                    SELECT pp.person_id, pp.is_profile, pp.caption,
                           pp.crop_x, pp.crop_y, pp.crop_w, pp.crop_h,
                           ppl.given_name, ppl.surname
                    FROM person_photos pp
                    JOIN people ppl ON ppl.id = pp.person_id
                    WHERE pp.photo_id = {p}
                    ORDER BY pp.display_order
                """,
                    (photo["id"],),
                )
                photo["tagged_people"] = people
                try:
                    regions = _fetchall(
                        conn,
                        f"""
                        SELECT fr.id, fr.person_id, fr.x, fr.y, fr.w, fr.h,
                               ppl.given_name, ppl.surname
                        FROM face_regions fr
                        JOIN people ppl ON ppl.id = fr.person_id
                        WHERE fr.photo_id = {p}
                        ORDER BY fr.id
                    """,
                        (photo["id"],),
                    )
                    photo["face_regions"] = regions
                except Exception:
                    photo["face_regions"] = []
                    if _is_pg():
                        conn.rollback()
            return photos
        finally:
            conn.close()

    # ── Face Regions ──────────────────────────────────────────────────

    def save_face_region(
        self, photo_id: int, person_id: str, x: float, y: float, w: float, h: float
    ) -> int:
        """Insert a face region for a person on a photo. Returns the region id.

        Multiple regions per person per photo are allowed (for montages).
        """
        conn = self._conn()
        try:
            _execute(
                conn,
                f"""
                INSERT INTO face_regions (photo_id, person_id, x, y, w, h)
                VALUES ({_ph(6)})
            """,
                (photo_id, person_id, x, y, w, h),
            )
            conn.commit()
            if _is_pg():
                row = _scalar(conn, "SELECT lastval() AS id")
            else:
                row = _scalar(conn, "SELECT last_insert_rowid() AS id")
            return row["id"]
        finally:
            conn.close()

    def get_face_regions(self, photo_id: int) -> list[dict]:
        """Return all face regions for a photo, with person names."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchall(
                conn,
                f"""
                SELECT fr.id, fr.photo_id, fr.person_id, fr.x, fr.y, fr.w, fr.h,
                       ppl.given_name, ppl.surname
                FROM face_regions fr
                JOIN people ppl ON ppl.id = fr.person_id
                WHERE fr.photo_id = {p}
                ORDER BY fr.id
            """,
                (photo_id,),
            )
        finally:
            conn.close()

    def delete_face_region(self, region_id: int) -> None:
        """Delete a face region by id."""
        conn = self._conn()
        try:
            _execute(conn, f"DELETE FROM face_regions WHERE id = {_ph()}", (region_id,))
            conn.commit()
        finally:
            conn.close()

    def face_region_for_person_photo(
        self, photo_id: int, person_id: str
    ) -> dict | None:
        """Return the face region for a specific person on a specific photo."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchone(
                conn,
                f"""
                SELECT id, photo_id, person_id, x, y, w, h
                FROM face_regions
                WHERE photo_id = {p} AND person_id = {p}
            """,
                (photo_id, person_id),
            )
        finally:
            conn.close()

    # ── Profile Crop ───────────────────────────────────────────────────

    def set_profile_crop(
        self,
        person_id: str,
        photo_id: int,
        crop_x: float,
        crop_y: float,
        crop_w: float,
        crop_h: float,
    ) -> None:
        """Set the crop region for a person's profile photo."""
        conn = self._conn()
        try:
            p = _ph()
            _execute(
                conn,
                f"""
                UPDATE person_photos
                SET crop_x = {p}, crop_y = {p}, crop_w = {p}, crop_h = {p}
                WHERE person_id = {p} AND photo_id = {p}
            """,
                (crop_x, crop_y, crop_w, crop_h, person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def clear_profile_crop(self, person_id: str, photo_id: int) -> None:
        """Clear the crop region for a person's profile photo."""
        conn = self._conn()
        try:
            p = _ph()
            _execute(
                conn,
                f"""
                UPDATE person_photos
                SET crop_x = NULL, crop_y = NULL, crop_w = NULL, crop_h = NULL
                WHERE person_id = {p} AND photo_id = {p}
            """,
                (person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _sync_person_photos(self, conn: Any, person: "Person") -> None:
        """Sync the new photos/person_photos tables from a person's photo_paths.

        Called during save_person for dual-write compatibility.
        """
        p = _ph()
        for idx, file_path in enumerate(person.photo_paths):
            _upsert(
                conn, "photos", ["file_path"], (file_path,), ["file_path"], update=False
            )

            row = _scalar(
                conn, f"SELECT id FROM photos WHERE file_path = {p}", (file_path,)
            )
            photo_id = row["id"]

            caption = person.photo_captions.get(file_path, "")

            existing = _fetchone(
                conn,
                f"""
                SELECT is_profile FROM person_photos
                WHERE person_id = {p} AND photo_id = {p}
            """,
                (person.id, photo_id),
            )

            if existing:
                _execute(
                    conn,
                    f"""
                    UPDATE person_photos SET display_order = {p}, caption = {p}
                    WHERE person_id = {p} AND photo_id = {p}
                """,
                    (idx, caption, person.id, photo_id),
                )
            else:
                is_profile_val: int = idx == 0  # bool is a subtype of int
                if not _is_pg():
                    is_profile_val = 1 if is_profile_val else 0
                _execute(
                    conn,
                    f"""
                    INSERT INTO person_photos (person_id, photo_id, is_profile, display_order, caption)
                    VALUES ({_ph(5)})
                """,
                    (person.id, photo_id, is_profile_val, idx, caption),
                )

        current_photos = _fetchall(
            conn,
            f"""
            SELECT p.file_path, pp.photo_id FROM person_photos pp
            JOIN photos p ON p.id = pp.photo_id
            WHERE pp.person_id = {p}
        """,
            (person.id,),
        )
        paths_set = set(person.photo_paths)
        for cp in current_photos:
            if cp["file_path"] not in paths_set:
                _execute(
                    conn,
                    f"DELETE FROM person_photos WHERE person_id = {p} AND photo_id = {p}",
                    (person.id, cp["photo_id"]),
                )

    # ── Internal helpers ────────────────────────────────────────────────

    def get_person_by_email(self, email: str) -> Person | None:
        """Fetch a single Person by email address."""
        conn = self._conn()
        try:
            row = _fetchone(
                conn,
                f"SELECT * FROM people WHERE email = {_ph()}",
                (email,),
            )
            return self._row_to_person(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def _row_to_person(row: dict) -> Person:
        return Person(
            id=row["id"],
            given_name=row["given_name"],
            surname=row["surname"],
            gender=Gender(row["gender"]),
            birth_date=row["birth_date"] or None,
            birth_place=row["birth_place"] or None,
            death_date=row["death_date"] or None,
            death_place=row["death_place"] or None,
            maiden_name=row["maiden_name"] or None,
            nicknames=json.loads(row["nicknames"] or "[]"),
            notes=row["notes"] or "",
            photo_paths=json.loads(row["photo_paths"] or "[]"),
            photo_captions=json.loads(row.get("photo_captions") or "{}"),
            email=row.get("email") or None,
        )

    @staticmethod
    def _row_to_source(row: dict) -> Source:
        return Source(
            id=row["id"],
            name=row["name"],
            source_type=SourceType(row["source_type"]),
            author=row["author"],
            date=row["date"],
            description=row["description"] or "",
            url=row["url"],
        )

    @staticmethod
    def _row_to_article(row: dict) -> NewsArticle:
        return NewsArticle(
            id=row["id"],
            title=row["title"],
            url=row.get("url"),
            publication=row.get("publication"),
            date=row.get("date"),
            summary=row.get("summary") or "",
            photo_url=row.get("photo_url"),
        )

    @staticmethod
    def _row_to_citation(row: dict) -> Citation:
        return Citation(
            source_id=row["source_id"],
            entity_type=EntityType(row["entity_type"]),
            entity_id=row["entity_id"],
            field_name=row["field_name"],
            excerpt=row["excerpt"] or "",
            confidence=Confidence(row["confidence"]),
            notes=row["notes"] or "",
        )
