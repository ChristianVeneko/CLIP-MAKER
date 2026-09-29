"""Auto-zoom: subtle eased punch-ins on sentence starts / emphasis (pure keyframe maths)."""

from __future__ import annotations

from .subtitles import SENTENCE_END, Word

PEAK = 1.12
EMPHASIS_END = ("!", "?")


def zoom_triggers(words: list[Word], duration: float, min_gap: float = 3.0, pause: float = 0.6) -> list[float]:
    """Times (clip-relative) where a punch-in starts: sentence starts, phrase starts after a
    pause, and emphasised words. Words must already be clip-relative."""
    candidates: list[tuple[float, bool]] = []
    for i, word in enumerate(words):
        text = word.text.strip()
        if not text:
            continue
        prev = words[i - 1] if i else None
        starts_sentence = prev is None or prev.text.strip().endswith(SENTENCE_END)
        after_pause = prev is not None and word.start - prev.end >= pause
        emphatic = text.endswith(EMPHASIS_END)
        if starts_sentence or after_pause or emphatic:
            candidates.append((word.start, emphatic))
    out: list[float] = []
    for t, _ in candidates:
        if t > duration - 1.0:
            continue
        if not out or t - out[-1] >= min_gap:
            out.append(t)
    return out


def zoom_at(keyframes: list[tuple[float, float]], t: float) -> float:
    """Zoom factor at ``t``: smoothstep interpolation between keyframes."""
    if t <= keyframes[0][0]:
        return keyframes[0][1]
    for (t0, z0), (t1, z1) in zip(keyframes, keyframes[1:]):
        if t <= t1:
            p = (t - t0) / (t1 - t0)
            return z0 + (z1 - z0) * (3 * p * p - 2 * p * p * p)
    return keyframes[-1][1]


def zoom_keyframes(
    triggers: list[float],
    duration: float,
    peak: float = PEAK,
    ramp_in: float = 0.3,
    hold: float = 1.4,
    ramp_out: float = 0.9,
) -> list[tuple[float, float]]:
    """Keyframes (t, zoom) with one pulse per trigger; overlapping pulses are truncated smoothly."""
    kf: list[tuple[float, float]] = [(0.0, 1.0)]
    for t in triggers:
        if t <= 0.0:
            t = 0.0
        if t > kf[-1][0]:
            start_z = zoom_at(kf, t)
            kf = [k for k in kf if k[0] < t]
            kf.append((t, start_z))
        else:
            kf = [k for k in kf if k[0] < t] or [(0.0, 1.0)]
            if t == 0.0:
                kf = [(0.0, 1.0)]
            else:
                kf.append((t, zoom_at(kf, t)))
        up = t + ramp_in
        kf += [(up, peak), (up + hold, peak), (up + hold + ramp_out, 1.0)]
    if kf[-1][0] < duration:
        kf.append((duration, kf[-1][1]))
    return kf


def zoom_expression(keyframes: list[tuple[float, float]]) -> str:
    """ffmpeg expression of ``t`` equal to :func:`zoom_at` (sum of smoothstep ramps)."""
    terms = [f"{keyframes[0][1]:g}"]
    for (t0, z0), (t1, z1) in zip(keyframes, keyframes[1:]):
        dz = z1 - z0
        if abs(dz) < 1e-9 or t1 <= t0:
            continue
        sign = "+" if dz > 0 else "-"
        p = f"st(1,clip((t-{t0:.3f})/{t1 - t0:.3f},0,1))"
        terms.append(f"{sign}{abs(dz):.4f}*({p}*ld(1)*(3-2*ld(1)))")
    return "".join(terms)
