"""ffmpeg command building (pure) and clip rendering (execution)."""

from __future__ import annotations

import re
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

VERTICAL = (1080, 1920)
HORIZONTAL = (1920, 1080)


def slugify(text: str, max_len: int = 50) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", norm.lower()).strip("-")
    return slug[:max_len].strip("-") or "clip"


def escape_filter_path(path: str) -> str:
    """Escape a path for use inside an ffmpeg filter option value."""
    p = path.replace("\\", "/")
    p = p.replace(":", "\\:").replace("'", "\\'")
    return p


def horizontal_filter(out_w: int, out_h: int) -> str:
    return (
        f"scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )


def vertical_filter(crop_w: int, crop_h: int, x_expr: str, out_w: int, out_h: int) -> str:
    return (
        f"crop=w={crop_w}:h={crop_h}:x='{x_expr}':y=0,"
        f"scale={out_w}:{out_h}:flags=lanczos,setsar=1"
    )


def subtitle_filter(ass_path: str, fonts_dir: str | None) -> str:
    f = f"ass=filename='{escape_filter_path(ass_path)}'"
    if fonts_dir:
        f += f":fontsdir='{escape_filter_path(fonts_dir)}'"
    return f


def build_ffmpeg_command(
    ffmpeg: str,
    source: str,
    output: str,
    start: float,
    duration: float,
    filter_script: str,
    crf: int = 18,
    preset: str = "medium",
) -> list[str]:
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-ss", f"{start:.3f}", "-i", source, "-t", f"{duration:.3f}",
        "-filter_script:v", filter_script,
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        output,
    ]  # fmt: skip


def _has_ass_filter(ffmpeg: str) -> bool:
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    except OSError:
        return False
    return any(line.split()[1:2] == ["ass"] for line in out.splitlines())


@lru_cache(maxsize=1)
def find_ffmpeg() -> str:
    """Pick an ffmpeg that has libass: $CLIPMAKER_FFMPEG, system ffmpeg, then imageio-ffmpeg."""
    import os
    import shutil

    candidates = []
    if os.environ.get("CLIPMAKER_FFMPEG"):
        candidates.append(os.environ["CLIPMAKER_FFMPEG"])
    system = shutil.which("ffmpeg")
    if system:
        candidates.append(system)
    for c in candidates:
        if _has_ass_filter(c):
            return c
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if _has_ass_filter(bundled):
            return bundled
    except Exception:  # pragma: no cover - depends on environment
        pass
    raise RuntimeError(
        "No ffmpeg with the 'ass' (libass) filter found. Install one (e.g. a full ffmpeg build) "
        "or set CLIPMAKER_FFMPEG."
    )


def render_clip(
    source: Path,
    out_path: Path,
    ass_path: Path,
    start: float,
    duration: float,
    video_filter: str,
    fonts_dir: Path | None,
) -> None:
    """Run a single ffmpeg pass: seek, crop/scale, burn subtitles, encode H.264 + AAC."""
    graph = video_filter + "," + subtitle_filter(str(ass_path.resolve()), str(fonts_dir.resolve()) if fonts_dir else None)
    script = out_path.with_suffix(".filter.txt")
    script.write_text(graph, encoding="utf-8")
    cmd = build_ffmpeg_command(find_ffmpeg(), str(source), str(out_path), start, duration, str(script))
    try:
        subprocess.run(cmd, check=True)
    finally:
        script.unlink(missing_ok=True)
