"""Whole-tree bulk operations and stats mixin for TreeRepository."""

from typing import Any

from models.event import EventType, LifeEvent
from models.relationship import Relationship, RelationshipType, Union, Visibility
from models.tree import FamilyTree

from ._sql import _fetchall, _is_pg, _scalar, _upsert


class TreeRepoMixin:
    """Bulk load/save and statistics operations for FamilyTree."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

    def _do_save_person(self, conn: Any, person: Any) -> None: ...  # provided by PeopleRepoMixin
    def _do_save_relationship(
        self, conn: Any, rel: Relationship
    ) -> None: ...  # provided by RelationshipsRepoMixin
    def _do_save_union(
        self, conn: Any, union: Union
    ) -> None: ...  # provided by RelationshipsRepoMixin
    def _do_save_event(
        self, conn: Any, event: LifeEvent
    ) -> None: ...  # provided by EventsRepoMixin
    def _do_save_source(self, conn: Any, source: Any) -> None: ...  # provided by SourcesRepoMixin
    def _do_save_citation(
        self, conn: Any, citation: Any
    ) -> None: ...  # provided by SourcesRepoMixin

    def _row_to_person(self, row: dict) -> Any: ...  # provided by PeopleRepoMixin
    def _row_to_source(self, row: dict) -> Any: ...  # provided by SourcesRepoMixin
    def _row_to_citation(self, row: dict) -> Any: ...  # provided by SourcesRepoMixin
    def _row_to_article(self, row: dict) -> Any: ...  # provided by ArticlesRepoMixin

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
                    (
                        article.id,
                        article.title,
                        article.url,
                        article.publication,
                        article.date,
                        article.summary,
                        article.photo_url,
                    ),
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
                        visibility=Visibility(row.get("visibility", "everyone")),
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
                        date_circa=bool(row.get("date_circa")),
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
                for row in _fetchall(conn, "SELECT person_id, article_id FROM person_articles"):
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

            row = _scalar(conn, "SELECT COUNT(*) as n FROM people WHERE death_date IS NULL")
            counts["living"] = row["n"]
            counts["deceased"] = counts["people"] - counts["living"]

            try:
                counts["sources"] = _scalar(conn, "SELECT COUNT(*) as n FROM sources")["n"]
                counts["citations"] = _scalar(conn, "SELECT COUNT(*) as n FROM citations")["n"]
            except Exception:
                if _is_pg():
                    conn.rollback()
                counts["sources"] = 0
                counts["citations"] = 0

            try:
                counts["articles"] = _scalar(conn, "SELECT COUNT(*) as n FROM news_articles")["n"]
            except Exception:
                if _is_pg():
                    conn.rollback()
                counts["articles"] = 0

            return counts
        finally:
            conn.close()
