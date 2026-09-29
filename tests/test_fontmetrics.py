from pathlib import Path

import pytest

from clipmaker.fontmetrics import FontMetrics, load_metrics

FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"


def test_width_scales_linearly_with_size():
    m = load_metrics(FONTS / "Montserrat-Black.ttf")
    assert m.text_width("HOLA", 100) == pytest.approx(2 * m.text_width("HOLA", 50))


def test_empty_and_unknown_chars():
    m = load_metrics(FONTS / "Anton-Regular.ttf")
    assert m.text_width("", 80) == 0
    assert m.text_width("中", 80) > 0  # falls back to .notdef width


def test_condensed_narrower_than_black():
    black = load_metrics(FONTS / "Montserrat-Black.ttf").text_width("ABCDEFG", 100)
    cond = load_metrics(FONTS / "BebasNeue-Regular.ttf").text_width("ABCDEFG", 100)
    assert cond < black


def test_vertical_metrics_reasonable():
    m = load_metrics(FONTS / "Poppins-SemiBold.ttf")
    assert isinstance(m, FontMetrics)
    assert m.ascent > 0 and m.descent > 0 and 0.5 < m.cap_height < 0.9
    assert m.line_height(100) == pytest.approx((m.ascent + m.descent) * 100)
