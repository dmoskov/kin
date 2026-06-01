"""NewsArticle — a news article referencing someone in the family tree.

Stores metadata about newspaper clippings, magazine features, online articles,
obituaries, and other press coverage that mention a family member.
"""

from dataclasses import dataclass


@dataclass
class NewsArticle:
    """A news article that references one or more people in the tree.

    Attributes:
        id: Unique identifier (e.g., "nyt-2024-obituary-john")
        title: Article headline
        url: Link to the article (may be None for print-only)
        publication: Newspaper/magazine/site name
        date: Publication date (free text: "2024-03-15", "March 2024")
        summary: Brief description or excerpt
        photo_url: Optional thumbnail/image URL from the article
    """

    id: str
    title: str
    url: str | None = None
    publication: str | None = None
    date: str | None = None
    summary: str = ""
    photo_url: str | None = None

    def __repr__(self) -> str:
        pub = f" ({self.publication})" if self.publication else ""
        return f"NewsArticle({self.id}, {self.title!r}{pub})"
