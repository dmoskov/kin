"""Tests for the timeline generator."""

import sys

sys.path.insert(0, "src")

from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, Union
from models.tree import FamilyTree
from traversal.timeline import (
    TimelineEntry,
    family_timeline,
    format_timeline,
    person_timeline,
)


def _build_test_tree() -> FamilyTree:
    """Build a synthetic 3-generation family tree for timeline tests."""
    tree = FamilyTree()

    al = Person(
        id="al",
        given_name="Al",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1930-05-10",
        death_date="2005-12-01",
        birth_place="Chicago, IL",
    )
    beth = Person(
        id="beth",
        given_name="Beth",
        surname="Jones",
        gender=Gender.FEMALE,
        birth_date="1932-08-22",
        death_date="2010-03-15",
        maiden_name="Jones",
    )
    carl = Person(
        id="carl",
        given_name="Carl",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1958-01-03",
        birth_place="Chicago, IL",
    )
    eve = Person(
        id="eve",
        given_name="Eve",
        surname="Smith",
        gender=Gender.FEMALE,
        birth_date="1960-07-14",
        maiden_name="Taylor",
    )
    fay = Person(
        id="fay",
        given_name="Fay",
        surname="Smith",
        gender=Gender.FEMALE,
        birth_date="1988-04-20",
    )
    gus = Person(
        id="gus",
        given_name="Gus",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1991-09-05",
    )

    for p in [al, beth, carl, eve, fay, gus]:
        tree.add_person(p)

    tree.add_relationship(Relationship(parent_id="al", child_id="carl"))
    tree.add_relationship(Relationship(parent_id="beth", child_id="carl"))
    tree.add_relationship(Relationship(parent_id="carl", child_id="fay"))
    tree.add_relationship(Relationship(parent_id="eve", child_id="fay"))
    tree.add_relationship(Relationship(parent_id="carl", child_id="gus"))
    tree.add_relationship(Relationship(parent_id="eve", child_id="gus"))

    tree.add_union(Union(partner1_id="al", partner2_id="beth", union_date="1955-06-15"))
    tree.add_union(Union(partner1_id="carl", partner2_id="eve", union_date="1985-09-28"))

    tree.add_event(
        LifeEvent(
            person_id="al",
            event_type=EventType.MILITARY,
            date="1950-06-01",
            description="Korean War",
        )
    )
    tree.add_event(
        LifeEvent(
            person_id="al",
            event_type=EventType.CAREER,
            date="1955-01-01",
            description="Joined the factory",
        )
    )

    return tree


def test_person_timeline_includes_birth():
    tree = _build_test_tree()
    entries = person_timeline(tree, "al")
    birth_entries = [e for e in entries if e.event_type == "birth"]
    assert len(birth_entries) == 1
    assert "Al Smith born" in birth_entries[0].description
    assert "Chicago, IL" in birth_entries[0].description


def test_person_timeline_includes_children_births():
    tree = _build_test_tree()
    entries = person_timeline(tree, "carl")
    child_births = [e for e in entries if e.event_type == "child_birth"]
    assert len(child_births) == 2
    names = {e.related_person_id for e in child_births}
    assert names == {"fay", "gus"}


def test_person_timeline_includes_death():
    tree = _build_test_tree()
    entries = person_timeline(tree, "al")
    death_entries = [e for e in entries if e.event_type == "death"]
    assert len(death_entries) == 1
    assert "Al Smith died" in death_entries[0].description


def test_person_timeline_includes_marriage():
    tree = _build_test_tree()
    entries = person_timeline(tree, "al")
    marriage_entries = [e for e in entries if e.event_type == "marriage"]
    assert len(marriage_entries) == 1
    assert "married" in marriage_entries[0].description
    assert "Beth" in marriage_entries[0].description


def test_person_timeline_includes_life_events():
    tree = _build_test_tree()
    entries = person_timeline(tree, "al")
    military = [e for e in entries if e.event_type == "military"]
    assert len(military) == 1
    assert "Korean War" in military[0].description


def test_person_timeline_includes_parent_deaths():
    tree = _build_test_tree()
    entries = person_timeline(tree, "carl")
    parent_deaths = [e for e in entries if e.event_type == "parent_death"]
    assert len(parent_deaths) == 2
    ids = {e.related_person_id for e in parent_deaths}
    assert ids == {"al", "beth"}


def test_person_timeline_sorted_by_date():
    tree = _build_test_tree()
    entries = person_timeline(tree, "al")
    dates = [e.date for e in entries if e.date]
    assert dates == sorted(dates)


def test_family_timeline_sorted_by_date():
    tree = _build_test_tree()
    entries = family_timeline(tree)
    dates = [e.date for e in entries if e.date]
    assert dates == sorted(dates)


def test_family_timeline_includes_all_births():
    tree = _build_test_tree()
    entries = family_timeline(tree)
    births = [e for e in entries if e.event_type == "birth"]
    assert len(births) == 6  # al, beth, carl, eve, fay, gus


def test_family_timeline_includes_marriages():
    tree = _build_test_tree()
    entries = family_timeline(tree)
    marriages = [e for e in entries if e.event_type == "marriage"]
    assert len(marriages) == 2


def test_format_timeline_readable():
    entries = [
        TimelineEntry(
            date="1930-05-10",
            description="Al Smith born in Chicago, IL",
            event_type="birth",
        ),
        TimelineEntry(
            date="1950-06-01",
            description="Al Smith — Korean War (military)",
            event_type="military",
        ),
        TimelineEntry(
            date="1955-06-15",
            description="Al Smith married Beth Jones",
            event_type="marriage",
        ),
        TimelineEntry(
            date="1958-01-03",
            description="Carl Smith born (son of Al & Beth)",
            event_type="child_birth",
        ),
    ]
    output = format_timeline(entries)
    lines = output.strip().split("\n")
    assert len(lines) == 4
    assert lines[0].startswith("1930")
    assert "Al Smith born" in lines[0]
    assert lines[1].startswith("1950")
    assert "Korean War" in lines[1]
    assert lines[2].startswith("1955")
    assert "married" in lines[2]


def test_person_timeline_unknown_person():
    tree = _build_test_tree()
    entries = person_timeline(tree, "nonexistent")
    assert entries == []
