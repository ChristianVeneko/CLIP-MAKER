"""Download a video (YouTube, Twitch or Kick) with yt-dlp, cached per platform and section."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from .sources import LIVE_MESSAGE, SourceRef, cache_key, ensure_supported, parse_source

FORMAT = (
    "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b[height<=1080]"
    "/bv*+ba/b"
)
COOKIES_ENV = "CLIPMAKER_COOKIES_FROM_BROWSER"
FULL_NAME = "source.mp4"


class Downloaded(NamedTuple):
    video_id: str  # cache directory name under the workdir
    path: Path
    offset: float  # source time (seconds) of the first frame of ``path`` (0 unless a section was downloaded)


def _ytdlp() -> list[str]:
    return [sys.executable, "-m", "yt_dlp"]


def impersonation_available() -> bool:
    from importlib.util import find_spec

    return find_spec("curl_cffi") is not None


def ytdlp_extra_args(
    platform: str, environ: Mapping[str, str] | None = None, impersonate_available: bool | None = None
) -> list[str]:
    """Per-platform yt-dlp flags: browser impersonation for Kick, optional browser cookies."""
    env = os.environ if environ is None else environ
    can = impersonation_available() if impersonate_available is None else impersonate_available
    args: list[str] = []
    if platform == "kick" and can:
        args += ["--impersonate", "chrome"]
    browser = (env.get(COOKIES_ENV) or "").strip()
    if browser:
        args += ["--cookies-from-browser", browser]
    return args


def _ffmpeg_args() -> list[str]:
    if shutil.which("ffmpeg"):
        return []
    try:
        import imageio_ffmpeg

        return ["--ffmpeg-location", imageio_ffmpeg.get_ffmpeg_exe()]
    except Exception:  # pragma: no cover - depends on environment
        return []


# -- sections ------------------------------------------------------------------------------


def section_spec(time_range: tuple[float, float]) -> str:
    return f"*{time_range[0]:.3f}-{time_range[1]:.3f}"


def section_file_name(time_range: tuple[float, float]) -> str:
    return f"source.r{time_range[0]:g}-{time_range[1]:g}.mp4"


def should_download_section(ref: SourceRef, time_range: tuple[float, float] | None) -> bool:
    """Only non-YouTube VODs (often hours long) are fetched by section."""
    return time_range is not None and ref.kind == "vod" and ref.platform in ("twitch", "kick")


def local_range(time_range: tuple[float, float], offset: float) -> tuple[float, float]:
    """Express a source-time range in the local time of a file whose first frame is at ``offset``."""
    return max(0.0, time_range[0] - offset), max(0.0, time_range[1] - offset)


def find_source(video_dir: Path, time_range: tuple[float, float] | None) -> tuple[Path, float] | None:
    """A cached file usable for ``time_range``: the full download (offset 0) or the matching section."""
    full = video_dir / FULL_NAME
    if full.exists():
        return full, 0.0
    if time_range is not None:
        section = video_dir / section_file_name(time_range)
        if section.exists():
            return section, time_range[0]
    return None


def download_command(
    ytdlp: list[str], url: str, out_template: Path, time_range: tuple[float, float] | None, extra: list[str]
) -> list[str]:
    cmd = [
        *ytdlp, "--no-playlist", "--no-progress", "-f", FORMAT,
        "--merge-output-format", "mp4", "--remux-video", "mp4", *extra,
    ]  # fmt: skip
    if time_range is not None:
        cmd += ["--download-sections", section_spec(time_range), "--force-keyframes-at-cuts"]
    return [*cmd, "-o", str(out_template), url]


# -- errors --------------------------------------------------------------------------------


def friendly_download_error(raw: str) -> str:
    """Readable Spanish message for common yt-dlp failures; unknown ones keep yt-dlp's text."""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    errors = [ln for ln in lines if ln.startswith("ERROR")]
    text = (errors or lines or ["yt-dlp failed"])[-1].removeprefix("ERROR: ")
    low = text.lower()
    if "impersonat" in low:
        return (
            "Kick requiere suplantar un navegador y falta la librería curl-cffi. "
            'Instálala con `uv add "yt-dlp[curl-cffi]"` y reinicia.'
        )
    if "not a bot" in low:
        return (
            "YouTube pidió verificar que no eres un bot. Define CLIPMAKER_COOKIES_FROM_BROWSER "
            "(por ejemplo chrome) para usar las cookies de tu navegador."
        )
    if "subscriber" in low or "sub-only" in low:
        return (
            "Este video es solo para suscriptores. Inicia sesión en Twitch en tu navegador y define "
            "CLIPMAKER_COOKIES_FROM_BROWSER (por ejemplo chrome) para usar tus cookies."
        )
    if "private" in low:
        return "El video es privado y no se puede descargar."
    if "country" in low or "geo" in low:
        return "El video no está disponible en tu país (bloqueo geográfico)."
    if "unsupported url" in low:
        return "Ese enlace no es compatible. Usa un enlace de YouTube, Twitch o Kick."
    if "404" in low or "not found" in low or "does not exist" in low or "removed" in low or "deleted" in low or "no longer available" in low:
        return "El clip o video no existe, fue eliminado o ya no está disponible."
    if "403" in low or "forbidden" in low or "cloudflare" in low:
        return (
            "La plataforma bloqueó la solicitud (403, posiblemente Cloudflare). Actualiza yt-dlp, "
            "confirma que curl-cffi está instalado o inténtalo de nuevo más tarde."
        )
    return text


