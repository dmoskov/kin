"""Tests for the site-wide login gate (_enforce_login).

The gate activates only when GOOGLE_CLIENT_ID is set. It must protect data,
photo files, and document files — regardless of file extension — while leaving
the public SPA shell (index, /js, /dist, /icons, css/fonts, /healthz) and the
endpoints needed to log in (/api/auth/*, /api/config) reachable.

Regression: photo files ending in .png/.jpg must NOT bypass the gate just
because they look like static assets.
"""

from __future__ import annotations

import importlib

import pytest

from models.person import Gender, Person


def _make_gated_client(tmp_path, monkeypatch):
    """Return a Flask test client with the login gate ON (GOOGLE_CLIENT_ID set)."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)
    monkeypatch.delenv("EDITORS", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")

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
def gated_client(tmp_path, monkeypatch):
    _, repo, app = _make_gated_client(tmp_path, monkeypatch)
    with app.test_client() as client:
        yield client, repo, app


def _sign_in(client):
    with client.session_transaction() as sess:
        sess["person_id"] = "p1"
        sess["email"] = "user@example.com"
        sess["is_editor"] = False


# ── Protected paths: blocked when unauthenticated ─────────────────────────


class TestGateBlocksUnauthenticated:
    @pytest.mark.parametrize(
        "path",
        [
            "/api/data",
            "/photos/foo.png",  # regression: .png must not bypass the gate
            "/photos/foo.jpg",
            "/photos/sub/bar.PNG",  # uppercase extension too
            "/photos/raw-bytes",  # no extension
            "/documents/scan.pdf",
        ],
    )
    def test_protected_path_returns_401(self, gated_client, path):
        client, _, _ = gated_client
        resp = client.get(path)
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "unauthorized"


# ── Public paths: reachable without auth ──────────────────────────────────


class TestGateAllowsPublic:
    @pytest.mark.parametrize(
        "path",
        [
            "/healthz",
            "/",
            "/api/config",
            "/photos/view/some-photo",  # client-side route → SPA shell, not a file
        ],
    )
    def test_public_path_not_gated(self, gated_client, path):
        client, _, _ = gated_client
        # Must not be a 401 — the gate lets these through (200, or 404 if the
        # underlying route/file is absent, but never an auth rejection).
        assert client.get(path).status_code != 401

    def test_auth_endpoints_not_gated(self, gated_client):
        client, _, _ = gated_client
        # /api/auth/* is needed to log in, so the gate must let it reach its
        # handler. Logged out, /api/auth/me returns its OWN 401 ("not
        # authenticated") — distinct from the gate's 401 ("unauthorized").
        resp = client.get("/api/auth/me")
        assert resp.get_json().get("code") != "unauthorized"
        # And once signed in, the handler runs and returns the user.
        _sign_in(client)
        assert client.get("/api/auth/me").status_code == 200


# ── Authenticated users pass through ──────────────────────────────────────


class TestGateAllowsAuthenticated:
    def test_data_accessible_once_signed_in(self, gated_client):
        client, _, _ = gated_client
        _sign_in(client)
        assert client.get("/api/data").status_code == 200

    def test_photo_request_not_gated_once_signed_in(self, gated_client):
        client, _, _ = gated_client
        _sign_in(client)
        # File doesn't exist → 404, but the gate no longer returns 401.
        assert client.get("/photos/foo.png").status_code != 401


# ── Gate off when no client id is configured anywhere ──────────────────────


def _make_open_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)
    monkeypatch.delenv("EDITORS", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("ALLOW_OPEN_ACCESS", raising=False)

    from database.connection import init_db

    init_db(db_path)

    import web_server

    importlib.reload(web_server)
    # Point at an empty private dir: a real private/config/family-config.json
    # (e.g. on a dev machine) would turn the gate on via the config fallback.
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True
    return web_server


def test_gate_off_without_any_client_id(tmp_path, monkeypatch):
    web_server = _make_open_client(tmp_path, monkeypatch)
    with web_server.app.test_client() as client:
        # No gate configured anywhere → data is openly reachable.
        assert client.get("/api/data").status_code == 200


# ── Gate on via family-config.json (no env var) ────────────────────────────


def test_gate_on_via_config_file_only(tmp_path, monkeypatch):
    """The API gate must key off the same client-id lookup as the frontend:
    a client id in family-config.json alone gates the API, so losing the env
    var can't silently fall open while the login screen still renders."""
    web_server = _make_open_client(tmp_path, monkeypatch)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "family-config.json").write_text('{"googleClientId": "file-client-id"}')
    with web_server.app.test_client() as client:
        resp = client.get("/api/data")
        assert resp.status_code == 401
        assert resp.get_json()["code"] == "unauthorized"


# ── ALLOW_OPEN_ACCESS: explicit opt-out wins ────────────────────────────────


def test_allow_open_access_disables_gate_and_frontend(tmp_path, monkeypatch):
    web_server = _make_open_client(tmp_path, monkeypatch)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "family-config.json").write_text('{"googleClientId": "file-client-id"}')
    monkeypatch.setenv("ALLOW_OPEN_ACCESS", "1")
    with web_server.app.test_client() as client:
        assert client.get("/api/data").status_code == 200
        # The frontend keys its login gate off googleClientId in /api/config;
        # explicit open access must strip it so UI and API agree.
        assert "googleClientId" not in client.get("/api/config").get_json()


# ── Production refuses to start with no auth configured ────────────────────


class TestProdFailsClosed:
    def test_prod_without_client_id_refuses_to_start(self, tmp_path, monkeypatch):
        web_server = _make_open_client(tmp_path, monkeypatch)
        monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
        with pytest.raises(RuntimeError, match="No Google client id"):
            web_server._assert_prod_auth_configured()

    def test_prod_with_client_id_starts(self, tmp_path, monkeypatch):
        web_server = _make_open_client(tmp_path, monkeypatch)
        monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        web_server._assert_prod_auth_configured()  # no raise

    def test_prod_with_explicit_open_access_starts(self, tmp_path, monkeypatch):
        web_server = _make_open_client(tmp_path, monkeypatch)
        monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
        monkeypatch.setenv("ALLOW_OPEN_ACCESS", "1")
        web_server._assert_prod_auth_configured()  # no raise
