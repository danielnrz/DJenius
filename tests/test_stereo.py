"""Tests for stereo preservation throughout the rendering pipeline.

Verifies that stereo audio is preserved end-to-end, not converted to mono.
"""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf
from pathlib import Path

from djenius.audio.transitions import apply_transition
from djenius.audio.renderer import _load_audio, _to_stereo


@pytest.fixture
def sr():
    return 44100


@pytest.fixture
def stereo_audio_2ch(sr):
    """Create 2-channel stereo audio with different L/R content."""
    duration = 2.0
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False, dtype=np.float32)
    left = 0.3 * np.sin(2 * np.pi * 440 * t)   # 440Hz left
    right = 0.3 * np.sin(2 * np.pi * 460 * t)  # 460Hz right
    return np.column_stack([left, right]).astype(np.float32)


@pytest.fixture
def mono_audio_1ch(sr):
    """Create 1-channel mono audio."""
    duration = 2.0
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False, dtype=np.float32)
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class TestStereoTransitions:
    """Test that transitions preserve stereo channels."""

    def test_crossfade_stereo_preserves_shape(self, stereo_audio_2ch, sr):
        """Crossfade should output 2 channels if input is stereo."""
        n = len(stereo_audio_2ch)
        mid = n // 2
        source = stereo_audio_2ch[:mid]
        target = stereo_audio_2ch[mid:]
        result = apply_transition(
            source, target, sr, "crossfade", mid, 0, 0,
        )
        assert result.ndim == 2, f"Expected 2D stereo output, got {result.ndim}D"
        assert result.shape[1] == 2, f"Expected 2 channels, got {result.shape[1]}"

    def test_phrase_cut_stereo_preserves_shape(self, stereo_audio_2ch, sr):
        n = len(stereo_audio_2ch)
        mid = n // 2
        source = stereo_audio_2ch[:mid]
        target = stereo_audio_2ch[mid:]
        result = apply_transition(
            source, target, sr, "phrase_cut", mid, 0, 0,
        )
        assert result.ndim == 2
        assert result.shape[1] == 2

    def test_bass_swap_stereo_preserves_shape(self, stereo_audio_2ch, sr):
        n = len(stereo_audio_2ch)
        mid = n // 2
        source = stereo_audio_2ch[:mid]
        target = stereo_audio_2ch[mid:]
        result = apply_transition(
            source, target, sr, "bass_swap", mid, 0, 0,
        )
        assert result.ndim == 2
        assert result.shape[1] == 2

    def test_filter_sweep_stereo_preserves_shape(self, stereo_audio_2ch, sr):
        n = len(stereo_audio_2ch)
        mid = n // 2
        source = stereo_audio_2ch[:mid]
        target = stereo_audio_2ch[mid:]
        result = apply_transition(
            source, target, sr, "filter_sweep", mid, 0, 0,
        )
        assert result.ndim == 2
        assert result.shape[1] == 2

    def test_echo_out_stereo_preserves_shape(self, stereo_audio_2ch, sr):
        n = len(stereo_audio_2ch)
        mid = n // 2
        source = stereo_audio_2ch[:mid]
        target = stereo_audio_2ch[mid:]
        result = apply_transition(
            source, target, sr, "echo_out", mid, 0, 0,
        )
        assert result.ndim == 2
        assert result.shape[1] == 2

    def test_stereo_content_differs_per_channel(self, sr):
        """Left and right channels should remain different after transition."""
        duration = 1.0
        n = int(sr * duration)
        t = np.linspace(0, duration, n, endpoint=False, dtype=np.float32)
        # Distinct L/R frequencies
        left = 0.3 * np.sin(2 * np.pi * 200 * t)   # Low freq left
        right = 0.3 * np.sin(2 * np.pi * 8000 * t)  # High freq right
        stereo = np.column_stack([left, right]).astype(np.float32)

        result = apply_transition(stereo, stereo, sr, "crossfade", n, 0, 0)

        # L and R should not be identical (they started with different content)
        left_result = result[:, 0]
        right_result = result[:, 1]
        correlation = np.corrcoef(left_result, right_result)[0, 1]
        assert correlation < 0.99, f"L/R channels should differ, got correlation {correlation}"

    def test_mono_input_still_works(self, mono_audio_1ch, sr):
        """Mono input should produce mono output."""
        n = len(mono_audio_1ch)
        result = apply_transition(
            mono_audio_1ch, mono_audio_1ch, sr, "crossfade", n, 0, 0,
        )
        assert result.ndim == 1 or result.shape[1] == 1


