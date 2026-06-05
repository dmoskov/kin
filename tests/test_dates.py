"""Tests for the canonical date normalizer (src/dates.py)."""

import pytest

from dates import looks_circa, normalize_date


class TestNormalizeDate:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("1845", "1845"),
            ("1845-06", "1845-06"),
            ("1845-06-01", "1845-06-01"),
            ("  1845-06-01  ", "1845-06-01"),
            # circa markers stripped to a bare ISO date
            ("~1622", "1622"),
            ("c. 1845", "1845"),
            ("ca 1845", "1845"),
            ("abt 1845", "1845"),
            ("about 1845", "1845"),
            ("circa 1845-06", "1845-06"),
            ("est. 1845", "1845"),
            ("1845?", "1845"),
            # slash separators normalized
            ("1845/06/01", "1845-06-01"),
            ("1845/06", "1845-06"),
        ],
    )
    def test_valid_and_normalized(self, raw, expected):
        assert normalize_date(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "18922",  # five digits
            "845",  # three digits
            "1845-13",  # month out of range
            "1845-00",  # month zero
            "1845-02-30",  # impossible day
            "1845-06-31",  # June has 30 days
            "1845-13-01",  # bad month with day
            "before 1900",  # unsupported qualifier
            "after 1900",
            "1845-06-01-02",  # too many parts
            "June 1845",  # non-numeric
            "1845 to 1850",  # range
        ],
    )
    def test_invalid_raises(self, raw):
        with pytest.raises(ValueError):
            normalize_date(raw)

    def test_leap_day_valid(self):
        assert normalize_date("2000-02-29") == "2000-02-29"

    def test_non_leap_day_invalid(self):
        with pytest.raises(ValueError):
            normalize_date("1900-02-29")  # 1900 is not a leap year


class TestLooksCirca:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("~1622", True),
            ("c. 1845", True),
            ("circa 1845", True),
            ("1845?", True),
            ("1845", False),
            ("1845-06-01", False),
            ("", False),
            (None, False),
        ],
    )
    def test_looks_circa(self, raw, expected):
        assert looks_circa(raw) is expected
