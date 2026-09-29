"""Word chunking and ASS subtitle generation (pure, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass

SENTENCE_END = (".", "?", "!", "…")


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class StylePreset:
    name: str
    font: str
    font_size_vertical: int
    font_size_horizontal: int
    text_color: str  # ASS &HAABBGGRR& colour
    highlight_color: str
    outline_color: str
    shadow_color: str
    outline: float
    shadow: float
    pop_scale: int  # peak scale (%) of the active word "pop" animation
    vertical_margin_ratio: float = 0.28  # bottom margin as a share of height -> ~70% down
    horizontal_margin_ratio: float = 0.06


STYLE_PRESETS: dict[str, StylePreset] = {
    "bold-yellow": StylePreset(
        name="bold-yellow",
        font="Montserrat Black",
        font_size_vertical=88,
        font_size_horizontal=66,
        text_color="&H00FFFFFF&",
        highlight_color="&H0000E6FF&",  # #FFE600
        outline_color="&H00000000&",
        shadow_color="&H80000000&",
        outline=8,
        shadow=3,
        pop_scale=118,
    ),
    "clean-white": StylePreset(
        name="clean-white",
        font="Montserrat ExtraBold",
        font_size_vertical=78,
        font_size_horizontal=58,
        text_color="&H00FFFFFF&",
        highlight_color="&H00B4F06B&",  # soft mint green #6BF0B4
        outline_color="&H00000000&",
        shadow_color="&H64000000&",
        outline=4,
        shadow=1,
        pop_scale=108,
    ),
}


def get_style(name: str) -> StylePreset:
    try:
        return STYLE_PRESETS[name]
    except KeyError:
        raise ValueError(
            f"Unknown style '{name}'. Available: {', '.join(sorted(STYLE_PRESETS))}"
        ) from None


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


def _header(style: StylePreset, width: int, height: int) -> str:
    vertical = height > width
    size = style.font_size_vertical if vertical else style.font_size_horizontal
    margin_v = round(height * (style.vertical_margin_ratio if vertical else style.horizontal_margin_ratio))
    margin_h = round(width * 0.06)
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: None\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{style.font},{size},{style.text_color},{style.highlight_color},"
        f"{style.outline_color},{style.shadow_color},-1,0,0,0,100,100,0,0,1,{style.outline:g},"
        f"{style.shadow:g},2,{margin_h},{margin_h},{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )


def build_ass(
    words: list[Word],
    style: StylePreset,
    width: int,
    height: int,
    clip_start: float = 0.0,
    clip_end: float | None = None,
    linger: float = 0.12,
) -> str:
    """Build an ASS document with karaoke-style word highlighting.

    Word times are absolute (source video) times; they are re-based so that the clip
    starts at 0. One event is emitted per word: the whole chunk is shown and the active
    word is coloured with the accent colour and given a short scale "pop".
    """
    if clip_end is None:
        clip_end = max((w.end for w in words), default=clip_start)
    local = rebase_words(words, clip_start, clip_end)
    limit = clip_end - clip_start
    vertical = height > width
    chunks = chunk_words(
        local,
        max_words=3,
        max_chars=14 if vertical else 26,
    )
    lines: list[str] = []
    pop = style.pop_scale
    for ci, chunk in enumerate(chunks):
        next_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else limit
        for wi, active in enumerate(chunk):
            start = active.start
            if wi + 1 < len(chunk):
                end = chunk[wi + 1].start
            else:
                end = min(active.end + linger, next_start, limit)
            if end <= start:
                end = start + 0.05
            parts = []
            for wj, w in enumerate(chunk):
                text = escape_ass_text(w.text).upper()
                if wj == wi:
                    tag = (
                        f"{{\\c{style.highlight_color}\\fscx{round(pop * 0.8)}\\fscy{round(pop * 0.8)}"
                        f"\\t(0,90,\\fscx{pop}\\fscy{pop})\\t(90,180,\\fscx100\\fscy100)}}"
                    )
                else:
                    tag = f"{{\\c{style.text_color}\\fscx100\\fscy100}}"
                parts.append(tag + text)
            lines.append(
                f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,"
                + " ".join(parts)
            )
    return _header(style, width, height) + "\n".join(lines) + "\n"
