"""Tests for server-side relationship-visibility filtering.

Two layers:
  1. Unit tests for ``traversal.visibility.compute_kin_circles`` — mirror the
     JS ``_kinCircles`` semantics (ancestors, siblings, nieces/nephews,
     aunts/uncles, cousins, and someone outside all circles).
  2. HTTP tests for the endpoints that return relationship rows
     (``/api/data`` and ``/api/export/gedcom``): an ordinary viewer never
     receives a "self_and_children" link between strangers, always receives
     their own, admins/editors receive everything, and open access is
     unfiltered.
"""

from __future__ import annotations

import importlib

from models.person import Gender, Person
from models.relationship import Relationship, Union, Visibility
from traversal.visibility import compute_kin_circles, filter_relationships

# ── Unit tests: kin-circle computation ────────────────────────────────────


# A small fixed graph shared by the unit tests.
#
#           gp                (grandparent)
#          /  \
#         p    au             (parent, aunt/uncle)
#        / \    \
#       v  sib  cous          (viewer, sibling, cousin)
#      /     \
#     ch     nib              (child, niece/nephew)
#
# plus a completely disconnected pair s1 -> s2 (strangers).
_EDGES = [
    ("gp", "p"),
    ("gp", "au"),
    ("p", "v"),
    ("p", "sib"),
    ("au", "cous"),
    ("v", "ch"),
    ("sib", "nib"),
    ("s1", "s2"),
]


class TestKinCircles:
    def test_family_contains_ancestors(self):
        family, _ = compute_kin_circles(_EDGES, "v")
        assert "p" in family
        assert "gp" in family

    def test_family_contains_siblings_and_children(self):
        family, _ = compute_kin_circles(_EDGES, "v")
        assert "sib" in family  # sibling (co-child of p)
        assert "ch" in family  # own child

    def test_family_contains_nieces_nephews(self):
        family, _ = compute_kin_circles(_EDGES, "v")
        assert "nib" in family  # child of a sibling

    def test_family_excludes_aunts_uncles_and_cousins(self):
        family, _ = compute_kin_circles(_EDGES, "v")
        assert "au" not in family
        assert "cous" not in family

    def test_extended_contains_aunts_uncles_and_cousins(self):
        family, extended = compute_kin_circles(_EDGES, "v")
        assert "au" in extended  # grandparent's other child
        assert "cous" in extended  # aunt/uncle's child
        # Extended is a superset of family.
        assert family <= extended

    def test_strangers_in_no_circle(self):
        family, extended = compute_kin_circles(_EDGES, "v")
        for outsider in ("s1", "s2"):
            assert outsider not in family
            assert outsider not in extended

    def test_none_viewer_yields_empty_circles(self):
        family, extended = compute_kin_circles(_EDGES, None)
        assert family == set()
        assert extended == set()


class TestFilterRelationships:
    def _rel(self, parent, child, vis):
        return Relationship(parent_id=parent, child_id=child, visibility=vis)

    def test_everyone_links_always_kept(self):
        rels = [self._rel("s1", "s2", Visibility.EVERYONE)]
        kept = filter_relationships(rels, "v")
        assert len(kept) == 1

    def test_self_and_children_between_strangers_dropped(self):
        rels = [self._rel("s1", "s2", Visibility.SELF_AND_CHILDREN)]
        kept = filter_relationships(rels, "v")
        assert kept == []

    def test_self_and_children_own_family_kept(self):
        # p -> v is needed so the circle knows v's parent; the sibling link
        # p -> sib is self_and_children and must stay visible to v.
        rels = [
            self._rel("p", "v", Visibility.EVERYONE),
            self._rel("p", "sib", Visibility.SELF_AND_CHILDREN),
        ]
        kept = filter_relationships(rels, "v")
        assert self._rel("p", "sib", Visibility.SELF_AND_CHILDREN) in kept

    def test_extended_link_to_cousin_kept(self):
        rels = [
            self._rel("gp", "p", Visibility.EVERYONE),
            self._rel("p", "v", Visibility.EVERYONE),
            self._rel("gp", "au", Visibility.EXTENDED),
            self._rel("au", "cous", Visibility.EXTENDED),
        ]
        kept = filter_relationships(rels, "v")
        pairs = {(r.parent_id, r.child_id) for r in kept}
        assert ("gp", "au") in pairs
        assert ("au", "cous") in pairs

    def test_extended_link_between_strangers_dropped(self):
        rels = [self._rel("s1", "s2", Visibility.EXTENDED)]
        kept = filter_relationships(rels, "v")
        assert kept == []


# ── HTTP tests ────────────────────────────────────────────────────────────


