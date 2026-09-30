"""Transcription with mlx-whisper (cached) and transcript.json helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .selection import Segment
from .subtitles import Word

DEFAULT_WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"


def whisper_language(language: str) -> str | None:
    """``auto`` -> None (let whisper detect), otherwise the lower-cased code."""
    lang = language.strip().lower()
    return None if lang in ("", "auto") else lang


def transcript_cache_name(time_range: tuple[float, float] | None, language: str) -> str:
    """Cache file name, distinct per language and time range (full/auto keeps ``transcript.json``)."""
    parts = ["transcript"]
    lang = whisper_language(language)
    if lang:
        parts.append(lang)
    if time_range:
        parts.append(f"r{time_range[0]:g}-{time_range[1]:g}")
    return ".".join(parts) + ".json"


def offset_transcript(data: dict, offset: float) -> dict:
    """Return a copy of a transcript with every timestamp shifted by ``offset`` seconds."""
    if not offset:
        return data
    out = {**data, "segments": []}
    for seg in data["segments"]:
        new = {**seg, "start": seg["start"] + offset, "end": seg["end"] + offset}
        if "words" in seg:
            new["words"] = [{**w, "start": w["start"] + offset, "end": w["end"] + offset} for w in seg["words"]]
        out["segments"].append(new)
    return out


def local_cut_range(time_range: tuple[float, float], source_offset: float) -> tuple[float, float]:
    """A source-time range expressed in the local time of a file that starts at ``source_offset``."""
    return max(0.0, time_range[0] - source_offset), max(0.0, time_range[1] - source_offset)


def audio_cut_command(ffmpeg: str, source: str, output: str, start: float, end: float) -> list[str]:
    """ffmpeg command extracting [start, end] as 16 kHz mono wav (the format whisper wants)."""
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-ss", f"{start:.3f}", "-i", source, "-t", f"{end - start:.3f}",
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", output,
    ]  # fmt: skip


def _run_whisper(audio: str, model: str, language: str) -> dict:
    import mlx_whisper

    lang = whisper_language(language)
    print(f"[transcribe] running {model} (language={lang or 'auto'}) ...")
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=model,
        language=lang,
        word_timestamps=True,
        condition_on_previous_text=False,
        verbose=None,
    )
    return {
        "language": result.get("language", lang or "und"),
        "model": model,
        "text": result.get("text", ""),
        "segments": [
            {
                "id": s.get("id"),
                "start": float(s["start"]),
                "end": float(s["end"]),
                "text": s["text"],
                "words": [
                    {"word": w["word"], "start": float(w["start"]), "end": float(w["end"]),
                     "probability": float(w.get("probability", 1.0))}
                    for w in s.get("words", [])
                ],
            }
            for s in result["segments"]
        ],
    }  # fmt: skip


def transcribe_video(
    source: Path,
    out_json: Path,
    model: str = DEFAULT_WHISPER_MODEL,
    language: str = "auto",
    time_range: tuple[float, float] | None = None,
    source_offset: float = 0.0,
) -> dict:
    """Transcribe (cached). With ``time_range`` only that portion is cut and transcribed,
    and timestamps are re-offset so they stay in source time. ``source_offset`` is the source
    time of the first frame of ``source`` (non-zero for downloaded VOD sections)."""
    if out_json.exists():
        print(f"[transcribe] cached: {out_json}")
        return json.loads(out_json.read_text(encoding="utf-8"))
    if time_range is None:
        legacy = out_json.parent / "transcript.json"
        if legacy != out_json and legacy.exists():
            cached = json.loads(legacy.read_text(encoding="utf-8"))
            if cached.get("language") == whisper_language(language):
                print(f"[transcribe] cached: {legacy}")
                return cached
    if time_range is None:
        data = _run_whisper(str(source), model, language)
    else:
        from .render import find_ffmpeg

        wav = out_json.with_suffix(".wav")
        cut = local_cut_range(time_range, source_offset)
        subprocess.run(audio_cut_command(find_ffmpeg(), str(source), str(wav), *cut), check=True)
        try:
            data = offset_transcript(_run_whisper(str(wav), model, language), cut[0] + source_offset)
        finally:
            wav.unlink(missing_ok=True)
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def segments_and_words(data: dict) -> tuple[list[Segment], list[Word]]:
    segments = [Segment(s["start"], s["end"], s["text"]) for s in data["segments"]]
    words = [
        Word(w["word"].strip(), w["start"], w["end"])
        for s in data["segments"]
        for w in s.get("words", [])
        if w["word"].strip()
    ]
    return segments, words
