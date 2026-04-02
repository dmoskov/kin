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
import os
from typing import Any, Optional

from models.person import Gender, Person
from models.relationship import Relationship, RelationshipType, Union
from models.event import EventType, LifeEvent
from models.source import Source, SourceType
from models.citation import Citation, EntityType, Confidence
from models.tree import FamilyTree

from .connection import get_connection


def _is_pg() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


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


def _fetchone(conn: Any, sql: str, params: tuple = ()) -> Optional[dict]:
    """Execute and fetch one row as a dict."""
    cur = _execute(conn, sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    # sqlite3.Row supports dict-style access; psycopg2 RealDictRow is already dict
    return dict(row)


def _fetchall(conn: Any, sql: str, params: tuple = ()) -> list[dict]:
    """Execute and fetch all rows as dicts."""
    cur = _execute(conn, sql, params)
    return [dict(r) for r in cur.fetchall()]


class TreeRepository:
    """Persistence layer for FamilyTree data (SQLite or PostgreSQL)."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self) -> Any:
        return get_connection(self._db_path)

    # ── People ──────────────────────────────────────────────────────────

    def save_person(self, person: Person) -> None:
        """Insert or upsert a Person."""
        conn = self._conn()
        params = (
            person.id,
            person.given_name,
            person.surname,
            person.gender.value,
            person.birth_date,
            person.birth_place,
            person.death_date,
            person.death_place,
            person.maiden_name,
            json.dumps(person.nicknames),
            person.notes,
            json.dumps(person.photo_paths),
        )
        try:
            if _is_pg():
                _execute(conn, f"""
                    INSERT INTO people
                        (id, given_name, surname, gender, birth_date, birth_place,
                         death_date, death_place, maiden_name, nicknames, notes,
                         photo_paths, updated_at)
                    VALUES ({_ph(12)}, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        given_name=EXCLUDED.given_name, surname=EXCLUDED.surname,
                        gender=EXCLUDED.gender, birth_date=EXCLUDED.birth_date,
                        birth_place=EXCLUDED.birth_place, death_date=EXCLUDED.death_date,
                        death_place=EXCLUDED.death_place, maiden_name=EXCLUDED.maiden_name,
                        nicknames=EXCLUDED.nicknames, notes=EXCLUDED.notes,
                        photo_paths=EXCLUDED.photo_paths, updated_at=NOW()
                """, params)
            else:
                _execute(conn, f"""
                    INSERT OR REPLACE INTO people
                        (id, given_name, surname, gender, birth_date, birth_place,
                         death_date, death_place, maiden_name, nicknames, notes,
                         photo_paths, updated_at)
                    VALUES ({_ph(12)}, datetime('now'))
                """, params)
            conn.commit()
        finally:
            conn.close()

    def get_person(self, person_id: str) -> Optional[Person]:
        """Fetch a single Person by ID."""
        conn = self._conn()
        try:
            row = _fetchone(conn, f"SELECT * FROM people WHERE id = {_ph()}", (person_id,))
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
                rows = _fetchall(conn, f"""
                    SELECT * FROM people
                    WHERE given_name ILIKE {p} OR surname ILIKE {p}
                       OR maiden_name ILIKE {p} OR nicknames ILIKE {p}
                       OR notes ILIKE {p}
                    ORDER BY surname, given_name
                """, (pattern,) * 5)
            else:
                rows = _fetchall(conn, f"""
                    SELECT * FROM people
                    WHERE given_name LIKE {p} OR surname LIKE {p}
                       OR maiden_name LIKE {p} OR nicknames LIKE {p}
                       OR notes LIKE {p}
                    ORDER BY surname, given_name
                """, (pattern,) * 5)
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
        params = (rel.parent_id, rel.child_id, rel.rel_type.value)
        try:
            if _is_pg():
                _execute(conn, f"""
                    INSERT INTO relationships (parent_id, child_id, rel_type)
                    VALUES ({_ph(3)})
                    ON CONFLICT (parent_id, child_id) DO NOTHING
                """, params)
            else:
                _execute(conn, f"""
                    INSERT OR IGNORE INTO relationships (parent_id, child_id, rel_type)
                    VALUES ({_ph(3)})
                """, params)
            conn.commit()
        finally:
            conn.close()

    # ── Unions ──────────────────────────────────────────────────────────

    def save_union(self, union: Union) -> None:
        """Insert a marriage/partnership."""
        conn = self._conn()
        params = (
            union.partner1_id, union.partner2_id, union.union_date,
            union.union_place, union.end_date, union.end_reason, union.notes,
        )
        try:
            _execute(conn, f"""
                INSERT INTO unions
                    (partner1_id, partner2_id, union_date, union_place,
                     end_date, end_reason, notes)
                VALUES ({_ph(7)})
            """, params)
            conn.commit()
        finally:
            conn.close()

    # ── Events ──────────────────────────────────────────────────────────

    def save_event(self, event: LifeEvent) -> None:
        """Insert a life event."""
        conn = self._conn()
        params = (
            event.person_id, event.event_type.value, event.date,
            event.end_date, event.place, event.description, event.source,
        )
        try:
            _execute(conn, f"""
                INSERT INTO events
                    (person_id, event_type, date, end_date, place,
                     description, source)
                VALUES ({_ph(7)})
            """, params)
            conn.commit()
        finally:
            conn.close()

    # ── Sources ─────────────────────────────────────────────────────────

    def save_source(self, source: Source) -> None:
        """Insert or upsert a Source."""
        conn = self._conn()
        params = (
            source.id, source.name, source.source_type.value,
            source.author, source.date, source.description, source.url,
        )
        try:
            if _is_pg():
                _execute(conn, f"""
                    INSERT INTO sources
                        (id, name, source_type, author, date, description, url)
                    VALUES ({_ph(7)})
                    ON CONFLICT (id) DO UPDATE SET
                        name=EXCLUDED.name, source_type=EXCLUDED.source_type,
                        author=EXCLUDED.author, date=EXCLUDED.date,
                        description=EXCLUDED.description, url=EXCLUDED.url
                """, params)
            else:
                _execute(conn, f"""
                    INSERT OR REPLACE INTO sources
                        (id, name, source_type, author, date, description, url)
                    VALUES ({_ph(7)})
                """, params)
            conn.commit()
        finally:
            conn.close()

    def get_source(self, source_id: str) -> Optional[Source]:
        """Fetch a single Source by ID."""
        conn = self._conn()
        try:
            row = _fetchone(conn, f"SELECT * FROM sources WHERE id = {_ph()}", (source_id,))
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
        params = (
            citation.source_id, citation.entity_type.value, citation.entity_id,
            citation.field_name, citation.excerpt, citation.confidence.value,
            citation.notes,
        )
        try:
            _execute(conn, f"""
                INSERT INTO citations
                    (source_id, entity_type, entity_id, field_name,
                     excerpt, confidence, notes)
                VALUES ({_ph(7)})
            """, params)
            conn.commit()
        finally:
            conn.close()

    def citations_for(
        self,
        entity_type: EntityType,
        entity_id: str,
        field_name: Optional[str] = None,
    ) -> list[Citation]:
        """Fetch all citations for a given entity (optionally filtered by field)."""
        conn = self._conn()
        try:
            p = _ph()
            if field_name:
                rows = _fetchall(conn, f"""
                    SELECT * FROM citations
                    WHERE entity_type = {p} AND entity_id = {p} AND field_name = {p}
                    ORDER BY id
                """, (entity_type.value, entity_id, field_name))
            else:
                rows = _fetchall(conn, f"""
                    SELECT * FROM citations
                    WHERE entity_type = {p} AND entity_id = {p}
                    ORDER BY id
                """, (entity_type.value, entity_id))
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

    # ── Bulk operations ─────────────────────────────────────────────────

    def save_tree(self, tree: FamilyTree) -> None:
        """Save an entire FamilyTree to the database in a single transaction."""
        conn = self._conn()
        try:
            for person in tree.people.values():
                params = (
                    person.id, person.given_name, person.surname,
                    person.gender.value, person.birth_date, person.birth_place,
                    person.death_date, person.death_place, person.maiden_name,
                    json.dumps(person.nicknames), person.notes,
                    json.dumps(person.photo_paths),
                )
                if _is_pg():
                    _execute(conn, f"""
                        INSERT INTO people
                            (id, given_name, surname, gender, birth_date, birth_place,
                             death_date, death_place, maiden_name, nicknames, notes,
                             photo_paths, updated_at)
                        VALUES ({_ph(12)}, NOW())
                        ON CONFLICT (id) DO UPDATE SET
                            given_name=EXCLUDED.given_name, surname=EXCLUDED.surname,
                            gender=EXCLUDED.gender, birth_date=EXCLUDED.birth_date,
                            birth_place=EXCLUDED.birth_place, death_date=EXCLUDED.death_date,
                            death_place=EXCLUDED.death_place, maiden_name=EXCLUDED.maiden_name,
                            nicknames=EXCLUDED.nicknames, notes=EXCLUDED.notes,
                            photo_paths=EXCLUDED.photo_paths, updated_at=NOW()
                    """, params)
                else:
                    _execute(conn, f"""
                        INSERT OR REPLACE INTO people
                            (id, given_name, surname, gender, birth_date, birth_place,
                             death_date, death_place, maiden_name, nicknames, notes,
                             photo_paths, updated_at)
                        VALUES ({_ph(12)}, datetime('now'))
                    """, params)

            for rel in tree.relationships:
                params = (rel.parent_id, rel.child_id, rel.rel_type.value)
                if _is_pg():
                    _execute(conn, f"""
                        INSERT INTO relationships (parent_id, child_id, rel_type)
                        VALUES ({_ph(3)})
                        ON CONFLICT (parent_id, child_id) DO NOTHING
                    """, params)
                else:
                    _execute(conn, f"""
                        INSERT OR IGNORE INTO relationships (parent_id, child_id, rel_type)
                        VALUES ({_ph(3)})
                    """, params)

            for union in tree.unions:
                _execute(conn, f"""
                    INSERT INTO unions
                        (partner1_id, partner2_id, union_date, union_place,
                         end_date, end_reason, notes)
                    VALUES ({_ph(7)})
                """, (
                    union.partner1_id, union.partner2_id, union.union_date,
                    union.union_place, union.end_date, union.end_reason, union.notes,
                ))

            for event in tree.events:
                _execute(conn, f"""
                    INSERT INTO events
                        (person_id, event_type, date, end_date, place,
                         description, source)
                    VALUES ({_ph(7)})
                """, (
                    event.person_id, event.event_type.value, event.date,
                    event.end_date, event.place, event.description, event.source,
                ))

            for source in tree.sources.values():
                params = (
                    source.id, source.name, source.source_type.value,
                    source.author, source.date, source.description, source.url,
                )
                if _is_pg():
                    _execute(conn, f"""
                        INSERT INTO sources
                            (id, name, source_type, author, date, description, url)
                        VALUES ({_ph(7)})
                        ON CONFLICT (id) DO UPDATE SET
                            name=EXCLUDED.name, source_type=EXCLUDED.source_type,
                            author=EXCLUDED.author, date=EXCLUDED.date,
                            description=EXCLUDED.description, url=EXCLUDED.url
                    """, params)
                else:
                    _execute(conn, f"""
                        INSERT OR REPLACE INTO sources
                            (id, name, source_type, author, date, description, url)
                        VALUES ({_ph(7)})
                    """, params)

            for citation in tree.citations:
                _execute(conn, f"""
                    INSERT INTO citations
                        (source_id, entity_type, entity_id, field_name,
                         excerpt, confidence, notes)
                    VALUES ({_ph(7)})
                """, (
                    citation.source_id, citation.entity_type.value, citation.entity_id,
                    citation.field_name, citation.excerpt, citation.confidence.value,
                    citation.notes,
                ))

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
                row = _fetchone(conn, f"SELECT COUNT(*) as n FROM {table}")
                counts[table] = row["n"]

            row = _fetchone(
                conn, "SELECT COUNT(*) as n FROM people WHERE death_date IS NULL"
            )
            counts["living"] = row["n"]
            counts["deceased"] = counts["people"] - counts["living"]

            try:
                counts["sources"] = _fetchone(
                    conn, "SELECT COUNT(*) as n FROM sources"
                )["n"]
                counts["citations"] = _fetchone(
                    conn, "SELECT COUNT(*) as n FROM citations"
                )["n"]
            except Exception:
                if _is_pg():
                    conn.rollback()
                counts["sources"] = 0
                counts["citations"] = 0

            return counts
        finally:
            conn.close()

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _row_to_person(row: dict) -> Person:
        return Person(
            id=row["id"],
            given_name=row["given_name"],
            surname=row["surname"],
            gender=Gender(row["gender"]),
            birth_date=row["birth_date"],
            birth_place=row["birth_place"],
            death_date=row["death_date"],
            death_place=row["death_place"],
            maiden_name=row["maiden_name"],
            nicknames=json.loads(row["nicknames"] or "[]"),
            notes=row["notes"] or "",
            photo_paths=json.loads(row["photo_paths"] or "[]"),
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
