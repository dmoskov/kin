"""Source and citation CRUD endpoints.

Sources are reusable provenance records (a document, letter, census, oral
history, etc.). Citations link a source to a specific fact in the tree —
any entity (person, relationship, union, event), optionally scoped to a
single field. This is the structured provenance layer; the free-text
``event.source`` field is a separate lightweight note and is left untouched.
"""

import uuid

from flask import Blueprint, jsonify, request

import web_server
from database.repository import TreeRepository
from import_export.json_io import _citation_to_dict, _source_to_dict
from models.citation import Confidence, EntityType
from models.source import Source, SourceType

sources_bp = Blueprint("sources", __name__)


# ── Sources ──────────────────────────────────────────────────────────────


@sources_bp.route("/api/sources", methods=["POST"])
@web_server.require_editor
def api_create_source():
    """Create a source.

    Body: {"name": "...", "source_type"?, "author"?, "date"?, "description"?,
           "url"?, "id"?}. ``id`` is minted if omitted.

    Returns 201 with the created source, 400 for validation errors, 409 if an
    explicit id already exists.
    """
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required", "code": "bad_request"}), 400

    try:
        source_type = SourceType(body.get("source_type", SourceType.OTHER.value))
    except ValueError:
        return jsonify(
            {"error": f"invalid source_type: {body.get('source_type')}", "code": "bad_request"}
        ), 400

    source_id = body.get("id", "").strip() if isinstance(body.get("id"), str) else ""
    if not source_id:
        source_id = f"source_{uuid.uuid4().hex[:12]}"

    repo = TreeRepository()
    if repo.get_source(source_id) is not None:
        return jsonify({"error": f"source id already exists: {source_id}", "code": "conflict"}), 409

    source = Source(
        id=source_id,
        name=name,
        source_type=source_type,
        author=(body.get("author") or None),
        date=(body.get("date") or None),
        description=(body.get("description") or ""),
        url=(body.get("url") or None),
    )
    repo.save_source(source)
    return jsonify(_source_to_dict(source)), 201


@sources_bp.route("/api/sources/<source_id>", methods=["PUT", "PATCH"])
@web_server.require_editor
def api_update_source(source_id):
    """Update a source. Partial updates supported. Returns 200, 404 if absent."""
    body = request.get_json(silent=True) or {}

    repo = TreeRepository()
    if repo.get_source(source_id) is None:
        return jsonify({"error": "source not found", "code": "not_found"}), 404

    kwargs = {}
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name cannot be empty", "code": "bad_request"}), 400
        kwargs["name"] = name
    if "source_type" in body:
        try:
            kwargs["source_type"] = SourceType(body["source_type"]).value
        except ValueError:
            return jsonify(
                {"error": f"invalid source_type: {body['source_type']}", "code": "bad_request"}
            ), 400
    for key in ("author", "date", "url"):
        if key in body:
            val = body[key]
            kwargs[key] = (val.strip() or None) if isinstance(val, str) else None
    if "description" in body:
        kwargs["description"] = (
            (body["description"] or "") if isinstance(body["description"], str) else ""
        )

    if not kwargs:
        return jsonify({"error": "nothing to update", "code": "bad_request"}), 400

    repo.update_source(source_id, **kwargs)
    updated = repo.get_source(source_id)
    return jsonify(_source_to_dict(updated)), 200


@sources_bp.route("/api/sources/<source_id>", methods=["DELETE"])
@web_server.require_editor
def api_delete_source(source_id):
    """Delete a source and its citations (FK cascade). Returns 204, 404 if absent."""
    repo = TreeRepository()
    if not repo.delete_source(source_id):
        return jsonify({"error": "source not found", "code": "not_found"}), 404
    return ("", 204)


# ── Citations ────────────────────────────────────────────────────────────


@sources_bp.route("/api/citations", methods=["POST"])
@web_server.require_editor
def api_create_citation():
    """Link a source to an entity.

    Body: {"source_id", "entity_type", "entity_id", "field_name"?, "excerpt"?,
           "confidence"?, "notes"?}.

    Returns 201 with the created citation (including its id), 400 for invalid
    fields, 404 if the source doesn't exist.
    """
    from models.citation import Citation

    body = request.get_json(silent=True) or {}
    source_id = (body.get("source_id") or "").strip()
    entity_id = (body.get("entity_id") or "").strip()
    if not source_id or not entity_id or not body.get("entity_type"):
        return jsonify(
            {"error": "source_id, entity_type and entity_id are required", "code": "bad_request"}
        ), 400

    try:
        entity_type = EntityType(body["entity_type"])
    except ValueError:
        return jsonify(
            {"error": f"invalid entity_type: {body['entity_type']}", "code": "bad_request"}
        ), 400
    try:
        confidence = Confidence(body.get("confidence", Confidence.CONFIRMED.value))
    except ValueError:
        return jsonify(
            {"error": f"invalid confidence: {body.get('confidence')}", "code": "bad_request"}
        ), 400

    repo = TreeRepository()
    if repo.get_source(source_id) is None:
        return jsonify({"error": f"source not found: {source_id}", "code": "not_found"}), 404

    field_name = body.get("field_name")
    citation = Citation(
        source_id=source_id,
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=(field_name.strip() or None) if isinstance(field_name, str) else None,
        excerpt=(body.get("excerpt") or ""),
        confidence=confidence,
        notes=(body.get("notes") or ""),
    )
    citation.id = repo.save_citation_returning_id(citation)
    return jsonify(_citation_to_dict(citation)), 201


@sources_bp.route("/api/citations/<int:citation_id>", methods=["PUT", "PATCH"])
@web_server.require_editor
def api_update_citation(citation_id):
    """Update a citation's field_name/excerpt/confidence/notes. The source and
    cited entity are immutable. Returns 200, 404 if absent."""
    body = request.get_json(silent=True) or {}

    repo = TreeRepository()
    existing = repo.get_citation(citation_id)
    if existing is None:
        return jsonify({"error": "citation not found", "code": "not_found"}), 404

    kwargs = {}
    if "field_name" in body:
        val = body["field_name"]
        kwargs["field_name"] = (val.strip() or None) if isinstance(val, str) else None
    if "excerpt" in body:
        kwargs["excerpt"] = (body["excerpt"] or "") if isinstance(body["excerpt"], str) else ""
    if "notes" in body:
        kwargs["notes"] = (body["notes"] or "") if isinstance(body["notes"], str) else ""
    if "confidence" in body:
        try:
            kwargs["confidence"] = Confidence(body["confidence"]).value
        except ValueError:
            return jsonify(
                {"error": f"invalid confidence: {body['confidence']}", "code": "bad_request"}
            ), 400

    if not kwargs:
        return jsonify({"error": "nothing to update", "code": "bad_request"}), 400

    repo.update_citation(citation_id, **kwargs)
    return jsonify(_citation_to_dict(repo.get_citation(citation_id))), 200


@sources_bp.route("/api/citations/<int:citation_id>", methods=["DELETE"])
@web_server.require_editor
def api_delete_citation(citation_id):
    """Delete a citation. Returns 204, 404 if absent."""
    repo = TreeRepository()
    if not repo.delete_citation(citation_id):
        return jsonify({"error": "citation not found", "code": "not_found"}), 404
    return ("", 204)