class TestStereoLoading:
    """Test that audio loading preserves channel count."""

    def test_load_stereo_wav(self, tmp_path, stereo_audio_2ch, sr):
        """Loading a stereo WAV should return 2-channel audio."""
        path = tmp_path / "stereo_test.wav"
        sf.write(str(path), stereo_audio_2ch, sr, subtype="PCM_16")

        audio, loaded_sr = _load_audio(str(path), sr)
        assert loaded_sr == sr
        assert audio.ndim == 2, f"Expected 2D stereo, got {audio.ndim}D"
        assert audio.shape[1] == 2, f"Expected 2 channels, got {audio.shape[1]}"

    def test_load_mono_wav(self, tmp_path, mono_audio_1ch, sr):
        """Loading a mono WAV should return 1D mono."""
        path = tmp_path / "mono_test.wav"
        sf.write(str(path), mono_audio_1ch, sr, subtype="PCM_16")

        audio, loaded_sr = _load_audio(str(path), sr)
        assert loaded_sr == sr
        # Mono can be 1D or 2D with 1 channel
        if audio.ndim == 2:
            assert audio.shape[1] == 1


class TestStereoConversion:
    """Test _to_stereo utility function."""

    def test_mono_to_stereo(self, sr):
        """Converting mono to stereo should duplicate the channel."""
        mono = np.sin(np.linspace(0, 1, sr, dtype=np.float32))
        stereo = _to_stereo(mono)
        assert stereo.ndim == 2
        assert stereo.shape[1] == 2
        # Both channels should be identical
        np.testing.assert_array_equal(stereo[:, 0], stereo[:, 1])

    def test_stereo_passthrough(self, stereo_audio_2ch):
        """Stereo input should pass through correctly."""
        result = _to_stereo(stereo_audio_2ch)
        assert result.ndim == 2
        assert result.shape[1] == 2
        np.testing.assert_array_equal(result, stereo_audio_2ch)


class TestStereoRoundTrip:
    """Integration test: stereo through full transition pipeline."""

    def test_full_transition_stereo_preserved(self, sr):
        """Two stereo tracks through a crossfade should remain stereo."""
        duration = 3.0
        n = int(sr * duration)
        t = np.linspace(0, duration, n, endpoint=False, dtype=np.float32)

        # Track 1: low frequency stereo
        left1 = 0.3 * np.sin(2 * np.pi * 200 * t)
        right1 = 0.3 * np.sin(2 * np.pi * 210 * t)
        source = np.column_stack([left1, right1]).astype(np.float32)

        # Track 2: high frequency stereo
        left2 = 0.3 * np.sin(2 * np.pi * 1000 * t)
        right2 = 0.3 * np.sin(2 * np.pi * 1100 * t)
        target = np.column_stack([left2, right2]).astype(np.float32)

        # Apply transition at 1 second mark
        overlap_samples = sr * 2  # 2 second overlap
        source_exit = sr          # Exit at 1 second
        target_entry = sr         # Enter at 1 second

        result = apply_transition(
            source, target, sr, "crossfade",
            overlap_samples, source_exit, target_entry,
        )

        assert result.ndim == 2, f"Expected 2D stereo output, got {result.ndim}D"
        assert result.shape[1] == 2, f"Expected 2 channels, got {result.shape[1]}"
        assert result.shape[0] > 0, "Output should not be empty"
        assert np.all(np.isfinite(result)), "Output should have no NaN/inf"

        # Check that stereo separation is maintained
        left_out = result[:, 0]
        right_out = result[:, 1]
        # They should not be identical since inputs were different
        assert not np.allclose(left_out, right_out, atol=1e-6), \
            "Left and right channels should remain distinct"
