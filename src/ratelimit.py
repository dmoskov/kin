"""In-memory rate limiting and TTL caching for expensive endpoints.

These helpers guard endpoints that trigger paid or outbound work (Anthropic
summaries, Nominatim geocoding, Wikipedia lookups) so a single logged-in
viewer can't burn credits or hammer external services in a loop.

Everything here is per-process and in-memory: there is no shared store, so
under gunicorn with N workers the effective limit is N times the configured
bound. That's an accepted trade-off — it needs no new dependency and no
network round-trip, and the goal is to stop runaway loops, not to enforce a
billing-grade global quota.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import jsonify, request, session


class SlidingWindowLimiter:
    """Per-key sliding-window counter.

    Allows at most ``max_calls`` hits per ``window_seconds`` for each key.
    Thread-safe; the clock is injectable so behaviour is deterministic in
    tests.
    """

    def __init__(
        self,
        max_calls: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, hits: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def check(self, key: str) -> tuple[bool, float]:
        """Record a hit for ``key`` and report whether it is allowed.

        Returns ``(allowed, retry_after)``. When allowed, ``retry_after`` is
        0. When denied, ``retry_after`` is the number of seconds until the
        oldest hit in the window expires (always >= 1, rounded up for the
        Retry-After header).
        """
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            self._prune(hits, now)
            if len(hits) >= self.max_calls:
                retry_after = hits[0] + self.window_seconds - now
                return False, max(1.0, retry_after)
            hits.append(now)
            return True, 0.0


def _client_identity() -> str:
    """Best-effort identity for rate-limiting the current request.

    Keys off the signed-in user (``session["person_id"]``) so a logged-in
    viewer is limited across sessions/devices consistently. In open-access
    mode there is no user, so fall back to the remote address. Never raises:
    if there is somehow no request context info, everything collapses onto a
    single shared bucket, which fails safe (more limiting, not less).
    """
    person_id = session.get("person_id")
    if person_id:
        return f"user:{person_id}"
    addr = request.remote_addr or "unknown"
    return f"addr:{addr}"


def rate_limit(max_calls: int, window_seconds: float, *, name: str) -> Callable:
    """Decorator: rate-limit a Flask view per client identity.

    ``name`` namespaces the limiter so different endpoints don't share a
    bucket. On limit, returns HTTP 429 with the app's standard error envelope
    ``{"error": ..., "code": "rate_limited"}`` and a ``Retry-After`` header.
    """
    limiter = SlidingWindowLimiter(max_calls, window_seconds)

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{name}:{_client_identity()}"
            allowed, retry_after = limiter.check(key)
            if not allowed:
                retry = int(retry_after + 0.999)
                resp = jsonify(
                    {
                        "error": "rate limit exceeded, please slow down",
                        "code": "rate_limited",
                    }
                )
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry)
                return resp
            return f(*args, **kwargs)

        # Expose the limiter for tests / introspection.
        wrapper._rate_limiter = limiter  # type: ignore[attr-defined]
        return wrapper

    return decorator


class TTLCache:
    """Tiny thread-safe key→value cache with per-entry expiry.

    Used to avoid re-billing for repeat requests (e.g. AI summaries). Entries
    expire ``ttl_seconds`` after they are stored. The clock is injectable for
    deterministic tests.
    """

    def __init__(
        self,
        ttl_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        now = self._clock()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= now:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        expires_at = self._clock() + self.ttl_seconds
        with self._lock:
            self._store[key] = (expires_at, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
