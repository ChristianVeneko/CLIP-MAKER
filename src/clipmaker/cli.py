"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .captions import ALIASES, PRESETS
from .download import download_video
from .moments import parse_time_range
from .options import ASPECT_RATIOS, CLIP_LENGTHS, GENRES, JobOptions
from .pipeline import prepare_transcript, render_clips, select_clips
from .transcribe import DEFAULT_WHISPER_MODEL, segments_and_words


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--workdir", type=Path, default=Path("workdir"), help="cache directory (default: ./workdir)")
    p.add_argument("--output", type=Path, default=Path("output"), help="output directory (default: ./output)")


def _job_opts(p: argparse.ArgumentParser, render: bool = True, select: bool = True) -> None:
    g = p.add_argument_group("job options")
    g.add_argument("--time-range", metavar="START-END", help="only process this part, e.g. 10:30-25:00")
    g.add_argument("--language", default="auto", help="whisper language code or 'auto' (also the language of titles)")
    g.add_argument("--srt", metavar="FILE", help="use this SRT instead of running whisper")
    if select:
        g.add_argument("--clips-file", type=Path, help="JSON file with manual clips; skips OpenAI")
        g.add_argument("--model-tier", choices=["powerful", "light"], default="powerful",
                       help="OpenAI model tier ($OPENAI_MODEL_POWERFUL / $OPENAI_MODEL_LIGHT override the ids)")  # fmt: skip
        g.add_argument("--model", help="explicit OpenAI model id (overrides --model-tier)")
        g.add_argument("--genre", choices=GENRES, default="podcast", help="content genre used in the selection prompt")
        g.add_argument("--clip-length", choices=CLIP_LENGTHS, default="auto", help="target clip length")
        g.add_argument("--max-clips", type=int, default=5, help="maximum number of clips, 1-20 (default: 5)")
        g.add_argument("--moments", default="", metavar="TEXT",
                       help="specific moments to look for; explicit ranges like 10:30-11:15 are forced as clips")  # fmt: skip
    if render:
        g.add_argument("--aspect-ratio", choices=ASPECT_RATIOS, default="9:16", help="output aspect ratio")
        g.add_argument("--caption-style", choices=sorted([*PRESETS, *ALIASES, "none"]), default="mozi",
                       help="caption preset")  # fmt: skip
        g.add_argument("--auto-zoom", action="store_true", help="subtle eased punch-in on sentence starts")


def options_from_args(args: argparse.Namespace) -> JobOptions:
    """Build validated :class:`JobOptions` from parsed CLI arguments."""
    g = lambda name, default=None: getattr(args, name, default)  # noqa: E731
    kwargs = {
        "selector_model_tier": g("model_tier", "powerful"),
        "selector_model": g("model"),
        "genre": g("genre", "podcast"),
        "clip_length": g("clip_length", "auto"),
        "max_clips": g("max_clips", 5),
        "auto_zoom": bool(g("auto_zoom", False)),
        "specific_moments": g("moments", "") or "",
        "time_range": parse_time_range(g("time_range")) if g("time_range") else None,
        "aspect_ratio": g("aspect_ratio", "9:16"),
        "language": g("language", "auto"),
        "srt_path": g("srt"),
        "caption_style": g("caption_style", "mozi"),
    }
    try:
        return JobOptions(**kwargs)
    except Exception as exc:  # pydantic validation error
        raise ValueError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipmaker",
        description="Turn a long YouTube video into short clips with burned-in animated captions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="download, transcribe, select and render")
    run.add_argument("url")
    run.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(run), _job_opts(run)  # noqa: B018

    dl = sub.add_parser("download", help="download the video only")
    dl.add_argument("url")
    _common(dl)

    tr = sub.add_parser("transcribe", help="download (cached) and transcribe only")
    tr.add_argument("url")
    tr.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(tr), _job_opts(tr, render=False, select=False)  # noqa: B018

    se = sub.add_parser("select", help="download, transcribe and select clips (writes clips.json)")
    se.add_argument("url")
    se.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(se), _job_opts(se, render=False)  # noqa: B018

    rd = sub.add_parser("render", help="render clips from an existing workdir using a clips file")
    rd.add_argument("video_id")
    rd.add_argument("--clips-file", type=Path, help="default: <workdir>/<id>/clips.json")
    rd.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(rd), _job_opts(rd, select=False)  # noqa: B018

    pv = sub.add_parser("preview-styles", help="render a still of every caption preset (PNG)")
    pv.add_argument("video_id")
    pv.add_argument("--at", type=float, default=380.0, help="frame time in seconds")
    pv.add_argument("--aspect-ratio", choices=ASPECT_RATIOS, default="9:16")
    _common(pv)
    return parser


def _prepare(args, options: JobOptions):
    video_id, source = download_video(args.url, args.workdir)
    data = prepare_transcript(source, args.workdir / video_id, options, args.whisper_model)
    return video_id, source, data


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "download":
            download_video(args.url, args.workdir)
        elif args.command == "transcribe":
            _prepare(args, options_from_args(args))
        elif args.command in ("select", "run"):
            options = options_from_args(args)
            video_id, source, data = _prepare(args, options)
            segments, words = segments_and_words(data)
            clips = select_clips(segments, words, args.workdir / video_id / "clips.json", options, args.clips_file)
            if args.command == "run":
                outs = render_clips(source, clips, words, args.output / video_id, options)
                print("\n".join(f"[done] {o}" for o in outs))
        elif args.command == "render":
            options = options_from_args(args)
            video_dir = args.workdir / args.video_id
            data = prepare_transcript(video_dir / "source.mp4", video_dir, options, args.whisper_model)
            segments, words = segments_and_words(data)
            clips_file = args.clips_file or video_dir / "clips.json"
            # a clips file is already final: do not re-clamp lengths to the option range
            from .selection import load_clips_file

            clips = load_clips_file(clips_file)
            outs = render_clips(video_dir / "source.mp4", clips, words, args.output / args.video_id, options)
            print("\n".join(f"[done] {o}" for o in outs))
        elif args.command == "preview-styles":
            from .detection import face_center_at, probe_video
            from .options import ASPECT_SIZES
            from .previews import render_style_previews

            source = args.workdir / args.video_id / "source.mp4"
            src_w, src_h, _, _ = probe_video(source)
            paths = render_style_previews(
                source, args.output / "style_previews", args.at, src_w, src_h,
                face_center_at(source, args.at) or src_w / 2, ASPECT_SIZES[args.aspect_ratio],
            )
            print("\n".join(f"[done] {p}" for p in paths))
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
