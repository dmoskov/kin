"""Wikipedia person-enrichment endpoint."""

from flask import Blueprint, jsonify, request

wikipedia_bp = Blueprint("wikipedia", __name__)


@wikipedia_bp.route("/api/person-wikipedia", methods=["POST"])
def api_person_wikipedia():
    """Resolve people to their Wikipedia article (cached, year-verified).

    Body: JSON array of person ids.
    Returns: { results: {id: {matched, title, url, description, events}}, pending: N }
    Cache hits return immediately; misses resolve in a rate-limited background
    thread — call again (pending > 0) to pick up newly resolved people.
    """
    from database.connection import _use_postgres, get_connection
    from wikipedia import resolve_people

    ids = request.get_json(silent=True) or []
    if not isinstance(ids, list):
        return jsonify({"error": "expected a JSON array of person ids"}), 400
    ids = [str(i) for i in ids if i][:50]
    if not ids:
        return jsonify({"results": {}, "pending": 0})

    pg = _use_postgres()
    ph = ",".join("%s" if pg else "?" for _ in ids)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, given_name, surname, birth_date, death_date FROM people WHERE id IN ({ph})",
            ids,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    people = []
    for r in rows:
        if hasattr(r, "keys"):
            pid, gn, sn, bd, dd = (
                r["id"],
                r["given_name"],
                r["surname"],
                r["birth_date"],
                r["death_date"],
            )
        else:
            pid, gn, sn, bd, dd = r
        name = " ".join(x for x in [gn, sn] if x).strip()
        people.append({"id": pid, "name": name, "birth": bd, "death": dd})

    results, pending = resolve_people(people)
    return jsonify({"results": results, "pending": pending})
