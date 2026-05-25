"""Photo — a photograph associated with one or more people.

Photos are first-class entities with their own metadata (date, place, type).
The person_photos junction table links photos to people with per-person
metadata (is_profile, display_order, caption).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PhotoType(Enum):
    PORTRAIT = "portrait"
    GROUP = "group"
    DOCUMENT = "document"
    HEADSTONE = "headstone"
    PHOTO = "photo"


@dataclass
class Photo:
    """A photograph in the family tree.

    Attributes:
        id: Auto-incremented primary key
        file_path: Unique path to the photo file (e.g. "photos/foo.jpg")
        date: Partial ISO date (YYYY, YYYY-MM, or YYYY-MM-DD)
        date_circa: Whether the date is approximate
        place: Free text location where the photo was taken
        photo_type: Category of photo
    """
    id: int = 0
    file_path: str = ""
    date: Optional[str] = None
    date_circa: bool = False
    place: Optional[str] = None
    photo_type: PhotoType = PhotoType.PHOTO


@dataclass
class PersonPhoto:
    """Junction record linking a person to a photo.

    Attributes:
        person_id: FK to people.id
        photo_id: FK to photos.id
        is_profile: Whether this is the person's profile photo
        display_order: Sort order for the person's photo gallery
        caption: Per-person caption for this photo
    """
    person_id: str = ""
    photo_id: int = 0
    is_profile: bool = False
    display_order: int = 0
    caption: str = ""
