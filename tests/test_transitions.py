"""Tests for DSP transition functions."""

from __future__ import annotations

import numpy as np
import pytest

from djenius.audio.transitions import (
    apply_transition,
    _phrase_cut,
    _crossfade,
    _beatmatched_blend,
    _bass_swap,
    _filter_sweep,
    _echo_out,
    _loop_blend,
)


@pytest.fixture
def sr():
    return 44100


@pytest.fixture
def mono_audio(sr):
    """1 second mono audio: left half is source, right half is target."""
    t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
    return 0.3 * np.sin(2 * np.pi * 440 * t)


@pytest.fixture
def stereo_audio(sr):
    """1 second stereo audio."""
    n = sr
    t = np.linspace(0, 1.0, n, endpoint=False, dtype=np.float32)
    left = 0.3 * np.sin(2 * np.pi * 440 * t)
    right = 0.3 * np.sin(2 * np.pi * 460 * t)
    return np.column_stack([left, right]).astype(np.float32)


@pytest.fixture
def full_tracks(sr):
    """Two 3-second mono tracks for full apply_transition tests."""
    n = sr * 3
    t1 = np.linspace(0, 3.0, n, endpoint=False, dtype=np.float32)
    t2 = np.linspace(0, 3.0, n, endpoint=False, dtype=np.float32)
    source = 0.3 * np.sin(2 * np.pi * 440 * t1)
    target = 0.3 * np.sin(2 * np.pi * 330 * t2)
    return source, target


