import pytest

from clipmaker.selection import (
    Clip,
    Segment,
    build_prompt,
    format_transcript,
    load_clips_file,
    postprocess_clips,
)
from clipmaker.subtitles import Word


def mkwords(spec):
    """spec: list of (text, start, end)."""
    return [Word(t, s, e) for t, s, e in spec]


def uniform_words(n, step=1.0):
    """n words, 1 word/sec; a sentence ends every 10 words."""
    out = []
    for i in range(n):
        text = f"w{i}" + ("." if (i + 1) % 10 == 0 else "")
        out.append(Word(text, i * step, i * step + 0.9 * step))
    return out


def test_format_transcript_lines():
    segs = [Segment(0.0, 4.2, "Hola a todos"), Segment(65.5, 70.0, "Segundo tramo")]
    text = format_transcript(segs)
    assert text.splitlines()[0] == "[0.0-4.2] Hola a todos"
    assert text.splitlines()[1] == "[65.5-70.0] Segundo tramo"


def test_build_prompt_mentions_constraints():
    p = build_prompt(count=5, min_duration=20, max_duration=60)
    assert "5" in p and "20" in p and "60" in p
    assert "Spanish" in p


class TestPostprocess:
    def test_snaps_to_word_boundaries(self):
        words = uniform_words(200)
        clips = [Clip(start=30.3, end=70.4, title="t", hook="h", score=80)]
        out = postprocess_clips(clips, words, min_duration=20, max_duration=60, max_clips=5)
        assert len(out) == 1
        starts = {round(x.start, 2) for x in words}
        ends = {round(x.end, 2) for x in words}
        assert any(abs(out[0].start - s) < 0.5 for s in starts)
        assert any(abs(out[0].end - e) < 0.5 for e in ends)

    def test_prefers_sentence_start(self):
        words = uniform_words(200)
        # sentence starts at word 30 (t=30.0); requested start is 31.6 -> nearest sentence start within tolerance? 30 is 1.6 away
        clips = [Clip(start=31.6, end=75.0, title="t", hook="h", score=50)]
        out = postprocess_clips(clips, words, min_duration=20, max_duration=60, max_clips=5)
        assert out[0].start == pytest.approx(30.0, abs=0.2) or out[0].start == pytest.approx(40.0, abs=0.2)

    def test_clamps_long_clip(self):
        words = uniform_words(300)
        clips = [Clip(start=10.0, end=150.0, title="t", hook="h", score=50)]
        out = postprocess_clips(clips, words, min_duration=20, max_duration=60, max_clips=5)
        assert out[0].end - out[0].start <= 60.01
        assert out[0].end - out[0].start >= 20

    def test_extends_short_clip(self):
        words = uniform_words(300)
        clips = [Clip(start=100.0, end=105.0, title="t", hook="h", score=50)]
        out = postprocess_clips(clips, words, min_duration=20, max_duration=60, max_clips=5)
        assert 20 <= out[0].end - out[0].start <= 60.01

    def test_drops_overlaps_keeps_higher_score(self):
        words = uniform_words(400)
        clips = [
            Clip(start=10, end=50, title="low", hook="", score=40),
            Clip(start=30, end=70, title="high", hook="", score=90),
            Clip(start=200, end=240, title="far", hook="", score=60),
        ]
        out = postprocess_clips(clips, words, min_duration=20, max_duration=60, max_clips=5)
        assert [c.title for c in out] == ["high", "far"]

    def test_sorted_by_score_and_limited(self):
        words = uniform_words(1000)
        clips = [Clip(start=i * 100, end=i * 100 + 40, title=str(i), hook="", score=i * 10) for i in range(1, 8)]
        out = postprocess_clips(clips, words, min_duration=20, max_duration=60, max_clips=3)
        assert [c.title for c in out] == ["7", "6", "5"]

    def test_clamps_to_video_bounds(self):
        words = uniform_words(100)
        clips = [Clip(start=-5, end=30, title="t", hook="", score=1)]
        out = postprocess_clips(clips, words, min_duration=20, max_duration=60, max_clips=5)
        assert out[0].start >= 0

    def test_score_clamped_0_100(self):
        words = uniform_words(100)
        out = postprocess_clips(
            [Clip(start=10, end=50, title="t", hook="", score=150)], words, 20, 60, 5
        )
        assert out[0].score == 100

    def test_impossible_short_video_dropped(self):
        words = uniform_words(10)
        out = postprocess_clips(
            [Clip(start=0, end=9, title="t", hook="", score=1)], words, 20, 60, 5
        )
        assert out == []

    def test_no_words_returns_clamped_as_is(self):
        out = postprocess_clips(
            [Clip(start=0, end=80, title="t", hook="", score=1)], [], 20, 60, 5
        )
        assert out[0].end - out[0].start == pytest.approx(60)


class TestLoadClipsFile:
    def test_object_schema(self, tmp_path):
        f = tmp_path / "c.json"
        f.write_text('{"clips":[{"start":1,"end":30,"title":"A","hook":"h","score":70}]}')
        clips = load_clips_file(f)
        assert clips[0].title == "A" and clips[0].score == 70

    def test_list_schema_with_defaults(self, tmp_path):
        f = tmp_path / "c.json"
        f.write_text('[{"start":1,"end":30,"title":"A"}]')
        clips = load_clips_file(f)
        assert clips[0].hook == "" and clips[0].score == 50

    def test_invalid(self, tmp_path):
        f = tmp_path / "c.json"
        f.write_text('{"nope":1}')
        with pytest.raises(ValueError):
            load_clips_file(f)
