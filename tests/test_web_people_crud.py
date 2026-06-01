"""Tests for the in-browser person CRUD endpoints.

Covers:
  - POST /api/people — create (happy path, id auto-gen, explicit id, conflict,
    validation errors, gender normalization, date-format validation).
  - PUT/PATCH /api/people/<id> — partial updates, clear-to-null, unknown
    fields ignored, 404 for missing person.
  - DELETE /api/people/<id> — 204 success, 404 for missing, cascades through
    relationships (schema-level FK ON DELETE CASCADE).
  - Round-trip: create → GET /api/data shows the person → update → delete
    removes them from /api/data.

All tests use a temporary SQLite database via the ``app_client`` fixture,
mirroring the pattern in test_web_uploads.py so they're hermetic and fast.
"""

from __future__ import annotations

import pytest

from models.person import Gender, Person


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Fresh SQLite DB + Flask test client with a few seeded people.

    Seeds ``p1`` (Alice) and ``p2`` (Bob) so tests that need someone to
    update/delete/reference don't each have to re-create them.
    """
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

    repo.save_person(Person(id="p1", given_name="Alice", surname="Test", gender=Gender.FEMALE))
    repo.save_person(Person(id="p2", given_name="Bob", surname="Test", gender=Gender.MALE))

    with web_server.app.test_client() as client:
        yield client, repo, tmp_path


# ── POST /api/people ─────────────────────────────────────────────────────


class TestCreatePerson:
    def test_happy_path_auto_id(self, app_client):
        client, repo, _ = app_client
        resp = client.post(
            "/api/people",
            json={
                "given_name": "Carol",
                "surname": "Hughes",
                "gender": "female",
                "birth_date": "1950-03-14",
                "birth_place": "Dallas, TX",
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["given_name"] == "Carol"
        assert body["surname"] == "Hughes"
        assert body["gender"] == "female"
        assert body["birth_date"] == "1950-03-14"
        # Auto-generated id should be a non-empty string that persists.
        assert body["id"]
        assert repo.get_person(body["id"]) is not None

    def test_explicit_id_is_honored(self, app_client):
        client, repo, _ = app_client
        resp = client.post(
            "/api/people",
            json={
                "id": "custom_id_123",
                "given_name": "Dana",
                "surname": "X",
            },
        )
        assert resp.status_code == 201
        assert resp.get_json()["id"] == "custom_id_123"
        assert repo.get_person("custom_id_123") is not None

    def test_surname_only_is_allowed(self, app_client):
        """A surname alone is enough — some ancestors only have a family name."""
        client, _, _ = app_client
        resp = client.post("/api/people", json={"surname": "Unknown"})
        assert resp.status_code == 201
        assert resp.get_json()["surname"] == "Unknown"

    def test_given_name_only_is_allowed(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"given_name": "Grandma"})
        assert resp.status_code == 201

    def test_empty_birth_date_accepted(self, app_client):
        """Birth dates are often unknown in genealogy — empty must not 500."""
        client, repo, _ = app_client
        for payload in [
            {"given_name": "NoBirth1", "birth_date": ""},
            {"given_name": "NoBirth2", "birth_date": None},
            {"given_name": "NoBirth3"},
        ]:
            resp = client.post("/api/people", json=payload)
            assert resp.status_code == 201, f"Failed for {payload}: {resp.get_data(as_text=True)}"
            body = resp.get_json()
            assert "birth_date" not in body or body["birth_date"] is None
            person = repo.get_person(body["id"])
            assert person.birth_date is None

    def test_requires_at_least_one_name(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"birth_date": "1900"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_empty_body_rejected(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={})
        assert resp.status_code == 400

    def test_non_dict_body_rejected(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json=["not", "a", "dict"])
        assert resp.status_code == 400
        assert "object" in resp.get_json()["error"]

    def test_conflict_on_duplicate_id(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"id": "p1", "given_name": "Alice"})
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "conflict"

    def test_invalid_gender_rejected(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"given_name": "Eve", "gender": "alien"})
        assert resp.status_code == 400
        assert "gender" in resp.get_json()["error"]

    def test_missing_gender_defaults_to_unknown(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"given_name": "Frank"})
        assert resp.status_code == 201
        # Unknown gender is omitted from dict by json_io — so absence is fine.
        body = resp.get_json()
        assert body.get("gender", "unknown") in ("unknown", None)

    def test_invalid_date_format_rejected(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"given_name": "Gus", "birth_date": "March 1950"})
        assert resp.status_code == 400
        assert "birth_date" in resp.get_json()["error"]

    @pytest.mark.parametrize("date", ["1900", "1900-06", "1900-06-15"])
    def test_partial_dates_accepted(self, app_client, date):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"given_name": "H", "birth_date": date})
        assert resp.status_code == 201

    def test_nicknames_must_be_list_of_strings(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/people", json={"given_name": "Ivy", "nicknames": "just a string"})
        assert resp.status_code == 400

    def test_nicknames_list_stored(self, app_client):
        client, repo, _ = app_client
        resp = client.post("/api/people", json={"given_name": "Jo", "nicknames": ["Jo-Jo", "Jojo"]})
        assert resp.status_code == 201
        pid = resp.get_json()["id"]
        assert repo.get_person(pid).nicknames == ["Jo-Jo", "Jojo"]

    def test_unknown_fields_are_ignored(self, app_client):
        """Forward compatibility — extra fields shouldn't 400."""
        client, _, _ = app_client
        resp = client.post(
            "/api/people",
            json={"given_name": "K", "favorite_color": "blue", "__proto__": "bad"},
        )
        assert resp.status_code == 201
        assert "favorite_color" not in resp.get_json()

    def test_whitespace_trimmed(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/people",
            json={
                "given_name": "  Liam  ",
                "surname": "  Smith\n",
            },
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["given_name"] == "Liam"
        assert body["surname"] == "Smith"


# ── PUT /api/people/<id> ─────────────────────────────────────────────────


class TestUpdatePerson:
    def test_happy_path(self, app_client):
        client, repo, _ = app_client
        resp = client.put(
            "/api/people/p1",
            json={
                "given_name": "Alicia",
                "birth_date": "1985-01-01",
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["given_name"] == "Alicia"
        assert body["birth_date"] == "1985-01-01"
        # Surname was not included — must not be clobbered.
        assert body["surname"] == "Test"

    def test_patch_is_partial(self, app_client):
        client, repo, _ = app_client
        # Set a value, then update only one unrelated field.
        client.put("/api/people/p1", json={"notes": "some notes"})
        client.put("/api/people/p1", json={"given_name": "Alicia2"})
        p = repo.get_person("p1")
        assert p.notes == "some notes"
        assert p.given_name == "Alicia2"

    def test_clear_optional_field_with_null(self, app_client):
        client, repo, _ = app_client
        client.put("/api/people/p1", json={"birth_place": "Somewhere"})
        assert repo.get_person("p1").birth_place == "Somewhere"
        client.put("/api/people/p1", json={"birth_place": None})
        assert repo.get_person("p1").birth_place is None

    def test_clear_optional_field_with_empty_string(self, app_client):
        client, repo, _ = app_client
        client.put("/api/people/p1", json={"birth_place": "X"})
        client.put("/api/people/p1", json={"birth_place": ""})
        assert repo.get_person("p1").birth_place is None

    def test_clear_birth_date_with_empty_string(self, app_client):
        """Clearing a birth date via the edit form must not 500."""
        client, repo, _ = app_client
        client.put("/api/people/p1", json={"birth_date": "1985-01-01"})
        assert repo.get_person("p1").birth_date == "1985-01-01"
        resp = client.patch("/api/people/p1", json={"birth_date": ""})
        assert resp.status_code == 200
        assert repo.get_person("p1").birth_date is None

    def test_clear_birth_date_with_null(self, app_client):
        """Clearing a birth date by sending null must not 500."""
        client, repo, _ = app_client
        client.put("/api/people/p1", json={"birth_date": "1985-01-01"})
        resp = client.patch("/api/people/p1", json={"birth_date": None})
        assert resp.status_code == 200
        assert repo.get_person("p1").birth_date is None

    def test_gender_change(self, app_client):
        client, repo, _ = app_client
        resp = client.put("/api/people/p1", json={"gender": "other"})
        assert resp.status_code == 200
        assert repo.get_person("p1").gender == Gender.OTHER

    def test_404_for_missing(self, app_client):
        client, _, _ = app_client
        resp = client.put("/api/people/does_not_exist", json={"given_name": "Z"})
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_invalid_date_rejected(self, app_client):
        client, _, _ = app_client
        resp = client.put("/api/people/p1", json={"death_date": "yesterday"})
        assert resp.status_code == 400

    def test_patch_method_works_too(self, app_client):
        client, _, _ = app_client
        resp = client.patch("/api/people/p1", json={"notes": "via PATCH"})
        assert resp.status_code == 200
        assert resp.get_json()["notes"] == "via PATCH"

    def test_id_field_in_body_is_ignored(self, app_client):
        """Client can't rename a person by slipping an id into the body."""
        client, repo, _ = app_client
        resp = client.put("/api/people/p1", json={"id": "p999", "given_name": "A"})
        assert resp.status_code == 200
        assert repo.get_person("p1") is not None
        assert repo.get_person("p999") is None


# ── DELETE /api/people/<id> ──────────────────────────────────────────────


class TestDeletePerson:
    def test_happy_path(self, app_client):
        client, repo, _ = app_client
        resp = client.delete("/api/people/p1")
        assert resp.status_code == 204
        assert resp.get_data() == b""
        assert repo.get_person("p1") is None

    def test_404_for_missing(self, app_client):
        client, _, _ = app_client
        resp = client.delete("/api/people/nonexistent")
        assert resp.status_code == 404

    def test_second_delete_returns_404(self, app_client):
        client, _, _ = app_client
        assert client.delete("/api/people/p1").status_code == 204
        assert client.delete("/api/people/p1").status_code == 404

    def test_cascades_relationships(self, app_client):
        """Deleting a person should remove their relationships too — the
        FK is declared ON DELETE CASCADE in schema.py."""
        client, repo, _ = app_client
        from models.relationship import Relationship, RelationshipType

        repo.save_relationship(
            Relationship(
                parent_id="p1",
                child_id="p2",
                rel_type=RelationshipType.BIOLOGICAL,
            )
        )
        tree_before = repo.load_tree()
        assert any(r.parent_id == "p1" and r.child_id == "p2" for r in tree_before.relationships)

        resp = client.delete("/api/people/p1")
        assert resp.status_code == 204

        tree_after = repo.load_tree()
        assert not any(r.parent_id == "p1" or r.child_id == "p1" for r in tree_after.relationships)


# ── Round-trips via /api/data ────────────────────────────────────────────


class TestRoundTripViaApiData:
    def test_create_shows_up_in_api_data(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/people",
            json={
                "given_name": "Mira",
                "surname": "New",
            },
        )
        assert resp.status_code == 201
        created_id = resp.get_json()["id"]

        data = client.get("/api/data").get_json()
        ids = {p["id"] for p in data["people"]}
        assert created_id in ids

    def test_update_is_visible_in_api_data(self, app_client):
        client, _, _ = app_client
        client.put("/api/people/p1", json={"given_name": "Renamed"})
        data = client.get("/api/data").get_json()
        p = next(p for p in data["people"] if p["id"] == "p1")
        assert p["given_name"] == "Renamed"

    def test_delete_removes_from_api_data(self, app_client):
        client, _, _ = app_client
        client.delete("/api/people/p2")
        data = client.get("/api/data").get_json()
        ids = {p["id"] for p in data["people"]}
        assert "p2" not in ids
