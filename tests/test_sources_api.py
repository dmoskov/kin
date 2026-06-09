"""Tests for the source and citation CRUD endpoints.

Covers:
  - POST/PATCH/DELETE /api/sources — manage provenance records.
  - POST/PATCH/DELETE /api/citations — link sources to entities.
  - Cascade: deleting a source removes its citations.

Uses the same hermetic ``app_client`` fixture pattern as the other web
test modules.
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
    repo.save_person(Person(id="p1", given_name="Alice", surname="Test", gender=Gender.FEMALE))

    with web_server.app.test_client() as client:
        yield client, repo, tmp_path


def _make_source(client, **overrides):
    payload = {"name": "1920 US Census", "source_type": "public"}
    payload.update(overrides)
    return client.post("/api/sources", json=payload)


# ── POST /api/sources ──────────────────────────────────────────────────────


class TestCreateSource:
    def test_happy_path(self, app_client):
        client, _, _ = app_client
        resp = _make_source(client)
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["name"] == "1920 US Census"
        assert body["source_type"] == "public"
        assert body["id"]

    def test_persists_in_api_data(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        sources = client.get("/api/data").get_json()["sources"]
        assert any(s["id"] == sid for s in sources)

    def test_missing_name(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/sources", json={"source_type": "public"})
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "bad_request"

    def test_invalid_source_type(self, app_client):
        client, _, _ = app_client
        resp = client.post("/api/sources", json={"name": "X", "source_type": "bogus"})
        assert resp.status_code == 400

    def test_duplicate_id_conflict(self, app_client):
        client, _, _ = app_client
        _make_source(client, id="dup")
        resp = _make_source(client, id="dup")
        assert resp.status_code == 409
        assert resp.get_json()["code"] == "conflict"


# ── PATCH /api/sources/<id> ──────────────────────────────────────────────────


class TestUpdateSource:
    def test_happy_path(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.patch(f"/api/sources/{sid}", json={"name": "Renamed", "author": "Clerk"})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["name"] == "Renamed"
        assert body["author"] == "Clerk"

    def test_clear_optional_field(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client, author="Someone").get_json()["id"]
        client.patch(f"/api/sources/{sid}", json={"author": ""})
        sources = client.get("/api/data").get_json()["sources"]
        src = next(s for s in sources if s["id"] == sid)
        assert "author" not in src  # serializer omits None

    def test_unknown_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.patch("/api/sources/nope", json={"name": "X"})
        assert resp.status_code == 404
        assert resp.get_json()["code"] == "not_found"

    def test_empty_name_rejected(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.patch(f"/api/sources/{sid}", json={"name": "   "})
        assert resp.status_code == 400

    def test_nothing_to_update(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.patch(f"/api/sources/{sid}", json={})
        assert resp.status_code == 400


# ── DELETE /api/sources/<id> ─────────────────────────────────────────────────


class TestDeleteSource:
    def test_happy_path(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.delete(f"/api/sources/{sid}")
        assert resp.status_code == 204
        sources = client.get("/api/data").get_json()["sources"]
        assert not any(s["id"] == sid for s in sources)

    def test_unknown_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.delete("/api/sources/nope")
        assert resp.status_code == 404

    def test_cascades_to_citations(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        client.post(
            "/api/citations",
            json={"source_id": sid, "entity_type": "person", "entity_id": "p1"},
        )
        client.delete(f"/api/sources/{sid}")
        citations = client.get("/api/data").get_json()["citations"]
        assert not any(c["source_id"] == sid for c in citations)


# ── POST /api/citations ──────────────────────────────────────────────────────


class TestCreateCitation:
    def test_happy_path(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.post(
            "/api/citations",
            json={
                "source_id": sid,
                "entity_type": "person",
                "entity_id": "p1",
                "field_name": "birth_date",
                "confidence": "probable",
                "excerpt": "b. 1887",
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        body = resp.get_json()
        assert isinstance(body["id"], int)
        assert body["source_id"] == sid
        assert body["confidence"] == "probable"

    def test_persists_in_api_data(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        cid = client.post(
            "/api/citations",
            json={"source_id": sid, "entity_type": "person", "entity_id": "p1"},
        ).get_json()["id"]
        citations = client.get("/api/data").get_json()["citations"]
        assert any(c.get("id") == cid for c in citations)

    def test_missing_fields(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.post("/api/citations", json={"source_id": sid, "entity_type": "person"})
        assert resp.status_code == 400

    def test_invalid_entity_type(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.post(
            "/api/citations",
            json={"source_id": sid, "entity_type": "bogus", "entity_id": "p1"},
        )
        assert resp.status_code == 400

    def test_invalid_confidence(self, app_client):
        client, _, _ = app_client
        sid = _make_source(client).get_json()["id"]
        resp = client.post(
            "/api/citations",
            json={
                "source_id": sid,
                "entity_type": "person",
                "entity_id": "p1",
                "confidence": "bogus",
            },
        )
        assert resp.status_code == 400

    def test_unknown_source_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.post(
            "/api/citations",
            json={"source_id": "nope", "entity_type": "person", "entity_id": "p1"},
        )
        assert resp.status_code == 404


# ── PATCH/DELETE /api/citations/<id> ─────────────────────────────────────────


class TestUpdateDeleteCitation:
    def _make_citation(self, client):
        sid = _make_source(client).get_json()["id"]
        return client.post(
            "/api/citations",
            json={"source_id": sid, "entity_type": "person", "entity_id": "p1"},
        ).get_json()["id"]

    def test_update_happy_path(self, app_client):
        client, _, _ = app_client
        cid = self._make_citation(client)
        resp = client.patch(
            f"/api/citations/{cid}",
            json={"confidence": "uncertain", "notes": "legible but faded"},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.get_json()["confidence"] == "uncertain"

    def test_update_unknown_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.patch("/api/citations/99999", json={"confidence": "probable"})
        assert resp.status_code == 404

    def test_update_invalid_confidence(self, app_client):
        client, _, _ = app_client
        cid = self._make_citation(client)
        resp = client.patch(f"/api/citations/{cid}", json={"confidence": "bogus"})
        assert resp.status_code == 400

    def test_delete_happy_path(self, app_client):
        client, _, _ = app_client
        cid = self._make_citation(client)
        resp = client.delete(f"/api/citations/{cid}")
        assert resp.status_code == 204
        citations = client.get("/api/data").get_json()["citations"]
        assert not any(c.get("id") == cid for c in citations)

    def test_delete_unknown_returns_404(self, app_client):
        client, _, _ = app_client
        resp = client.delete("/api/citations/99999")
        assert resp.status_code == 404
