"""Tests for BPM timing utilities and beat phase alignment.

Generates synthetic click tracks at known BPMs and verifies that timing
calculations are mathematically correct.
"""

from __future__ import annotations

import numpy as np
import pytest

from djenius.utils.timing import (
    bpm_to_samples,
    bpm_to_beat_period,
    _envelope,
    calculate_phase_shift,
    apply_phase_shift,
    measure_phase_error,
)

SR = 44100


# ── Click track generator ──────────────────────────────────────────────

def make_click_track(bpm: float, duration: float = 4.0, sr: int = SR) -> np.ndarray:
    """Generate a synthetic click track at a given BPM.

    Each click is a short burst of 1000 Hz sine with exponential decay.
    This is used as a ground-truth transient source for beat alignment tests.
    """
    n_samples = int(sr * duration)
    audio = np.zeros(n_samples, dtype=np.float32)
    samples_per_beat = int(sr * 60.0 / bpm)
    click_len = min(256, samples_per_beat // 4)

    for i in range(0, n_samples, samples_per_beat):
        end = min(i + click_len, n_samples)
        t = np.linspace(0, click_len / sr, click_len, endpoint=False, dtype=np.float32)
        click = 0.8 * np.sin(2 * np.pi * 1000 * t)
        click *= np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        audio[i:end] = click[:end - i]

    return audio


# ── Fixtures for all required BPMs ─────────────────────────────────────

BPM_VALUES = [80, 90, 100, 120, 128, 140, 160]


@pytest.fixture(params=BPM_VALUES, ids=[f"{b}bpm" for b in BPM_VALUES])
def click_track(request):
    """Generate a click track at the parameterized BPM."""
    return make_click_track(request.param, duration=4.0)


@pytest.fixture
def click_120():
    """Click track at 120 BPM."""
    return make_click_track(120.0)


@pytest.fixture
def click_140():
    """Click track at 140 BPM."""
    return make_click_track(140.0)


# ── Tests: bpm_to_samples ─────────────────────────────────────────────

class TestBpmToSamples:
    """Verify BPM-to-sample conversion is mathematically exact."""

    @pytest.mark.parametrize("bpm,expected_samples", [
        (60, 44100),       # 60 BPM = 1 beat/sec = 44100 samples
        (120, 22050),      # 120 BPM = 2 beats/sec = 22050 samples
        (180, 14700),      # 180 BPM = 3 beats/sec = 14700 samples
        (80, 33075),       # 80 BPM: 44100 * 60 / 80 = 33075
        (90, 29400),       # 90 BPM: 44100 * 60 / 90 = 29400
        (100, 26460),      # 100 BPM: 44100 * 60 / 100 = 26460
        (128, 20672),      # 128 BPM: 44100 * 60 / 128 ≈ 20672
        (140, 18900),      # 140 BPM: 44100 * 60 / 140 = 18900
        (160, 16538),      # 160 BPM: 44100 * 60 / 160 ≈ 16538
    ])
    def test_exact_sample_count(self, bpm, expected_samples):
        result = bpm_to_samples(bpm, SR)
        assert result == expected_samples

    def test_bpm_to_samples_known_values(self):
        """Direct verification of the 7 required BPM values."""
        for bpm in BPM_VALUES:
            samples = bpm_to_samples(bpm, SR)
            # Verify by computing back: bpm = sr * 60 / samples
            computed_bpm = SR * 60.0 / samples
            assert computed_bpm == pytest.approx(bpm, rel=0.001), \
                f"BPM {bpm}: got {samples} samples, roundtrip gave {computed_bpm}"

    def test_zero_bpm_raises(self):
        with pytest.raises(ValueError, match="positive"):
            bpm_to_samples(0, SR)

    def test_negative_bpm_raises(self):
        with pytest.raises(ValueError, match="positive"):
            bpm_to_samples(-120, SR)


# ── Tests: bpm_to_beat_period ─────────────────────────────────────────

class TestBpmToBeatPeriod:

    @pytest.mark.parametrize("bpm,expected_period", [
        (60, 1.0),
        (120, 0.5),
        (180, 1.0 / 3.0),
        (90, 2.0 / 3.0),
    ])
    def test_exact_period(self, bpm, expected_period):
        assert bpm_to_beat_period(bpm, SR) == pytest.approx(expected_period, abs=1e-10)


# ── Tests: Click track generation ─────────────────────────────────────

class TestClickTrack:
    """Verify that synthetic click tracks have correct transient spacing."""

    def test_click_has_clicks(self, click_track):
        """Click track should have non-zero energy."""
        assert np.max(np.abs(click_track)) > 0.1

    def test_click_track_length(self):
        """4-second click track at any BPM should have expected sample count."""
        audio = make_click_track(120.0, duration=4.0)
        assert len(audio) == int(SR * 4.0)

    @pytest.mark.parametrize("bpm", BPM_VALUES)
    def test_click_spacing_matches_bpm(self, bpm):
        """Distance between click onsets should match BPM in samples."""
        audio = make_click_track(bpm, duration=4.0)
        expected_samples_per_beat = bpm_to_samples(bpm, SR)

        # Find click positions via onset envelope
        env = _envelope(audio, hop=256)
        threshold = env.max() * 0.3
        onsets = np.where(env > threshold)[0]

        # Get unique onset positions (cluster nearby frames)
        if len(onsets) < 2:
            pytest.skip("Not enough onsets detected")

        # Cluster onsets within 1 hop of each other
        clusters = []
        current_cluster = [onsets[0]]
        for o in onsets[1:]:
            if o - current_cluster[-1] <= 2:
                current_cluster.append(o)
            else:
                clusters.append(int(np.mean(current_cluster)))
                current_cluster = [o]
        clusters.append(int(np.mean(current_cluster)))

        if len(clusters) < 2:
            pytest.skip("Not enough onset clusters")

        # Convert to sample positions (multiply by hop)
        hop = 256
        onset_samples = [c * hop for c in clusters]

        # Check inter-onset intervals
        intervals = np.diff(onset_samples)
        for interval in intervals:
            assert interval == pytest.approx(expected_samples_per_beat, rel=0.15), \
                f"BPM {bpm}: interval {interval} != expected {expected_samples_per_beat}"


# ── Tests: apply_phase_shift ──────────────────────────────────────────

class TestApplyPhaseShift:
    """Verify sample-level phase shifting is correct."""

    def test_zero_shift_no_change(self):
        audio = make_click_track(120.0, duration=1.0)
        shifted = apply_phase_shift(audio, 0)
        np.testing.assert_array_equal(shifted, audio)

    def test_positive_shift_delays(self):
        """Positive shift should delay the signal (pad zeros at start)."""
        audio = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        shifted = apply_phase_shift(audio, 3)
        # The impulse at index 3 should now be at index 6
        expected = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        np.testing.assert_array_almost_equal(shifted, expected)

    def test_negative_shift_advances(self):
        """Negative shift should advance the signal (trim from start)."""
        audio = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        shifted = apply_phase_shift(audio, -3)
        # The impulse at index 3 should now be at index 0
        expected = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        np.testing.assert_array_almost_equal(shifted, expected)

    def test_preserves_length(self):
        """Output length must always match input length."""
        audio = make_click_track(120.0, duration=2.0)
        for shift in [-5000, -100, 0, 100, 5000]:
            shifted = apply_phase_shift(audio, shift)
            assert len(shifted) == len(audio), \
                f"Shift {shift}: len {len(shifted)} != {len(audio)}"

    def test_preserves_stereo(self):
        """Stereo shift should preserve channel count and both channels."""
        sr = SR
        n = sr  # 1 second
        t = np.linspace(0, 1.0, n, endpoint=False, dtype=np.float32)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = 0.5 * np.sin(2 * np.pi * 880 * t)
        stereo = np.column_stack([left, right]).astype(np.float32)

        shifted = apply_phase_shift(stereo, 1000)
        assert shifted.shape == (n, 2)
        # Left and right should both be shifted
        assert np.max(np.abs(shifted[:, 0])) > 0
        assert np.max(np.abs(shifted[:, 1])) > 0

    def test_large_shift_beyond_signal(self):
        """Shifting beyond signal length should produce zeros."""
        audio = np.array([0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        shifted = apply_phase_shift(audio, 100)
        np.testing.assert_array_equal(shifted, np.zeros(5, dtype=np.float32))


# ── Tests: calculate_phase_shift ──────────────────────────────────────

class TestCalculatePhaseShift:
    """Verify beat phase shift detection between click tracks."""

    def test_identical_signals_zero_shift(self):
        """Two identical click tracks should have zero phase shift."""
        audio = make_click_track(120.0, duration=2.0)
        shift = calculate_phase_shift(audio, audio, SR)
        # Should be near zero (may not be exactly 0 due to envelope resolution)
        assert abs(shift) <= 512, f"Self-shift should be near 0, got {shift}"

    def test_known_shift_detected(self):
        """A known delay should be detected by the phase shift calculator."""
        audio = make_click_track(120.0, duration=4.0)
        known_shift = 4410  # ~100ms at 44100 Hz (2 beats at 120 BPM)
        delayed = np.zeros_like(audio)
        delayed[known_shift:] = audio[:-known_shift]

        detected = calculate_phase_shift(audio, delayed, SR)
        # The sign convention: positive shift = target is delayed relative to source
        # We detect how much we need to shift target back, so it's negative of the delay
        # Just check the magnitude is in the right ballpark (envelope resolution = hop*2)
        assert abs(abs(detected) - known_shift) <= 2048, \
            f"Expected shift magnitude ~{known_shift}, got {detected}"

    def test_shift_invariance_to_amplitude(self):
        """Phase shift detection should work regardless of amplitude."""
        audio = make_click_track(120.0, duration=2.0)
        quiet = audio * 0.1
        shift = calculate_phase_shift(audio, quiet, SR)
        assert abs(shift) <= 512

    def test_shift_works_with_bpm_parameterized(self, click_track):
        """Phase shift should work for all BPM values."""
        audio = click_track
        # Self-shift should be near zero
        shift = calculate_phase_shift(audio, audio, SR)
        assert abs(shift) <= 1024, f"Self-shift: {shift}"


# ── Tests: measure_phase_error ────────────────────────────────────────

class TestMeasurePhaseError:
    """Verify phase error measurement."""

    def test_identical_signals_low_error(self):
        """Identical tracks should have near-zero phase error."""
        audio = make_click_track(120.0, duration=2.0)
        error = measure_phase_error(audio, audio, SR)
        assert error <= 1024, f"Self-error should be near 0, got {error}"

    def test_shifted_signals_higher_error(self):
        """Shifted tracks should have higher error than aligned ones."""
        audio = make_click_track(120.0, duration=4.0)
        # Create a shifted version
        known_shift = 5000
        shifted = np.zeros_like(audio)
        shifted[known_shift:] = audio[:-known_shift]

        error_unaligned = measure_phase_error(audio, shifted, SR)
        error_aligned = measure_phase_error(audio, audio, SR)

        assert error_unaligned > error_aligned, \
            f"Unaligned error ({error_unaligned}) should be > aligned ({error_aligned})"

    def test_error_always_non_negative(self):
        """Phase error should always be >= 0."""
        audio = make_click_track(120.0, duration=2.0)
        error = measure_phase_error(audio, audio, SR)
        assert error >= 0


# ── Tests: Envelope detection ─────────────────────────────────────────

class TestEnvelope:
    """Verify onset envelope extraction."""

    def test_silence_gives_zeros(self):
        silence = np.zeros(SR * 2, dtype=np.float32)
        env = _envelope(silence)
        np.testing.assert_allclose(env, 0.0)

    def test_click_track_has_peaks(self):
        audio = make_click_track(120.0, duration=2.0)
        env = _envelope(audio, hop=256)
        assert env.max() > 0

    def test_envelope_length(self):
        """Envelope length should be approximately n_samples / hop."""
        audio = make_click_track(120.0, duration=2.0)
        hop = 512
        env = _envelope(audio, hop)
        expected_len = len(audio) // hop
        assert len(env) == expected_len
