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
