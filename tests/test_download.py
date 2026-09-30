from pathlib import Path

import pytest

from clipmaker.download import (
    FORMAT,
    download_command,
    find_source,
    friendly_download_error,
    local_range,
    parse_probe,
    section_file_name,
    section_spec,
    should_download_section,
    ytdlp_extra_args,
)
from clipmaker.sources import parse_source


def test_section_spec_and_file_name():
    assert section_spec((90.0, 150.5)) == "*90.000-150.500"
    assert section_file_name((90.0, 150.5)) == "source.r90-150.5.mp4"
    assert section_file_name((0.0, 60.0)) == "source.r0-60.mp4"


def test_should_download_section_only_for_non_youtube_vods():
    rng = (10.0, 70.0)
    assert should_download_section(parse_source("https://www.twitch.tv/videos/1"), rng)
    assert should_download_section(parse_source("https://kick.com/video/7b1a2c3d-1111-4222-8333-944455556666"), rng)
    assert not should_download_section(parse_source("https://www.twitch.tv/videos/1"), None)
    assert not should_download_section(parse_source("https://youtu.be/abcDEF12345"), rng)
    assert not should_download_section(parse_source("https://clips.twitch.tv/Slug-abc"), rng)


def test_local_range_shifts_and_clamps():
    assert local_range((600.0, 660.0), 600.0) == (0.0, 60.0)
    assert local_range((600.0, 660.0), 0.0) == (600.0, 660.0)
    assert local_range((590.0, 660.0), 600.0) == (0.0, 60.0)


def test_extra_args_kick_impersonates_when_available():
    assert ytdlp_extra_args("kick", {}, impersonate_available=True) == ["--impersonate", "chrome"]
    assert ytdlp_extra_args("kick", {}, impersonate_available=False) == []
    assert ytdlp_extra_args("twitch", {}, impersonate_available=True) == []


def test_extra_args_cookies_from_browser_env():
    env = {"CLIPMAKER_COOKIES_FROM_BROWSER": " chrome "}
    assert ytdlp_extra_args("twitch", env, impersonate_available=False) == ["--cookies-from-browser", "chrome"]
    assert ytdlp_extra_args("kick", env, impersonate_available=True) == [
        "--impersonate", "chrome", "--cookies-from-browser", "chrome",
    ]
    assert ytdlp_extra_args("twitch", {"CLIPMAKER_COOKIES_FROM_BROWSER": " "}, impersonate_available=False) == []


def test_download_command_full_and_section():
    base = download_command(["py", "-m", "yt_dlp"], "u", Path("/w/source.%(ext)s"), None, ["--x"])
    assert base[:3] == ["py", "-m", "yt_dlp"] and "--x" in base and base[-1] == "u"
    assert "--download-sections" not in base
    assert FORMAT in base and "mp4" in base
    sec = download_command(["py"], "u", Path("/w/s.%(ext)s"), (10.0, 20.0), [])
    i = sec.index("--download-sections")
    assert sec[i + 1] == "*10.000-20.000" and "--force-keyframes-at-cuts" in sec


def test_find_source_prefers_full_file_then_section(tmp_path):
    assert find_source(tmp_path, (10.0, 20.0)) is None
    (tmp_path / section_file_name((10.0, 20.0))).write_bytes(b"x")
    assert find_source(tmp_path, (10.0, 20.0)) == (tmp_path / "source.r10-20.mp4", 10.0)
    assert find_source(tmp_path, None) is None
    (tmp_path / "source.mp4").write_bytes(b"x")
    assert find_source(tmp_path, (10.0, 20.0)) == (tmp_path / "source.mp4", 0.0)
    assert find_source(tmp_path, None) == (tmp_path / "source.mp4", 0.0)


def test_parse_probe_youtube_fields():
    out = parse_probe(
        'warning\n{"id": "abc", "title": "T", "duration": 61.5, "thumbnail": "http://x/y.jpg", '
        '"uploader": "Chan", "formats": []}',
        "https://youtu.be/abc",
    )
    assert out == {
        "id": "abc", "title": "T", "duration": 61.5, "thumbnail": "http://x/y.jpg",
        "platform": "youtube", "kind": "vod", "uploader": "Chan",
    }


def test_parse_probe_twitch_clip_and_channel_fallback():
    out = parse_probe(
        '{"id": "Slug-1", "title": "C", "duration": 27, "creator": "someone", "channel": "elxokas"}',
        "https://clips.twitch.tv/Slug-1",
    )
    assert out["platform"] == "twitch" and out["kind"] == "clip" and out["uploader"] == "elxokas"
    assert out["thumbnail"] == "" and out["duration"] == 27.0


def test_parse_probe_rejects_live_metadata():
    with pytest.raises(RuntimeError, match="directo"):
        parse_probe('{"id": "x", "title": "t", "is_live": true}', "https://youtu.be/x")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ERROR: [twitch:vod] 123: This video is only available for subscribers", "suscriptores"),
        ("ERROR: [youtube] x: Private video. Sign in if you've been granted access", "privado"),
        ("ERROR: [twitch:clips] x: Unable to download JSON metadata: HTTP Error 404: Not Found", "eliminado"),
        ("ERROR: [Kick] x: Unable to download webpage: HTTP Error 403: Forbidden", "Cloudflare"),
        ("ERROR: Unsupported URL: https://example.com/x", "no es compatible"),
        ("ERROR: [Kick] x: The extractor is attempting impersonation, but no impersonate target is available", "curl-cffi"),
        ("ERROR: [youtube] x: The uploader has not made this video available in your country", "país"),
    ],
)
def test_friendly_download_error(raw, expected):
    assert expected in friendly_download_error(raw)


def test_friendly_download_error_keeps_unknown_message():
    assert friendly_download_error("ERROR: weird failure") == "weird failure"
