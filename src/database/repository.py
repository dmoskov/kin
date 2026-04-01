"""TreeRepository — CRUD operations mapping domain models to SQLite.

The repository is the bridge between the in-memory domain models (Person,
Relationship, Union, LifeEvent, FamilyTree) and the SQLite database.

Usage:
    from database import TreeRepository, init_db

    init_db()
    repo = TreeRepository()
    repo.save_person(person)
    tree = repo.load_tree()
"""

import json
import sqlite3
from typing import Optional

from models.person import Gender, Person
from models.relationship import Relationship, RelationshipType, Union
from models.event import EventType, LifeEvent
from models.tree import FamilyTree

from .connection import get_connection


class TreeRepository:
    """Persistence layer for FamilyTree data in SQLite."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    # ── People ──────────────────────────────────────────────────────────

    def save_person(self, person: Person) -> None:
        """Insert or replace a Person in the database."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO people
                    (id, given_name, surname, gender, birth_date, birth_place,
                     death_date, death_place, maiden_name, nicknames, notes,
                     photo_paths, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
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
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_person(self, person_id: str) -> Optional[Person]:
        """Fetch a single Person by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM people WHERE id = ?", (person_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_person(row)
        finally:
            conn.close()

    def list_people(self) -> list[Person]:
        """Fetch all people, ordered by surname then given name."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM people ORDER BY surname, given_name"
            ).fetchall()
            return [self._row_to_person(r) for r in rows]
        finally:
            conn.close()

    def search_people(self, query: str) -> list[Person]:
        """Search people by name (case-insensitive substring match)."""
        conn = self._conn()
        try:
            pattern = f"%{query}%"
            rows = conn.execute(
                """
                SELECT * FROM people
                WHERE given_name LIKE ? OR surname LIKE ?
                   OR maiden_name LIKE ? OR nicknames LIKE ?
                   OR notes LIKE ?
                ORDER BY surname, given_name
                """,
                (pattern, pattern, pattern, pattern, pattern),
            ).fetchall()
            return [self._row_to_person(r) for r in rows]
        finally:
            conn.close()

    def delete_person(self, person_id: str) -> bool:
        """Delete a person and all their relationships/events (cascading)."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM people WHERE id = ?", (person_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ── Relationships ───────────────────────────────────────────────────

    def save_relationship(self, rel: Relationship) -> None:
        """Insert a parent-child relationship (ignore if duplicate)."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO relationships (parent_id, child_id, rel_type)
                VALUES (?, ?, ?)
                """,
                (rel.parent_id, rel.child_id, rel.rel_type.value),
            )
            conn.commit()
        finally:
            conn.close()

    # ── Unions ──────────────────────────────────────────────────────────

    def save_union(self, union: Union) -> None:
        """Insert a marriage/partnership."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO unions
                    (partner1_id, partner2_id, union_date, union_place,
                     end_date, end_reason, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
            conn.commit()
        finally:
            conn.close()

    # ── Events ──────────────────────────────────────────────────────────

    def save_event(self, event: LifeEvent) -> None:
        """Insert a life event."""
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO events
                    (person_id, event_type, date, end_date, place,
                     description, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
            conn.commit()
        finally:
            conn.close()

    # ── Bulk operations ─────────────────────────────────────────────────

    def save_tree(self, tree: FamilyTree) -> None:
        """Save an entire FamilyTree to the database in a single transaction."""
        conn = self._conn()
        try:
            for person in tree.people.values():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO people
                        (id, given_name, surname, gender, birth_date, birth_place,
                         death_date, death_place, maiden_name, nicknames, notes,
                         photo_paths, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
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
                    ),
                )

            for rel in tree.relationships:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO relationships (parent_id, child_id, rel_type)
                    VALUES (?, ?, ?)
                    """,
                    (rel.parent_id, rel.child_id, rel.rel_type.value),
                )

            for union in tree.unions:
                conn.execute(
                    """
                    INSERT INTO unions
                        (partner1_id, partner2_id, union_date, union_place,
                         end_date, end_reason, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
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

            for event in tree.events:
                conn.execute(
                    """
                    INSERT INTO events
                        (person_id, event_type, date, end_date, place,
                         description, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
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

            conn.commit()
        finally:
            conn.close()

    def load_tree(self) -> FamilyTree:
        """Load the entire family tree from the database into memory."""
        conn = self._conn()
        try:
            tree = FamilyTree()

            # People
            for row in conn.execute("SELECT * FROM people").fetchall():
                tree.add_person(self._row_to_person(row))

            # Relationships
            for row in conn.execute("SELECT * FROM relationships").fetchall():
                tree.add_relationship(
                    Relationship(
                        parent_id=row["parent_id"],
                        child_id=row["child_id"],
                        rel_type=RelationshipType(row["rel_type"]),
                    )
                )

            # Unions
            for row in conn.execute("SELECT * FROM unions").fetchall():
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

            # Events
            for row in conn.execute("SELECT * FROM events").fetchall():
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
                row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
                counts[table] = row["n"]

            # Living vs deceased
            living = conn.execute(
                "SELECT COUNT(*) as n FROM people WHERE death_date IS NULL"
            ).fetchone()["n"]
            counts["living"] = living
            counts["deceased"] = counts["people"] - living

            return counts
        finally:
            conn.close()

    # ── Internal helpers ────────────────────────────────────────────────

    @staticmethod
    def _row_to_person(row: sqlite3.Row) -> Person:
        """Convert a database row to a Person domain object."""
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
