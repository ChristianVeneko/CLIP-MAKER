"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .captions import ALIASES, PRESETS
from .detection import probe_video
from .download import download_video, find_source
from .moments import parse_time_range
from .options import ASPECT_RATIOS, CLIP_LENGTHS, GENRES, JobOptions
from .paths import default_output, default_workdir
from .pipeline import prepare_transcript, render_clips, select_clips
from .transcribe import DEFAULT_WHISPER_MODEL, segments_and_words


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--workdir", type=Path, default=default_workdir(), help="cache directory (default: <project>/workdir)")
    p.add_argument("--output", type=Path, default=default_output(), help="output directory (default: <project>/output)")


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
        description="Turn a long YouTube, Twitch or Kick video into short clips with burned-in animated captions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="download, transcribe, select and render")
    run.add_argument("url")
    run.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(run), _job_opts(run)  # noqa: B018

    dl = sub.add_parser("download", help="download the video only")
    dl.add_argument("url")
    dl.add_argument("--time-range", metavar="START-END",
                    help="Twitch/Kick VODs: download only this part, e.g. 1:10:00-1:20:00")  # fmt: skip
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

    sv = sub.add_parser("serve", help="start the local web app")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    _common(sv)
    return parser


def _prepare(args, options: JobOptions):
    video_id, source, offset = download_video(args.url, args.workdir, options.time_range)
    data = prepare_transcript(source, args.workdir / video_id, options, args.whisper_model, offset)
    return video_id, source, offset, data


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "download":
            rng = parse_time_range(args.time_range) if args.time_range else None
            download_video(args.url, args.workdir, rng)
        elif args.command == "transcribe":
            _prepare(args, options_from_args(args))
        elif args.command in ("select", "run"):
            options = options_from_args(args)
            video_id, source, offset, data = _prepare(args, options)
            segments, words = segments_and_words(data)
            clips = select_clips(
                segments, words, args.workdir / video_id / "clips.json", options, args.clips_file,
                source_duration=None if options.time_range else probe_video(source)[3],
            )
            if args.command == "run":
                outs = render_clips(source, clips, words, args.output / video_id, options, source_offset=offset)
                print("\n".join(f"[done] {o}" for o in outs))
        elif args.command == "render":
            options = options_from_args(args)
            video_dir = args.workdir / args.video_id
            found = find_source(video_dir, options.time_range)
            if found is None:
                raise FileNotFoundError(f"no downloaded source in {video_dir}; run `clipmaker download` first")
            source, offset = found
            data = prepare_transcript(source, video_dir, options, args.whisper_model, offset)
            segments, words = segments_and_words(data)
            clips_file = args.clips_file or video_dir / "clips.json"
            # a clips file is already final: do not re-clamp lengths to the option range
            from .selection import load_clips_file

            clips = load_clips_file(clips_file)
            outs = render_clips(source, clips, words, args.output / args.video_id, options, source_offset=offset)
            print("\n".join(f"[done] {o}" for o in outs))
        elif args.command == "serve":
            import uvicorn

            from .web.app import Settings, create_app

            settings = Settings(workdir=args.workdir, output_dir=args.output)
            if settings.web_dist is None:
                print("[serve] web/dist not found: only the API is served (build it with `npm run build` in web/)")
            uvicorn.run(create_app(settings), host=args.host, port=args.port)
        elif args.command == "preview-styles":
            from .detection import face_center_at
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