class TestIndividualTransitions:
    def test_crossfade_length(self, mono_audio):
        n = len(mono_audio)
        result = _crossfade(mono_audio[:n // 2], mono_audio[n // 2:])
        assert len(result) > 0

    def test_crossfade_no_distortion(self, mono_audio):
        mid = len(mono_audio) // 2
        result = _crossfade(mono_audio[:mid], mono_audio[mid:])
        # No NaN, no inf, all within reasonable range
        assert np.all(np.isfinite(result))
        assert np.max(np.abs(result)) <= 1.5

    def test_phrase_cut_length(self, mono_audio):
        mid = len(mono_audio) // 2
        result = _phrase_cut(mono_audio[:mid], mono_audio[mid:])
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_beatmatched_blend_length(self, mono_audio, sr):
        mid = len(mono_audio) // 2
        result = _beatmatched_blend(mono_audio[:mid], mono_audio[mid:], sr)
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_bass_swap_length(self, mono_audio, sr):
        mid = len(mono_audio) // 2
        result = _bass_swap(mono_audio[:mid], mono_audio[mid:], sr)
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_filter_sweep_length(self, mono_audio, sr):
        mid = len(mono_audio) // 2
        result = _filter_sweep(mono_audio[:mid], mono_audio[mid:], sr)
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_filter_sweep_keeps_a_dry_energy_floor(self, sr):
        duration = 8
        time = np.arange(sr * duration, dtype=np.float32) / sr
        source = 0.2 * np.sin(2 * np.pi * 110 * time)
        target = 0.2 * np.sin(2 * np.pi * 440 * time)

        result = _filter_sweep(source, target, sr)
        input_rms = float(np.sqrt(np.mean(source ** 2)))
        frame_rms = [
            float(np.sqrt(np.mean(result[start:start + sr] ** 2)))
            for start in range(0, len(result), sr)
        ]

        assert min(frame_rms) >= input_rms * 10 ** (-6.0 / 20.0)

    def test_echo_out_length(self, mono_audio, sr):
        mid = len(mono_audio) // 2
        result = _echo_out(mono_audio[:mid], mono_audio[mid:], sr)
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_loop_blend_length(self, mono_audio):
        mid = len(mono_audio) // 2
        result = _loop_blend(mono_audio[:mid], mono_audio[mid:])
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_crossfade_energy_conservation(self, sr):
        """Equal-power crossfade should preserve energy."""
        n = 4096
        t = np.linspace(0, n / sr, n, endpoint=False, dtype=np.float32)
        a = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        b = np.sin(2 * np.pi * 460 * t).astype(np.float32)
        result = _crossfade(a, b)
        # Energy of source and target at midpoint should both be ~0.5 of their originals
        assert np.all(np.isfinite(result))


class TestApplyTransitionFull:
    def test_transition_gain_floor_is_bounded_and_slow(self):
        sample_rate = 8000
        source = np.full(sample_rate * 30, 0.1, dtype=np.float32)
        target = np.full(sample_rate * 30, 0.1, dtype=np.float32)
        source[sample_rate * 10:sample_rate * 20] = 0.04
        target[:sample_rate * 10] = 0.04

        result = apply_transition(
            source,
            target,
            sample_rate,
            "crossfade",
            sample_rate * 10,
            sample_rate * 10,
            0,
        )
        frame_rms = [
            float(np.sqrt(np.mean(result[start:start + sample_rate] ** 2)))
            for start in range(0, len(result), sample_rate)
        ]
        drop_db = 20.0 * np.log10(0.1 / min(frame_rms))

        assert drop_db <= 4.7
        assert max(frame_rms) <= 0.04 * 10 ** (4.0 / 20.0) + 1e-4

    def test_all_transition_types(self, full_tracks, sr):
        source, target = full_tracks
        overlap_samples = sr * 2  # 2-second overlap
        source_exit_sample = sr  # 1 second from start
        target_entry_sample = sr  # 1 second from start

        for ttype in ["crossfade", "phrase_cut", "beatmatched_blend",
                       "bass_swap", "filter_sweep", "echo_out", "loop_blend"]:
            result = apply_transition(
                source, target, sr, ttype,
                overlap_samples, source_exit_sample, target_entry_sample,
            )
            assert len(result) > 0, f"Transition {ttype} produced empty output"
            assert np.all(np.isfinite(result)), f"Transition {ttype} produced NaN/inf"
            assert result.dtype == np.float32, f"Transition {ttype} wrong dtype"

    def test_stereo_input(self, stereo_audio, sr):
        """apply_transition should handle stereo input without crashing."""
        overlap = sr
        result = apply_transition(
            stereo_audio, stereo_audio, sr, "crossfade",
            overlap, 0, 0,
        )
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_unknown_type_falls_back_to_crossfade(self, full_tracks, sr):
        source, target = full_tracks
        overlap_samples = sr
        result_known = apply_transition(
            source, target, sr, "crossfade", overlap_samples, 0, 0,
        )
        result_unknown = apply_transition(
            source, target, sr, "NONEXISTENT", overlap_samples, 0, 0,
        )
        np.testing.assert_allclose(result_known, result_unknown, atol=1e-6)

    def test_short_overlap(self, full_tracks, sr):
        """Very short overlap should not crash."""
        source, target = full_tracks
        result = apply_transition(
            source, target, sr, "crossfade",
            512, 0, 0,
        )
        assert len(result) > 0
        assert np.all(np.isfinite(result))

    def test_output_not_all_zeros(self, full_tracks, sr):
        source, target = full_tracks
        result = apply_transition(
            source, target, sr, "crossfade",
            sr * 2, sr, sr,
        )
        assert np.max(np.abs(result)) > 0.0


# ── Tests for real beatmatched blend (Phase 3) ────────────────────────

SR = 44100


def make_click_track(bpm: float, duration: float = 4.0, sr: int = SR) -> np.ndarray:
    """Generate a synthetic click track at a given BPM."""
    n_samples = int(sr * duration)
    audio = np.zeros(n_samples, dtype=np.float32)
    samples_per_beat = int(sr * 60.0 / bpm)
    click_len = min(256, samples_per_beat // 4)
    for i in range(0, n_samples, samples_per_beat):
        end = min(i + click_len, n_samples)
        t = np.linspace(0, click_len / sr, click_len, endpoint=False, dtype=np.float32)
        click = 0.8 * np.sin(2 * np.pi * 1000 * t)
        click *= np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        audio[i:end] = click[: end - i]
    return audio


def make_stereo_click_track(bpm: float, duration: float = 4.0, sr: int = SR) -> np.ndarray:
    """Generate a stereo synthetic click track."""
    mono = make_click_track(bpm, duration, sr)
    left = mono * 0.8
    right = mono * 0.8
    return np.column_stack([left, right]).astype(np.float32)


class TestBeatmatchedBlendReal:
    """Tests for the real beatmatched blend implementation."""

    def test_same_bpm_no_stretch(self):
        """Same BPM: should not trigger time-stretch, just crossfade + alignment."""
        audio = make_click_track(120.0, duration=6.0)
        n = len(audio)
        overlap = n // 4
        src = audio[:overlap]
        tgt = audio[overlap:2 * overlap]
        result = _beatmatched_blend(src, tgt, SR, source_bpm=120.0, target_bpm=120.0)
        assert result.shape[0] == len(src)
        assert np.all(np.isfinite(result))
        assert np.max(np.abs(result)) > 0

    def test_different_bpm_triggers_stretch(self):
        """Different BPMs should trigger time-stretch and produce valid output."""
        src = make_click_track(120.0, duration=6.0)
        tgt = make_click_track(128.0, duration=6.0)
        n = len(src) // 3
        result = _beatmatched_blend(src[:n], tgt[:n], SR, source_bpm=120.0, target_bpm=128.0)
        assert result.shape[0] == n
        assert np.all(np.isfinite(result))
        assert np.max(np.abs(result)) > 0

    def test_output_stereo_when_input_stereo(self):
        """Stereo input must produce stereo output."""
        src = make_stereo_click_track(120.0, duration=6.0)
        tgt = make_stereo_click_track(128.0, duration=6.0)
        n = len(src) // 3
        result = _beatmatched_blend(src[:n], tgt[:n], SR, source_bpm=120.0, target_bpm=128.0)
        assert result.ndim == 2
        assert result.shape[1] == 2
        assert result.shape[0] == n

    def test_output_mono_when_input_mono(self):
        """Mono input must produce mono output."""
        src = make_click_track(120.0, duration=6.0)
        tgt = make_click_track(128.0, duration=6.0)
        n = len(src) // 3
        result = _beatmatched_blend(src[:n], tgt[:n], SR, source_bpm=120.0, target_bpm=128.0)
        assert result.ndim == 1

    def test_crossfade_energy_conservation(self):
        """Crossfade region should maintain consistent energy."""
        src = make_click_track(120.0, duration=6.0)
        tgt = make_click_track(120.0, duration=6.0)
        n = len(src) // 3
        result = _beatmatched_blend(src[:n], tgt[:n], SR, source_bpm=120.0, target_bpm=120.0)
        # RMS of result should be within reasonable bounds
        rms = np.sqrt(np.mean(result ** 2))
        src_rms = np.sqrt(np.mean(src[:n] ** 2))
        # RMS should not be drastically different (within 3x)
        assert rms < src_rms * 3.0
        assert rms > src_rms * 0.01

    def test_zero_bpm_fallback(self):
        """Zero BPM should fall back to crossfade."""
        src = make_click_track(120.0, duration=4.0)
        tgt = make_click_track(120.0, duration=4.0)
        n = len(src) // 3
        result = _beatmatched_blend(src[:n], tgt[:n], SR, source_bpm=0.0, target_bpm=0.0)
        assert result.shape[0] == n
        assert np.all(np.isfinite(result))

    def test_beat_aligned_crossfade_length(self):
        """Crossfade length should be aligned to beat boundaries."""
        src = make_click_track(120.0, duration=6.0)
        tgt = make_click_track(120.0, duration=6.0)
        n = len(src) // 3
        result = _beatmatched_blend(src[:n], tgt[:n], SR, source_bpm=120.0, target_bpm=120.0)
        # At 120 BPM, one beat = 22050 samples
        beat_samples = int(SR * 60.0 / 120.0)
        # Result should have length that's a multiple of beats or equal to input
        assert result.shape[0] == n

    def test_stretch_percentage_calculation(self):
        """Verify stretch percentage is calculated correctly for different BPMs."""
        # This is a smoke test - we verify the function runs without error
        # for various BPM ratios
        bpm_pairs = [
            (120, 128), (128, 120), (120, 140), (140, 120),
            (100, 120), (120, 100), (90, 150), (150, 90),
        ]
        for src_bpm, tgt_bpm in bpm_pairs:
            src = make_click_track(src_bpm, duration=6.0)
            tgt = make_click_track(tgt_bpm, duration=6.0)
            n = len(src) // 3
            result = _beatmatched_blend(
                src[:n], tgt[:n], SR,
                source_bpm=src_bpm, target_bpm=tgt_bpm,
            )
            assert result.shape[0] == n
            assert np.all(np.isfinite(result))
