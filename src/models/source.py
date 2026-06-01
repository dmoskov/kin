"""Source — a document, letter, or other origin of family tree information.

Each fact in the tree can cite one or more Sources via Citations.
This enables structured provenance tracking: "Where did we learn this?"
"""

from dataclasses import dataclass
from enum import Enum


class SourceType(Enum):
    DOCUMENT = "document"  # physical/scanned document (Golden Book, fan chart)
    LETTER = "letter"  # personal correspondence (Herb's letter)
    ORAL = "oral"  # oral history / interview
    PUBLIC = "public"  # publicly available (Wikipedia, Open Library)
    DIRECT = "direct"  # directly from a living family member
    OTHER = "other"


@dataclass
class Source:
    """A source of family tree information.

    Attributes:
        id: Unique identifier (e.g., "golden-book", "fan-chart-2016")
        name: Human-readable name
        source_type: Category of source
        author: Who created/provided this source
        date: When the source was created (free text: "May 2016", "1996")
        description: Additional context about the source
        url: For public sources (Wikipedia URL, etc.)
    """

    id: str
    name: str
    source_type: SourceType = SourceType.OTHER
    author: str | None = None
    date: str | None = None
    description: str = ""
    url: str | None = None

    def __repr__(self) -> str:
        return f"Source({self.id}, {self.name!r})"
