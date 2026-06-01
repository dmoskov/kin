"""Tests for editor access control (EDITORS env var).

Covers:
  - When EDITORS is not set: all mutation endpoints remain open (no regression).
  - When EDITORS is set: unauthenticated requests to mutation endpoints get 403.
  - When EDITORS is set: signed-in editors can mutate; non-editors cannot.
  - /api/config returns correct editorsEnabled and editorsMisconfigured flags.
  - /api/auth/me returns is_editor reflecting the current session.
"""

from __future__ import annotations

import importlib

import pytest

from models.person import Gender, Person

# ── Fixtures ─────────────────────────────────────────────────────────────


def _make_client(tmp_path, monkeypatch, editors_env: str | None = None, google_client_id: str | None = None):
    """Return a Flask test client with a fresh DB and optional EDITORS env var."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)

    if editors_env is not None:
        monkeypatch.setenv("EDITORS", editors_env)
    else:
        monkeypatch.delenv("EDITORS", raising=False)

    if google_client_id is not None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", google_client_id)
    else:
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    from database.connection import init_db
    init_db(db_path)

    import web_server
    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True
    web_server.app.config["SECRET_KEY"] = "test-secret"

    from database.repository import TreeRepository
    repo = TreeRepository(db_path)
    repo.save_person(Person(id="p1", given_name="Alice", surname="Test", gender=Gender.FEMALE))

    return web_server.app.test_client(), repo, web_server.app


@pytest.fixture
def open_client(tmp_path, monkeypatch):
    """Client with no EDITORS set — original open-access behaviour."""
    _, repo, app = _make_client(tmp_path, monkeypatch, editors_env=None)
    with app.test_client() as client:
        yield client, repo, app


@pytest.fixture
def restricted_client(tmp_path, monkeypatch):
    """Client with EDITORS=editor@example.com set."""
    _, repo, app = _make_client(tmp_path, monkeypatch, editors_env="editor@example.com")
    with app.test_client() as client:
        yield client, repo, app


def _sign_in_as(client, app, *, is_editor: bool, email: str = "user@example.com"):
    """Inject a session directly, bypassing Google OAuth."""
    with client.session_transaction() as sess:
        sess["person_id"] = f"editor:{email}" if is_editor else "p1"
        sess["email"] = email
        sess["name"] = "Test User"
        sess["picture"] = ""
        sess["is_editor"] = is_editor


# ── No EDITORS set: original behaviour preserved ──────────────────────────

class TestNoEditorsSet:
    def test_create_person_allowed_without_auth(self, open_client):
        client, _, _ = open_client
        resp = client.post("/api/people", json={"given_name": "Bob"})
        assert resp.status_code == 201

    def test_update_person_allowed_without_auth(self, open_client):
        client, _, _ = open_client
        resp = client.put("/api/people/p1", json={"given_name": "Alicia"})
        assert resp.status_code == 200

    def test_delete_person_allowed_without_auth(self, open_client):
        client, _, _ = open_client
        resp = client.delete("/api/people/p1")
        assert resp.status_code == 204

    def test_create_relationship_allowed_without_auth(self, open_client):
        client, repo, _ = open_client
        repo.save_person(Person(id="p2", given_name="Carol", surname="", gender=Gender.FEMALE))
        resp = client.post("/api/relationships", json={"parent_id": "p1", "child_id": "p2"})
        assert resp.status_code == 201

    def test_config_editors_enabled_false(self, open_client):
        client, _, _ = open_client
        data = client.get("/api/config").get_json()
        assert data["editorsEnabled"] is False
        assert data["editorsMisconfigured"] is False


# ── EDITORS set: unauthenticated requests blocked ─────────────────────────

class TestEditorsSetUnauthenticated:
    def test_create_person_blocked(self, restricted_client):
        client, _, _ = restricted_client
        resp = client.post("/api/people", json={"given_name": "Bob"})
        assert resp.status_code == 403
        assert resp.get_json()["code"] == "forbidden"

    def test_update_person_blocked(self, restricted_client):
        client, _, _ = restricted_client
        resp = client.put("/api/people/p1", json={"given_name": "Alicia"})
        assert resp.status_code == 403

    def test_delete_person_blocked(self, restricted_client):
        client, _, _ = restricted_client
        resp = client.delete("/api/people/p1")
        assert resp.status_code == 403

    def test_create_relationship_blocked(self, restricted_client):
        client, _, _ = restricted_client
        resp = client.post("/api/relationships", json={"parent_id": "p1", "child_id": "p2"})
        assert resp.status_code == 403

    def test_create_union_blocked(self, restricted_client):
        client, _, _ = restricted_client
        resp = client.post("/api/unions", json={"partner1_id": "p1", "partner2_id": "p2"})
        assert resp.status_code == 403

    def test_read_endpoints_still_open(self, restricted_client):
        """Viewers can always read data — only writes are gated."""
        client, _, _ = restricted_client
        assert client.get("/api/data").status_code == 200
        assert client.get("/api/config").status_code == 200
        assert client.get("/api/photos").status_code == 200

    def test_config_editors_enabled_true(self, restricted_client):
        client, _, _ = restricted_client
        data = client.get("/api/config").get_json()
        assert data["editorsEnabled"] is True


# ── EDITORS set: signed-in editor can mutate ─────────────────────────────

class TestEditorsSetAsEditor:
    def test_editor_can_create_person(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=True, email="editor@example.com")
        resp = client.post("/api/people", json={"given_name": "Bob"})
        assert resp.status_code == 201

    def test_editor_can_update_person(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=True, email="editor@example.com")
        resp = client.put("/api/people/p1", json={"given_name": "Alicia"})
        assert resp.status_code == 200

    def test_editor_can_delete_person(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=True, email="editor@example.com")
        resp = client.delete("/api/people/p1")
        assert resp.status_code == 204

    def test_auth_me_returns_is_editor_true(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=True, email="editor@example.com")
        data = client.get("/api/auth/me").get_json()
        assert data["is_editor"] is True


# ── EDITORS set: non-editor viewer is blocked ────────────────────────────

class TestEditorsSetAsViewer:
    def test_viewer_cannot_create_person(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=False, email="viewer@example.com")
        resp = client.post("/api/people", json={"given_name": "Bob"})
        assert resp.status_code == 403

    def test_viewer_cannot_update_person(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=False, email="viewer@example.com")
        resp = client.put("/api/people/p1", json={"given_name": "Alicia"})
        assert resp.status_code == 403

    def test_viewer_can_read_data(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=False, email="viewer@example.com")
        assert client.get("/api/data").status_code == 200

    def test_auth_me_returns_is_editor_false(self, restricted_client):
        client, _, app = restricted_client
        _sign_in_as(client, app, is_editor=False, email="viewer@example.com")
        data = client.get("/api/auth/me").get_json()
        assert data["is_editor"] is False


# ── editorsMisconfigured flag ────────────────────────────────────────────

class TestEditorsMisconfigured:
    def test_misconfigured_when_editors_set_without_google(self, tmp_path, monkeypatch):
        _, _, app = _make_client(
            tmp_path, monkeypatch,
            editors_env="someone@example.com",
            google_client_id=None,
        )
        import web_server
        # Point WEB_DIR at tmp_path so no family-config.json with a
        # googleClientId is found by _get_google_client_id().
        web_server.WEB_DIR = str(tmp_path)
        with app.test_client() as client:
            data = client.get("/api/config").get_json()
            assert data["editorsEnabled"] is True
            assert data["editorsMisconfigured"] is True

    def test_not_misconfigured_when_google_also_set(self, tmp_path, monkeypatch):
        _, _, app = _make_client(
            tmp_path, monkeypatch,
            editors_env="someone@example.com",
            google_client_id="fake-client-id.apps.googleusercontent.com",
        )
        with app.test_client() as client:
            data = client.get("/api/config").get_json()
            assert data["editorsEnabled"] is True
            assert data["editorsMisconfigured"] is False
