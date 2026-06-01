"""Tests for the news article feature.

Covers:
  - NewsArticle model
  - Database CRUD for articles (repository layer)
  - Person-article linking
  - API endpoints: create, update, delete, list, link/unlink
  - Round-trip: create → GET /api/data includes articles
  - JSON import/export with articles
"""

from __future__ import annotations

import pytest

from models.article import NewsArticle
from models.person import Gender, Person
from models.tree import FamilyTree

# ── Model tests ──────────────────────────────────────────────────────────


class TestNewsArticleModel:
    def test_basic_creation(self):
        a = NewsArticle(id="test-1", title="Test Article")
        assert a.id == "test-1"
        assert a.title == "Test Article"
        assert a.url is None
        assert a.publication is None
        assert a.date is None
        assert a.summary == ""
        assert a.photo_url is None

    def test_full_creation(self):
        a = NewsArticle(
            id="nyt-2024",
            title="Local Hero",
            url="https://example.com/article",
            publication="New York Times",
            date="2024-03-15",
            summary="A story about a local hero.",
            photo_url="https://example.com/photo.jpg",
        )
        assert a.publication == "New York Times"
        assert a.date == "2024-03-15"

    def test_repr(self):
        a = NewsArticle(id="x", title="Headline", publication="NYT")
        assert "Headline" in repr(a)
        assert "NYT" in repr(a)

    def test_repr_no_publication(self):
        a = NewsArticle(id="x", title="Headline")
        assert "Headline" in repr(a)


# ── Database tests ───────────────────────────────────────────────────────


@pytest.fixture
def db_path(tmp_path):
    from database.connection import init_db

    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def repo(db_path):
    from database.repository import TreeRepository

    return TreeRepository(db_path)


def _make_article(**kwargs) -> NewsArticle:
    defaults = {"id": "art-1", "title": "Test Article"}
    defaults.update(kwargs)
    return NewsArticle(**defaults)


def _make_person(pid="p1", given="Alice", surname="Smith") -> Person:
    return Person(id=pid, given_name=given, surname=surname, gender=Gender.FEMALE)


class TestArticleRepository:
    def test_save_and_get(self, repo):
        a = _make_article(url="https://example.com", publication="Times")
        repo.save_article(a)
        got = repo.get_article("art-1")
        assert got is not None
        assert got.title == "Test Article"
        assert got.url == "https://example.com"
        assert got.publication == "Times"

    def test_get_nonexistent(self, repo):
        assert repo.get_article("nope") is None

    def test_upsert(self, repo):
        repo.save_article(_make_article(title="V1"))
        repo.save_article(_make_article(title="V2"))
        got = repo.get_article("art-1")
        assert got.title == "V2"

    def test_list_articles(self, repo):
        repo.save_article(_make_article(id="a1", title="First", date="2024-01"))
        repo.save_article(_make_article(id="a2", title="Second", date="2024-06"))
        articles = repo.list_articles()
        assert len(articles) == 2
        assert articles[0].title == "Second"

    def test_delete_article(self, repo):
        repo.save_article(_make_article())
        assert repo.delete_article("art-1") is True
        assert repo.get_article("art-1") is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete_article("nope") is False

    def test_link_and_articles_for_person(self, repo):
        repo.save_person(_make_person())
        repo.save_article(_make_article())
        repo.link_article_to_person("p1", "art-1")
        articles = repo.articles_for_person("p1")
        assert len(articles) == 1
        assert articles[0].id == "art-1"

    def test_link_idempotent(self, repo):
        repo.save_person(_make_person())
        repo.save_article(_make_article())
        repo.link_article_to_person("p1", "art-1")
        repo.link_article_to_person("p1", "art-1")
        articles = repo.articles_for_person("p1")
        assert len(articles) == 1

    def test_unlink(self, repo):
        repo.save_person(_make_person())
        repo.save_article(_make_article())
        repo.link_article_to_person("p1", "art-1")
        repo.unlink_article_from_person("p1", "art-1")
        assert repo.articles_for_person("p1") == []

    def test_people_for_article(self, repo):
        repo.save_person(_make_person("p1", "Alice", "Smith"))
        repo.save_person(_make_person("p2", "Bob", "Jones"))
        repo.save_article(_make_article())
        repo.link_article_to_person("p1", "art-1")
        repo.link_article_to_person("p2", "art-1")
        people = repo.people_for_article("art-1")
        assert len(people) == 2
        ids = {p["id"] for p in people}
        assert ids == {"p1", "p2"}

    def test_cascade_on_person_delete(self, repo):
        repo.save_person(_make_person())
        repo.save_article(_make_article())
        repo.link_article_to_person("p1", "art-1")
        repo.delete_person("p1")
        people = repo.people_for_article("art-1")
        assert len(people) == 0

    def test_cascade_on_article_delete(self, repo):
        repo.save_person(_make_person())
        repo.save_article(_make_article())
        repo.link_article_to_person("p1", "art-1")
        repo.delete_article("art-1")
        articles = repo.articles_for_person("p1")
        assert len(articles) == 0

    def test_stats_includes_articles(self, repo):
        repo.save_article(_make_article())
        s = repo.stats()
        assert s["articles"] == 1


