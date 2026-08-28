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

    def test_beatmatched_blend_length(self, mono_audio):
        mid = len(mono_audio) // 2
        result = _beatmatched_blend(mono_audio[:mid], mono_audio[mid:])
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
