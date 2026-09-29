import pytest
from pydantic import ValidationError

from clipmaker.options import (
    ASPECT_SIZES,
    CLIP_LENGTH_RANGES,
    JobOptions,
    resolve_model_id,
)


def test_defaults():
    o = JobOptions()
    assert o.selector_model_tier == "powerful"
    assert o.genre == "podcast"
    assert o.clip_length == "auto"
    assert o.max_clips == 5
    assert o.aspect_ratio == "9:16"
    assert o.language == "auto"
    assert o.caption_style == "mozi"
    assert not o.auto_zoom and o.time_range is None and o.srt_path is None


@pytest.mark.parametrize("n", [0, 21, -1])
def test_max_clips_bounds(n):
    with pytest.raises(ValidationError):
        JobOptions(max_clips=n)


def test_invalid_choices_rejected():
    for kw in ({"genre": "cooking"}, {"clip_length": "5m"}, {"aspect_ratio": "3:2"}, {"selector_model_tier": "x"}):
        with pytest.raises(ValidationError):
            JobOptions(**kw)


def test_time_range_must_be_ordered():
    assert JobOptions(time_range=(10, 20)).time_range == (10, 20)
    with pytest.raises(ValidationError):
        JobOptions(time_range=(20, 10))
    with pytest.raises(ValidationError):
        JobOptions(time_range=(-1, 10))


def test_caption_style_aliases_and_unknown():
    assert JobOptions(caption_style="bold-yellow").caption_style == "mozi"
    assert JobOptions(caption_style="clean-white").caption_style == "youshaei"
    assert JobOptions(caption_style="none").caption_style == "none"
    with pytest.raises(ValidationError):
        JobOptions(caption_style="comic-sans")


def test_duration_range_from_clip_length():
    assert JobOptions(clip_length="30-60s").duration_range == (30, 60)
    assert JobOptions(clip_length="<30s").duration_range[1] == 30
    assert JobOptions(clip_length="90s-3m").duration_range == (90, 180)
    assert set(CLIP_LENGTH_RANGES) == {"auto", "<30s", "30-60s", "60-90s", "90s-3m"}


def test_output_size():
    assert JobOptions(aspect_ratio="9:16").output_size == (1080, 1920)
    assert JobOptions(aspect_ratio="1:1").output_size == (1080, 1080)
    assert JobOptions(aspect_ratio="4:5").output_size == (1080, 1350)
    assert JobOptions(aspect_ratio="16:9").output_size == (1920, 1080)
    assert ASPECT_SIZES["16:9"] == (1920, 1080)


def test_model_resolution_defaults_and_env():
    assert resolve_model_id("powerful", {}) == "gpt-5.6-sol"
    assert resolve_model_id("light", {}) == "gpt-5.6-terra"
    env = {"OPENAI_MODEL_POWERFUL": "my-big", "OPENAI_MODEL_LIGHT": "my-small"}
    assert resolve_model_id("powerful", env) == "my-big"
    assert resolve_model_id("light", env) == "my-small"
    assert resolve_model_id("light", {"OPENAI_MODEL_LIGHT": "  "}) == "gpt-5.6-terra"


def test_explicit_model_wins():
    o = JobOptions(selector_model="custom-model")
    assert o.resolved_model({}) == "custom-model"
    assert JobOptions().resolved_model({}) == "gpt-5.6-sol"
