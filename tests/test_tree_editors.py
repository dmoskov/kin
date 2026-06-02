"""Tests for non-family editor roles (tree_editors table).

Covers:
  - CRUD operations on /api/editors (admin-only).
  - Auth flow: tree_editors grant is_editor + role.
  - tree_editors enforce access even without the EDITORS env var.
  - /api/auth/me returns role field.
"""

from __future__ import annotations

import importlib

import pytest

from database.connection import get_connection, init_db
from models.person import Gender, Person

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_client(tmp_path, monkeypatch, *, editors_env=None, admin_person_id=None):
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)

    if editors_env is not None:
        monkeypatch.setenv("EDITORS", editors_env)
    else:
        monkeypatch.delenv("EDITORS", raising=False)

    if admin_person_id:
        monkeypatch.setenv("ADMIN_PERSON_ID", admin_person_id)
    else:
        monkeypatch.delenv("ADMIN_PERSON_ID", raising=False)

    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    init_db(db_path)

    import web_server

    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True
    web_server.app.config["SECRET_KEY"] = "test-secret"

    from database.repository import TreeRepository

    repo = TreeRepository(db_path)
    repo.save_person(Person(id="admin1", given_name="Admin", surname="User", gender=Gender.MALE))
    repo.save_person(Person(id="p1", given_name="Alice", surname="Test", gender=Gender.FEMALE))

    return web_server.app, repo, db_path


def _sign_in(client, app, *, person_id, email, is_editor, role=None):
    with client.session_transaction() as sess:
        sess["person_id"] = person_id
        sess["email"] = email
        sess["name"] = "Test User"
        sess["picture"] = ""
        sess["is_editor"] = is_editor
        sess["role"] = role


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    app, repo, db_path = _make_client(tmp_path, monkeypatch, admin_person_id="admin1")
    with app.test_client() as client:
        _sign_in(
            client,
            app,
            person_id="admin1",
            email="admin@example.com",
            is_editor=True,
            role="owner",
        )
        yield client, app, db_path


@pytest.fixture
def non_admin_client(tmp_path, monkeypatch):
    app, repo, db_path = _make_client(tmp_path, monkeypatch, admin_person_id="admin1")
    with app.test_client() as client:
        _sign_in(
            client,
            app,
            person_id="p1",
            email="alice@example.com",
            is_editor=True,
            role="editor",
        )
        yield client, app, db_path


# ── CRUD tests (admin only) ─────────────────────────────────────────────


