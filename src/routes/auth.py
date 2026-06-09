"""Authentication endpoints."""

import json
import logging
import os
import time
from pathlib import Path

from flask import Blueprint, jsonify, request, session
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

import web_server
from database.connection import INTEGRITY_ERRORS, db_transaction
from database.repository import TreeRepository, _execute, _fetchone, _ph

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


# ── Rate limiting ─────────────────────────────────────────────────────
# Fixed-window per-IP limit on sign-in attempts. In-memory, so it's
# per-gunicorn-worker — good enough to blunt brute force without a
# shared store.

_AUTH_WINDOW_SECONDS = 60
_AUTH_MAX_ATTEMPTS = 10
_auth_attempts: dict[str, tuple[float, int]] = {}


def _rate_limited(ip: str) -> bool:
    now = time.time()
    window_start, count = _auth_attempts.get(ip, (now, 0))
    if now - window_start >= _AUTH_WINDOW_SECONDS:
        window_start, count = now, 0
    count += 1
    _auth_attempts[ip] = (window_start, count)
    if len(_auth_attempts) > 10_000:
        cutoff = now - _AUTH_WINDOW_SECONDS
        for stale in [k for k, (s, _) in _auth_attempts.items() if s < cutoff]:
            del _auth_attempts[stale]
    return count > _AUTH_MAX_ATTEMPTS


def _get_tree_editor(email: str) -> dict | None:
    try:
        with db_transaction() as conn:
            row = _fetchone(
                conn,
                f"SELECT email, role, name FROM tree_editors WHERE email = {_ph()}",
                (email,),
            )
        return dict(row) if row else None
    except Exception:
        return None


def _has_any_tree_editors() -> bool:
    try:
        with db_transaction() as conn:
            return _fetchone(conn, "SELECT 1 FROM tree_editors LIMIT 1") is not None
    except Exception:
        return False


def _get_google_client_id() -> str | None:
    """Get the Google Client ID from env or config file."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if client_id:
        return client_id
    # Fall back to family-config.json
    for candidate in [
        web_server.PRIVATE_DIR / "config" / "family-config.json",
        Path(web_server.WEB_DIR) / "family-config.json",
    ]:
        if candidate.exists():
            config = json.loads(candidate.read_text())
            if config.get("googleClientId"):
                return config["googleClientId"]
    return None


def _verify_id_token(credential: str) -> dict | None:
    """Verify a Google ID token: signature, expiry, issuer, and (when a
    client ID is configured) audience — all checked by google-auth against
    Google's published signing keys.

    Returns the token claims dict on success, or None on failure.
    """
    try:
        return google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), audience=_get_google_client_id()
        )
    except (ValueError, OSError) as e:
        logger.warning("Google token verification failed: %s", e)
        return None


@auth_bp.route("/api/auth/google", methods=["POST"])
def api_auth_google():
    """Authenticate with a Google ID token.

    Body: {"credential": "<google id_token>"}
    Returns: {"person_id": "...", "name": "...", "email": "..."}
    """
    if _rate_limited(request.remote_addr or "unknown"):
        return jsonify({"error": "Too many sign-in attempts; try again in a minute"}), 429

    body = request.get_json(force=True)
    credential = body.get("credential", "")
    if not credential:
        return jsonify({"error": "credential required"}), 400

    # Verify token with Google (includes the audience check when a client ID
    # is configured — see _verify_id_token).
    payload = _verify_id_token(credential)
    if not payload:
        return jsonify({"error": "Invalid Google token"}), 401

    email = (payload.get("email") or "").lower()
    # google-auth returns decoded JWT claims, so email_verified is a bool.
    if not email or payload.get("email_verified") not in (True, "true"):
        return jsonify({"error": "Email not verified"}), 401

    # Determine editor status and role from three sources:
    # 1. tree_editors table (DB-backed, has explicit role)
    # 2. EDITORS env var (legacy, all treated as role="editor")
    # 3. If neither is configured, everyone is an editor (open access)
    repo = TreeRepository()
    person = repo.get_person_by_email(email)

    editor_record = _get_tree_editor(email)
    role = None
    if editor_record:
        is_editor = True
        role = editor_record["role"]
    elif web_server.EDITORS and email in web_server.EDITORS:
        is_editor = True
        role = "editor"
    elif not web_server.EDITORS and not _has_any_tree_editors():
        is_editor = True
        role = "editor"
    else:
        is_editor = False

    if not person and not is_editor:
        return jsonify(
            {
                "error": "No matching person record for this email",
                "email": email,
            }
        ), 403

    person_id = person.id if person else f"editor:{email}"
    full_name = person.full_name if person else payload.get("name", email)

    session["person_id"] = person_id
    session["email"] = email
    session["name"] = full_name
    session["picture"] = payload.get("picture", "")
    session["is_editor"] = is_editor
    session["role"] = role

    return jsonify(
        {
            "person_id": person_id,
            "name": full_name,
            "email": email,
            "picture": payload.get("picture", ""),
            "is_editor": is_editor,
            "role": role,
        }
    )


@auth_bp.route("/api/auth/me")
def api_auth_me():
    """Return the current logged-in user, or 401."""
    if "person_id" not in session:
        return jsonify({"error": "not authenticated"}), 401
    return jsonify(
        {
            "person_id": session["person_id"],
            "name": session.get("name", ""),
            "email": session.get("email", ""),
            "picture": session.get("picture", ""),
            "is_editor": session.get("is_editor", False),
            "role": session.get("role"),
        }
    )


@auth_bp.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Clear the session."""
    session.clear()
    return jsonify({"ok": True})


