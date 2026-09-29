import pytest

from clipmaker.cli import build_parser, options_from_args


def parse(*argv):
    return build_parser().parse_args(["run", "https://youtu.be/x", *argv])


def test_defaults_map_to_default_options():
    o = options_from_args(parse())
    assert o.aspect_ratio == "9:16" and o.caption_style == "mozi" and o.max_clips == 5
    assert o.selector_model_tier == "powerful" and o.time_range is None


def test_all_flags():
    args = parse(
        "--model-tier", "light", "--genre", "comedy", "--clip-length", "30-60s", "--max-clips", "3",
        "--auto-zoom", "--moments", "chiste 10:30-11:15", "--time-range", "5:00-20:00",
        "--aspect-ratio", "1:1", "--language", "en", "--srt", "subs.srt", "--caption-style", "beasty",
    )  # fmt: skip
    o = options_from_args(args)
    assert (o.selector_model_tier, o.genre, o.clip_length, o.max_clips) == ("light", "comedy", "30-60s", 3)
    assert o.auto_zoom and o.specific_moments == "chiste 10:30-11:15"
    assert o.time_range == (300.0, 1200.0) and o.aspect_ratio == "1:1"
    assert o.language == "en" and o.srt_path == "subs.srt" and o.caption_style == "beasty"


def test_legacy_style_aliases_accepted():
    assert options_from_args(parse("--caption-style", "bold-yellow")).caption_style == "mozi"


def test_bad_time_range_is_reported_as_value_error():
    with pytest.raises(ValueError):
        options_from_args(parse("--time-range", "20:00-10:00"))


def test_invalid_choice_rejected_by_argparse():
    with pytest.raises(SystemExit):
        parse("--aspect-ratio", "2:1")


def test_render_and_select_share_options():
    p = build_parser()
    a = p.parse_args(["render", "vid", "--aspect-ratio", "4:5", "--auto-zoom"])
    o = options_from_args(a)
    assert o.aspect_ratio == "4:5" and o.auto_zoom


def test_preview_styles_subcommand():
    a = build_parser().parse_args(["preview-styles", "vid", "--at", "380"])
    assert a.command == "preview-styles" and a.at == 380.0


def test_serve_command_parses_defaults():
    from clipmaker.cli import build_parser

    args = build_parser().parse_args(["serve"])
    assert (args.command, args.host, args.port) == ("serve", "127.0.0.1", 8000)
    args = build_parser().parse_args(["serve", "--port", "9000", "--workdir", "w"])
    assert args.port == 9000 and str(args.workdir) == "w"
