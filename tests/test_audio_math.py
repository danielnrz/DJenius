"""Tests for audio math utility functions."""

from __future__ import annotations

import numpy as np
import pytest

from djenius.utils.audio_math import (
    equal_power_crossfade,
    linear_fade_out,
    linear_fade_in,
    db_to_linear,
    linear_to_db,
    soft_clip,
    compute_rms_energy,
    compute_energy_curve,
    detect_intro_outro,
)


class TestCrossfade:
    def test_equal_power_length(self):
        fo, fi = equal_power_crossfade(1000)
        assert len(fo) == 1000
        assert len(fi) == 1000

    def test_equal_power_values(self):
        fo, fi = equal_power_crossfade(1000)
        assert fo[0] == pytest.approx(1.0, abs=0.01)
        assert fi[0] == pytest.approx(0.0, abs=0.01)
        assert fo[-1] == pytest.approx(0.0, abs=0.01)
        assert fi[-1] == pytest.approx(1.0, abs=0.01)

    def test_equal_power_sum(self):
        """cos^2 + sin^2 = 1 at every point."""
        n = 500
        fo, fi = equal_power_crossfade(n)
        total = fo ** 2 + fi ** 2
        np.testing.assert_allclose(total, 1.0, atol=1e-6)

    def test_linear_fade_out(self):
        f = linear_fade_out(100)
        assert f[0] == pytest.approx(1.0, abs=0.01)
        assert f[-1] == pytest.approx(0.0, abs=0.01)

    def test_linear_fade_in(self):
        f = linear_fade_in(100)
        assert f[0] == pytest.approx(0.0, abs=0.01)
        assert f[-1] == pytest.approx(1.0, abs=0.01)


class TestDbConversion:
    def test_db_to_linear_0db(self):
        assert db_to_linear(0.0) == pytest.approx(1.0)

    def test_db_to_linear_neg20(self):
        assert db_to_linear(-20.0) == pytest.approx(0.1)

    def test_linear_to_db_1(self):
        assert linear_to_db(1.0) == pytest.approx(0.0)

    def test_linear_to_db_zero(self):
        assert linear_to_db(0.0) == -120.0

    def test_linear_to_db_negative(self):
        assert linear_to_db(-1.0) == -120.0

    def test_roundtrip(self):
        for db_val in [-6.0, -12.0, -24.0, 0.0]:
            lin = db_to_linear(db_val)
            db_back = linear_to_db(lin)
            assert db_back == pytest.approx(db_val, abs=0.01)


class TestSoftClip:
    def test_below_threshold_unchanged(self):
        audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = soft_clip(audio, threshold_db=-1.0)
        np.testing.assert_allclose(result, audio, atol=1e-6)

    def test_above_threshold_compressed(self):
        audio = np.array([0.0, 0.5, 1.0, 2.0], dtype=np.float32)
        result = soft_clip(audio, threshold_db=-6.0)
        # Peaks above threshold should be reduced
        assert abs(result[3]) < abs(audio[3])
        # Values below threshold unchanged
        assert result[0] == 0.0

    def test_preserves_length(self):
        audio = np.random.randn(1000).astype(np.float32) * 0.5
        result = soft_clip(audio)
        assert len(result) == 1000


class TestRMSEnergy:
    def test_silence(self):
        signal = np.zeros(44100, dtype=np.float32)
        rms = compute_rms_energy(signal, 2048, 512)
        np.testing.assert_allclose(rms, 0.0, atol=1e-10)

    def test_sine_wave(self):
        sr = 44100
        t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
        signal = 0.5 * np.sin(2 * np.pi * 440 * t)
        rms = compute_rms_energy(signal, 2048, 512)
        # RMS of a sine wave = amplitude / sqrt(2)
        expected = 0.5 / np.sqrt(2)
        np.testing.assert_allclose(rms, expected, atol=0.05)

    def test_output_length(self):
        signal = np.random.randn(44100).astype(np.float32)
        rms = compute_rms_energy(signal, 2048, 512)
        expected_len = 1 + (44100 - 2048) // 512
        assert len(rms) == expected_len


class TestEnergyCurve:
    def test_silence_returns_zeros(self):
        signal = np.zeros(44100, dtype=np.float32)
        curve = compute_energy_curve(signal, 44100, resolution_hz=1.0)
        assert len(curve) > 0
        np.testing.assert_allclose(curve, 0.0, atol=1e-10)

    def test_normalized_0_to_1(self):
        t = np.linspace(0, 2.0, 88200, endpoint=False, dtype=np.float32)
        signal = 0.3 * np.sin(2 * np.pi * 440 * t)
        curve = compute_energy_curve(signal, 44100, resolution_hz=1.0)
        assert curve.max() <= 1.0 + 1e-6
        assert curve.max() > 0.0


class TestDetectIntroOutro:
    def test_uniform_energy(self):
        curve = np.ones(60, dtype=np.float32) * 0.8
        intro_end, outro_start = detect_intro_outro(curve, threshold=0.3)
        assert intro_end >= 0
        assert outro_start >= intro_end

    def test_silent_track(self):
        curve = np.zeros(60, dtype=np.float32)
        intro_end, outro_start = detect_intro_outro(curve)
        assert intro_end == 0.0
        # With all-zero energy, outro_start defaults to n-1
        assert outro_start == 59.0

    def test_empty_curve(self):
        intro_end, outro_start = detect_intro_outro(np.array([]))
        assert intro_end == 0.0
        assert outro_start == 0.0
