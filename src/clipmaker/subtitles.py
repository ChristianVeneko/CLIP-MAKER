"""Word model and word/time helpers shared by the caption builders (pure, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass

SENTENCE_END = (".", "?", "!", "…")


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


def format_ass_time(seconds: float) -> str:
    """Format seconds as an ASS timestamp ``H:MM:SS.cc`` (centisecond precision)."""
    cs_total = max(0, round(seconds * 100))
    cs = cs_total % 100
    total_s = cs_total // 100
    return f"{total_s // 3600}:{(total_s % 3600) // 60:02d}:{total_s % 60:02d}.{cs:02d}"


def escape_ass_text(text: str) -> str:
    """Strip characters that libass would interpret as override tags or line breaks."""
    cleaned = text.replace("\\", "").replace("{", "").replace("}", "")
    return " ".join(cleaned.split())


def chunk_words(
    words: list[Word],
    max_words: int = 3,
    max_chars: int = 16,
    max_gap: float = 0.5,
) -> list[list[Word]]:
    """Group words into short on-screen chunks (Opus Clip style, 1-3 words)."""
    chunks: list[list[Word]] = []
    current: list[Word] = []

    def flush() -> None:
        nonlocal current
        if current:
            chunks.append(current)
            current = []

    for word in words:
        if not word.text.strip():
            continue
        if current:
            gap = word.start - current[-1].end
            chars = sum(len(x.text.strip()) for x in current) + len(current) + len(word.text.strip())
            if len(current) >= max_words or gap > max_gap or chars > max_chars:
                flush()
        current.append(word)
        if word.text.strip().endswith(SENTENCE_END):
            flush()
    flush()
    return chunks


def rebase_words(words: list[Word], clip_start: float, clip_end: float) -> list[Word]:
    """Keep words inside [clip_start, clip_end] and shift them so the clip starts at 0."""
    out: list[Word] = []
    for w in words:
        if w.start >= clip_end or w.end <= clip_start:
            continue
        start = max(0.0, w.start - clip_start)
        end = min(clip_end - clip_start, w.end - clip_start)
        out.append(Word(w.text, start, end))
    return out
