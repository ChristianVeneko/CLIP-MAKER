"""Pure helpers describing job stages and overall progress."""

from __future__ import annotations

STAGE_IDS = ("download", "transcribe", "select", "render")
# Relative weight of each stage in the overall percentage.
WEIGHTS = {"download": 10, "transcribe": 30, "select": 10, "render": 50}


def initial_stages(has_download: bool, has_transcribe: bool) -> list[dict]:
    """Ordered stage list; stages that will not run start as ``skipped``."""
    skipped = {"download": not has_download, "transcribe": not has_transcribe}
    return [{"id": sid, "status": "skipped" if skipped.get(sid) else "pending"} for sid in STAGE_IDS]


def overall_percent(stages: list[dict], stage: str, fraction: float) -> int:
    """Overall percentage (0-100) given the active stage and its own 0..1 fraction."""
    if stage not in WEIGHTS:
        raise ValueError(f"unknown stage '{stage}'")
    fraction = min(1.0, max(0.0, fraction))
    active = [s["id"] for s in stages if s["status"] != "skipped"]
    total = sum(WEIGHTS[s] for s in active)
    if stage not in active or not total:
        return 0
    done = 0.0
    for sid in active:
        if sid == stage:
            done += WEIGHTS[sid] * fraction
            break
        done += WEIGHTS[sid]
    return round(100 * done / total)
