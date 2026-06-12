"""Tests for session/auth hardening: SECRET_KEY enforcement, session cookie
flags, and rate limiting on the Google sign-in endpoint."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)
    monkeypatch.delenv("EDITORS", raising=False)
    # Sign-in requires a configured client id (no-audience verification is
    # refused), so these tests run with one set.
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.delenv("ALLOW_OPEN_ACCESS", raising=False)

    from database.connection import init_db

    init_db(db_path)

    import web_server

    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True

    from routes import auth

    auth._auth_attempts.clear()

    with web_server.app.test_client() as c:
        yield c


# ── SECRET_KEY enforcement ─────────────────────────────────────────────────


class TestSecretKey:
    def test_explicit_secret_key_used(self, monkeypatch):
        import web_server

        monkeypatch.setenv("SECRET_KEY", "configured-key")
        assert web_server._resolve_secret_key() == "configured-key"

    def test_production_without_secret_key_refuses_to_start(self, monkeypatch):
        import web_server

        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
        with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
            web_server._resolve_secret_key()

    def test_dev_gets_ephemeral_key(self, monkeypatch):
        import web_server

        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        key = web_server._resolve_secret_key()
        assert len(key) == 64
        assert key != web_server._resolve_secret_key()


# ── Session cookie flags ───────────────────────────────────────────────────


def test_session_cookie_flags(client):
    import web_server

    assert web_server.app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert web_server.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    # Local dev runs over http, so Secure is off; production (DATABASE_URL
    # set) turns it on — covered by the _resolve flag expression itself.
    assert web_server.app.config["SESSION_COOKIE_SECURE"] is False


# ── Rate limiting on /api/auth/google ──────────────────────────────────────


class TestAuthRateLimit:
    def test_sign_in_attempts_rate_limited(self, client, monkeypatch):
        from routes import auth

        monkeypatch.setattr(auth, "_verify_id_token", lambda credential, audience: None)

        for _ in range(auth._AUTH_MAX_ATTEMPTS):
            resp = client.post("/api/auth/google", json={"credential": "bad"})
            assert resp.status_code == 401

        resp = client.post("/api/auth/google", json={"credential": "bad"})
        assert resp.status_code == 429

    def test_window_expiry_resets_limit(self, client, monkeypatch):
        from routes import auth

        monkeypatch.setattr(auth, "_verify_id_token", lambda credential, audience: None)

        for _ in range(auth._AUTH_MAX_ATTEMPTS + 1):
            client.post("/api/auth/google", json={"credential": "bad"})

        # Age the window out; the next attempt is allowed again.
        ip, (start, count) = next(iter(auth._auth_attempts.items()))
        auth._auth_attempts[ip] = (start - auth._AUTH_WINDOW_SECONDS - 1, count)
        resp = client.post("/api/auth/google", json={"credential": "bad"})
        assert resp.status_code == 401

    def test_unverified_email_rejected(self, client, monkeypatch):
        from routes import auth

        # google-auth returns decoded JWT claims: email_verified is a bool.
        monkeypatch.setattr(
            auth,
            "_verify_id_token",
            lambda credential, audience: {"email": "x@example.com", "email_verified": False},
        )
        resp = client.post("/api/auth/google", json={"credential": "tok"})
        assert resp.status_code == 401
        assert "verified" in resp.get_json()["error"].lower()


# ── Sign-in refused when no client id is configured ─────────────────────────


def test_sign_in_refused_without_client_id(client, monkeypatch):
    """With no client id there is no audience to verify against — google-auth
    would accept a valid token minted for ANY app, so sign-in must refuse."""
    import web_server

    monkeypatch.setattr(web_server, "_get_google_client_id", lambda: None)
    resp = client.post("/api/auth/google", json={"credential": "tok"})
    assert resp.status_code == 503
    assert "not configured" in resp.get_json()["error"].lower()


# ── Editor lookups fail loudly on DB errors ─────────────────────────────────


def test_editors_configured_propagates_db_errors(client, monkeypatch):
    """A DB hiccup must not read as 'no editors configured' — that fallback
    grants editor to everyone. The error has to surface, not be swallowed."""
    import database.connection as db_conn
    import web_server

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db_conn, "db_transaction", boom)
    with pytest.raises(RuntimeError, match="db down"):
        web_server._editors_configured()


def test_has_any_tree_editors_propagates_db_errors(client, monkeypatch):
    from routes import auth

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(auth, "db_transaction", boom)
    with pytest.raises(RuntimeError, match="db down"):
        auth._has_any_tree_editors()
