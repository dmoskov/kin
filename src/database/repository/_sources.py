"""Sources and citations domain mixin for TreeRepository."""

from typing import Any

from models.citation import Citation, Confidence, EntityType
from models.source import Source, SourceType

from ._sql import _execute, _fetchall, _fetchone, _ph, _upsert


class SourcesRepoMixin:
    """CRUD operations for sources and citations tables."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

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
