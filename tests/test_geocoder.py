"""Tests for geocoder module — cache, background resolution, Nominatim calls.

All external calls (database, Nominatim) are mocked.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import geocoder as geocoder_mod

_RECENT = "2099-01-01 00:00:00"  # far-future = always fresh
_STALE = "2000-01-01 00:00:00"  # old enough to always be stale


# ── Helpers ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_pending():
    """Clear the module-level pending set between tests."""
    geocoder_mod._pending.clear()
    yield
    geocoder_mod._pending.clear()


# ── _expand_state_abbrevs ─────────────────────────────────────────────


class TestExpandStateAbbrevs:
    def test_expands_trailing_abbrev(self):
        assert geocoder_mod._expand_state_abbrevs("Boston, MA") == "Boston, Massachusetts"

    def test_expands_dc(self):
        assert (
            geocoder_mod._expand_state_abbrevs("Washington, DC")
            == "Washington, District of Columbia"
        )

    def test_expands_mid_string(self):
        result = geocoder_mod._expand_state_abbrevs("Albany, NY, USA")
        assert "New York" in result

    def test_ignores_non_state_two_letter(self):
        # "UK" is not in the table; should be left alone
        result = geocoder_mod._expand_state_abbrevs("London, UK")
        assert result == "London, UK"

    def test_no_change_for_full_name(self):
        s = "Boston, Massachusetts"
        assert geocoder_mod._expand_state_abbrevs(s) == s


# ── _simplify_place ───────────────────────────────────────────────────


class TestSimplifyPlace:
    def test_expands_state_abbrev(self):
        candidates = geocoder_mod._simplify_place("Ossining, NY")
        assert "Ossining, New York" in candidates

    def test_strips_county(self):
        candidates = geocoder_mod._simplify_place("Boston, Suffolk County, MA")
        assert any("Suffolk" not in c for c in candidates)

    def test_drops_usa_suffix(self):
        candidates = geocoder_mod._simplify_place("Boston, MA, USA")
        assert any(c.endswith(", MA") or c.endswith(", Massachusetts") for c in candidates)

    def test_city_only_fallback(self):
        candidates = geocoder_mod._simplify_place("Springfield, Sangamon County, IL")
        assert "Springfield" in candidates

    def test_no_duplicates(self):
        candidates = geocoder_mod._simplify_place("Paris")
        assert len(candidates) == len(set(candidates))

    def test_single_word_returns_empty(self):
        # No simplifications possible for a bare word
        assert geocoder_mod._simplify_place("Atlantis") == []


# ── _is_stale_null ────────────────────────────────────────────────────


class TestIsStaleNull:
    def test_none_fetched_at_is_stale(self):
        assert geocoder_mod._is_stale_null(None) is True

    def test_old_string_is_stale(self):
        assert geocoder_mod._is_stale_null(_STALE) is True

    def test_recent_string_is_not_stale(self):
        assert geocoder_mod._is_stale_null(_RECENT) is False

    def test_datetime_object(self):
        recent = datetime.now(UTC) - timedelta(days=1)
        assert geocoder_mod._is_stale_null(recent) is False
        old = datetime.now(UTC) - timedelta(days=60)
        assert geocoder_mod._is_stale_null(old) is True


# ── _nominatim_query / _nominatim ─────────────────────────────────────


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
    def test_returns_none_when_all_queries_fail(self, mock_urlopen, mock_time, mock_sleep):
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

        geocoder_mod._nominatim_query("test")
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 0.5 < delay < 0.7

    @patch("geocoder.time.sleep")
    @patch("geocoder.time.time", return_value=1000.0)
    @patch("geocoder.urllib.request.urlopen")
    def test_fallback_to_simplified_query(self, mock_urlopen, mock_time, mock_sleep):
        """When exact query fails, _nominatim tries simplified forms."""
        geocoder_mod._last_request_time = 0.0
        empty_resp = MagicMock()
        empty_resp.read.return_value = b"[]"
        empty_resp.__enter__ = lambda s: s
        empty_resp.__exit__ = MagicMock(return_value=False)

        hit_resp = MagicMock()
        hit_resp.read.return_value = json.dumps([{"lat": "41.16", "lon": "-73.86"}]).encode()
        hit_resp.__enter__ = lambda s: s
        hit_resp.__exit__ = MagicMock(return_value=False)

        # First call (exact "Ossining, NY") returns empty; second (simplified) hits
        mock_urlopen.side_effect = [empty_resp, hit_resp]

        result = geocoder_mod._nominatim("Ossining, NY")
        assert result == (41.16, -73.86)
        assert mock_urlopen.call_count == 2


# ── _load_cache / _save_cache ─────────────────────────────────────────


class TestCache:
    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=False)
    def test_load_cache_returns_coords(self, mock_pg, mock_conn):
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {"place": "Boston", "lat": 42.36, "lng": -71.06, "fetched_at": _RECENT},
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        result = geocoder_mod._load_cache(["Boston"])
        assert result == {"Boston": (42.36, -71.06)}

    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=False)
    def test_load_cache_fresh_null_is_sentinel(self, mock_pg, mock_conn):
        """A recently cached NULL is returned as None (don't retry yet)."""
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {"place": "Atlantis", "lat": None, "lng": None, "fetched_at": _RECENT},
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        result = geocoder_mod._load_cache(["Atlantis"])
        assert result == {"Atlantis": None}

    @patch("geocoder.get_connection")
    @patch("geocoder._is_pg", return_value=False)
    def test_load_cache_stale_null_is_miss(self, mock_pg, mock_conn):
        """A stale cached NULL is omitted so the background thread retries it."""
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {"place": "OldTown", "lat": None, "lng": None, "fetched_at": _STALE},
        ]
        conn = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        result = geocoder_mod._load_cache(["OldTown"])
        assert "OldTown" not in result

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
