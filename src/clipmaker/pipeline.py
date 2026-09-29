"""Orchestration of the full pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from . import cropping
from .detection import probe_video, sample_face_centers
from .render import (
    HORIZONTAL,
    VERTICAL,
    horizontal_filter,
    render_clip,
    slugify,
    vertical_filter,
)
from .selection import Clip, Segment, format_transcript, load_clips_file, postprocess_clips, select_with_openai
from .subtitles import Word, build_ass, get_style

FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def select_clips(
    segments: list[Segment],
    words: list[Word],
    out_json: Path,
    clips_file: Path | None,
    count: int,
    min_duration: float,
    max_duration: float,
    model: str | None,
) -> list[Clip]:
    if clips_file:
        raw = load_clips_file(clips_file)
        print(f"[select] using manual clips from {clips_file}")
    else:
        print("[select] asking OpenAI for clip candidates ...")
        raw = select_with_openai(format_transcript(segments), count, min_duration, max_duration, model)
    clips = postprocess_clips(raw, words, min_duration, max_duration, count)
    out_json.write_text(
        json.dumps({"clips": [c.model_dump() for c in clips]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[select] {len(clips)} clip(s) -> {out_json}")
    return clips


def render_clips(
    source: Path,
    clips: list[Clip],
    words: list[Word],
    out_dir: Path,
    fmt: str,
    style_name: str,
    sample_fps: float = 3.0,
) -> list[Path]:
    style = get_style(style_name)
    out_w, out_h = VERTICAL if fmt == "vertical" else HORIZONTAL
    src_w, src_h, _, _ = probe_video(source)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for n, clip in enumerate(clips, start=1):
        duration = clip.end - clip.start
        stem = f"{n:02d}_{slugify(clip.title)}"
        mp4, ass = out_dir / f"{stem}.mp4", out_dir / f"{stem}.ass"
        print(f"[render] {stem}  ({clip.start:.1f}s-{clip.end:.1f}s, {duration:.1f}s, {fmt})")
        if fmt == "vertical":
            crop_w = cropping.crop_width_for(src_h)
            times, raw, backend = sample_face_centers(source, clip.start, clip.end, sample_fps)
            found = sum(c is not None for c in raw)
            print(f"[render]   face detection ({backend}): {found}/{len(raw)} samples")
            centers = cropping.smooth_centers(raw, default=src_w / 2, deadzone=src_w * 0.03)
            xs = cropping.centers_to_crop_x(centers, src_w, crop_w)
            keypoints = cropping.build_keypoints(times, xs, duration, step=0.5)
            vf = vertical_filter(crop_w, src_h, cropping.crop_x_expression(keypoints), out_w, out_h)
        else:
            vf = horizontal_filter(out_w, out_h)
        ass.write_text(
            build_ass(words, style, out_w, out_h, clip_start=clip.start, clip_end=clip.end),
            encoding="utf-8",
        )
        render_clip(source, mp4, ass, clip.start, duration, vf, FONTS_DIR if FONTS_DIR.exists() else None)
        outputs.append(mp4)
    return outputs
