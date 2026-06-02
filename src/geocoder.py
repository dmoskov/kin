"""Server-side geocoding via Nominatim with DB cache + background resolution.

Each unique place string is resolved once and stored in geocode_cache.
NULL lat/lng is stored for places that can't be resolved, so we don't
hammer Nominatim with repeat failures. Stale NULLs (older than
_RETRY_NULL_AFTER_DAYS) are retried automatically.

The main entry point `geocode_places()` returns cached results immediately
and spawns a background thread to resolve cache misses. Callers receive a
`pending` count so they can poll again for newly resolved places.
"""

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from database.connection import _use_postgres as _is_pg
from database.connection import get_connection

logger = logging.getLogger(__name__)

_USER_AGENT = "family-tree-app/1.0 (https://github.com/dmoskov/family-tree)"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_RATE_LIMIT = 1.1          # seconds between requests (Nominatim policy: max 1/sec)
_RETRY_NULL_AFTER_DAYS = 30  # retry cached failures after this many days

_last_request_time: float = 0.0
_lock = threading.Lock()

_pending: set[str] = set()
_pending_lock = threading.Lock()

# US state and territory abbreviation → full name
_STATE_ABBREVS: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "US Virgin Islands",
}


def _expand_state_abbrevs(s: str) -> str:
    """Expand US state abbreviations after commas: 'Boston, MA' → 'Boston, Massachusetts'."""
    def _replace(m: re.Match) -> str:
        abbr = m.group(1)
        return f", {_STATE_ABBREVS[abbr]}" if abbr in _STATE_ABBREVS else m.group(0)
    return re.sub(r",\s*([A-Z]{2})(?=\s*(?:,|$))", _replace, s)


def _simplify_place(place: str) -> list[str]:
    """Return progressively simpler query strings for a place that failed lookup.

    Tries in order:
      1. Expand state abbreviations  — "Boston, MA"           → "Boston, Massachusetts"
      2. Strip county qualifiers     — "Boston, Suffolk County, MA" → "Boston, MA"
      3. Drop trailing country names — "Paris, France, USA"   → "Paris, France"
      4. City only                   — "Boston, Massachusetts" → "Boston"
    """
    seen: set[str] = {place}
    candidates: list[str] = []

    def _add(s: str) -> None:
        s = s.strip().strip(",").strip()
        if s and s not in seen:
            seen.add(s)
            candidates.append(s)

    # 1. Expand state abbreviations
    expanded = _expand_state_abbrevs(place)
    _add(expanded)

    # 2. Strip "Xxx County" qualifiers, then also try expanding abbrevs on the result
    no_county = re.sub(r",\s*[^,]+ County\b", "", place).strip().strip(",").strip()
    _add(no_county)
    _add(_expand_state_abbrevs(no_county))

    # 3. Drop trailing country suffixes
    for suffix in (", USA", ", United States", ", United States of America", ", U.S.A."):
        if place.endswith(suffix):
            _add(place[: -len(suffix)])
            break

    # 4. City only (first comma-separated token)
    _add(place.split(",")[0].strip())

    return candidates


def _is_stale_null(fetched_at: object) -> bool:
    """Return True if a cached NULL is old enough to be worth retrying."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETRY_NULL_AFTER_DAYS)
    if fetched_at is None:
        return True
    if isinstance(fetched_at, datetime):
        dt = fetched_at.replace(tzinfo=None)
    else:
        try:
            dt = datetime.strptime(str(fetched_at)[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return True
    return dt < cutoff.replace(tzinfo=None)


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
            f"SELECT place, lat, lng, fetched_at FROM geocode_cache WHERE place IN ({ph})",
            places,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    result: dict[str, tuple[float, float] | None] = {}
    for row in rows:
        if hasattr(row, "keys"):
            place, lat, lng, fetched_at = row["place"], row["lat"], row["lng"], row["fetched_at"]
        else:
            place, lat, lng, fetched_at = row[0], row[1], row[2], row[3]

        if lat is not None and lng is not None:
            result[place] = (lat, lng)
        elif not _is_stale_null(fetched_at):
            # Recent failure — don't retry yet
            result[place] = None
        # else: stale NULL → omit from result so background thread retries it

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
    """Query Nominatim for a place, falling back to simplified strings on failure."""
    result = _nominatim_query(place)
    if result:
        return result

    for simplified in _simplify_place(place):
        result = _nominatim_query(simplified)
        if result:
            logger.debug("Geocoded %r via simplified query %r", place, simplified)
            return result

    return None


def _nominatim_query(query: str) -> tuple[float, float] | None:
    """Make a single rate-limited Nominatim request."""
    global _last_request_time
    with _lock:
        elapsed = time.time() - _last_request_time
        if elapsed < _RATE_LIMIT:
            time.sleep(_RATE_LIMIT - elapsed)
        _last_request_time = time.time()

    url = (
        _NOMINATIM_URL
        + "?"
        + urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    )
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        logger.debug("Nominatim request failed for %r", query)
    return None
