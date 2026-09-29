"""Job options shared by the CLI and (later) the web app. Pure, no I/O."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Verified against the OpenAI docs (models page / latest-model guide, 2026-09):
# gpt-5.6-sol = frontier tier (the bare `gpt-5.6` alias points to it),
# gpt-5.6-terra = balance of quality and cost, gpt-5.6-luna = cheapest, high-volume tier.
MODEL_DEFAULTS = {"powerful": "gpt-5.6-sol", "light": "gpt-5.6-terra"}
MODEL_ENV = {"powerful": "OPENAI_MODEL_POWERFUL", "light": "OPENAI_MODEL_LIGHT"}

ModelTier = Literal["powerful", "light"]
Genre = Literal[
    "podcast", "interview", "educational", "comedy", "motivational",
    "gaming", "sports", "news", "vlog", "other",
]  # fmt: skip
ClipLength = Literal["auto", "<30s", "30-60s", "60-90s", "90s-3m"]
AspectRatio = Literal["9:16", "1:1", "4:5", "16:9"]

GENRES: tuple[str, ...] = Genre.__args__  # type: ignore[attr-defined]
CLIP_LENGTHS: tuple[str, ...] = ClipLength.__args__  # type: ignore[attr-defined]
ASPECT_RATIOS: tuple[str, ...] = AspectRatio.__args__  # type: ignore[attr-defined]

# (min, max) seconds used in the prompt and by the post-processing clamps.
CLIP_LENGTH_RANGES: dict[str, tuple[float, float]] = {
    "auto": (15.0, 90.0),
    "<30s": (10.0, 30.0),
    "30-60s": (30.0, 60.0),
    "60-90s": (60.0, 90.0),
    "90s-3m": (90.0, 180.0),
}
ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
    "16:9": (1920, 1080),
}


def resolve_model_id(tier: str, environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    override = (env.get(MODEL_ENV[tier]) or "").strip()
    return override or MODEL_DEFAULTS[tier]


class JobOptions(BaseModel):
    selector_model_tier: ModelTier = "powerful"
    selector_model: str | None = None  # explicit model id, wins over the tier
    genre: Genre = "podcast"
    clip_length: ClipLength = "auto"
    max_clips: int = Field(default=5, ge=1, le=20)
    auto_zoom: bool = False
    specific_moments: str = ""
    time_range: tuple[float, float] | None = None
    aspect_ratio: AspectRatio = "9:16"
    language: str = "auto"
    srt_path: str | None = None
    caption_style: str = "mozi"

    @field_validator("caption_style")
    @classmethod
    def _check_style(cls, v: str) -> str:
        from .captions import resolve_style_id

        return resolve_style_id(v)

    @field_validator("time_range")
    @classmethod
    def _check_range(cls, v):
        if v is not None:
            if v[0] < 0 or v[1] <= v[0]:
                raise ValueError("time_range must satisfy 0 <= start < end")
        return v

    @model_validator(mode="after")
    def _normalize(self):
        self.language = self.language.strip().lower() or "auto"
        return self

    @property
    def duration_range(self) -> tuple[float, float]:
        return CLIP_LENGTH_RANGES[self.clip_length]

    @property
    def output_size(self) -> tuple[int, int]:
        return ASPECT_SIZES[self.aspect_ratio]

    def resolved_model(self, environ: Mapping[str, str] | None = None) -> str:
        return self.selector_model or resolve_model_id(self.selector_model_tier, environ)
