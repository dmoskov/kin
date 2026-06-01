"""News article CRUD and person-article linking endpoints."""

import uuid

from flask import Blueprint, jsonify, request

import web_server
from database.repository import TreeRepository
from import_export.json_io import _article_to_dict

articles_bp = Blueprint("articles", __name__)


@articles_bp.route("/api/articles", methods=["POST"])
@web_server.require_editor
def api_create_article():
    """Create a news article and optionally link it to people.

    Body: {"title": "...", "url": "...", "publication": "...", "date": "...",
           "summary": "...", "photo_url": "...", "person_ids": ["..."]}

    Returns 201 with the created article on success.
    """
    from models.article import NewsArticle

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required", "code": "bad_request"}), 400

    article_id = body.get("id", "").strip() if isinstance(body.get("id"), str) else ""
    if not article_id:
        article_id = f"article_{uuid.uuid4().hex[:12]}"

    repo = TreeRepository()
    if repo.get_article(article_id) is not None:
        return jsonify(
            {"error": f"article id already exists: {article_id}", "code": "conflict"}
        ), 409

    url = (body.get("url") or "").strip() or None
    publication = (body.get("publication") or "").strip() or None
    date = (body.get("date") or "").strip() or None
    summary = (body.get("summary") or "").strip()
    photo_url = (body.get("photo_url") or "").strip() or None

    article = NewsArticle(
        id=article_id,
        title=title,
        url=url,
        publication=publication,
        date=date,
        summary=summary,
        photo_url=photo_url,
    )
    repo.save_article(article)

    person_ids = body.get("person_ids", [])
    if isinstance(person_ids, list):
        for pid in person_ids:
            pid = (pid or "").strip()
            if pid and repo.get_person(pid):
                repo.link_article_to_person(pid, article_id)

    linked_people = repo.people_for_article(article_id)
    result = _article_to_dict(article, [p["id"] for p in linked_people])
    return jsonify(result), 201


@articles_bp.route("/api/articles/<article_id>", methods=["PUT", "PATCH"])
@web_server.require_editor
def api_update_article(article_id):
    """Update an existing article.

    Body: JSON with any subset of article fields. Fields not included are
    left unchanged.

    Returns 200 with the updated article, 404 if not found.
    """
    body = request.get_json(silent=True) or {}
    repo = TreeRepository()
    existing = repo.get_article(article_id)
    if existing is None:
        return jsonify({"error": "article not found", "code": "not_found"}), 404

    if "title" in body:
        title = (body["title"] or "").strip()
        if not title:
            return jsonify(
                {"error": "title cannot be empty", "code": "bad_request"}
            ), 400
        existing.title = title
    if "url" in body:
        existing.url = (body["url"] or "").strip() or None
    if "publication" in body:
        existing.publication = (body["publication"] or "").strip() or None
    if "date" in body:
        existing.date = (body["date"] or "").strip() or None
    if "summary" in body:
        existing.summary = (body["summary"] or "").strip()
    if "photo_url" in body:
        existing.photo_url = (body["photo_url"] or "").strip() or None

    repo.save_article(existing)

    if "person_ids" in body:
        current_people = repo.people_for_article(article_id)
        current_pids = {p["id"] for p in current_people}
        new_pids = set()
        for pid in body["person_ids"]:
            pid = (pid or "").strip()
            if pid:
                new_pids.add(pid)

        for pid in new_pids - current_pids:
            if repo.get_person(pid):
                repo.link_article_to_person(pid, article_id)
        for pid in current_pids - new_pids:
            repo.unlink_article_from_person(pid, article_id)

    linked_people = repo.people_for_article(article_id)
    return jsonify(_article_to_dict(existing, [p["id"] for p in linked_people]))


@articles_bp.route("/api/articles/<article_id>", methods=["DELETE"])
@web_server.require_editor
def api_delete_article(article_id):
    """Delete a news article and its person links.

    Returns 204 on success, 404 if not found.
    """
    repo = TreeRepository()
    if repo.get_article(article_id) is None:
        return jsonify({"error": "article not found", "code": "not_found"}), 404

    ok = repo.delete_article(article_id)
    if not ok:
        return jsonify({"error": "delete failed", "code": "server_error"}), 500
    return ("", 204)


@articles_bp.route("/api/articles/<article_id>", methods=["GET"])
def api_get_article(article_id):
    """Fetch a single article with its linked people."""
    repo = TreeRepository()
    article = repo.get_article(article_id)
    if article is None:
        return jsonify({"error": "article not found", "code": "not_found"}), 404

    linked_people = repo.people_for_article(article_id)
    return jsonify(_article_to_dict(article, [p["id"] for p in linked_people]))


@articles_bp.route("/api/articles", methods=["GET"])
def api_list_articles():
    """List all articles with their linked people."""
    repo = TreeRepository()
    articles = repo.list_articles()
    result = []
    for a in articles:
        linked = repo.people_for_article(a.id)
        result.append(_article_to_dict(a, [p["id"] for p in linked]))
    return jsonify(result)


@articles_bp.route("/api/people/<person_id>/articles", methods=["GET"])
def api_person_articles(person_id):
    """List all articles linked to a specific person."""
    repo = TreeRepository()
    if repo.get_person(person_id) is None:
        return jsonify({"error": "person not found", "code": "not_found"}), 404

    articles = repo.articles_for_person(person_id)
    result = []
    for a in articles:
        linked = repo.people_for_article(a.id)
        result.append(_article_to_dict(a, [p["id"] for p in linked]))
    return jsonify(result)


@articles_bp.route("/api/people/<person_id>/articles", methods=["POST"])
@web_server.require_editor
def api_link_article_to_person(person_id):
    """Link an existing article to a person.

    Body: {"article_id": "..."}

    Returns 201 on success, 404 if person or article not found.
    """
    body = request.get_json(silent=True) or {}
    article_id = (body.get("article_id") or "").strip()
    if not article_id:
        return jsonify({"error": "article_id is required", "code": "bad_request"}), 400

    repo = TreeRepository()
    if repo.get_person(person_id) is None:
        return jsonify({"error": "person not found", "code": "not_found"}), 404
    if repo.get_article(article_id) is None:
        return jsonify({"error": "article not found", "code": "not_found"}), 404

    repo.link_article_to_person(person_id, article_id)
    return jsonify({"person_id": person_id, "article_id": article_id}), 201


@articles_bp.route("/api/people/<person_id>/articles/<article_id>", methods=["DELETE"])
@web_server.require_editor
def api_unlink_article_from_person(person_id, article_id):
    """Remove the link between a person and an article.

    Returns 204 on success.
    """
    repo = TreeRepository()
    repo.unlink_article_from_person(person_id, article_id)
    return ("", 204)
