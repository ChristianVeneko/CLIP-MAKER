import pytest

from clipmaker.srt import Cue, cues_to_transcript, parse_srt, parse_srt_time, synthesize_words
from clipmaker.transcribe import segments_and_words

SAMPLE = """1
00:00:01,000 --> 00:00:03,500
Hola a todos

2
00:00:04,000 --> 00:00:06,000
Esto es <i>una</i> prueba
de varias líneas
"""


class TestTime:
    def test_comma_and_dot(self):
        assert parse_srt_time("00:01:02,500") == pytest.approx(62.5)
        assert parse_srt_time("00:01:02.500") == pytest.approx(62.5)

    def test_short_millis_and_no_hours(self):
        assert parse_srt_time("01:02,5") == pytest.approx(62.5)
        assert parse_srt_time("1:02:03,25") == pytest.approx(3723.25)

    def test_invalid(self):
        with pytest.raises(ValueError):
            parse_srt_time("abc")


class TestParse:
    def test_basic(self):
        cues = parse_srt(SAMPLE)
        assert cues == [
            Cue(1.0, 3.5, "Hola a todos"),
            Cue(4.0, 6.0, "Esto es una prueba de varias líneas"),
        ]

    def test_bom_and_crlf(self):
        cues = parse_srt("﻿" + SAMPLE.replace("\n", "\r\n"))
        assert len(cues) == 2 and cues[0].text == "Hola a todos"

    def test_dot_millis_and_missing_index(self):
        cues = parse_srt("00:00:01.000 --> 00:00:02.000\nhola\n")
        assert cues == [Cue(1.0, 2.0, "hola")]

    def test_strips_markup(self):
        cues = parse_srt("1\n00:00:01,000 --> 00:00:02,000\n{\\an8}<b>Hola</b> &amp; adiós\n")
        assert cues[0].text == "Hola & adiós"

    def test_skips_empty_and_broken_cues(self):
        text = "1\n00:00:01,000 --> 00:00:02,000\n\n\n2\nnot a time line\nfoo\n\n3\n00:00:05,000 --> 00:00:04,000\nreversed\n\n4\n00:00:06,000 --> 00:00:07,000\nok\n"
        assert parse_srt(text) == [Cue(6.0, 7.0, "ok")]

    def test_sorted_by_start(self):
        text = "1\n00:00:05,000 --> 00:00:06,000\nb\n\n2\n00:00:01,000 --> 00:00:02,000\na\n"
        assert [c.text for c in parse_srt(text)] == ["a", "b"]

    def test_empty(self):
        assert parse_srt("") == []


class TestSynthesizeWords:
    def test_weighted_by_length_and_contiguous(self):
        words = synthesize_words(Cue(0.0, 10.0, "aa bbbbbb"))
        assert [w.text for w in words] == ["aa", "bbbbbb"]
        assert words[0].start == 0.0 and words[-1].end == pytest.approx(10.0)
        assert words[0].end == words[1].start
        assert words[0].end - words[0].start == pytest.approx(2.5)  # 2 / 8 of 10s

    def test_single_word(self):
        w = synthesize_words(Cue(1.0, 2.0, "hola"))[0]
        assert (w.start, w.end) == (1.0, 2.0)

    def test_no_words(self):
        assert synthesize_words(Cue(0, 1, "   ")) == []


class TestTranscript:
    def test_roundtrip_through_segments_and_words(self):
        data = cues_to_transcript(parse_srt(SAMPLE))
        segments, words = segments_and_words(data)
        assert [s.text.strip() for s in segments][0] == "Hola a todos"
        assert [w.text for w in words][:3] == ["Hola", "a", "todos"]
        assert len(words) == 3 + 7
        assert all(a.end <= b.start + 1e-9 for a, b in zip(words, words[1:]))
