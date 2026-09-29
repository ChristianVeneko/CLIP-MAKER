import pytest

from clipmaker.web.schemas import CreateJobRequest, RequestError, build_options


def req(**kw):
    base = {"source": {"type": "url", "url": "https://youtu.be/abc"}}
    base.update(kw)
    return CreateJobRequest(**base)


def test_defaults_map_to_job_options():
    opts = build_options(req(), has_api_key=True)
    assert opts.selector_model_tier == "powerful" and opts.max_clips == 5 and opts.caption_style == "mozi"


def test_full_mapping():
    r = req(
        model_tier="light", genre="comedy", clip_length="30-60s", max_clips=3, auto_zoom=True,
        specific_moments="10:40-11:35, 6:10-6:58", time_range=[60, 900], aspect_ratio="1:1",
        language="ES", caption_style="beasty",
    )
    o = build_options(r, has_api_key=False)
    assert (o.selector_model_tier, o.genre, o.clip_length, o.max_clips, o.auto_zoom) == ("light", "comedy", "30-60s", 3, True)
    assert o.time_range == (60, 900) and o.aspect_ratio == "1:1" and o.language == "es" and o.caption_style == "beasty"


def test_srt_upload_resolves_to_path(tmp_path):
    srt = tmp_path / "s.srt"
    srt.write_text("x")
    o = build_options(req(srt_upload_id="abcabcabcabc"), has_api_key=True, resolve_srt=lambda uid: srt)
    assert o.srt_path == str(srt)


def test_unknown_srt_upload_rejected():
    with pytest.raises(RequestError):
        build_options(req(srt_upload_id="abcabcabcabc"), has_api_key=True, resolve_srt=lambda uid: None)


def test_without_key_requires_explicit_ranges():
    with pytest.raises(RequestError, match="OPENAI_API_KEY"):
        build_options(req(specific_moments="the funny part"), has_api_key=False)
    with pytest.raises(RequestError):
        build_options(req(), has_api_key=False)
    build_options(req(specific_moments="the funny part 1:00-1:30"), has_api_key=False)


def test_invalid_values_rejected():
    with pytest.raises(RequestError):
        build_options(req(caption_style="nope"), has_api_key=True)
    with pytest.raises(RequestError):
        build_options(req(time_range=[10, 5]), has_api_key=True)
    with pytest.raises(RequestError):
        build_options(req(max_clips=99), has_api_key=True)


def test_source_requires_url_or_upload():
    with pytest.raises(Exception):
        CreateJobRequest(source={"type": "url"})
    with pytest.raises(Exception):
        CreateJobRequest(source={"type": "upload"})
