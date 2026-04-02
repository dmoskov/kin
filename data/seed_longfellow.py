#!/usr/bin/env python3
"""Seed the family tree database with Longfellow descendant data.

Source:
  - "Descendants of William LONGFELLOW" report (4 Dec 2009)
  - 10 generations, ~62 individuals

Run from project root:
    cd /Users/moskov/Code/family-tree
    python3 data/seed_longfellow.py
"""

import sys
from pathlib import Path

# Add src/ to path so we can import our modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database.connection import init_db
from database.repository import TreeRepository
from models.person import Gender, Person
from models.relationship import Relationship, RelationshipType, Union
from models.event import EventType, LifeEvent
from models.source import Source, SourceType
from models.tree import FamilyTree


SOURCE_DOC = "longfellow-descendants-2009"


def build_longfellow_tree() -> FamilyTree:
    """Build the Longfellow descendant tree from the 4 Dec 2009 report."""
    tree = FamilyTree()

    # ── Source ──────────────────────────────────────────────────────────
    tree.add_source(Source(
        id=SOURCE_DOC,
        name="Descendants of William Longfellow",
        source_type=SourceType.DOCUMENT,
        date="2009-12-04",
        description="Descendant report for William Longfellow (1650–1690), 10 generations.",
    ))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  FIRST GENERATION                                               ║
    # ╚══════════════════════════════════════════════════════════════════╝

    tree.add_person(Person(
        id="william-longfellow-1650",
        given_name="William",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1650",
        death_date="1690",
        notes="Progenitor of the Longfellow line. Born 1650/51, died 1690.",
    ))

    tree.add_person(Person(
        id="anne-sewall",
        given_name="Anne",
        surname="Sewall",
        gender=Gender.FEMALE,
        notes="Wife of William Longfellow. Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="william-longfellow-1650",
        partner2_id="anne-sewall",
        union_date="1668-11-10",
        notes="Married November 10, 1668.",
    ))

    # -- Children of William & Anne --

    tree.add_person(Person(
        id="william-longfellow-1679",
        given_name="William",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1679-11-20",
        notes="Son of William & Anne Sewall. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1650", child_id="william-longfellow-1679"))
    tree.add_relationship(Relationship(parent_id="anne-sewall", child_id="william-longfellow-1679"))

    tree.add_person(Person(
        id="stephen-longfellow-1681",
        given_name="Stephen",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1681-01-10",
        notes="Son of William & Anne Sewall. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1650", child_id="stephen-longfellow-1681"))
    tree.add_relationship(Relationship(parent_id="anne-sewall", child_id="stephen-longfellow-1681"))

    tree.add_person(Person(
        id="anna-longfellow-1683",
        given_name="Anna",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1683-10-03",
        notes="Daughter of William & Anne Sewall. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1650", child_id="anna-longfellow-1683"))
    tree.add_relationship(Relationship(parent_id="anne-sewall", child_id="anna-longfellow-1683"))

    tree.add_person(Person(
        id="stephen-longfellow-1685",
        given_name="Stephen",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1685-09-22",
        death_date="1764-11-17",
        notes="Lieut. Stephen Longfellow. Son of William & Anne Sewall. Continued the line.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1650", child_id="stephen-longfellow-1685"))
    tree.add_relationship(Relationship(parent_id="anne-sewall", child_id="stephen-longfellow-1685"))

    tree.add_person(Person(
        id="elizabeth-longfellow-1688",
        given_name="Elizabeth",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1688-07-03",
        notes="Daughter of William & Anne Sewall. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1650", child_id="elizabeth-longfellow-1688"))
    tree.add_relationship(Relationship(parent_id="anne-sewall", child_id="elizabeth-longfellow-1688"))

    tree.add_person(Person(
        id="nathan-longfellow-1690",
        given_name="Nathan",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1690-02-05",
        notes="Son of William & Anne Sewall. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1650", child_id="nathan-longfellow-1690"))
    tree.add_relationship(Relationship(parent_id="anne-sewall", child_id="nathan-longfellow-1690"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  SECOND GENERATION                                              ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # Stephen (1685) already created above

    tree.add_person(Person(
        id="abigail-thompson",
        given_name="Abigail",
        surname="Thompson",
        gender=Gender.FEMALE,
        notes="Wife of Lieut. Stephen Longfellow. Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="stephen-longfellow-1685",
        partner2_id="abigail-thompson",
        union_date="1713-03-25",
        notes="Married March 25, 1713.",
    ))

    # -- Children of Stephen & Abigail --

    tree.add_person(Person(
        id="william-longfellow-1714",
        given_name="William",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1714-09-10",
        death_date="1787-08",
        notes="Son of Lieut. Stephen & Abigail Thompson. Continued the line.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="william-longfellow-1714"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="william-longfellow-1714"))

    tree.add_person(Person(
        id="anne-longfellow-1716",
        given_name="Anne",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1716-04-24",
        death_date="1792-07-03",
        notes="Daughter of Lieut. Stephen & Abigail Thompson.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="anne-longfellow-1716"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="anne-longfellow-1716"))

    tree.add_person(Person(
        id="edward-longfellow-1718",
        given_name="Edward",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1718-04-29",
        death_date="1794-08-22",
        notes="Son of Lieut. Stephen & Abigail Thompson.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="edward-longfellow-1718"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="edward-longfellow-1718"))

    tree.add_person(Person(
        id="sarah-longfellow-1721",
        given_name="Sarah",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1721-01-08",
        death_date="1803-07-17",
        notes="Daughter of Lieut. Stephen & Abigail Thompson.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="sarah-longfellow-1721"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="sarah-longfellow-1721"))

    tree.add_person(Person(
        id="stephen-longfellow-1723",
        given_name="Stephen",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1723-02-07",
        death_date="1790-05-01",
        notes="Son of Lieut. Stephen & Abigail Thompson.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="stephen-longfellow-1723"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="stephen-longfellow-1723"))

    tree.add_person(Person(
        id="samuel-longfellow-1725",
        given_name="Samuel",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1725-03-12",
        death_date="1800-08-04",
        notes="Son of Lieut. Stephen & Abigail Thompson.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="samuel-longfellow-1725"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="samuel-longfellow-1725"))

    tree.add_person(Person(
        id="abigal-longfellow-1727",
        given_name="Abigal",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1727-05-23",
        death_date="1729-07-29",
        notes="Daughter of Lieut. Stephen & Abigail Thompson. Died young.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="abigal-longfellow-1727"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="abigal-longfellow-1727"))

    tree.add_person(Person(
        id="elizabeth-longfellow-1732",
        given_name="Elizabeth",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1732-08-18",
        death_date="1732-08-25",
        notes="Daughter of Lieut. Stephen & Abigail Thompson. Died as infant.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="elizabeth-longfellow-1732"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="elizabeth-longfellow-1732"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  THIRD GENERATION                                               ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # William (1714) already created above

    tree.add_person(Person(
        id="hepsibah-plumer",
        given_name="Hepsibah",
        surname="Plumer",
        gender=Gender.FEMALE,
        notes="Wife of William Longfellow (1714). Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="william-longfellow-1714",
        partner2_id="hepsibah-plumer",
        union_date="1740-01-24",
        notes="Married January 24, 1739/40.",
    ))

    # -- Children of William & Hepsibah --

    tree.add_person(Person(
        id="ann-b-longfellow-1742",
        given_name="Ann B.",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1742-05-01",
        death_date="1778-12-22",
        notes="Daughter of William & Hepsibah Plumer.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="ann-b-longfellow-1742"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="ann-b-longfellow-1742"))

    tree.add_person(Person(
        id="nathan-longfellow-1744",
        given_name="Nathan",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1744-09-01",
        death_date="1828-01-08",
        notes="Son of William & Hepsibah Plumer.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="nathan-longfellow-1744"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="nathan-longfellow-1744"))

    tree.add_person(Person(
        id="stephen-longfellow-1746",
        given_name="Stephen",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1746-11-18",
        notes="Son of William & Hepsibah Plumer. Continued the line. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="stephen-longfellow-1746"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="stephen-longfellow-1746"))

    tree.add_person(Person(
        id="jane-longfellow-1749",
        given_name="Jane",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1749-10-29",
        death_date="1760-02-23",
        notes="Daughter of William & Hepsibah Plumer. Baptized October 29, 1749.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="jane-longfellow-1749"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="jane-longfellow-1749"))

    tree.add_person(Person(
        id="abigail-longfellow-1752",
        given_name="Abigail",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1752-03-15",
        death_date="1778-12-13",
        notes="Daughter of William & Hepsibah Plumer.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="abigail-longfellow-1752"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="abigail-longfellow-1752"))

    tree.add_person(Person(
        id="william-longfellow-1755",
        given_name="William",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1755-04-19",
        notes="Son of William & Hepsibah Plumer. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="william-longfellow-1755"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="william-longfellow-1755"))

    tree.add_person(Person(
        id="samuel-longfellow-1758",
        given_name="Samuel",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1758-07-08",
        notes="Son of William & Hepsibah Plumer. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="samuel-longfellow-1758"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="samuel-longfellow-1758"))

    tree.add_person(Person(
        id="benjamin-longfellow-1761",
        given_name="Benjamin",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1761-04-04",
        notes="Son of William & Hepsibah Plumer. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1714", child_id="benjamin-longfellow-1761"))
    tree.add_relationship(Relationship(parent_id="hepsibah-plumer", child_id="benjamin-longfellow-1761"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  FOURTH GENERATION                                              ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # Stephen (1746) already created above

    tree.add_person(Person(
        id="mary-pritchard",
        given_name="Mary",
        surname="Pritchard",
        gender=Gender.FEMALE,
        notes="Wife of Stephen Longfellow (1746). Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="stephen-longfellow-1746",
        partner2_id="mary-pritchard",
    ))

    # -- Children of Stephen & Mary --

    tree.add_person(Person(
        id="jane-longfellow-1773",
        given_name="Jane",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1773-03-22",
        notes="Daughter of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="jane-longfellow-1773"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="jane-longfellow-1773"))

    tree.add_person(Person(
        id="mary-longfellow-1774",
        given_name="Mary",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1774-10-15",
        notes="Daughter of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="mary-longfellow-1774"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="mary-longfellow-1774"))

    tree.add_person(Person(
        id="lydia-longfellow-1777",
        given_name="Lydia",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1777-01-03",
        notes="Daughter of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="lydia-longfellow-1777"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="lydia-longfellow-1777"))

    tree.add_person(Person(
        id="stephen-longfellow-1779",
        given_name="Stephen",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1779-07-29",
        notes="Son of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="stephen-longfellow-1779"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="stephen-longfellow-1779"))

    tree.add_person(Person(
        id="john-longfellow-1781",
        given_name="John",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1781-08-02",
        death_date="1828-01-16",
        notes="Son of Stephen & Mary Pritchard. Continued the line.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="john-longfellow-1781"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="john-longfellow-1781"))

    tree.add_person(Person(
        id="samuel-longfellow-1784",
        given_name="Samuel",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1784-06-11",
        notes="Son of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="samuel-longfellow-1784"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="samuel-longfellow-1784"))

    tree.add_person(Person(
        id="david-longfellow-1786",
        given_name="David",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1786-11-23",
        notes="Son of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="david-longfellow-1786"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="david-longfellow-1786"))

    tree.add_person(Person(
        id="sewall-longfellow-1789",
        given_name="Sewall",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1789-12-28",
        notes="Son of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="sewall-longfellow-1789"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="sewall-longfellow-1789"))

    tree.add_person(Person(
        id="patty-g-longfellow-1792",
        given_name="Patty G.",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1792-10-07",
        notes="Daughter of Stephen & Mary Pritchard. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1746", child_id="patty-g-longfellow-1792"))
    tree.add_relationship(Relationship(parent_id="mary-pritchard", child_id="patty-g-longfellow-1792"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  FIFTH GENERATION                                               ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # John (1781) already created above

    tree.add_person(Person(
        id="lydia-brown-longfellow",
        given_name="Lydia",
        surname="Brown",
        gender=Gender.FEMALE,
        notes="Wife of John Longfellow (1781). Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="john-longfellow-1781",
        partner2_id="lydia-brown-longfellow",
        union_date="1803-09-04",
        notes="Married September 4, 1803.",
    ))

    # -- Children of John & Lydia --

    tree.add_person(Person(
        id="john-longfellow-1804",
        given_name="John",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1804-08-14",
        death_date="1829-11-27",
        notes="Son of John & Lydia Brown. Continued the line.",
    ))
    tree.add_relationship(Relationship(parent_id="john-longfellow-1781", child_id="john-longfellow-1804"))
    tree.add_relationship(Relationship(parent_id="lydia-brown-longfellow", child_id="john-longfellow-1804"))

    tree.add_person(Person(
        id="lydia-longfellow-1807",
        given_name="Lydia",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1807-05-25",
        notes="Daughter of John & Lydia Brown. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-longfellow-1781", child_id="lydia-longfellow-1807"))
    tree.add_relationship(Relationship(parent_id="lydia-brown-longfellow", child_id="lydia-longfellow-1807"))

    tree.add_person(Person(
        id="samuel-longfellow-1813",
        given_name="Samuel",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1813-12-28",
        notes="Son of John & Lydia Brown. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-longfellow-1781", child_id="samuel-longfellow-1813"))
    tree.add_relationship(Relationship(parent_id="lydia-brown-longfellow", child_id="samuel-longfellow-1813"))

    tree.add_person(Person(
        id="mary-j-longfellow-1818",
        given_name="Mary J.",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1818",
        notes="Daughter of John & Lydia Brown. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-longfellow-1781", child_id="mary-j-longfellow-1818"))
    tree.add_relationship(Relationship(parent_id="lydia-brown-longfellow", child_id="mary-j-longfellow-1818"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  SIXTH GENERATION                                               ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # John (1804) already created above

    tree.add_person(Person(
        id="mary-russel",
        given_name="Mary",
        surname="Russel",
        gender=Gender.FEMALE,
        notes="Wife of John Longfellow (1804). Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="john-longfellow-1804",
        partner2_id="mary-russel",
        union_date="1825-03-29",
        notes="Married March 29, 1825.",
    ))

    # -- Children of John & Mary Russel --

    tree.add_person(Person(
        id="mary-e-longfellow-1826",
        given_name="Mary E.",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1826-01-08",
        death_date="1888-08-17",
        notes="Daughter of John & Mary Russel.",
    ))
    tree.add_relationship(Relationship(parent_id="john-longfellow-1804", child_id="mary-e-longfellow-1826"))
    tree.add_relationship(Relationship(parent_id="mary-russel", child_id="mary-e-longfellow-1826"))

    tree.add_person(Person(
        id="john-r-longfellow-1828",
        given_name="John R.",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1828-01-01",
        death_date="1899-12-19",
        notes="Son of John & Mary Russel. Continued the line.",
    ))
    tree.add_relationship(Relationship(parent_id="john-longfellow-1804", child_id="john-r-longfellow-1828"))
    tree.add_relationship(Relationship(parent_id="mary-russel", child_id="john-r-longfellow-1828"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  SEVENTH GENERATION                                             ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # John R. (1828) already created above

    tree.add_person(Person(
        id="mary-brown-longfellow",
        given_name="Mary",
        surname="Brown",
        gender=Gender.FEMALE,
        notes="Wife of John R. Longfellow. Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="john-r-longfellow-1828",
        partner2_id="mary-brown-longfellow",
        union_date="1846-09-23",
        notes="Married September 23, 1846.",
    ))

    # -- Children of John R. & Mary Brown --

    tree.add_person(Person(
        id="john-longfellow-1848",
        given_name="John",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1848-01",
        death_date="1850-06",
        notes="Son of John R. & Mary Brown. Died young.",
    ))
    tree.add_relationship(Relationship(parent_id="john-r-longfellow-1828", child_id="john-longfellow-1848"))
    tree.add_relationship(Relationship(parent_id="mary-brown-longfellow", child_id="john-longfellow-1848"))

    tree.add_person(Person(
        id="john-h-longfellow-1850",
        given_name="John H.",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1850-06-03",
        death_date="1915-05-24",
        notes="Son of John R. & Mary Brown. Continued the line.",
    ))
    tree.add_relationship(Relationship(parent_id="john-r-longfellow-1828", child_id="john-h-longfellow-1850"))
    tree.add_relationship(Relationship(parent_id="mary-brown-longfellow", child_id="john-h-longfellow-1850"))

    tree.add_person(Person(
        id="mary-r-longfellow-1852",
        given_name="Mary R.",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1852-03-18",
        death_date="1915-09-24",
        notes="Daughter of John R. & Mary Brown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-r-longfellow-1828", child_id="mary-r-longfellow-1852"))
    tree.add_relationship(Relationship(parent_id="mary-brown-longfellow", child_id="mary-r-longfellow-1852"))

    tree.add_person(Person(
        id="albert-longfellow-1854",
        given_name="Albert",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1854-02",
        death_date="1855-01",
        notes="Son of John R. & Mary Brown. Twin with George. Died as infant.",
    ))
    tree.add_relationship(Relationship(parent_id="john-r-longfellow-1828", child_id="albert-longfellow-1854"))
    tree.add_relationship(Relationship(parent_id="mary-brown-longfellow", child_id="albert-longfellow-1854"))

    tree.add_person(Person(
        id="george-longfellow-1854",
        given_name="George",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1854-02",
        death_date="1922-01-25",
        notes="Son of John R. & Mary Brown. Twin with Albert.",
    ))
    tree.add_relationship(Relationship(parent_id="john-r-longfellow-1828", child_id="george-longfellow-1854"))
    tree.add_relationship(Relationship(parent_id="mary-brown-longfellow", child_id="george-longfellow-1854"))

    tree.add_person(Person(
        id="walter-longfellow-1860",
        given_name="Walter",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1860-09",
        death_date="1933-09",
        notes="Son of John R. & Mary Brown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-r-longfellow-1828", child_id="walter-longfellow-1860"))
    tree.add_relationship(Relationship(parent_id="mary-brown-longfellow", child_id="walter-longfellow-1860"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  EIGHTH GENERATION                                              ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # John H. (1850) already created above

    # -- First marriage: Helen S. Preme --

    tree.add_person(Person(
        id="helen-preme",
        given_name="Helen S.",
        surname="Preme",
        gender=Gender.FEMALE,
        notes="First wife of John H. Longfellow. Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="john-h-longfellow-1850",
        partner2_id="helen-preme",
        union_date="1872-12-24",
        notes="Married December 24, 1872.",
    ))

    # Children with Helen S. Preme
    tree.add_person(Person(
        id="albert-r-longfellow-1875",
        given_name="Albert R.",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1875-01-25",
        notes="Son of John H. & Helen S. Preme. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="albert-r-longfellow-1875"))
    tree.add_relationship(Relationship(parent_id="helen-preme", child_id="albert-r-longfellow-1875"))

    tree.add_person(Person(
        id="samuel-h-longfellow-1876",
        given_name="Samuel H.",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1876-10-19",
        death_date="1933-12-01",
        notes="Son of John H. & Helen S. Preme.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="samuel-h-longfellow-1876"))
    tree.add_relationship(Relationship(parent_id="helen-preme", child_id="samuel-h-longfellow-1876"))

    # -- Second marriage: Viola Cambelle --

    tree.add_person(Person(
        id="viola-cambelle",
        given_name="Viola",
        surname="Cambelle",
        gender=Gender.FEMALE,
        notes="Second wife of John H. Longfellow. Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="john-h-longfellow-1850",
        partner2_id="viola-cambelle",
        union_date="1882-03-19",
        notes="Married March 19, 1882.",
    ))

    # Children with Viola Cambelle
    tree.add_person(Person(
        id="chester-longfellow-1883",
        given_name="Chester",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1883-05-07",
        death_date="1884-02-14",
        notes="Son of John H. & Viola Cambelle. Died as infant.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="chester-longfellow-1883"))
    tree.add_relationship(Relationship(parent_id="viola-cambelle", child_id="chester-longfellow-1883"))

    tree.add_person(Person(
        id="mildred-rena-longfellow-1885",
        given_name="Mildred Rena",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1885-01-06",
        death_date="1976-10-19",
        death_place="Hennepin County, Minnesota",
        notes=(
            "Daughter of John H. & Viola Cambelle. Continued the line. "
            "Widow July 21, 1927. Second husband Arthur R. Smith (married Jan 19, 1934). "
            "Buried in Riverside Cemetery, Riverside, St. Louis County, Minnesota. "
            "Resided in Minneapolis, Hennepin County, Minnesota."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="mildred-rena-longfellow-1885"))
    tree.add_relationship(Relationship(parent_id="viola-cambelle", child_id="mildred-rena-longfellow-1885"))

    tree.add_person(Person(
        id="harry-b-longfellow-1886",
        given_name="Harry B.",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1886-10-12",
        notes="Son of John H. & Viola Cambelle. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="harry-b-longfellow-1886"))
    tree.add_relationship(Relationship(parent_id="viola-cambelle", child_id="harry-b-longfellow-1886"))

    tree.add_person(Person(
        id="margaret-m-longfellow-1889",
        given_name="Margaret M.",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1889-05-16",
        notes="Daughter of John H. & Viola Cambelle. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="margaret-m-longfellow-1889"))
    tree.add_relationship(Relationship(parent_id="viola-cambelle", child_id="margaret-m-longfellow-1889"))

    tree.add_person(Person(
        id="john-c-longfellow-1891",
        given_name="John C.",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1891-12-20",
        notes="Son of John H. & Viola Cambelle. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="john-c-longfellow-1891"))
    tree.add_relationship(Relationship(parent_id="viola-cambelle", child_id="john-c-longfellow-1891"))

    tree.add_person(Person(
        id="helen-v-longfellow-1894",
        given_name="Helen V.",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1894-12-04",
        notes="Daughter of John H. & Viola Cambelle. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="helen-v-longfellow-1894"))
    tree.add_relationship(Relationship(parent_id="viola-cambelle", child_id="helen-v-longfellow-1894"))

    tree.add_person(Person(
        id="clarence-r-longfellow-1900",
        given_name="Clarence R.",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1900-03-11",
        notes="Son of John H. & Viola Cambelle. Death date unknown.",
    ))
    tree.add_relationship(Relationship(parent_id="john-h-longfellow-1850", child_id="clarence-r-longfellow-1900"))
    tree.add_relationship(Relationship(parent_id="viola-cambelle", child_id="clarence-r-longfellow-1900"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  NINTH GENERATION                                               ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # Mildred Rena Longfellow (1885) already created above

    # -- First marriage: Dr. Lindley Ambrose Parkinson Sr --

    tree.add_person(Person(
        id="lindley-parkinson-sr",
        given_name="Lindley Ambrose",
        surname="Parkinson",
        gender=Gender.MALE,
        birth_date="1863",
        birth_place="Truro, Franklin County, Ohio",
        death_date="1927-07-21",
        death_place="Wright, Carlton County, Minnesota",
        notes=(
            "Dr. Lindley Ambrose Parkinson Sr. Son of Daniel Homer Parkinson and "
            "Sarah Ann Seiler. Buried in Riverside Cemetery, Riverside, "
            "St. Louis County, Minnesota."
        ),
    ))
    tree.add_union(Union(
        partner1_id="mildred-rena-longfellow-1885",
        partner2_id="lindley-parkinson-sr",
        union_date="1905-11-20",
        end_date="1927-07-21",
        end_reason="death",
        notes="Married November 20, 1905. He died July 21, 1927.",
    ))

    # Children of Mildred Rena & Dr. Parkinson Sr
    tree.add_person(Person(
        id="mildred-e-parkinson-1906",
        given_name="Mildred E.",
        surname="Parkinson",
        gender=Gender.FEMALE,
        birth_date="1906-11-21",
        death_date="2005-01-26",
        death_place="Bloomington, Hennepin County, Minnesota",
        notes=(
            "Daughter of Mildred Rena Longfellow & Dr. Parkinson Sr. "
            "Appeared on 1930 census in Belvidere, Jackson County, South Dakota. "
            "Retired in 1971 from Bloomington Public Schools. "
            "Widow April 9, 1981. Died in Nursing Home, Bloomington, MN. "
            "Buried Feb 1, 2005 in Riverside Cemetery, Riverside, St. Louis Co., MN. "
            "Named after her mother."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="mildred-rena-longfellow-1885", child_id="mildred-e-parkinson-1906"))
    tree.add_relationship(Relationship(parent_id="lindley-parkinson-sr", child_id="mildred-e-parkinson-1906"))

    tree.add_person(Person(
        id="lindley-parkinson-jr",
        given_name="Lindley Ambrose",
        surname="Parkinson",
        gender=Gender.MALE,
        birth_date="1909-03-16",
        notes="Son of Mildred Rena Longfellow & Dr. Parkinson Sr. Lindley Ambrose Parkinson Jr.",
    ))
    tree.add_relationship(Relationship(parent_id="mildred-rena-longfellow-1885", child_id="lindley-parkinson-jr"))
    tree.add_relationship(Relationship(parent_id="lindley-parkinson-sr", child_id="lindley-parkinson-jr"))

    tree.add_person(Person(
        id="margaret-a-parkinson-1917",
        given_name="Margaret A.",
        surname="Parkinson",
        gender=Gender.FEMALE,
        birth_date="1917-11-03",
        notes="Daughter of Mildred Rena Longfellow & Dr. Parkinson Sr.",
    ))
    tree.add_relationship(Relationship(parent_id="mildred-rena-longfellow-1885", child_id="margaret-a-parkinson-1917"))
    tree.add_relationship(Relationship(parent_id="lindley-parkinson-sr", child_id="margaret-a-parkinson-1917"))

    # Margaret A. Parkinson married Arthur R. Smith
    tree.add_person(Person(
        id="arthur-r-smith",
        given_name="Arthur R.",
        surname="Smith",
        gender=Gender.MALE,
        notes="Second husband of Mildred Rena Longfellow (married Jan 9, 1934). Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="mildred-rena-longfellow-1885",
        partner2_id="arthur-r-smith",
        union_date="1934-01-09",
        notes="Married January 9, 1934. Second marriage for Mildred Rena.",
    ))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  TENTH GENERATION                                               ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # -- Mildred E. Parkinson & Sterling Thomas Walters Sr --

    tree.add_person(Person(
        id="sterling-walters-sr",
        given_name="Sterling Thomas",
        surname="Walters",
        gender=Gender.MALE,
        birth_date="1905-11-05",
        birth_place="Illinois",
        death_date="1981-04-09",
        death_place="San Diego, San Diego County, California",
        nicknames=["Sue-Sue"],
        notes=(
            "Sterling Thomas Walters Sr. Son of Brooks. "
            "Appeared on 1930 census in Belvidere, Jackson County, South Dakota. "
            "Also known as Sue-Sue. "
            "Buried in Riverside Cemetery, Riverside, St. Louis County, Minnesota."
        ),
    ))
    tree.add_union(Union(
        partner1_id="mildred-e-parkinson-1906",
        partner2_id="sterling-walters-sr",
        union_date="1929-03-11",
        notes="Married March 11, 1929.",
    ))

    # Children of Mildred E. Parkinson & Sterling Walters Sr
    tree.add_person(Person(
        id="sterling-walters-jr",
        given_name="Sterling Thomas",
        surname="Walters",
        gender=Gender.MALE,
        birth_date="1929-10-07",
        nicknames=["Sterling Thomas Walters Jr"],
        notes="Son of Mildred E. Parkinson & Sterling Thomas Walters Sr.",
    ))
    tree.add_relationship(Relationship(parent_id="mildred-e-parkinson-1906", child_id="sterling-walters-jr"))
    tree.add_relationship(Relationship(parent_id="sterling-walters-sr", child_id="sterling-walters-jr"))

    tree.add_person(Person(
        id="merle-lindley-walters",
        given_name="Merle Lindley",
        surname="Walters",
        gender=Gender.MALE,
        birth_date="1930-12-17",
        notes="Son of Mildred E. Parkinson & Sterling Thomas Walters Sr.",
    ))
    tree.add_relationship(Relationship(parent_id="mildred-e-parkinson-1906", child_id="merle-lindley-walters"))
    tree.add_relationship(Relationship(parent_id="sterling-walters-sr", child_id="merle-lindley-walters"))

    tree.add_person(Person(
        id="wayne-luther-walters",
        given_name="Wayne Luther",
        surname="Walters",
        gender=Gender.MALE,
        birth_date="1932-03-27",
        notes="Son of Mildred E. Parkinson & Sterling Thomas Walters Sr.",
    ))
    tree.add_relationship(Relationship(parent_id="mildred-e-parkinson-1906", child_id="wayne-luther-walters"))
    tree.add_relationship(Relationship(parent_id="sterling-walters-sr", child_id="wayne-luther-walters"))

    tree.add_person(Person(
        id="glen-robert-walters",
        given_name="Glen Robert",
        surname="Walters",
        gender=Gender.MALE,
        birth_date="1943-09-11",
        notes="Son of Mildred E. Parkinson & Sterling Thomas Walters Sr.",
    ))
    tree.add_relationship(Relationship(parent_id="mildred-e-parkinson-1906", child_id="glen-robert-walters"))
    tree.add_relationship(Relationship(parent_id="sterling-walters-sr", child_id="glen-robert-walters"))

    # -- Lindley Ambrose Parkinson Jr & Helen May Hornsby --

    tree.add_person(Person(
        id="helen-may-hornsby",
        given_name="Helen May",
        surname="Hornsby",
        gender=Gender.FEMALE,
        birth_date="1913-05-22",
        death_date="1993-11-24",
        notes=(
            "Wife of Lindley Ambrose Parkinson Jr. "
            "Resided in Anoka, Anoka County, Minnesota."
        ),
    ))
    tree.add_union(Union(
        partner1_id="lindley-parkinson-jr",
        partner2_id="helen-may-hornsby",
    ))

    # Children of Lindley Jr & Helen May
    tree.add_person(Person(
        id="lindley-parkinson-iii",
        given_name="Lindley Ambrose",
        surname="Parkinson",
        gender=Gender.MALE,
        birth_date="1939-01-16",
        notes="Son of Lindley Ambrose Parkinson Jr & Helen May Hornsby.",
    ))
    tree.add_relationship(Relationship(parent_id="lindley-parkinson-jr", child_id="lindley-parkinson-iii"))
    tree.add_relationship(Relationship(parent_id="helen-may-hornsby", child_id="lindley-parkinson-iii"))

    tree.add_person(Person(
        id="kay-parkinson-1947",
        given_name="Kay",
        surname="Parkinson",
        gender=Gender.FEMALE,
        birth_date="1947-08-26",
        birth_place="Ramsey County, Minnesota",
        notes="Daughter of Lindley Ambrose Parkinson Jr & Helen May Hornsby.",
    ))
    tree.add_relationship(Relationship(parent_id="lindley-parkinson-jr", child_id="kay-parkinson-1947"))
    tree.add_relationship(Relationship(parent_id="helen-may-hornsby", child_id="kay-parkinson-1947"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  LIFE EVENTS                                                     ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # -- Mildred Rena Longfellow --
    tree.add_event(LifeEvent(
        person_id="mildred-rena-longfellow-1885",
        event_type=EventType.RESIDENCE,
        place="Minneapolis, Hennepin County, Minnesota",
        description="Resided in Minneapolis, Hennepin County, Minnesota",
        source=SOURCE_DOC,
    ))

    # -- Mildred E. Parkinson --
    tree.add_event(LifeEvent(
        person_id="mildred-e-parkinson-1906",
        event_type=EventType.RESIDENCE,
        date="1930-04-26",
        place="Belvidere, Jackson County, South Dakota",
        description="Appeared on 1930 census in Belvidere, Jackson County, South Dakota",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="mildred-e-parkinson-1906",
        event_type=EventType.CAREER,
        end_date="1971",
        place="Bloomington, Minnesota",
        description="Retired in 1971 from Bloomington Public Schools",
        source=SOURCE_DOC,
    ))

    # -- Sterling Thomas Walters Sr --
    tree.add_event(LifeEvent(
        person_id="sterling-walters-sr",
        event_type=EventType.RESIDENCE,
        date="1930-04-26",
        place="Belvidere, Jackson County, South Dakota",
        description="Appeared on 1930 census in Belvidere, Jackson County, South Dakota",
        source=SOURCE_DOC,
    ))

    # -- Helen May Hornsby --
    tree.add_event(LifeEvent(
        person_id="helen-may-hornsby",
        event_type=EventType.RESIDENCE,
        place="Anoka, Anoka County, Minnesota",
        description="Resided in Anoka, Anoka County, Minnesota",
        source=SOURCE_DOC,
    ))

    return tree


def main():
    print("Initializing database...")
    db_path = init_db()
    print(f"  Database: {db_path}")

    print("\nBuilding Longfellow descendant tree...")
    tree = build_longfellow_tree()

    print(f"  People:        {tree.num_people}")
    print(f"  Relationships: {len(tree.relationships)}")
    print(f"  Unions:        {len(tree.unions)}")
    print(f"  Events:        {len(tree.events)}")
    print(f"  Sources:       {len(tree.sources)}")

    print("\nSaving to database...")
    repo = TreeRepository()
    repo.save_tree(tree)

    print("\nDone! Longfellow data loaded.")
    print("  Try: python3 -m cli show william-longfellow-1650")
    print("  Try: python3 -m cli stats")


if __name__ == "__main__":
    main()
