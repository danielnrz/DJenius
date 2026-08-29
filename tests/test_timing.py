"""Tests for BPM timing utilities and beat phase alignment.

Generates synthetic click tracks at known BPMs and verifies that timing
calculations are mathematically correct.
"""

from __future__ import annotations

import numpy as np
import pytest
import scipy.signal as scipy_signal

from djenius.utils.timing import (
    bpm_to_samples,
    bpm_to_beat_period,
    _to_mono,
    _envelope,
    calculate_phase_shift,
    apply_phase_shift,
    measure_phase_error,
)
from djenius.audio.transitions import _beatmatched_blend

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


# ── Tests: _to_mono stereo conversion ─────────────────────────────────

class TestToMono:
    """Verify _to_mono properly averages channels without interleaving."""

    def test_mono_passthrough(self):
        """1D audio should pass through unchanged."""
        audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = _to_mono(audio)
        np.testing.assert_array_equal(result, audio)

    def test_stereo_averages_channels(self):
        """Stereo (N,2) should be mean of both channels."""
        stereo = np.array([[1.0, 3.0], [2.0, 4.0]], dtype=np.float32)
        result = _to_mono(stereo)
        expected = np.array([2.0, 3.0], dtype=np.float32)
        np.testing.assert_array_almost_equal(result, expected)

    def test_stereo_impulse_preserved_unlike_flatten(self):
        """Impulse on left channel only should stay at correct index.

        This is the regression test for the flatten() bug:
        flatten() interleaves L/R → doubles length, moves impulse position.
        _to_mono averages → preserves time axis.
        """
        sr = SR
        n = 1000
        stereo = np.zeros((n, 2), dtype=np.float32)
        stereo[500, 0] = 1.0  # impulse only on left

        result = _to_mono(stereo)
        assert result.shape == (n,), f"_to_mono shape {result.shape} != ({n},)"
        assert np.argmax(result) == 500, f"Impulse at {np.argmax(result)}, expected 500"

        # Confirm flatten() would have been wrong
        flat = stereo.flatten()
        assert flat.shape == (n * 2,), "flatten() doubles length for stereo"
        assert np.argmax(flat) == 1000, "flatten() moves impulse to wrong position"

    def test_asymmetric_stereo_content(self):
        """Asymmetric stereo: loud click on left, quiet click on right at different times.

        _to_mono must produce a clean mono signal where both transients
        are visible at their original time positions.
        """
        sr = SR
        n = sr  # 1 second
        stereo = np.zeros((n, 2), dtype=np.float32)

        # Loud click on left at 200ms
        left_pos = int(sr * 0.2)
        click_len = 256
        t = np.linspace(0, click_len / sr, click_len, endpoint=False, dtype=np.float32)
        left_click = 0.9 * np.sin(2 * np.pi * 1000 * t) * np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        end = min(left_pos + click_len, n)
        stereo[left_pos:end, 0] = left_click[:end - left_pos]

        # Click on right at 500ms (lower amplitude than left but still detectable)
        right_pos = int(sr * 0.5)
        right_click = 0.4 * np.sin(2 * np.pi * 800 * t) * np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        end = min(right_pos + click_len, n)
        stereo[right_pos:end, 1] = right_click[:end - right_pos]

        mono = _to_mono(stereo)
        assert mono.shape == (n,), f"Mono shape {mono.shape} != ({n},)"

        # Verify left transient is visible around 200ms
        env = _envelope(mono, hop=256)
        onset_frames = np.where(env > env.max() * 0.1)[0]
        onset_times_ms = (onset_frames * 256 / sr) * 1000
        # Left click at 200ms should be detected
        assert any(150 < t < 300 for t in onset_times_ms), \
            f"Left click not found in mono envelope at ~200ms, onsets: {onset_times_ms}"
        # Right click at 500ms should also be detected
        assert any(400 < t < 600 for t in onset_times_ms), \
            f"Right click not found in mono envelope at ~500ms, onsets: {onset_times_ms}"


# ── Tests: Beat alignment BPM × offset matrix ──────────────────────────

TARGET_BPM = [90, 120, 128, 140]
TARGET_OFFSETS_MS = [20, 50, 100, 175, 250]


