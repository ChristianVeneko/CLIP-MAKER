"""The real job runner: glue between the web job model and the pipeline."""

from __future__ import annotations

from pathlib import Path

from ..download import download_video
from ..options import JobOptions
from ..pipeline import prepare_transcript, render_clips, select_clips
from ..transcribe import DEFAULT_WHISPER_MODEL, segments_and_words
from .media import make_thumbnail


def find_upload_video(upload_dir: Path) -> Path | None:
    return next(iter(sorted(upload_dir.glob("source.*"))), None)


def run_job(job: dict, report, job_dir: Path, workdir: Path, thumbnail=make_thumbnail) -> list[dict]:
    options = JobOptions(**job["options"])
    source = job["source"]
    if source["type"] == "url":
        report("download", 0.0, "Downloading video")
        video_id, video = download_video(source["url"], workdir)
        video_dir = workdir / video_id
    else:
        video_dir = workdir / "uploads" / source["upload_id"]
        video = find_upload_video(video_dir)
        if video is None:
            raise RuntimeError("The uploaded video is no longer available; upload it again.")
    report("download", 1.0, "Video ready")

    report("transcribe", 0.0, "Loading the SRT" if options.srt_path else "Transcribing audio")
    data = prepare_transcript(video, video_dir, options, DEFAULT_WHISPER_MODEL)
    segments, words = segments_and_words(data)
    report("transcribe", 1.0, "Transcript ready")

    report("select", 0.0, "Selecting clips")
    clips = select_clips(segments, words, job_dir / "selection.json", options)
    if not clips:
        raise RuntimeError("No clips were selected for this video and these options.")
    report("select", 1.0, f"{len(clips)} clip(s) selected")

    outputs = render_clips(video, clips, words, job_dir, options, progress=report)
    results = []
    for clip, mp4 in zip(clips, outputs, strict=True):
        jpg = mp4.with_suffix(".jpg")
        duration = clip.end - clip.start
        thumbnail(mp4, jpg, min(1.0, duration / 2))
        results.append(
            {"title": clip.title, "score": clip.score, "hook": clip.hook, "start": clip.start,
             "end": clip.end, "duration": round(duration, 2), "video": mp4.name, "thumbnail": jpg.name}
        )  # fmt: skip
    return results
