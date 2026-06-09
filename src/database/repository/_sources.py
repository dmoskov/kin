"""Sources and citations domain mixin for TreeRepository."""

from typing import Any

from models.citation import Citation, Confidence, EntityType
from models.source import Source, SourceType

from ._sql import _execute, _fetchall, _fetchone, _is_pg, _ph, _upsert

# Sentinel distinguishing "argument not provided" from an explicit None.
_UNSET: Any = object()


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

    def update_source(
        self,
        source_id: str,
        *,
        name: str = _UNSET,
        source_type: str = _UNSET,
        author: str | None = _UNSET,
        date: str | None = _UNSET,
        description: str = _UNSET,
        url: str | None = _UNSET,
    ) -> bool:
        """Update fields on an existing source. Returns True if a row changed."""
        sets: list[str] = []
        params: list = []
        for col, val in [
            ("name", name),
            ("source_type", source_type),
            ("author", author),
            ("date", date),
            ("description", description),
            ("url", url),
        ]:
            if val is not _UNSET:
                sets.append(f"{col} = {_ph()}")
                params.append(val)
        if not sets:
            return False

        params.append(source_id)
        conn = self._conn()
        try:
            cur = _execute(
                conn,
                f"UPDATE sources SET {', '.join(sets)} WHERE id = {_ph()}",
                tuple(params),
            )
            conn.commit()
            return (getattr(cur, "rowcount", 0) or 0) > 0
        finally:
            conn.close()

    def delete_source(self, source_id: str) -> bool:
        """Delete a source (cascades to its citations). Returns True if removed."""
        conn = self._conn()
        try:
            cur = _execute(conn, f"DELETE FROM sources WHERE id = {_ph()}", (source_id,))
            conn.commit()
            return (getattr(cur, "rowcount", 0) or 0) > 0
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

    def save_citation_returning_id(self, citation: Citation) -> int:
        """Insert a citation and return the new row id (cross-backend)."""
        cols = "(source_id, entity_type, entity_id, field_name, excerpt, confidence, notes)"
        vals = (
            citation.source_id,
            citation.entity_type.value,
            citation.entity_id,
            citation.field_name,
            citation.excerpt,
            citation.confidence.value,
            citation.notes,
        )
        conn = self._conn()
        try:
            if _is_pg():
                row = _fetchone(
                    conn,
                    f"INSERT INTO citations {cols} VALUES ({_ph(7)}) RETURNING id",
                    vals,
                )
                conn.commit()
                assert row is not None  # INSERT ... RETURNING always yields a row
                return row["id"]
            cur = conn.cursor()
            cur.execute(f"INSERT INTO citations {cols} VALUES ({_ph(7)})", vals)
            new_id = cur.lastrowid
            conn.commit()
            return new_id
        finally:
            conn.close()

    def get_citation(self, citation_id: int) -> Citation | None:
        """Fetch a single citation by row id."""
        conn = self._conn()
        try:
            row = _fetchone(conn, f"SELECT * FROM citations WHERE id = {_ph()}", (citation_id,))
            return self._row_to_citation(row) if row else None
        finally:
            conn.close()

    def update_citation(
        self,
        citation_id: int,
        *,
        field_name: str | None = _UNSET,
        excerpt: str = _UNSET,
        confidence: str = _UNSET,
        notes: str = _UNSET,
    ) -> bool:
        """Update a citation's field/excerpt/confidence/notes. The source and
        cited entity are immutable — delete and re-create to re-point a citation.

        Returns True if a row changed.
        """
        sets: list[str] = []
        params: list = []
        for col, val in [
            ("field_name", field_name),
            ("excerpt", excerpt),
            ("confidence", confidence),
            ("notes", notes),
        ]:
            if val is not _UNSET:
                sets.append(f"{col} = {_ph()}")
                params.append(val)
        if not sets:
            return False

        params.append(citation_id)
        conn = self._conn()
        try:
            cur = _execute(
                conn,
                f"UPDATE citations SET {', '.join(sets)} WHERE id = {_ph()}",
                tuple(params),
            )
            conn.commit()
            return (getattr(cur, "rowcount", 0) or 0) > 0
        finally:
            conn.close()

    def delete_citation(self, citation_id: int) -> bool:
        """Delete a citation by row id. Returns True if removed."""
        conn = self._conn()
        try:
            cur = _execute(conn, f"DELETE FROM citations WHERE id = {_ph()}", (citation_id,))
            conn.commit()
            return (getattr(cur, "rowcount", 0) or 0) > 0
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
            id=row["id"],
            source_id=row["source_id"],
            entity_type=EntityType(row["entity_type"]),
            entity_id=row["entity_id"],
            field_name=row["field_name"],
            excerpt=row["excerpt"] or "",
            confidence=Confidence(row["confidence"]),
            notes=row["notes"] or "",
        )
