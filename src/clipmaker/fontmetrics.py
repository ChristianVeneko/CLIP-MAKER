"""Font metrics (text width, vertical metrics) read from the bundled TTF files."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class FontMetrics:
    """All values are in em units (1.0 == the em size in pixels).

    ``ascent``/``descent`` are the Windows metrics: libass sizes a font so that
    ``ascent + descent`` equals the ASS ``Fontsize``, not the em.
    """

    advances: dict[str, float] = field(repr=False)
    default_advance: float
    ascent: float
    descent: float  # positive
    cap_height: float
    x_height: float

    def text_width(self, text: str, size: float) -> float:
        return sum(self.advances.get(ch, self.default_advance) for ch in text) * size

    def line_height(self, size: float) -> float:
        return (self.ascent + self.descent) * size


@lru_cache(maxsize=32)
def load_metrics(path: str | Path) -> FontMetrics:
    from fontTools.ttLib import TTFont

    font = TTFont(str(path), lazy=True)
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    hmtx = font["hmtx"]
    advances = {chr(cp): hmtx[name][0] / upm for cp, name in cmap.items()}
    os2 = font["OS/2"]
    return FontMetrics(
        advances=advances,
        default_advance=hmtx[".notdef"][0] / upm if ".notdef" in hmtx.metrics else 0.5,
        ascent=os2.usWinAscent / upm,
        descent=os2.usWinDescent / upm,
        cap_height=(getattr(os2, "sCapHeight", 0) or 0.7 * upm) / upm,
        x_height=(getattr(os2, "sxHeight", 0) or 0.5 * upm) / upm,
    )
