"""Timeline generator — chronological narrative per person or family.

Merges life events with family milestones (births of children, deaths of
parents, marriages) into a single chronological timeline.
"""

from dataclasses import dataclass
from typing import Optional

from models.event import EventType
from models.tree import FamilyTree


@dataclass
class TimelineEntry:
    """A single entry in a chronological timeline."""

    date: Optional[str]
    description: str
    event_type: str
    related_person_id: Optional[str] = None


def person_timeline(tree: FamilyTree, person_id: str) -> list[TimelineEntry]:
    """Generate a chronological timeline for a single person.

    Includes: their birth, their life events, marriages, births of their
    children, deaths of their parents/partners, and their death.
    """
    person = tree.get_person(person_id)
    if person is None:
        return []

    entries: list[TimelineEntry] = []

    # Their birth
    if person.birth_date:
        place_suffix = f" in {person.birth_place}" if person.birth_place else ""
        entries.append(
            TimelineEntry(
                date=person.birth_date,
                description=f"{person.full_name} born{place_suffix}",
                event_type="birth",
                related_person_id=person_id,
            )
        )

    # Their life events (excluding birth/death which we handle separately)
    for event in tree.events_for(person_id):
        if event.event_type in (EventType.BIRTH, EventType.DEATH):
            continue
        place_suffix = f" at {event.place}" if event.place else ""
        desc = event.description or event.event_type.value
        entries.append(
            TimelineEntry(
                date=event.date,
                description=f"{person.full_name} — {desc}{place_suffix} ({event.event_type.value})",
                event_type=event.event_type.value,
                related_person_id=person_id,
            )
        )

    # Marriages
    for union in tree.unions:
        if union.involves(person_id):
            partner_id = union.other_partner(person_id)
            partner = tree.get_person(partner_id)
            if partner and union.union_date:
                entries.append(
                    TimelineEntry(
                        date=union.union_date,
                        description=f"{person.full_name} married {partner.full_name}",
                        event_type="marriage",
                        related_person_id=partner_id,
                    )
                )

    # Births of their children
    for child in tree.children_of(person_id):
        if child.birth_date:
            # Find the other parent for context
            other_parent = _other_parent(tree, person_id, child.id)
            if other_parent:
                parent_desc = (
                    f" (child of {person.full_name} & {other_parent.full_name})"
                )
            else:
                parent_desc = f" (child of {person.full_name})"
            entries.append(
                TimelineEntry(
                    date=child.birth_date,
                    description=f"{child.full_name} born{parent_desc}",
                    event_type="child_birth",
                    related_person_id=child.id,
                )
            )

    # Deaths of their parents
    for parent in tree.parents_of(person_id):
        if parent.death_date:
            entries.append(
                TimelineEntry(
                    date=parent.death_date,
                    description=f"{parent.full_name} died (parent of {person.full_name})",
                    event_type="parent_death",
                    related_person_id=parent.id,
                )
            )

    # Deaths of their partners
    for union in tree.unions:
        if union.involves(person_id):
            partner_id = union.other_partner(person_id)
            partner = tree.get_person(partner_id)
            if partner and partner.death_date:
                entries.append(
                    TimelineEntry(
                        date=partner.death_date,
                        description=f"{partner.full_name} died (partner of {person.full_name})",
                        event_type="partner_death",
                        related_person_id=partner_id,
                    )
                )

    # Their death
    if person.death_date:
        place_suffix = f" in {person.death_place}" if person.death_place else ""
        entries.append(
            TimelineEntry(
                date=person.death_date,
                description=f"{person.full_name} died{place_suffix}",
                event_type="death",
                related_person_id=person_id,
            )
        )

    entries.sort(key=lambda e: e.date or "")
    return entries


def family_timeline(tree: FamilyTree) -> list[TimelineEntry]:
    """Generate a chronological timeline for the entire family.

    All events for all people, merged and sorted by date.
    Deduplicates entries that would appear from multiple perspectives.
    """
    seen: set[tuple] = set()
    entries: list[TimelineEntry] = []

    for person_id, person in tree.people.items():
        # Birth
        if person.birth_date:
            place_suffix = f" in {person.birth_place}" if person.birth_place else ""
            key = ("birth", person_id)
            if key not in seen:
                seen.add(key)
                entries.append(
                    TimelineEntry(
                        date=person.birth_date,
                        description=f"{person.full_name} born{place_suffix}",
                        event_type="birth",
                        related_person_id=person_id,
                    )
                )

        # Death
        if person.death_date:
            place_suffix = f" in {person.death_place}" if person.death_place else ""
            key = ("death", person_id)
            if key not in seen:
                seen.add(key)
                entries.append(
                    TimelineEntry(
                        date=person.death_date,
                        description=f"{person.full_name} died{place_suffix}",
                        event_type="death",
                        related_person_id=person_id,
                    )
                )

    # Life events
    for event in tree.events:
        if event.event_type in (EventType.BIRTH, EventType.DEATH):
            continue
        person = tree.get_person(event.person_id)
        if not person:
            continue
        place_suffix = f" at {event.place}" if event.place else ""
        desc = event.description or event.event_type.value
        entries.append(
            TimelineEntry(
                date=event.date,
                description=f"{person.full_name} — {desc}{place_suffix} ({event.event_type.value})",
                event_type=event.event_type.value,
                related_person_id=event.person_id,
            )
        )

    # Marriages (deduplicated)
    for union in tree.unions:
        if union.union_date:
            p1 = tree.get_person(union.partner1_id)
            p2 = tree.get_person(union.partner2_id)
            if p1 and p2:
                key = ("marriage", union.partner1_id, union.partner2_id)
                if key not in seen:
                    seen.add(key)
                    entries.append(
                        TimelineEntry(
                            date=union.union_date,
                            description=f"{p1.full_name} married {p2.full_name}",
                            event_type="marriage",
                            related_person_id=union.partner1_id,
                        )
                    )

    entries.sort(key=lambda e: e.date or "")
    return entries


def format_timeline(entries: list[TimelineEntry]) -> str:
    """Pretty-print timeline entries as a readable narrative.

    Format:
        1930  Al Smith born in Chicago, IL
        1950  Al Smith — Korean War (military)
    """
    lines: list[str] = []
    for entry in entries:
        year = entry.date[:4] if entry.date else "????"
        lines.append(f"{year}  {entry.description}")
    return "\n".join(lines)


def _other_parent(tree: FamilyTree, parent_id: str, child_id: str):
    """Find the other parent of a child, given one parent."""
    parents = tree.parents_of(child_id)
    for p in parents:
        if p.id != parent_id:
            return p
    return None
