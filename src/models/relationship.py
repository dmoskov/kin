"""Relationship — edges in the family graph.

Two fundamental edge types:
1. Parent-Child: directed (parent → child). The backbone of the tree.
2. Union (Marriage/Partnership): undirected link between two partners, with optional dates.

Everything else (siblings, grandparents, cousins) is computed by traversal.
"""

from dataclasses import dataclass
from enum import Enum


class RelationshipType(Enum):
    BIOLOGICAL = "biological"  # biological parent-child
    ADOPTIVE = "adoptive"  # adoptive parent-child
    STEP = "step"  # step-parent/step-child
    FOSTER = "foster"  # foster parent-child


class Visibility(Enum):
    EVERYONE = "everyone"
    SELF_AND_CHILDREN = "self_and_children"
    PRIVATE = "private"


@dataclass
class Relationship:
    """A parent-child relationship edge.

    Directed: parent_id → child_id.
    Type distinguishes biological from adoptive/step/foster.
    Visibility controls who can see birth-family connections.
    """

    parent_id: str
    child_id: str
    rel_type: RelationshipType = RelationshipType.BIOLOGICAL
    visibility: Visibility = Visibility.EVERYONE

    def involves(self, person_id: str) -> bool:
        return person_id in (self.parent_id, self.child_id)


@dataclass
class Union:
    """A marriage or partnership between two people.

    Not a parent-child link — this represents the couple bond itself.
    Children are linked to each parent individually via Relationship edges.
    """

    partner1_id: str
    partner2_id: str
    union_date: str | None = None  # ISO date
    union_place: str | None = None
    end_date: str | None = None  # divorce or death date
    end_reason: str | None = None  # "divorce", "death", "annulment"
    notes: str = ""

    @property
    def is_active(self) -> bool:
        return self.end_date is None

    def involves(self, person_id: str) -> bool:
        return person_id in (self.partner1_id, self.partner2_id)

    def other_partner(self, person_id: str) -> str:
        """Given one partner's ID, return the other's."""
        if person_id == self.partner1_id:
            return self.partner2_id
        elif person_id == self.partner2_id:
            return self.partner1_id
        raise ValueError(f"{person_id} not in this union")
