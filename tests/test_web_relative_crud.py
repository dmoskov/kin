"""Tests for the add-relative endpoints.

Covers:
  - POST /api/relationships — create parent-child relationship (happy path,
    missing fields, 404 for unknown parent or child).
  - PATCH /api/relationships — edit rel_type/visibility (happy path, persist,
    missing ids, 404, invalid value, nothing-to-update).
  - DELETE /api/relationships — remove a link (happy path, persist, missing
    ids, 404).
  - POST /api/unions — create partnership (happy path, missing fields, 404
    for unknown partner).
  - PATCH /api/people/<id> — edit person details from the panel (name, gender,
    birth/death dates and places, clear-to-null). Already partially covered
    by test_web_people_crud.py; tests here focus on the fields exposed by the
    edit form (birth_place, death_date, death_place).

All tests use the same hermetic ``app_client`` fixture pattern as the other
web test modules.
"""

from __future__ import annotations

import pytest

from models.person import Gender, Person


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)

    from database.connection import init_db

    init_db(db_path)

    import importlib

    import web_server

    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True

    from database.repository import TreeRepository

    repo = TreeRepository(db_path)

    repo.save_person(Person(id="parent1", given_name="Alice", surname="Test", gender=Gender.FEMALE))
    repo.save_person(Person(id="child1", given_name="Bob", surname="Test", gender=Gender.MALE))
    repo.save_person(
        Person(id="partner1", given_name="Carol", surname="Test", gender=Gender.FEMALE)
    )

    with web_server.app.test_client() as client:
        yield client, repo, tmp_path


# ── POST /api/relationships ──────────────────────────────────────────────


