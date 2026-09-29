"""Multi-face tracking and active-speaker selection (pure logic; detection lives elsewhere)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class FaceObs:
    """One detected face in one sample. Coordinates are source pixels."""

    cx: float
    cy: float
    w: float
    h: float
    patch: np.ndarray | None = field(default=None, compare=False, repr=False)  # mouth-region gray patch
    score: float = 1.0

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass
class Track:
    id: int
    obs: dict[int, FaceObs] = field(default_factory=dict)  # sample index -> observation

    @property
    def last_index(self) -> int:
        return max(self.obs)


def filter_faces(faces: list[FaceObs], min_rel: float = 0.5, min_score: float = 0.0) -> list[FaceObs]:
    """Drop likely false positives: low score, or much smaller than the largest face in the frame
    (posters, logos and background photos produce small "faces")."""
    faces = [f for f in faces if f.score >= min_score]
    if not faces:
        return []
    biggest = max(f.w for f in faces)
    return [f for f in faces if f.w >= min_rel * biggest]


def prune_tracks(tracks: list[Track], min_obs: int = 3) -> list[Track]:
    """Remove short-lived tracks (flicker); if that would remove everything, keep all."""
    kept = [t for t in tracks if len(t.obs) >= min_obs]
    return kept or tracks


def build_tracks(
    samples: list[list[FaceObs]], max_gap: int = 4, max_dist: float = 1.2
) -> list[Track]:
    """Associate per-sample detections into tracks (greedy nearest neighbour).

    ``max_dist`` is in units of face width; a track may go unseen for ``max_gap`` samples.
    """
    tracks: list[Track] = []
    for i, dets in enumerate(samples):
        pairs = []
        for t in tracks:
            if i - t.last_index > max_gap:
                continue
            last = t.obs[t.last_index]
            for j, d in enumerate(dets):
                dist = math.hypot(d.cx - last.cx, d.cy - last.cy) / max(last.w, d.w, 1e-6)
                if dist <= max_dist:
                    pairs.append((dist, t.id, j))
        used_t: set[int] = set()
        used_d: set[int] = set()
        by_id = {t.id: t for t in tracks}
        for _, tid, j in sorted(pairs):
            if tid in used_t or j in used_d:
                continue
            by_id[tid].obs[i] = dets[j]
            used_t.add(tid)
            used_d.add(j)
        for j, d in enumerate(dets):
            if j not in used_d:
                tracks.append(Track(id=len(tracks), obs={i: d}))
    return tracks


def mouth_diff(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    """Mean absolute difference between two mouth patches (0..1), invariant to global brightness."""
    if a is None or b is None or a.shape != b.shape:
        return None
    a = a.astype(np.float32) - float(a.mean())
    b = b.astype(np.float32) - float(b.mean())
    return float(np.abs(a - b).mean() / 255.0)


def track_energies(tracks: list[Track], n_samples: int) -> dict[int, list[float | None]]:
    """Mouth-movement energy per track and sample (None when it cannot be measured)."""
    out: dict[int, list[float | None]] = {}
    for t in tracks:
        row: list[float | None] = [None] * n_samples
        for i in range(1, n_samples):
            if i in t.obs and i - 1 in t.obs:
                row[i] = mouth_diff(t.obs[i - 1].patch, t.obs[i].patch)
        out[t.id] = row
    return out


def smooth_energy(values: list[float | None], window: int) -> list[float | None]:
    """Centered moving average over the measurable values; unmeasured samples stay None."""
    half = max(0, window // 2)
    out: list[float | None] = []
    for i, v in enumerate(values):
        if v is None:
            out.append(None)
            continue
        seg = [x for x in values[max(0, i - half) : i + half + 1] if x is not None]
        out.append(sum(seg) / len(seg))
    return out


def choose_speakers(
    present: list[set[int]],
    energy: dict[int, list[float | None]],
    dt: float,
    min_hold: float = 1.5,
    margin: float = 1.3,
    min_energy: float = 0.01,
    areas: dict[int, list[float]] | None = None,
) -> list[int | None]:
    """Pick the active speaker (a track id) per sample with hysteresis.

    A switch needs the challenger to beat the current speaker by ``margin`` and the current
    speaker to have been held for ``min_hold`` seconds. If the current track disappears the
    switch is immediate. With no measurable movement the largest face wins.
    """

    def e(tid: int, i: int) -> float:
        v = energy.get(tid, [])[i] if i < len(energy.get(tid, [])) else None
        return v or 0.0

    def best(ids: set[int], i: int) -> int:
        top = max(ids, key=lambda t: (e(t, i), -t))
        if e(top, i) >= min_energy:
            return top
        if areas:
            return max(ids, key=lambda t: (areas.get(t, [0.0] * (i + 1))[i], -t))
        return min(ids)

    out: list[int | None] = []
    current: int | None = None
    last_switch = 0
    for i, ids in enumerate(present):
        if not ids:
            out.append(None)
            continue
        if current is None or current not in ids:
            current = best(ids, i)
            last_switch = i
        else:
            cand = max(ids, key=lambda t: (e(t, i), -t))
            if (
                cand != current
                and e(cand, i) >= min_energy
                and e(cand, i) > margin * e(current, i)
                and (i - last_switch) * dt >= min_hold
            ):
                current = cand
                last_switch = i
        out.append(current)
    return out


def _position(track: Track, i: int) -> float:
    if i in track.obs:
        return track.obs[i].cx
    before = [k for k in track.obs if k < i]
    after = [k for k in track.obs if k > i]
    if before and after:
        a, b = max(before), min(after)
        return track.obs[a].cx + (track.obs[b].cx - track.obs[a].cx) * (i - a) / (b - a)
    return track.obs[max(before) if before else min(after)].cx


def crop_centers(
    tracks: list[Track],
    speakers: list[int | None],
    default_x: float,
    crop_w: float,
    cut_threshold: float = 0.2,
    group_fill: float = 0.85,
) -> tuple[list[float], list[bool]]:
    """Crop-window centre per sample plus a flag marking hard cuts (speaker switches).

    If every visible face fits inside the crop window the group is framed together instead.
    """
    by_id = {t.id: t for t in tracks}
    xs: list[float] = []
    cuts: list[bool] = []
    prev_speaker: int | None = None
    for i, s in enumerate(speakers):
        visible = [t for t in tracks if i in t.obs]
        if len(visible) >= 2:
            left = min(t.obs[i].cx - t.obs[i].w / 2 for t in visible)
            right = max(t.obs[i].cx + t.obs[i].w / 2 for t in visible)
            if right - left <= group_fill * crop_w:
                x = sum(t.obs[i].cx for t in visible) / len(visible)
                cuts.append(False)
                xs.append(x)
                prev_speaker = s
                continue
        x = default_x if s is None else _position(by_id[s], i)
        xs.append(x)
        cuts.append(bool(i > 0 and s != prev_speaker and abs(x - xs[i - 1]) > cut_threshold * crop_w))
        prev_speaker = s
    return xs, cuts
