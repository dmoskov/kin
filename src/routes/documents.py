"""Document upload, AI parsing, GEDCOM import, and document serving endpoints."""

import json
import logging
import threading
import uuid
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_from_directory, session

import web_server
from database.connection import get_connection
from database.repository import TreeRepository, _execute, _fetchone, _ph
from import_export.gedcom_import import parse_gedcom

logger = logging.getLogger(__name__)

documents_bp = Blueprint("documents", __name__)


ALLOWED_DOC_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}

# In-memory tracking for background parse jobs
_parse_jobs: dict[str, dict] = {}


def _update_document(
    doc_id: str, *, status: str | None = None, parsed_data: dict | None = None
) -> None:
    """Portable helper that updates a documents row on either backend."""
    sets = []
    params: list = []
    if status is not None:
        sets.append(f"status = {_ph()}")
        params.append(status)
    if parsed_data is not None:
        sets.append(f"parsed_data = {_ph()}")
        params.append(json.dumps(parsed_data))
    if not sets:
        return
    params.append(doc_id)
    sql = f"UPDATE documents SET {', '.join(sets)} WHERE id = {_ph()}"
    conn = get_connection()
    try:
        _execute(conn, sql, tuple(params))
        conn.commit()
    finally:
        conn.close()


def _get_document(doc_id: str) -> dict | None:
    conn = get_connection()
    try:
        return _fetchone(
            conn,
            f"SELECT * FROM documents WHERE id = {_ph()}",
            (doc_id,),
        )
    finally:
        conn.close()


def _get_existing_people() -> list[dict]:
    """Load existing people for AI matching context."""
    repo = TreeRepository()
    tree = repo.load_tree()
    return [
        {
            "id": p.id,
            "given_name": p.given_name,
            "surname": p.surname,
            "birth_date": p.birth_date,
            "death_date": p.death_date,
            "maiden_name": p.maiden_name,
            "gender": p.gender.value,
        }
        for p in tree.people.values()
    ]


def _save_chunk_result(doc_id: str, chunk_index: int, chunk: dict, result: dict) -> None:
    """Update a pending chunk row with parsed results."""
    status = "error" if "error" in result else "done"
    error_msg = result.get("error") if "error" in result else None
    conn = get_connection()
    try:
        _execute(
            conn,
            f"UPDATE document_chunks SET status = {_ph()}, parsed_data = {_ph()}, error_message = {_ph()} "
            f"WHERE document_id = {_ph()} AND chunk_index = {_ph()}",
            (status, json.dumps(result), error_msg, doc_id, chunk_index),
        )
        conn.commit()
    finally:
        conn.close()


def _update_document_progress(doc_id: str, total: int, done: int) -> None:
    """Update chunk progress columns on the documents table."""
    conn = get_connection()
    try:
        _execute(
            conn,
            f"UPDATE documents SET total_chunks = {_ph()}, chunks_done = {_ph()} WHERE id = {_ph()}",
            (total, done, doc_id),
        )
        conn.commit()
    finally:
        conn.close()


def _load_done_chunks(doc_id: str) -> list[tuple[int, dict]]:
    """Return (chunk_index, parsed_data_dict) for all status='done' chunks."""
    from database.repository import _fetchall

    conn = get_connection()
    try:
        rows = _fetchall(
            conn,
            f"SELECT chunk_index, parsed_data FROM document_chunks "
            f"WHERE document_id = {_ph()} AND status = 'done' "
            f"ORDER BY chunk_index",
            (doc_id,),
        )
    finally:
        conn.close()
    result = []
    for row in rows:
        try:
            data = json.loads(row["parsed_data"]) if row["parsed_data"] else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        result.append((row["chunk_index"], data))
    return result


