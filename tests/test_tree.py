"""Tests for the family tree data model.

Uses a synthetic 3-generation family for testing:

    Grandpa Al ─── Grandma Beth
         │               │
    ┌────┴────┐
    Dad Carl     Aunt Dana
      │
      │ ── Mom Eve
      │
  ┌───┴───┐
  Kid Fay  Kid Gus
"""
from models.person import Person, Gender
from models.relationship import Relationship, RelationshipType, Union
from models.event import LifeEvent, EventType
from models.tree import FamilyTree


def _build_test_tree() -> FamilyTree:
    """Build a synthetic 3-generation family tree."""
    tree = FamilyTree()

    # Generation 0: grandparents
    al = Person(id="al", given_name="Al", surname="Smith", gender=Gender.MALE,
                birth_date="1930-05-10", death_date="2005-12-01", birth_place="Chicago, IL")
    beth = Person(id="beth", given_name="Beth", surname="Jones", gender=Gender.FEMALE,
                  birth_date="1932-08-22", death_date="2010-03-15", maiden_name="Jones")

    # Generation 1: parents + aunt
    carl = Person(id="carl", given_name="Carl", surname="Smith", gender=Gender.MALE,
                  birth_date="1958-01-03", birth_place="Chicago, IL")
    dana = Person(id="dana", given_name="Dana", surname="Smith", gender=Gender.FEMALE,
                  birth_date="1960-11-30")
    eve = Person(id="eve", given_name="Eve", surname="Smith", gender=Gender.FEMALE,
                 birth_date="1960-07-14", maiden_name="Taylor")

    # Generation 2: kids
    fay = Person(id="fay", given_name="Fay", surname="Smith", gender=Gender.FEMALE,
                 birth_date="1988-04-20")
    gus = Person(id="gus", given_name="Gus", surname="Smith", gender=Gender.MALE,
                 birth_date="1991-09-05")

    for p in [al, beth, carl, dana, eve, fay, gus]:
        tree.add_person(p)

    # Parent-child relationships
    tree.add_relationship(Relationship(parent_id="al", child_id="carl"))
    tree.add_relationship(Relationship(parent_id="beth", child_id="carl"))
    tree.add_relationship(Relationship(parent_id="al", child_id="dana"))
    tree.add_relationship(Relationship(parent_id="beth", child_id="dana"))
    tree.add_relationship(Relationship(parent_id="carl", child_id="fay"))
    tree.add_relationship(Relationship(parent_id="eve", child_id="fay"))
    tree.add_relationship(Relationship(parent_id="carl", child_id="gus"))
    tree.add_relationship(Relationship(parent_id="eve", child_id="gus"))

    # Marriages
    tree.add_union(Union(partner1_id="al", partner2_id="beth", union_date="1955-06-15"))
    tree.add_union(Union(partner1_id="carl", partner2_id="eve", union_date="1985-09-28"))

    # Events
    tree.add_event(LifeEvent(person_id="al", event_type=EventType.MILITARY,
                             date="1950-06-01", end_date="1953-07-27", description="Korean War"))
    tree.add_event(LifeEvent(person_id="al", event_type=EventType.CAREER,
                             date="1955-01-01", description="Joined the factory"))
    tree.add_event(LifeEvent(person_id="eve", event_type=EventType.EDUCATION,
                             date="1978-09-01", end_date="1982-06-01", place="State University"))

    return tree


# --- Tests ---

def test_num_people():
    tree = _build_test_tree()
    assert tree.num_people == 7


def test_parents():
    tree = _build_test_tree()
    parents = tree.parents_of("carl")
    names = {p.given_name for p in parents}
    assert names == {"Al", "Beth"}


def test_children():
    tree = _build_test_tree()
    kids = tree.children_of("carl")
    names = {p.given_name for p in kids}
    assert names == {"Fay", "Gus"}


def test_siblings():
    tree = _build_test_tree()
    sibs = tree.siblings_of("carl")
    assert len(sibs) == 1
    assert sibs[0].given_name == "Dana"


def test_fay_and_gus_are_siblings():
    tree = _build_test_tree()
    sibs = tree.siblings_of("fay")
    assert len(sibs) == 1
    assert sibs[0].id == "gus"


def test_partners():
    tree = _build_test_tree()
    partners = tree.partners_of("carl")
    assert len(partners) == 1
    assert partners[0].given_name == "Eve"


def test_ancestors():
    tree = _build_test_tree()
    ancestors = tree.ancestors_of("fay")
    names = {p.given_name for p in ancestors}
    # Parents + grandparents
    assert names == {"Carl", "Eve", "Al", "Beth"}


def test_descendants():
    tree = _build_test_tree()
    desc = tree.descendants_of("al")
    names = {p.given_name for p in desc}
    assert names == {"Carl", "Dana", "Fay", "Gus"}


def test_generations():
    tree = _build_test_tree()
    assert tree.generation_of("al") == 0
    assert tree.generation_of("carl") == 1
    assert tree.generation_of("fay") == 2


def test_num_generations():
    tree = _build_test_tree()
    assert tree.num_generations == 3


def test_living_count():
    tree = _build_test_tree()
    # Al and Beth are deceased, everyone else living
    assert tree.num_living == 5


def test_events_for_person():
    tree = _build_test_tree()
    events = tree.events_for("al")
    assert len(events) == 2
    types = [e.event_type for e in events]
    assert EventType.MILITARY in types
    assert EventType.CAREER in types


def test_events_sorted_by_date():
    tree = _build_test_tree()
    events = tree.events_for("al")
    dates = [e.date for e in events]
    assert dates == sorted(dates)


def test_person_properties():
    tree = _build_test_tree()
    al = tree.get_person("al")
    assert al.full_name == "Al Smith"
    assert al.birth_year == 1930
    assert al.death_year == 2005
    assert not al.is_living

    fay = tree.get_person("fay")
    assert fay.is_living
    assert fay.birth_year == 1988


def test_union_properties():
    tree = _build_test_tree()
    union = tree.unions[0]  # Al-Beth
    assert union.is_active  # no divorce
    assert union.involves("al")
    assert union.other_partner("al") == "beth"


def test_maiden_name():
    tree = _build_test_tree()
    beth = tree.get_person("beth")
    assert beth.maiden_name == "Jones"
    assert beth.surname == "Jones"  # kept birth name in our model

    eve = tree.get_person("eve")
    assert eve.maiden_name == "Taylor"
    assert eve.surname == "Smith"  # took married name
