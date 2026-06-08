"""Relationships and unions domain mixin for TreeRepository."""

from typing import Any

from models.relationship import Relationship, RelationshipType, Union

from ._sql import _execute, _fetchall, _fetchone, _ph, _upsert

# Sentinel for update_union: distinguishes "argument not provided" from an
# explicit None (which clears a field). Typed Any so it's assignable to the
# str | None parameters.
_UNSET: Any = object()


class RelationshipsRepoMixin:
    """CRUD operations for relationships and unions tables."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

    def _do_save_relationship(self, conn: Any, rel: Relationship) -> None:
        if rel.parent_id == rel.child_id:
            raise ValueError("a person cannot be their own parent")
        _upsert(
            conn,
            "relationships",
            ["parent_id", "child_id", "rel_type", "visibility"],
            (rel.parent_id, rel.child_id, rel.rel_type.value, rel.visibility.value),
            ["parent_id", "child_id"],
            update=False,
        )

    def _do_save_union(self, conn: Any, union: Union) -> None:
        _execute(
            conn,
            f"""
            INSERT INTO unions
                (partner1_id, partner2_id, union_date, union_place,
                 end_date, end_reason, notes)
            VALUES ({_ph(7)})
        """,
            (
                union.partner1_id,
                union.partner2_id,
                union.union_date,
                union.union_place,
                union.end_date,
                union.end_reason,
                union.notes,
            ),
        )

    # ── Relationships ───────────────────────────────────────────────────

    def save_relationship(self, rel: Relationship) -> None:
        """Insert a parent-child relationship (ignore if duplicate)."""
        conn = self._conn()
        try:
            self._do_save_relationship(conn, rel)
            conn.commit()
        finally:
            conn.close()

    def get_relationship(self, parent_id: str, child_id: str) -> dict | None:
        """Look up a single parent-child relationship row."""
        conn = self._conn()
        try:
            p = _ph()
            row = _fetchone(
                conn,
                f"SELECT * FROM relationships WHERE parent_id = {p} AND child_id = {p} LIMIT 1",
                (parent_id, child_id),
            )
            return dict(row) if row else None
        finally:
            conn.close()

    def update_relationship(
        self,
        parent_id: str,
        child_id: str,
        *,
        rel_type: str | None = _UNSET,
        visibility: str | None = _UNSET,
    ) -> bool:
        """Update rel_type/visibility on an existing relationship.

        Returns True if a row was updated.
        """
        sets = []
        params: list = []
        for col, val in [("rel_type", rel_type), ("visibility", visibility)]:
            if val is not _UNSET:
                sets.append(f"{col} = {_ph()}")
                params.append(val)
        if not sets:
            return False

        p = _ph()
        params.extend([parent_id, child_id])
        conn = self._conn()
        try:
            cur = _execute(
                conn,
                f"UPDATE relationships SET {', '.join(sets)} WHERE parent_id = {p} AND child_id = {p}",
                tuple(params),
            )
            conn.commit()
            return (getattr(cur, "rowcount", 0) or 0) > 0
        finally:
            conn.close()

    def delete_relationship(self, parent_id: str, child_id: str) -> bool:
        """Delete a parent-child relationship. Returns True if a row was removed."""
        p = _ph()
        conn = self._conn()
        try:
            cur = _execute(
                conn,
                f"DELETE FROM relationships WHERE parent_id = {p} AND child_id = {p}",
                (parent_id, child_id),
            )
            conn.commit()
            return (getattr(cur, "rowcount", 0) or 0) > 0
        finally:
            conn.close()

    def auto_link_siblings(self) -> int:
        """Ensure all children of a union share both parents.

        For every union, looks up children linked to *either* partner
        and ensures each child has a parent-child relationship to
        *both* partners.  This handles full siblings (same two parents)
        and correctly avoids linking half-siblings to a step-parent.

        Returns the number of new relationships created.
        """
        conn = self._conn()
        try:
            # Load all unions and relationships
            unions = _fetchall(conn, "SELECT partner1_id, partner2_id FROM unions")
            rels = _fetchall(conn, "SELECT parent_id, child_id FROM relationships")

            # Build parent→children and child→parents maps
            parent_to_children: dict[str, set[str]] = {}
            child_to_parents: dict[str, set[str]] = {}
            for r in rels:
                parent_to_children.setdefault(r["parent_id"], set()).add(r["child_id"])
                child_to_parents.setdefault(r["child_id"], set()).add(r["parent_id"])

            created = 0
            for u in unions:
                p1, p2 = u["partner1_id"], u["partner2_id"]
                children_of_p1 = parent_to_children.get(p1, set())
                children_of_p2 = parent_to_children.get(p2, set())

                # Children linked to both partners = full siblings (already OK)
                # Children linked to only one partner AND the other partner
                # is in a union with them → should also be linked to the other
                for child_id in children_of_p1:
                    if p2 not in child_to_parents.get(child_id, set()):
                        # Check: does this child have p1 as a parent AND
                        # the other parent (if any) is p2's partner?
                        # i.e., only link if the child doesn't already have
                        # a *different* second parent (half-sibling case)
                        other_parents = child_to_parents.get(child_id, set()) - {p1}
                        if len(other_parents) == 0:
                            # Child only has one parent (p1), and p1+p2 are partners
                            # → safe to add p2
                            self._do_save_relationship(
                                conn,
                                Relationship(
                                    parent_id=p2,
                                    child_id=child_id,
                                    rel_type=RelationshipType.BIOLOGICAL,
                                ),
                            )
                            child_to_parents.setdefault(child_id, set()).add(p2)
                            parent_to_children.setdefault(p2, set()).add(child_id)
                            created += 1

                for child_id in children_of_p2:
                    if p1 not in child_to_parents.get(child_id, set()):
                        other_parents = child_to_parents.get(child_id, set()) - {p2}
                        if len(other_parents) == 0:
                            self._do_save_relationship(
                                conn,
                                Relationship(
                                    parent_id=p1,
                                    child_id=child_id,
                                    rel_type=RelationshipType.BIOLOGICAL,
                                ),
                            )
                            child_to_parents.setdefault(child_id, set()).add(p1)
                            parent_to_children.setdefault(p1, set()).add(child_id)
                            created += 1

            if created > 0:
                conn.commit()
            return created
        finally:
            conn.close()

    # ── Unions ──────────────────────────────────────────────────────────

    def save_union(self, union: Union) -> None:
        """Insert a marriage/partnership.

        A couple has at most one union row. If one already exists for this
        (unordered) pair, enrich it — fill any empty fields from the new
        data — rather than creating a duplicate. This keeps every write path
        idempotent and consistent with the unique index on the partner pair.
        """
        if union.partner1_id == union.partner2_id:
            raise ValueError("a person cannot be in a union with themselves")
        conn = self._conn()
        try:
            p = _ph()
            existing = _fetchone(
                conn,
                f"""
                SELECT id FROM unions
                WHERE (partner1_id = {p} AND partner2_id = {p})
                   OR (partner1_id = {p} AND partner2_id = {p})
                LIMIT 1
                """,
                (union.partner1_id, union.partner2_id, union.partner2_id, union.partner1_id),
            )
            if existing:
                # Fill only currently-empty fields (keep existing values).
                _execute(
                    conn,
                    f"""
                    UPDATE unions SET
                        union_date  = COALESCE(union_date, {p}),
                        union_place = COALESCE(union_place, {p}),
                        end_date    = COALESCE(end_date, {p}),
                        end_reason  = COALESCE(end_reason, {p}),
                        notes       = CASE WHEN notes IS NULL OR notes = '' THEN {p} ELSE notes END
                    WHERE id = {p}
                    """,
                    (
                        union.union_date,
                        union.union_place,
                        union.end_date,
                        union.end_reason,
                        union.notes,
                        existing["id"],
                    ),
                )
            else:
                self._do_save_union(conn, union)
            conn.commit()
        finally:
            conn.close()

    def get_union(self, partner1_id: str, partner2_id: str) -> dict | None:
        """Look up a union row by either partner order."""
        conn = self._conn()
        try:
            p = _ph()
            row = _fetchone(
                conn,
                f"""
                SELECT * FROM unions
                WHERE (partner1_id = {p} AND partner2_id = {p})
                   OR (partner1_id = {p} AND partner2_id = {p})
                LIMIT 1
                """,
                (partner1_id, partner2_id, partner2_id, partner1_id),
            )
            return dict(row) if row else None
        finally:
            conn.close()

    def update_union(
        self,
        partner1_id: str,
        partner2_id: str,
        *,
        end_date: str | None = _UNSET,
        end_reason: str | None = _UNSET,
        union_date: str | None = _UNSET,
        union_place: str | None = _UNSET,
        notes: str | None = _UNSET,
    ) -> bool:
        """Update fields on an existing union. Returns True if a row was updated."""
        sets = []
        params: list = []
        sentinel = _UNSET
        for col, val in [
            ("end_date", end_date),
            ("end_reason", end_reason),
            ("union_date", union_date),
            ("union_place", union_place),
            ("notes", notes),
        ]:
            if val is not sentinel:
                sets.append(f"{col} = {_ph()}")
                params.append(val)

        if not sets:
            return False

        p = _ph()
        params.extend([partner1_id, partner2_id, partner2_id, partner1_id])
        conn = self._conn()
        try:
            _execute(
                conn,
                f"""
                UPDATE unions SET {", ".join(sets)}
                WHERE (partner1_id = {p} AND partner2_id = {p})
                   OR (partner1_id = {p} AND partner2_id = {p})
                """,
                tuple(params),
            )
            conn.commit()
            return True
        finally:
            conn.close()
