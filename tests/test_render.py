import pytest

from clipmaker.render import (
    build_ffmpeg_command,
    escape_filter_path,
    horizontal_filter,
    slugify,
    vertical_filter,
)


def test_slugify():
    assert slugify("¡Cómo ganar más dinero!") == "como-ganar-mas-dinero"
    assert slugify("   ") == "clip"
    assert len(slugify("a" * 200)) <= 50


def test_escape_filter_path():
    assert escape_filter_path("/a/b c/d.ass") == "/a/b c/d.ass"
    assert escape_filter_path("C:\\x\\y.ass") == "C\\:/x/y.ass"
    assert escape_filter_path("/a/it's.ass") == "/a/it\\'s.ass"


def test_horizontal_filter():
    f = horizontal_filter(1920, 1080)
    assert "scale=1920:1080" in f and "pad=1920:1080" in f and "force_original_aspect_ratio=decrease" in f


def test_vertical_filter_contains_crop_and_scale():
    f = vertical_filter(crop_w=606, crop_h=1080, x_expr="120", out_w=1080, out_h=1920)
    assert f.startswith("crop=w=606:h=1080:x='120':y=0")
    assert "scale=1080:1920" in f


class TestCommand:
    def base(self, **kw):
        args = dict(
            ffmpeg="ffmpeg",
            source="src.mp4",
            output="out.mp4",
            start=12.5,
            duration=30.0,
            filter_script="filters.txt",
        )
        args.update(kw)
        return build_ffmpeg_command(**args)

    def test_seek_before_input_and_duration(self):
        cmd = self.base()
        assert cmd.index("-ss") < cmd.index("-i")
        assert cmd[cmd.index("-ss") + 1] == "12.500"
        assert cmd[cmd.index("-t") + 1] == "30.000"

    def test_codecs_and_faststart(self):
        cmd = self.base()
        assert cmd[cmd.index("-c:v") + 1] == "libx264"
        assert cmd[cmd.index("-c:a") + 1] == "aac"
        assert "+faststart" in cmd
        assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"

    def test_filter_script_used(self):
        cmd = self.base()
        assert cmd[cmd.index("-filter_script:v") + 1] == "filters.txt"

    def test_output_last_and_overwrite(self):
        cmd = self.base()
        assert cmd[-1] == "out.mp4"
        assert "-y" in cmd


def test_build_frame_command_absolute_timestamps():
    from clipmaker.render import build_frame_command

    cmd = build_frame_command("ffmpeg", "in.mp4", "out.png", 12.5, "scale=10:10")
    assert cmd[cmd.index("-ss") + 1] == "12.500"
    vf = cmd[cmd.index("-vf") + 1]
    assert vf.startswith("setpts=PTS+12.5/TB,") and vf.endswith("scale=10:10")
    assert "-frames:v" in cmd and cmd[-1] == "out.png"


class TestZoomFilters:
    def test_zoom_filter_scales_per_frame_then_recrops(self):
        from clipmaker.render import zoom_filter

        f = zoom_filter(1080, 1920, "1+0.1*t")
        assert "eval=frame" in f
        assert "w='trunc(1080*(1+0.1*t)/2)*2'" in f and "h='trunc(1920*(1+0.1*t)/2)*2'" in f
        assert f.endswith("crop=1080:1920:'(iw-ow)/2':'(ih-oh)*0.4'")

    def test_vertical_filter_with_zoom_appends_zoom_after_crop_scale(self):
        f = vertical_filter(606, 1080, "120", 1080, 1920, zoom_expr="1.05")
        assert f.index("crop=w=606") < f.index("eval=frame")
        assert "setsar=1" in f

    def test_vertical_filter_without_zoom_unchanged(self):
        assert "eval=frame" not in vertical_filter(606, 1080, "120", 1080, 1920)

    def test_fit_filter_for_native_aspect(self):
        from clipmaker.render import fit_filter

        assert "scale=1920:1080" in fit_filter(1920, 1080, 1920, 1080)
        assert "eval=frame" in fit_filter(1920, 1080, 1920, 1080, zoom_expr="1.05")

    def test_build_command_without_subtitles_filter_still_valid(self):
        from clipmaker.render import subtitle_filter

        assert subtitle_filter("/a.ass", None) == "ass=filename='/a.ass'"
