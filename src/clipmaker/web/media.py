"""Safe media path resolution and thumbnail generation."""

from __future__ import annotations

import subprocess
from pathlib import Path

MEDIA_TYPES = {".mp4": "video/mp4", ".jpg": "image/jpeg"}


def safe_media_path(base: Path, name: str) -> Path | None:
    """Resolve ``name`` inside ``base`` or return None.

    Only a plain file name with a whitelisted media extension is accepted; separators,
    NUL bytes, ``..`` and symlinks that leave ``base`` are all rejected.
    """
    if not name or name in (".", "..") or any(c in name for c in "/\\\x00"):
        return None
    if Path(name).suffix.lower() not in MEDIA_TYPES:
        return None
    base = base.resolve()
    candidate = (base / name).resolve()
    if candidate.parent != base or not candidate.is_file():
        return None
    return candidate


def make_thumbnail(video: Path, out: Path, at: float = 1.0) -> None:
    """Grab a JPEG frame (max 480px wide) from ``video`` at ``at`` seconds."""
    from ..render import find_ffmpeg

    cmd = [
        find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1",
        "-vf", "scale='min(480,iw)':-2", "-q:v", "4", str(out),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)
    if not out.exists():  # seek past the end of a very short video
        cmd[cmd.index("-ss") + 1] = "0"
        subprocess.run(cmd, check=True, capture_output=True)
