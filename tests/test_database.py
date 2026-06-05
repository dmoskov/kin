"""Tests for the SQLite database layer.

Every test uses a fresh in-memory database (no file I/O, fast, isolated).
"""

import pytest

from database.connection import get_connection, init_db
from database.repository import TreeRepository
from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, Union
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


# ── Schema & Init ──────────────────────────────────────────────────────


class TestInit:
    def test_init_creates_tables(self, db_path):
        conn = get_connection(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        assert "people" in table_names
        assert "relationships" in table_names
        assert "unions" in table_names
        assert "events" in table_names
        assert "schema_version" in table_names
        conn.close()

    def test_init_records_schema_version(self, db_path):
        from database.schema import SCHEMA_VERSION

        conn = get_connection(db_path)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row["version"] == SCHEMA_VERSION
        conn.close()

    def test_init_is_idempotent(self, db_path):
        """Calling init_db twice doesn't fail or duplicate the version row."""
        init_db(db_path)
        conn = get_connection(db_path)
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        assert len(rows) == 1
        conn.close()

    def test_foreign_keys_enabled(self, db_path):
        conn = get_connection(db_path)
        fk = conn.execute("PRAGMA foreign_keys").fetchone()
        assert fk[0] == 1
        conn.close()


# ── Person CRUD ────────────────────────────────────────────────────────


class TestPersonCrud:
    def _make_person(self, **overrides):
        defaults = dict(
            id="alice",
            given_name="Alice",
            surname="Smith",
            gender=Gender.FEMALE,
            birth_date="1990-01-15",
            birth_place="Portland, OR",
            notes="Test person",
        )
        defaults.update(overrides)
        return Person(**defaults)

    def test_save_and_get(self, repo):
        person = self._make_person()
        repo.save_person(person)
        loaded = repo.get_person("alice")
        assert loaded is not None
        assert loaded.given_name == "Alice"
        assert loaded.surname == "Smith"
        assert loaded.gender == Gender.FEMALE
        assert loaded.birth_date == "1990-01-15"
        assert loaded.birth_place == "Portland, OR"
        assert loaded.notes == "Test person"

    def test_get_nonexistent_returns_none(self, repo):
        assert repo.get_person("nobody") is None

    def test_save_replaces_on_conflict(self, repo):
        repo.save_person(self._make_person(notes="version 1"))
        repo.save_person(self._make_person(notes="version 2"))
        loaded = repo.get_person("alice")
        assert loaded.notes == "version 2"

    def test_list_people(self, repo):
        repo.save_person(self._make_person(id="bob", given_name="Bob", surname="Jones"))
        repo.save_person(self._make_person(id="alice", given_name="Alice", surname="Smith"))
        people = repo.list_people()
        assert len(people) == 2
        # Should be sorted by surname
        assert people[0].surname == "Jones"
        assert people[1].surname == "Smith"

    def test_search_people(self, repo):
        repo.save_person(self._make_person(id="alice"))
        repo.save_person(self._make_person(id="bob", given_name="Bob", surname="Jones"))
        results = repo.search_people("Alice")
        assert len(results) == 1
        assert results[0].id == "alice"

    def test_search_case_insensitive(self, repo):
        repo.save_person(self._make_person())
        results = repo.search_people("alice")
        assert len(results) == 1

    def test_delete_person(self, repo):
        repo.save_person(self._make_person())
        assert repo.delete_person("alice") is True
        assert repo.get_person("alice") is None

    def test_delete_nonexistent_returns_false(self, repo):
        assert repo.delete_person("nobody") is False

    def test_nicknames_round_trip(self, repo):
        person = self._make_person(nicknames=["Ali", "A"])
        repo.save_person(person)
        loaded = repo.get_person("alice")
        assert loaded.nicknames == ["Ali", "A"]

    def test_photo_paths_sync_to_person_photos(self, repo):
        # The legacy people.photo_paths column was dropped (schema v20); setting
        # photo_paths on a saved Person now flows into person_photos via the
        # additive sync (this is the path JSON/GEDCOM import relies on).
        person = self._make_person(photo_paths=["photos/alice1.jpg"])
        repo.save_person(person)
        linked = {p["file_path"] for p in repo.photos_for_person("alice")}
        assert "photos/alice1.jpg" in linked

    def test_save_person_preserves_directly_assigned_photos(self, repo):
        """Regression: a photo linked via assign_photo_to_person (so it lives in
        person_photos but not in the legacy photo_paths list) must survive a
        later save_person. The old destructive sync rebuilt person_photos from
        photo_paths and silently deleted such links."""
        repo.save_person(self._make_person())
        photo_id = repo.get_or_create_photo("photos/portrait.jpg")
        repo.assign_photo_to_person("alice", photo_id, is_profile=True)

        # Edit an unrelated column — this used to wipe the person_photos link.
        person = repo.get_person("alice")
        person.notes = "edited"
        repo.save_person(person)

        linked = {p["file_path"] for p in repo.photos_for_person("alice")}
        assert "photos/portrait.jpg" in linked


# ── Relationships ──────────────────────────────────────────────────────


class TestRelationships:
    def test_save_relationship(self, repo):
        repo.save_person(Person(id="parent", given_name="P", surname="S"))
        repo.save_person(Person(id="child", given_name="C", surname="S"))
        rel = Relationship(parent_id="parent", child_id="child")
        repo.save_relationship(rel)
        tree = repo.load_tree()
        assert len(tree.relationships) == 1
        assert tree.relationships[0].parent_id == "parent"
        assert tree.relationships[0].child_id == "child"

    def test_duplicate_relationship_ignored(self, repo):
        repo.save_person(Person(id="parent", given_name="P", surname="S"))
        repo.save_person(Person(id="child", given_name="C", surname="S"))
        rel = Relationship(parent_id="parent", child_id="child")
        repo.save_relationship(rel)
        repo.save_relationship(rel)  # duplicate
        tree = repo.load_tree()
        assert len(tree.relationships) == 1

    def test_cascade_delete_removes_relationships(self, repo):
        repo.save_person(Person(id="parent", given_name="P", surname="S"))
        repo.save_person(Person(id="child", given_name="C", surname="S"))
        repo.save_relationship(Relationship(parent_id="parent", child_id="child"))
        repo.delete_person("parent")
        tree = repo.load_tree()
        assert len(tree.relationships) == 0


class TestSavePersonPreservesRelatedData:
    """Re-saving (editing) a person must not destroy their related rows.

    Regression for the SQLite INSERT OR REPLACE bug: with foreign_keys=ON, a
    delete-then-reinsert upsert cascade-deleted the person's relationships,
    unions, and events and reset created_at on every edit.
    """

    def test_editing_person_keeps_relationships_unions_events(self, repo):
        repo.save_person(Person(id="parent", given_name="P", surname="S"))
        repo.save_person(Person(id="child", given_name="C", surname="S"))
        repo.save_person(Person(id="spouse", given_name="Sp", surname="S"))
        repo.save_relationship(Relationship(parent_id="parent", child_id="child"))
        repo.save_union(Union(partner1_id="parent", partner2_id="spouse"))
        repo.save_event(LifeEvent(person_id="parent", event_type=EventType.CAREER, date="2010"))

        # Edit the parent (a routine update) and re-save.
        edited = repo.get_person("parent")
        edited.given_name = "Patricia"
        repo.save_person(edited)

        tree = repo.load_tree()
        assert edited.given_name == "Patricia"
        assert len(tree.relationships) == 1, "relationship cascade-deleted on edit"
        assert len(tree.unions) == 1, "union cascade-deleted on edit"
        assert len(tree.events) == 1, "event cascade-deleted on edit"

    def test_editing_person_preserves_created_at(self, repo):
        repo.save_person(Person(id="p", given_name="P", surname="S"))
        conn = get_connection(repo._db_path)
        original = conn.execute("SELECT created_at FROM people WHERE id = 'p'").fetchone()[
            "created_at"
        ]
        conn.close()

        edited = repo.get_person("p")
        edited.given_name = "Renamed"
        repo.save_person(edited)

        conn = get_connection(repo._db_path)
        after = conn.execute("SELECT created_at FROM people WHERE id = 'p'").fetchone()[
            "created_at"
        ]
        conn.close()
        assert after == original, "created_at was reset on edit"


# ── Unions ─────────────────────────────────────────────────────────────


class TestUnions:
    def test_save_and_load_union(self, repo):
        repo.save_person(Person(id="p1", given_name="A", surname="X"))
        repo.save_person(Person(id="p2", given_name="B", surname="Y"))
        union = Union(
            partner1_id="p1",
            partner2_id="p2",
            union_date="2020-06-15",
            union_place="SF",
            notes="Lovely wedding",
        )
        repo.save_union(union)
        tree = repo.load_tree()
        assert len(tree.unions) == 1
        u = tree.unions[0]
        assert u.partner1_id == "p1"
        assert u.partner2_id == "p2"
        assert u.union_date == "2020-06-15"
        assert u.union_place == "SF"
        assert u.notes == "Lovely wedding"


# ── Events ─────────────────────────────────────────────────────────────


class TestEvents:
    def test_save_and_load_event(self, repo):
        repo.save_person(Person(id="alice", given_name="A", surname="S"))
        event = LifeEvent(
            person_id="alice",
            event_type=EventType.CAREER,
            date="2015-03",
            place="NYC",
            description="Started new job",
            source="LinkedIn",
        )
        repo.save_event(event)
        tree = repo.load_tree()
        assert len(tree.events) == 1
        e = tree.events[0]
        assert e.person_id == "alice"
        assert e.event_type == EventType.CAREER
        assert e.description == "Started new job"


# ── Full Tree Round-Trip ───────────────────────────────────────────────


class TestTreeRoundTrip:
    def _build_family(self) -> FamilyTree:
        tree = FamilyTree()
        tree.add_person(
            Person(
                id="dad",
                given_name="Dad",
                surname="Smith",
                gender=Gender.MALE,
                birth_date="1960-01-01",
            )
        )
        tree.add_person(
            Person(
                id="mom",
                given_name="Mom",
                surname="Smith",
                gender=Gender.FEMALE,
                birth_date="1962-03-15",
                maiden_name="Jones",
            )
        )
        tree.add_person(
            Person(
                id="kid",
                given_name="Kid",
                surname="Smith",
                gender=Gender.MALE,
                birth_date="1990-07-20",
            )
        )
        tree.add_relationship(Relationship(parent_id="dad", child_id="kid"))
        tree.add_relationship(Relationship(parent_id="mom", child_id="kid"))
        tree.add_union(
            Union(
                partner1_id="dad",
                partner2_id="mom",
                union_date="1988-09-01",
                union_place="Boston",
            )
        )
        tree.add_event(
            LifeEvent(
                person_id="dad",
                event_type=EventType.CAREER,
                date="1985",
                description="First job",
            )
        )
        return tree

    def test_save_and_load_tree(self, repo):
        original = self._build_family()
        repo.save_tree(original)
        loaded = repo.load_tree()

        # People
        assert loaded.num_people == 3
        assert loaded.get_person("dad").given_name == "Dad"
        assert loaded.get_person("mom").maiden_name == "Jones"

        # Relationships
        assert len(loaded.relationships) == 2
        parents = loaded.parents_of("kid")
        parent_ids = {p.id for p in parents}
        assert parent_ids == {"dad", "mom"}

        # Unions
        assert len(loaded.unions) == 1
        assert loaded.unions[0].union_date == "1988-09-01"

        # Events
        assert len(loaded.events) == 1
        assert loaded.events[0].description == "First job"

    def test_round_trip_preserves_traversal(self, repo):
        """Graph traversal works identically after DB round-trip."""
        original = self._build_family()
        repo.save_tree(original)
        loaded = repo.load_tree()

        # Children query
        kids = loaded.children_of("dad")
        assert len(kids) == 1
        assert kids[0].id == "kid"

        # Partners query
        partners = loaded.partners_of("dad")
        assert len(partners) == 1
        assert partners[0].id == "mom"

        # Siblings (kid has no siblings)
        assert loaded.siblings_of("kid") == []

        # Generations
        assert loaded.generation_of("dad") == 0
        assert loaded.generation_of("mom") == 0
        assert loaded.generation_of("kid") == 1


# ── Stats ──────────────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty_db(self, repo):
        s = repo.stats()
        assert s["people"] == 0
        assert s["relationships"] == 0
        assert s["unions"] == 0
        assert s["events"] == 0
        assert s["living"] == 0
        assert s["deceased"] == 0

    def test_stats_with_data(self, repo):
        repo.save_person(
            Person(
                id="alive",
                given_name="A",
                surname="S",
            )
        )
        repo.save_person(
            Person(
                id="dead",
                given_name="D",
                surname="S",
                death_date="2020-01-01",
            )
        )
        s = repo.stats()
        assert s["people"] == 2
        assert s["living"] == 1
        assert s["deceased"] == 1