def _make_client(tmp_path, monkeypatch, *, open_access: bool = False):
    """Return (client, app) with a populated tree.

    Auth is gated by default (GOOGLE_CLIENT_ID set) so the visibility filter
    engages; pass ``open_access=True`` to exercise the unfiltered path.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)
    monkeypatch.delenv("EDITORS", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("ADMIN_PERSON_ID", "admin_person")
    if open_access:
        monkeypatch.setenv("ALLOW_OPEN_ACCESS", "1")
    else:
        monkeypatch.delenv("ALLOW_OPEN_ACCESS", raising=False)

    from database.connection import init_db

    init_db(db_path)

    import web_server

    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True
    web_server.app.config["SECRET_KEY"] = "test-secret"

    from database.repository import TreeRepository

    repo = TreeRepository(db_path)
    people = {
        "gp": "Grandparent",
        "p": "Parent",
        "ps": "OtherParent",
        "v": "Viewer",
        "sib": "Sibling",
        "ch": "Child",
        "nib": "Nibling",
        "au": "AuntUncle",
        "cous": "Cousin",
        "s1": "StrangerOne",
        "s2": "StrangerTwo",
        "sc": "StrangerChild",
        "admin_person": "Admin",
    }
    for pid, name in people.items():
        repo.save_person(Person(id=pid, given_name=name, surname="X", gender=Gender.UNKNOWN))

    E = Visibility.EVERYONE
    SAC = Visibility.SELF_AND_CHILDREN
    EXT = Visibility.EXTENDED
    rels = [
        ("p", "v", E),
        ("ps", "v", E),
        ("p", "sib", SAC),
        ("ps", "sib", SAC),
        ("gp", "p", E),
        ("gp", "au", EXT),
        ("au", "cous", EXT),
        ("v", "ch", E),
        ("sib", "nib", E),
        ("s1", "sc", SAC),
        ("s2", "sc", SAC),
    ]
    for parent, child, vis in rels:
        repo.save_relationship(Relationship(parent_id=parent, child_id=child, visibility=vis))
    repo.save_union(Union(partner1_id="p", partner2_id="ps"))
    repo.save_union(Union(partner1_id="s1", partner2_id="s2"))

    return web_server.app.test_client(), web_server.app


def _sign_in(client, person_id, *, is_editor=False):
    with client.session_transaction() as sess:
        sess["person_id"] = person_id
        sess["email"] = f"{person_id}@example.com"
        sess["is_editor"] = is_editor


def _pairs(data):
    return {(r["parent_id"], r["child_id"]) for r in data["relationships"]}


class TestApiDataFiltering:
    def test_viewer_does_not_receive_stranger_link(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch)
        _sign_in(client, "v")
        pairs = _pairs(client.get("/api/data").get_json())
        assert ("s1", "sc") not in pairs
        assert ("s2", "sc") not in pairs

    def test_viewer_receives_own_and_sibling_and_extended(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch)
        _sign_in(client, "v")
        pairs = _pairs(client.get("/api/data").get_json())
        assert ("p", "v") in pairs  # own parent
        assert ("p", "sib") in pairs  # sibling (self_and_children)
        assert ("gp", "au") in pairs  # aunt/uncle (extended)
        assert ("au", "cous") in pairs  # cousin (extended)

    def test_viewer_with_no_relationships_sees_only_everyone(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch)
        # A logged-in person with no relationship edges (not admin/editor).
        _sign_in(client, "nobody")
        pairs = _pairs(client.get("/api/data").get_json())
        # All self_and_children / extended links are hidden.
        assert ("p", "sib") not in pairs
        assert ("s1", "sc") not in pairs
        assert ("gp", "au") not in pairs
        # "everyone" links remain.
        assert ("p", "v") in pairs

    def test_admin_receives_everything(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch)
        _sign_in(client, "admin_person")
        pairs = _pairs(client.get("/api/data").get_json())
        assert ("s1", "sc") in pairs
        assert ("s2", "sc") in pairs
        assert ("p", "sib") in pairs

    def test_editor_receives_everything(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch)
        _sign_in(client, "editor:someone@example.com", is_editor=True)
        pairs = _pairs(client.get("/api/data").get_json())
        assert ("s1", "sc") in pairs
        assert ("p", "sib") in pairs

    def test_open_access_unfiltered(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch, open_access=True)
        # No sign-in at all — open access serves everything.
        pairs = _pairs(client.get("/api/data").get_json())
        assert ("s1", "sc") in pairs
        assert ("p", "sib") in pairs


class TestGedcomExportFiltering:
    def test_viewer_export_omits_stranger_children(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch)
        _sign_in(client, "v")
        text = client.get("/api/export/gedcom").get_data(as_text=True)
        # The strangers' child link is hidden → no CHIL pointer for it.
        assert "1 CHIL @sc@" not in text
        # The viewer's own family still lists them as a child.
        assert "1 CHIL @v@" in text
        # And the sibling (self_and_children, visible to v) too.
        assert "1 CHIL @sib@" in text

    def test_admin_export_includes_stranger_children(self, tmp_path, monkeypatch):
        client, _ = _make_client(tmp_path, monkeypatch)
        _sign_in(client, "admin_person")
        text = client.get("/api/export/gedcom").get_data(as_text=True)
        assert "1 CHIL @sc@" in text