def _fail(proc: subprocess.CompletedProcess) -> RuntimeError:
    return RuntimeError(friendly_download_error(proc.stderr or ""))


# -- download / probe ----------------------------------------------------------------------


def resolve_video_id(url: str, extra: list[str] | None = None) -> str:
    proc = subprocess.run(
        [*_ytdlp(), "--no-playlist", "--skip-download", "--print", "id", *(extra or []), url],
        capture_output=True, text=True,
    )  # fmt: skip
    if proc.returncode != 0 or not proc.stdout.strip():
        raise _fail(proc)
    return proc.stdout.strip().splitlines()[-1]


def download_video(url: str, workdir: Path, time_range: tuple[float, float] | None = None) -> Downloaded:
    """Download (cached). Twitch/Kick VODs with a ``time_range`` fetch only that section."""
    ref = ensure_supported(url)
    extra = ytdlp_extra_args(ref.platform)
    ident = ref.id or resolve_video_id(url, extra)
    video_id = cache_key(ref.platform, ident)
    target_dir = workdir / video_id
    section = time_range if should_download_section(ref, time_range) else None
    cached = find_source(target_dir, section)
    if cached is not None:
        print(f"[download] cached: {cached[0]}")
        return Downloaded(video_id, *cached)
    target = target_dir / (section_file_name(section) if section else FULL_NAME)
    target_dir.mkdir(parents=True, exist_ok=True)
    what = f"section {section_spec(section)}" if section else "full video"
    print(f"[download] fetching {video_id} ({what}) ...")
    template = target.with_name(target.stem + ".%(ext)s")
    cmd = download_command(_ytdlp(), url, template, section, [*extra, *_ffmpeg_args()])
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise _fail(proc)
    if not target.exists():
        raise RuntimeError(f"yt-dlp finished but {target} was not created")
    return Downloaded(video_id, target, section[0] if section else 0.0)


def parse_probe(stdout: str, url: str = "") -> dict:
    """Reduce yt-dlp ``--dump-json`` output to the fields the UI needs."""
    info = json.loads(stdout.strip().splitlines()[-1])
    if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
        raise RuntimeError(LIVE_MESSAGE)
    ref = parse_source(url)
    return {
        "id": info["id"],
        "title": info.get("title") or info["id"],
        "duration": float(info.get("duration") or 0),
        "thumbnail": info.get("thumbnail") or "",
        "platform": ref.platform,
        "kind": ref.kind if ref.kind in ("clip", "vod") else "vod",
        "uploader": info.get("channel") or info.get("uploader") or info.get("creator") or "",
    }


def probe_url(url: str) -> dict:
    """Fetch metadata (title, duration, thumbnail, platform, ...) without downloading the video."""
    ref = ensure_supported(url)
    proc = subprocess.run(
        [*_ytdlp(), "--no-playlist", "--skip-download", "--dump-json", "--no-warnings",
         *ytdlp_extra_args(ref.platform), url],
        capture_output=True, text=True,
    )  # fmt: skip
    if proc.returncode != 0:
        raise _fail(proc)
    return parse_probe(proc.stdout, url)
