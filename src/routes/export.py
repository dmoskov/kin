"""Export endpoints — serve the family tree in downloadable formats."""

from flask import Blueprint, Response

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
