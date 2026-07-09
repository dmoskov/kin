"""Tests for the shared rate limiter, TTL cache, and their wiring onto the
expensive endpoints (AI summary, geocode, wikipedia).

Covers:
  - SlidingWindowLimiter allow/deny + retry-after math (injected clock).
  - TTLCache get/set/expiry (injected clock).
  - HTTP 429 with the standard envelope + Retry-After header once an endpoint's
    limit is exceeded.
  - The summary endpoint serves a cached result without a second Anthropic call.

The app fixture mirrors test_web_people_crud.py (temporary SQLite via the
FAMILY_TREE_DB env var) and installs a fake ``anthropic`` module so no real
API call is ever made.
"""

from __future__ import annotations

import sys

import pytest

from models.person import Gender, Person
from ratelimit import SlidingWindowLimiter, TTLCache

# ── Unit: SlidingWindowLimiter ────────────────────────────────────────────


class TestSlidingWindowLimiter:
    def test_allows_up_to_limit_then_denies(self):
        clock = {"t": 0.0}
        lim = SlidingWindowLimiter(3, 60, clock=lambda: clock["t"])
        assert lim.check("k")[0] is True
        assert lim.check("k")[0] is True
        assert lim.check("k")[0] is True
        allowed, retry = lim.check("k")
        assert allowed is False
        # First hit was at t=0, window 60 → retry_after ~= 60.
        assert retry == pytest.approx(60.0)

    def test_window_slides_forward(self):
        clock = {"t": 0.0}
        lim = SlidingWindowLimiter(1, 10, clock=lambda: clock["t"])
        assert lim.check("k")[0] is True
        assert lim.check("k")[0] is False
        # Advance past the window: the old hit expires, a new one is allowed.
        clock["t"] = 10.1
        assert lim.check("k")[0] is True

    def test_keys_are_independent(self):
        lim = SlidingWindowLimiter(1, 60, clock=lambda: 0.0)
        assert lim.check("a")[0] is True
        assert lim.check("b")[0] is True
        assert lim.check("a")[0] is False

    def test_retry_after_never_below_one(self):
        clock = {"t": 0.0}
        lim = SlidingWindowLimiter(1, 5, clock=lambda: clock["t"])
        lim.check("k")
        clock["t"] = 4.9  # only 0.1s left in the window
        allowed, retry = lim.check("k")
        assert allowed is False
        assert retry >= 1.0

    @pytest.mark.parametrize("bad", [0, -1])
    def test_rejects_nonpositive_config(self, bad):
        with pytest.raises(ValueError):
            SlidingWindowLimiter(bad, 60)
        with pytest.raises(ValueError):
            SlidingWindowLimiter(1, bad)


# ── Unit: TTLCache ────────────────────────────────────────────────────────


class TestTTLCache:
    def test_get_returns_stored_value(self):
        cache = TTLCache(100, clock=lambda: 0.0)
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_missing_key_returns_none(self):
        cache = TTLCache(100, clock=lambda: 0.0)
        assert cache.get("nope") is None

    def test_entry_expires(self):
        clock = {"t": 0.0}
        cache = TTLCache(10, clock=lambda: clock["t"])
        cache.set("k", "v")
        clock["t"] = 9.9
        assert cache.get("k") == "v"
        clock["t"] = 10.1
        assert cache.get("k") is None

    def test_rejects_nonpositive_ttl(self):
        with pytest.raises(ValueError):
            TTLCache(0)


# ── Fake anthropic module ─────────────────────────────────────────────────


class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self.content = [_FakeBlock(text)]


def _install_fake_anthropic(monkeypatch):
    """Install a fake ``anthropic`` module; return a counter dict of calls."""
    import types

    counter = {"calls": 0}

    class _FakeMessages:
        def create(self, **kwargs):
            counter["calls"] += 1
            return _FakeMessage(f"Generated summary #{counter['calls']}")

    class _FakeAnthropic:
        def __init__(self, api_key=None):
            self.messages = _FakeMessages()

    module = types.ModuleType("anthropic")
    module.Anthropic = _FakeAnthropic
    monkeypatch.setitem(sys.modules, "anthropic", module)
    return counter


# ── App fixture (open access, so identity falls back to remote addr) ───────


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("ALLOW_OPEN_ACCESS", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

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

    # The summary limiter and cache live at module scope in routes.people and
    # persist across tests in the same process — reset them so each test starts
    # from a clean slate.
    from routes import people as people_routes

    people_routes._SUMMARY_CACHE.clear()
    people_routes.api_person_summary._rate_limiter._hits.clear()

    with web_server.app.test_client() as client:
        yield client, repo, tmp_path


# ── HTTP: 429 after exceeding the limit ───────────────────────────────────


class TestRateLimit429:
    def test_summary_429_after_limit(self, app_client, monkeypatch):
        client, _, _ = app_client
        _install_fake_anthropic(monkeypatch)

        # Limit is 10/min. The first 10 succeed; the 11th is throttled. The
        # limiter wraps the view, so even cache-hit responses count against it.
        for _ in range(10):
            resp = client.get("/api/people/p1/summary")
            assert resp.status_code == 200, resp.get_data(as_text=True)

        resp = client.get("/api/people/p1/summary")
        assert resp.status_code == 429
        body = resp.get_json()
        assert body["code"] == "rate_limited"
        assert "error" in body
        assert int(resp.headers["Retry-After"]) >= 1


# ── HTTP: summary cache avoids a second Anthropic call ────────────────────


class TestSummaryCache:
    def test_second_view_is_cache_hit(self, app_client, monkeypatch):
        client, _, _ = app_client
        counter = _install_fake_anthropic(monkeypatch)

        first = client.get("/api/people/p1/summary")
        assert first.status_code == 200
        summary = first.get_json()["summary"]
        assert counter["calls"] == 1

        # Same person, unchanged data → served from cache, no new API call.
        second = client.get("/api/people/p1/summary")
        assert second.status_code == 200
        assert second.get_json()["summary"] == summary
        assert counter["calls"] == 1

    def test_edit_invalidates_cache(self, app_client, monkeypatch):
        client, _, _ = app_client
        counter = _install_fake_anthropic(monkeypatch)

        client.get("/api/people/p1/summary")
        assert counter["calls"] == 1

        # Changing the person's data changes the cache-key hash → cache miss.
        client.put("/api/people/p1", json={"birth_date": "1950-01-01"})
        client.get("/api/people/p1/summary")
        assert counter["calls"] == 2
