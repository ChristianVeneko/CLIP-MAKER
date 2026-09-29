import numpy as np

from clipmaker.cropping import interpolate
from clipmaker.detection import mouth_roi
from clipmaker.framing import plan_framing
from clipmaker.speaker import FaceObs


def patch(seed):
    return np.random.default_rng(seed).integers(0, 255, (20, 24)).astype(np.float32)


STILL = patch(99)


def f(cx, p):
    return FaceObs(cx, 300.0, 200.0, 240.0, p)


def split_screen_samples(n, talker_of):
    """Left face at x=480, right at x=1440; the talker's mouth patch changes every sample."""
    out = []
    for i in range(n):
        left = patch(i) if talker_of(i) == "L" else STILL
        right = patch(1000 + i) if talker_of(i) == "R" else STILL
        out.append([f(480, left), f(1440, right)])
    return out


def test_mouth_roi_centered_on_mouth_and_scaled_by_width():
    x0, y0, x1, y1 = mouth_roi((90, 120), (110, 120))
    assert (x0 + x1) / 2 == 100 and x1 - x0 > 20
    assert y0 < 120 < y1
    small = mouth_roi((95, 120), (105, 120))
    assert (small[2] - small[0]) < (x1 - x0)


def test_speaker_switch_produces_hard_cut_at_the_switch():
    fps = 6.0
    n = 60  # 10 s: left talks 0-5 s, right talks 5-10 s
    samples = split_screen_samples(n, lambda i: "L" if i < 30 else "R")
    times = [i / fps for i in range(n)]
    kps, info = plan_framing(times, samples, src_w=1920, crop_w=606, duration=10.0, sample_fps=fps)
    assert info["speaker_switches"] == 1 and info["backend"] == "speaker"
    left_x, right_x = 480 - 303, 1440 - 303
    assert abs(interpolate(kps, 2.0) - left_x) < 25
    assert abs(interpolate(kps, 9.0) - right_x) < 25
    # no slow pan: within 0.5 s around the switch the window has fully jumped
    assert abs(interpolate(kps, 5.0 - 0.7) - left_x) < 25
    assert abs(interpolate(kps, 5.0 + 1.5) - right_x) < 25
    jump_time = next(t for (t, x) in kps if x > (left_x + right_x) / 2)
    assert 4.9 <= jump_time <= 7.0


def test_no_faces_centres_the_crop():
    times = [i / 6 for i in range(12)]
    kps, info = plan_framing(times, [[] for _ in times], src_w=1920, crop_w=606, duration=2.0, sample_fps=6.0)
    assert info["backend"] == "center"
    assert all(abs(x - (1920 - 606) / 2) < 1 for _, x in kps)


def test_single_face_is_followed():
    times = [i / 6 for i in range(30)]
    samples = [[f(600 + i * 10, patch(i))] for i in range(30)]
    kps, info = plan_framing(times, samples, src_w=1920, crop_w=606, duration=5.0, sample_fps=6.0)
    assert info["speaker_switches"] == 0
    assert interpolate(kps, 4.5) > interpolate(kps, 0.5)


def test_silent_split_screen_falls_back_to_largest_face():
    n = 30
    samples = []
    for i in range(n):
        big = FaceObs(1440, 300, 260, 300, STILL)
        small = FaceObs(480, 300, 120, 140, STILL)
        samples.append([small, big])
    times = [i / 6 for i in range(n)]
    kps, _ = plan_framing(times, samples, src_w=1920, crop_w=606, duration=5.0, sample_fps=6.0)
    assert abs(interpolate(kps, 2.0) - (1440 - 303)) < 25
