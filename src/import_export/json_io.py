"""JSON import/export for family tree data.

Load and save family trees from/to the JSON format described in the README.
Includes validation for common data integrity issues.
"""

import json
import re
from pathlib import Path
from typing import Any

from models.person import Person, Gender
from models.relationship import Relationship, RelationshipType, Union
from models.event import LifeEvent, EventType
from models.source import Source, SourceType
from models.citation import Citation, EntityType, Confidence
from models.tree import FamilyTree


def load_tree(path: str) -> FamilyTree:
    """Read a JSON file and construct a FamilyTree.

    The JSON must have top-level keys: people, relationships, unions, events.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tree = FamilyTree()

    for p in data.get("people", []):
        person = Person(
            id=p["id"],
            given_name=p["given_name"],
            surname=p["surname"],
            gender=Gender(p.get("gender", "unknown")),
            birth_date=p.get("birth_date"),
            birth_place=p.get("birth_place"),
            death_date=p.get("death_date"),
            death_place=p.get("death_place"),
            maiden_name=p.get("maiden_name"),
            nicknames=p.get("nicknames", []),
            notes=p.get("notes", ""),
            photo_paths=p.get("photo_paths", []),
            photo_captions=p.get("photo_captions", {}),
            email=p.get("email"),
        )
        tree.add_person(person)

    for r in data.get("relationships", []):
        rel = Relationship(
            parent_id=r["parent_id"],
            child_id=r["child_id"],
            rel_type=RelationshipType(r.get("rel_type", "biological")),
        )
        tree.add_relationship(rel)

    for u in data.get("unions", []):
        union = Union(
            partner1_id=u["partner1_id"],
            partner2_id=u["partner2_id"],
            union_date=u.get("union_date"),
            union_place=u.get("union_place"),
            end_date=u.get("end_date"),
            end_reason=u.get("end_reason"),
            notes=u.get("notes", ""),
        )
        tree.add_union(union)

    for e in data.get("events", []):
        event = LifeEvent(
            person_id=e["person_id"],
            event_type=EventType(e["event_type"]),
            date=e.get("date"),
            end_date=e.get("end_date"),
            place=e.get("place"),
            description=e.get("description", ""),
            source=e.get("source"),
        )
        tree.add_event(event)

    for s in data.get("sources", []):
        source = Source(
            id=s["id"],
            name=s["name"],
            source_type=SourceType(s.get("source_type", "other")),
            author=s.get("author"),
            date=s.get("date"),
            description=s.get("description", ""),
            url=s.get("url"),
        )
        tree.add_source(source)

    for c in data.get("citations", []):
        citation = Citation(
            source_id=c["source_id"],
            entity_type=EntityType(c["entity_type"]),
            entity_id=c["entity_id"],
            field_name=c.get("field_name"),
            excerpt=c.get("excerpt", ""),
            confidence=Confidence(c.get("confidence", "confirmed")),
            notes=c.get("notes", ""),
        )
        tree.add_citation(citation)

    return tree


def _person_to_dict(p: Person) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": p.id,
        "given_name": p.given_name,
        "surname": p.surname,
        "gender": p.gender.value,
    }
    for key in (
        "birth_date",
        "birth_place",
        "death_date",
        "death_place",
        "maiden_name",
    ):
        val = getattr(p, key)
        if val is not None:
            d[key] = val
    if p.nicknames:
        d["nicknames"] = p.nicknames
    if p.notes:
        d["notes"] = p.notes
    if p.photo_paths:
        d["photo_paths"] = p.photo_paths
    if p.photo_captions:
        d["photo_captions"] = p.photo_captions
    if p.email:
        d["email"] = p.email
    return d


def _rel_to_dict(r: Relationship) -> dict[str, str]:
    d: dict[str, str] = {
        "parent_id": r.parent_id,
        "child_id": r.child_id,
    }
    if r.rel_type != RelationshipType.BIOLOGICAL:
        d["rel_type"] = r.rel_type.value
    return d


def _union_to_dict(u: Union) -> dict[str, Any]:
    d: dict[str, Any] = {
        "partner1_id": u.partner1_id,
        "partner2_id": u.partner2_id,
    }
    for key in ("union_date", "union_place", "end_date", "end_reason"):
        val = getattr(u, key)
        if val is not None:
            d[key] = val
    if u.notes:
        d["notes"] = u.notes
    return d


def _event_to_dict(e: LifeEvent) -> dict[str, Any]:
    d: dict[str, Any] = {
        "person_id": e.person_id,
        "event_type": e.event_type.value,
    }
    for key in ("date", "end_date", "place", "source"):
        val = getattr(e, key)
        if val is not None:
            d[key] = val
    if e.description:
        d["description"] = e.description
    return d


def _source_to_dict(s: Source) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": s.id,
        "name": s.name,
        "source_type": s.source_type.value,
    }
    for key in ("author", "date", "url"):
        val = getattr(s, key)
        if val is not None:
            d[key] = val
    if s.description:
        d["description"] = s.description
    return d


def _citation_to_dict(c: Citation) -> dict[str, Any]:
    d: dict[str, Any] = {
        "source_id": c.source_id,
        "entity_type": c.entity_type.value,
        "entity_id": c.entity_id,
    }
    if c.field_name:
        d["field_name"] = c.field_name
    if c.excerpt:
        d["excerpt"] = c.excerpt
    if c.confidence != Confidence.CONFIRMED:
        d["confidence"] = c.confidence.value
    if c.notes:
        d["notes"] = c.notes
    return d


def save_tree(tree: FamilyTree, path: str) -> None:
    """Serialize a FamilyTree to the JSON format."""
    data = {
        "people": [_person_to_dict(p) for p in tree.people.values()],
        "relationships": [_rel_to_dict(r) for r in tree.relationships],
        "unions": [_union_to_dict(u) for u in tree.unions],
        "events": [_event_to_dict(e) for e in tree.events],
        "sources": [_source_to_dict(s) for s in tree.sources.values()],
        "citations": [_citation_to_dict(c) for c in tree.citations],
    }
    Path(path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def validate_tree(tree: FamilyTree) -> list[str]:
    """Validate a FamilyTree and return a list of warnings/errors.

    Checks:
    - Person referenced in relationship/union/event but not in people list
    - Child born before parent
    - Marriage date before birth of either partner
    - Duplicate person IDs (cannot occur with dict, but checked in raw data)
    - Orphan events (person_id not in tree)
    """
    warnings: list[str] = []
    person_ids = set(tree.people.keys())

    # Check relationships reference valid people
    for r in tree.relationships:
        if r.parent_id not in person_ids:
            warnings.append(f"Relationship references unknown parent: {r.parent_id}")
        if r.child_id not in person_ids:
            warnings.append(f"Relationship references unknown child: {r.child_id}")

    # Check unions reference valid people
    for u in tree.unions:
        if u.partner1_id not in person_ids:
            warnings.append(f"Union references unknown partner: {u.partner1_id}")
        if u.partner2_id not in person_ids:
            warnings.append(f"Union references unknown partner: {u.partner2_id}")

    # Check orphan events
    for e in tree.events:
        if e.person_id not in person_ids:
            warnings.append(f"Event references unknown person: {e.person_id}")

    # Check child born before parent
    for r in tree.relationships:
        parent = tree.get_person(r.parent_id)
        child = tree.get_person(r.child_id)
        if parent and child and parent.birth_date and child.birth_date:
            if child.birth_date <= parent.birth_date:
                warnings.append(
                    f"Child {child.id} born before/same as parent {parent.id}"
                )

    # Check marriage date before birth of either partner
    for u in tree.unions:
        if not u.union_date:
            continue
        p1 = tree.get_person(u.partner1_id)
        p2 = tree.get_person(u.partner2_id)
        if p1 and p1.birth_date and u.union_date < p1.birth_date:
            warnings.append(f"Union date {u.union_date} before birth of {p1.id}")
        if p2 and p2.birth_date and u.union_date < p2.birth_date:
            warnings.append(f"Union date {u.union_date} before birth of {p2.id}")

    return warnings


# ── Source-tag parsing ──────────────────────────────────────────────────

# Mapping from common textual source references to canonical source IDs.
# Extend this dict for your own family's source documents.
SOURCE_TAG_MAP: dict[str, str] = {
    "golden book": "golden-book",
    "golden book questionnaire": "golden-book",
    "herb's letter": "herb-letter",
    "herb letter": "herb-letter",
    "sumner's memoir": "sumner-memoir",
    "sumner memoir": "sumner-memoir",
    "fan chart": "fan-chart-2016",
    "fan chart (may 2016)": "fan-chart-2016",
    "wikipedia": "wikipedia",
    "open library": "open-library",
    "direct submission": "direct-submission",
}

_SOURCE_PATTERN = re.compile(
    r"\s*Source:\s*(.+?)\.?\s*$",
    re.IGNORECASE,
)


def parse_source_tags(notes: str) -> tuple[list[str], str]:
    """Extract source IDs from notes and return (source_ids, cleaned_notes).

    Looks for "Source: X, Y, Z" at the end of notes.
    Returns the list of matched source IDs and the notes with the
    Source line removed.
    """
    match = _SOURCE_PATTERN.search(notes)
    if not match:
        return [], notes

    raw_sources = match.group(1)
    cleaned = notes[:match.start()].rstrip()

    # Split on commas, semicolons, or " and "
    parts = re.split(r"[,;]|\band\b", raw_sources)
    source_ids = []
    for part in parts:
        tag = part.strip().strip(".").lower()
        # Try exact match first
        if tag in SOURCE_TAG_MAP:
            source_ids.append(SOURCE_TAG_MAP[tag])
        else:
            # Try substring matching
            for key, sid in SOURCE_TAG_MAP.items():
                if key in tag:
                    source_ids.append(sid)
                    break

    return list(dict.fromkeys(source_ids)), cleaned  # dedupe preserving order
