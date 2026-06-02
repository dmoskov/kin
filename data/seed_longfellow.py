#!/usr/bin/env python3
"""Seed the family tree database with Longfellow descendant data.

Source:
  - "Descendants of William LONGFELLOW" report (4 Dec 2009)
  - 10 generations, ~62 individuals

Run from project root:
    python3 data/seed_longfellow.py
"""

import sys
from pathlib import Path

# Add src/ to path so we can import our modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database.connection import init_db
from database.repository import TreeRepository
from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, Union
from models.source import Source, SourceType
from models.tree import FamilyTree

SOURCE_DOC = "longfellow-descendants-2009"
SOURCE_FARNHAM = "farnham-2002"
SOURCE_FINDAGRAVE = "findagrave"
SOURCE_ME_HISTORICAL = "me-historical-society"


def build_longfellow_tree() -> FamilyTree:
    """Build the Longfellow descendant tree from the 4 Dec 2009 report."""
    tree = FamilyTree()

    # ── Sources ─────────────────────────────────────────────────────────
    tree.add_source(Source(
        id=SOURCE_DOC,
        name="Descendants of William Longfellow",
        source_type=SourceType.DOCUMENT,
        date="2009-12-04",
        description="Descendant report for William Longfellow (1650–1690), 10 generations.",
    ))
    tree.add_source(Source(
        id=SOURCE_FARNHAM,
        name="A Longfellow Genealogy",
        source_type=SourceType.PUBLIC,
        author="Russell C. Farnham & Dorothy E. Crawford",
        date="2002",
        description=(
            "Comprising the English ancestry and descendants of the immigrant "
            "William Longfellow of Newbury, Massachusetts, and Henry Wadsworth "
            "Longfellow. Walrus Publishers, 1188 pages."
        ),
    ))
    tree.add_source(Source(
        id=SOURCE_FINDAGRAVE,
        name="Find A Grave",
        source_type=SourceType.PUBLIC,
        url="https://www.findagrave.com",
        description="Online cemetery records and gravestone photographs.",
    ))
    tree.add_source(Source(
        id=SOURCE_ME_HISTORICAL,
        name="Maine Historical Society Collections",
        source_type=SourceType.PUBLIC,
        url="https://www.mainehistory.org",
        description="Maine Historical Society library and archival collections.",
    ))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  ENGLISH ANCESTORS                                              ║
    # ╚══════════════════════════════════════════════════════════════════╝

    tree.add_person(Person(
        id="william-longfellow-sr",
        given_name="William",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1619",
        birth_place="Horsforth, Yorkshire, England",
        death_date="1676",
        death_place="Horsforth, Yorkshire, England",
        notes=(
            "Father of the immigrant William Longfellow. Resided in Horsforth, "
            "Yorkshire, England. Source: Farnham (2002)."
        ),
    ))

    tree.add_person(Person(
        id="elizabeth-thornton",
        given_name="Elizabeth",
        surname="Thornton",
        gender=Gender.FEMALE,
        birth_date="~1622",
        birth_place="Yorkshire, England",
        notes=(
            "Mother of the immigrant William Longfellow. Wife of William Longfellow Sr. "
            "Source: Farnham (2002)."
        ),
    ))
    tree.add_union(Union(
        partner1_id="william-longfellow-sr",
        partner2_id="elizabeth-thornton",
        notes="Married in Yorkshire, England.",
    ))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  FIRST GENERATION                                               ║
    # ╚══════════════════════════════════════════════════════════════════╝

    tree.add_person(Person(
        id="william-longfellow-1650",
        given_name="William",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1650-10-20",
        birth_place="Horsforth, Yorkshire, England",
        death_date="1690-10-31",
        death_place="Anticosti Island, Quebec, Canada",
        notes=(
            "Progenitor of the Longfellow line in America. Born 20 Oct 1650/51 in "
            "Horsforth, Yorkshire, England. Immigrated to Newbury, MA c. 1676. "
            "Died 31 Oct 1690 in the Phips expedition to Quebec. "
            "Find A Grave Memorial #22571205."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-sr", child_id="william-longfellow-1650"))
    tree.add_relationship(Relationship(parent_id="elizabeth-thornton", child_id="william-longfellow-1650"))

    tree.add_person(Person(
        id="anne-sewall",
        given_name="Anne",
        surname="Sewall",
        gender=Gender.FEMALE,
        birth_place="Newbury, Massachusetts",
        notes=(
            "Wife of William Longfellow. Sister of Chief Justice Samuel Sewall. "
            "Death date unknown. Samuel Sewall's diary references eight children."
        ),
    ))
    tree.add_union(Union(
        partner1_id="william-longfellow-1650",
        partner2_id="anne-sewall",
        union_date="1678-11-10",
        union_place="Newbury, Massachusetts",
        notes="Married November 10, 1678.",
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
        birth_place="Newbury, Massachusetts",
        death_date="1764-11-17",
        death_place="Byfield (Newbury Falls), Essex County, Massachusetts",
        notes=(
            "Lieut. Stephen Longfellow, 'the Blacksmith.' Son of William & Anne Sewall. "
            "Locksmith and farmer in Byfield (Newbury Falls), Essex County, MA. "
            "Find A Grave Memorial #14327894. Buried Elm Street, Byfield."
        ),
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
        birth_place="Newbury, Massachusetts",
        death_date="1731",
        death_place="Hampton Falls, New Hampshire",
        notes=(
            "Youngest son of William & Anne Sewall. Died 1731 in Hampton Falls, NH. "
            "Source: Farnham (2002)."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="william-longfellow-1650", child_id="nathan-longfellow-1690"))
    tree.add_relationship(Relationship(parent_id="anne-sewall", child_id="nathan-longfellow-1690"))

    # -- Nathan Longfellow's branch (Generation 2b) --

    tree.add_person(Person(
        id="jonathan-longfellow-1714",
        given_name="Jonathan",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1714",
        birth_place="Deerfield (Nottingham), New Hampshire",
        death_date="1774",
        death_place="Machias, Maine",
        notes=(
            "Son of Nathan Longfellow (1690). Founder of Deerfield, NH. "
            "Died 1774 in Machias, Maine. Source: Farnham (2002)."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="nathan-longfellow-1690", child_id="jonathan-longfellow-1714"))

    # ╔══════════════════════════════════════════════════════════════════╗
    # ║  SECOND GENERATION                                              ║
    # ╚══════════════════════════════════════════════════════════════════╝

    # Stephen (1685) already created above

    tree.add_person(Person(
        id="abigail-thompson",
        given_name="Abigail",
        surname="Thompson",
        gender=Gender.FEMALE,
        birth_place="Newbury, Massachusetts",
        notes="Wife of Lieut. Stephen Longfellow. Death date unknown.",
    ))
    tree.add_union(Union(
        partner1_id="stephen-longfellow-1685",
        partner2_id="abigail-thompson",
        union_date="1714-03-25",
        union_place="Newbury, Massachusetts",
        notes="Married March 25, 1714.",
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
        birth_place="Byfield, Essex County, Massachusetts",
        death_date="1790-05-01",
        death_place="Gorham, Maine",
        notes=(
            "Stephen Longfellow, 'the Schoolmaster.' Son of Lieut. Stephen & Abigail "
            "Thompson. Invited to teach in Falmouth (Portland), Maine (1744–1745). "
            "Held roles as town clerk, judicial court clerk, register of probate for "
            "Cumberland County. Find A Grave Memorial #101663338. Buried Eastern "
            "Cemetery, Portland, Maine (Plot Sec. F, Gr 32)."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1685", child_id="stephen-longfellow-1723"))
    tree.add_relationship(Relationship(parent_id="abigail-thompson", child_id="stephen-longfellow-1723"))

    # -- Stephen (1723) "the Schoolmaster" branch: the poet's line --

    tree.add_person(Person(
        id="tabitha-bragdon",
        given_name="Tabitha",
        surname="Bragdon",
        gender=Gender.FEMALE,
        death_date="1777-06-11",
        death_place="Portland (Falmouth), Maine",
        notes=(
            "Wife of Stephen Longfellow (1723). Died 11 Jun 1777 in Portland. "
            "Buried beside Stephen at Eastern Cemetery, Portland, Maine."
        ),
    ))
    tree.add_union(Union(
        partner1_id="stephen-longfellow-1723",
        partner2_id="tabitha-bragdon",
        union_date="1749-10-19",
        union_place="Falmouth (Portland), Maine",
        notes="Married October 19, 1749.",
    ))

    # -- Children of Stephen (1723) & Tabitha Bragdon --

    tree.add_person(Person(
        id="stephen-longfellow-1750",
        given_name="Stephen",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1750-08-13",
        birth_place="Falmouth (Portland), Maine",
        death_date="1824-05-28",
        death_place="Gorham, Maine",
        notes=(
            "Stephen Longfellow, 'the Judge.' Son of Stephen & Tabitha Bragdon. "
            "Judge of court of common pleas (1798–1811). State senator and "
            "representative to Massachusetts general court."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1723", child_id="stephen-longfellow-1750"))
    tree.add_relationship(Relationship(parent_id="tabitha-bragdon", child_id="stephen-longfellow-1750"))

    tree.add_person(Person(
        id="patience-young",
        given_name="Patience",
        surname="Young",
        gender=Gender.FEMALE,
        notes="Wife of Stephen Longfellow (1750), 'the Judge.'",
    ))
    tree.add_union(Union(
        partner1_id="stephen-longfellow-1750",
        partner2_id="patience-young",
        union_date="1773-12-13",
        notes="Married December 13, 1773.",
    ))

    # -- Children of Stephen (1750) & Patience Young --

    tree.add_person(Person(
        id="stephen-longfellow-1776",
        given_name="Stephen",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1776-03-23",
        birth_place="Gorham, Maine",
        death_date="1849-08-23",
        death_place="Portland, Maine",
        notes=(
            "Son of Stephen & Patience Young. Lawyer, Bowdoin College trustee "
            "(19 years), president of Maine Historical Society (1834). "
            "Father of the poet Henry Wadsworth Longfellow."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1750", child_id="stephen-longfellow-1776"))
    tree.add_relationship(Relationship(parent_id="patience-young", child_id="stephen-longfellow-1776"))

    tree.add_person(Person(
        id="zilpah-wadsworth",
        given_name="Zilpah",
        surname="Wadsworth",
        gender=Gender.FEMALE,
        birth_date="1778",
        birth_place="Duxbury, Massachusetts",
        death_date="1851",
        death_place="Portland, Maine",
        notes=(
            "Wife of Stephen Longfellow (1776). Daughter of General Peleg Wadsworth, "
            "Revolutionary War major-general. Mother of the poet."
        ),
    ))
    tree.add_union(Union(
        partner1_id="stephen-longfellow-1776",
        partner2_id="zilpah-wadsworth",
        union_date="1804-01-01",
        notes="Married January 1, 1804.",
    ))

    # -- Children of Stephen (1776) & Zilpah Wadsworth --

    tree.add_person(Person(
        id="henry-wadsworth-longfellow-1807",
        given_name="Henry Wadsworth",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1807-02-27",
        birth_place="Portland, Maine",
        death_date="1882-03-24",
        death_place="Cambridge, Massachusetts",
        notes=(
            "Most famous American poet of his era. Harvard professor of modern "
            "languages (22 years). Works include Evangeline, The Song of Hiawatha, "
            "The Courtship of Miles Standish. Born in the Wadsworth-Longfellow House "
            "on Congress Street, Portland, ME."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="stephen-longfellow-1776", child_id="henry-wadsworth-longfellow-1807"))
    tree.add_relationship(Relationship(parent_id="zilpah-wadsworth", child_id="henry-wadsworth-longfellow-1807"))

    # -- Henry Wadsworth Longfellow's first marriage --

    tree.add_person(Person(
        id="mary-storer-potter",
        given_name="Mary Storer",
        surname="Potter",
        gender=Gender.FEMALE,
        death_date="1835",
        death_place="Rotterdam, Netherlands",
        notes=(
            "First wife of Henry Wadsworth Longfellow. Married 1831. "
            "Died 1835 in Rotterdam from complications of miscarriage."
        ),
    ))
    tree.add_union(Union(
        partner1_id="henry-wadsworth-longfellow-1807",
        partner2_id="mary-storer-potter",
        union_date="1831",
        end_date="1835",
        end_reason="death",
        notes="Married 1831. She died 1835 in Rotterdam.",
    ))

    # -- Henry Wadsworth Longfellow's second marriage --

    tree.add_person(Person(
        id="fanny-appleton",
        given_name="Fanny",
        surname="Appleton",
        gender=Gender.FEMALE,
        birth_date="1817",
        death_date="1861",
        death_place="Cambridge, Massachusetts",
        notes=(
            "Second wife of Henry Wadsworth Longfellow. Married 1843. "
            "Died 1861 from burns when her dress caught fire. "
            "Daughter of industrialist Nathan Appleton."
        ),
    ))
    tree.add_union(Union(
        partner1_id="henry-wadsworth-longfellow-1807",
        partner2_id="fanny-appleton",
        union_date="1843",
        end_date="1861",
        end_reason="death",
        notes="Married 1843. She died July 1861 from accidental burns.",
    ))

    # -- Children of Henry Wadsworth & Fanny Appleton --

    tree.add_person(Person(
        id="charles-longfellow-1844",
        given_name="Charles",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1844",
        birth_place="Cambridge, Massachusetts",
        death_date="1893",
        notes="Eldest son of Henry Wadsworth & Fanny Appleton Longfellow.",
    ))
    tree.add_relationship(Relationship(parent_id="henry-wadsworth-longfellow-1807", child_id="charles-longfellow-1844"))
    tree.add_relationship(Relationship(parent_id="fanny-appleton", child_id="charles-longfellow-1844"))

    tree.add_person(Person(
        id="ernest-longfellow-1845",
        given_name="Ernest Wadsworth",
        surname="Longfellow",
        gender=Gender.MALE,
        birth_date="1845",
        birth_place="Cambridge, Massachusetts",
        death_date="1921",
        notes="Second son of Henry Wadsworth & Fanny Appleton Longfellow.",
    ))
    tree.add_relationship(Relationship(parent_id="henry-wadsworth-longfellow-1807", child_id="ernest-longfellow-1845"))
    tree.add_relationship(Relationship(parent_id="fanny-appleton", child_id="ernest-longfellow-1845"))

    tree.add_person(Person(
        id="fanny-longfellow-1847",
        given_name="Fanny",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1847",
        birth_place="Cambridge, Massachusetts",
        death_date="1883",
        notes="Daughter of Henry Wadsworth & Fanny Appleton Longfellow.",
    ))
    tree.add_relationship(Relationship(parent_id="henry-wadsworth-longfellow-1807", child_id="fanny-longfellow-1847"))
    tree.add_relationship(Relationship(parent_id="fanny-appleton", child_id="fanny-longfellow-1847"))

    tree.add_person(Person(
        id="alice-longfellow-1850",
        given_name="Alice",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1850",
        birth_place="Cambridge, Massachusetts",
        death_date="1928",
        notes=(
            "Daughter of Henry Wadsworth & Fanny Appleton Longfellow. "
            "Lived in the Longfellow House (Craigie House) until her death."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="henry-wadsworth-longfellow-1807", child_id="alice-longfellow-1850"))
    tree.add_relationship(Relationship(parent_id="fanny-appleton", child_id="alice-longfellow-1850"))

    tree.add_person(Person(
        id="edith-longfellow-1853",
        given_name="Edith",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1853",
        birth_place="Cambridge, Massachusetts",
        notes="Daughter of Henry Wadsworth & Fanny Appleton Longfellow.",
    ))
    tree.add_relationship(Relationship(parent_id="henry-wadsworth-longfellow-1807", child_id="edith-longfellow-1853"))
    tree.add_relationship(Relationship(parent_id="fanny-appleton", child_id="edith-longfellow-1853"))

    tree.add_person(Person(
        id="anne-longfellow-1855",
        given_name="Anne Allegra",
        surname="Longfellow",
        gender=Gender.FEMALE,
        birth_date="1855",
        birth_place="Cambridge, Massachusetts",
        death_date="1855",
        notes="Daughter of Henry Wadsworth & Fanny Appleton Longfellow. Died as infant.",
    ))
    tree.add_relationship(Relationship(parent_id="henry-wadsworth-longfellow-1807", child_id="anne-longfellow-1855"))
    tree.add_relationship(Relationship(parent_id="fanny-appleton", child_id="anne-longfellow-1855"))

    # -- General Peleg Wadsworth (Zilpah's father, Revolutionary War hero) --

    tree.add_person(Person(
        id="peleg-wadsworth",
        given_name="Peleg",
        surname="Wadsworth",
        gender=Gender.MALE,
        birth_date="1748",
        birth_place="Duxbury, Massachusetts",
        death_date="1829",
        death_place="Hiram, Maine",
        notes=(
            "General Peleg Wadsworth, Revolutionary War major-general. "
            "Father of Zilpah Wadsworth Longfellow. Built the Wadsworth-Longfellow "
            "House on Congress Street, Portland, ME — now a National Historic Site."
        ),
    ))
    tree.add_relationship(Relationship(parent_id="peleg-wadsworth", child_id="zilpah-wadsworth"))

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

    # ── William Longfellow (1650) ──────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1650",
        event_type=EventType.BIRTH,
        date="1650-10-20",
        place="Horsforth, Yorkshire, England",
        description="Born 20 Oct 1650/51 in Horsforth, Yorkshire, England",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1650",
        event_type=EventType.IMMIGRATION,
        date="1676",
        place="Newbury, Massachusetts",
        description="Immigrated from Horsforth, Yorkshire to Newbury, MA c. 1676",
        source=SOURCE_FARNHAM,
        date_circa=True,
    ))
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1650",
        event_type=EventType.MARRIAGE,
        date="1678-11-10",
        place="Newbury, Massachusetts",
        description="Married Anne Sewall, sister of Chief Justice Samuel Sewall",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1650",
        event_type=EventType.MILITARY,
        date="1690",
        place="Anticosti Island, Quebec, Canada",
        description="Served as ensign in the Phips expedition to Quebec, 1690. Died in service.",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1650",
        event_type=EventType.DEATH,
        date="1690-10-31",
        place="Anticosti Island, Quebec, Canada",
        description="Died 31 Oct 1690 at Anticosti Island during the Phips expedition",
        source=SOURCE_FINDAGRAVE,
    ))

    # ── Stephen Longfellow (1685) "the Blacksmith" ────────────────────
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1685",
        event_type=EventType.BIRTH,
        date="1685-09-22",
        place="Newbury, Massachusetts",
        description="Born 22 Sep 1685 in Newbury, Massachusetts",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1685",
        event_type=EventType.CAREER,
        place="Byfield (Newbury Falls), Essex County, Massachusetts",
        description="Locksmith and farmer in Byfield (Newbury Falls), Essex County, MA",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1685",
        event_type=EventType.MARRIAGE,
        date="1714-03-25",
        place="Newbury, Massachusetts",
        description="Married Abigail Thompson",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1685",
        event_type=EventType.DEATH,
        date="1764-11-17",
        place="Byfield (Newbury Falls), Essex County, Massachusetts",
        description="Died 17 Nov 1764 in Byfield. Buried Elm Street, Byfield.",
        source=SOURCE_FINDAGRAVE,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1685",
        event_type=EventType.RELIGION,
        place="Byfield Parish Church, Newbury, Massachusetts",
        description="Member of Byfield Parish Church (established 1702; renamed 1704 for Judge Nathanial Byfield)",
        source=SOURCE_FARNHAM,
    ))

    # ── Stephen Longfellow (1723) "the Schoolmaster" ──────────────────
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1723",
        event_type=EventType.BIRTH,
        date="1723-02-07",
        place="Byfield, Essex County, Massachusetts",
        description="Born 7 Feb 1723 in Byfield, Essex County, MA",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1723",
        event_type=EventType.EDUCATION,
        date="1744",
        place="Falmouth (Portland), Maine",
        description="Invited to teach in Falmouth (Portland), Maine (1744–1745 letter documented)",
        source=SOURCE_ME_HISTORICAL,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1723",
        event_type=EventType.CAREER,
        place="Falmouth (Portland), Maine",
        description="Town clerk, judicial court clerk, register of probate for Cumberland County",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1723",
        event_type=EventType.MARRIAGE,
        date="1749-10-19",
        place="Falmouth (Portland), Maine",
        description="Married Tabitha Bragdon",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1723",
        event_type=EventType.RESIDENCE,
        place="Gorham, Maine",
        description="Resided in Gorham, Maine in later life",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1723",
        event_type=EventType.DEATH,
        date="1790-05-01",
        place="Gorham, Maine",
        description="Died 1 May 1790 in Gorham, Maine. Buried Eastern Cemetery, Portland, ME (Plot Sec. F, Gr 32).",
        source=SOURCE_FINDAGRAVE,
    ))

    # ── Tabitha Bragdon ────────────────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="tabitha-bragdon",
        event_type=EventType.DEATH,
        date="1777-06-11",
        place="Portland (Falmouth), Maine",
        description="Died 11 Jun 1777 in Portland. Buried beside Stephen at Eastern Cemetery, Portland, ME.",
        source=SOURCE_FARNHAM,
    ))

    # ── Stephen Longfellow (1750) "the Judge" ─────────────────────────
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1750",
        event_type=EventType.BIRTH,
        date="1750-08-13",
        place="Falmouth (Portland), Maine",
        description="Born 13 Aug 1750 in Falmouth (Portland), Maine",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1750",
        event_type=EventType.MARRIAGE,
        date="1773-12-13",
        description="Married Patience Young",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1750",
        event_type=EventType.CAREER,
        date="1798",
        end_date="1811",
        place="Gorham, Maine",
        description="Judge of court of common pleas (1798–1811)",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1750",
        event_type=EventType.CAREER,
        place="Massachusetts",
        description="State senator and representative to Massachusetts general court",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1750",
        event_type=EventType.DEATH,
        date="1824-05-28",
        place="Gorham, Maine",
        description="Died 28 May 1824 in Gorham, Maine",
        source=SOURCE_FARNHAM,
    ))

    # ── Stephen Longfellow (1776) ─────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1776",
        event_type=EventType.BIRTH,
        date="1776-03-23",
        place="Gorham, Maine",
        description="Born 23 Mar 1776 in Gorham, Maine",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1776",
        event_type=EventType.EDUCATION,
        place="Brunswick, Maine",
        description="Graduated from Bowdoin College",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1776",
        event_type=EventType.CAREER,
        place="Portland, Maine",
        description="Lawyer in Portland, Maine",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1776",
        event_type=EventType.MARRIAGE,
        date="1804-01-01",
        place="Portland, Maine",
        description="Married Zilpah Wadsworth, daughter of General Peleg Wadsworth",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1776",
        event_type=EventType.CAREER,
        date="1815",
        end_date="1834",
        place="Brunswick, Maine",
        description="Bowdoin College trustee (19 years)",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1776",
        event_type=EventType.CAREER,
        date="1834",
        place="Portland, Maine",
        description="President of Maine Historical Society (1834)",
        source=SOURCE_ME_HISTORICAL,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1776",
        event_type=EventType.DEATH,
        date="1849-08-23",
        place="Portland, Maine",
        description="Died 23 Aug 1849 in Portland, Maine",
        source=SOURCE_FARNHAM,
    ))

    # ── Zilpah Wadsworth ──────────────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="zilpah-wadsworth",
        event_type=EventType.BIRTH,
        date="1778",
        place="Duxbury, Massachusetts",
        description="Born 1778 in Duxbury, Massachusetts. Daughter of General Peleg Wadsworth.",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="zilpah-wadsworth",
        event_type=EventType.RESIDENCE,
        place="Portland, Maine",
        description="Resided in the Wadsworth-Longfellow House on Congress Street, Portland, ME",
        source=SOURCE_ME_HISTORICAL,
    ))
    tree.add_event(LifeEvent(
        person_id="zilpah-wadsworth",
        event_type=EventType.DEATH,
        date="1851",
        place="Portland, Maine",
        description="Died 1851 in Portland, Maine",
        source=SOURCE_FARNHAM,
    ))

    # ── General Peleg Wadsworth ───────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="peleg-wadsworth",
        event_type=EventType.BIRTH,
        date="1748",
        place="Duxbury, Massachusetts",
        description="Born 1748 in Duxbury, Massachusetts",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="peleg-wadsworth",
        event_type=EventType.MILITARY,
        date="1775",
        end_date="1783",
        place="Massachusetts and Maine",
        description="Revolutionary War major-general. Commanded forces in Massachusetts and Maine.",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="peleg-wadsworth",
        event_type=EventType.RESIDENCE,
        place="Portland, Maine",
        description="Built the Wadsworth-Longfellow House on Congress Street, Portland, ME — now a National Historic Site",
        source=SOURCE_ME_HISTORICAL,
    ))
    tree.add_event(LifeEvent(
        person_id="peleg-wadsworth",
        event_type=EventType.DEATH,
        date="1829",
        place="Hiram, Maine",
        description="Died 1829 in Hiram, Maine",
        source=SOURCE_FARNHAM,
    ))

    # ── Henry Wadsworth Longfellow (1807) ─────────────────────────────
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.BIRTH,
        date="1807-02-27",
        place="Portland, Maine",
        description="Born 27 Feb 1807 in the Wadsworth-Longfellow House, Portland, ME",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.EDUCATION,
        date="1825",
        place="Brunswick, Maine",
        description="Graduated from Bowdoin College, 1825",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.EDUCATION,
        date="1826",
        end_date="1829",
        place="Europe",
        description="Traveled to Europe to study languages (1826–1829)",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.CAREER,
        date="1829",
        end_date="1835",
        place="Brunswick, Maine",
        description="Professor of modern languages at Bowdoin College (1829–1835)",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.MARRIAGE,
        date="1831",
        place="Portland, Maine",
        description="First marriage to Mary Storer Potter",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.EDUCATION,
        date="1835",
        end_date="1836",
        place="Europe",
        description="Traveled to Europe for study and bereavement after Mary's death (1835–1836)",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.CAREER,
        date="1836",
        end_date="1854",
        place="Cambridge, Massachusetts",
        description="Harvard professor of modern languages (22 years), Smith Professor of French and Spanish",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.RESIDENCE,
        date="1837",
        place="Cambridge, Massachusetts",
        description="Took lodgings at Craigie House (now Longfellow House–Washington's Headquarters NHS), 105 Brattle Street, Cambridge, MA",
        source=SOURCE_ME_HISTORICAL,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.MARRIAGE,
        date="1843",
        place="Boston, Massachusetts",
        description="Second marriage to Fanny Appleton, daughter of industrialist Nathan Appleton",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.CAREER,
        date="1847",
        place="Cambridge, Massachusetts",
        description="Published Evangeline: A Tale of Acadie",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.CAREER,
        date="1855",
        place="Cambridge, Massachusetts",
        description="Published The Song of Hiawatha",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.CAREER,
        date="1858",
        place="Cambridge, Massachusetts",
        description="Published The Courtship of Miles Standish",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="henry-wadsworth-longfellow-1807",
        event_type=EventType.DEATH,
        date="1882-03-24",
        place="Cambridge, Massachusetts",
        description="Died 24 Mar 1882 in Cambridge, MA. Buried at Mount Auburn Cemetery, Cambridge.",
        source=SOURCE_FARNHAM,
    ))

    # ── Mary Storer Potter ────────────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="mary-storer-potter",
        event_type=EventType.DEATH,
        date="1835",
        place="Rotterdam, Netherlands",
        description="Died 1835 in Rotterdam from complications of miscarriage while traveling in Europe",
        source=SOURCE_FARNHAM,
    ))

    # ── Fanny Appleton ────────────────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="fanny-appleton",
        event_type=EventType.BIRTH,
        date="1817",
        place="Boston, Massachusetts",
        description="Born 1817 in Boston. Daughter of industrialist Nathan Appleton.",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="fanny-appleton",
        event_type=EventType.DEATH,
        date="1861-07",
        place="Cambridge, Massachusetts",
        description="Died July 1861 from burns when her dress caught fire at the Longfellow House, Cambridge",
        source=SOURCE_FARNHAM,
    ))

    # ── Nathan Longfellow (1690) ─────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="nathan-longfellow-1690",
        event_type=EventType.BIRTH,
        date="1690-02-05",
        place="Newbury, Massachusetts",
        description="Born 5 Feb 1690 in Newbury, Massachusetts",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="nathan-longfellow-1690",
        event_type=EventType.RESIDENCE,
        place="Hampton Falls, New Hampshire",
        description="Resided in Hampton Falls, New Hampshire",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="nathan-longfellow-1690",
        event_type=EventType.DEATH,
        date="1731",
        place="Hampton Falls, New Hampshire",
        description="Died 1731 in Hampton Falls, NH",
        source=SOURCE_FARNHAM,
    ))

    # ── Jonathan Longfellow (1714) ───────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="jonathan-longfellow-1714",
        event_type=EventType.BIRTH,
        date="1714",
        place="Deerfield (Nottingham), New Hampshire",
        description="Born 1714 in Deerfield (Nottingham), NH",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="jonathan-longfellow-1714",
        event_type=EventType.RESIDENCE,
        place="Deerfield, New Hampshire",
        description="Founder of Deerfield, NH",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="jonathan-longfellow-1714",
        event_type=EventType.RESIDENCE,
        place="Machias, Maine",
        description="Later resided in Machias, Maine",
        source=SOURCE_FARNHAM,
    ))
    tree.add_event(LifeEvent(
        person_id="jonathan-longfellow-1714",
        event_type=EventType.DEATH,
        date="1774",
        place="Machias, Maine",
        description="Died 1774 in Machias, Maine",
        source=SOURCE_FARNHAM,
    ))

    # ── William Longfellow (1714) ────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1714",
        event_type=EventType.BIRTH,
        date="1714-09-10",
        place="Byfield, Essex County, Massachusetts",
        description="Born 10 Sep 1714 in Byfield, Essex County, MA. Baptized at Byfield Parish Church.",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1714",
        event_type=EventType.MARRIAGE,
        date="1740-01-24",
        description="Married Hepsibah Plumer, January 24, 1739/40",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="william-longfellow-1714",
        event_type=EventType.DEATH,
        date="1787-08",
        description="Died Aug 1787",
        source=SOURCE_DOC,
    ))

    # ── Stephen Longfellow (1746) ────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1746",
        event_type=EventType.BIRTH,
        date="1746-11-18",
        description="Born 18 Nov 1746",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="stephen-longfellow-1746",
        event_type=EventType.MARRIAGE,
        description="Married Mary Pritchard",
        source=SOURCE_DOC,
    ))

    # ── John Longfellow (1781) ───────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="john-longfellow-1781",
        event_type=EventType.BIRTH,
        date="1781-08-02",
        description="Born 2 Aug 1781",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="john-longfellow-1781",
        event_type=EventType.MARRIAGE,
        date="1803-09-04",
        description="Married Lydia Brown, September 4, 1803",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="john-longfellow-1781",
        event_type=EventType.DEATH,
        date="1828-01-16",
        description="Died 16 Jan 1828",
        source=SOURCE_DOC,
    ))

    # ── Mildred Rena Longfellow ──────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="mildred-rena-longfellow-1885",
        event_type=EventType.RESIDENCE,
        place="Minneapolis, Hennepin County, Minnesota",
        description="Resided in Minneapolis, Hennepin County, Minnesota",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="mildred-rena-longfellow-1885",
        event_type=EventType.MARRIAGE,
        date="1905-11-20",
        description="First marriage to Dr. Lindley Ambrose Parkinson Sr.",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="mildred-rena-longfellow-1885",
        event_type=EventType.MARRIAGE,
        date="1934-01-09",
        description="Second marriage to Arthur R. Smith",
        source=SOURCE_DOC,
    ))

    # ── Mildred E. Parkinson ──────────────────────────────────────────
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

    # ── Sterling Thomas Walters Sr ───────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="sterling-walters-sr",
        event_type=EventType.RESIDENCE,
        date="1930-04-26",
        place="Belvidere, Jackson County, South Dakota",
        description="Appeared on 1930 census in Belvidere, Jackson County, South Dakota",
        source=SOURCE_DOC,
    ))

    # ── Helen May Hornsby ─────────────────────────────────────────────
    tree.add_event(LifeEvent(
        person_id="helen-may-hornsby",
        event_type=EventType.RESIDENCE,
        place="Anoka, Anoka County, Minnesota",
        description="Resided in Anoka, Anoka County, Minnesota",
        source=SOURCE_DOC,
    ))

    # ── Dr. Lindley Ambrose Parkinson Sr ─────────────────────────────
    tree.add_event(LifeEvent(
        person_id="lindley-parkinson-sr",
        event_type=EventType.CAREER,
        place="Minnesota",
        description="Physician (Dr.) in Minnesota",
        source=SOURCE_DOC,
    ))
    tree.add_event(LifeEvent(
        person_id="lindley-parkinson-sr",
        event_type=EventType.DEATH,
        date="1927-07-21",
        place="Wright, Carlton County, Minnesota",
        description="Died 21 Jul 1927 in Wright, Carlton County, MN. Buried Riverside Cemetery, Riverside, St. Louis County, MN.",
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
