import numpy as np
import pytest

from clipmaker.speaker import (
    FaceObs,
    build_tracks,
    choose_speakers,
    crop_centers,
    mouth_diff,
    smooth_energy,
    track_energies,
)


def face(cx, cy=100.0, w=80.0, patch=None):
    return FaceObs(cx, cy, w, w * 1.2, patch)


class TestBuildTracks:
    def test_two_static_faces_make_two_tracks(self):
        samples = [[face(300), face(1300)] for _ in range(5)]
        tracks = build_tracks(samples)
        assert len(tracks) == 2
        assert all(len(t.obs) == 5 for t in tracks)
        assert sorted(round(t.obs[0].cx) for t in tracks) == [300, 1300]

    def test_order_of_detections_does_not_matter(self):
        samples = [[face(300), face(1300)], [face(1305), face(302)], [face(304), face(1310)]]
        tracks = build_tracks(samples)
        assert len(tracks) == 2
        left = min(tracks, key=lambda t: t.obs[0].cx)
        assert [round(left.obs[i].cx) for i in range(3)] == [300, 302, 304]

    def test_short_gap_keeps_identity(self):
        samples = [[face(300)], [], [], [face(305)]]
        tracks = build_tracks(samples, max_gap=3)
        assert len(tracks) == 1 and set(tracks[0].obs) == {0, 3}

    def test_long_gap_starts_new_track(self):
        samples = [[face(300)]] + [[]] * 6 + [[face(305)]]
        assert len(build_tracks(samples, max_gap=3)) == 2

    def test_far_jump_is_a_different_track(self):
        tracks = build_tracks([[face(300)], [face(1500)]])
        assert len(tracks) == 2

    def test_new_face_appears_midway(self):
        samples = [[face(300)], [face(300)], [face(300), face(1300)], [face(300), face(1300)]]
        tracks = build_tracks(samples)
        assert sorted(len(t.obs) for t in tracks) == [2, 4]

    def test_ids_unique_and_empty_input(self):
        assert build_tracks([]) == []
        tracks = build_tracks([[face(1), face(900)]])
        assert len({t.id for t in tracks}) == 2

    def test_one_detection_never_assigned_to_two_tracks(self):
        samples = [[face(300), face(400)], [face(350)]]
        tracks = build_tracks(samples)
        assert sum(1 for t in tracks if 1 in t.obs) == 1


class TestMouthEnergy:
    def test_identical_patches_zero(self):
        p = np.random.default_rng(0).integers(0, 255, (20, 24)).astype(np.float32)
        assert mouth_diff(p, p) == pytest.approx(0.0, abs=1e-6)

    def test_different_patches_positive_and_brightness_invariant(self):
        rng = np.random.default_rng(1)
        a = rng.integers(0, 255, (20, 24)).astype(np.float32)
        b = rng.integers(0, 255, (20, 24)).astype(np.float32)
        assert mouth_diff(a, b) > 0.05
        assert mouth_diff(a, a + 40) == pytest.approx(0.0, abs=1e-5)  # pure lighting change

    def test_missing_patch(self):
        assert mouth_diff(None, np.zeros((2, 2))) is None

    def test_track_energies(self):
        rng = np.random.default_rng(2)
        still = rng.integers(0, 255, (20, 24)).astype(np.float32)
        moving = [rng.integers(0, 255, (20, 24)).astype(np.float32) for _ in range(4)]
        samples = [[face(300, patch=still), face(1300, patch=moving[i])] for i in range(4)]
        tracks = build_tracks(samples)
        e = track_energies(tracks, 4)
        left = min(tracks, key=lambda t: t.obs[0].cx).id
        right = max(tracks, key=lambda t: t.obs[0].cx).id
        assert e[left][0] is None  # no previous sample
        assert e[left][1:] == pytest.approx([0.0, 0.0, 0.0], abs=1e-6)
        assert all(v > 0.05 for v in e[right][1:])

    def test_smooth_energy_ignores_missing(self):
        out = smooth_energy([None, 1.0, None, 3.0, 5.0], window=3)
        assert out[0] is None and out[2] is None
        assert out[1] == pytest.approx(1.0) and out[3] == pytest.approx(4.0)


def energies(**tracks):
    return {int(k[1:]): v for k, v in tracks.items()}


