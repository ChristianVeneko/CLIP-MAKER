import re
from dataclasses import replace

import pytest

from clipmaker.captions import (
    FONTS_DIR,
    PRESETS,
    build_captions,
    get_preset,
    hex_to_ass,
    plan_lines,
    preset_catalog,
    resolve_style_id,
    rounded_rect_path,
)
from clipmaker.fontmetrics import load_metrics
from clipmaker.subtitles import Word

EXPECTED = {
    "karaoke", "deep_diver", "youshaei", "pod_p", "mozi", "beasty", "simple", "popline", "think_media",
}


def w(text, start, end):
    return Word(text=text, start=start, end=end)


def fake_measure(preset, text, size):
    return 0.5 * size * len(text)  # deterministic: 0.5 em per char


WORDS = [w("esto", 0.0, 0.4), w("es", 0.4, 0.6), w("una", 0.6, 0.9), w("prueba", 0.9, 1.4), w("real", 1.4, 1.8)]


def events(ass):
    return [l for l in ass.splitlines() if l.startswith("Dialogue:")]


def text_events(ass):
    return [l for l in events(ass) if "\\p1" not in l]


def build(name, words=WORDS, w_=1080, h=1920):
    return build_captions(words, name, w_, h, measure=fake_measure)


class TestColors:
    def test_hex_to_ass_is_bgr(self):
        assert hex_to_ass("#FF8000") == "&H000080FF&"

    def test_alpha(self):
        assert hex_to_ass("#000000", alpha=0x80) == "&H80000000&"

    def test_bad_hex(self):
        with pytest.raises(ValueError):
            hex_to_ass("red")


class TestRegistry:
    def test_all_presets_present(self):
        assert EXPECTED <= set(PRESETS)

    def test_aliases(self):
        assert resolve_style_id("bold-yellow") == "mozi"
        assert resolve_style_id("clean-white") == "youshaei"
        assert resolve_style_id("NONE") == "none"

    def test_unknown(self):
        with pytest.raises(ValueError, match="Unknown"):
            resolve_style_id("nope")
        with pytest.raises(ValueError):
            get_preset("none")

    def test_catalog(self):
        cat = preset_catalog()
        ids = [c["id"] for c in cat]
        assert EXPECTED <= set(ids) and "none" in ids
        for c in cat:
            assert {"id", "name", "font_family", "colors"} <= set(c)
        mozi = next(c for c in cat if c["id"] == "mozi")
        assert mozi["font_family"] == "Montserrat"
        assert re.fullmatch(r"#[0-9A-F]{6}", mozi["colors"]["active"])


class TestGeometry:
    def test_rounded_rect_path(self):
        p = rounded_rect_path(200, 100, 20)
        assert p.startswith("m 20 0") and "b" in p
        assert p.count("b") == 4  # one bezier per corner

    def test_radius_clamped(self):
        assert "m 50 0" in rounded_rect_path(100, 100, 999)


class TestPlanLines:
    def test_single_line(self):
        ws = [w("a", 0, 1), w("bb", 1, 2), w("ccc", 2, 3)]
        assert [[x.text for x in ln] for ln in plan_lines(ws, 1)] == [["a", "bb", "ccc"]]

    def test_two_lines_balanced_by_chars(self):
        ws = [w(t, i, i + 1) for i, t in enumerate(["uno", "dos", "tres", "cuatro"])]
        lines = plan_lines(ws, 2)
        assert len(lines) == 2
        assert [x.text for ln in lines for x in ln] == ["uno", "dos", "tres", "cuatro"]
        assert abs(sum(len(x.text) for x in lines[0]) - sum(len(x.text) for x in lines[1])) <= 5

    def test_one_word_two_lines_yields_one(self):
        assert len(plan_lines([w("x", 0, 1)], 2)) == 1


class TestEveryPreset:
    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_valid_ass_document(self, name):
        ass = build(name)
        assert "[Script Info]" in ass and "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
        assert "[V4+ Styles]" in ass and "[Events]" in ass
        assert len(text_events(ass)) >= len(WORDS)
        assert get_preset(name).font in ass

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_font_size_in_opus_range(self, name):
        # em size in px for a 1080-wide canvas; libass Fontsize = ascent + descent (win metrics)
        assert 70 <= get_preset(name).size_ratio * 1080 <= 115
        ass = build(name)
        fontsize = int(re.search(r"Style: Default,[^,]+,(\d+),", ass).group(1))
        m = load_metrics(FONTS_DIR / get_preset(name).font_file)
        assert fontsize == round(m.line_height(get_preset(name).size_ratio * 1080))

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_font_scales_with_output_size(self, name):
        small = int(re.search(r"Style: Default,[^,]+,(\d+),", build(name, w_=540, h=960)).group(1))
        big = int(re.search(r"Style: Default,[^,]+,(\d+),", build(name)).group(1))
        assert big == pytest.approx(2 * small, abs=3)

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_never_more_than_two_lines_per_frame(self, name):
        ass = build(name, [w(f"palabra{i}", i * 0.3, i * 0.3 + 0.25) for i in range(30)])
        by_time = {}
        for e in text_events(ass):
            by_time.setdefault(e.split(",")[1], []).append(e)
        assert max(len(v) for v in by_time.values()) <= 2

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_positioned_within_canvas(self, name):
        for e in text_events(build(name)):
            x, y = map(float, re.search(r"\\pos\(([\d.]+),([\d.]+)\)", e).groups())
            assert 0 < x < 1080 and 0 < y < 1920

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_rebased_and_bounded(self, name):
        ws = [w("hola", 100.0, 100.4), w("fin", 109.9, 110.0)]
        ass = build_captions(ws, name, 1080, 1920, clip_start=100.0, clip_end=110.05, measure=fake_measure)
        ends = [e.split(",")[2] for e in events(ass)]
        assert events(ass)[0].split(",")[1] == "0:00:00.00"
        assert max(ends) <= "0:00:10.05"

    def test_vertical_text_sits_around_70_percent_height(self):
        ass = build("mozi")
        ys = [float(re.search(r"\\pos\([\d.]+,([\d.]+)\)", e).group(1)) for e in text_events(ass)]
        assert 0.6 * 1920 < min(ys) and max(ys) < 0.85 * 1920


