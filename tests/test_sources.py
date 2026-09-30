import pytest

from clipmaker.sources import (
    UnsupportedSource,
    cache_key,
    detect_platform,
    ensure_supported,
    parse_source,
    sanitize_id,
)

CASES = [
    ("https://youtu.be/WLdX-JUfU_k", "youtube", "vod", "WLdX-JUfU_k"),
    ("https://www.youtube.com/watch?v=WLdX-JUfU_k&t=30s", "youtube", "vod", "WLdX-JUfU_k"),
    ("https://m.youtube.com/watch?v=WLdX-JUfU_k", "youtube", "vod", "WLdX-JUfU_k"),
    ("https://www.youtube.com/shorts/abcDEF12345", "youtube", "clip", "abcDEF12345"),
    ("https://www.youtube.com/embed/abcDEF12345", "youtube", "vod", "abcDEF12345"),
    ("https://clips.twitch.tv/CrispyAmazingKumquat-HxOR_mS1", "twitch", "clip", "CrispyAmazingKumquat-HxOR_mS1"),
    ("https://www.twitch.tv/elxokas/clip/CrispyAmazingKumquat-HxOR_mS1?filter=clips", "twitch", "clip", "CrispyAmazingKumquat-HxOR_mS1"),
    ("https://m.twitch.tv/elxokas/clip/CrispyAmazingKumquat-HxOR_mS1", "twitch", "clip", "CrispyAmazingKumquat-HxOR_mS1"),
    ("https://clips.twitch.tv/embed?clip=CrispyAmazingKumquat-HxOR_mS1&parent=x.com", "twitch", "clip", "CrispyAmazingKumquat-HxOR_mS1"),
    ("https://www.twitch.tv/videos/2885611944", "twitch", "vod", "2885611944"),
    ("https://www.twitch.tv/videos/2885611944?t=1h2m3s", "twitch", "vod", "2885611944"),
    ("https://www.twitch.tv/ibai", "twitch", "live", None),
    ("https://kick.com/westcol/clips/clip_01M3FVBZZ5D7TQ13E4M53GX4YZ", "kick", "clip", "clip_01M3FVBZZ5D7TQ13E4M53GX4YZ"),
    ("https://kick.com/westcol?clip=clip_01M3FVBZZ5D7TQ13E4M53GX4YZ", "kick", "clip", "clip_01M3FVBZZ5D7TQ13E4M53GX4YZ"),
    ("https://kick.com/westcol?foo=1&clip=clip_01M3FVBZZ5D7TQ13E4M53GX4YZ", "kick", "clip", "clip_01M3FVBZZ5D7TQ13E4M53GX4YZ"),
    ("https://kick.com/westcol/videos/7b1a2c3d-1111-4222-8333-944455556666", "kick", "vod", "7b1a2c3d-1111-4222-8333-944455556666"),
    ("https://kick.com/video/7b1a2c3d-1111-4222-8333-944455556666", "kick", "vod", "7b1a2c3d-1111-4222-8333-944455556666"),
    ("https://kick.com/westcol", "kick", "live", None),
    ("https://www.kick.com/westcol/", "kick", "live", None),
]


@pytest.mark.parametrize("url,platform,kind,ident", CASES)
def test_parse_source(url, platform, kind, ident):
    ref = parse_source(url)
    assert (ref.platform, ref.kind, ref.id) == (platform, kind, ident)
    assert detect_platform(url) == platform


def test_other_platform():
    assert detect_platform("https://vimeo.com/123") == "other"
    assert parse_source("not a url").platform == "other"
    assert detect_platform("https://notkick.com/x") == "other"
    assert detect_platform("https://evil.com/kick.com/x") == "other"


def test_unknown_kind_for_channel_listings():
    assert parse_source("https://www.twitch.tv/ibai/videos").kind == "unknown"
    assert parse_source("https://www.twitch.tv/ibai/clips").kind == "unknown"
    assert parse_source("https://kick.com/westcol/clips").kind == "unknown"


@pytest.mark.parametrize("url", ["https://www.twitch.tv/ibai", "https://kick.com/westcol"])
def test_ensure_supported_rejects_live(url):
    with pytest.raises(UnsupportedSource, match="directo"):
        ensure_supported(url)


def test_ensure_supported_rejects_listings():
    with pytest.raises(UnsupportedSource):
        ensure_supported("https://www.twitch.tv/ibai/clips")


@pytest.mark.parametrize("url", [c[0] for c in CASES if c[2] != "live"] + ["https://vimeo.com/1"])
def test_ensure_supported_accepts_others(url):
    ensure_supported(url)


def test_cache_key_keeps_bare_id_for_youtube():
    assert cache_key("youtube", "y_WLdX-JUfU") == "y_WLdX-JUfU"
    assert cache_key("twitch", "123") == "twitch_123"
    assert cache_key("kick", "clip_01M") == "kick_clip_01M"
    assert cache_key("twitch", "123") != cache_key("kick", "123")


def test_sanitize_id_is_filesystem_safe():
    assert sanitize_id("a/b\\c..d e") == "a_b_c__d_e"
    assert sanitize_id("../../etc") == "______etc"
    assert sanitize_id("ok-Id_1") == "ok-Id_1"
    with pytest.raises(ValueError):
        sanitize_id("")
