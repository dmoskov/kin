"""Tests for apply-time relationship validation (prevents the grandparent-as-
parent corruption that mislabeled relatives when documents were mis-parsed)."""

from collections import defaultdict

import web_server  # noqa: F401  (import first so routes package initializes cleanly)
from routes.documents import _validate_relationship_edge


def _pm(edges):
    """Build a child_id -> {parent_ids} map from (parent, child) tuples."""
    d = defaultdict(set)
    for p, c in edges:
        d[c].add(p)
    return d


def test_self_loop_rejected():
    ok, why = _validate_relationship_edge(defaultdict(set), "x", "x")
    assert not ok and "self-loop" in why


def test_grandparent_as_parent_rejected():
    # gp -> p -> c exists; adding gp -> c directly is a grandparent-as-parent edge
    ok, why = _validate_relationship_edge(_pm([("gp", "p"), ("p", "c")]), "gp", "c")
    assert not ok and "ancestor" in why


def test_cycle_rejected():
    # p -> c exists; adding c -> p would make a cycle
    ok, why = _validate_relationship_edge(_pm([("p", "c")]), "c", "p")
    assert not ok and "cycle" in why


def test_third_parent_rejected():
    ok, why = _validate_relationship_edge(_pm([("a", "c"), ("b", "c")]), "d", "c")
    assert not ok and "two parents" in why


def test_valid_edge_accepted():
    ok, _why = _validate_relationship_edge(_pm([("gp", "p")]), "p", "c")
    assert ok
