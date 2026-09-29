"""Render still previews of the caption presets on a frame of a real video."""

from __future__ import annotations

from pathlib import Path

from .captions import FONTS_DIR, PRESETS, build_captions
from .render import render_frame, vertical_filter
from .cropping import crop_width_for
from .subtitles import Word

SAMPLE_TEXT = ["esto", "es", "lo", "que", "nadie", "te", "dice", "sobre", "el", "éxito"]


def sample_words(at: float, active_index: int = 3) -> list[Word]:
    """A representative sentence whose ``active_index``-th word is being spoken at ``at``."""
    words, t = [], at - 0.1 - 0.3 * active_index
    for text in SAMPLE_TEXT:
        words.append(Word(text, round(t, 3), round(t + 0.28, 3)))
        t += 0.3
    return words


def render_style_previews(
    source: Path, out_dir: Path, at: float, src_w: int, src_h: int, center_x: float, size: tuple[int, int]
) -> list[Path]:
    out_w, out_h = size
    crop_w = min(src_w, int(src_h * out_w / out_h) // 2 * 2)
    x = max(0, min(src_w - crop_w, round(center_x - crop_w / 2)))
    vf = vertical_filter(crop_w, src_h, str(x), out_w, out_h)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    words = sample_words(at)
    for name in PRESETS:
        ass = out_dir / f"{name}.ass"
        ass.write_text(build_captions(words, name, out_w, out_h) or "", encoding="utf-8")
        png = out_dir / f"{name}.png"
        render_frame(source, png, at, vf, ass, FONTS_DIR)
        ass.unlink()
        paths.append(png)
    return paths
