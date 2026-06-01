"""News articles domain mixin for TreeRepository."""

from typing import Any

from models.article import NewsArticle

from ._sql import _execute, _fetchall, _fetchone, _ph, _upsert


class ArticlesRepoMixin:
    """CRUD operations for news_articles and person_articles tables."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

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
            _upsert(
                conn,
                "news_articles",
                ["id", "title", "url", "publication", "date", "summary", "photo_url"],
                params,
                ["id"],
            )
            conn.commit()
        finally:
            conn.close()

    def get_article(self, article_id: str) -> NewsArticle | None:
        """Fetch a single NewsArticle by ID."""
        conn = self._conn()
        try:
            row = _fetchone(conn, f"SELECT * FROM news_articles WHERE id = {_ph()}", (article_id,))
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
            _upsert(
                conn,
                "person_articles",
                ["person_id", "article_id"],
                (person_id, article_id),
                ["person_id", "article_id"],
                update=False,
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