class TestEditorsCRUD:
    def test_list_editors_empty(self, admin_client):
        client, _, _ = admin_client
        resp = client.get("/api/editors")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_add_editor(self, admin_client):
        client, _, _ = admin_client
        resp = client.post(
            "/api/editors",
            json={"email": "helper@example.com", "role": "assistant", "name": "Jane"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["email"] == "helper@example.com"
        assert data["role"] == "assistant"
        assert data["name"] == "Jane"

    def test_add_editor_invalid_role(self, admin_client):
        client, _, _ = admin_client
        resp = client.post(
            "/api/editors",
            json={"email": "x@example.com", "role": "superadmin"},
        )
        assert resp.status_code == 400

    def test_add_editor_missing_email(self, admin_client):
        client, _, _ = admin_client
        resp = client.post("/api/editors", json={"role": "assistant"})
        assert resp.status_code == 400

    def test_add_duplicate_editor(self, admin_client):
        client, _, _ = admin_client
        client.post(
            "/api/editors",
            json={"email": "dup@example.com", "role": "editor"},
        )
        resp = client.post(
            "/api/editors",
            json={"email": "dup@example.com", "role": "researcher"},
        )
        assert resp.status_code == 409

    def test_update_editor_role(self, admin_client):
        client, _, _ = admin_client
        client.post(
            "/api/editors",
            json={"email": "up@example.com", "role": "assistant"},
        )
        resp = client.patch(
            "/api/editors/up@example.com",
            json={"role": "researcher"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["role"] == "researcher"

    def test_update_editor_not_found(self, admin_client):
        client, _, _ = admin_client
        resp = client.patch(
            "/api/editors/nobody@example.com",
            json={"role": "editor"},
        )
        assert resp.status_code == 404

    def test_remove_editor(self, admin_client):
        client, _, _ = admin_client
        client.post(
            "/api/editors",
            json={"email": "rm@example.com", "role": "assistant"},
        )
        resp = client.delete("/api/editors/rm@example.com")
        assert resp.status_code == 204

        # Confirm gone
        editors = client.get("/api/editors").get_json()
        assert all(e["email"] != "rm@example.com" for e in editors)

    def test_remove_editor_not_found(self, admin_client):
        client, _, _ = admin_client
        resp = client.delete("/api/editors/nobody@example.com")
        assert resp.status_code == 404

    def test_list_editors_returns_all(self, admin_client):
        client, _, _ = admin_client
        client.post(
            "/api/editors",
            json={"email": "a@example.com", "role": "assistant", "name": "A"},
        )
        client.post(
            "/api/editors",
            json={"email": "b@example.com", "role": "researcher", "name": "B"},
        )
        editors = client.get("/api/editors").get_json()
        assert len(editors) == 2
        emails = {e["email"] for e in editors}
        assert emails == {"a@example.com", "b@example.com"}


# ── Non-admin is blocked ────────────────────────────────────────────────


class TestEditorsNonAdmin:
    def test_non_admin_cannot_list(self, non_admin_client):
        client, _, _ = non_admin_client
        resp = client.get("/api/editors")
        assert resp.status_code == 403

    def test_non_admin_cannot_add(self, non_admin_client):
        client, _, _ = non_admin_client
        resp = client.post(
            "/api/editors",
            json={"email": "x@example.com", "role": "assistant"},
        )
        assert resp.status_code == 403

    def test_non_admin_cannot_remove(self, non_admin_client):
        client, _, _ = non_admin_client
        resp = client.delete("/api/editors/x@example.com")
        assert resp.status_code == 403


# ── tree_editors enforce access without EDITORS env var ──────────────────


class TestTreeEditorsEnforceAccess:
    def test_tree_editors_enable_access_control(self, tmp_path, monkeypatch):
        """When tree_editors has rows (no EDITORS env), unauthenticated
        mutation requests should be blocked."""
        app, repo, db_path = _make_client(tmp_path, monkeypatch)

        # Insert a tree_editor directly
        conn = get_connection(db_path)
        try:
            conn.execute(
                "INSERT INTO tree_editors (email, role, name) VALUES (?, ?, ?)",
                ("helper@example.com", "assistant", "Helper"),
            )
            conn.commit()
        finally:
            conn.close()

        # Reload web_server to pick up the new state
        import web_server

        importlib.reload(web_server)
        web_server.PRIVATE_DIR = tmp_path
        web_server.app.config["TESTING"] = True
        web_server.app.config["SECRET_KEY"] = "test-secret"

        with app.test_client() as client:
            resp = client.post("/api/people", json={"given_name": "Bob"})
            assert resp.status_code == 403


# ── /api/auth/me returns role ────────────────────────────────────────────


class TestAuthMeRole:
    def test_auth_me_includes_role(self, admin_client):
        client, _, _ = admin_client
        data = client.get("/api/auth/me").get_json()
        assert data["role"] == "owner"
        assert data["is_editor"] is True

    def test_auth_me_role_for_assistant(self, tmp_path, monkeypatch):
        app, _, _ = _make_client(tmp_path, monkeypatch)
        with app.test_client() as client:
            _sign_in(
                client,
                app,
                person_id="editor:helper@example.com",
                email="helper@example.com",
                is_editor=True,
                role="assistant",
            )
            data = client.get("/api/auth/me").get_json()
            assert data["role"] == "assistant"
            assert data["is_editor"] is True
