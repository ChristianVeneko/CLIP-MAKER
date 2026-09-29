import pytest

from clipmaker.subtitles import SENTENCE_END, Word
from clipmaker.zoom import zoom_at, zoom_expression, zoom_keyframes, zoom_triggers


def w(text, start, end):
    return Word(text, start, end)


def evaluate(expr, t):
    """Evaluate an ffmpeg expression the way ffmpeg would (clip/st/ld)."""
    store = {}

    def clip(x, lo, hi):
        return max(lo, min(hi, x))

    def st(i, v):
        store[i] = v
        return v

    def ld(i):
        return store[i]

    return eval(expr, {"clip": clip, "st": st, "ld": ld, "t": t})


class TestTriggers:
    words = [
        w("Hola", 0.0, 0.4), w("a", 0.4, 0.5), w("todos.", 0.5, 1.0),
        w("Esto", 1.1, 1.4), w("es", 1.4, 1.6), w("increíble!", 1.6, 2.4),
        w("Pero", 6.0, 6.3), w("bueno", 6.3, 6.8),
    ]  # fmt: skip

    def test_sentence_starts_and_emphasis(self):
        trig = zoom_triggers(self.words, duration=10.0, min_gap=1.0)
        assert 0.0 in trig and 1.1 in trig and 6.0 in trig

    def test_min_gap_enforced(self):
        trig = zoom_triggers(self.words, duration=10.0, min_gap=3.0)
        assert all(b - a >= 3.0 for a, b in zip(trig, trig[1:]))

    def test_none_near_clip_end(self):
        trig = zoom_triggers(self.words, duration=6.5, min_gap=1.0)
        assert all(t <= 6.5 - 1.0 for t in trig)

    def test_pause_starts_a_phrase(self):
        ws = [w("uno", 0, 0.3), w("dos", 0.3, 0.6), w("tres", 3.0, 3.3)]
        assert 3.0 in zoom_triggers(ws, duration=10.0, min_gap=1.0)

    def test_empty(self):
        assert zoom_triggers([], 10.0) == []


class TestKeyframes:
    def test_starts_and_ends_at_rest(self):
        kf = zoom_keyframes([2.0], duration=10.0)
        assert kf[0] == (0.0, 1.0)
        assert zoom_at(kf, 0.0) == 1.0 and zoom_at(kf, 10.0) == pytest.approx(1.0)

    def test_peak_within_range(self):
        kf = zoom_keyframes([2.0, 6.0], duration=12.0, peak=1.12)
        zs = [zoom_at(kf, i / 20) for i in range(240)]
        assert max(zs) == pytest.approx(1.12, abs=0.005) and min(zs) >= 1.0 - 1e-9

    def test_eased_not_linear(self):
        kf = zoom_keyframes([1.0], duration=6.0, peak=1.12, ramp_in=0.4)
        assert zoom_at(kf, 1.0) == pytest.approx(1.0)
        quarter = zoom_at(kf, 1.1) - 1.0  # 25% through the ramp
        assert quarter < 0.25 * 0.12  # smoothstep starts slow
        assert zoom_at(kf, 1.2) == pytest.approx(1.06, abs=1e-6)  # midpoint symmetric

    def test_continuous_when_pulses_overlap(self):
        kf = zoom_keyframes([1.0, 1.8], duration=8.0)
        assert all(t1 > t0 for (t0, _), (t1, _) in zip(kf, kf[1:]))
        assert abs(zoom_at(kf, 1.8 - 1e-6) - zoom_at(kf, 1.8 + 1e-6)) < 1e-3

    def test_no_triggers_is_constant(self):
        kf = zoom_keyframes([], duration=5.0)
        assert zoom_at(kf, 2.5) == 1.0

    def test_bounded(self):
        kf = zoom_keyframes([0.5, 1.0, 1.5, 2.0], duration=6.0)
        assert all(1.0 - 1e-9 <= zoom_at(kf, i / 50) <= 1.12 + 1e-9 for i in range(300))


class TestExpression:
    @pytest.mark.parametrize("triggers", [[], [2.0], [1.0, 1.8, 6.0]])
    def test_expression_matches_python(self, triggers):
        kf = zoom_keyframes(triggers, duration=9.0)
        expr = zoom_expression(kf)
        for i in range(0, 91):
            t = i / 10
            assert evaluate(expr, t) == pytest.approx(zoom_at(kf, t), abs=1e-4)

    def test_constant_expression(self):
        assert zoom_expression(zoom_keyframes([], 5.0)) == "1"

    def test_no_forbidden_characters(self):
        expr = zoom_expression(zoom_keyframes([1.0, 5.0], duration=9.0))
        assert "'" not in expr and ":" not in expr
