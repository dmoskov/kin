"""Events domain mixin for TreeRepository."""

from typing import Any

from models.event import LifeEvent

from ._sql import _execute, _fetchone, _is_pg, _ph


class EventsRepoMixin:
    """CRUD operations for the events table."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

    def _do_save_event(self, conn: Any, event: LifeEvent) -> None:
        date_circa_val = bool(event.date_circa) if _is_pg() else (1 if event.date_circa else 0)
        _execute(
            conn,
            f"""
            INSERT INTO events
                (person_id, event_type, date, end_date, place,
                 description, source, date_circa)
            VALUES ({_ph(8)})
        """,
            (
                event.person_id,
                event.event_type.value,
                event.date,
                event.end_date,
                event.place,
                event.description,
                event.source,
                date_circa_val,
            ),
        )

    # ── Events ──────────────────────────────────────────────────────────

    def save_event(self, event: LifeEvent) -> None:
        """Insert a life event."""
        conn = self._conn()
        try:
            self._do_save_event(conn, event)
            conn.commit()
        finally:
            conn.close()

    def save_event_returning_id(self, event: LifeEvent) -> int:
        """Insert a life event and return the new row id."""
        conn = self._conn()
        try:
            date_circa_val = bool(event.date_circa) if _is_pg() else (1 if event.date_circa else 0)
            if _is_pg():
                row = _fetchone(
                    conn,
                    f"""
                    INSERT INTO events
                        (person_id, event_type, date, end_date, place,
                         description, source, date_circa)
                    VALUES ({_ph(8)})
                    RETURNING id
                    """,
                    (
                        event.person_id,
                        event.event_type.value,
                        event.date,
                        event.end_date,
                        event.place,
                        event.description,
                        event.source,
                        date_circa_val,
                    ),
                )
                conn.commit()
                assert row is not None  # INSERT ... RETURNING always yields a row
                return row["id"]
            else:
                cur = conn.cursor()
                cur.execute(
                    f"""
                    INSERT INTO events
                        (person_id, event_type, date, end_date, place,
                         description, source, date_circa)
                    VALUES ({_ph(8)})
                    """,
                    (
                        event.person_id,
                        event.event_type.value,
                        event.date,
                        event.end_date,
                        event.place,
                        event.description,
                        event.source,
                        date_circa_val,
                    ),
                )
                event_id = cur.lastrowid
                conn.commit()
                return event_id
        finally:
            conn.close()

    def update_event(self, event_id: int, **kwargs) -> dict | None:
        """Update an event by id. Returns the updated row or None."""
        allowed = {"event_type", "date", "end_date", "place", "description", "source", "date_circa"}
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
            return None
        params.append(event_id)
        conn = self._conn()
        try:
            _execute(conn, f"UPDATE events SET {', '.join(sets)} WHERE id = {_ph()}", tuple(params))
            row = _fetchone(conn, f"SELECT * FROM events WHERE id = {_ph()}", (event_id,))
            conn.commit()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_event(self, event_id: int) -> bool:
        """Delete an event by id. Returns True if a row was deleted."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM events WHERE id = {_ph()}", (event_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def get_event(self, event_id: int) -> dict | None:
        """Get an event by id."""
        conn = self._conn()
        try:
            row = _fetchone(conn, f"SELECT * FROM events WHERE id = {_ph()}", (event_id,))
            return dict(row) if row else None
        finally:
            conn.close()