def _run_background_parse(
    doc_id: str,
    file_path: str,
    filename: str,
    existing_people: list[dict],
    done_results: list[dict] | None = None,
) -> None:
    """Background thread target for all document parsing (single or multi-chunk)."""
    from intelligence.document_parser import parse_document_chunked

    job = _parse_jobs[doc_id]

    def on_progress(chunk_idx: int, total: int, chunk_result: dict) -> None:
        chunks_done = chunk_idx + 1
        job["chunks_done"] = chunks_done
        _update_document_progress(doc_id, total, chunks_done)

        chunk_plan = job.get("chunk_plan", [])
        chunk_info = chunk_plan[chunk_idx] if chunk_idx < len(chunk_plan) else {}
        _save_chunk_result(doc_id, chunk_idx, chunk_info, chunk_result)

    try:
        result = parse_document_chunked(
            file_path=file_path,
            existing_people=existing_people,
            filename=filename,
            on_progress=on_progress,
            done_results=done_results,
        )
    except Exception as e:
        logger.error("Document parsing failed: %s", e)
        result = {"error": str(e)}

    if "error" in result:
        _update_document(doc_id, status="error", parsed_data=result)
        job["status"] = "error"
        job["error"] = result.get("error", "Unknown error")
    else:
        _update_document(doc_id, status="parsed", parsed_data=result)
        job["status"] = "parsed"
        job["result"] = result


@documents_bp.route("/api/documents")
def api_list_documents():
    """Return all documents ordered by upload date (newest first)."""
    from database.repository import _fetchall

    conn = get_connection()
    try:
        rows = _fetchall(
            conn,
            "SELECT id, filename, file_type, status, uploaded_at, "
            "total_chunks, chunks_done FROM documents ORDER BY uploaded_at DESC",
        )
    except Exception:
        return jsonify([])
    finally:
        conn.close()

    docs = []
    for r in rows:
        status = r["status"]
        total = r.get("total_chunks") or 0
        done = r.get("chunks_done") or 0
        if status == "parsing" and r["id"] not in _parse_jobs and done < total:
            status = "stalled"
        docs.append(
            {
                "id": r["id"],
                "filename": r["filename"],
                "file_type": r.get("file_type"),
                "status": status,
                "uploaded_at": r.get("uploaded_at"),
                "total_chunks": total,
                "chunks_done": done,
            }
        )
    return jsonify(docs)


@documents_bp.route("/api/import/gedcom", methods=["POST"])
@web_server.require_editor
def api_import_gedcom():
    """Import a GEDCOM (.ged) file into the database.

    Returns summary stats: people, unions, relationships, events imported.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in (".ged", ".gedcom"):
        return jsonify({"error": f"Expected a .ged file, got {ext or '(none)'}"}), 400

    # Save to a temp file for parsing
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".ged", delete=False)
    try:
        f.save(tmp.name)
        tree = parse_gedcom(tmp.name)
    except Exception as e:
        logger.error("GEDCOM parse failed: %s", e)
        return jsonify({"error": f"Failed to parse GEDCOM file: {e}"}), 400
    finally:
        try:
            Path(tmp.name).unlink()
        except OSError:
            pass

    # Persist everything via the repository
    repo = TreeRepository()
    stats = {"people": 0, "unions": 0, "relationships": 0, "events": 0, "skipped": []}

    for person in tree.people.values():
        try:
            repo.save_person(person)
            stats["people"] += 1
        except Exception as e:
            stats["skipped"].append(f"Person {person.id}: {e}")

    for union in tree.unions:
        try:
            repo.save_union(union)
            stats["unions"] += 1
        except Exception as e:
            stats["skipped"].append(f"Union: {e}")

    for rel in tree.relationships:
        try:
            repo.save_relationship(rel)
            stats["relationships"] += 1
        except Exception as e:
            stats["skipped"].append(f"Relationship: {e}")

    for event in tree.events:
        try:
            repo.save_event(event)
            stats["events"] += 1
        except Exception as e:
            stats["skipped"].append(f"Event: {e}")

    # Auto-link siblings after bulk import of relationships + unions
    try:
        linked = repo.auto_link_siblings()
        if linked:
            stats["auto_linked_siblings"] = linked
    except Exception as e:
        stats["skipped"].append(f"auto_link_siblings: {e}")

    return jsonify(stats)


@documents_bp.route("/api/documents/upload", methods=["POST"])
@web_server.require_editor
def api_upload_document():
    """Upload a document for AI parsing.

    Returns ``{"document_id": "...", "filename": "...", "status": "uploaded"}``.

    Hardened in the same ways as ``/api/photos/upload`` (size cap, magic-byte
    check, atomic write) plus transactional cleanup: if the DB insert fails,
    the saved file is removed so we don't leave orphans on disk.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided", "code": "missing_file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename", "code": "empty_filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_DOC_EXTS:
        return jsonify(
            {
                "error": f"Unsupported file type: {ext or '(none)'}. Use images or PDF.",
                "code": "invalid_type",
            }
        ), 400

    size = web_server._measure_file_size(f)
    if size == 0:
        return jsonify({"error": "Empty file", "code": "empty"}), 400
    if size > web_server.MAX_DOC_BYTES:
        mb = web_server.MAX_DOC_BYTES // (1024 * 1024)
        return jsonify(
            {
                "error": f"File too large (max {mb} MB)",
                "code": "too_large",
            }
        ), 413

    doc_id = str(uuid.uuid4())[:12]
    safe_name = web_server._sanitize_filename(f.filename)
    doc_dir = web_server.PRIVATE_DIR / "documents"
    dest = doc_dir / safe_name

    try:
        web_server._atomic_save(f, dest)
    except OSError as e:
        logger.error("document save failed: %s", e)
        return jsonify({"error": "Could not save file", "code": "io_error"}), 500

    # Magic-byte check post-save
    is_pdf = ext == ".pdf"
    ok = web_server._looks_like_pdf(dest) if is_pdf else web_server._looks_like_image(dest, ext)
    if not ok:
        try:
            dest.unlink()
        except OSError:
            pass
        return jsonify(
            {
                "error": "File contents do not match its extension",
                "code": "bad_content",
            }
        ), 400

    file_type = "pdf" if is_pdf else "image"
    uploaded_by = session.get("person_id")

    conn = get_connection()
    try:
        try:
            _execute(
                conn,
                f"INSERT INTO documents (id, filename, file_path, file_type, uploaded_by) "
                f"VALUES ({_ph(5)})",
                (doc_id, f.filename, f"documents/{safe_name}", file_type, uploaded_by),
            )
            conn.commit()
        except Exception as e:
            # Transactional cleanup: if the DB insert fails, don't leave
            # the file sitting on disk with no tracking row.
            try:
                if dest.exists():
                    dest.unlink()
            except OSError:
                pass
            logger.error("document DB insert failed: %s", e)
            return jsonify(
                {
                    "error": "Could not record document",
                    "code": "db_error",
                }
            ), 500
    finally:
        conn.close()

    return jsonify(
        {
            "document_id": doc_id,
            "filename": f.filename,
            "file_type": file_type,
            "status": "uploaded",
        }
    )


