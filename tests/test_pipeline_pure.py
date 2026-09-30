from clipmaker.pipeline import clip_ranges_in_window, restrict_transcript


def test_ranges_intersect_window():
    r = [(100.0, 200.0), (50.0, 60.0), (300.0, 400.0)]
    assert clip_ranges_in_window(r, (80.0, 350.0)) == [(100.0, 200.0), (300.0, 350.0)]
    assert clip_ranges_in_window(r, None) == r


def test_short_intersections_dropped():
    assert clip_ranges_in_window([(10.0, 20.0)], (19.5, 30.0)) == []


def test_restrict_transcript_filters_segments_and_words():
    data = {
        "segments": [
            {"start": 0, "end": 5, "text": "a", "words": [{"word": "a", "start": 0, "end": 5}]},
            {"start": 10, "end": 20, "text": "b c", "words": [
                {"word": "b", "start": 10, "end": 15}, {"word": "c", "start": 15, "end": 20}]},
            {"start": 30, "end": 40, "text": "d", "words": [{"word": "d", "start": 30, "end": 40}]},
        ]
    }  # fmt: skip
    out = restrict_transcript(data, (12.0, 25.0))
    assert len(out["segments"]) == 1
    assert [w["word"] for w in out["segments"][0]["words"]] == ["b", "c"]
    assert restrict_transcript(data, None) is data


def test_source_local_window_offsets_section_downloads():
    from clipmaker.pipeline import source_local_window

    assert source_local_window(3605.0, 3650.0, 3600.0) == (5.0, 50.0)
    assert source_local_window(10.0, 20.0, 0.0) == (10.0, 20.0)
    assert source_local_window(3599.0, 3650.0, 3600.0) == (0.0, 50.0)


def test_whole_source_clip_for_short_sources():
    from clipmaker.selection import fits_single_clip, whole_source_clip

    assert fits_single_clip(27.0, 90.0) and fits_single_clip(90.0, 90.0)
    assert not fits_single_clip(91.0, 90.0) and not fits_single_clip(0.0, 90.0)
    c = whole_source_clip(27.4, "Título del clip")
    assert (c.start, c.end, c.title, c.score) == (0.0, 27.4, "Título del clip", 100)
    assert whole_source_clip(10.0, "  ").title == "Clip completo"


def test_select_clips_short_source_skips_openai(tmp_path, monkeypatch):
    from clipmaker import pipeline
    from clipmaker.options import JobOptions

    def boom(*a, **k):
        raise AssertionError("OpenAI must not be called")

    monkeypatch.setattr(pipeline, "select_with_openai", boom)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    clips = pipeline.select_clips(
        [], [], tmp_path / "sel.json", JobOptions(), source_duration=27.0, source_title="Jaja"
    )
    assert len(clips) == 1 and clips[0].start == 0.0 and clips[0].end == 27.0 and clips[0].title == "Jaja"


def test_select_clips_long_source_still_uses_openai(tmp_path, monkeypatch):
    from clipmaker import pipeline
    from clipmaker.options import JobOptions
    from clipmaker.selection import Clip

    calls = []
    monkeypatch.setattr(pipeline, "select_with_openai", lambda *a, **k: calls.append(1) or [Clip(start=0, end=30, title="x")])
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    pipeline.select_clips([], [], tmp_path / "sel.json", JobOptions(), source_duration=600.0)
    assert calls
