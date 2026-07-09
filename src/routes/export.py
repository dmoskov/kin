"""Export endpoints — serve the family tree in downloadable formats."""

from flask import Blueprint, Response

import web_server
from database.repository import TreeRepository
from import_export.gedcom_export import export_gedcom

export_bp = Blueprint("export", __name__)


@export_bp.route("/api/export/gedcom", methods=["GET"])
def api_export_gedcom() -> Response:
    """Export the entire family tree as a GEDCOM 5.5.1 file.

    Returns a text/plain download named family-tree.ged that can be
    imported into Ancestry, FamilySearch, Gramps, and any other
    GEDCOM-compatible genealogy application.
    """
    repo = TreeRepository()
    tree = repo.load_tree()
    # Same per-link visibility enforcement as /api/data: an exported GEDCOM
    # must not carry links the viewer isn't allowed to see.
    web_server.filter_tree_for_viewer(tree)
    gedcom_text = export_gedcom(tree)

    return Response(
        gedcom_text,
        status=200,
        mimetype="application/x-gedcom",
        headers={
            "Content-Disposition": 'attachment; filename="family-tree.ged"',
            "Content-Type": "application/x-gedcom; charset=utf-8",
        },
    )
