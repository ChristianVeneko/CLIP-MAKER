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


class TestPromptOptions:
    def test_every_genre_has_a_hint_and_is_injected(self):
        from clipmaker.options import GENRES
        from clipmaker.selection import GENRE_HINTS

        assert set(GENRES) <= set(GENRE_HINTS)
        seen = set()
        for g in GENRES:
            p = build_prompt(3, 20, 60, genre=g)
            assert GENRE_HINTS[g] in p
            seen.add(GENRE_HINTS[g])
        assert len(seen) == len(GENRES)  # hints are genre specific

    def test_language_names_and_auto(self):
        assert "Spanish" in build_prompt(3, 20, 60, language="es")
        p = build_prompt(3, 20, 60, language="en")
        assert "English" in p and "Spanish" not in p
        auto = build_prompt(3, 20, 60, language="auto")
        assert "same language as the transcript" in auto
        assert "Portuguese" in build_prompt(3, 20, 60, language="pt")

    def test_specific_moments_injected(self):
        p = build_prompt(3, 20, 60, specific_moments="cuando hablan de Bad Bunny")
        assert "cuando hablan de Bad Bunny" in p
        assert "cuando hablan" not in build_prompt(3, 20, 60)

    def test_default_prompt_unchanged_contract(self):
        p = build_prompt(5, 20, 60)
        assert "Spanish" in p and "at most 5" in p


class TestForcedClips:
    def test_forced_clips_keep_requested_range(self):
        from clipmaker.selection import forced_clips

        words = uniform_words(200)
        clips = forced_clips([(30.0, 75.0)], words)
        assert len(clips) == 1
        assert clips[0].start == pytest.approx(30.0, abs=0.6) and clips[0].end == pytest.approx(75.0, abs=1.0)
        assert clips[0].score == 100 and "0:30" in clips[0].title

    def test_forced_ranges_are_not_length_clamped_and_are_bounded_by_video(self):
        from clipmaker.selection import forced_clips

        words = uniform_words(100)
        clips = forced_clips([(10.0, 15.0), (90.0, 500.0)], words)
        assert clips[0].end - clips[0].start >= 4  # 5 s is allowed even if shorter than min
        assert clips[1].end <= words[-1].end + 1e-6

    def test_invalid_ranges_dropped(self):
        from clipmaker.selection import forced_clips

        assert forced_clips([(50.0, 50.0), (500.0, 600.0)], uniform_words(100)) == []

    def test_merge_keeps_forced_first_and_drops_overlaps(self):
        from clipmaker.selection import merge_clips

        forced = [Clip(start=10, end=40, title="F", score=100)]
        auto = [
            Clip(start=30, end=60, title="overlaps", score=90),
            Clip(start=100, end=130, title="A", score=80),
            Clip(start=200, end=230, title="B", score=70),
        ]
        out = merge_clips(forced, auto, max_clips=2)
        assert [c.title for c in out] == ["F", "A"]

    def test_merge_never_drops_forced(self):
        from clipmaker.selection import merge_clips

        forced = [Clip(start=i * 100, end=i * 100 + 30, title=f"F{i}", score=100) for i in range(3)]
        assert len(merge_clips(forced, [], max_clips=1)) == 3
