"""Tests for the musical bass/EQ management module."""

import numpy as np
import pytest

from djenius.audio.eq import (
    compute_bass_duck_curve,
    compute_eq_sweep_curve,
    compute_mid_duck_curve,
    apply_bass_management,
    compute_lf_shelf_curve,
)


class TestBassDuckCurve:
    """Tests for beat-aligned bass ducking curves."""

    def test_outgoing_ducks_bass(self):
        curve = compute_bass_duck_curve(44100, 44100, 120.0, "outgoing")
        assert curve.shape == (44100,)
        assert curve.dtype == np.float32
        # Starts near 1.0, ends lower
        assert curve[0] > curve[-1]
        # Never goes negative
        assert np.all(curve >= 0.0)
        assert np.all(curve <= 1.0)

    def test_incoming_lifts_bass(self):
        curve = compute_bass_duck_curve(44100, 44100, 120.0, "incoming")
        assert curve.shape == (44100,)
        # Starts lower, ends higher
        assert curve[0] < curve[-1]
        assert np.all(curve >= 0.0)
        assert np.all(curve <= 1.0)

    def test_beat_alignment(self):
        sr = 44100
        bpm = 120.0
        beat_samples = int(sr * 60.0 / bpm)  # 22050 samples per beat
        curve = compute_bass_duck_curve(beat_samples * 4, sr, bpm, "outgoing")
        # Should have periodic variation at beat rate
        assert curve.shape == (beat_samples * 4,)
        # Pumping creates local variation
        diffs = np.abs(np.diff(curve))
        assert np.max(diffs) > 0.0

    def test_zero_samples(self):
        curve = compute_bass_duck_curve(0, 44100, 120.0, "outgoing")
        assert curve.shape == (0,)

    def test_invalid_bpm(self):
        curve = compute_bass_duck_curve(44100, 44100, 0.0, "outgoing")
        assert np.all(curve == 1.0)


class TestEqSweepCurve:
    """Tests for filter sweep curves."""

    def test_highpass_sweep(self):
        curve = compute_eq_sweep_curve(44100, 44100, 100.0, 4000.0, "highpass_sweep")
        assert curve.shape == (44100,)
        assert curve[0] == pytest.approx(100.0, rel=0.01)
        assert curve[-1] == pytest.approx(4000.0, rel=0.01)
        # Monotonically increasing
        assert np.all(np.diff(curve) >= 0)

    def test_lowpass_sweep(self):
        curve = compute_eq_sweep_curve(44100, 44100, 100.0, 4000.0, "lowpass_sweep")
        assert curve[0] == pytest.approx(4000.0, rel=0.01)
        assert curve[-1] == pytest.approx(100.0, rel=0.01)
        # Monotonically decreasing
        assert np.all(np.diff(curve) <= 0)

    def test_log_spacing(self):
        curve = compute_eq_sweep_curve(100, 44100, 100.0, 1000.0, "highpass_sweep")
        # Log spacing: ratios between consecutive samples should be roughly constant
        ratios = curve[1:] / curve[:-1]
        # Filter out zeros
        ratios = ratios[ratios > 0]
        assert np.std(ratios) < 0.01  # Very low variance


class TestMidDuckCurve:
    """Tests for midrange ducking curves."""

    def test_no_clash_no_duck(self):
        curve = compute_mid_duck_curve(44100, 44100, 0.1, 0.1)
        assert np.all(curve == 1.0)

    def test_clash_ducks(self):
        curve = compute_mid_duck_curve(44100, 44100, 0.5, 0.5)
        assert np.all(curve <= 1.0)
        assert np.all(curve >= 0.5)
        # Should have a dip in the middle
        mid_idx = len(curve) // 2
        assert curve[mid_idx] < 1.0

    def test_symmetric_shape(self):
        curve = compute_mid_duck_curve(44100, 44100, 0.4, 0.4)
        # Smooth envelope: starts at 1.0, monotonically decreases, ends at min
        assert curve[0] >= curve[len(curve) // 2]
        assert curve[len(curve) // 2] >= curve[-1]
        # Should be smooth (no large jumps)
        diffs = np.abs(np.diff(curve))
        assert np.max(diffs) < 0.001


class TestLfShelfCurve:
    """Tests for LF shelf gain curve."""

    def test_zero_db(self):
        curve = compute_lf_shelf_curve(44100, 0.0)
        assert np.all(curve == pytest.approx(1.0, rel=1e-5))

    def test_negative_db(self):
        curve = compute_lf_shelf_curve(44100, -6.0)
        assert np.all(curve < 1.0)

    def test_positive_db(self):
        curve = compute_lf_shelf_curve(44100, 3.0)
        assert np.all(curve > 1.0)


class TestApplyBassManagement:
    """Tests for the full bass management pipeline."""

    def test_returns_matching_shapes(self):
        sr = 44100
        n = sr * 2  # 2 seconds
        source = np.random.randn(n).astype(np.float32)
        target = np.random.randn(n).astype(np.float32)

        ms, mt = apply_bass_management(
            source, target, sr, bpm=120.0,
            source_low_energy=0.4, target_low_energy=0.4,
            source_mid_energy=0.35, target_mid_energy=0.35,
        )
        assert ms.shape == source.shape
        assert mt.shape == target.shape

    def test_low_energy_no_duck(self):
        sr = 44100
        n = sr * 2
        source = np.random.randn(n).astype(np.float32)
        target = np.random.randn(n).astype(np.float32)

        # Both tracks have low energy — should return copies unchanged
        ms, mt = apply_bass_management(
            source, target, sr, bpm=120.0,
            source_low_energy=0.05, target_low_energy=0.05,
            source_mid_energy=0.05, target_mid_energy=0.05,
        )
        # Source should be a copy (identical values)
        np.testing.assert_array_equal(ms, source)

    def test_high_energy_reduced_bass(self):
        sr = 44100
        n = sr * 2
        # Pure bass signal
        t = np.linspace(0, 2.0, n, dtype=np.float32)
        bass = (np.sin(2 * np.pi * 60 * t) * 0.5).astype(np.float32)

        ms, mt = apply_bass_management(
            bass, bass, sr, bpm=120.0,
            source_low_energy=0.5, target_low_energy=0.5,
            source_mid_energy=0.3, target_mid_energy=0.3,
        )
        # Outgoing bass should be reduced
        assert np.max(np.abs(ms)) < np.max(np.abs(bass))

    def test_invalid_inputs_return_copy(self):
        sr = 44100
        source = np.zeros(sr, dtype=np.float32)
        target = np.zeros(sr, dtype=np.float32)
        ms, mt = apply_bass_management(source, target, sr, bpm=0.0)
        np.testing.assert_array_equal(ms, source)
