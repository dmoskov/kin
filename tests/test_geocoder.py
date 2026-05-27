"""Tests for geocoder module — cache, background resolution, Nominatim calls.

All external calls (database, Nominatim) are mocked.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import geocoder as geocoder_mod


# ── Helpers ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_pending():
    """Clear the module-level pending set between tests."""
    geocoder_mod._pending.clear()
    yield
    geocoder_mod._pending.clear()


# ── _nominatim ────────────────────────────────────────────────────────


class TestNominatim:
    @patch("geocoder.time.sleep")
    @patch("geocoder.time.time", return_value=1000.0)
    @patch("geocoder.urllib.request.urlopen")
    def test_parses_lat_lon(self, mock_urlopen, mock_time, mock_sleep):
        geocoder_mod._last_request_time = 0.0
        body = json.dumps([{"lat": "42.36", "lon": "-71.06"}]).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = geocoder_mod._nominatim("Boston, MA")
        assert result == (42.36, -71.06)

    @patch("geocoder.time.sleep")
    @patch("geocoder.time.time", return_value=1000.0)
    @patch("geocoder.urllib.request.urlopen")
    def test_returns_none_on_empty_result(self, mock_urlopen, mock_time, mock_sleep):
        geocoder_mod._last_request_time = 0.0
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        assert geocoder_mod._nominatim("Atlantis") is None

    @patch("geocoder.time.sleep")
    @patch("geocoder.time.time", return_value=1000.0)
    @patch("geocoder.urllib.request.urlopen", side_effect=Exception("network"))
    def test_returns_none_on_error(self, mock_urlopen, mock_time, mock_sleep):
        geocoder_mod._last_request_time = 0.0
        assert geocoder_mod._nominatim("Nowhere") is None

    @patch("geocoder.urllib.request.urlopen")
    @patch("geocoder.time.time")
    @patch("geocoder.time.sleep")
    def test_rate_limits(self, mock_sleep, mock_time, mock_urlopen):
        mock_time.return_value = 100.5
        geocoder_mod._last_request_time = 100.0
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        geocoder_mod._nominatim("test")
        # elapsed = 0.5, rate limit = 1.1, should sleep 0.6
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 0.5 < delay < 0.7


# ── _load_cache / _save_cache ─────────────────────────────────────────


class TestCache:
    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=False)
    def test_load_cache_returns_coords(self, mock_pg, mock_conn):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {"place": "Boston", "lat": 42.36, "lng": -71.06},
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        result = geocoder_mod._load_cache(["Boston"])
        assert result == {"Boston": (42.36, -71.06)}

    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=False)
    def test_load_cache_returns_none_sentinel(self, mock_pg, mock_conn):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {"place": "Atlantis", "lat": None, "lng": None},
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        result = geocoder_mod._load_cache(["Atlantis"])
        assert result == {"Atlantis": None}

    def test_load_cache_empty_input(self):
        assert geocoder_mod._load_cache([]) == {}

    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=False)
    def test_save_cache_with_coords(self, mock_pg, mock_conn):
        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        geocoder_mod._save_cache("NYC", (40.71, -74.01))
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "INSERT OR REPLACE" in sql
        assert cursor.execute.call_args[0][1] == ("NYC", 40.71, -74.01)

    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=False)
    def test_save_cache_with_none(self, mock_pg, mock_conn):
        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        geocoder_mod._save_cache("Atlantis", None)
        assert cursor.execute.call_args[0][1] == ("Atlantis", None, None)

    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=True)
    def test_save_cache_pg_uses_on_conflict(self, mock_pg, mock_conn):
        cursor = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        geocoder_mod._save_cache("NYC", (40.71, -74.01))
        sql = cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql


# ── geocode_places ────────────────────────────────────────────────────


class TestGeocodePlaces:
    def test_empty_list_returns_empty(self):
        result, pending = geocoder_mod.geocode_places([])
        assert result == {}
        assert pending == 0

    @patch("geocoder._load_cache")
    def test_all_cached_returns_immediately(self, mock_cache):
        mock_cache.return_value = {"Boston": (42.36, -71.06)}
        result, pending = geocoder_mod.geocode_places(["Boston"])
        assert result == {"Boston": (42.36, -71.06)}
        assert pending == 0

    @patch("geocoder.threading.Thread")
    @patch("geocoder._load_cache", return_value={})
    def test_misses_spawn_background_thread(self, mock_cache, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        result, pending = geocoder_mod.geocode_places(["New York"])
        assert pending == 1
        assert result == {}
        mock_thread.start.assert_called_once()

    @patch("geocoder._load_cache")
    def test_none_sentinels_excluded_from_result(self, mock_cache):
        mock_cache.return_value = {
            "Boston": (42.36, -71.06),
            "Atlantis": None,
        }
        result, pending = geocoder_mod.geocode_places(["Boston", "Atlantis"])
        assert "Atlantis" not in result
        assert "Boston" in result

    @patch("geocoder.threading.Thread")
    @patch("geocoder._load_cache", return_value={})
    def test_deduplicates_input(self, mock_cache, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        geocoder_mod.geocode_places(["NYC", "NYC", "NYC"])
        thread_args = mock_thread_cls.call_args
        places_arg = thread_args.kwargs.get("args") or thread_args[1].get("args")
        assert places_arg[0] == ["NYC"]

    @patch("geocoder.threading.Thread")
    @patch("geocoder._load_cache", return_value={})
    def test_already_pending_not_respawned(self, mock_cache, mock_thread_cls):
        geocoder_mod._pending.add("NYC")
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        geocoder_mod.geocode_places(["NYC"])
        mock_thread.start.assert_not_called()


# ── _resolve_background ──────────────────────────────────────────────


class TestResolveBackground:
    @patch("geocoder._save_cache")
    @patch("geocoder._nominatim", return_value=(42.36, -71.06))
    def test_resolves_and_saves(self, mock_nom, mock_save):
        geocoder_mod._pending.add("Boston")
        geocoder_mod._resolve_background(["Boston"])
        mock_nom.assert_called_once_with("Boston")
        mock_save.assert_called_once_with("Boston", (42.36, -71.06))
        assert "Boston" not in geocoder_mod._pending

    @patch("geocoder._save_cache")
    @patch("geocoder._nominatim", side_effect=Exception("fail"))
    def test_removes_from_pending_on_error(self, mock_nom, mock_save):
        geocoder_mod._pending.add("Bad Place")
        geocoder_mod._resolve_background(["Bad Place"])
        assert "Bad Place" not in geocoder_mod._pending
        mock_save.assert_not_called()