class TestArticleInTree:
    def test_save_and_load_tree_with_articles(self, repo):
        person = _make_person()
        repo.save_person(person)
        art = _make_article(publication="Times", date="2024-01")
        repo.save_article(art)
        repo.link_article_to_person("p1", "art-1")

        tree = repo.load_tree()
        assert "art-1" in tree.articles
        loaded = tree.articles["art-1"]
        assert loaded.title == "Test Article"
        assert loaded.publication == "Times"
        assert "p1" in tree.person_article_links
        assert "art-1" in tree.person_article_links["p1"]

    def test_save_tree_bulk_with_articles(self, repo):
        tree = FamilyTree()
        tree.add_person(_make_person())
        tree.add_article(_make_article())
        tree.add_person_article_link("p1", "art-1")
        repo.save_tree(tree)

        loaded = repo.load_tree()
        assert "art-1" in loaded.articles
        assert "art-1" in loaded.person_article_links.get("p1", set())


# ── JSON I/O tests ───────────────────────────────────────────────────────


class TestArticleJsonIO:
    def test_article_to_dict(self):
        from import_export.json_io import _article_to_dict

        a = _make_article(url="https://ex.com", publication="Times")
        d = _article_to_dict(a, ["p1", "p2"])
        assert d["id"] == "art-1"
        assert d["title"] == "Test Article"
        assert d["url"] == "https://ex.com"
        assert d["person_ids"] == ["p1", "p2"]

    def test_article_to_dict_minimal(self):
        from import_export.json_io import _article_to_dict

        a = NewsArticle(id="x", title="Bare")
        d = _article_to_dict(a)
        assert "url" not in d
        assert "publication" not in d
        assert "person_ids" not in d

    def test_round_trip_json(self, tmp_path):
        from import_export.json_io import load_tree, save_tree

        tree = FamilyTree()
        tree.add_person(_make_person())
        art = _make_article(url="https://ex.com", publication="Times", date="2024")
        tree.add_article(art)
        tree.add_person_article_link("p1", "art-1")

        path = str(tmp_path / "tree.json")
        save_tree(tree, path)

        loaded = load_tree(path)
        assert "art-1" in loaded.articles
        assert loaded.articles["art-1"].publication == "Times"
        assert "art-1" in loaded.person_article_links.get("p1", set())


# ── API tests ────────────────────────────────────────────────────────────


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("FAMILY_TREE_DB", db_path)

    from database.connection import init_db

    init_db(db_path)

    import importlib

    import web_server

    importlib.reload(web_server)
    web_server.PRIVATE_DIR = tmp_path
    web_server.app.config["TESTING"] = True

    from database.repository import TreeRepository

    repo = TreeRepository(db_path)
    repo.save_person(_make_person("p1", "Alice", "Smith"))
    repo.save_person(_make_person("p2", "Bob", "Jones"))

    with web_server.app.test_client() as client:
        yield client


