"""Relationship calculator — compute English relationship labels between two people.

Given two person IDs, finds the Lowest Common Ancestor (LCA) and derives the
relationship label (parent, grandparent, cousin, uncle/aunt, etc.).
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.tree import FamilyTree


def _ancestors_with_distance(tree: FamilyTree, person_id: str) -> dict[str, int]:
    """BFS upward from *person_id*, returning {ancestor_id: min_distance}.

    Distance 0 = the person themselves.
    """
    dist: dict[str, int] = {person_id: 0}
    queue: deque[str] = deque([person_id])
    while queue:
        current = queue.popleft()
        for parent in tree.parents_of(current):
            if parent.id not in dist:
                dist[parent.id] = dist[current] + 1
                queue.append(parent.id)
    return dist


def find_common_ancestors(
    tree: FamilyTree, id_a: str, id_b: str
) -> list[tuple[str, int, int]]:
    """Return common ancestors of *id_a* and *id_b*.

    Each entry is ``(ancestor_id, dist_a, dist_b)`` where *dist_a* / *dist_b*
    are the generation distances from that ancestor to person A / B.

    Results are sorted by total distance (closest common ancestor first).
    """
    ancestors_a = _ancestors_with_distance(tree, id_a)
    ancestors_b = _ancestors_with_distance(tree, id_b)
    common = set(ancestors_a) & set(ancestors_b)
    result = [(cid, ancestors_a[cid], ancestors_b[cid]) for cid in common]
    result.sort(key=lambda t: t[1] + t[2])
    return result


def _ordinal(n: int) -> str:
    """Return ordinal string: 1→'first', 2→'second', 3→'third', etc."""
    names = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
    }
    return names.get(n, f"{n}th")


def _times_removed(n: int) -> str:
    if n == 1:
        return "once removed"
    if n == 2:
        return "twice removed"
    return f"{n} times removed"


def _greats(n: int) -> str:
    """Return the correct number of 'great-' prefixes."""
    return "great-" * n


def _direct_ancestor_label(generations: int, ancestor_gender: str) -> str:
    """Label when A is a direct ancestor of B (A → … → B).

    *generations* is the number of steps from ancestor to descendant.
    *ancestor_gender* is 'male', 'female', or 'unknown'.
    """
    if generations == 1:
        return (
            "parent"
            if ancestor_gender == "unknown"
            else ("father" if ancestor_gender == "male" else "mother")
        )
    if generations == 2:
        if ancestor_gender == "male":
            return "grandfather"
        if ancestor_gender == "female":
            return "grandmother"
        return "grandparent"
    # 3+ generations
    prefix = _greats(generations - 2)
    if ancestor_gender == "male":
        return f"{prefix}grandfather"
    if ancestor_gender == "female":
        return f"{prefix}grandmother"
    return f"{prefix}grandparent"


def _direct_descendant_label(generations: int, descendant_gender: str) -> str:
    """Label when A is a direct descendant of B (B → … → A).

    *generations* is the number of steps from ancestor to descendant.
    """
    if generations == 1:
        return (
            "child"
            if descendant_gender == "unknown"
            else ("son" if descendant_gender == "male" else "daughter")
        )
    if generations == 2:
        if descendant_gender == "male":
            return "grandson"
        if descendant_gender == "female":
            return "granddaughter"
        return "grandchild"
    prefix = _greats(generations - 2)
    if descendant_gender == "male":
        return f"{prefix}grandson"
    if descendant_gender == "female":
        return f"{prefix}granddaughter"
    return f"{prefix}grandchild"


def describe_relationship(tree: FamilyTree, id_a: str, id_b: str) -> str:
    """Return the English relationship label of person B *relative to* person A.

    Examples (read as "B is A's ___"):
      - describe_relationship(tree, parent_id, child_id) → 'son' / 'daughter' / 'child'
      - describe_relationship(tree, child_id, parent_id) → 'father' / 'mother' / 'parent'
      - describe_relationship(tree, uncle_id, niece_id) → 'niece' / 'nephew'

    Returns 'self' when id_a == id_b, and 'no relation found' when there is
    no common ancestor.
    """
    if id_a == id_b:
        return "self"

    common = find_common_ancestors(tree, id_a, id_b)
    if not common:
        return "no relation found"

    # Use the closest common ancestor (lowest total distance).
    _ancestor_id, dist_a, dist_b = common[0]

    person_b = tree.get_person(id_b)
    gender_b = person_b.gender.value if person_b else "unknown"

    # --- Direct line (one distance is 0) ---
    if dist_a == 0:
        # A is the ancestor → B is A's descendant
        return _direct_descendant_label(dist_b, gender_b)
    if dist_b == 0:
        # B is the ancestor → B is A's ancestor
        return _direct_ancestor_label(dist_a, gender_b)

    # --- Siblings (both at distance 1 from common ancestor) ---
    if dist_a == 1 and dist_b == 1:
        if gender_b == "male":
            return "brother"
        if gender_b == "female":
            return "sister"
        return "sibling"

    # --- Uncle/aunt or niece/nephew ---
    if dist_a == 1 and dist_b == 2:
        # B is child of A's sibling → B is A's niece/nephew
        if gender_b == "male":
            return "nephew"
        if gender_b == "female":
            return "niece"
        return "niece/nephew"
    if dist_a == 2 and dist_b == 1:
        # A is child of B's sibling → B is A's uncle/aunt
        if gender_b == "male":
            return "uncle"
        if gender_b == "female":
            return "aunt"
        return "uncle/aunt"

    # --- Great-uncle / great-aunt / grand-niece / grand-nephew ---
    if dist_b == 1 and dist_a > 2:
        prefix = _greats(dist_a - 2)
        if gender_b == "male":
            return f"{prefix}grand-uncle"
        if gender_b == "female":
            return f"{prefix}grand-aunt"
        return f"{prefix}grand-uncle/aunt"
    if dist_a == 1 and dist_b > 2:
        prefix = _greats(dist_b - 2)
        if gender_b == "male":
            return f"{prefix}grand-nephew"
        if gender_b == "female":
            return f"{prefix}grand-niece"
        return f"{prefix}grand-niece/nephew"

    # --- Cousins ---
    # degree = min(dist_a, dist_b) - 1, removed = |dist_a - dist_b|
    degree = min(dist_a, dist_b) - 1
    removed = abs(dist_a - dist_b)
    label = f"{_ordinal(degree)} cousin"
    if removed > 0:
        label += f" {_times_removed(removed)}"
    return label
