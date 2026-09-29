"""Tolerant SRT parsing and synthetic word timings (pure)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .subtitles import Word

_TIME_LINE = re.compile(
    r"^\s*(\d{1,2}:\d{1,2}(?::\d{1,2})?[.,]?\d*)\s*-->\s*(\d{1,2}:\d{1,2}(?::\d{1,2})?[.,]?\d*)"
)
_TAGS = re.compile(r"<[^>]*>|\{[^}]*\}")


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def parse_srt_time(text: str) -> float:
    m = re.fullmatch(r"\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d+))?\s*", text)
    if not m:
        raise ValueError(f"invalid SRT time '{text}'")
    h, mi, s, frac = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + (float(f"0.{frac}") if frac else 0.0)


def _clean(text: str) -> str:
    return " ".join(html.unescape(_TAGS.sub("", text)).split())


def parse_srt(text: str) -> list[Cue]:
    """Parse SRT text (BOM, CRLF, ``,`` or ``.`` millis, optional indices). Broken cues are skipped."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.split("\n")]
        idx = next((i for i, ln in enumerate(lines) if _TIME_LINE.match(ln)), None)
        if idx is None:
            continue
        m = _TIME_LINE.match(lines[idx])
        try:
            start, end = parse_srt_time(m.group(1)), parse_srt_time(m.group(2))
        except ValueError:
            continue
        body = _clean(" ".join(lines[idx + 1 :]))
        if end <= start or not body:
            continue
        cues.append(Cue(start, end, body))
    return sorted(cues, key=lambda c: c.start)


def synthesize_words(cue: Cue) -> list[Word]:
    """Distribute the cue duration across its words, weighted by character length."""
    tokens = cue.text.split()
    if not tokens:
        return []
    total = sum(len(t) for t in tokens)
    duration = cue.end - cue.start
    words, t = [], cue.start
    for i, tok in enumerate(tokens):
        end = cue.end if i == len(tokens) - 1 else t + duration * len(tok) / total
        words.append(Word(tok, round(t, 3), round(end, 3)))
        t = end
    return words


def cues_to_transcript(cues: list[Cue], language: str = "und") -> dict:
    """Build a transcript dict shaped like ``transcript.json`` (segments with words)."""
    segments = [
        {
            "id": i,
            "start": c.start,
            "end": c.end,
            "text": " " + c.text,
            "words": [
                {"word": w.text, "start": w.start, "end": w.end, "probability": 1.0}
                for w in synthesize_words(c)
            ],
        }
        for i, c in enumerate(cues)
    ]
    return {
        "language": language,
        "model": "srt",
        "text": " ".join(c.text for c in cues),
        "segments": segments,
    }
