import pytest

from clipmaker.subtitles import (
    STYLE_PRESETS,
    Word,
    build_ass,
    chunk_words,
    escape_ass_text,
    format_ass_time,
    get_style,
    rebase_words,
)


def w(text, start, end):
    return Word(text=text, start=start, end=end)


class TestFormatAssTime:
    def test_zero(self):
        assert format_ass_time(0) == "0:00:00.00"

    def test_centiseconds_rounding(self):
        assert format_ass_time(1.234) == "0:00:01.23"
        assert format_ass_time(1.236) == "0:00:01.24"

    def test_minutes_and_hours(self):
        assert format_ass_time(61.5) == "0:01:01.50"
        assert format_ass_time(3725.0) == "1:02:05.00"

    def test_rounding_carry(self):
        assert format_ass_time(59.999) == "0:01:00.00"

    def test_negative_clamped(self):
        assert format_ass_time(-3) == "0:00:00.00"


class TestEscape:
    def test_braces_and_backslashes_removed(self):
        assert "{" not in escape_ass_text("hola {\\an8} mundo")
        assert "\\" not in escape_ass_text("a\\Nb")

    def test_newlines_become_spaces(self):
        assert escape_ass_text("a\nb") == "a b"

    def test_accents_preserved(self):
        assert escape_ass_text("¿Qué pasó?") == "¿Qué pasó?"


class TestChunking:
    def test_max_words(self):
        words = [w(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(7)]
        chunks = chunk_words(words, max_words=3, max_chars=100)
        assert [len(c) for c in chunks] == [3, 3, 1]

    def test_preserves_order_and_all_words(self):
        words = [w(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(10)]
        flat = [x for c in chunk_words(words) for x in c]
        assert flat == words

    def test_break_on_sentence_punctuation(self):
        words = [w("Hola.", 0, 0.3), w("Esto", 0.3, 0.6), w("funciona", 0.6, 1.0)]
        chunks = chunk_words(words, max_words=3, max_chars=100)
        assert [[x.text for x in c] for c in chunks] == [["Hola."], ["Esto", "funciona"]]

    def test_break_on_long_gap(self):
        words = [w("uno", 0, 0.3), w("dos", 2.0, 2.3)]
        chunks = chunk_words(words, max_words=3, max_chars=100, max_gap=0.5)
        assert len(chunks) == 2

    def test_break_on_max_chars(self):
        words = [w("extraordinario", 0, 0.5), w("resultado", 0.5, 1.0), w("final", 1.0, 1.4)]
        chunks = chunk_words(words, max_words=3, max_chars=16)
        assert [[x.text for x in c] for c in chunks] == [["extraordinario"], ["resultado", "final"]]

    def test_empty(self):
        assert chunk_words([]) == []

    def test_blank_words_dropped(self):
        words = [w("  ", 0, 0.1), w("hola", 0.1, 0.4)]
        assert chunk_words(words) == [[words[1]]]


class TestRebase:
    def test_shifts_and_filters(self):
        words = [w("a", 9.0, 9.5), w("b", 10.0, 10.5), w("c", 12.0, 12.5), w("d", 20.0, 20.5)]
        out = rebase_words(words, clip_start=10.0, clip_end=13.0)
        assert [(x.text, x.start, x.end) for x in out] == [("b", 0.0, 0.5), ("c", 2.0, 2.5)]

    def test_clamps_end_to_clip(self):
        out = rebase_words([w("a", 12.5, 14.0)], clip_start=10.0, clip_end=13.0)
        assert out[0].end == pytest.approx(3.0)


class TestStyles:
    def test_has_at_least_two_presets(self):
        assert {"bold-yellow", "clean-white"} <= set(STYLE_PRESETS)

    def test_unknown_style(self):
        with pytest.raises(ValueError):
            get_style("nope")


class TestBuildAss:
    words = [w("hola", 0.0, 0.4), w("mundo", 0.4, 0.9), w("cruel", 1.0, 1.5)]

    def test_structure(self):
        ass = build_ass(self.words, get_style("bold-yellow"), 1080, 1920)
        assert "[Script Info]" in ass and "[V4+ Styles]" in ass and "[Events]" in ass
        assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
        assert ass.count("Dialogue:") == 3  # one event per word

    def test_uppercase(self):
        ass = build_ass(self.words, get_style("bold-yellow"), 1080, 1920)
        assert "HOLA" in ass and "hola" not in ass

    def test_active_word_highlighted(self):
        style = get_style("bold-yellow")
        ass = build_ass(self.words, style, 1080, 1920)
        first = [l for l in ass.splitlines() if l.startswith("Dialogue:")][0]
        assert style.highlight_color in first
        assert "\\t(" in first  # pop animation

    def test_events_do_not_overlap(self):
        ass = build_ass(self.words, get_style("clean-white"), 1920, 1080)
        times = []
        for l in ass.splitlines():
            if l.startswith("Dialogue:"):
                parts = l.split(",", 9)
                times.append((parts[1], parts[2]))
        assert times[0] == ("0:00:00.00", "0:00:00.40")
        assert times[1][0] == "0:00:00.40"

    def test_vertical_margin_lower_third(self):
        v = build_ass(self.words, get_style("bold-yellow"), 1080, 1920)
        h = build_ass(self.words, get_style("bold-yellow"), 1920, 1080)
        def margin_v(ass):
            line = [l for l in ass.splitlines() if l.startswith("Style:")][0]
            return int(line.split(",")[21])
        assert margin_v(v) > margin_v(h)
        assert margin_v(v) == pytest.approx(1920 * 0.28, abs=2)

    def test_font_in_style(self):
        ass = build_ass(self.words, get_style("bold-yellow"), 1080, 1920)
        assert "Montserrat Black" in ass

    def test_rebased_times(self):
        words = [w("hola", 100.0, 100.4)]
        ass = build_ass(words, get_style("bold-yellow"), 1080, 1920, clip_start=100.0, clip_end=110.0)
        assert "0:00:00.00,0:00:00.40" in ass or "0:00:00.00,0:00:00.5" in ass

    def test_last_word_extended_but_bounded(self):
        # a lone chunk: last word may linger slightly but never past the clip end
        words = [w("fin", 9.9, 10.0)]
        ass = build_ass(words, get_style("bold-yellow"), 1080, 1920, clip_start=0.0, clip_end=10.05)
        end = [l for l in ass.splitlines() if l.startswith("Dialogue:")][0].split(",")[2]
        assert end <= "0:00:10.05"
