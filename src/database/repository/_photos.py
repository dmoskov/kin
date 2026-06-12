"""Photos, person_photos, and face_regions domain mixin for TreeRepository."""

from typing import Any

from models.person import Person

from ._sql import _ensure_photo_id, _execute, _fetchall, _fetchone, _is_pg, _ph, _scalar, _upsert


class PhotosRepoMixin:
    """CRUD operations for photos, person_photos, and face_regions tables."""

    def _conn(self) -> Any: ...  # provided by TreeRepository

    def _sync_person_photos(self, conn: Any, person: "Person") -> None:
        """Additively mirror a person's photo_paths into photos/person_photos.

        Called during save_person for dual-write compatibility. This is
        INSERT/UPDATE-only by design: it never deletes person_photos rows.
        person_photos is the authoritative store (crops, profile flag, face
        regions, multi-person tags); deriving deletions from the flat
        photo_paths list here would wipe data added directly via
        assign_photo_to_person whenever an unrelated column is saved. Removal is
        owned by the photo routes, which call unassign_photo_from_person.
        """
        p = _ph()
        for idx, file_path in enumerate(person.photo_paths):
            photo_id = _ensure_photo_id(conn, file_path)

            caption = person.photo_captions.get(file_path, "")

            existing = _fetchone(
                conn,
                f"""
                SELECT is_profile FROM person_photos
                WHERE person_id = {p} AND photo_id = {p}
            """,
                (person.id, photo_id),
            )

            if existing:
                _execute(
                    conn,
                    f"""
                    UPDATE person_photos SET display_order = {p}, caption = {p}
                    WHERE person_id = {p} AND photo_id = {p}
                """,
                    (idx, caption, person.id, photo_id),
                )
            else:
                is_profile_val: int = idx == 0  # bool is a subtype of int
                if not _is_pg():
                    is_profile_val = 1 if is_profile_val else 0
                _execute(
                    conn,
                    f"""
                    INSERT INTO person_photos (person_id, photo_id, is_profile, display_order, caption)
                    VALUES ({_ph(5)})
                """,
                    (person.id, photo_id, is_profile_val, idx, caption),
                )

    # ── Photos ─────────────────────────────────────────────────────────

    def get_or_create_photo(self, file_path: str) -> int:
        """Return the photo id for a file_path, creating a row if needed."""
        conn = self._conn()
        try:
            photo_id = _ensure_photo_id(conn, file_path)
            conn.commit()
            return photo_id
        finally:
            conn.close()

    def update_photo_metadata(self, photo_id: int, **kwargs) -> None:
        """Update metadata fields on a photo (date, date_circa, place, photo_type)."""
        allowed = {"date", "date_circa", "place", "photo_type", "lat", "lng"}
        sets = []
        params = []
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "date_circa":
                v = bool(v) if _is_pg() else (1 if v else 0)
            sets.append(f"{k} = {_ph()}")
            params.append(v)
        if not sets:
            return
        params.append(photo_id)
        sql = f"UPDATE photos SET {', '.join(sets)} WHERE id = {_ph()}"
        conn = self._conn()
        try:
            _execute(conn, sql, tuple(params))
            conn.commit()
        finally:
            conn.close()

    def get_photo(self, photo_id: int) -> dict | None:
        """Fetch a single photo by id."""
        conn = self._conn()
        try:
            return _fetchone(conn, f"SELECT * FROM photos WHERE id = {_ph()}", (photo_id,))
        finally:
            conn.close()

    def delete_photo(self, photo_id: int) -> str | None:
        """Permanently delete a photo row and its links (person assignments,
        face regions). Returns the photo's file_path so the caller can remove
        the underlying file, or None if the photo doesn't exist.

        The links are also covered by ON DELETE CASCADE; the explicit deletes
        make the intent visible and don't depend on FK enforcement.
        """
        conn = self._conn()
        try:
            row = _fetchone(conn, f"SELECT file_path FROM photos WHERE id = {_ph()}", (photo_id,))
            if not row:
                return None
            _execute(conn, f"DELETE FROM person_photos WHERE photo_id = {_ph()}", (photo_id,))
            _execute(conn, f"DELETE FROM face_regions WHERE photo_id = {_ph()}", (photo_id,))
            _execute(conn, f"DELETE FROM photos WHERE id = {_ph()}", (photo_id,))
            conn.commit()
            return row["file_path"]
        finally:
            conn.close()

    def photos_for_person(self, person_id: str) -> list[dict]:
        """Return all photos for a person, joined with person_photos metadata."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchall(
                conn,
                f"""
                SELECT p.*, pp.is_profile, pp.display_order, pp.caption, pp.person_id,
                       pp.crop_x, pp.crop_y, pp.crop_w, pp.crop_h
                FROM photos p
                JOIN person_photos pp ON pp.photo_id = p.id
                WHERE pp.person_id = {p}
                ORDER BY p.created_at DESC, p.id DESC
            """,
                (person_id,),
            )
        finally:
            conn.close()

    def people_for_photo(self, photo_id: int) -> list[dict]:
        """Return all people tagged in a photo."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchall(
                conn,
                f"""
                SELECT pp.person_id, pp.is_profile, pp.display_order, pp.caption,
                       pp.crop_x, pp.crop_y, pp.crop_w, pp.crop_h,
                       ppl.given_name, ppl.surname
                FROM person_photos pp
                JOIN people ppl ON ppl.id = pp.person_id
                WHERE pp.photo_id = {p}
                ORDER BY pp.display_order
            """,
                (photo_id,),
            )
        finally:
            conn.close()

    def assign_photo_to_person(
        self,
        person_id: str,
        photo_id: int,
        caption: str = "",
        display_order: int = 0,
        is_profile: bool = False,
    ) -> None:
        """Link a photo to a person."""
        conn = self._conn()
        try:
            is_profile_val: int = is_profile  # bool is a subtype of int
            if not _is_pg():
                is_profile_val = 1 if is_profile else 0
            _upsert(
                conn,
                "person_photos",
                ["person_id", "photo_id", "is_profile", "display_order", "caption"],
                (person_id, photo_id, is_profile_val, display_order, caption),
                ["person_id", "photo_id"],
            )
            conn.commit()
        finally:
            conn.close()

    def unassign_photo_from_person(self, person_id: str, photo_id: int) -> None:
        """Remove a photo from a person."""
        conn = self._conn()
        try:
            _execute(
                conn,
                f"DELETE FROM person_photos WHERE person_id = {_ph()} AND photo_id = {_ph()}",
                (person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def set_profile_photo(self, person_id: str, photo_id: int) -> None:
        """Set a photo as the profile photo for a person, clearing others."""
        conn = self._conn()
        try:
            false_val = False if _is_pg() else 0
            true_val = True if _is_pg() else 1
            _execute(
                conn,
                f"UPDATE person_photos SET is_profile = {_ph()} WHERE person_id = {_ph()}",
                (false_val, person_id),
            )
            _execute(
                conn,
                f"UPDATE person_photos SET is_profile = {_ph()} WHERE person_id = {_ph()} AND photo_id = {_ph()}",
                (true_val, person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def set_photo_caption_new(self, person_id: str, photo_id: int, caption: str) -> None:
        """Set the caption for a person-photo link."""
        conn = self._conn()
        try:
            _execute(
                conn,
                f"UPDATE person_photos SET caption = {_ph()} WHERE person_id = {_ph()} AND photo_id = {_ph()}",
                (caption, person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def list_all_photos(self) -> list[dict]:
        """Return all photos with their tagged people and face regions."""
        conn = self._conn()
        try:
            photos = _fetchall(conn, "SELECT * FROM photos ORDER BY created_at DESC, id DESC")
            p = _ph()
            for photo in photos:
                people = _fetchall(
                    conn,
                    f"""
                    SELECT pp.person_id, pp.is_profile, pp.caption, pp.display_order,
                           pp.crop_x, pp.crop_y, pp.crop_w, pp.crop_h,
                           ppl.given_name, ppl.surname
                    FROM person_photos pp
                    JOIN people ppl ON ppl.id = pp.person_id
                    WHERE pp.photo_id = {p}
                    ORDER BY pp.display_order
                """,
                    (photo["id"],),
                )
                photo["tagged_people"] = people
                try:
                    regions = _fetchall(
                        conn,
                        f"""
                        SELECT fr.id, fr.person_id, fr.x, fr.y, fr.w, fr.h,
                               ppl.given_name, ppl.surname
                        FROM face_regions fr
                        JOIN people ppl ON ppl.id = fr.person_id
                        WHERE fr.photo_id = {p}
                        ORDER BY fr.id
                    """,
                        (photo["id"],),
                    )
                    photo["face_regions"] = regions
                except Exception:
                    photo["face_regions"] = []
                    if _is_pg():
                        conn.rollback()
            return photos
        finally:
            conn.close()

    # ── Face Regions ──────────────────────────────────────────────────

    def save_face_region(
        self, photo_id: int, person_id: str, x: float, y: float, w: float, h: float
    ) -> int:
        """Insert a face region for a person on a photo. Returns the region id.

        Multiple regions per person per photo are allowed (for montages).
        """
        conn = self._conn()
        try:
            _execute(
                conn,
                f"""
                INSERT INTO face_regions (photo_id, person_id, x, y, w, h)
                VALUES ({_ph(6)})
            """,
                (photo_id, person_id, x, y, w, h),
            )
            conn.commit()
            if _is_pg():
                row = _scalar(conn, "SELECT lastval() AS id")
            else:
                row = _scalar(conn, "SELECT last_insert_rowid() AS id")
            return row["id"]
        finally:
            conn.close()

    def get_face_regions(self, photo_id: int) -> list[dict]:
        """Return all face regions for a photo, with person names."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchall(
                conn,
                f"""
                SELECT fr.id, fr.photo_id, fr.person_id, fr.x, fr.y, fr.w, fr.h,
                       ppl.given_name, ppl.surname
                FROM face_regions fr
                JOIN people ppl ON ppl.id = fr.person_id
                WHERE fr.photo_id = {p}
                ORDER BY fr.id
            """,
                (photo_id,),
            )
        finally:
            conn.close()

    def delete_face_region(self, region_id: int) -> None:
        """Delete a face region by id."""
        conn = self._conn()
        try:
            _execute(conn, f"DELETE FROM face_regions WHERE id = {_ph()}", (region_id,))
            conn.commit()
        finally:
            conn.close()

    def face_region_for_person_photo(self, photo_id: int, person_id: str) -> dict | None:
        """Return the face region for a specific person on a specific photo."""
        conn = self._conn()
        try:
            p = _ph()
            return _fetchone(
                conn,
                f"""
                SELECT id, photo_id, person_id, x, y, w, h
                FROM face_regions
                WHERE photo_id = {p} AND person_id = {p}
            """,
                (photo_id, person_id),
            )
        finally:
            conn.close()

    # ── Profile Crop ───────────────────────────────────────────────────

    def set_profile_crop(
        self,
        person_id: str,
        photo_id: int,
        crop_x: float,
        crop_y: float,
        crop_w: float,
        crop_h: float,
    ) -> None:
        """Set the crop region for a person's profile photo."""
        conn = self._conn()
        try:
            p = _ph()
            _execute(
                conn,
                f"""
                UPDATE person_photos
                SET crop_x = {p}, crop_y = {p}, crop_w = {p}, crop_h = {p}
                WHERE person_id = {p} AND photo_id = {p}
            """,
                (crop_x, crop_y, crop_w, crop_h, person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()

    def clear_profile_crop(self, person_id: str, photo_id: int) -> None:
        """Clear the crop region for a person's profile photo."""
        conn = self._conn()
        try:
            p = _ph()
            _execute(
                conn,
                f"""
                UPDATE person_photos
                SET crop_x = NULL, crop_y = NULL, crop_w = NULL, crop_h = NULL
                WHERE person_id = {p} AND photo_id = {p}
            """,
                (person_id, photo_id),
            )
            conn.commit()
        finally:
            conn.close()
