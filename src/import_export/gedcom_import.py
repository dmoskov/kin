"""GEDCOM import — parse standard .ged files into a FamilyTree.

GEDCOM (Genealogical Data Communication) is the de-facto file format used
by genealogy software such as Ancestry.com, FamilySearch, and Gramps.

Line format:  LEVEL [XREF] TAG [VALUE]
Example:
    0 @I1@ INDI
    1 NAME John /Smith/
    1 BIRT
    2 DATE 15 MAR 1930
    2 PLAC Chicago, IL
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from models.person import Gender, Person
from models.relationship import Relationship, Union
from models.event import EventType, LifeEvent
from models.tree import FamilyTree

# Maps GEDCOM month abbreviations to numeric months.
_MONTH_MAP = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}

# Regex for a GEDCOM line: level, optional xref, tag, optional value
_LINE_RE = re.compile(
    r"^(\d+)"  # level
    r"\s+(?:(@\w+@)\s+)?"  # optional xref id
    r"(\w+)"  # tag
    r"(?:\s+(.*))?$"  # optional value
)


def _parse_gedcom_date(raw: str) -> Optional[str]:
    """Convert a GEDCOM date string to an ISO-ish date (YYYY, YYYY-MM, or YYYY-MM-DD).

    Handles formats like:
        15 MAR 1930  -> 1930-03-15
        MAR 1930     -> 1930-03
        1930         -> 1930
        ABT 1930     -> 1930  (qualifiers stripped)
    """
    # Strip common qualifiers
    cleaned = re.sub(r"^(ABT|EST|CAL|BEF|AFT|BET|FROM|TO|INT)\s+", "", raw.strip())
    # Also strip "AND ..." portion from BET ... AND ...
    cleaned = re.sub(r"\s+AND\s+.*$", "", cleaned)

    parts = cleaned.split()
    if not parts:
        return None

    # Year only
    if len(parts) == 1 and parts[0].isdigit():
        return parts[0]

    # Month Year
    if len(parts) == 2 and parts[0].upper() in _MONTH_MAP and parts[1].isdigit():
        return f"{parts[1]}-{_MONTH_MAP[parts[0].upper()]}"

    # Day Month Year
    if len(parts) == 3 and parts[1].upper() in _MONTH_MAP and parts[2].isdigit():
        day = parts[0].zfill(2)
        return f"{parts[2]}-{_MONTH_MAP[parts[1].upper()]}-{day}"

    return None


def _parse_gedcom_name(raw: str) -> tuple[str, str]:
    """Parse 'Given /Surname/' into (given_name, surname)."""
    match = re.match(r"^(.*?)\s*/([^/]*)/", raw)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    # Fallback: no surname delimiters
    parts = raw.strip().split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return raw.strip(), ""


def _gedcom_sex_to_gender(sex: str) -> Gender:
    """Map GEDCOM SEX value to our Gender enum."""
    mapping = {"M": Gender.MALE, "F": Gender.FEMALE}
    return mapping.get(sex.strip().upper(), Gender.UNKNOWN)


def _tokenize(text: str) -> list[tuple[int, Optional[str], str, str]]:
    """Parse raw GEDCOM text into a list of (level, xref, tag, value) tuples."""
    lines: list[tuple[int, Optional[str], str, str]] = []
    for raw_line in text.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        m = _LINE_RE.match(raw_line)
        if not m:
            continue
        level = int(m.group(1))
        xref = m.group(2)  # may be None
        tag = m.group(3)
        value = m.group(4) or ""
        lines.append((level, xref, tag, value))
    return lines


# ---------------------------------------------------------------------------
# Record processors
# ---------------------------------------------------------------------------


def _process_indi(
    tokens: list[tuple[int, Optional[str], str, str]], start: int, xref: str
) -> tuple[Person, list[LifeEvent]]:
    """Process an INDI record starting at *start* and return a Person + events."""
    given = ""
    surname = ""
    gender = Gender.UNKNOWN
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    death_date: Optional[str] = None
    death_place: Optional[str] = None
    notes = ""
    events: list[LifeEvent] = []

    person_id = xref.strip("@")
    i = start + 1
    while i < len(tokens):
        level, _, tag, value = tokens[i]
        if level == 0:
            break

        if level == 1 and tag == "NAME":
            given, surname = _parse_gedcom_name(value)
        elif level == 1 and tag == "SEX":
            gender = _gedcom_sex_to_gender(value)
        elif level == 1 and tag == "NOTE":
            notes = value
        elif level == 1 and tag == "BIRT":
            # Collect sub-records
            i += 1
            while i < len(tokens) and tokens[i][0] > 1:
                _, _, stag, sval = tokens[i]
                if stag == "DATE":
                    birth_date = _parse_gedcom_date(sval)
                elif stag == "PLAC":
                    birth_place = sval
                i += 1
            # Create event
            events.append(
                LifeEvent(
                    person_id=person_id,
                    event_type=EventType.BIRTH,
                    date=birth_date,
                    place=birth_place,
                )
            )
            continue  # already advanced past sub-records
        elif level == 1 and tag == "DEAT":
            i += 1
            while i < len(tokens) and tokens[i][0] > 1:
                _, _, stag, sval = tokens[i]
                if stag == "DATE":
                    death_date = _parse_gedcom_date(sval)
                elif stag == "PLAC":
                    death_place = sval
                i += 1
            events.append(
                LifeEvent(
                    person_id=person_id,
                    event_type=EventType.DEATH,
                    date=death_date,
                    place=death_place,
                )
            )
            continue

        i += 1

    person = Person(
        id=person_id,
        given_name=given,
        surname=surname,
        gender=gender,
        birth_date=birth_date,
        birth_place=birth_place,
        death_date=death_date,
        death_place=death_place,
        notes=notes,
    )
    return person, events


def _process_fam(
    tokens: list[tuple[int, Optional[str], str, str]],
    start: int,
    xref: str,
) -> tuple[Optional[Union], list[Relationship], list[LifeEvent]]:
    """Process a FAM record. Returns a Union (if two partners), Relationships, and events."""
    husb: Optional[str] = None
    wife: Optional[str] = None
    children: list[str] = []
    marr_date: Optional[str] = None
    marr_place: Optional[str] = None
    events: list[LifeEvent] = []

    i = start + 1
    while i < len(tokens):
        level, _, tag, value = tokens[i]
        if level == 0:
            break

        if level == 1 and tag == "HUSB":
            husb = value.strip("@")
        elif level == 1 and tag == "WIFE":
            wife = value.strip("@")
        elif level == 1 and tag == "CHIL":
            children.append(value.strip("@"))
        elif level == 1 and tag == "MARR":
            i += 1
            while i < len(tokens) and tokens[i][0] > 1:
                _, _, stag, sval = tokens[i]
                if stag == "DATE":
                    marr_date = _parse_gedcom_date(sval)
                elif stag == "PLAC":
                    marr_place = sval
                i += 1
            continue

        i += 1

    # Build union
    union: Optional[Union] = None
    if husb and wife:
        union = Union(
            partner1_id=husb,
            partner2_id=wife,
            union_date=marr_date,
            union_place=marr_place,
        )
        # Marriage events for both partners
        for pid in (husb, wife):
            events.append(
                LifeEvent(
                    person_id=pid,
                    event_type=EventType.MARRIAGE,
                    date=marr_date,
                    place=marr_place,
                )
            )

    # Build parent-child relationships
    rels: list[Relationship] = []
    for parent_id in (husb, wife):
        if parent_id is None:
            continue
        for child_id in children:
            rels.append(Relationship(parent_id=parent_id, child_id=child_id))

    return union, rels, events


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_gedcom(path: str) -> FamilyTree:
    """Parse a GEDCOM (.ged) file and return a populated FamilyTree.

    Handles the following GEDCOM record types:
    - INDI -> Person (NAME, SEX, BIRT, DEAT, NOTE)
    - FAM  -> Union + Relationships (HUSB, WIFE, CHIL, MARR)
    """
    text = Path(path).read_text(encoding="utf-8-sig")  # BOM-safe
    tokens = _tokenize(text)
    tree = FamilyTree()

    i = 0
    while i < len(tokens):
        level, xref, tag, _value = tokens[i]
        if level == 0 and tag == "INDI" and xref:
            person, events = _process_indi(tokens, i, xref)
            tree.add_person(person)
            for ev in events:
                tree.add_event(ev)
        elif level == 0 and tag == "FAM" and xref:
            union, rels, events = _process_fam(tokens, i, xref)
            if union:
                tree.add_union(union)
            for rel in rels:
                tree.add_relationship(rel)
            for ev in events:
                tree.add_event(ev)
        i += 1

    return tree
