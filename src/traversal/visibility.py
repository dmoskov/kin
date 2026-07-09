"""Relationship-visibility filtering — server-side enforcement of the
per-link privacy tags ("everyone" / "extended" / "self_and_children").

Every parent-child edge carries a ``visibility`` tag. This module decides,
for a given viewer, which edges that viewer is allowed to see, and drops the
rest before the data ever leaves the server. It mirrors the client-side
declutter logic in ``web/js/03-data-nav.js`` (``_kinCircles`` +
``applyVisibilityFilter``), which remains the semantics spec.

The circle computation is a pure function over parent→child edges so it can
be unit-tested independently of Flask and the database.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

# A parent→child edge as a ``(parent_id, child_id)`` pair.
Edge = tuple[str, str]


def _edge_maps(edges: Iterable[Edge]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build ``parents_of[child] -> [parents]`` and ``children_of[parent] -> [children]``."""
    parents_of: dict[str, list[str]] = defaultdict(list)
    children_of: dict[str, list[str]] = defaultdict(list)
    for parent_id, child_id in edges:
        parents_of[child_id].append(parent_id)
        children_of[parent_id].append(child_id)
    return parents_of, children_of


def compute_kin_circles(edges: Iterable[Edge], viewer_id: str | None) -> tuple[set[str], set[str]]:
    """Compute the viewer's ``(family, extended)`` kinship circles.

    * ``family`` = viewer + all direct ancestors + siblings (co-children of
      the viewer's parents) + own children + nieces/nephews (children of
      siblings).
    * ``extended`` = ``family`` + aunts/uncles (grandparents' other children)
      + their children (cousins).

    Mirrors ``_kinCircles()`` in ``web/js/03-data-nav.js``. Computed over the
    FULL edge set so hidden links still count toward ancestry when deciding
    the visibility of other links.
    """
    parents_of, children_of = _edge_maps(edges)

    def ps(pid: str) -> list[str]:
        return parents_of.get(pid, [])

    def cs(pid: str) -> list[str]:
        return children_of.get(pid, [])

    family: set[str] = {viewer_id} if viewer_id is not None else set()
    if viewer_id is None:
        return family, set(family)

    # Direct ancestors (walk parents up).
    frontier = [viewer_id]
    seen = {viewer_id}
    while frontier:
        nxt: list[str] = []
        for x in frontier:
            for p in ps(x):
                if p not in seen:
                    seen.add(p)
                    family.add(p)
                    nxt.append(p)
        frontier = nxt

    my_parents = ps(viewer_id)
    # Siblings (other children of my parents) and my own children.
    siblings: set[str] = set()
    for p in my_parents:
        for sib in cs(p):
            family.add(sib)
            if sib != viewer_id:
                siblings.add(sib)
    for ch in cs(viewer_id):
        family.add(ch)
    # Nieces/nephews (children of siblings).
    for sib in siblings:
        for n in cs(sib):
            family.add(n)

    # Extended = family + aunts/uncles (parents' siblings) + their children (cousins).
    extended = set(family)
    for p in my_parents:
        for gp in ps(p):
            for aunt_uncle in cs(gp):
                if aunt_uncle in my_parents:
                    continue
                extended.add(aunt_uncle)
                for cousin in cs(aunt_uncle):
                    extended.add(cousin)

    return family, extended


def is_link_visible(
    visibility: str,
    parent_id: str,
    child_id: str,
    family: set[str],
    extended: set[str],
) -> bool:
    """Return whether a single link is visible given the precomputed circles.

    Mirrors the filter rule in ``applyVisibilityFilter()``:
      * ``everyone``           → always visible.
      * ``self_and_children``  → an endpoint is in the family circle.
      * ``extended``           → an endpoint is in family or extended.
    Any unrecognised value is treated as visible (matches the JS default).
    """
    if visibility == "everyone":
        return True
    in_family = parent_id in family or child_id in family
    if visibility == "self_and_children":
        return in_family
    if visibility == "extended":
        return in_family or parent_id in extended or child_id in extended
    return True


def _visibility_str(rel: object) -> str:
    """Extract the visibility value from a Relationship object or dict row.

    Accepts a ``Visibility`` enum, a plain string, or a missing/None value
    (→ ``"everyone"``, the default tag).
    """
    if isinstance(rel, dict):
        v = rel.get("visibility")
    else:
        v = getattr(rel, "visibility", None)
    v = getattr(v, "value", v)  # unwrap enum → its string value
    return v or "everyone"


def filter_relationships(relationships: Iterable[object], viewer_id: str | None) -> list:
    """Return the subset of *relationships* visible to *viewer_id*.

    Each element must expose ``parent_id`` / ``child_id`` (attributes or dict
    keys) and, optionally, ``visibility``. The full set is used to compute the
    kin circles, so hidden links still count toward ancestry.
    """
    rels = list(relationships)

    def _get(r: object, field: str) -> str:
        return r[field] if isinstance(r, dict) else getattr(r, field)

    edges: list[Edge] = [(_get(r, "parent_id"), _get(r, "child_id")) for r in rels]
    family, extended = compute_kin_circles(edges, viewer_id)
    return [
        r
        for r in rels
        if is_link_visible(
            _visibility_str(r), _get(r, "parent_id"), _get(r, "child_id"), family, extended
        )
    ]
