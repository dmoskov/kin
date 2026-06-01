"""Tests for sources and citations (schema v2).

Covers source CRUD, citation CRUD, the tree round-trip with sources/citations,
and the migration script's source tag parsing.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from database.connection import init_db
from database.repository import TreeRepository
from models.citation import Citation, Confidence, EntityType
from models.person import Person
from models.source import Source, SourceType
from models.tree import FamilyTree


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database and return its path."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def repo(db_path):
    """Return a TreeRepository pointed at the temp database."""
    return TreeRepository(db_path)


def _make_source(**overrides):
    defaults = dict(
        id="test-source",
        name="Test Source",
        source_type=SourceType.DOCUMENT,
        author="Test Author",
        date="2024",
        description="A test source.",
    )
    defaults.update(overrides)
    return Source(**defaults)


def _make_citation(**overrides):
    defaults = dict(
        source_id="test-source",
        entity_type=EntityType.PERSON,
        entity_id="alice",
        field_name=None,
        excerpt="",
        confidence=Confidence.CONFIRMED,
        notes="",
    )
    defaults.update(overrides)
    return Citation(**defaults)


# ── Schema ──────────────────────────────────────────────────────────────


class TestSchemaV2:
    def test_sources_table_exists(self, db_path):
        from database.connection import get_connection

        conn = get_connection(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t["name"] for t in tables}
        assert "sources" in table_names
        assert "citations" in table_names
        conn.close()


# ── Source CRUD ─────────────────────────────────────────────────────────


class TestSourceCrud:
    def test_save_and_get(self, repo):
        source = _make_source()
        repo.save_source(source)
        loaded = repo.get_source("test-source")
        assert loaded is not None
        assert loaded.name == "Test Source"
        assert loaded.source_type == SourceType.DOCUMENT
        assert loaded.author == "Test Author"

    def test_get_nonexistent_returns_none(self, repo):
        assert repo.get_source("nonexistent") is None

    def test_save_replaces_on_conflict(self, repo):
        repo.save_source(_make_source(description="v1"))
        repo.save_source(_make_source(description="v2"))
        loaded = repo.get_source("test-source")
        assert loaded.description == "v2"

    def test_list_sources(self, repo):
        repo.save_source(_make_source(id="b-source", name="B Source"))
        repo.save_source(_make_source(id="a-source", name="A Source"))
        sources = repo.list_sources()
        assert len(sources) == 2
        assert sources[0].name == "A Source"  # sorted by name

    def test_source_url_round_trip(self, repo):
        repo.save_source(_make_source(url="https://example.com"))
        loaded = repo.get_source("test-source")
        assert loaded.url == "https://example.com"


# ── Citation CRUD ───────────────────────────────────────────────────────


class TestCitationCrud:
    def test_save_and_fetch(self, repo):
        repo.save_source(_make_source())
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        repo.save_citation(_make_citation())

        cites = repo.citations_for(EntityType.PERSON, "alice")
        assert len(cites) == 1
        assert cites[0].source_id == "test-source"
        assert cites[0].entity_type == EntityType.PERSON

    def test_citations_with_field_filter(self, repo):
        repo.save_source(_make_source())
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        repo.save_citation(_make_citation(field_name="birth_date"))
        repo.save_citation(_make_citation(field_name="death_date"))
        repo.save_citation(_make_citation(field_name=None))  # general

        birth_cites = repo.citations_for(EntityType.PERSON, "alice", "birth_date")
        assert len(birth_cites) == 1

        all_cites = repo.citations_for(EntityType.PERSON, "alice")
        assert len(all_cites) == 3

    def test_citations_by_source(self, repo):
        repo.save_source(_make_source())
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        repo.save_person(Person(id="bob", given_name="B", surname="S"))
        repo.save_citation(_make_citation(entity_id="alice"))
        repo.save_citation(_make_citation(entity_id="bob"))

        cites = repo.citations_by_source("test-source")
        assert len(cites) == 2

    def test_confidence_levels(self, repo):
        repo.save_source(_make_source())
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        repo.save_citation(_make_citation(confidence=Confidence.UNCERTAIN))

        cites = repo.citations_for(EntityType.PERSON, "alice")
        assert cites[0].confidence == Confidence.UNCERTAIN

    def test_citation_excerpt(self, repo):
        repo.save_source(_make_source())
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        repo.save_citation(_make_citation(excerpt="Born in 1948"))

        cites = repo.citations_for(EntityType.PERSON, "alice")
        assert cites[0].excerpt == "Born in 1948"


# ── Tree Round-Trip with Sources ────────────────────────────────────────


class TestTreeWithSources:
    def test_save_and_load_tree_with_sources(self, repo):
        tree = FamilyTree()
        tree.add_person(Person(id="alice", given_name="A", surname="S"))
        tree.add_source(_make_source())
        tree.add_citation(_make_citation())

        repo.save_tree(tree)
        loaded = repo.load_tree()

        assert len(loaded.sources) == 1
        assert "test-source" in loaded.sources
        assert loaded.sources["test-source"].name == "Test Source"
        assert len(loaded.citations) == 1
        assert loaded.citations[0].source_id == "test-source"

    def test_tree_citations_for(self):
        tree = FamilyTree()
        tree.add_person(Person(id="alice", given_name="A", surname="S"))
        tree.add_citation(_make_citation(entity_id="alice"))
        tree.add_citation(_make_citation(entity_id="bob"))

        alice_cites = tree.citations_for(EntityType.PERSON, "alice")
        assert len(alice_cites) == 1

    def test_tree_source_ids_for_person(self):
        tree = FamilyTree()
        tree.add_citation(
            Citation(
                source_id="src-a",
                entity_type=EntityType.PERSON,
                entity_id="alice",
            )
        )
        tree.add_citation(
            Citation(
                source_id="src-b",
                entity_type=EntityType.PERSON,
                entity_id="alice",
            )
        )
        tree.add_citation(
            Citation(
                source_id="src-a",
                entity_type=EntityType.PERSON,
                entity_id="bob",
            )
        )

        assert tree.source_ids_for_person("alice") == {"src-a", "src-b"}
        assert tree.source_ids_for_person("bob") == {"src-a"}


# ── Stats ───────────────────────────────────────────────────────────────


class TestStatsV2:
    def test_stats_include_sources_and_citations(self, repo):
        repo.save_source(_make_source())
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        repo.save_citation(_make_citation())

        s = repo.stats()
        assert s["sources"] == 1
        assert s["citations"] == 1


# ── Migration Source Tag Parsing ────────────────────────────────────────


class TestSourceTagParsing:
    def test_parse_single_source(self):
        from import_export.json_io import parse_source_tags

        source_ids, cleaned = parse_source_tags("Some biographical info. Source: Golden Book.")
        assert "golden-book" in source_ids
        assert "Source:" not in cleaned
        assert cleaned == "Some biographical info."

    def test_parse_multiple_sources(self):
        from import_export.json_io import parse_source_tags

        source_ids, cleaned = parse_source_tags(
            "Wolf's father. Source: Golden Book, Herb's letter, fan chart."
        )
        assert "golden-book" in source_ids
        assert "herb-letter" in source_ids
        assert "fan-chart-2016" in source_ids
        assert len(source_ids) == 3

    def test_parse_no_source(self):
        from import_export.json_io import parse_source_tags

        source_ids, cleaned = parse_source_tags("Just some notes without a source reference.")
        assert source_ids == []
        assert cleaned == "Just some notes without a source reference."

    def test_parse_with_and_connector(self):
        from import_export.json_io import parse_source_tags

        source_ids, _ = parse_source_tags("Some info. Source: fan chart and Wikipedia.")
        assert "fan-chart-2016" in source_ids
        assert "wikipedia" in source_ids
