"""Download a YouTube video with yt-dlp (cached)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FORMAT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b[height<=1080]"


def _ytdlp() -> list[str]:
    return [sys.executable, "-m", "yt_dlp"]


def resolve_video_id(url: str) -> str:
    out = subprocess.run(
        [*_ytdlp(), "--no-playlist", "--skip-download", "--print", "id", url],
        check=True, capture_output=True, text=True,
    )  # fmt: skip
    return out.stdout.strip().splitlines()[-1]


def download_video(url: str, workdir: Path) -> tuple[str, Path]:
    """Return (video_id, path to source.mp4). Skips the download if the file exists."""
    video_id = resolve_video_id(url)
    target_dir = workdir / video_id
    target = target_dir / "source.mp4"
    if target.exists():
        print(f"[download] cached: {target}")
        return video_id, target
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[download] fetching {video_id} ...")
    subprocess.run(
        [
            *_ytdlp(), "--no-playlist", "--no-progress", "-f", FORMAT, "--merge-output-format", "mp4",
            "-o", str(target_dir / "source.%(ext)s"), url,
        ],
        check=True,
    )  # fmt: skip
    if not target.exists():
        raise RuntimeError(f"yt-dlp finished but {target} was not created")
    return video_id, target
