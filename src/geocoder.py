"""Server-side geocoding via Nominatim with DB cache + background resolution.

Each unique place string is resolved once and stored in geocode_cache.
NULL lat/lng is stored for places that can't be resolved, so we don't
hammer Nominatim with repeat failures.

The main entry point `geocode_places()` returns cached results immediately
and spawns a background thread to resolve cache misses. Callers receive a
`pending` count so they can poll again for newly resolved places.
"""

import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request

from database.connection import get_connection

logger = logging.getLogger(__name__)

_USER_AGENT = "family-tree-app/1.0 (https://github.com/dmoskov/family-tree)"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_RATE_LIMIT = 1.1  # seconds between requests (Nominatim policy: max 1/sec)

_last_request_time: float = 0.0
_lock = threading.Lock()

# Track which places are currently being resolved in the background
_pending: set[str] = set()
_pending_lock = threading.Lock()


def _is_pg() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def geocode_places(places: list[str]) -> tuple[dict[str, tuple[float, float]], int]:
    """Resolve a list of place strings to (lat, lng) coordinates.

    Returns (coords_dict, pending_count):
      - coords_dict: place -> (lat, lng) for all cached/resolved places
      - pending_count: number of places being resolved in the background

    Cached results are returned immediately. Cache misses are resolved
    in a background thread; call again to pick up newly resolved places.
    """
    if not places:
        return {}, 0

    unique = list(dict.fromkeys(p for p in places if p))
    cached = _load_cache(unique)
    misses = [p for p in unique if p not in cached]

    # Filter out places already being resolved by a background thread
    with _pending_lock:
        new_misses = [p for p in misses if p not in _pending]
        _pending.update(new_misses)

    pending_count = len(misses)

    if new_misses:
        thread = threading.Thread(
            target=_resolve_background,
            args=(new_misses,),
            daemon=True,
        )
        thread.start()

    # Return only successfully resolved coords (not None sentinels)
    result = {p: c for p, c in cached.items() if c is not None}
    return result, pending_count


def _resolve_background(places: list[str]) -> None:
    """Geocode a list of places in the background, saving to cache."""
    for place in places:
        try:
            coords = _nominatim(place)
            _save_cache(place, coords)
        except Exception:
            logger.exception("Background geocode failed for %s", place)
        finally:
            with _pending_lock:
                _pending.discard(place)


def _load_cache(places: list[str]) -> dict[str, tuple[float, float] | None]:
    if not places:
        return {}
    pg = _is_pg()
    ph = ",".join("%s" if pg else "?" for _ in places)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT place, lat, lng FROM geocode_cache WHERE place IN ({ph})",
            places,
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
    with _lock:
        elapsed = time.time() - _last_request_time
        if elapsed < _RATE_LIMIT:
            time.sleep(_RATE_LIMIT - elapsed)
        _last_request_time = time.time()

    url = _NOMINATIM_URL + "?" + urllib.parse.urlencode({
        "q": place,
        "format": "json",
        "limit": 1,
    })
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        logger.debug("Nominatim request failed for %s", place)
    return None
