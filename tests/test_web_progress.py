import pytest

from clipmaker.web.progress import initial_stages, overall_percent


def test_initial_stages_full():
    assert initial_stages(has_download=True, has_transcribe=True) == [
        {"id": "download", "status": "pending"},
        {"id": "transcribe", "status": "pending"},
        {"id": "select", "status": "pending"},
        {"id": "render", "status": "pending"},
    ]


def test_initial_stages_skips_download_and_transcribe():
    st = initial_stages(has_download=False, has_transcribe=False)
    assert {s["id"]: s["status"] for s in st} == {
        "download": "skipped", "transcribe": "skipped", "select": "pending", "render": "pending",
    }


def test_percent_monotonic_and_bounded():
    st = initial_stages(True, True)
    values = [overall_percent(st, sid, f) for sid in ("download", "transcribe", "select", "render") for f in (0, 0.5, 1)]
    assert values == sorted(values)
    assert values[0] == 0
    assert values[-1] == 100


def test_percent_ignores_skipped_stages():
    st = initial_stages(False, False)
    assert overall_percent(st, "select", 0.0) == 0
    assert overall_percent(st, "render", 1.0) == 100
    assert 0 < overall_percent(st, "render", 0.5) < 100


def test_percent_clamps_fraction():
    st = initial_stages(True, True)
    assert overall_percent(st, "render", 5) == 100
    assert overall_percent(st, "download", -1) == 0


def test_unknown_stage_rejected():
    with pytest.raises(ValueError):
        overall_percent(initial_stages(True, True), "bogus", 0.5)
