"""Speaker-aware crop planning: samples of faces -> crop keypoints (pure)."""

from __future__ import annotations

from . import cropping
from .speaker import (
    FaceObs,
    build_tracks,
    choose_speakers,
    crop_centers,
    prune_tracks,
    smooth_energy,
    track_energies,
)

MIN_HOLD = 1.5  # seconds a speaker is held before another may take over
ENERGY_WINDOW_S = 1.0


def plan_framing(
    times: list[float],
    samples: list[list[FaceObs]],
    src_w: int,
    crop_w: int,
    duration: float,
    sample_fps: float,
    step: float = 0.5,
) -> tuple[list[tuple[float, float]], dict]:
    """Return crop-x keypoints (piecewise linear, hard cuts on speaker switches) and diagnostics."""
    n = len(samples)
    tracks = prune_tracks(build_tracks(samples, max_gap=max(2, int(sample_fps))), min_obs=max(3, int(sample_fps / 2)))
    default_x = src_w / 2
    dt = 1.0 / sample_fps
    if not tracks:
        xs, cuts = [default_x] * n, [False] * n
        speakers: list[int | None] = [None] * n
        backend = "center"
    else:
        window = max(3, int(round(ENERGY_WINDOW_S * sample_fps)) | 1)
        energy = {tid: smooth_energy(row, window) for tid, row in track_energies(tracks, n).items()}
        present = [{t.id for t in tracks if i in t.obs} for i in range(n)]
        areas = {t.id: [t.obs[i].area if i in t.obs else 0.0 for i in range(n)] for t in tracks}
        speakers = choose_speakers(present, energy, dt, min_hold=MIN_HOLD, areas=areas)
        xs, cuts = crop_centers(tracks, speakers, default_x, crop_w)
        backend = "speaker"
    xs = cropping.smooth_segments(xs, cuts, deadzone=src_w * 0.03, window=max(3, int(sample_fps) | 1))
    crop_xs = cropping.centers_to_crop_x(xs, src_w, crop_w)
    kps = cropping.build_cut_keypoints(times, crop_xs, cuts, duration, step=step)
    switches = sum(
        1 for i in range(1, n) if speakers[i] is not None and speakers[i - 1] is not None and speakers[i] != speakers[i - 1]
    )
    info = {
        "backend": backend,
        "tracks": len(tracks),
        "speaker_switches": switches,
        "cuts": sum(cuts),
        "speakers": speakers,
    }
    return kps, info
