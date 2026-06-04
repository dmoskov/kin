"""Resolve family members to their Wikipedia article (if notable), with a DB
cache and gentle background resolution — mirrors geocoder.py.

A person matches only when a candidate article is biographical AND the person's
birth or death year appears in it (±1), which guards against same-name hits. On
a match we also parse the article into a few dated events (stored as JSON), so
the bio becomes structured, queryable data — without touching the user's own
hand-curated `events` table.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from database.connection import _use_postgres as _is_pg
from database.connection import get_connection

logger = logging.getLogger(__name__)

_USER_AGENT = "family-tree-app/1.0 (https://github.com/dmoskov/kin)"
_API = "https://en.wikipedia.org/w/api.php"
_RATE_LIMIT = 1.3  # seconds between Wikipedia requests (be a good citizen)
_RETRY_NULL_AFTER_DAYS = 30  # re-check "no match" after this many days

_last_request_time: float = 0.0
_rate_lock = threading.Lock()
_pending: set[str] = set()
_pending_lock = threading.Lock()

_PERSON_RE = re.compile(
    r"\b(born|was an?|is an?|served|founded|poet|general|colonel|major|"
    r"justice|judge|entrepreneur|politician|congress|author|painter|"
    r"composer|hymn|clergy|minister|philanthrop|reverend)\b",
    re.I,
)
_EVENT_RE = re.compile(
    r"\b(born|published|married|died|appointed|elected|graduat|enlist|founded|"
    r"established|wrote|composed|painted|awarded|ordained|settled|emigrat|"
    r"immigrat|served|wounded|captured|commissioned|premiered|invented|"
    r"discovered|co-founded|launched|opened)\b",
    re.I,
)
_NOISE_RE = re.compile(r"\b(population|census|km2|km²|metres|feet above)\b", re.I)


def resolve_people(people: list[dict]) -> tuple[dict[str, dict], int]:
    """people: list of {id, name, birth, death}.

    Returns (results, pending) where results maps person_id -> a cache row dict
    {matched, title, url, description, events} for everything already resolved.
    Misses are resolved in a rate-limited background thread; call again to pick
    up newly resolved people.
    """
    by_id = {p["id"]: p for p in people if p.get("id") and p.get("name")}
    if not by_id:
        return {}, 0

    cached = _load_cache(list(by_id))
    misses = [pid for pid in by_id if pid not in cached]

    with _pending_lock:
        new_misses = [pid for pid in misses if pid not in _pending]
        _pending.update(new_misses)

    if new_misses:
        targets = [by_id[pid] for pid in new_misses]
        threading.Thread(target=_resolve_background, args=(targets,), daemon=True).start()

    return cached, len(misses)


def _resolve_background(people: list[dict]) -> None:
    for p in people:
        try:
            result = _lookup(p["name"], _year(p.get("birth")), _year(p.get("death")))
            _save_cache(p["id"], result)
        except Exception:
            logger.exception("Wikipedia lookup failed for %s", p.get("id"))
        finally:
            with _pending_lock:
                _pending.discard(p["id"])


def _year(s: str | None) -> int | None:
    m = re.search(r"(\d{4})", s or "")
    return int(m.group(1)) if m else None


def _api_get(params: dict) -> dict | None:
    with _rate_lock:
        global _last_request_time
        wait = _RATE_LIMIT - (time.monotonic() - _last_request_time)
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.monotonic()
    url = _API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _lookup(name: str, by: int | None, dy: int | None) -> dict:
    """Search Wikipedia for `name`, confirm a biographical year match, and parse
    a few dated events. Returns a cache row dict (matched may be False)."""
    if not by and not dy:
        return {"matched": False, "title": None, "url": None, "description": "", "events": []}

    data = _api_get(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": name,
            "gsrlimit": "3",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
        }
    )
    pages = list((data or {}).get("query", {}).get("pages", {}).values())
    for pg in pages:
        ex = pg.get("extract") or ""
        if not ex or re.search(r"may refer to|disambiguation", ex, re.I):
            continue
        if not _PERSON_RE.search(ex):
            continue
        hit = (by and any(str(y) in ex for y in (by - 1, by, by + 1))) or (
            dy and any(str(y) in ex for y in (dy - 1, dy, dy + 1))
        )
        if not hit:
            continue
        title = pg["title"]
        desc = ex.strip().split(". ")[0][:240]
        events = _fetch_and_parse_events(title, by, dy)
        return {
            "matched": True,
            "title": title,
            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
            "description": desc,
            "events": events,
        }
    return {"matched": False, "title": None, "url": None, "description": "", "events": []}


def _fetch_and_parse_events(title: str, by: int | None, dy: int | None) -> list[dict]:
    """Fetch the full plain-text article and split it into a few dated events
    within the person's lifetime."""
    data = _api_get(
        {
            "action": "query",
            "format": "json",
            "redirects": "1",
            "prop": "extracts",
            "explaintext": "1",
            "titles": title,
        }
    )
    pages = list((data or {}).get("query", {}).get("pages", {}).values())
    extract = (pages[0].get("extract") if pages else "") or ""
    text = re.sub(r"\n+", " ", extract)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z(0-9])", text)
    lo = (by - 1) if by else 0
    hi = (dy + 1) if dy else (datetime.now(UTC).year)
    out: list[dict] = []
    seen: set[int] = set()
    for s in sentences:
        if len(s) < 25 or len(s) > 220:
            continue
        if _NOISE_RE.search(s) or not _EVENT_RE.search(s):
            continue
        m = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", s)
        if not m:
            continue
        yr = int(m.group(1))
        if yr < lo or yr > hi or yr in seen:
            continue
        seen.add(yr)
        out.append({"year": yr, "text": s.strip()})
    out.sort(key=lambda e: e["year"])
    return out[:6]


