"""Request models and the request -> JobOptions mapping."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from ..moments import extract_ranges
from ..options import AspectRatio, ClipLength, Genre, JobOptions, ModelTier


class RequestError(ValueError):
    """A request that cannot be turned into a valid job (readable message)."""


class Source(BaseModel):
    type: Literal["url", "upload"]
    url: str | None = None
    upload_id: str | None = None
    title: str | None = None
    thumbnail: str | None = None
    duration: float | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.type == "url" and not (self.url or "").strip():
            raise ValueError("url is required for a url source")
        if self.type == "upload" and not self.upload_id:
            raise ValueError("upload_id is required for an upload source")
        return self


class CreateJobRequest(BaseModel):
    source: Source
    model_tier: ModelTier = "powerful"
    genre: Genre = "podcast"
    clip_length: ClipLength = "auto"
    max_clips: int = Field(default=5)
    auto_zoom: bool = False
    specific_moments: str = ""
    time_range: tuple[float, float] | None = None
    aspect_ratio: AspectRatio = "9:16"
    language: str = "auto"
    srt_upload_id: str | None = None
    caption_style: str = "mozi"


NO_KEY_MESSAGE = (
    "Automatic clip selection needs OPENAI_API_KEY. Without it, write explicit ranges "
    "such as 10:30-11:15 in the specific moments field."
)


def build_options(
    req: CreateJobRequest,
    has_api_key: bool,
    resolve_srt: Callable[[str], Path | None] | None = None,
) -> JobOptions:
    srt_path: str | None = None
    if req.srt_upload_id:
        found = resolve_srt(req.srt_upload_id) if resolve_srt else None
        if found is None:
            raise RequestError("The uploaded SRT file was not found; upload it again.")
        srt_path = str(found)
    if not has_api_key and not extract_ranges(req.specific_moments)[0]:
        raise RequestError(NO_KEY_MESSAGE)
    try:
        return JobOptions(
            selector_model_tier=req.model_tier, genre=req.genre, clip_length=req.clip_length,
            max_clips=req.max_clips, auto_zoom=req.auto_zoom, specific_moments=req.specific_moments,
            time_range=req.time_range, aspect_ratio=req.aspect_ratio, language=req.language,
            srt_path=srt_path, caption_style=req.caption_style,
        )  # fmt: skip
    except ValidationError as exc:
        msgs = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise RequestError(msgs) from exc
