"""Tests for the DB-backed undo feature.

Covers:
  - push_undo / pop_undo / peek_undo / undo_count (repo layer)
  - Pruning to the stack limit
  - Snapshot-then-delete: person, relationships, unions, events all restored
  - POST /api/undo restores everything via the Flask test client
  - GET /api/undo/status reflects current stack depth
  - Empty stack returns {"restored": null}

Uses the same ``app_client`` fixture pattern as test_web_people_crud.py.
"""

from __future__ import annotations

import pytest

from database.connection import init_db
from database.repository import TreeRepository
from models.event import EventType, LifeEvent
from models.person import Gender, Person
from models.relationship import Relationship, RelationshipType, Union

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "undo_test.db")
    init_db(path)
    return path


@pytest.fixture
def repo(db_path):
    return TreeRepository(db_path)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Fresh SQLite DB + Flask test client."""
    db_path = str(tmp_path / "undo_web_test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)

    init_db(db_path)

    import importlib

    import web_server

    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True

    repo = TreeRepository(db_path)
    with web_server.app.test_client() as client:
        yield client, repo


# ── Repository-level undo tests ──────────────────────────────────────────


class TestUndoRepo:
    def test_push_and_pop(self, repo):
        repo.push_undo("delete_person", {"id": "p1", "given_name": "Alice"})
        entry = repo.pop_undo()
        assert entry is not None
        assert entry["kind"] == "delete_person"
        assert entry["payload"]["id"] == "p1"

    def test_pop_empty_returns_none(self, repo):
        assert repo.pop_undo() is None

    def test_peek_does_not_remove(self, repo):
        repo.push_undo("delete_person", {"id": "p2"})
        peeked = repo.peek_undo()
        assert peeked is not None
        assert peeked["payload"]["id"] == "p2"
        # Still there after peek
        assert repo.undo_count() == 1

    def test_undo_count(self, repo):
        assert repo.undo_count() == 0
        repo.push_undo("delete_person", {"x": 1})
        assert repo.undo_count() == 1
        repo.push_undo("delete_person", {"x": 2})
        assert repo.undo_count() == 2
        repo.pop_undo()
        assert repo.undo_count() == 1

    def test_lifo_order(self, repo):
        repo.push_undo("delete_person", {"seq": 1})
        repo.push_undo("delete_person", {"seq": 2})
        repo.push_undo("delete_person", {"seq": 3})
        assert repo.pop_undo()["payload"]["seq"] == 3
        assert repo.pop_undo()["payload"]["seq"] == 2
        assert repo.pop_undo()["payload"]["seq"] == 1

    def test_pruning_at_limit(self, repo):
        from database.repository._undo import _UNDO_STACK_LIMIT

        for i in range(_UNDO_STACK_LIMIT + 5):
            repo.push_undo("delete_person", {"seq": i})
        assert repo.undo_count() == _UNDO_STACK_LIMIT


# ── End-to-end via Flask test client ────────────────────────────────────


class TestUndoEndpoints:
    def _seed_person_with_edges(self, repo):
        """Create a person with one relationship, one union, and one event."""
        alice = Person(id="alice", given_name="Alice", surname="Smith", gender=Gender.FEMALE)
        bob = Person(id="bob", given_name="Bob", surname="Smith", gender=Gender.MALE)
        child = Person(id="child1", given_name="Carol", surname="Smith", gender=Gender.FEMALE)
        repo.save_person(alice)
        repo.save_person(bob)
        repo.save_person(child)

        # Relationship: alice → child1
        repo.save_relationship(
            Relationship(parent_id="alice", child_id="child1", rel_type=RelationshipType.BIOLOGICAL)
        )
        # Union: alice ↔ bob
        repo.save_union(Union(partner1_id="alice", partner2_id="bob"))
        # Event on alice
        repo.save_event(
            LifeEvent(
                person_id="alice",
                event_type=EventType.BIRTH,
                date="1980-01-15",
                place="Springfield",
            )
        )
        return alice

    def test_status_empty_stack(self, app_client):
        client, repo = app_client
        resp = client.get("/api/undo/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["available"] is False
        assert data["count"] == 0

    def test_status_after_push(self, app_client):
        client, repo = app_client
        repo.push_undo("delete_person", {"id": "x"})
        resp = client.get("/api/undo/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["available"] is True
        assert data["count"] == 1

    def test_undo_empty_returns_null(self, app_client):
        client, repo = app_client
        resp = client.post("/api/undo")
        assert resp.status_code == 200
        assert resp.get_json()["restored"] is None

    def test_delete_then_undo_restores_person(self, app_client):
        client, repo = app_client
        self._seed_person_with_edges(repo)

        # Delete alice via the API
        del_resp = client.delete("/api/people/alice")
        assert del_resp.status_code == 204

        # alice should be gone
        assert repo.get_person("alice") is None

        # Stack should have one entry
        assert repo.undo_count() == 1

        # Undo
        undo_resp = client.post("/api/undo")
        assert undo_resp.status_code == 200
        body = undo_resp.get_json()
        assert body["restored"] == "delete_person"
        assert body["person_id"] == "alice"
        assert "Alice" in body["name"]

        # alice is back
        restored = repo.get_person("alice")
        assert restored is not None
        assert restored.given_name == "Alice"
        assert restored.surname == "Smith"

    def test_undo_restores_relationships(self, app_client):
        client, repo = app_client
        self._seed_person_with_edges(repo)

        tree_before = repo.load_tree()
        rels_before = [r for r in tree_before.relationships if r.parent_id == "alice"]
        assert len(rels_before) == 1

        client.delete("/api/people/alice")
        tree_mid = repo.load_tree()
        assert not any(
            r.parent_id == "alice" or r.child_id == "alice" for r in tree_mid.relationships
        )

        client.post("/api/undo")

        tree_after = repo.load_tree()
        rels_after = [r for r in tree_after.relationships if r.parent_id == "alice"]
        assert len(rels_after) == 1
        assert rels_after[0].child_id == "child1"

    def test_undo_restores_unions(self, app_client):
        client, repo = app_client
        self._seed_person_with_edges(repo)

        client.delete("/api/people/alice")
        tree_mid = repo.load_tree()
        assert not any(
            u.partner1_id == "alice" or u.partner2_id == "alice" for u in tree_mid.unions
        )

        client.post("/api/undo")

        tree_after = repo.load_tree()
        unions = [u for u in tree_after.unions if "alice" in (u.partner1_id, u.partner2_id)]
        assert len(unions) == 1
        assert set([unions[0].partner1_id, unions[0].partner2_id]) == {"alice", "bob"}

    def test_undo_restores_events(self, app_client):
        client, repo = app_client
        self._seed_person_with_edges(repo)

        client.delete("/api/people/alice")
        tree_mid = repo.load_tree()
        assert not any(e.person_id == "alice" for e in tree_mid.events)

        client.post("/api/undo")

        tree_after = repo.load_tree()
        events = [e for e in tree_after.events if e.person_id == "alice"]
        assert len(events) == 1
        assert events[0].event_type == EventType.BIRTH
        assert events[0].date == "1980-01-15"
        assert events[0].place == "Springfield"

    def test_stack_empty_after_undo(self, app_client):
        client, repo = app_client
        self._seed_person_with_edges(repo)
        client.delete("/api/people/alice")
        client.post("/api/undo")
        assert repo.undo_count() == 0

    def test_undo_status_reflected_in_api(self, app_client):
        client, repo = app_client
        self._seed_person_with_edges(repo)

        assert client.get("/api/undo/status").get_json()["available"] is False

        client.delete("/api/people/alice")
        assert client.get("/api/undo/status").get_json()["available"] is True

        client.post("/api/undo")
        assert client.get("/api/undo/status").get_json()["available"] is False
