"""GEDCOM export — serialise a FamilyTree into a GEDCOM 5.5.1 text file.

Mirrors the field handling in gedcom_import.py so that a round-trip
(export → re-import) preserves all people, unions, and relationships.

GEDCOM 5.5.1 line format:  LEVEL [XREF] TAG [VALUE]

Key records emitted:
  0 HEAD   — file header
  0 @Ix@ INDI — one per person (NAME, SEX, BIRT, DEAT, events, NOTE)
  0 @Fx@ FAM  — one per union (HUSB, WIFE, CHIL, MARR)
  0 TRLR  — end-of-file trailer
"""

from __future__ import annotations

from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Union
from models.tree import FamilyTree

# Month number → GEDCOM month abbreviation (reverse of the importer's _MONTH_MAP)
_NUM_TO_MONTH: dict[str, str] = {
    "01": "JAN",
    "02": "FEB",
    "03": "MAR",
    "04": "APR",
    "05": "MAY",
    "06": "JUN",
    "07": "JUL",
    "08": "AUG",
    "09": "SEP",
    "10": "OCT",
    "11": "NOV",
    "12": "DEC",
}


def _iso_to_gedcom_date(date: str | None) -> str | None:
    """Convert an ISO-ish date string to a GEDCOM date.

    Handles:
        YYYY         -> YYYY
        YYYY-MM      -> MON YYYY
        YYYY-MM-DD   -> DD MON YYYY
    """
    if not date:
        return None
    parts = date.split("-")
    if len(parts) == 1:
        # Year only
        return parts[0]
    if len(parts) == 2:
        year, month = parts
        mon = _NUM_TO_MONTH.get(month)
        if mon:
            return f"{mon} {year}"
        return year
    if len(parts) >= 3:
        year, month, day = parts[0], parts[1], parts[2]
        mon = _NUM_TO_MONTH.get(month)
        if mon:
            return f"{day.lstrip('0') or '0'} {mon} {year}"
        return year
    return date


def _gender_to_gedcom(gender: Gender) -> str | None:
    """Map our Gender enum to a GEDCOM SEX value."""
    mapping = {
        Gender.MALE: "M",
        Gender.FEMALE: "F",
    }
    return mapping.get(gender)


def _indi_lines(person: Person, events: list[LifeEvent]) -> list[str]:
    """Build GEDCOM lines for one INDI record."""
    lines: list[str] = []
    pid = person.id
    lines.append(f"0 @{pid}@ INDI")

    # NAME — "Given /Surname/"
    given = person.given_name or ""
    surname = person.surname or ""
    lines.append(f"1 NAME {given} /{surname}/")

    # SEX
    sex = _gender_to_gedcom(person.gender)
    if sex:
        lines.append(f"1 SEX {sex}")

    # Collect birth and death events (prefer Person fields; fall back to events list)
    birth_date = person.birth_date
    birth_place = person.birth_place
    death_date = person.death_date
    death_place = person.death_place

    # Override/supplement from events if the person fields are missing
    for ev in events:
        if ev.person_id != pid:
            continue
        if ev.event_type == EventType.BIRTH:
            if birth_date is None and ev.date:
                birth_date = ev.date
            if birth_place is None and ev.place:
                birth_place = ev.place
        elif ev.event_type == EventType.DEATH:
            if death_date is None and ev.date:
                death_date = ev.date
            if death_place is None and ev.place:
                death_place = ev.place

    # BIRT
    if birth_date or birth_place:
        lines.append("1 BIRT")
        if birth_date:
            ged_date = _iso_to_gedcom_date(birth_date)
            if ged_date:
                lines.append(f"2 DATE {ged_date}")
        if birth_place:
            lines.append(f"2 PLAC {birth_place}")

    # DEAT
    if death_date or death_place:
        lines.append("1 DEAT")
        if death_date:
            ged_date = _iso_to_gedcom_date(death_date)
            if ged_date:
                lines.append(f"2 DATE {ged_date}")
        if death_place:
            lines.append(f"2 PLAC {death_place}")

    # NOTE
    if person.notes:
        # GEDCOM NOTE values must be single-line; replace newlines with spaces
        note = person.notes.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        lines.append(f"1 NOTE {note}")

    return lines


def _fam_lines(
    fam_id: str,
    union: Union,
    children: list[str],
) -> list[str]:
    """Build GEDCOM lines for one FAM record."""
    lines: list[str] = []
    lines.append(f"0 @{fam_id}@ FAM")
    lines.append(f"1 HUSB @{union.partner1_id}@")
    lines.append(f"1 WIFE @{union.partner2_id}@")

    for child_id in children:
        lines.append(f"1 CHIL @{child_id}@")

    # MARR
    if union.union_date or union.union_place:
        lines.append("1 MARR")
        if union.union_date:
            ged_date = _iso_to_gedcom_date(union.union_date)
            if ged_date:
                lines.append(f"2 DATE {ged_date}")
        if union.union_place:
            lines.append(f"2 PLAC {union.union_place}")

    return lines


def export_gedcom(tree: FamilyTree) -> str:
    """Serialise a FamilyTree into a GEDCOM 5.5.1 text string.

    The resulting text can be written to a .ged file and re-imported
    by any GEDCOM-compatible genealogy application, including this app's
    own gedcom_import.parse_gedcom().

    Returns:
        A string containing the complete GEDCOM document, with lines
        separated by CRLF as required by the GEDCOM standard.
    """
    all_lines: list[str] = []

    # ── HEAD ──────────────────────────────────────────────────────
    all_lines += [
        "0 HEAD",
        "1 SOUR FamilyTreeApp",
        "1 GEDC",
        "2 VERS 5.5.1",
        "2 FORM LINEAGE-LINKED",
        "1 CHAR UTF-8",
    ]

    # ── INDI records ──────────────────────────────────────────────
    for person in tree.people.values():
        person_events = [e for e in tree.events if e.person_id == person.id]
        all_lines += _indi_lines(person, person_events)

    # ── FAM records ───────────────────────────────────────────────
    # Build a lookup: set of (parent_id, child_id) for quick retrieval
    # We need to find the shared children of each union.
    parent_children: dict[str, list[str]] = {}
    for rel in tree.relationships:
        parent_children.setdefault(rel.parent_id, []).append(rel.child_id)

    for fam_idx, union in enumerate(tree.unions, start=1):
        fam_id = f"F{fam_idx}"

        # Children shared by this couple: appear in both parents' child lists
        p1_kids = set(parent_children.get(union.partner1_id, []))
        p2_kids = set(parent_children.get(union.partner2_id, []))
        shared_children = sorted(p1_kids & p2_kids)

        all_lines += _fam_lines(fam_id, union, shared_children)

    # ── TRLR ──────────────────────────────────────────────────────
    all_lines.append("0 TRLR")

    return "\r\n".join(all_lines) + "\r\n"
