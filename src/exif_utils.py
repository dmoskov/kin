"""EXIF metadata extraction from JPEG/TIFF images.

Uses Pillow to read EXIF data and extract:
  - DateTimeOriginal (or DateTime fallback) → ISO date string
  - GPSInfo → decimal lat/lng coordinates

Never throws — returns empty dict on failure so uploads are never blocked.
"""

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _dms_to_decimal(dms_tuple: tuple, ref: str) -> float | None:
    """Convert EXIF GPS DMS (degrees, minutes, seconds) to decimal degrees.

    Each element of dms_tuple is an IFDRational or float.
    ref is 'N'/'S' for latitude, 'E'/'W' for longitude.
    """
    try:
        degrees = float(dms_tuple[0])
        minutes = float(dms_tuple[1])
        seconds = float(dms_tuple[2])
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        return None


def extract_exif_metadata(image_bytes: bytes) -> dict[str, Any]:
    """Extract date and GPS coordinates from image EXIF data.

    Returns dict with optional keys:
      - date: str  (YYYY-MM-DD format)
      - lat: float (decimal degrees, negative for south)
      - lng: float (decimal degrees, negative for west)

    Returns {} on any failure. Never raises.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import IFD
    except ImportError:
        logger.debug("Pillow not installed, skipping EXIF extraction")
        return {}

    result = {}

    try:
        img = Image.open(io.BytesIO(image_bytes))
        exif = img.getexif()
        if not exif:
            return {}

        # --- Date extraction ---
        # Try EXIF IFD first (DateTimeOriginal = tag 36867)
        date_str = None
        try:
            exif_ifd = exif.get_ifd(IFD.Exif)
            if exif_ifd:
                date_str = exif_ifd.get(36867)  # DateTimeOriginal
                if not date_str:
                    date_str = exif_ifd.get(36868)  # DateTimeDigitized
        except Exception:
            pass

        # Fallback to root DateTime (tag 306)
        if not date_str:
            date_str = exif.get(306)

        if date_str and isinstance(date_str, str):
            # Format: "2019:07:04 14:30:22" → "2019-07-04"
            date_part = date_str.strip().split(" ")[0]
            if ":" in date_part and len(date_part) >= 10:
                iso_date = date_part.replace(":", "-")
                # Validate it looks like a real date
                parts = iso_date.split("-")
                if len(parts) == 3 and all(p.isdigit() for p in parts):
                    year = int(parts[0])
                    if 1800 <= year <= 2100:
                        result["date"] = iso_date

        # --- GPS extraction ---
        try:
            gps_ifd = exif.get_ifd(IFD.GPSInfo)
            if gps_ifd:
                # GPSLatitude = tag 2, GPSLatitudeRef = tag 1
                # GPSLongitude = tag 4, GPSLongitudeRef = tag 3
                lat_dms = gps_ifd.get(2)
                lat_ref = gps_ifd.get(1, "N")
                lng_dms = gps_ifd.get(4)
                lng_ref = gps_ifd.get(3, "E")

                if lat_dms and lng_dms:
                    lat = _dms_to_decimal(lat_dms, lat_ref)
                    lng = _dms_to_decimal(lng_dms, lng_ref)
                    if lat is not None and lng is not None:
                        # Sanity check: valid coordinate ranges
                        if -90 <= lat <= 90 and -180 <= lng <= 180:
                            result["lat"] = lat
                            result["lng"] = lng
        except Exception:
            pass

    except Exception as e:
        logger.debug("EXIF extraction failed: %s", e)

    return result
