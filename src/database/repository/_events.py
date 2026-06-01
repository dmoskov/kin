"""Events domain mixin for TreeRepository."""

from typing import Any

from models.event import LifeEvent

from ._sql import _execute, _ph


class EventsRepoMixin:
    """CRUD operations for the events table."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

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

    # ── Events ──────────────────────────────────────────────────────────

    def save_event(self, event: LifeEvent) -> None:
        """Insert a life event."""
        conn = self._conn()
        try:
            self._do_save_event(conn, event)
            conn.commit()
        finally:
            conn.close()
