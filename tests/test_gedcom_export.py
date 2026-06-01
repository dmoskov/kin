"""Tests for GEDCOM export.

Verifies that export_gedcom() produces valid GEDCOM 5.5.1 output and that
a round-trip (export → re-import via parse_gedcom) faithfully preserves
people, unions, relationships, and key field values.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")

from import_export.gedcom_export import _iso_to_gedcom_date, export_gedcom
from import_export.gedcom_import import parse_gedcom
from models.person import Gender, Person
from models.relationship import Relationship, Union
from models.tree import FamilyTree

FIXTURE = str(Path(__file__).parent / "fixtures" / "tiny.ged")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_tiny_tree() -> FamilyTree:
    """Build the same 3-person tree as tiny.ged, programmatically."""
    tree = FamilyTree()

    john = Person(
        id="I1",
        given_name="John",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1930-03-15",
        birth_place="Chicago, IL",
        death_date="2005-12-22",
        death_place="Springfield, IL",
        notes="Served in the Korean War.",
    )
    jane = Person(
        id="I2",
        given_name="Jane",
        surname="Doe",
        gender=Gender.FEMALE,
        birth_date="1932-07-10",
    )
    bobby = Person(
        id="I3",
        given_name="Bobby",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1960",
    )

    tree.add_person(john)
    tree.add_person(jane)
    tree.add_person(bobby)

    tree.add_union(
        Union(
            partner1_id="I1",
            partner2_id="I2",
            union_date="1955-06-05",
            union_place="Springfield, IL",
        )
    )

    tree.add_relationship(Relationship(parent_id="I1", child_id="I3"))
    tree.add_relationship(Relationship(parent_id="I2", child_id="I3"))

    return tree


# ── Date conversion ───────────────────────────────────────────────────────────


def test_iso_to_gedcom_date_full():
    assert _iso_to_gedcom_date("1930-03-15") == "15 MAR 1930"


def test_iso_to_gedcom_date_month_year():
    assert _iso_to_gedcom_date("1932-07") == "JUL 1932"


def test_iso_to_gedcom_date_year_only():
    assert _iso_to_gedcom_date("1960") == "1960"


def test_iso_to_gedcom_date_none():
    assert _iso_to_gedcom_date(None) is None


# ── Structure of emitted GEDCOM ───────────────────────────────────────────────


def test_gedcom_has_head_and_trlr():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    lines = text.splitlines()
    assert lines[0] == "0 HEAD"
    assert lines[-1] == "0 TRLR"


def test_gedcom_indi_records():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "0 @I1@ INDI" in text
    assert "0 @I2@ INDI" in text
    assert "0 @I3@ INDI" in text


def test_gedcom_name_format():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "1 NAME John /Smith/" in text
    assert "1 NAME Jane /Doe/" in text


def test_gedcom_sex_field():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    # John is male, Jane is female
    lines = text.splitlines()
    john_idx = lines.index("0 @I1@ INDI")
    jane_idx = lines.index("0 @I2@ INDI")
    # SEX M must appear after John's INDI line and before the next 0-level record
    john_block = "\n".join(lines[john_idx:jane_idx])
    assert "1 SEX M" in john_block
    jane_end = next(
        i for i, ln in enumerate(lines[jane_idx + 1 :], start=jane_idx + 1) if ln.startswith("0 ")
    )
    jane_block = "\n".join(lines[jane_idx:jane_end])
    assert "1 SEX F" in jane_block


def test_gedcom_birth_record():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "2 DATE 15 MAR 1930" in text
    assert "2 PLAC Chicago, IL" in text


def test_gedcom_death_record():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "2 DATE 22 DEC 2005" in text
    assert "2 PLAC Springfield, IL" in text


def test_gedcom_note():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "1 NOTE Served in the Korean War." in text


def test_gedcom_fam_record():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "0 @F1@ FAM" in text
    assert "1 HUSB @I1@" in text
    assert "1 WIFE @I2@" in text
    assert "1 CHIL @I3@" in text


def test_gedcom_marriage_record():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "2 DATE 5 JUN 1955" in text
    assert "2 PLAC Springfield, IL" in text


def test_gedcom_version_header():
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "2 VERS 5.5.1" in text


# ── Round-trip via the importer ───────────────────────────────────────────────


def _roundtrip(tree: FamilyTree) -> FamilyTree:
    """Export tree to GEDCOM, write to a temp file, re-import it."""
    text = export_gedcom(tree)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ged", encoding="utf-8", delete=False) as f:
        f.write(text)
        tmp_path = f.name
    return parse_gedcom(tmp_path)


def test_roundtrip_person_count():
    original = _make_tiny_tree()
    restored = _roundtrip(original)
    assert len(restored.people) == len(original.people)


def test_roundtrip_union_count():
    original = _make_tiny_tree()
    restored = _roundtrip(original)
    assert len(restored.unions) == len(original.unions)


def test_roundtrip_relationship_count():
    original = _make_tiny_tree()
    restored = _roundtrip(original)
    assert len(restored.relationships) == len(original.relationships)


def test_roundtrip_person_fields():
    original = _make_tiny_tree()
    restored = _roundtrip(original)

    john = restored.get_person("I1")
    assert john is not None
    assert john.given_name == "John"
    assert john.surname == "Smith"
    assert john.gender == Gender.MALE
    assert john.birth_date == "1930-03-15"
    assert john.birth_place == "Chicago, IL"
    assert john.death_date == "2005-12-22"
    assert john.death_place == "Springfield, IL"
    assert john.notes == "Served in the Korean War."


def test_roundtrip_living_person():
    """A person with no death date remains living after round-trip."""
    original = _make_tiny_tree()
    restored = _roundtrip(original)
    jane = restored.get_person("I2")
    assert jane is not None
    assert jane.is_living


def test_roundtrip_year_only_date():
    """Year-only birth dates survive the round-trip intact."""
    original = _make_tiny_tree()
    restored = _roundtrip(original)
    bobby = restored.get_person("I3")
    assert bobby is not None
    assert bobby.birth_date == "1960"


def test_roundtrip_union_dates():
    original = _make_tiny_tree()
    restored = _roundtrip(original)
    assert len(restored.unions) == 1
    u = restored.unions[0]
    assert u.union_date == "1955-06-05"
    assert u.union_place == "Springfield, IL"


def test_roundtrip_parent_child():
    """Parent-child relationships are preserved through export→import."""
    original = _make_tiny_tree()
    restored = _roundtrip(original)
    parents = {p.id for p in restored.parents_of("I3")}
    assert parents == {"I1", "I2"}


def test_roundtrip_from_gedcom_import():
    """Round-trip starting from the canonical tiny.ged fixture."""
    original = parse_gedcom(FIXTURE)
    restored = _roundtrip(original)

    assert len(restored.people) == len(original.people)
    assert len(restored.unions) == len(original.unions)
    assert len(restored.relationships) == len(original.relationships)

    john = restored.get_person("I1")
    assert john is not None
    assert john.given_name == "John"
    assert john.birth_date == "1930-03-15"
    assert john.death_date == "2005-12-22"


def test_empty_tree_export():
    """An empty tree exports with HEAD and TRLR but no INDI/FAM records."""
    tree = FamilyTree()
    text = export_gedcom(tree)
    assert "0 HEAD" in text
    assert "0 TRLR" in text
    assert "INDI" not in text
    assert "FAM" not in text


def test_crlf_line_endings():
    """GEDCOM standard requires CRLF line endings."""
    tree = _make_tiny_tree()
    text = export_gedcom(tree)
    assert "\r\n" in text
