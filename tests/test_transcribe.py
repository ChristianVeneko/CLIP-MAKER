import json

import pytest

from clipmaker.transcribe import (
    audio_cut_command,
    offset_transcript,
    transcript_cache_name,
    whisper_language,
)

DATA = {
    "language": "es",
    "segments": [
        {"id": 0, "start": 0.5, "end": 2.0, "text": " hola",
         "words": [{"word": " hola", "start": 0.5, "end": 2.0, "probability": 0.9}]},
    ],
}  # fmt: skip


def test_offset_transcript_shifts_segments_and_words_without_mutating():
    out = offset_transcript(DATA, 600.0)
    seg = out["segments"][0]
    assert seg["start"] == 600.5 and seg["end"] == 602.0
    assert seg["words"][0]["start"] == 600.5 and seg["words"][0]["end"] == 602.0
    assert DATA["segments"][0]["start"] == 0.5  # untouched
    assert out["segments"][0]["text"] == " hola"


def test_offset_zero_is_identity():
    assert offset_transcript(DATA, 0) == DATA


def test_cache_names_are_distinct_per_range_and_language():
    assert transcript_cache_name(None, "auto") == "transcript.json"
    assert transcript_cache_name(None, "en") == "transcript.en.json"
    a = transcript_cache_name((600, 1200), "auto")
    b = transcript_cache_name((600, 1300), "auto")
    assert a != b and a.startswith("transcript.") and a.endswith(".json")
    assert transcript_cache_name((600.0, 1200.0), "auto") == transcript_cache_name((600, 1200), "auto")
    assert transcript_cache_name((600, 1200), "en") != a


def test_whisper_language():
    assert whisper_language("auto") is None
    assert whisper_language(" ES ") == "es"


def test_audio_cut_command():
    cmd = audio_cut_command("ffmpeg", "in.mp4", "out.wav", 600.0, 1200.0)
    assert cmd[cmd.index("-ss") + 1] == "600.000"
    assert cmd[cmd.index("-t") + 1] == "600.000"
    assert "-vn" in cmd and cmd[cmd.index("-ar") + 1] == "16000" and cmd[-1] == "out.wav"
    # -ss before -i (fast seek)
    assert cmd.index("-ss") < cmd.index("-i")


def test_local_cut_range_for_section_files():
    from clipmaker.transcribe import local_cut_range

    assert local_cut_range((600.0, 660.0), 600.0) == (0.0, 60.0)
    assert local_cut_range((600.0, 660.0), 0.0) == (600.0, 660.0)
    assert local_cut_range((590.0, 660.0), 600.0) == (0.0, 60.0)
