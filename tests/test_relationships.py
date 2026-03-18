"""Tests for the relationship calculator.

Uses the same synthetic 3-generation tree from test_tree.py:

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

from models.person import Gender, Person
from models.relationship import Relationship, Union
from models.tree import FamilyTree
from traversal.relationship_calculator import (
    describe_relationship,
    find_common_ancestors,
)


def _build_test_tree() -> FamilyTree:
    """Build the same synthetic 3-generation family tree used in test_tree.py."""
    tree = FamilyTree()

    al = Person(
        id="al",
        given_name="Al",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1930-05-10",
        death_date="2005-12-01",
    )
    beth = Person(
        id="beth",
        given_name="Beth",
        surname="Jones",
        gender=Gender.FEMALE,
        birth_date="1932-08-22",
        death_date="2010-03-15",
    )
    carl = Person(
        id="carl",
        given_name="Carl",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1958-01-03",
    )
    dana = Person(
        id="dana",
        given_name="Dana",
        surname="Smith",
        gender=Gender.FEMALE,
        birth_date="1960-11-30",
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

    for p in [al, beth, carl, dana, eve, fay, gus]:
        tree.add_person(p)

    tree.add_relationship(Relationship(parent_id="al", child_id="carl"))
    tree.add_relationship(Relationship(parent_id="beth", child_id="carl"))
    tree.add_relationship(Relationship(parent_id="al", child_id="dana"))
    tree.add_relationship(Relationship(parent_id="beth", child_id="dana"))
    tree.add_relationship(Relationship(parent_id="carl", child_id="fay"))
    tree.add_relationship(Relationship(parent_id="eve", child_id="fay"))
    tree.add_relationship(Relationship(parent_id="carl", child_id="gus"))
    tree.add_relationship(Relationship(parent_id="eve", child_id="gus"))

    tree.add_union(Union(partner1_id="al", partner2_id="beth", union_date="1955-06-15"))
    tree.add_union(
        Union(partner1_id="carl", partner2_id="eve", union_date="1985-09-28")
    )

    return tree


# --- Tests ---


def test_self_relationship():
    tree = _build_test_tree()
    assert describe_relationship(tree, "al", "al") == "self"
    assert describe_relationship(tree, "fay", "fay") == "self"


def test_parent_child_relationship():
    tree = _build_test_tree()
    # Carl is Fay's father
    assert describe_relationship(tree, "fay", "carl") == "father"
    # Fay is Carl's daughter
    assert describe_relationship(tree, "carl", "fay") == "daughter"
    # Eve is Fay's mother
    assert describe_relationship(tree, "fay", "eve") == "mother"
    # Gus is Carl's son
    assert describe_relationship(tree, "carl", "gus") == "son"


def test_grandparent_relationship():
    tree = _build_test_tree()
    # Al is Fay's grandfather
    assert describe_relationship(tree, "fay", "al") == "grandfather"
    # Beth is Fay's grandmother
    assert describe_relationship(tree, "fay", "beth") == "grandmother"
    # Fay is Al's granddaughter
    assert describe_relationship(tree, "al", "fay") == "granddaughter"
    # Gus is Al's grandson
    assert describe_relationship(tree, "al", "gus") == "grandson"


def test_sibling_relationship():
    tree = _build_test_tree()
    # Carl and Dana are siblings
    assert describe_relationship(tree, "carl", "dana") == "sister"
    assert describe_relationship(tree, "dana", "carl") == "brother"
    # Fay and Gus are siblings
    assert describe_relationship(tree, "fay", "gus") == "brother"
    assert describe_relationship(tree, "gus", "fay") == "sister"


def test_uncle_aunt_relationship():
    tree = _build_test_tree()
    # Dana is Fay's aunt (Dana is sibling of Carl, Fay's parent)
    assert describe_relationship(tree, "fay", "dana") == "aunt"
    # Fay is Dana's niece
    assert describe_relationship(tree, "dana", "fay") == "niece"
    # Gus is Dana's nephew
    assert describe_relationship(tree, "dana", "gus") == "nephew"


def test_find_common_ancestors():
    tree = _build_test_tree()
    # Fay and Dana share Al and Beth as common ancestors
    common = find_common_ancestors(tree, "fay", "dana")
    ancestor_ids = {c[0] for c in common}
    assert "al" in ancestor_ids
    assert "beth" in ancestor_ids


def test_first_cousin():
    """If Dana had a child, that child and Fay would be first cousins."""
    tree = _build_test_tree()
    # Add a child for Dana to test cousin relationship
    child = Person(
        id="hank",
        given_name="Hank",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1990-03-15",
    )
    tree.add_person(child)
    tree.add_relationship(Relationship(parent_id="dana", child_id="hank"))

    # Fay and Hank are first cousins (both grandchildren of Al/Beth, through different children)
    assert describe_relationship(tree, "fay", "hank") == "first cousin"
    assert describe_relationship(tree, "hank", "fay") == "first cousin"


def test_first_cousin_once_removed():
    """Dana's grandchild and Fay would be first cousins once removed."""
    tree = _build_test_tree()
    # Add child and grandchild for Dana
    hank = Person(
        id="hank",
        given_name="Hank",
        surname="Smith",
        gender=Gender.MALE,
        birth_date="1990-03-15",
    )
    iris = Person(
        id="iris",
        given_name="Iris",
        surname="Smith",
        gender=Gender.FEMALE,
        birth_date="2015-07-01",
    )
    tree.add_person(hank)
    tree.add_person(iris)
    tree.add_relationship(Relationship(parent_id="dana", child_id="hank"))
    tree.add_relationship(Relationship(parent_id="hank", child_id="iris"))

    # Fay (gen 2) and Iris (gen 3): first cousin once removed
    assert describe_relationship(tree, "fay", "iris") == "first cousin once removed"
    assert describe_relationship(tree, "iris", "fay") == "first cousin once removed"


def test_no_relation():
    """Eve has no blood relation to Dana (Eve married into the family)."""
    tree = _build_test_tree()
    assert describe_relationship(tree, "eve", "dana") == "no relation found"
