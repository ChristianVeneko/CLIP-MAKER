"""Crop math for face-tracked vertical framing (pure)."""

from __future__ import annotations


def crop_width_for(src_h: int, aspect: float = 9 / 16) -> int:
    """Width of a crop window with the given aspect ratio, rounded down to an even number."""
    w = int(src_h * aspect)
    return w - (w % 2)


def fill_missing(values: list[float | None], default: float) -> list[float]:
    """Fill gaps by linear interpolation; hold edge values; use ``default`` if nothing detected."""
    known = [i for i, v in enumerate(values) if v is not None]
    if not known:
        return [default] * len(values)
    out: list[float] = [0.0] * len(values)
    first, last = known[0], known[-1]
    for i in range(len(values)):
        if i <= first:
            out[i] = values[first]
        elif i >= last:
            out[i] = values[last]
        elif values[i] is not None:
            out[i] = values[i]
        else:
            lo = max(k for k in known if k < i)
            hi = min(k for k in known if k > i)
            frac = (i - lo) / (hi - lo)
            out[i] = values[lo] + (values[hi] - values[lo]) * frac
    return out


def moving_average(values: list[float], window: int) -> list[float]:
    if window <= 1 or not values:
        return list(values)
    half = window // 2
    out = []
    for i in range(len(values)):
        seg = values[max(0, i - half) : i + half + 1]
        out.append(sum(seg) / len(seg))
    return out


def apply_deadzone(values: list[float], deadzone: float) -> list[float]:
    """Hold the position until the target leaves the dead zone, then follow its edge."""
    if not values:
        return []
    pos = values[0]
    out = []
    for v in values:
        if v - pos > deadzone:
            pos = v - deadzone
        elif pos - v > deadzone:
            pos = v + deadzone
        out.append(pos)
    return out


def smooth_centers(
    raw: list[float | None],
    default: float,
    window: int = 5,
    deadzone: float = 40.0,
) -> list[float]:
    """Raw per-sample face centers (or None) -> smoothed, jitter-free crop centers."""
    filled = fill_missing(raw, default)
    held = apply_deadzone(filled, deadzone)
    return moving_average(held, window)


def centers_to_crop_x(centers: list[float], src_w: int, crop_w: int) -> list[int]:
    max_x = max(0, src_w - crop_w)
    return [int(round(min(max(c - crop_w / 2, 0), max_x))) for c in centers]


def build_keypoints(
    times: list[float], xs: list[float], duration: float, step: float = 0.5
) -> list[tuple[float, float]]:
    """Resample (time, x) samples to keypoints every ``step`` seconds (nearest sample)."""
    if not times:
        return [(0.0, 0), (duration, 0)]
    n = max(1, int(round(duration / step)))
    points = []
    for k in range(n + 1):
        t = min(k * step, duration)
        idx = min(range(len(times)), key=lambda i: abs(times[i] - t))
        points.append((round(t, 3), xs[idx]))
    if points[-1][0] < duration:
        points.append((round(duration, 3), points[-1][1]))
    return points


def interpolate(keypoints: list[tuple[float, float]], t: float) -> float:
    if t <= keypoints[0][0]:
        return keypoints[0][1]
    for (t0, x0), (t1, x1) in zip(keypoints, keypoints[1:]):
        if t <= t1:
            return x0 + (x1 - x0) * (t - t0) / (t1 - t0)
    return keypoints[-1][1]


def crop_x_expression(keypoints: list[tuple[float, float]]) -> str:
    """ffmpeg expression of ``t`` equal to the piecewise-linear interpolation of keypoints.

    Built as a flat sum of clipped ramps (no nested ``if``), so it stays cheap and
    never hits expression depth limits. Contains no quotes/colons/commas outside ``clip()``.
    """
    base = keypoints[0][1]
    terms = [f"{base:g}"]
    for (t0, x0), (t1, x1) in zip(keypoints, keypoints[1:]):
        delta = x1 - x0
        if delta == 0 or t1 <= t0:
            continue
        sign = "+" if delta > 0 else "-"
        terms.append(f"{sign}{abs(delta):g}*clip((t-{t0:g})/{t1 - t0:g},0,1)")
    return "".join(terms)


def smooth_segments(xs: list[float], cuts: list[bool], deadzone: float, window: int = 5) -> list[float]:
    """Dead-zone + moving-average smoothing applied independently inside each cut-free run."""
    out: list[float] = []
    bounds = [0] + [i for i, c in enumerate(cuts) if c] + [len(xs)]
    for a, b in zip(bounds, bounds[1:]):
        if b > a:
            out.extend(moving_average(apply_deadzone(list(xs[a:b]), deadzone), window))
    return out


def build_cut_keypoints(
    times: list[float],
    xs: list[float],
    cuts: list[bool],
    duration: float,
    step: float = 0.5,
    cut_len: float = 0.001,
) -> list[tuple[float, float]]:
    """Like :func:`build_keypoints`, but a ``True`` in ``cuts`` makes the window jump (hard cut)."""
    if not any(cuts) or not times:
        return build_keypoints(times, xs, duration, step)
    bounds = [0] + [i for i, c in enumerate(cuts) if c] + [len(times)]
    points: list[tuple[float, float]] = []

    def add(t: float, x: float) -> None:
        t = round(t, 4)
        if not points or t > points[-1][0]:
            points.append((t, x))

    for a, b in zip(bounds, bounds[1:]):
        first = a == 0
        last = b == len(times)
        t_start = 0.0 if first else times[a] + cut_len
        t_end = duration if last else times[b]
        seg_t, seg_x = times[a:b], xs[a:b]

        def value(t: float) -> float:
            return seg_x[min(range(len(seg_t)), key=lambda i: abs(seg_t[i] - t))]

        add(t_start, value(t_start))
        k = int(t_start // step) + 1
        while k * step < t_end:
            add(k * step, value(k * step))
            k += 1
        add(t_end, value(t_end))
    return points
