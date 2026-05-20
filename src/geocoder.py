"""Server-side geocoding via Nominatim with SQLite cache.

Each unique place string is resolved once and stored in geocode_cache.
NULL lat/lng is stored for places that can't be resolved, so we don't
hammer Nominatim with repeat failures.
"""

import json
import os
import time
import urllib.parse
import urllib.request

from database.connection import get_connection


def _is_pg() -> bool:
    return bool(os.environ.get("DATABASE_URL"))

_USER_AGENT = "family-tree-app/1.0 (https://github.com/dmoskov/family-tree)"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_RATE_LIMIT = 1.1  # seconds between requests (Nominatim policy: max 1/sec)

_last_request_time: float = 0.0


def geocode_places(places: list[str]) -> dict[str, tuple[float, float]]:
    """Resolve a list of place strings to (lat, lng) coordinates.

    Returns a dict of place -> (lat, lng) for places that resolved.
    Places that can't be resolved are omitted from the result.
    Checks the DB cache first; calls Nominatim only for cache misses.
    """
    if not places:
        return {}

    unique = list(dict.fromkeys(p for p in places if p))
    cached = _load_cache(unique)
    misses = [p for p in unique if p not in cached]

    for place in misses:
        coords = _nominatim(place)
        _save_cache(place, coords)
        if coords:
            cached[place] = coords

    return cached


def _load_cache(places: list[str]) -> dict[str, tuple[float, float]]:
    if not places:
        return {}
    pg = _is_pg()
    ph = ",".join("%s" if pg else "?" for _ in places)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT place, lat, lng FROM geocode_cache WHERE place IN ({ph})",
            places if pg else places,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    result = {}
    for row in rows:
        place = row["place"] if hasattr(row, "keys") else row[0]
        lat   = row["lat"]   if hasattr(row, "keys") else row[1]
        lng   = row["lng"]   if hasattr(row, "keys") else row[2]
        if lat is not None and lng is not None:
            result[place] = (lat, lng)
        else:
            # Cached as unresolvable — include as sentinel so we skip Nominatim
            result[place] = None
    return result


def _save_cache(place: str, coords: tuple[float, float] | None) -> None:
    lat, lng = (coords[0], coords[1]) if coords else (None, None)
    pg = _is_pg()
    conn = get_connection()
    try:
        cur = conn.cursor()
        if pg:
            cur.execute(
                "INSERT INTO geocode_cache (place, lat, lng) VALUES (%s, %s, %s) "
                "ON CONFLICT (place) DO UPDATE SET lat = EXCLUDED.lat, lng = EXCLUDED.lng, "
                "fetched_at = NOW()",
                (place, lat, lng),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO geocode_cache (place, lat, lng) VALUES (?, ?, ?)",
                (place, lat, lng),
            )
        conn.commit()
    finally:
        conn.close()


def _nominatim(place: str) -> tuple[float, float] | None:
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _RATE_LIMIT:
        time.sleep(_RATE_LIMIT - elapsed)

    url = _NOMINATIM_URL + "?" + urllib.parse.urlencode({
        "q": place,
        "format": "json",
        "limit": 1,
    })
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            _last_request_time = time.time()
            data = json.loads(resp.read())
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        _last_request_time = time.time()
    return None
