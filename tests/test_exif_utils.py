"""Tests for EXIF metadata extraction (src/exif_utils.py).

Covers:
  - _dms_to_decimal: GPS DMS → decimal degree conversion with all compass refs
  - extract_exif_metadata: date extraction, GPS extraction, error resilience
"""

import io

import pytest
from PIL import Image
from PIL.ExifTags import IFD

from exif_utils import _dms_to_decimal, extract_exif_metadata

# ── _dms_to_decimal ──────────────────────────────────────────────────


class TestDmsToDecimal:
    def test_north_latitude(self):
        # 40°26'46" N → 40.446111
        result = _dms_to_decimal((40.0, 26.0, 46.0), "N")
        assert result == pytest.approx(40.446111, abs=1e-5)

    def test_south_latitude(self):
        # 33°51'54" S → -33.865
        result = _dms_to_decimal((33.0, 51.0, 54.0), "S")
        assert result == pytest.approx(-33.865, abs=1e-5)

    def test_east_longitude(self):
        # 116°23'30" E → 116.391667
        result = _dms_to_decimal((116.0, 23.0, 30.0), "E")
        assert result == pytest.approx(116.391667, abs=1e-5)

    def test_west_longitude(self):
        # 73°58'10" W → -73.969444
        result = _dms_to_decimal((73.0, 58.0, 10.0), "W")
        assert result == pytest.approx(-73.969444, abs=1e-5)

    def test_zero_coordinates(self):
        result = _dms_to_decimal((0.0, 0.0, 0.0), "N")
        assert result == 0.0

    def test_fractional_seconds(self):
        # 51°30'26.46" N → 51.507350
        result = _dms_to_decimal((51.0, 30.0, 26.46), "N")
        assert result == pytest.approx(51.507350, abs=1e-5)

    def test_returns_none_on_empty_tuple(self):
        assert _dms_to_decimal((), "N") is None

    def test_returns_none_on_non_numeric(self):
        assert _dms_to_decimal(("a", "b", "c"), "N") is None

    def test_returns_none_on_none_element(self):
        assert _dms_to_decimal((None, 0, 0), "N") is None

    def test_result_rounded_to_six_decimals(self):
        result = _dms_to_decimal((40.0, 26.0, 46.0), "N")
        assert result is not None
        decimal_str = str(result)
        if "." in decimal_str:
            assert len(decimal_str.split(".")[1]) <= 6


# ── Helpers ──────────────────────────────────────────────────────────


def _make_jpeg_bytes_with_exif(
    *,
    date_original: str | None = None,
    date_digitized: str | None = None,
    date_root: str | None = None,
    gps_lat: tuple | None = None,
    gps_lat_ref: str = "N",
    gps_lng: tuple | None = None,
    gps_lng_ref: str = "E",
) -> bytes:
    """Create a minimal JPEG with the given EXIF fields baked in."""
    img = Image.new("RGB", (1, 1), color="red")

    exif = img.getexif()

    if date_original or date_digitized:
        exif_ifd = exif.get_ifd(IFD.Exif)
        if date_original:
            exif_ifd[36867] = date_original  # DateTimeOriginal
        if date_digitized:
            exif_ifd[36868] = date_digitized  # DateTimeDigitized
        exif[0x8769] = exif_ifd

    if date_root:
        exif[306] = date_root  # DateTime

    if gps_lat and gps_lng:
        gps_ifd = {
            1: gps_lat_ref,
            2: gps_lat,
            3: gps_lng_ref,
            4: gps_lng,
        }
        exif[0x8825] = gps_ifd

    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


# ── extract_exif_metadata: Date extraction ───────────────────────────


class TestExtractDate:
    def test_date_from_datetime_original(self):
        data = _make_jpeg_bytes_with_exif(date_original="2019:07:04 14:30:22")
        result = extract_exif_metadata(data)
        assert result["date"] == "2019-07-04"

    def test_date_from_datetime_digitized_fallback(self):
        data = _make_jpeg_bytes_with_exif(date_digitized="2020:12:25 08:00:00")
        result = extract_exif_metadata(data)
        assert result["date"] == "2020-12-25"

    def test_date_from_root_datetime_fallback(self):
        data = _make_jpeg_bytes_with_exif(date_root="2018:03:15 10:45:00")
        result = extract_exif_metadata(data)
        assert result["date"] == "2018-03-15"

    def test_date_original_preferred_over_root(self):
        data = _make_jpeg_bytes_with_exif(
            date_original="2021:01:01 00:00:00",
            date_root="2019:06:06 12:00:00",
        )
        result = extract_exif_metadata(data)
        assert result["date"] == "2021-01-01"

    def test_year_range_lower_bound(self):
        data = _make_jpeg_bytes_with_exif(date_original="1800:01:01 00:00:00")
        result = extract_exif_metadata(data)
        assert result["date"] == "1800-01-01"

    def test_year_below_1800_rejected(self):
        data = _make_jpeg_bytes_with_exif(date_original="1799:12:31 23:59:59")
        result = extract_exif_metadata(data)
        assert "date" not in result

    def test_year_above_2100_rejected(self):
        data = _make_jpeg_bytes_with_exif(date_original="2101:01:01 00:00:00")
        result = extract_exif_metadata(data)
        assert "date" not in result


# ── extract_exif_metadata: GPS extraction ────────────────────────────


class TestExtractGPS:
    def test_gps_north_east(self):
        data = _make_jpeg_bytes_with_exif(
            gps_lat=(40.0, 26.0, 46.0),
            gps_lat_ref="N",
            gps_lng=(73.0, 58.0, 10.0),
            gps_lng_ref="W",
        )
        result = extract_exif_metadata(data)
        assert result["lat"] == pytest.approx(40.446111, abs=1e-5)
        assert result["lng"] == pytest.approx(-73.969444, abs=1e-5)

    def test_gps_south_west(self):
        data = _make_jpeg_bytes_with_exif(
            gps_lat=(33.0, 51.0, 54.0),
            gps_lat_ref="S",
            gps_lng=(151.0, 12.0, 36.0),
            gps_lng_ref="E",
        )
        result = extract_exif_metadata(data)
        assert result["lat"] == pytest.approx(-33.865, abs=1e-5)
        assert result["lng"] == pytest.approx(151.21, abs=1e-3)


# ── extract_exif_metadata: Error resilience ──────────────────────────


class TestExtractErrorResilience:
    def test_empty_bytes_returns_empty_dict(self):
        result = extract_exif_metadata(b"")
        assert result == {}

    def test_garbage_bytes_returns_empty_dict(self):
        result = extract_exif_metadata(b"\x00\x01\x02\x03random garbage")
        assert result == {}

    def test_non_image_file_returns_empty_dict(self):
        result = extract_exif_metadata(b"this is just a text file, not an image")
        assert result == {}

    def test_valid_jpeg_without_exif_returns_empty_dict(self):
        img = Image.new("RGB", (1, 1), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        result = extract_exif_metadata(buf.getvalue())
        assert result == {}

    def test_combined_date_and_gps(self):
        data = _make_jpeg_bytes_with_exif(
            date_original="2022:08:15 16:30:00",
            gps_lat=(48.0, 51.0, 24.0),
            gps_lat_ref="N",
            gps_lng=(2.0, 21.0, 7.0),
            gps_lng_ref="E",
        )
        result = extract_exif_metadata(data)
        assert result["date"] == "2022-08-15"
        assert result["lat"] == pytest.approx(48.856667, abs=1e-4)
        assert result["lng"] == pytest.approx(2.351944, abs=1e-4)