def _load_cache(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    pg = _is_pg()
    ph = ",".join("%s" if pg else "?" for _ in ids)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT person_id, matched, title, url, description, events, fetched_at "
            f"FROM person_wikipedia WHERE person_id IN ({ph})",
            ids,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    result: dict[str, dict] = {}
    for row in rows:
        if hasattr(row, "keys"):
            pid, matched, title, url, desc, events, fetched = (
                row["person_id"],
                row["matched"],
                row["title"],
                row["url"],
                row["description"],
                row["events"],
                row["fetched_at"],
            )
        else:
            pid, matched, title, url, desc, events, fetched = row
        is_match = bool(matched)
        if not is_match and _is_stale(fetched):
            continue  # stale "no match" → let the background thread retry
        try:
            ev = json.loads(events) if events else []
        except Exception:
            ev = []
        result[pid] = {
            "matched": is_match,
            "title": title,
            "url": url,
            "description": desc or "",
            "events": ev,
        }
    return result


def _save_cache(person_id: str, result: dict) -> None:
    pg = _is_pg()
    events_json = json.dumps(result.get("events") or [])
    conn = get_connection()
    try:
        cur = conn.cursor()
        if pg:
            cur.execute(
                "INSERT INTO person_wikipedia (person_id, matched, title, url, description, events) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (person_id) DO UPDATE SET matched=EXCLUDED.matched, "
                "title=EXCLUDED.title, url=EXCLUDED.url, description=EXCLUDED.description, "
                "events=EXCLUDED.events, fetched_at=NOW()",
                (
                    person_id,
                    bool(result["matched"]),
                    result["title"],
                    result["url"],
                    result["description"],
                    events_json,
                ),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO person_wikipedia "
                "(person_id, matched, title, url, description, events) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    person_id,
                    1 if result["matched"] else 0,
                    result["title"],
                    result["url"],
                    result["description"],
                    events_json,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _is_stale(fetched_at) -> bool:
    if not fetched_at:
        return True
    try:
        if isinstance(fetched_at, str):
            dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00").split(".")[0])
        else:
            dt = fetched_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return datetime.now(UTC) - dt > timedelta(days=_RETRY_NULL_AFTER_DAYS)
    except Exception:
        return True
