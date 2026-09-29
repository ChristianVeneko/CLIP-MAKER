import pytest

from clipmaker.cropping import (
    apply_deadzone,
    build_keypoints,
    centers_to_crop_x,
    crop_width_for,
    crop_x_expression,
    fill_missing,
    interpolate,
    moving_average,
    smooth_centers,
)


def eval_expr(expr, t):
    def clip(x, lo, hi):
        return max(lo, min(hi, x))
    return eval(expr, {"clip": clip, "t": t})


def test_crop_width_even_and_9_16():
    assert crop_width_for(1080, 9 / 16) == 606
    assert crop_width_for(720, 9 / 16) % 2 == 0


class TestFillMissing:
    def test_all_missing_uses_default(self):
        assert fill_missing([None, None], default=500) == [500, 500]

    def test_interpolates_gaps(self):
        assert fill_missing([100, None, None, 400], default=0) == [100, 200, 300, 400]

    def test_holds_edges(self):
        assert fill_missing([None, 100, None], default=0) == [100, 100, 100]


class TestMovingAverage:
    def test_constant(self):
        assert moving_average([5, 5, 5], 3) == [5, 5, 5]

    def test_smooths_spike(self):
        out = moving_average([0, 0, 90, 0, 0], 3)
        assert max(out) == pytest.approx(30)
        assert len(out) == 5

    def test_window_one_is_identity(self):
        assert moving_average([1, 2, 3], 1) == [1, 2, 3]


class TestDeadzone:
    def test_small_jitter_ignored(self):
        out = apply_deadzone([100, 105, 95, 102], deadzone=20)
        assert out == [100, 100, 100, 100]

    def test_large_move_followed(self):
        out = apply_deadzone([100, 100, 200], deadzone=20)
        assert out[-1] == pytest.approx(180)  # follows the edge of the dead zone

    def test_empty(self):
        assert apply_deadzone([], 10) == []


class TestSmoothCenters:
    def test_no_detection_returns_default(self):
        out = smooth_centers([None] * 6, default=960)
        assert out == [960] * 6

    def test_reduces_jitter(self):
        raw = [500 + (10 if i % 2 else -10) for i in range(20)]
        out = smooth_centers(raw, default=960, window=5, deadzone=30)
        assert max(out) - min(out) < 5

    def test_tracks_real_move(self):
        raw = [300.0] * 15 + [900.0] * 15
        out = smooth_centers(raw, default=960, window=3, deadzone=30)
        assert out[0] == pytest.approx(300, abs=1)
        assert out[-1] == pytest.approx(900, abs=40)


class TestCropX:
    def test_centered_on_face(self):
        assert centers_to_crop_x([960], src_w=1920, crop_w=606) == [657]

    def test_clamped_left_right(self):
        xs = centers_to_crop_x([0, 1920], src_w=1920, crop_w=606)
        assert xs == [0, 1920 - 606]


class TestKeypointsAndExpression:
    def test_keypoint_times(self):
        kps = build_keypoints([0, 0.5, 1.0, 1.5, 2.0], [10, 10, 20, 20, 30], duration=2.0, step=1.0)
        assert [k[0] for k in kps] == [0.0, 1.0, 2.0]
        assert [k[1] for k in kps] == [10, 20, 30]

    def test_interpolate(self):
        kps = [(0.0, 0), (1.0, 100)]
        assert interpolate(kps, 0.5) == 50
        assert interpolate(kps, -1) == 0
        assert interpolate(kps, 5) == 100

    def test_expression_matches_interpolate(self):
        kps = [(0.0, 100), (1.0, 300), (2.0, 300), (3.0, 50)]
        expr = crop_x_expression(kps)
        for t in [0, 0.3, 1.0, 1.7, 2.5, 3.0, 9.0]:
            assert eval_expr(expr, t) == pytest.approx(interpolate(kps, t), abs=0.01)

    def test_constant_is_plain_number(self):
        expr = crop_x_expression([(0.0, 250), (1.0, 250)])
        assert "clip" not in expr
        assert eval_expr(expr, 0.5) == 250

    def test_expression_has_no_shell_or_filter_specials(self):
        expr = crop_x_expression([(0.0, 0), (1.0, 10), (2.0, 5)])
        assert "'" not in expr and ":" not in expr
