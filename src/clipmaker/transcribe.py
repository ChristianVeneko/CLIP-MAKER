"""Transcription with mlx-whisper (cached) and transcript.json helpers."""

from __future__ import annotations

import json
from pathlib import Path

from .selection import Segment
from .subtitles import Word

DEFAULT_WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"


def transcribe_video(source: Path, out_json: Path, model: str = DEFAULT_WHISPER_MODEL) -> dict:
    if out_json.exists():
        print(f"[transcribe] cached: {out_json}")
        return json.loads(out_json.read_text(encoding="utf-8"))
    import mlx_whisper

    print(f"[transcribe] running {model} (language=es) ...")
    result = mlx_whisper.transcribe(
        str(source),
        path_or_hf_repo=model,
        language="es",
        word_timestamps=True,
        condition_on_previous_text=False,
        verbose=None,
    )
    data = {
        "language": result.get("language", "es"),
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
