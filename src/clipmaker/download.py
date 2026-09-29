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


def parse_probe(stdout: str) -> dict:
    """Reduce yt-dlp ``--dump-json`` output to the fields the UI needs."""
    import json

    info = json.loads(stdout.strip().splitlines()[-1])
    return {
        "id": info["id"],
        "title": info.get("title") or info["id"],
        "duration": float(info.get("duration") or 0),
        "thumbnail": info.get("thumbnail") or "",
    }


def probe_url(url: str) -> dict:
    """Fetch metadata (title, duration, thumbnail, id) without downloading the video."""
    proc = subprocess.run(
        [*_ytdlp(), "--no-playlist", "--skip-download", "--dump-json", "--no-warnings", url],
        capture_output=True, text=True,
    )  # fmt: skip
    if proc.returncode != 0:
        lines = [ln for ln in proc.stderr.splitlines() if ln.strip()]
        raise RuntimeError((lines[-1] if lines else "yt-dlp failed").removeprefix("ERROR: "))
    return parse_probe(proc.stdout)