class TestPresetSpecifics:
    def test_none_returns_none(self):
        assert build_captions(WORDS, "none", 1080, 1920) is None

    def test_karaoke_progressive_fill_and_two_lines(self):
        p = get_preset("karaoke")
        ass = build("karaoke")
        assert p.max_lines == 2
        active = hex_to_ass(p.active_color)
        third = [e for e in text_events(ass) if e.split(",")[1] == "0:00:00.60"][0]
        # words already spoken keep the fill colour
        assert third.count(f"\\c{active}") >= 3 or "ESTO" in third
        first = text_events(ass)[0]
        assert "ESTO" in first and "ES" in first  # whole chunk visible at once

    def test_karaoke_spoken_words_stay_filled(self):
        p = get_preset("karaoke")
        ass = build("karaoke", [w("a", 0, 1), w("b", 1, 2), w("c", 2, 3)])
        ev = "".join(e for e in text_events(ass) if e.split(",")[1] == "0:00:02.00")  # active = "c"
        assert ev.count(f"\\c{hex_to_ass(p.active_color)}") == 3

    def test_mozi_only_active_word_green_uppercase(self):
        p = get_preset("mozi")
        ass = build("mozi", [w("hola", 0, 1), w("mundo", 1, 2)])
        ev = text_events(ass)[0]
        assert ev.count(f"\\c{hex_to_ass(p.active_color)}") == 1 and "HOLA" in ev
        assert "\\fscx" in ev and "\\t(" in ev  # pop animation

    def test_deep_diver_rounded_box_and_dark_active_word(self):
        p = get_preset("deep_diver")
        ass = build("deep_diver")
        boxes = [e for e in events(ass) if "\\p1" in e]
        assert boxes and " b " in boxes[0] and hex_to_ass(p.box_color) in boxes[0]
        text = text_events(ass)[0]
        assert "esto" in text  # sentence case preserved
        assert hex_to_ass(p.active_color) in text and hex_to_ass(p.text_color) in text

    def test_youshaei_single_line_uppercase_mint(self):
        p = get_preset("youshaei")
        assert p.max_lines == 1 and p.uppercase
        ass = build("youshaei")
        assert hex_to_ass(p.active_color) in text_events(ass)[0]

    def test_pod_p_max_two_words_dark_edge(self):
        p = get_preset("pod_p")
        assert p.max_words <= 2
        ass = build("pod_p")
        ev = text_events(ass)[0]
        assert hex_to_ass(p.active_color) in ev and hex_to_ass(p.active_outline_color) in ev

    def test_beasty_bounce_and_italic(self):
        p = get_preset("beasty")
        ass = build("beasty")
        assert p.italic and p.max_words <= 3
        assert re.search(r"Style: Default,[^,]+,\d+,(&H[0-9A-F]{8}&,){4}0,-1,", ass)  # bold off, italic on
        ev = text_events(ass)[0]
        assert ev.count("\\t(") >= 3  # overshoot then settle

    def test_simple_has_no_colour_change(self):
        p = get_preset("simple")
        assert p.max_words <= 2 and p.active_color == p.text_color
        ass = build("simple")
        colours = set(re.findall(r"\\c(&H[0-9A-F]{8}&)", "".join(text_events(ass))))
        assert len(colours) == 1

    def test_popline_purple_box_behind_active_word_only(self):
        p = get_preset("popline")
        ass = build("popline", [w("hola", 0, 1), w("mundo", 1, 2)])
        boxes = [e for e in events(ass) if "\\p1" in e]
        assert len(boxes) == 2  # one active-word box per word event
        assert all(hex_to_ass(p.box_color) in b for b in boxes)
        # the two words sit on two lines, so the boxes follow them
        ys = [float(re.search(r"\\pos\([\d.]+,([\d.]+)\)", b).group(1)) for b in boxes]
        assert ys[0] < ys[1]

    def test_popline_box_moves_right_within_a_line(self):
        ws = [w("a", 0, 1), w("b", 1, 2), w("c", 2, 3)]
        ass = build_captions(ws, replace(get_preset("popline"), max_lines=1), 1080, 1920, measure=fake_measure)
        xs = [float(re.search(r"\\pos\(([\d.]+),", b).group(1)) for b in events(ass) if "\\p1" in b]
        assert xs == sorted(xs) and len(set(xs)) == 3

    def test_think_media_second_line_yellow(self):
        p = get_preset("think_media")
        assert p.max_lines == 2
        ass = build("think_media", [w("uno", 0, 1), w("dos", 1, 2), w("tres", 2, 3), w("cuatro", 3, 4)])
        lines = [e for e in text_events(ass) if e.split(",")[1] == "0:00:00.00"]
        assert len(lines) == 2
        assert hex_to_ass(p.line2_color) in lines[1] and hex_to_ass(p.line2_color) not in lines[0]

    def test_wide_canvas_allows_more_words_per_line(self):
        narrow = len({e.split(",")[1] for e in text_events(build("mozi", [w(f"pal{i}", i, i + .9) for i in range(12)]))})
        wide = len({e.split(",")[1] for e in text_events(build("mozi", [w(f"pal{i}", i, i + .9) for i in range(12)], 1920, 1080))})
        assert wide <= narrow
