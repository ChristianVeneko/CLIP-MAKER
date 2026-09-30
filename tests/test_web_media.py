import shutil
import subprocess

import pytest

from clipmaker.web.media import make_thumbnail, safe_media_path


def test_safe_media_path_accepts_plain_media(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    assert safe_media_path(tmp_path, "a.mp4") == (tmp_path / "a.mp4").resolve()


@pytest.mark.parametrize("name", ["../a.mp4", "a/../a.mp4", "/abs.mp4", "..", "", "job.json", "a.txt", "a\\b.mp4", "a\x00.mp4"])
def test_safe_media_path_rejects(tmp_path, name):
    (tmp_path / "a.mp4").write_bytes(b"x")
    assert safe_media_path(tmp_path, name) is None


def test_safe_media_path_rejects_symlink_escape(tmp_path):
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"x")
    d = tmp_path / "job"
    d.mkdir()
    (d / "link.mp4").symlink_to(outside)
    assert safe_media_path(d, "link.mp4") is None


def test_safe_media_path_missing_file(tmp_path):
    assert safe_media_path(tmp_path, "nope.mp4") is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_make_thumbnail_creates_jpeg(tmp_path):
    video = tmp_path / "v.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10:duration=2",
         "-pix_fmt", "yuv420p", str(video)], check=True,
    )  # fmt: skip
    out = tmp_path / "t.jpg"
    make_thumbnail(video, out, at=0.5)
    assert out.read_bytes()[:2] == b"\xff\xd8"