class TestChooseSpeakers:
    dt = 0.25

    def test_follows_the_most_active_track(self):
        n = 40
        e = energies(t0=[0.5] * n, t1=[0.05] * n)
        present = [{0, 1}] * n
        assert set(choose_speakers(present, e, self.dt, min_hold=1.5)) == {0}

    def test_switches_when_other_track_dominates_after_min_hold(self):
        n = 40
        e = energies(t0=[0.5] * 20 + [0.02] * 20, t1=[0.02] * 20 + [0.5] * 20)
        present = [{0, 1}] * n
        out = choose_speakers(present, e, self.dt, min_hold=1.5)
        assert out[0] == 0 and out[-1] == 1
        switch = out.index(1)
        assert switch >= 20  # never earlier than the takeover

    def test_min_hold_prevents_rapid_flipping(self):
        n = 40
        a = [0.5 if (i // 2) % 2 == 0 else 0.05 for i in range(n)]  # flips every 0.5 s
        b = [0.05 if (i // 2) % 2 == 0 else 0.5 for i in range(n)]
        out = choose_speakers([{0, 1}] * n, energies(t0=a, t1=b), self.dt, min_hold=1.5)
        switches = [i for i in range(1, n) if out[i] != out[i - 1]]
        assert all(b_ - a_ >= 6 for a_, b_ in zip(switches, switches[1:]))  # 1.5 s / 0.25 s
        assert len(switches) <= 6

    def test_hysteresis_margin_keeps_current_when_close(self):
        n = 40
        e = energies(t0=[0.30] * n, t1=[0.33] * n)  # only 10% higher
        out = choose_speakers([{0, 1}] * n, e, self.dt, min_hold=0.5, margin=1.3)
        assert len(set(out)) == 1

    def test_forced_switch_when_current_track_disappears(self):
        n = 20
        e = energies(t0=[0.5] * n, t1=[0.1] * n)
        present = [{0, 1}] * 8 + [{1}] * 12
        out = choose_speakers(present, e, self.dt, min_hold=5.0)
        assert out[7] == 0 and out[8] == 1  # immediate, min_hold does not apply

    def test_no_faces_gives_none(self):
        out = choose_speakers([set(), {0}, set()], energies(t0=[None, 0.1, None]), self.dt)
        assert out == [None, 0, None]

    def test_silence_falls_back_to_largest_face_then_holds(self):
        n = 10
        e = energies(t0=[0.0] * n, t1=[0.0] * n)
        areas = {0: [100.0] * n, 1: [900.0] * n}
        out = choose_speakers([{0, 1}] * n, e, self.dt, areas=areas)
        assert set(out) == {1}

    def test_missing_energy_treated_as_zero(self):
        out = choose_speakers([{0, 1}] * 4, energies(t0=[None] * 4, t1=[0.4] * 4), self.dt)
        assert set(out) == {1}


class TestCropCenters:
    def test_follows_speaker_and_flags_cuts(self):
        tracks = build_tracks([[face(400), face(1400)]] * 6)
        by_pos = {round(t.obs[0].cx): t.id for t in tracks}
        speakers = [by_pos[400]] * 3 + [by_pos[1400]] * 3
        xs, cuts = crop_centers(tracks, speakers, default_x=960, crop_w=608)
        assert xs[:3] == [400] * 3 and xs[3:] == [1400] * 3
        assert cuts == [False, False, False, True, False, False]

    def test_no_speaker_uses_default(self):
        xs, cuts = crop_centers([], [None, None], default_x=960, crop_w=608)
        assert xs == [960, 960] and cuts == [False, False]

    def test_group_shot_when_everyone_fits_in_crop(self):
        tracks = build_tracks([[face(800), face(1000)]] * 3)
        ids = [t.id for t in tracks]
        xs, cuts = crop_centers(tracks, [ids[0], ids[1], ids[0]], default_x=960, crop_w=608)
        assert xs == [900, 900, 900] and not any(cuts)

    def test_speaker_track_missing_at_sample_holds_last_position(self):
        tracks = build_tracks([[face(400)], [], [face(402)]], max_gap=3)
        xs, _ = crop_centers(tracks, [tracks[0].id] * 3, default_x=960, crop_w=608)
        assert xs[1] == pytest.approx(400, abs=3)
