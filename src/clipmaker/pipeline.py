"""Orchestration of the full pipeline (I/O glue around the pure modules)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from . import cropping
from .captions import FONTS_DIR, build_captions
from .detection import probe_video, sample_faces
from .framing import plan_framing
from .moments import extract_ranges
from .options import JobOptions
from .render import fit_filter, render_clip, slugify, vertical_filter
from .selection import (
    Clip,
    Segment,
    forced_clips,
    format_transcript,
    load_clips_file,
    merge_clips,
    postprocess_clips,
    fits_single_clip,
    select_with_openai,
    whole_source_clip,
)
from .srt import cues_to_transcript, parse_srt
from .subtitles import Word, rebase_words
from .transcribe import segments_and_words, transcribe_video, transcript_cache_name
from .zoom import zoom_expression, zoom_keyframes, zoom_triggers


# progress(stage, fraction 0..1 within the stage, human-readable message)
ProgressFn = Callable[[str, float, str], None]


def clip_ranges_in_window(
    ranges: list[tuple[float, float]], window: tuple[float, float] | None
) -> list[tuple[float, float]]:
    """Intersect explicit ranges with the processed time window (pure)."""
    if window is None:
        return list(ranges)
    out = []
    for a, b in ranges:
        a, b = max(a, window[0]), min(b, window[1])
        if b - a >= 1.0:
            out.append((a, b))
    return out


def restrict_transcript(data: dict, window: tuple[float, float] | None) -> dict:
    """Keep only segments/words inside ``window`` (used for SRT input with a time range)."""
    if window is None:
        return data
    segments = []
    for seg in data["segments"]:
        if seg["end"] <= window[0] or seg["start"] >= window[1]:
            continue
        words = [w for w in seg.get("words", []) if w["end"] > window[0] and w["start"] < window[1]]
        segments.append({**seg, "words": words})
    return {**data, "segments": segments}


def source_local_window(start: float, end: float, source_offset: float) -> tuple[float, float]:
    """Source-time [start, end] -> time inside a file whose first frame is at ``source_offset``."""
    return max(0.0, start - source_offset), max(0.0, end - source_offset)


def prepare_transcript(
    source: Path, video_dir: Path, options: JobOptions, whisper_model: str, source_offset: float = 0.0
) -> dict:
    if options.srt_path:
        print(f"[transcribe] using SRT {options.srt_path} (whisper skipped)")
        text = Path(options.srt_path).read_text(encoding="utf-8-sig", errors="replace")
        cues = parse_srt(text)
        if not cues:
            raise ValueError(f"{options.srt_path}: no valid SRT cues found")
        return restrict_transcript(cues_to_transcript(cues, options.language), options.time_range)
    cache = video_dir / transcript_cache_name(options.time_range, options.language)
    return transcribe_video(source, cache, whisper_model, options.language, options.time_range, source_offset)


def select_clips(
    segments: list[Segment],
    words: list[Word],
    out_json: Path,
    options: JobOptions,
    clips_file: Path | None = None,
    source_duration: float | None = None,
    source_title: str | None = None,
) -> list[Clip]:
    min_d, max_d = options.duration_range
    ranges, remaining = extract_ranges(options.specific_moments)
    forced = forced_clips(clip_ranges_in_window(ranges, options.time_range), words)
    if forced:
        print(f"[select] {len(forced)} explicit range(s) forced as clips")

    auto: list[Clip] = []
    wanted = options.max_clips - len(forced)
    if clips_file:
        print(f"[select] using manual clips from {clips_file}")
        auto = postprocess_clips(load_clips_file(clips_file), words, min_d, max_d, options.max_clips)
    elif wanted <= 0:
        pass
    elif (
        not forced and options.time_range is None and source_duration is not None
        and fits_single_clip(source_duration, max_d)
    ):
        print(f"[select] source is only {source_duration:.0f}s: using it whole as one clip (OpenAI skipped)")
        auto = [whole_source_clip(source_duration, source_title or "")]
    elif ranges and not os.environ.get("OPENAI_API_KEY"):
        print("[select] OPENAI_API_KEY not set; using only the explicit ranges")
    else:
        model = options.resolved_model()
        print(f"[select] asking OpenAI ({model}) for clip candidates ...")
        raw = select_with_openai(
            format_transcript(segments), wanted, min_d, max_d, model,
            genre=options.genre, language=options.language, specific_moments=remaining,
        )  # fmt: skip
        auto = postprocess_clips(raw, words, min_d, max_d, wanted)
    clips = merge_clips(forced, auto, options.max_clips)
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
    options: JobOptions,
    sample_fps: float = 6.0,
    progress: ProgressFn | None = None,
    source_offset: float = 0.0,
) -> list[Path]:
    """Render clips. Clip/word times are in source time; ``source_offset`` is the source time of the
    first frame of ``source`` (non-zero for downloaded VOD sections)."""
    out_w, out_h = options.output_size
    src_w, src_h, _, _ = probe_video(source)
    crop_w = cropping.crop_width_for(src_h, out_w / out_h)
    needs_crop = crop_w < src_w - 2
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    total = len(clips)
    report = progress or (lambda stage, fraction, message: None)
    for n, clip in enumerate(clips, start=1):
        report("render", (n - 1) / total, f"Rendering clip {n}/{total}")
        duration = clip.end - clip.start
        seek, seek_end = source_local_window(clip.start, clip.end, source_offset)
        stem = f"{n:02d}_{slugify(clip.title)}"
        mp4, ass = out_dir / f"{stem}.mp4", out_dir / f"{stem}.ass"
        print(f"[render] {stem}  ({clip.start:.1f}s-{clip.end:.1f}s, {duration:.1f}s, {options.aspect_ratio})")
        zoom_expr = None
        if options.auto_zoom:
            triggers = zoom_triggers(rebase_words(words, clip.start, clip.end), duration)
            zoom_expr = zoom_expression(zoom_keyframes(triggers, duration))
            print(f"[render]   auto-zoom: {len(triggers)} punch-in(s)")
        if needs_crop:
            times, samples, backend = sample_faces(source, seek, seek_end, sample_fps)
            keypoints, info = plan_framing(times, samples, src_w, crop_w, duration, sample_fps)
            found = sum(bool(s) for s in samples)
            print(
                f"[render]   faces ({backend}): {found}/{len(samples)} samples, {info['tracks']} track(s), "
                f"{info['speaker_switches']} speaker switch(es), {info['cuts']} hard cut(s)"
            )
            vf = vertical_filter(crop_w, src_h, cropping.crop_x_expression(keypoints), out_w, out_h, zoom_expr)
        else:
            vf = fit_filter(src_w, src_h, out_w, out_h, zoom_expr)
        ass_text = build_captions(words, options.caption_style, out_w, out_h, clip_start=clip.start, clip_end=clip.end)
        if ass_text is not None:
            ass.write_text(ass_text, encoding="utf-8")
        render_clip(
            source, mp4, ass if ass_text is not None else None, seek, duration, vf,
            FONTS_DIR if FONTS_DIR.exists() else None,
        )  # fmt: skip
        outputs.append(mp4)
    report("render", 1.0, f"Rendered {total} clip(s)")
    return outputs


__all__ = [
    "prepare_transcript", "render_clips", "select_clips", "segments_and_words",
    "clip_ranges_in_window", "restrict_transcript", "source_local_window",
]  # fmt: skip
