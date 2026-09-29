"""Caption presets (Opus-Clip-like looks) and ASS generation.

Pure logic: layout is computed from font metrics, every caption line is positioned with
``\\pos`` so highlight boxes (drawings) line up with the text.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from .fontmetrics import load_metrics
from .subtitles import Word, chunk_words, escape_ass_text, format_ass_time, rebase_words

FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

Measure = Callable[["CaptionPreset", str, float], float]


@dataclass(frozen=True)
class CaptionPreset:
    id: str
    name: str
    font: str  # family name as libass/fontconfig sees it
    font_family: str  # CSS-friendly family (for web previews)
    font_file: str
    size_ratio: float  # em size (CSS-like px) as a share of min(width, height)
    text_color: str  # "#RRGGBB" for non-active words
    active_color: str
    uppercase: bool = True
    max_words: int = 3
    max_lines: int = 1
    fill_mode: str = "active"  # active | progressive | none
    outline_color: str = "#000000"
    outline_ratio: float = 0.0
    active_outline_color: str | None = None
    shadow_ratio: float = 0.0
    shadow_alpha: int = 0x80
    italic: bool = False
    pop: str = "pop"  # none | pop | bounce
    pop_scale: int = 118
    box: str = "none"  # none | line (rounded box behind the block) | word (behind active word)
    box_color: str = "#000000"
    line2_color: str | None = None

    @property
    def active_outline(self) -> str:
        return self.active_outline_color or self.outline_color


PRESETS: dict[str, CaptionPreset] = {
    p.id: p
    for p in [
        CaptionPreset(
            "karaoke", "Karaoke", "Montserrat Black", "Montserrat", "Montserrat-Black.ttf", 0.078,
            text_color="#FFFFFF", active_color="#FFE600", max_words=6, max_lines=2,
            fill_mode="progressive", outline_ratio=0.11, shadow_ratio=0.03, pop="none",
        ),  # fmt: skip
        CaptionPreset(
            "deep_diver", "Deep Diver", "Barlow Condensed SemiBold", "Barlow Condensed",
            "BarlowCondensed-SemiBold.ttf", 0.095, text_color="#B5B5B5", active_color="#111111",
            uppercase=False, max_words=8, max_lines=2, pop="none", box="line", box_color="#F2F2F2",
        ),  # fmt: skip
        CaptionPreset(
            "youshaei", "Youshaei", "Poppins SemiBold", "Poppins", "Poppins-SemiBold.ttf", 0.078,
            text_color="#F4F1EA", active_color="#2EE6C5", max_words=5, max_lines=1,
            shadow_ratio=0.06, shadow_alpha=0x70, pop="none",
        ),  # fmt: skip
        CaptionPreset(
            "pod_p", "Pod P", "Anton", "Anton", "Anton-Regular.ttf", 0.092,
            text_color="#FFFFFF", active_color="#FF2E93", max_words=2, outline_color="#2A0A1A",
            outline_ratio=0.07, active_outline_color="#8A0F4E", shadow_ratio=0.03, pop_scale=115,
        ),  # fmt: skip
        CaptionPreset(
            "mozi", "Mozi", "Montserrat Black", "Montserrat", "Montserrat-Black.ttf", 0.085,
            text_color="#FFFFFF", active_color="#2BFF3A", max_words=4, max_lines=2,
            outline_ratio=0.11, shadow_ratio=0.03, pop_scale=118,
        ),  # fmt: skip
        CaptionPreset(
            "beasty", "Beasty", "Bangers", "Bangers", "Bangers-Regular.ttf", 0.088,
            text_color="#FFFFFF", active_color="#FFFFFF", max_words=3, outline_ratio=0.12,
            shadow_ratio=0.04, italic=True, pop="bounce", pop_scale=135,
        ),  # fmt: skip
        CaptionPreset(
            "simple", "Simple", "Anton", "Anton", "Anton-Regular.ttf", 0.095,
            text_color="#FFFFFF", active_color="#FFFFFF", max_words=2, outline_ratio=0.10,
            pop="none",
        ),  # fmt: skip
        CaptionPreset(
            "popline", "Popline", "Montserrat ExtraBold", "Montserrat", "Montserrat-ExtraBold.ttf",
            0.078, text_color="#FFFFFF", active_color="#FFFFFF", max_words=5, max_lines=2,
            shadow_ratio=0.03, pop="none", box="word", box_color="#7B3FE4",
        ),  # fmt: skip
        CaptionPreset(
            "think_media", "Think Media", "Bebas Neue", "Bebas Neue", "BebasNeue-Regular.ttf", 0.10,
            text_color="#FFFFFF", active_color="#FFFFFF", max_words=6, max_lines=2,
            fill_mode="none", outline_ratio=0.07, line2_color="#FFD60A", pop_scale=108,
        ),  # fmt: skip
    ]
}
ALIASES = {"bold-yellow": "mozi", "clean-white": "youshaei"}
NONE = "none"


def resolve_style_id(name: str) -> str:
    key = name.strip().lower()
    key = ALIASES.get(key, key)
    if key == NONE or key in PRESETS:
        return key
    raise ValueError(f"Unknown caption style '{name}'. Available: {', '.join([*PRESETS, NONE])}")


def get_preset(name: str) -> CaptionPreset:
    key = resolve_style_id(name)
    if key == NONE:
        raise ValueError("'none' has no preset")
    return PRESETS[key]


def preset_catalog() -> list[dict]:
    """Machine-readable catalog (for UIs to render sample cards)."""
    out = []
    for p in PRESETS.values():
        colors = {"text": p.text_color, "active": p.active_color, "outline": p.outline_color}
        if p.box != "none":
            colors["box"] = p.box_color
        if p.line2_color:
            colors["line2"] = p.line2_color
        out.append(
            {
                "id": p.id, "name": p.name, "font_family": p.font_family, "font_file": p.font_file,
                "font_weight_hint": p.font, "uppercase": p.uppercase, "max_lines": p.max_lines,
                "max_words": p.max_words, "italic": p.italic, "fill_mode": p.fill_mode,
                "box": p.box, "colors": colors, "size_ratio": p.size_ratio,
                "outline_ratio": p.outline_ratio, "shadow_ratio": p.shadow_ratio, "pop": p.pop,
            }
        )  # fmt: skip
    out.append(
        {"id": NONE, "name": "None", "font_family": "", "font_file": "", "font_weight_hint": "",
         "uppercase": False, "max_lines": 0, "max_words": 0, "italic": False, "fill_mode": "none",
         "box": "none", "colors": {}, "size_ratio": 0.0, "outline_ratio": 0.0,
         "shadow_ratio": 0.0, "pop": "none"}
    )  # fmt: skip
    return out


# --- pure helpers ---------------------------------------------------------------------


def hex_to_ass(color: str, alpha: int = 0) -> str:
    m = re.fullmatch(r"#([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})", color)
    if not m:
        raise ValueError(f"Invalid colour '{color}', expected #RRGGBB")
    r, g, b = (x.upper() for x in m.groups())
    return f"&H{alpha:02X}{b}{g}{r}&"


def rounded_rect_path(w: float, h: float, r: float) -> str:
    """ASS drawing path (origin top-left) of a rounded rectangle."""
    r = max(0.0, min(r, w / 2, h / 2))
    k = r * 0.5523  # bezier circle approximation
    f = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")  # noqa: E731
    return (
        f"m {f(r)} 0 l {f(w - r)} 0 b {f(w - r + k)} 0 {f(w)} {f(r - k)} {f(w)} {f(r)} "
        f"l {f(w)} {f(h - r)} b {f(w)} {f(h - r + k)} {f(w - r + k)} {f(h)} {f(w - r)} {f(h)} "
        f"l {f(r)} {f(h)} b {f(r - k)} {f(h)} 0 {f(h - r + k)} 0 {f(h - r)} "
        f"l 0 {f(r)} b 0 {f(r - k)} {f(r - k)} 0 {f(r)} 0"
    )


def plan_lines(words: list[Word], max_lines: int) -> list[list[Word]]:
    """Split a chunk into at most ``max_lines`` lines with balanced character counts."""
    if max_lines <= 1 or len(words) < 2:
        return [list(words)]
    n = min(max_lines, len(words))
    if n == 2:
        total = sum(len(w.text) for w in words) + len(words) - 1
        best, best_diff, run = 1, None, 0
        for i in range(1, len(words)):
            run += len(words[i - 1].text) + 1
            diff = abs(run - 1 - (total - run))
            if best_diff is None or diff < best_diff:
                best, best_diff = i, diff
        return [list(words[:best]), list(words[best:])]
    size = -(-len(words) // n)
    return [list(words[i : i + size]) for i in range(0, len(words), size)]


def _default_measure(preset: CaptionPreset, text: str, size: float) -> float:
    return load_metrics(FONTS_DIR / preset.font_file).text_width(text, size)


def _anchor_ratio(width: int, height: int) -> float:
    """Where the last caption line sits, as a share of the height."""
    ratio = height / width
    if ratio > 1.2:
        return 0.72
    if ratio > 0.9:
        return 0.80
    return 0.87


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _header(preset: CaptionPreset, width: int, height: int, em: float, fontsize: int) -> str:
    outline = round(preset.outline_ratio * em, 1)
    shadow = round(preset.shadow_ratio * em, 1)
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\nYCbCr Matrix: None\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{preset.font},{fontsize},{hex_to_ass(preset.text_color)},"
        f"{hex_to_ass(preset.active_color)},{hex_to_ass(preset.outline_color)},"
        f"{hex_to_ass('#000000', preset.shadow_alpha)},0,{-1 if preset.italic else 0},0,0,100,100,0,0,1,"
        f"{_fmt(outline)},{_fmt(shadow)},5,0,0,0,1\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )


def _pop_tags(preset: CaptionPreset) -> str:
    if preset.pop == "pop":
        p = preset.pop_scale
        s = round(p * 0.8)
        return f"\\fscx{s}\\fscy{s}\\t(0,90,\\fscx{p}\\fscy{p})\\t(90,180,\\fscx100\\fscy100)"
    if preset.pop == "bounce":
        p = preset.pop_scale
        lo = round(p * 0.5)
        under = 92
        return (
            f"\\fscx{lo}\\fscy{lo}\\t(0,90,\\fscx{p}\\fscy{p})"
            f"\\t(90,170,\\fscx{under}\\fscy{under})\\t(170,240,\\fscx100\\fscy100)"
        )
    return "\\fscx100\\fscy100"


def _word_color(p: CaptionPreset, line_idx: int, idx: int, active: int) -> str:
    if p.line2_color and line_idx == 1:
        return p.line2_color
    if p.fill_mode == "progressive":
        return p.active_color if idx <= active else p.text_color
    if p.fill_mode == "active":
        return p.active_color if idx == active else p.text_color
    return p.text_color


def build_captions(
    words: list[Word],
    style: str | CaptionPreset,
    width: int,
    height: int,
    clip_start: float = 0.0,
    clip_end: float | None = None,
    linger: float = 0.12,
    measure: Measure | None = None,
) -> str | None:
    """Build an ASS document for ``style`` (``None`` for the ``none`` style).

    Word times are absolute source times; they are re-based so the clip starts at 0.
    One event per (word, line) is emitted; boxes are separate drawing events on layer 0.
    """
    if isinstance(style, str):
        if resolve_style_id(style) == NONE:
            return None
        preset = get_preset(style)
    else:
        preset = style
    measure = measure or _default_measure
    if clip_end is None:
        clip_end = max((w.end for w in words), default=clip_start)
    local = rebase_words(words, clip_start, clip_end)
    limit = clip_end - clip_start

    base = min(width, height)
    scale = 0.8 if width > height else 1.0
    size = base * preset.size_ratio * scale  # em size in px
    metrics = load_metrics(FONTS_DIR / preset.font_file)
    fontsize = round(metrics.line_height(size))  # libass: Fontsize == ascent + descent (win metrics)
    usable_w = width * 0.88
    sample = "ESTAOCRNLDPMU" if preset.uppercase else "estaocrnldpmu"
    avg_em = measure(preset, sample, 100.0) / (100.0 * len(sample))
    chars_per_line = max(6, int(usable_w / (avg_em * size)))
    chunks = chunk_words(local, max_words=preset.max_words, max_chars=chars_per_line * preset.max_lines)

    cap = metrics.cap_height
    dy = (metrics.ascent - metrics.descent - cap) / 2  # cap-centre offset from line-box centre (em)
    anchor_y = height * _anchor_ratio(width, height)
    outline_c, shadow_pad = hex_to_ass(preset.outline_color), 0

    def label(w: Word) -> str:
        t = escape_ass_text(w.text)
        return t.upper() if preset.uppercase else t

    out: list[str] = []
    for ci, chunk in enumerate(chunks):
        next_start = chunks[ci + 1][0].start if ci + 1 < len(chunks) else limit
        lines = plan_lines(chunk, preset.max_lines)
        texts = [[label(w) for w in ln] for ln in lines]
        widths = [measure(preset, " ".join(t), size) for t in texts]
        fit = min(1.0, usable_w / max(widths)) if max(widths) > 0 else 1.0
        fsize = size * fit
        widths = [x * fit for x in widths]
        step = (cap + 0.32) * fsize
        n = len(lines)
        centers = [anchor_y - (n - 1 - i) * step for i in range(n)]  # visual centres of the lines
        cx = width / 2
        fs_tag = f"\\fs{round(metrics.line_height(fsize))}" if fit < 1.0 else ""
        starts = [w.start for w in chunk]
        ends = []
        for wi, w in enumerate(chunk):
            end = chunk[wi + 1].start if wi + 1 < len(chunk) else min(w.end + linger, next_start, limit)
            ends.append(end if end > w.start else w.start + 0.05)

        if preset.box == "line":
            pad_x, pad_y = 0.45 * fsize, 0.32 * fsize
            bw = max(widths) + 2 * pad_x
            top = centers[0] - cap * fsize / 2 - pad_y
            bh = (centers[-1] - centers[0]) + cap * fsize + 2 * pad_y
            out.append(
                f"Dialogue: 0,{format_ass_time(starts[0])},{format_ass_time(ends[-1])},Default,,0,0,0,,"
                f"{{\\an7\\pos({_fmt(cx - bw / 2)},{_fmt(top)})\\p1\\bord0\\shad0\\1c{hex_to_ass(preset.box_color)}}}"
                f"{rounded_rect_path(bw, bh, 0.35 * bh if n == 1 else 0.22 * bh)}{{\\p0}}"
            )

        index_of = {id(w): i for i, w in enumerate(chunk)}
        for wi, active in enumerate(chunk):
            start, end = starts[wi], ends[wi]
            ts, te = format_ass_time(start), format_ass_time(end)
            if preset.box == "word":
                li = next(i for i, ln in enumerate(lines) if any(w is active for w in ln))
                pos_in_line = next(i for i, w in enumerate(lines[li]) if w is active)
                prefix = " ".join(texts[li][:pos_in_line]) + (" " if pos_in_line else "")
                left = cx - widths[li] / 2 + measure(preset, prefix, size) * fit
                aw = measure(preset, texts[li][pos_in_line], size) * fit
                pad_x, pad_y = 0.22 * fsize, 0.2 * fsize
                bw, bh = aw + 2 * pad_x, cap * fsize + 2 * pad_y
                out.append(
                    f"Dialogue: 0,{ts},{te},Default,,0,0,0,,"
                    f"{{\\an7\\pos({_fmt(left - pad_x)},{_fmt(centers[li] - bh / 2)})\\p1\\bord0\\shad0"
                    f"\\1c{hex_to_ass(preset.box_color)}}}{rounded_rect_path(bw, bh, 0.3 * bh)}{{\\p0}}"
                )
            for li, ln in enumerate(lines):
                parts = []
                for wj, w in enumerate(ln):
                    gi = index_of[id(w)]
                    is_active = w is active
                    color = hex_to_ass(_word_color(preset, li, gi, wi))
                    oc = hex_to_ass(preset.active_outline) if is_active else outline_c
                    anim = _pop_tags(preset) if is_active else "\\fscx100\\fscy100"
                    parts.append(f"{{\\c{color}\\3c{oc}{anim}}}{texts[li][wj]}")
                line_y = centers[li] - dy * fsize
                out.append(
                    f"Dialogue: 1,{ts},{te},Default,,0,0,0,,"
                    f"{{\\an5\\pos({_fmt(cx)},{_fmt(line_y)}){fs_tag}}}" + " ".join(parts)
                )
    return _header(preset, width, height, size, fontsize) + "\n".join(out) + "\n"
