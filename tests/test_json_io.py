"""Tests for JSON import/export of family tree data."""

import os

from import_export.json_io import load_tree, save_tree, validate_tree
from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, Union
from models.tree import FamilyTree

EXAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "example_family.json"
)


def _make_sample_tree() -> FamilyTree:
    """Build a small tree for round-trip testing."""
    tree = FamilyTree()
    tree.add_person(
        Person(
            id="P1",
            given_name="Alice",
            surname="Doe",
            gender=Gender.FEMALE,
            birth_date="1950-01-01",
            birth_place="Springfield",
        )
    )
    tree.add_person(
        Person(
            id="P2",
            given_name="Bob",
            surname="Doe",
            gender=Gender.MALE,
            birth_date="1948-06-15",
        )
    )
    tree.add_person(
        Person(
            id="P3",
            given_name="Charlie",
            surname="Doe",
            gender=Gender.MALE,
            birth_date="1975-03-20",
        )
    )
    tree.add_relationship(Relationship(parent_id="P1", child_id="P3"))
    tree.add_relationship(Relationship(parent_id="P2", child_id="P3"))
    tree.add_union(
        Union(
            partner1_id="P1",
            partner2_id="P2",
            union_date="1970-05-10",
            union_place="City Hall",
        )
    )
    tree.add_event(
        LifeEvent(
            person_id="P1",
            event_type=EventType.BIRTH,
            date="1950-01-01",
            place="Springfield",
        )
    )
    tree.add_event(
        LifeEvent(
            person_id="P3",
            event_type=EventType.EDUCATION,
            date="1993-09-01",
            end_date="1997-06-01",
            place="State University",
            description="BS in Physics",
        )
    )
    return tree


def test_roundtrip(tmp_path):
    """Save a tree then load it back — all data should survive."""
    original = _make_sample_tree()
    out_file = str(tmp_path / "roundtrip.json")

    save_tree(original, out_file)
    loaded = load_tree(out_file)

    # People
    assert set(loaded.people.keys()) == set(original.people.keys())
    for pid in original.people:
        orig = original.people[pid]
        load = loaded.people[pid]
        assert orig.given_name == load.given_name
        assert orig.surname == load.surname
        assert orig.gender == load.gender
        assert orig.birth_date == load.birth_date
        assert orig.birth_place == load.birth_place

    # Relationships
    assert len(loaded.relationships) == len(original.relationships)
    for orig_r, load_r in zip(original.relationships, loaded.relationships, strict=False):
        assert orig_r.parent_id == load_r.parent_id
        assert orig_r.child_id == load_r.child_id
        assert orig_r.rel_type == load_r.rel_type

    # Unions
    assert len(loaded.unions) == len(original.unions)
    for orig_u, load_u in zip(original.unions, loaded.unions, strict=False):
        assert orig_u.partner1_id == load_u.partner1_id
        assert orig_u.partner2_id == load_u.partner2_id
        assert orig_u.union_date == load_u.union_date
        assert orig_u.union_place == load_u.union_place

    # Events
    assert len(loaded.events) == len(original.events)
    for orig_e, load_e in zip(original.events, loaded.events, strict=False):
        assert orig_e.person_id == load_e.person_id
        assert orig_e.event_type == load_e.event_type
        assert orig_e.date == load_e.date
        assert orig_e.end_date == load_e.end_date
        assert orig_e.place == load_e.place
        assert orig_e.description == load_e.description


def test_validation_catches_missing_person():
    """Validate should flag relationships/events referencing unknown people."""
    tree = FamilyTree()
    tree.add_person(Person(id="P1", given_name="A", surname="B"))
    tree.add_relationship(Relationship(parent_id="P1", child_id="MISSING"))
    tree.add_event(
        LifeEvent(person_id="GHOST", event_type=EventType.BIRTH, date="2000-01-01")
    )

    warnings = validate_tree(tree)
    assert any("MISSING" in w for w in warnings)
    assert any("GHOST" in w for w in warnings)


def test_validation_catches_impossible_dates():
    """Validate should flag child born before parent and marriage before birth."""
    tree = FamilyTree()
    tree.add_person(
        Person(id="P1", given_name="Parent", surname="X", birth_date="2000-01-01")
    )
    tree.add_person(
        Person(id="P2", given_name="Child", surname="X", birth_date="1990-01-01")
    )
    tree.add_person(
        Person(id="P3", given_name="Spouse", surname="X", birth_date="2001-06-01")
    )
    tree.add_relationship(Relationship(parent_id="P1", child_id="P2"))
    tree.add_union(Union(partner1_id="P1", partner2_id="P3", union_date="1999-01-01"))

    warnings = validate_tree(tree)
    # Child born before parent
    assert any("Child" in w or "P2" in w for w in warnings)
    # Marriage before birth of both partners
    assert any("P1" in w and "1999" in w for w in warnings)
    assert any("P3" in w and "1999" in w for w in warnings)


def test_load_example_family():
    """Load the shipped example_family.json and verify basic structure."""
    tree = load_tree(EXAMPLE_PATH)

    assert tree.num_people == 7
    assert len(tree.relationships) == 8
    assert len(tree.unions) == 2
    assert len(tree.events) == 5

    # Verify specific people
    al = tree.get_person("P001")
    assert al is not None
    assert al.given_name == "Al"
    assert al.surname == "Smith"

    fay = tree.get_person("P006")
    assert fay is not None
    assert fay.birth_date == "1990-09-14"

    # Al and Beth are parents of Carl
    carl_parents = tree.parents_of("P003")
    parent_ids = {p.id for p in carl_parents}
    assert parent_ids == {"P001", "P002"}

    # Carl and Eve are siblings
    carl_siblings = tree.siblings_of("P003")
    sibling_ids = {s.id for s in carl_siblings}
    assert "P005" in sibling_ids

    # Fay and Gus are Carl's children
    carl_children = tree.children_of("P003")
    child_ids = {c.id for c in carl_children}
    assert child_ids == {"P006", "P007"}

    # Validation should pass clean
    warnings = validate_tree(tree)
    assert warnings == []
