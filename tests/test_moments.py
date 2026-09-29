import pytest

from clipmaker.moments import extract_ranges, parse_time, parse_time_range


class TestParseTime:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("10:30", 630), ("1:02:03", 3723), ("0:05", 5), ("90", 90), ("90s", 90), ("10m30s", 630),
            ("1h2m3s", 3723), ("2m", 120), ("10:30.5", 630.5), ("10:30,5", 630.5), (" 5:00 ", 300),
            ("1h", 3600), ("12.5", 12.5),
        ],
    )  # fmt: skip
    def test_valid(self, text, expected):
        assert parse_time(text) == pytest.approx(expected)

    @pytest.mark.parametrize("text", ["", "abc", "10:75", "1:2:3:4", "-5", "10::30"])
    def test_invalid(self, text):
        with pytest.raises(ValueError):
            parse_time(text)


class TestParseTimeRange:
    def test_basic(self):
        assert parse_time_range("10:30-11:15") == (630, 675)

    def test_spaces_and_dashes(self):
        assert parse_time_range(" 10:30 – 11:15 ") == (630, 675)
        assert parse_time_range("600-1200") == (600, 1200)
        assert parse_time_range("10:00 to 20:00") == (600, 1200)

    def test_rejects_reversed_or_garbage(self):
        with pytest.raises(ValueError):
            parse_time_range("20:00-10:00")
        with pytest.raises(ValueError):
            parse_time_range("hello")


class TestExtractRanges:
    def test_simple(self):
        ranges, rest = extract_ranges("10:30-11:15")
        assert ranges == [(630, 675)] and rest == ""

    def test_multiple_in_free_text(self):
        text = "Quiero el chiste de 10:30-11:15 y también 25:00 - 26:10, además cualquier momento emotivo"
        ranges, rest = extract_ranges(text)
        assert ranges == [(630, 675), (1500, 1570)]
        assert "emotivo" in rest and "10:30" not in rest

    def test_words_as_separators(self):
        assert extract_ranges("de 1:00 a 1:30")[0] == [(60, 90)]
        assert extract_ranges("from 2:00 to 2:45")[0] == [(120, 165)]
        assert extract_ranges("1:00 hasta 1:20")[0] == [(60, 80)]

    def test_unit_formats(self):
        assert extract_ranges("10m30s-11m15s")[0] == [(630, 675)]

    def test_hours(self):
        assert extract_ranges("1:02:00-1:03:10")[0] == [(3720, 3790)]

    def test_ignores_non_time_dashes_and_reversed(self):
        assert extract_ranges("top 10-15 moments")[0] == []
        assert extract_ranges("20:00-10:00")[0] == []

    def test_no_ranges(self):
        ranges, rest = extract_ranges("cuando hablan de música")
        assert ranges == [] and rest == "cuando hablan de música"

    def test_empty(self):
        assert extract_ranges("") == ([], "")
