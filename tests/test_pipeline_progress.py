from pathlib import Path

from clipmaker import pipeline
from clipmaker.options import JobOptions
from clipmaker.selection import Clip


def test_render_clips_reports_progress_per_clip(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "probe_video", lambda p: (1920, 1080, 30.0, 100.0))
    monkeypatch.setattr(pipeline, "render_clip", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "build_captions", lambda *a, **k: None)
    events = []
    clips = [Clip(start=0, end=10, title="A"), Clip(start=20, end=30, title="B")]
    outs = pipeline.render_clips(
        Path("src.mp4"), clips, [], tmp_path, JobOptions(aspect_ratio="16:9", caption_style="none"),
        progress=lambda stage, fraction, message: events.append((stage, fraction, message)),
    )
    assert [o.name for o in outs] == ["01_a.mp4", "02_b.mp4"]
    assert [(s, f) for s, f, _ in events] == [("render", 0.0), ("render", 0.5), ("render", 1.0)]
    assert "1/2" in events[0][2] and "2/2" in events[1][2]


def test_render_clips_progress_is_optional(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "probe_video", lambda p: (1920, 1080, 30.0, 100.0))
    monkeypatch.setattr(pipeline, "render_clip", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "build_captions", lambda *a, **k: None)
    pipeline.render_clips(
        Path("src.mp4"), [Clip(start=0, end=5, title="A")], [], tmp_path,
        JobOptions(aspect_ratio="16:9", caption_style="none"),
    )  # must not raise