class TestArticleAPI:
    def test_create_article(self, app_client):
        rv = app_client.post(
            "/api/articles",
            json={
                "title": "Famous Person",
                "url": "https://news.example.com/story",
                "publication": "Daily News",
                "date": "2024-06-15",
                "person_ids": ["p1"],
            },
        )
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["title"] == "Famous Person"
        assert data["url"] == "https://news.example.com/story"
        assert "p1" in data.get("person_ids", [])

    def test_create_article_missing_title(self, app_client):
        rv = app_client.post("/api/articles", json={"url": "https://example.com"})
        assert rv.status_code == 400

    def test_create_article_explicit_id(self, app_client):
        rv = app_client.post("/api/articles", json={"id": "my-art-1", "title": "Test"})
        assert rv.status_code == 201
        assert rv.get_json()["id"] == "my-art-1"

    def test_create_article_conflict(self, app_client):
        app_client.post("/api/articles", json={"id": "dup", "title": "First"})
        rv = app_client.post("/api/articles", json={"id": "dup", "title": "Second"})
        assert rv.status_code == 409

    def test_get_article(self, app_client):
        app_client.post("/api/articles", json={"id": "g1", "title": "Get Me"})
        rv = app_client.get("/api/articles/g1")
        assert rv.status_code == 200
        assert rv.get_json()["title"] == "Get Me"

    def test_get_article_not_found(self, app_client):
        rv = app_client.get("/api/articles/nope")
        assert rv.status_code == 404

    def test_update_article(self, app_client):
        app_client.post("/api/articles", json={"id": "u1", "title": "Original"})
        rv = app_client.put(
            "/api/articles/u1",
            json={"title": "Updated", "publication": "Times"},
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["title"] == "Updated"
        assert data["publication"] == "Times"

    def test_update_article_not_found(self, app_client):
        rv = app_client.put("/api/articles/nope", json={"title": "X"})
        assert rv.status_code == 404

    def test_update_article_empty_title(self, app_client):
        app_client.post("/api/articles", json={"id": "u2", "title": "OK"})
        rv = app_client.put("/api/articles/u2", json={"title": ""})
        assert rv.status_code == 400

    def test_update_article_person_ids(self, app_client):
        app_client.post(
            "/api/articles",
            json={"id": "u3", "title": "Link", "person_ids": ["p1"]},
        )
        rv = app_client.put("/api/articles/u3", json={"person_ids": ["p1", "p2"]})
        data = rv.get_json()
        assert set(data["person_ids"]) == {"p1", "p2"}

        rv = app_client.put("/api/articles/u3", json={"person_ids": ["p2"]})
        data = rv.get_json()
        assert data["person_ids"] == ["p2"]

    def test_delete_article(self, app_client):
        app_client.post("/api/articles", json={"id": "d1", "title": "Delete Me"})
        rv = app_client.delete("/api/articles/d1")
        assert rv.status_code == 204

        rv = app_client.get("/api/articles/d1")
        assert rv.status_code == 404

    def test_delete_article_not_found(self, app_client):
        rv = app_client.delete("/api/articles/nope")
        assert rv.status_code == 404

    def test_list_articles(self, app_client):
        app_client.post("/api/articles", json={"id": "l1", "title": "One"})
        app_client.post("/api/articles", json={"id": "l2", "title": "Two"})
        rv = app_client.get("/api/articles")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data) == 2

    def test_person_articles(self, app_client):
        app_client.post(
            "/api/articles",
            json={"id": "pa1", "title": "About Alice", "person_ids": ["p1"]},
        )
        rv = app_client.get("/api/people/p1/articles")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data) == 1
        assert data[0]["id"] == "pa1"

    def test_person_articles_not_found(self, app_client):
        rv = app_client.get("/api/people/nope/articles")
        assert rv.status_code == 404

    def test_link_article_to_person(self, app_client):
        app_client.post("/api/articles", json={"id": "lk1", "title": "Link Test"})
        rv = app_client.post("/api/people/p2/articles", json={"article_id": "lk1"})
        assert rv.status_code == 201

        rv = app_client.get("/api/people/p2/articles")
        data = rv.get_json()
        assert any(a["id"] == "lk1" for a in data)

    def test_link_article_missing_article(self, app_client):
        rv = app_client.post("/api/people/p1/articles", json={"article_id": "nope"})
        assert rv.status_code == 404

    def test_link_article_missing_person(self, app_client):
        app_client.post("/api/articles", json={"id": "lk2", "title": "Test"})
        rv = app_client.post("/api/people/nope/articles", json={"article_id": "lk2"})
        assert rv.status_code == 404

    def test_unlink_article_from_person(self, app_client):
        app_client.post(
            "/api/articles",
            json={"id": "ul1", "title": "Unlink", "person_ids": ["p1"]},
        )
        rv = app_client.delete("/api/people/p1/articles/ul1")
        assert rv.status_code == 204

        rv = app_client.get("/api/people/p1/articles")
        assert rv.get_json() == []

    def test_articles_in_api_data(self, app_client):
        app_client.post(
            "/api/articles",
            json={
                "id": "data-art",
                "title": "In Data",
                "person_ids": ["p1"],
            },
        )
        rv = app_client.get("/api/data")
        data = rv.get_json()
        assert "articles" in data
        arts = [a for a in data["articles"] if a["id"] == "data-art"]
        assert len(arts) == 1
        assert arts[0]["title"] == "In Data"
        assert "p1" in arts[0].get("person_ids", [])