def _make_stereo_click_track(bpm: float, duration: float = 5.0, sr: int = SR) -> np.ndarray:
    """Generate a stereo click track with clicks primarily on the left channel.

    This provides asymmetric stereo content for testing _to_mono behavior
    in the context of real beat alignment.
    """
    n_samples = int(sr * duration)
    stereo = np.zeros((n_samples, 2), dtype=np.float32)
    samples_per_beat = int(sr * 60.0 / bpm)
    click_len = min(256, samples_per_beat // 4)

    for i in range(0, n_samples, samples_per_beat):
        end = min(i + click_len, n_samples)
        t = np.linspace(0, click_len / sr, click_len, endpoint=False, dtype=np.float32)
        click = 0.8 * np.sin(2 * np.pi * 1000 * t)
        click *= np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        # Left channel: full amplitude; Right channel: 30% amplitude
        stereo[i:end, 0] = click[:end - i]
        stereo[i:end, 1] = (0.3 * click[:end - i]).astype(np.float32)

    return stereo


class TestBeatAlignmentMatrix:
    """Comprehensive matrix: BPM × offset → verify after-correction error < 20ms.

    This is the primary validation that the beat-phase alignment system
    achieves the required <20ms tolerance after correction.
    """

    @pytest.mark.parametrize("bpm", TARGET_BPM, ids=[f"{b}bpm" for b in TARGET_BPM])
    @pytest.mark.parametrize("offset_ms", TARGET_OFFSETS_MS, ids=[f"{o}ms" for o in TARGET_OFFSETS_MS])
    def test_mono_alignment_error_below_20ms(self, bpm, offset_ms):
        """Mono click track alignment: error after correction < 20ms."""
        src = make_click_track(bpm, duration=5.0)
        offset_samp = int(SR * offset_ms / 1000)
        tgt = np.zeros_like(src)
        tgt[offset_samp:] = src[:-offset_samp]

        err_before = measure_phase_error(src, tgt, SR)
        shift = calculate_phase_shift(src, tgt, SR, bpm=bpm)
        corrected = apply_phase_shift(tgt, shift)
        err_after = measure_phase_error(src, corrected, SR, bpm=bpm)

        err_after_ms = err_after / SR * 1000
        assert err_after_ms < 20.0, \
            f"{bpm}BPM {offset_ms}ms: after={err_after_ms:.1f}ms (must be <20ms), " \
            f"shift={shift}, before={err_before/SR*1000:.1f}ms"
        # Also verify improvement (or at least not worse)
        assert err_after <= err_before + 200, \
            f"{bpm}BPM {offset_ms}ms: after ({err_after}) much worse than before ({err_before})"

    @pytest.mark.parametrize("bpm", TARGET_BPM, ids=[f"{b}bpm" for b in TARGET_BPM])
    @pytest.mark.parametrize("offset_ms", TARGET_OFFSETS_MS, ids=[f"{o}ms" for o in TARGET_OFFSETS_MS])
    def test_stereo_alignment_error_below_20ms(self, bpm, offset_ms):
        """Stereo click track (asymmetric): error after correction < 20ms.

        Regression test for the flatten() bug. With the old flatten()-based
        stereo→mono, these tests would fail because interleaving corrupts
        the temporal representation.
        """
        src = _make_stereo_click_track(bpm, duration=5.0)
        offset_samp = int(SR * offset_ms / 1000)
        tgt = np.zeros_like(src)
        tgt[offset_samp:] = src[:-offset_samp]

        err_before = measure_phase_error(src, tgt, SR)
        shift = calculate_phase_shift(src, tgt, SR, bpm=bpm)
        corrected = apply_phase_shift(tgt, shift)
        err_after = measure_phase_error(src, corrected, SR, bpm=bpm)

        err_after_ms = err_after / SR * 1000
        assert err_after_ms < 20.0, \
            f"Stereo {bpm}BPM {offset_ms}ms: after={err_after_ms:.1f}ms (must be <20ms), " \
            f"shift={shift}, before={err_before/SR*1000:.1f}ms"
        assert err_after <= err_before + 200, \
            f"Stereo {bpm}BPM {offset_ms}ms: after ({err_after}) much worse than before ({err_before})"

    @pytest.mark.parametrize("bpm", TARGET_BPM, ids=[f"{b}bpm" for b in TARGET_BPM])
    @pytest.mark.parametrize("offset_ms", TARGET_OFFSETS_MS, ids=[f"{o}ms" for o in TARGET_OFFSETS_MS])
    def test_alignment_round_trip(self, bpm, offset_ms):
        """Full round trip: misaligned → detect → shift → verify.

        Exercises the real sequence: create misaligned signal,
        calculate_phase_shift, apply_phase_shift, measure_phase_error.
        The corrected error must always be substantially lower than before.
        """
        src = make_click_track(bpm, duration=5.0)
        offset_samp = int(SR * offset_ms / 1000)
        tgt = np.zeros_like(src)
        tgt[offset_samp:] = src[:-offset_samp]

        # Step 1: measure error before correction
        err_before_samples = measure_phase_error(src, tgt, SR, bpm=bpm)
        err_before_ms = err_before_samples / SR * 1000

        # Step 2: detect shift
        shift = calculate_phase_shift(src, tgt, SR, bpm=bpm)

        # Step 3: apply correction
        corrected = apply_phase_shift(tgt, shift)

        # Step 4: measure error after correction
        err_after_samples = measure_phase_error(src, corrected, SR, bpm=bpm)
        err_after_ms = err_after_samples / SR * 1000

        # Assertions
        assert err_after_ms < 20.0, \
            f"{bpm}BPM {offset_ms}ms round-trip: after={err_after_ms:.1f}ms (must be <20ms)"
        assert err_before_ms > err_after_ms, \
            f"{bpm}BPM {offset_ms}ms: before ({err_before_ms:.1f}ms) should be > after ({err_after_ms:.1f}ms)"
        # Substantial improvement: after should be at least 5x better
        if err_before_ms > 10:
            assert err_before_ms / max(err_after_ms, 0.001) >= 5.0, \
                f"{bpm}BPM {offset_ms}ms: improvement ratio {err_before_ms/err_after_ms:.1f}x (need >=5x)"


# ── Tests: Asymmetric stereo regression ────────────────────────────────

class TestAsymmetricStereoRegression:
    """Regression tests for the flatten() bug with asymmetric stereo content.

    The old code used ndarray.flatten() for stereo-to-mono conversion in
    calculate_phase_shift. For a (N, 2) array, flatten() interleaves
    L/R samples, producing a 2N-length array that corrupts the temporal
    representation and causes incorrect phase shift detection.
    """

    def test_asymmetric_stereo_detects_correct_shift(self):
        """Stereo audio with only left-channel content: shift detection must
        match mono-equivalent behavior."""
        sr = SR
        mono = make_click_track(120.0, duration=5.0)
        n = len(mono)

        # Create stereo version: left = mono, right = silence
        stereo_left_only = np.zeros((n, 2), dtype=np.float32)
        stereo_left_only[:, 0] = mono
        # right channel = 0 (asymmetric)

        # Shift both by same amount
        offset_samp = int(sr * 0.1)  # 100ms
        shifted_mono = np.zeros_like(mono)
        shifted_mono[offset_samp:] = mono[:-offset_samp]
        shifted_stereo = np.zeros_like(stereo_left_only)
        shifted_stereo[offset_samp:] = stereo_left_only[:-offset_samp]

        # Phase shift detection should be consistent
        shift_mono = calculate_phase_shift(mono, shifted_mono, sr)
        shift_stereo = calculate_phase_shift(stereo_left_only, shifted_stereo, sr)

        # Both should detect ~same shift (within 500 samples)
        assert abs(shift_mono - shift_stereo) <= 500, \
            f"Mono shift {shift_mono} != stereo shift {shift_stereo}"

    def test_asymmetric_stereo_both_channels_detected(self):
        """Stereo with clicks on different channels at different times:
        mono mix must preserve both transient positions."""
        sr = SR
        n = sr * 3  # 3 seconds
        stereo = np.zeros((n, 2), dtype=np.float32)

        # Click on left at 500ms
        left_pos = int(sr * 0.5)
        click_len = 256
        t = np.linspace(0, click_len / sr, click_len, endpoint=False, dtype=np.float32)
        left_click = 0.8 * np.sin(2 * np.pi * 1000 * t)
        left_click *= np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        end = min(left_pos + click_len, n)
        stereo[left_pos:end, 0] = left_click[:end - left_pos]

        # Click on right at 1500ms
        right_pos = int(sr * 1.5)
        right_click = 0.8 * np.sin(2 * np.pi * 600 * t)
        right_click *= np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        end = min(right_pos + click_len, n)
        stereo[right_pos:end, 1] = right_click[:end - right_pos]

        # Convert to mono via _to_mono
        mono = _to_mono(stereo)

        # Detect onsets in mono signal
        env = _envelope(mono, hop=256)
        threshold = env.max() * 0.2
        onset_frames = np.where(env > threshold)[0]

        if len(onset_frames) == 0:
            pytest.skip("No onsets detected")

        # Cluster
        clusters = []
        current = [onset_frames[0]]
        for f in onset_frames[1:]:
            if f - current[-1] <= 2:
                current.append(f)
            else:
                clusters.append(int(np.mean(current)))
                current = [f]
        clusters.append(int(np.mean(current)))

        onset_times_ms = [(c * 256 / sr) * 1000 for c in clusters]

        # Must find onsets near 500ms (left channel) and 1500ms (right channel)
        left_found = any(350 < t < 700 for t in onset_times_ms)
        right_found = any(1300 < t < 1700 for t in onset_times_ms)

        assert left_found, f"Left channel onset not found at ~500ms, onsets: {onset_times_ms}"
        assert right_found, f"Right channel onset not found at ~1500ms, onsets: {onset_times_ms}"


# ── Tests: Independent ground-truth validation ─────────────────────────
#
# These tests do NOT use measure_phase_error (which re-runs the estimator
# and is self-confirming). Instead, they validate against the KNOWN
# injected offset that was used to create the synthetic misalignment.


def _independent_residual(src, tgt, sr, bpm, offset_samp):
    """Compute independent ground-truth residual after correction.

    Returns the absolute residual in samples between the injected offset
    and the applied correction. This is NOT self-confirming because we
    compare the applied shift against the known injected offset, not
    against a re-estimation.

    For periodic signals (click tracks), the residual is measured modulo
    the beat period: advancing by 21 frames or delaying by 19 frames
    on a 40-frame-period signal are musically equivalent. The
    beat-period-aware residual captures the true alignment quality.
    """
    shift = calculate_phase_shift(src, tgt, sr, bpm=bpm)
    corrected = apply_phase_shift(tgt, shift)

    # The raw offset+shift may differ by whole beat periods.
    # For periodic signals this is musically equivalent, so we
    # measure the residual modulo the beat period.
    beat_samp = int(sr * 60.0 / bpm) if bpm and bpm > 0 else 0
    raw_res = abs(offset_samp + shift)
    if beat_samp > 0:
        res_mod = (offset_samp + shift) % beat_samp
        true_residual_samples = min(res_mod, beat_samp - res_mod)
    else:
        true_residual_samples = raw_res

    return true_residual_samples, shift


class TestIndependentGroundTruth:
    """Validate beat alignment against known injected offsets.

    These tests are NOT self-confirming. They compute the residual by
    comparing the known injected offset against the algorithm's correction,
    not by re-running the estimator on the corrected signal.
    """

    @pytest.mark.parametrize("bpm", TARGET_BPM, ids=[f"{b}bpm" for b in TARGET_BPM])
    @pytest.mark.parametrize("offset_ms", TARGET_OFFSETS_MS, ids=[f"{o}ms" for o in TARGET_OFFSETS_MS])
    def test_mono_independent_residual_below_20ms(self, bpm, offset_ms):
        """Mono: independent residual < 20ms for all BPM × offset combinations."""
        src = make_click_track(bpm, duration=5.0)
        offset_samp = int(SR * offset_ms / 1000)
        tgt = np.zeros_like(src)
        tgt[offset_samp:] = src[:-offset_samp]

        residual_samples, shift = _independent_residual(src, tgt, SR, bpm, offset_samp)
        residual_ms = residual_samples / SR * 1000

        assert residual_ms < 20.0, (
            f"{bpm}BPM {offset_ms}ms mono: independent residual {residual_ms:.1f}ms "
            f"(must be <20ms), shift={shift}, offset={offset_samp}"
        )

    @pytest.mark.parametrize("bpm", TARGET_BPM, ids=[f"{b}bpm" for b in TARGET_BPM])
    @pytest.mark.parametrize("offset_ms", TARGET_OFFSETS_MS, ids=[f"{o}ms" for o in TARGET_OFFSETS_MS])
    def test_stereo_independent_residual_below_20ms(self, bpm, offset_ms):
        """Stereo: independent residual < 20ms for all BPM × offset combinations."""
        src = _make_stereo_click_track(bpm, duration=5.0)
        offset_samp = int(SR * offset_ms / 1000)
        tgt = np.zeros_like(src)
        tgt[offset_samp:] = src[:-offset_samp]

        residual_samples, shift = _independent_residual(src, tgt, SR, bpm, offset_samp)
        residual_ms = residual_samples / SR * 1000

        assert residual_ms < 20.0, (
            f"{bpm}BPM {offset_ms}ms stereo: independent residual {residual_ms:.1f}ms "
            f"(must be <20ms), shift={shift}, offset={offset_samp}"
        )


# ── Tests: Production-path regression for _beatmatched_blend ───────────
#
# Tests the full _beatmatched_blend function end-to-end with synthetic
# audio to ensure the rate fix and BPM wiring work correctly.


class TestBeatmatchedBlendProduction:
    """Regression tests for the _beatmatched_blend production function.

    Verifies that:
    1. The rate = source_bpm / target_bpm (not inverted).
    2. BPM is passed to calculate_phase_shift.
    3. The output improves beat alignment vs. no correction.
    """

    def test_rate_is_not_inverted(self):
        """Time-stretch rate must be source_bpm/target_bpm, not inverted.

        If inverted, the target would be stretched in the wrong direction,
        making the alignment worse instead of better.
        """
        sr = SR
        source_bpm = 117.5
        target_bpm = 123.0

        source = make_click_track(source_bpm, duration=5.0)
        target = make_click_track(target_bpm, duration=5.0)

        result = _beatmatched_blend(source, target, sr,
                                     source_bpm=source_bpm,
                                     target_bpm=target_bpm)

        # The result should have similar spectral content to the source
        # (because the target was stretched to match source BPM).
        # Use cross-correlation to check alignment.
        from djenius.utils.timing import _envelope
        src_env = _envelope(source, 512)
        res_env = _envelope(result, 512)

        # The cross-correlation peak should be near zero (well-aligned)
        correlation = scipy_signal.correlate(src_env, res_env, mode='full')
        lags = np.arange(-len(res_env) + 1, len(src_env))
        best_lag_frames = lags[np.argmax(correlation)]
        best_lag_samples = best_lag_frames * 512
        best_lag_ms = abs(best_lag_samples) / sr * 1000

        assert best_lag_ms < 50.0, (
            f"Rate inversion suspected: result is {best_lag_ms:.1f}ms off from source"
        )

    def test_blend_improves_alignment_vs_uncorrected(self):
        """The blended result should be better aligned than the raw target.

        This is the key regression test: if the rate or BPM wiring is wrong,
        the blend will be worse than doing nothing.
        """
        sr = SR
        source_bpm = 120.0
        target_bpm = 128.0

        source = make_click_track(source_bpm, duration=5.0)
        target = make_click_track(target_bpm, duration=5.0)

        # Blend with full production path
        result = _beatmatched_blend(source, target, sr,
                                     source_bpm=source_bpm,
                                     target_bpm=target_bpm)

        # Measure alignment of raw target vs source
        raw_shift = calculate_phase_shift(source, target, sr)
        raw_residual = abs(raw_shift) / sr * 1000

        # Measure alignment of result vs source
        result_shift = calculate_phase_shift(source, result, sr)
        result_residual = abs(result_shift) / sr * 1000

        # The result should be at least as good as the raw target,
        # and ideally much better.
        assert result_residual <= raw_residual + 10.0, (
            f"Blend ({result_residual:.1f}ms) is worse than raw ({raw_residual:.1f}ms)"
        )

    def test_same_bpm_no_stretch_needed(self):
        """When source and target have the same BPM, no time-stretch should occur."""
        sr = SR
        bpm = 120.0

        source = make_click_track(bpm, duration=5.0)
        # Create misaligned target (delayed by 100ms)
        offset_samp = int(sr * 0.1)
        target = np.zeros_like(source)
        target[offset_samp:] = source[:-offset_samp]

        result = _beatmatched_blend(source, target, sr,
                                     source_bpm=bpm,
                                     target_bpm=bpm)

        # The result should be well-aligned (within 20ms)
        from djenius.utils.timing import _envelope
        src_env = _envelope(source, 512)
        res_env = _envelope(result, 512)

        correlation = scipy_signal.correlate(src_env, res_env, mode='full')
        lags = np.arange(-len(res_env) + 1, len(src_env))
        best_lag_frames = lags[np.argmax(correlation)]
        best_lag_ms = abs(best_lag_frames * 512) / sr * 1000

        assert best_lag_ms < 20.0, (
            f"Same-BPM blend: result is {best_lag_ms:.1f}ms off (must be <20ms)"
        )
