"""Person — an individual in the family tree.

The atomic node. Every relationship, event, and traversal starts from a Person.
"""

from dataclasses import dataclass, field
from enum import Enum


class Gender(Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass
class Person:
    """A person in the family tree.

    Attributes:
        id: Unique identifier (stable across imports)
        given_name: First/given name
        surname: Family name (at birth)
        gender: Gender
        birth_date: ISO date string (YYYY-MM-DD), partial OK (YYYY or YYYY-MM)
        birth_place: Free text location
        death_date: ISO date string if deceased, None if living
        death_place: Free text location
        maiden_name: Pre-marriage surname (if changed)
        nicknames: Alternate names
        notes: Free text biographical notes, stories
        photo_paths: Relative paths to photos in data/photos/
    """

    id: str
    given_name: str
    surname: str
    gender: Gender = Gender.UNKNOWN
    birth_date: str | None = None
    birth_place: str | None = None
    death_date: str | None = None
    death_place: str | None = None
    maiden_name: str | None = None
    nicknames: list[str] = field(default_factory=list)
    notes: str = ""
    photo_paths: list[str] = field(default_factory=list)
    photo_captions: dict[str, str] = field(default_factory=dict)
    email: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.surname}"

    @property
    def is_living(self) -> bool:
        return self.death_date is None

    @property
    def birth_year(self) -> int | None:
        if self.birth_date:
            return int(self.birth_date[:4])
        return None

    @property
    def death_year(self) -> int | None:
        if self.death_date:
            return int(self.death_date[:4])
        return None

    def __repr__(self) -> str:
        dates = f"{self.birth_date or '?'} – {self.death_date or 'living'}"
        return f"Person({self.full_name}, {dates})"