class TestCreateRelationship:
    def test_happy_path(self, app_client):
        client, repo, _ = app_client
        resp = client.post(
            "/api/relationships",
            json={
                "parent_id": "parent1",
                "child_id": "child1",
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["parent_id"] == "parent1"
        assert body["child_id"] == "child1"

    def test_relationship_persists_in_api_data(self, app_client):
        client, _, _ = app_client
        client.post("/api/relationships", json={"parent_id": "parent1", "child_id": "child1"})
        data = client.get("/api/data").get_json()
        rels = data["relationships"]
        assert any(r["parent_id"] == "parent1" and r["child_id"] == "child1" for r in rels)

    def test_missing_parent_id(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/relationships", json={"child_id": "child1"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_missing_child_id(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/relationships", json={"parent_id": "parent1"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_missing_both_fields(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/relationships", json={})
        assert resp.status_code == 400

    def test_unknown_parent_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/relationships",
            json={
                "parent_id": "does-not-exist",
                "child_id": "child1",
            },
        )
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_unknown_child_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/relationships",
            json={
                "parent_id": "parent1",
                "child_id": "does-not-exist",
            },
        )
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_empty_body(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/relationships", data="", content_type="application/json")
        assert resp.status_code == 400

    def test_self_parent_rejected(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/relationships",
            json={
                "parent_id": "parent1",
                "child_id": "parent1",
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"


# ── PATCH /api/relationships ─────────────────────────────────────────────


class TestUpdateRelationship:
    def _create(self, client):
        client.post("/api/relationships", json={"parent_id": "parent1", "child_id": "child1"})

    def test_happy_path(self, app_client):
        client, _, _ = app_client
        self._create(client)
        resp = client.patch(
            "/api/relationships",
            json={
                "parent_id": "parent1",
                "child_id": "child1",
                "rel_type": "adoptive",
                "visibility": "extended",
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)

    def test_update_persists_in_api_data(self, app_client):
        client, _, _ = app_client
        self._create(client)
        client.patch(
            "/api/relationships",
            json={
                "parent_id": "parent1",
                "child_id": "child1",
                "rel_type": "adoptive",
                "visibility": "extended",
            },
        )
        rels = client.get("/api/data").get_json()["relationships"]
        rel = next(r for r in rels if r["parent_id"] == "parent1" and r["child_id"] == "child1")
        assert rel["rel_type"] == "adoptive"
        assert rel["visibility"] == "extended"

    def test_missing_ids(self, app_client):
        client, _, _ = app_client
        resp = client.patch("/api/relationships", json={"rel_type": "step"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_unknown_relationship_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.patch(
            "/api/relationships",
            json={"parent_id": "parent1", "child_id": "child1", "rel_type": "step"},
        )
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_invalid_rel_type_rejected(self, app_client):
        client, _, _ = app_client
        self._create(client)
        resp = client.patch(
            "/api/relationships",
            json={"parent_id": "parent1", "child_id": "child1", "rel_type": "bogus"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_nothing_to_update_rejected(self, app_client):
        client, _, _ = app_client
        self._create(client)
        resp = client.patch(
            "/api/relationships",
            json={"parent_id": "parent1", "child_id": "child1"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"


# ── DELETE /api/relationships ────────────────────────────────────────────


class TestDeleteRelationship:
    def _create(self, client):
        client.post("/api/relationships", json={"parent_id": "parent1", "child_id": "child1"})

    def test_happy_path(self, app_client):
        client, _, _ = app_client
        self._create(client)
        resp = client.delete(
            "/api/relationships",
            json={"parent_id": "parent1", "child_id": "child1"},
        )
        assert resp.status_code == 204, resp.get_data(as_text=True)

    def test_delete_removes_from_api_data(self, app_client):
        client, _, _ = app_client
        self._create(client)
        client.delete("/api/relationships", json={"parent_id": "parent1", "child_id": "child1"})
        rels = client.get("/api/data").get_json()["relationships"]
        assert not any(r["parent_id"] == "parent1" and r["child_id"] == "child1" for r in rels)

    def test_missing_ids(self, app_client):
        client, _, _ = app_client
        resp = client.delete("/api/relationships", json={"parent_id": "parent1"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_unknown_relationship_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.delete(
            "/api/relationships",
            json={"parent_id": "parent1", "child_id": "child1"},
        )
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"


# ── POST /api/unions ─────────────────────────────────────────────────────


class TestCreateUnion:
    def test_happy_path(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/unions",
            json={
                "partner1_id": "parent1",
                "partner2_id": "partner1",
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["partner1_id"] == "parent1"
        assert body["partner2_id"] == "partner1"

    def test_union_persists_in_api_data(self, app_client):
        client, _, _ = app_client
        client.post("/api/unions", json={"partner1_id": "parent1", "partner2_id": "partner1"})
        data = client.get("/api/data").get_json()
        unions = data["unions"]
        assert any(
            (u["partner1_id"] == "parent1" and u["partner2_id"] == "partner1")
            or (u["partner1_id"] == "partner1" and u["partner2_id"] == "parent1")
            for u in unions
        )

    def test_missing_partner1_id(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/unions", json={"partner2_id": "partner1"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_missing_partner2_id(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/unions", json={"partner1_id": "parent1"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_unknown_partner1_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/unions",
            json={
                "partner1_id": "does-not-exist",
                "partner2_id": "partner1",
            },
        )
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_unknown_partner2_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/unions",
            json={
                "partner1_id": "parent1",
                "partner2_id": "does-not-exist",
            },
        )
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_empty_body(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/unions", data="", content_type="application/json")
        assert resp.status_code == 400

    def test_self_union_rejected(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/unions",
            json={
                "partner1_id": "parent1",
                "partner2_id": "parent1",
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"


# ── PATCH /api/people/<id> (edit person form) ────────────────────────────


class TestEditPerson:
    def test_update_birth_and_death_dates(self, app_client):
        client, repo, _ = app_client
        resp = client.patch(
            "/api/people/parent1",
            json={
                "birth_date": "1940-06-15",
                "death_date": "2010-11-03",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["birth_date"] == "1940-06-15"
        assert body["death_date"] == "2010-11-03"

    def test_update_birth_and_death_places(self, app_client):
        client, _, _ = app_client
        resp = client.patch(
            "/api/people/parent1",
            json={
                "birth_place": "Toronto, Canada",
                "death_place": "New York, NY",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["birth_place"] == "Toronto, Canada"
        assert body["death_place"] == "New York, NY"

    def test_update_name(self, app_client):
        client, _, _ = app_client
        resp = client.patch(
            "/api/people/parent1",
            json={
                "given_name": "Alicia",
                "surname": "Smith",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["given_name"] == "Alicia"
        assert body["surname"] == "Smith"

    def test_update_gender(self, app_client):
        client, _, _ = app_client
        resp = client.patch("/api/people/parent1", json={"gender": "male"})
        assert resp.status_code == 200
        assert resp.get_json()["gender"] == "male"

    def test_clear_death_date_to_null(self, app_client):
        client, _, _ = app_client
        client.patch("/api/people/parent1", json={"death_date": "2000"})
        resp = client.patch("/api/people/parent1", json={"death_date": None})
        assert resp.status_code == 200
        # API omits null fields from the response
        assert resp.get_json().get("death_date") is None

    def test_partial_update_does_not_clobber_other_fields(self, app_client):
        client, _, _ = app_client
        client.patch("/api/people/parent1", json={"birth_date": "1940"})
        resp = client.patch("/api/people/parent1", json={"death_date": "2010"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["birth_date"] == "1940"
        assert body["death_date"] == "2010"

    def test_edit_shows_up_in_api_data(self, app_client):
        client, _, _ = app_client
        client.patch("/api/people/parent1", json={"birth_place": "Montreal"})
        data = client.get("/api/data").get_json()
        person = next(p for p in data["people"] if p["id"] == "parent1")
        assert person["birth_place"] == "Montreal"

    def test_unknown_person_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.patch("/api/people/does-not-exist", json={"given_name": "Ghost"})
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_partial_date_accepted(self, app_client):
        client, _, _ = app_client
        resp = client.patch("/api/people/parent1", json={"birth_date": "1940"})
        assert resp.status_code == 200
        assert resp.get_json()["birth_date"] == "1940"


# ── GET /api/people/search ──────────────────────────────────────────────


class TestSearchPeople:
    def test_search_by_given_name(self, app_client):
        client, _, _ = app_client
        resp = client.get("/api/people/search?q=Alice")
        assert resp.status_code == 200
        results = resp.get_json()
        assert len(results) >= 1
        assert any(p["given_name"] == "Alice" for p in results)

    def test_search_by_surname(self, app_client):
        client, _, _ = app_client
        resp = client.get("/api/people/search?q=Test")
        assert resp.status_code == 200
        results = resp.get_json()
        assert len(results) == 3

    def test_search_partial_match(self, app_client):
        client, _, _ = app_client
        resp = client.get("/api/people/search?q=Bo")
        assert resp.status_code == 200
        results = resp.get_json()
        assert any(p["given_name"] == "Bob" for p in results)

    def test_search_empty_query(self, app_client):
        client, _, _ = app_client
        resp = client.get("/api/people/search?q=")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_search_no_query_param(self, app_client):
        client, _, _ = app_client
        resp = client.get("/api/people/search")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_search_no_matches(self, app_client):
        client, _, _ = app_client
        resp = client.get("/api/people/search?q=Zzzznotexist")
        assert resp.status_code == 200
        assert resp.get_json() == []
