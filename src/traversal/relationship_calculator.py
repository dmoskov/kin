"""Relationship calculator — compute English relationship labels between two people.

Given two person IDs, finds the Lowest Common Ancestor (LCA) and derives the
relationship label (parent, grandparent, cousin, uncle/aunt, etc.).
"""

from __future__ import annotations

import re
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


def find_common_ancestors(tree: FamilyTree, id_a: str, id_b: str) -> list[tuple[str, int, int]]:
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
        if ancestor_gender == "male":
            return "father"
        if ancestor_gender == "female":
            return "mother"
        return "parent"
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
        if descendant_gender == "male":
            return "son"
        if descendant_gender == "female":
            return "daughter"
        return "child"
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


def _blood_label(tree: FamilyTree, id_a: str, id_b: str) -> str | None:
    """Return the blood-only relationship label of B relative to A, or None."""
    common = find_common_ancestors(tree, id_a, id_b)
    if not common:
        return None

    _ancestor_id, dist_a, dist_b = common[0]
    person_b = tree.get_person(id_b)
    gender_b = person_b.gender.value if person_b else "unknown"

    if dist_a == 0:
        return _direct_descendant_label(dist_b, gender_b)
    if dist_b == 0:
        return _direct_ancestor_label(dist_a, gender_b)

    if dist_a == 1 and dist_b == 1:
        return "brother" if gender_b == "male" else "sister" if gender_b == "female" else "sibling"

    if dist_a == 1 and dist_b == 2:
        return (
            "nephew" if gender_b == "male" else "niece" if gender_b == "female" else "niece/nephew"
        )
    if dist_a == 2 and dist_b == 1:
        return "uncle" if gender_b == "male" else "aunt" if gender_b == "female" else "uncle/aunt"

    if dist_b == 1 and dist_a > 2:
        prefix = _greats(dist_a - 2)
        return (
            f"{prefix}grand-uncle"
            if gender_b == "male"
            else f"{prefix}grand-aunt"
            if gender_b == "female"
            else f"{prefix}grand-uncle/aunt"
        )
    if dist_a == 1 and dist_b > 2:
        prefix = _greats(dist_b - 2)
        return (
            f"{prefix}grand-nephew"
            if gender_b == "male"
            else f"{prefix}grand-niece"
            if gender_b == "female"
            else f"{prefix}grand-niece/nephew"
        )

    degree = min(dist_a, dist_b) - 1
    removed = abs(dist_a - dist_b)
    label = f"{_ordinal(degree)} cousin"
    if removed > 0:
        label += f" {_times_removed(removed)}"
    return label


_IN_LAW_MAP = {
    "father": "father-in-law",
    "mother": "mother-in-law",
    "parent": "parent-in-law",
    "brother": "brother-in-law",
    "sister": "sister-in-law",
    "sibling": "sibling-in-law",
    "grandfather": "grandfather-in-law",
    "grandmother": "grandmother-in-law",
    "grandparent": "grandparent-in-law",
    "uncle": "uncle-in-law",
    "aunt": "aunt-in-law",
    "uncle/aunt": "uncle/aunt-in-law",
    "nephew": "nephew-in-law",
    "niece": "niece-in-law",
    "niece/nephew": "niece/nephew-in-law",
}


def _to_in_law(lbl: str) -> str | None:
    if lbl in _IN_LAW_MAP:
        return _IN_LAW_MAP[lbl]
    if "cousin" in lbl:
        return lbl + "-in-law"
    if re.search(r"great-.*grand(father|mother|parent)", lbl):
        return lbl + "-in-law"
    return None


def _reverse_in_law(lbl: str, gender_b: str) -> str | None:
    """B is the spouse of someone who is A's [lbl] → what is B to A?"""
    if lbl in ("son", "daughter", "child"):
        return (
            "son-in-law"
            if gender_b == "male"
            else "daughter-in-law"
            if gender_b == "female"
            else "child-in-law"
        )
    if lbl in ("brother", "sister", "sibling"):
        return (
            "brother-in-law"
            if gender_b == "male"
            else "sister-in-law"
            if gender_b == "female"
            else "sibling-in-law"
        )
    if lbl in ("grandson", "granddaughter", "grandchild"):
        return (
            "grandson-in-law"
            if gender_b == "male"
            else "granddaughter-in-law"
            if gender_b == "female"
            else "grandchild-in-law"
        )
    return None


def _spouse_word(gender: str) -> str:
    """Return the word for how a person of *gender* refers to their spouse.

    A male person's spouse is his 'wife'; a female person's spouse is her 'husband'.
    """
    return "wife" if gender == "male" else "husband" if gender == "female" else "spouse"


def describe_relationship(tree: FamilyTree, id_a: str, id_b: str) -> str:
    """Return the English relationship label of person B *relative to* person A.

    Covers blood relations, direct spouses, and in-law relationships (parent-in-law,
    child-in-law, sibling-in-law, and co-in-law e.g. "wife's sister's husband").

    Returns 'self' when id_a == id_b, and 'no relation found' when no path exists.
    """
    if id_a == id_b:
        return "self"

    # 1. Blood relation
    blood = _blood_label(tree, id_a, id_b)
    if blood:
        return blood

    person_a = tree.get_person(id_a)
    person_b = tree.get_person(id_b)
    gender_a = person_a.gender.value if person_a else "unknown"
    gender_b = person_b.gender.value if person_b else "unknown"

    spouses_a = [p.id for p in tree.partners_of(id_a)]
    spouses_b = [p.id for p in tree.partners_of(id_b)]

    # 2. Direct spouse / ex-spouse
    if id_b in spouses_a:
        union = tree.union_between(id_a, id_b)
        is_ex = union is not None and union.end_date is not None
        if is_ex:
            return (
                "ex-husband"
                if gender_b == "male"
                else "ex-wife"
                if gender_b == "female"
                else "ex-spouse"
            )
        return "husband" if gender_b == "male" else "wife" if gender_b == "female" else "spouse"

    # 3. B is A's spouse's blood relative → in-law
    for s_a in spouses_a:
        lbl = _blood_label(tree, s_a, id_b)
        if lbl:
            in_law = _to_in_law(lbl)
            if in_law:
                return in_law

    # 4. A is B's spouse's blood relative → reverse in-law
    for s_b in spouses_b:
        lbl = _blood_label(tree, id_a, s_b)
        if lbl:
            in_law = _reverse_in_law(lbl, gender_b)
            if in_law:
                return in_law

    # 5. A's spouse's blood relative is B's spouse → co-in-law
    for s_a in spouses_a:
        for s_b in spouses_b:
            lbl = _blood_label(tree, s_a, s_b)
            if lbl:
                # w_a: how A refers to their own spouse (male→"wife", female→"husband")
                w_a = _spouse_word(gender_a)
                # w_b: what B is called in their marriage (male→"husband", female→"wife")
                w_b = (
                    "husband"
                    if gender_b == "male"
                    else "wife"
                    if gender_b == "female"
                    else "spouse"
                )
                return f"{w_a}'s {lbl}'s {w_b}"

    return "no relation found"
