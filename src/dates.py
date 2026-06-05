"""Canonical date handling for the family tree.

Dates are stored as ISO strings at three precisions — ``YYYY``, ``YYYY-MM``,
or ``YYYY-MM-DD``. This is the de-facto genealogy interchange format: it sorts
lexicographically, supports partial dates, and stays human-readable. Keeping
every stored date in this shape is what lets the rest of the app extract a year
with a simple prefix and sort with a plain string compare.

``normalize_date`` is the single write-path gate that enforces it. Callers
should treat a ``ValueError`` as a 400-level input problem.
"""

from __future__ import annotations

import calendar
import re

# A full or partial ISO date.
_ISO_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")

# Leading approximation markers we strip. "Circa" uncertainty is tracked
# separately via the date_circa flag where a table has one; here we just
# canonicalize the stored string to a bare ISO date. Before/after qualifiers
# are intentionally NOT accepted yet (no such data, and they'd change ordering).
# Longest alternatives first so "circa"/"ca" aren't truncated by the "c" branch.
_CIRCA_RE = re.compile(
    r"^\s*(?:~|(?:circa|approx|about|abt|est|ca|c)\.?\s)\s*",
    re.IGNORECASE,
)


def looks_circa(value: str | None) -> bool:
    """True if *value* carries an approximation marker (``~1845``, ``c. 1845``)."""
    if not value:
        return False
    return bool(_CIRCA_RE.match(str(value).strip()) or str(value).strip().endswith("?"))


def normalize_date_lenient(value: str | None) -> str | None:
    """Like :func:`normalize_date`, but returns the original value unchanged when
    it can't be parsed instead of raising. For bulk import / AI-parsed data,
    which should canonicalize what it can without aborting on one messy date.
    """
    try:
        return normalize_date(value)
    except ValueError:
        return value


def normalize_date(value: str | None) -> str | None:
    """Return a canonical ISO date (``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD``).

    Returns ``None`` for empty input. Strips circa/approximation markers and a
    trailing ``?``. Raises ``ValueError`` for anything that isn't a valid
    (possibly partial) calendar date — e.g. ``18922``, ``1845-13``,
    ``1845-02-30``, ``before 1900``.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    s = _CIRCA_RE.sub("", s)
    s = s.rstrip("?").strip()
    # Accept slashes as separators ("1845/06/01") and normalize to dashes.
    s = s.replace("/", "-")

    m = _ISO_RE.match(s)
    if not m:
        raise ValueError(f"unrecognized date: {value!r} (use YYYY, YYYY-MM, or YYYY-MM-DD)")

    year_s, month_s, day_s = m.group(1), m.group(2), m.group(3)
    if day_s is not None and month_s is None:
        raise ValueError(f"day without month in date: {value!r}")

    out = year_s
    if month_s is not None:
        month = int(month_s)
        if not 1 <= month <= 12:
            raise ValueError(f"invalid month in date: {value!r}")
        out = f"{year_s}-{month_s}"
        if day_s is not None:
            day = int(day_s)
            max_day = calendar.monthrange(int(year_s), month)[1]
            if not 1 <= day <= max_day:
                raise ValueError(f"invalid day in date: {value!r}")
            out = f"{year_s}-{month_s}-{day_s}"
    return out
