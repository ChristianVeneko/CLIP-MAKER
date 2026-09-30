"""Recognise where a URL comes from (YouTube, Twitch, Kick) and what it points to. Pure, no I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse

Platform = Literal["youtube", "twitch", "kick", "other"]
Kind = Literal["clip", "vod", "live", "unknown"]

LIVE_MESSAGE = (
    "Los directos (streams en vivo) no son compatibles porque nunca terminan. "
    "Usa el enlace de un clip o de un VOD ya finalizado."
)
UNKNOWN_MESSAGE = (
    "Ese enlace no apunta a un clip o VOD concreto. Abre el clip o el VOD y copia su enlace directo."
)

_YT_ID = re.compile(r"^[\w-]{11}$")
_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com",
             "www.youtube-nocookie.com", "youtu.be"}  # fmt: skip
_TWITCH_HOSTS = {"twitch.tv", "www.twitch.tv", "m.twitch.tv", "go.twitch.tv", "clips.twitch.tv"}
_KICK_HOSTS = {"kick.com", "www.kick.com"}
_TWITCH_RESERVED = {"videos", "directory", "clips", "downloads", "jobs", "settings", "subscriptions", "p", "turbo"}
_KICK_RESERVED = {"video", "videos", "categories", "category", "browse", "search", "clips", "dashboard", "following"}


@dataclass(frozen=True)
class SourceRef:
    platform: Platform
    kind: Kind
    id: str | None  # platform-native id when it can be read from the URL alone


class UnsupportedSource(ValueError):
    """The URL cannot be processed (readable Spanish message)."""


def _segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def _first(query: dict[str, list[str]], key: str) -> str | None:
    vals = query.get(key)
    return vals[0] if vals and vals[0] else None


def _youtube(host: str, segs: list[str], query: dict[str, list[str]]) -> SourceRef:
    ident: str | None = None
    kind: Kind = "vod"
    if host == "youtu.be":
        ident = segs[0] if segs else None
    elif segs and segs[0] == "watch":
        ident = _first(query, "v")
    elif len(segs) >= 2 and segs[0] in ("shorts", "embed", "live", "v"):
        ident = segs[1]
        kind = "clip" if segs[0] == "shorts" else "vod"
    return SourceRef("youtube", kind, ident if ident and _YT_ID.match(ident) else None)


def _twitch(host: str, segs: list[str], query: dict[str, list[str]]) -> SourceRef:
    if host == "clips.twitch.tv":
        if segs and segs[0] == "embed":
            slug = _first(query, "clip")
        else:
            slug = segs[0] if segs else None
        return SourceRef("twitch", "clip" if slug else "unknown", slug)
    if len(segs) >= 2 and segs[0] == "videos":
        return SourceRef("twitch", "vod", segs[1].lstrip("v") if segs[1].startswith("v") and segs[1][1:].isdigit() else segs[1])
    if len(segs) >= 3 and segs[1] == "clip":
        return SourceRef("twitch", "clip", segs[2])
    if len(segs) >= 3 and segs[1] == "v" and segs[2].isdigit():
        return SourceRef("twitch", "vod", segs[2])
    if len(segs) == 1 and segs[0] not in _TWITCH_RESERVED:
        return SourceRef("twitch", "live", None)
    return SourceRef("twitch", "unknown", None)


def _kick(segs: list[str], query: dict[str, list[str]]) -> SourceRef:
    clip = _first(query, "clip")
    if clip and len(segs) == 1:
        return SourceRef("kick", "clip", clip)
    if len(segs) >= 3 and segs[1] == "clips":
        return SourceRef("kick", "clip", segs[2])
    if len(segs) >= 3 and segs[1] == "videos":
        return SourceRef("kick", "vod", segs[2])
    if len(segs) >= 2 and segs[0] == "video":
        return SourceRef("kick", "vod", segs[1])
    if len(segs) == 1 and segs[0] not in _KICK_RESERVED:
        return SourceRef("kick", "live", None)
    return SourceRef("kick", "unknown", None)


def parse_source(url: str) -> SourceRef:
    """Classify a URL by platform, kind (clip / vod / live) and native id."""
    try:
        parts = urlparse(url.strip())
    except ValueError:
        return SourceRef("other", "unknown", None)
    host = (parts.hostname or "").lower()
    segs, query = _segments(parts.path), parse_qs(parts.query)
    if host in _YT_HOSTS:
        return _youtube(host, segs, query)
    if host in _TWITCH_HOSTS:
        return _twitch(host, segs, query)
    if host in _KICK_HOSTS:
        return _kick(segs, query)
    return SourceRef("other", "unknown", None)


def detect_platform(url: str) -> Platform:
    return parse_source(url).platform


def ensure_supported(url: str) -> SourceRef:
    """Return the parsed reference or raise :class:`UnsupportedSource` for live streams / listings."""
    ref = parse_source(url)
    if ref.kind == "live":
        raise UnsupportedSource(LIVE_MESSAGE)
    if ref.platform in ("twitch", "kick") and ref.kind == "unknown":
        raise UnsupportedSource(UNKNOWN_MESSAGE)
    return ref


def sanitize_id(ident: str) -> str:
    """Make an id safe as a directory name (letters, digits, ``_`` and ``-`` only)."""
    clean = re.sub(r"[^A-Za-z0-9_-]", "_", ident.strip())
    if not clean:
        raise ValueError("empty id")
    return clean


def cache_key(platform: str, ident: str) -> str:
    """Directory name under the workdir. YouTube keeps its bare id (existing caches stay valid)."""
    clean = sanitize_id(ident)
    return clean if platform == "youtube" else f"{platform}_{clean}"