@auth_bp.route("/api/people/<person_id>/email", methods=["PUT"])
def api_set_email(person_id):
    """Set the email for a person. Body: {"email": "user@example.com"}

    Only the admin (configured via ADMIN_PERSON_ID env var) can set emails for other people.
    Any logged-in user can clear their own email.
    """
    admin_person_id = os.environ.get("ADMIN_PERSON_ID", "")
    admin_id = session.get("person_id")
    if not admin_person_id or admin_id != admin_person_id:
        return jsonify({"error": "admin only"}), 403

    body = request.get_json(force=True) or {}
    email = body.get("email", "").strip().lower() or None

    with db_transaction() as conn:
        _execute(
            conn,
            f"UPDATE people SET email = {_ph()} WHERE id = {_ph()}",
            (email, person_id),
        )
    return jsonify({"email": email, "person_id": person_id})


# ── Editor management ─────────────────────────────────────────────────


def _require_admin():
    """Check that the current user is an admin (ADMIN_PERSON_ID or owner role)."""
    admin_person_id = os.environ.get("ADMIN_PERSON_ID", "")
    caller_id = session.get("person_id")
    caller_role = session.get("role")
    if caller_role == "owner":
        return None
    if admin_person_id and caller_id == admin_person_id:
        return None
    return jsonify({"error": "admin only"}), 403


VALID_ROLES = {"owner", "editor", "assistant", "researcher"}


@auth_bp.route("/api/editors")
def api_list_editors():
    """List all non-family editors from the tree_editors table."""
    err = _require_admin()
    if err:
        return err
    from database.repository import _fetchall

    with db_transaction() as conn:
        rows = _fetchall(conn, "SELECT * FROM tree_editors ORDER BY created_at")
    return jsonify(
        [
            {
                "email": r["email"],
                "role": r["role"],
                "name": r["name"] or "",
                "invited_by": r["invited_by"],
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in rows
        ]
    )


@auth_bp.route("/api/editors", methods=["POST"])
def api_add_editor():
    """Add a non-family editor. Body: {"email": "...", "role": "assistant", "name": "..."}"""
    err = _require_admin()
    if err:
        return err

    body = request.get_json(force=True) or {}
    email = (body.get("email") or "").strip().lower()
    role = body.get("role", "editor").strip().lower()
    name = (body.get("name") or "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "valid email required"}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": f"role must be one of: {', '.join(sorted(VALID_ROLES))}"}), 400

    invited_by = session.get("email", "")

    try:
        with db_transaction() as conn:
            _execute(
                conn,
                f"INSERT INTO tree_editors (email, role, name, invited_by) VALUES ({_ph()}, {_ph()}, {_ph()}, {_ph()})",
                (email, role, name, invited_by),
            )
    except INTEGRITY_ERRORS:
        return jsonify({"error": "Editor with this email already exists"}), 409
    return jsonify({"email": email, "role": role, "name": name}), 201


@auth_bp.route("/api/editors/<path:email>", methods=["PATCH"])
def api_update_editor(email):
    """Update an editor's role or name. Body: {"role": "researcher", "name": "..."}"""
    err = _require_admin()
    if err:
        return err

    body = request.get_json(force=True) or {}
    updates = {}
    if "role" in body:
        role = body["role"].strip().lower()
        if role not in VALID_ROLES:
            return jsonify({"error": f"role must be one of: {', '.join(sorted(VALID_ROLES))}"}), 400
        updates["role"] = role
    if "name" in body:
        updates["name"] = (body["name"] or "").strip()

    if not updates:
        return jsonify({"error": "nothing to update"}), 400

    set_clauses = ", ".join(f"{k} = {_ph()}" for k in updates)
    values = list(updates.values()) + [email.lower()]

    with db_transaction() as conn:
        cur = _execute(
            conn,
            f"UPDATE tree_editors SET {set_clauses} WHERE email = {_ph()}",
            tuple(values),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "editor not found"}), 404
    return jsonify({"email": email.lower(), **updates})


@auth_bp.route("/api/editors/<path:email>", methods=["DELETE"])
def api_remove_editor(email):
    """Remove a non-family editor."""
    err = _require_admin()
    if err:
        return err

    with db_transaction() as conn:
        cur = _execute(
            conn,
            f"DELETE FROM tree_editors WHERE email = {_ph()}",
            (email.lower(),),
        )
        if cur.rowcount == 0:
            return jsonify({"error": "editor not found"}), 404
    return "", 204
