"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .download import download_video
from .pipeline import render_clips, select_clips
from .render import HORIZONTAL, VERTICAL  # noqa: F401
from .subtitles import STYLE_PRESETS
from .transcribe import DEFAULT_WHISPER_MODEL, segments_and_words, transcribe_video


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--workdir", type=Path, default=Path("workdir"), help="cache directory (default: ./workdir)")
    p.add_argument("--output", type=Path, default=Path("output"), help="output directory (default: ./output)")


def _selection_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--clips-file", type=Path, help="JSON file with manual clips; skips OpenAI")
    p.add_argument("--max-clips", type=int, default=5, help="maximum number of clips (default: 5)")
    p.add_argument("--min-duration", type=float, default=20.0, help="minimum clip length in seconds")
    p.add_argument("--max-duration", type=float, default=60.0, help="maximum clip length in seconds")
    p.add_argument("--model", help="OpenAI model (default: $OPENAI_MODEL or gpt-5)")


def _render_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument("--format", choices=["vertical", "horizontal"], default="vertical",
                   help="vertical = 1080x1920 (9:16), horizontal = 1920x1080 (16:9)")  # fmt: skip
    p.add_argument("--style", choices=sorted(STYLE_PRESETS), default="bold-yellow", help="subtitle style preset")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipmaker",
        description="Turn a long YouTube video into short clips with burned-in animated subtitles.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="download, transcribe, select and render")
    run.add_argument("url")
    run.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(run), _selection_opts(run), _render_opts(run)  # noqa: B018

    dl = sub.add_parser("download", help="download the video only")
    dl.add_argument("url")
    _common(dl)

    tr = sub.add_parser("transcribe", help="download (cached) and transcribe only")
    tr.add_argument("url")
    tr.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(tr)

    se = sub.add_parser("select", help="download, transcribe and select clips (writes clips.json)")
    se.add_argument("url")
    se.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL)
    _common(se), _selection_opts(se)  # noqa: B018

    rd = sub.add_parser("render", help="render clips from an existing workdir using a clips file")
    rd.add_argument("video_id")
    rd.add_argument("--clips-file", type=Path, help="default: <workdir>/<id>/clips.json")
    _common(rd), _render_opts(rd)  # noqa: B018
    return parser


def _prepare(args) -> tuple[str, Path, dict]:
    video_id, source = download_video(args.url, args.workdir)
    data = transcribe_video(source, args.workdir / video_id / "transcript.json", args.whisper_model)
    return video_id, source, data


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "download":
            download_video(args.url, args.workdir)
        elif args.command == "transcribe":
            _prepare(args)
        elif args.command in ("select", "run"):
            video_id, source, data = _prepare(args)
            segments, words = segments_and_words(data)
            clips = select_clips(
                segments, words, args.workdir / video_id / "clips.json", args.clips_file,
                args.max_clips, args.min_duration, args.max_duration, args.model,
            )  # fmt: skip
            if args.command == "run":
                outs = render_clips(source, clips, words, args.output / video_id, args.format, args.style)
                print("\n".join(f"[done] {o}" for o in outs))
        elif args.command == "render":
            video_dir = args.workdir / args.video_id
            data = transcribe_video(video_dir / "source.mp4", video_dir / "transcript.json")
            segments, words = segments_and_words(data)
            clips = select_clips(
                segments, words, video_dir / "clips.json", args.clips_file or video_dir / "clips.json",
                999, 1.0, 3600.0, None,
            )  # fmt: skip
            outs = render_clips(video_dir / "source.mp4", clips, words, args.output / args.video_id, args.format, args.style)
            print("\n".join(f"[done] {o}" for o in outs))
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
