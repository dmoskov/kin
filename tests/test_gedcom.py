"""Tests for GEDCOM import.

Uses tests/fixtures/tiny.ged — a 3-person family:
    John Smith (1930–2005) ── Jane Doe (1932–)
                │
           Bobby Smith (1960–)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from import_export.gedcom_import import parse_gedcom

FIXTURE = str(Path(__file__).parent / "fixtures" / "tiny.ged")


def test_parse_individual():
    """INDI records produce Person objects with correct attributes."""
    tree = parse_gedcom(FIXTURE)

    john = tree.get_person("I1")
    assert john is not None
    assert john.given_name == "John"
    assert john.surname == "Smith"
    assert john.gender.value == "male"
    assert john.birth_place == "Chicago, IL"
    assert john.death_date == "2005-12-22"
    assert john.death_place == "Springfield, IL"
    assert john.notes == "Served in the Korean War."

    jane = tree.get_person("I2")
    assert jane is not None
    assert jane.given_name == "Jane"
    assert jane.surname == "Doe"
    assert jane.gender.value == "female"
    assert jane.is_living  # no DEAT record

    bobby = tree.get_person("I3")
    assert bobby is not None
    assert bobby.given_name == "Bobby"
    assert bobby.surname == "Smith"


def test_parse_family_links():
    """FAM records create parent-child relationships and a union."""
    tree = parse_gedcom(FIXTURE)

    # Bobby's parents
    parents = tree.parents_of("I3")
    parent_ids = {p.id for p in parents}
    assert parent_ids == {"I1", "I2"}

    # John and Jane's child
    assert len(tree.children_of("I1")) == 1
    assert tree.children_of("I1")[0].id == "I3"

    # Union exists
    assert len(tree.unions) == 1
    union = tree.unions[0]
    assert union.partner1_id == "I1"
    assert union.partner2_id == "I2"
    assert union.union_date == "1955-06-05"
    assert union.union_place == "Springfield, IL"


def test_parse_dates():
    """Various GEDCOM date formats are converted to ISO-ish strings."""
    tree = parse_gedcom(FIXTURE)

    john = tree.get_person("I1")
    assert john.birth_date == "1930-03-15"  # 15 MAR 1930 -> full date

    jane = tree.get_person("I2")
    assert jane.birth_date == "1932-07-10"  # 10 JUL 1932

    bobby = tree.get_person("I3")
    assert bobby.birth_date == "1960"  # year only


def test_roundtrip_gedcom_to_json():
    """Parse GEDCOM, serialise key data to JSON, and verify round-trip fidelity."""
    tree = parse_gedcom(FIXTURE)

    # Serialise people to JSON-compatible dicts
    people_data = {
        pid: {
            "given_name": p.given_name,
            "surname": p.surname,
            "birth_date": p.birth_date,
            "death_date": p.death_date,
        }
        for pid, p in tree.people.items()
    }

    # Round-trip through JSON
    json_str = json.dumps(people_data)
    restored = json.loads(json_str)

    assert restored["I1"]["given_name"] == "John"
    assert restored["I1"]["surname"] == "Smith"
    assert restored["I1"]["birth_date"] == "1930-03-15"
    assert restored["I1"]["death_date"] == "2005-12-22"
    assert restored["I2"]["death_date"] is None
    assert restored["I3"]["birth_date"] == "1960"
    assert len(restored) == 3
