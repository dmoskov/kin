"""Citation — links a specific fact to a Source.

Citations are the glue between the family data and its provenance.
Any entity (person, relationship, union, event) can have citations,
optionally scoped to a specific field (e.g., "birth_date").
"""

from dataclasses import dataclass
from enum import Enum


class EntityType(Enum):
    PERSON = "person"
    RELATIONSHIP = "relationship"
    UNION = "union"
    EVENT = "event"


class Confidence(Enum):
    CONFIRMED = "confirmed"  # multiple sources agree, or primary source
    PROBABLE = "probable"  # single reliable source
    UNCERTAIN = "uncertain"  # inferred, partially legible, estimated
    CONFLICTING = "conflicting"  # sources disagree on this fact


@dataclass
class Citation:
    """A link between a source and a specific fact in the tree.

    Attributes:
        source_id: Which source this cites
        entity_type: What kind of entity is being cited (person, relationship, etc.)
        entity_id: The ID of the cited entity
        field_name: Optional — which specific field (e.g., "birth_date", "birth_place")
        excerpt: Relevant quote or description from the source
        confidence: How reliable is this citation
        notes: Additional context
    """

    source_id: str
    entity_type: EntityType
    entity_id: str
    field_name: str | None = None
    excerpt: str = ""
    confidence: Confidence = Confidence.CONFIRMED
    notes: str = ""

    def __repr__(self) -> str:
        scope = f".{self.field_name}" if self.field_name else ""
        return f"Citation({self.source_id} → {self.entity_type.value}:{self.entity_id}{scope})"
