"""Clip selection: prompt building, OpenAI call (isolated) and pure post-processing."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from .subtitles import SENTENCE_END, Word

DEFAULT_MODEL = "gpt-5"
SNAP_TOLERANCE = 2.5  # seconds
PAD_START = 0.10
PAD_END = 0.25


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


class Clip(BaseModel):
    start: float
    end: float
    title: str
    hook: str = ""
    score: float = 50


# Schema sent to OpenAI (Structured Outputs): every field required, no defaults.
class LLMClip(BaseModel):
    start: float = Field(description="Clip start in seconds (from the transcript timestamps)")
    end: float = Field(description="Clip end in seconds")
    title: str = Field(description="Catchy title in Spanish")
    hook: str = Field(description="Why this clip is viral / the hook, in Spanish")
    score: int = Field(description="Virality score from 0 to 100")


class LLMSelection(BaseModel):
    clips: list[LLMClip]


def format_transcript(segments: list[Segment]) -> str:
    return "\n".join(f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}" for s in segments)


def build_prompt(count: int, min_duration: float, max_duration: float) -> str:
    return (
        "You are an expert short-form video editor (TikTok, Reels, YouTube Shorts). "
        "You receive the timestamped Spanish transcript of a long video. "
        f"Pick the {count} best self-contained moments most likely to go viral as short clips.\n"
        "Rules:\n"
        f"- Each clip must last between {min_duration:g} and {max_duration:g} seconds.\n"
        "- Clips must not overlap and must start/end on natural sentence boundaries.\n"
        "- Start with a strong hook (a bold claim, a question, a surprising fact or emotional peak) "
        "and end on a satisfying conclusion; it must make sense without the rest of the video.\n"
        "- Use the exact timestamps (in seconds) shown in the transcript brackets.\n"
        "- Write `title` and `hook` in Spanish. `score` is an integer 0-100 for viral potential.\n"
        f"Return at most {count} clips."
    )


def select_with_openai(
    transcript_text: str,
    count: int,
    min_duration: float,
    max_duration: float,
    model: str | None = None,
) -> list[Clip]:
    """Ask OpenAI for clip candidates using Structured Outputs (Responses API)."""
    from openai import OpenAI  # imported lazily so the rest works without a key

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it, or pass --clips-file to skip clip selection."
        )
    client = OpenAI()
    response = client.responses.parse(
        model=model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        input=[
            {"role": "system", "content": build_prompt(count, min_duration, max_duration)},
            {"role": "user", "content": transcript_text},
        ],
        text_format=LLMSelection,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("OpenAI returned no parsed clip selection (possible refusal).")
    return [Clip(**c.model_dump()) for c in parsed.clips]


def load_clips_file(path: str | Path) -> list[Clip]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("clips"), list):
        items = data["clips"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f"{path}: expected a list of clips or an object with a 'clips' list")
    try:
        return [Clip(**item) for item in items]
    except Exception as exc:  # pydantic validation error
        raise ValueError(f"{path}: invalid clip entry: {exc}") from exc


def _nearest(candidates: list[float], target: float, tolerance: float) -> float | None:
    best = min(candidates, key=lambda c: abs(c - target), default=None)
    if best is not None and abs(best - target) <= tolerance:
        return best
    return None


def _overlaps(a: Clip, b: Clip) -> bool:
    return a.start < b.end and b.start < a.end


def postprocess_clips(
    clips: list[Clip],
    words: list[Word],
    min_duration: float,
    max_duration: float,
    max_clips: int,
) -> list[Clip]:
    """Snap to word/sentence boundaries, clamp durations, drop overlaps, sort by score."""
    words = sorted(words, key=lambda w: w.start)
    video_end = words[-1].end if words else None

    word_starts = [w.start for w in words]
    word_ends = [w.end for w in words]
    sent_starts = [
        w.start
        for i, w in enumerate(words)
        if i == 0 or words[i - 1].text.strip().endswith(SENTENCE_END)
    ]
    sent_ends = [w.end for w in words if w.text.strip().endswith(SENTENCE_END)]

    fixed: list[Clip] = []
    for c in clips:
        start = max(0.0, c.start)
        end = c.end
        if end <= start:
            continue
        if not words:
            end = min(end, start + max_duration)
            if end - start < min_duration:
                continue
        else:
            start = min(start, video_end)
            snapped = _nearest(sent_starts, start, SNAP_TOLERANCE)
            if snapped is None:
                snapped = _nearest(word_starts, start, float("inf"))
            start = snapped if snapped is not None else start

            snapped_end = _nearest(sent_ends, end, SNAP_TOLERANCE)
            if snapped_end is None:
                snapped_end = _nearest(word_ends, end, float("inf"))
            end = snapped_end if snapped_end is not None else end

            lo, hi = start + min_duration, start + max_duration
            if not (lo <= end <= hi):
                target = hi if end > hi else lo
                in_range = lambda vals: [v for v in vals if lo <= v <= hi]  # noqa: E731
                pool = in_range(sent_ends) or in_range(word_ends)
                if not pool:
                    continue
                end = max(pool) if end > hi else min(pool)
            start = max(0.0, start - PAD_START)
            end = min(video_end, end + PAD_END, start + max_duration)
        fixed.append(
            Clip(
                start=round(start, 3),
                end=round(end, 3),
                title=c.title,
                hook=c.hook,
                score=max(0.0, min(100.0, c.score)),
            )
        )

    kept: list[Clip] = []
    for c in sorted(fixed, key=lambda x: x.score, reverse=True):
        if any(_overlaps(c, k) for k in kept):
            continue
        kept.append(c)
        if len(kept) >= max_clips:
            break
    return kept