@documents_bp.route("/api/documents/<doc_id>/parse", methods=["POST"])
@web_server.require_editor
def api_parse_document(doc_id):
    """Trigger AI parsing of a document.

    Always returns immediately and spawns a background thread.
    Client polls /parse-status for progress and final result.

    If existing done chunks are found from a previous interrupted run,
    enters resume mode: skips already-done chunks and picks up from where
    it left off.
    """
    row = _get_document(doc_id)
    if not row:
        return jsonify({"error": "Document not found", "code": "not_found"}), 404

    file_path = str(web_server.PRIVATE_DIR / row["file_path"])
    if not Path(file_path).exists():
        return jsonify({"error": "Document file not found on disk", "code": "missing_file"}), 404

    existing_people = _get_existing_people()

    # Check for existing done chunks (resume mode)
    done_chunk_rows = _load_done_chunks(doc_id)
    done_results: list[dict] | None = None
    resume_count = 0

    ext = Path(file_path).suffix.lower()
    total_chunks = 1
    chunks: list[dict] = []

    if done_chunk_rows:
        # Resume mode: we have prior completed chunks
        resume_count = len(done_chunk_rows)
        done_results = [{"_chunk_index": idx, **data} for idx, data in done_chunk_rows]

        # Re-plan chunks to get total (must match original plan)
        if ext == ".pdf":
            from intelligence.document_parser import _plan_chunks

            chunks = _plan_chunks(file_path)
            total_chunks = max(len(chunks), 1)

        # Reset non-done chunks to pending for re-processing
        conn = get_connection()
        try:
            _execute(
                conn,
                f"UPDATE document_chunks SET status = 'pending', error_message = NULL "
                f"WHERE document_id = {_ph()} AND status != 'done'",
                (doc_id,),
            )
            conn.commit()
        finally:
            conn.close()

        _update_document(doc_id, status="parsing")
        _update_document_progress(doc_id, total_chunks, resume_count)

        _parse_jobs[doc_id] = {
            "status": "parsing",
            "total_chunks": total_chunks,
            "chunks_done": resume_count,
            "chunk_plan": chunks,
        }

        t = threading.Thread(
            target=_run_background_parse,
            args=(doc_id, file_path, row["filename"], existing_people),
            kwargs={"done_results": done_results},
            daemon=True,
        )
        t.start()

        return jsonify(
            {
                "document_id": doc_id,
                "status": "parsing",
                "total_chunks": total_chunks,
                "chunks_done": resume_count,
            }
        )

    # Fresh parse: no prior chunks
    _update_document(doc_id, status="parsing")

    if ext == ".pdf":
        from intelligence.document_parser import _plan_chunks

        chunks = _plan_chunks(file_path)
        total_chunks = max(len(chunks), 1)

        if len(chunks) > 1:
            _update_document_progress(doc_id, total_chunks, 0)

            conn = get_connection()
            try:
                for i, chunk in enumerate(chunks):
                    _execute(
                        conn,
                        f"INSERT INTO document_chunks "
                        f"(document_id, chunk_index, start_page, end_page, mode, status) "
                        f"VALUES ({_ph(6)})",
                        (
                            doc_id,
                            i,
                            chunk["start_page"],
                            chunk["end_page"],
                            chunk["mode"],
                            "pending",
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

    _parse_jobs[doc_id] = {
        "status": "parsing",
        "total_chunks": total_chunks,
        "chunks_done": 0,
        "chunk_plan": chunks,
    }

    t = threading.Thread(
        target=_run_background_parse,
        args=(doc_id, file_path, row["filename"], existing_people),
        daemon=True,
    )
    t.start()

    return jsonify(
        {
            "document_id": doc_id,
            "status": "parsing",
            "total_chunks": total_chunks,
            "chunks_done": 0,
        }
    )


@documents_bp.route("/api/documents/<doc_id>/parse-status", methods=["GET"])
def api_parse_status(doc_id):
    """Poll endpoint for multi-chunk parse progress."""
    # Check in-memory job first (fast path)
    job = _parse_jobs.get(doc_id)
    if job:
        resp = {
            "document_id": doc_id,
            "status": job["status"],
            "total_chunks": job.get("total_chunks", 0),
            "chunks_done": job.get("chunks_done", 0),
        }
        if job["status"] == "parsed":
            resp["proposed_changes"] = job.get("result", {})
            # Clean up finished job
            _parse_jobs.pop(doc_id, None)
        elif job["status"] == "error":
            resp["error"] = job.get("error", "Unknown error")
            _parse_jobs.pop(doc_id, None)
        return jsonify(resp)

    # Fallback: check DB status
    row = _get_document(doc_id)
    if not row:
        return jsonify({"error": "Document not found", "code": "not_found"}), 404

    status = row.get("status", "uploaded")
    total_chunks = row.get("total_chunks", 0) or 0
    chunks_done = row.get("chunks_done", 0) or 0

    # Stall detection: DB says "parsing" but no in-memory job is running.
    # This happens when the server restarts (e.g. gunicorn deploy) mid-parse.
    if status == "parsing" and chunks_done < total_chunks:
        status = "stalled"

    resp = {
        "document_id": doc_id,
        "status": status,
        "total_chunks": total_chunks,
        "chunks_done": chunks_done,
    }

    if status in ("parsed", "applied"):
        try:
            resp["proposed_changes"] = json.loads(row.get("parsed_data", "{}"))
        except (json.JSONDecodeError, TypeError):
            resp["proposed_changes"] = {}
    elif status == "error":
        try:
            parsed = json.loads(row.get("parsed_data", "{}"))
            resp["error"] = parsed.get("error", "Unknown error")
        except (json.JSONDecodeError, TypeError):
            resp["error"] = "Unknown error"

    return jsonify(resp)


@documents_bp.route("/api/documents/<doc_id>/apply", methods=["POST"])
@web_server.require_editor
def api_apply_document(doc_id):
    """Apply reviewed/edited changes from a parsed document to the database.

    Body: The proposed_changes JSON (possibly edited by user in the review modal).
    """
    changes = request.get_json(force=True) or {}

    row = _get_document(doc_id)
    if not row:
        return jsonify({"error": "Document not found", "code": "not_found"}), 404

    repo = TreeRepository()
    applied = {"people": 0, "relationships": 0, "events": 0, "unions": 0}

    # Create a Source for this document
    from models.source import Source, SourceType

    source = Source(
        id=f"doc-{doc_id}",
        name=row["filename"],
        source_type=SourceType.DOCUMENT,
        description=changes.get("summary", "Uploaded document"),
    )
    repo.save_source(source)

    # Apply people
    from models.person import Gender, Person

    for p_data in changes.get("people", []):
        person_id = p_data.get("id", "")
        if not person_id or not p_data.get("given_name"):
            continue

        # Check if person exists
        existing = repo.get_person(person_id)
        if existing:
            # Update fields that are currently empty
            changed = False
            for field in (
                "birth_date",
                "birth_place",
                "death_date",
                "death_place",
                "maiden_name",
            ):
                new_val = p_data.get(field)
                if new_val and not getattr(existing, field):
                    setattr(existing, field, new_val)
                    changed = True
            if p_data.get("notes") and not existing.notes:
                existing.notes = p_data["notes"]
                changed = True
            if changed:
                repo.save_person(existing)
                applied["people"] += 1
        elif p_data.get("is_new"):
            # Create new person
            gender_val = p_data.get("gender", "unknown")
            try:
                gender = Gender(gender_val)
            except ValueError:
                gender = Gender.UNKNOWN

            person = Person(
                id=person_id,
                given_name=p_data["given_name"],
                surname=p_data.get("surname", ""),
                gender=gender,
                birth_date=p_data.get("birth_date"),
                birth_place=p_data.get("birth_place"),
                death_date=p_data.get("death_date"),
                death_place=p_data.get("death_place"),
                maiden_name=p_data.get("maiden_name"),
                notes=p_data.get("notes", ""),
            )
            repo.save_person(person)
            applied["people"] += 1

    # Apply relationships
    from models.relationship import Relationship, RelationshipType

    for r_data in changes.get("relationships", []):
        parent_id = r_data.get("parent_id", "")
        child_id = r_data.get("child_id", "")
        if not parent_id or not child_id:
            continue
        try:
            rel_type = RelationshipType(r_data.get("rel_type", "biological"))
        except ValueError:
            rel_type = RelationshipType.BIOLOGICAL
        rel = Relationship(parent_id=parent_id, child_id=child_id, rel_type=rel_type)
        try:
            repo.save_relationship(rel)
            applied["relationships"] += 1
        except Exception as e:
            logger.warning("Could not save relationship %s→%s: %s", parent_id, child_id, e)

    # Apply events
    from models.event import EventType, LifeEvent

    for e_data in changes.get("events", []):
        person_id = e_data.get("person_id", "")
        if not person_id:
            continue
        try:
            event_type = EventType(e_data.get("event_type", "custom"))
        except ValueError:
            event_type = EventType.CUSTOM
        event = LifeEvent(
            person_id=person_id,
            event_type=event_type,
            date=e_data.get("date"),
            end_date=e_data.get("end_date"),
            place=e_data.get("place"),
            description=e_data.get("description", ""),
            source=f"doc-{doc_id}",
        )
        try:
            repo.save_event(event)
            applied["events"] += 1
        except Exception as e:
            logger.warning("Could not save event for %s: %s", person_id, e)

    # Apply unions
    from models.relationship import Union

    for u_data in changes.get("unions", []):
        p1 = u_data.get("partner1_id", "")
        p2 = u_data.get("partner2_id", "")
        if not p1 or not p2:
            continue
        union = Union(
            partner1_id=p1,
            partner2_id=p2,
            union_date=u_data.get("union_date"),
            union_place=u_data.get("union_place"),
        )
        try:
            repo.save_union(union)
            applied["unions"] += 1
        except Exception as e:
            logger.warning("Could not save union %s + %s: %s", p1, p2, e)

    # Auto-link siblings after applying relationships + unions from document
    try:
        linked = repo.auto_link_siblings()
        if linked:
            applied["auto_linked_siblings"] = linked
    except Exception:
        pass

    # Update document status
    _update_document(doc_id, status="applied")

    return jsonify({"status": "applied", "applied": applied})


@documents_bp.route("/documents/<path:filename>")
def serve_document(filename):
    """Serve uploaded documents from private/documents/."""
    doc_dir = web_server.PRIVATE_DIR / "documents"
    if (doc_dir / filename).exists():
        return send_from_directory(str(doc_dir), filename)
    abort(404)
