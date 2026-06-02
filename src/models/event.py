"""LifeEvent — significant moments attached to a person.

Events are how we capture the narrative: immigration journeys, career milestones,
moves, education. They give the tree its story beyond just birth-marriage-death.
"""

from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    BIRTH = "birth"
    DEATH = "death"
    MARRIAGE = "marriage"
    DIVORCE = "divorce"
    IMMIGRATION = "immigration"
    EMIGRATION = "emigration"
    NATURALIZATION = "naturalization"
    EDUCATION = "education"
    CAREER = "career"
    MILITARY = "military"
    RESIDENCE = "residence"
    RELIGION = "religion"
    MEDICAL = "medical"
    CUSTOM = "custom"


@dataclass
class LifeEvent:
    """A life event associated with a person.

    Events are timestamped and located. They form the narrative
    timeline of a person's life.
    """

    person_id: str
    event_type: EventType
    date: str | None = None  # ISO date (partial OK)
    end_date: str | None = None  # for spans (education, career, residence)
    place: str | None = None
    description: str = ""
    source: str | None = None  # where we learned this (document, oral, etc.)
    date_circa: bool = False

    @property
    def year(self) -> int | None:
        if self.date:
            return int(self.date[:4])
        return None

    def __repr__(self) -> str:
        return f"LifeEvent({self.event_type.value}, {self.date or '?'}, {self.person_id})"
