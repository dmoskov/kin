"""People domain mixin for TreeRepository."""

import json
from typing import TYPE_CHECKING, Any

from models.person import Gender, Person

from ._sql import _execute, _fetchall, _fetchone, _is_pg, _now, _ph, _upsert


class PeopleRepoMixin:
    """CRUD operations for the people table."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

    # _sync_person_photos lives in PhotosRepoMixin. Declare it for the type
    # checker ONLY: a real stub here would shadow the implementation at runtime,
    # because PeopleRepoMixin is first in TreeRepository's MRO (it once did,
    # silently no-op'ing the sync). Under TYPE_CHECKING it doesn't exist at
    # runtime, so the MRO resolves the real method.
    if TYPE_CHECKING:

        def _sync_person_photos(self, conn: Any, person: "Person") -> None: ...

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
                "email",
            ],
            params,
            ["id"],
            extra_columns=["updated_at"],
            extra_values=[_now()],
        )
        # person_photos is the source of truth. The legacy people.photo_paths /
        # photo_captions columns are gone (schema v20). This additive sync still
        # populates person_photos from person.photo_paths when it is set on the
        # in-memory object (e.g. by JSON/GEDCOM import); it never deletes.
        self._sync_person_photos(conn, person)

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
            # photo_paths / photo_captions columns were dropped in schema v20;
            # photos now live in person_photos. The Person fields stay (default
            # empty) so import can still set them and round-trip through sync.
            email=row.get("email") or None,
        )
