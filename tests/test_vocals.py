"""Tests for the vocal activity heuristic module."""

import numpy as np
import pytest

from djenius.audio.vocals import (
    estimate_vocal_regions,
    score_vocal_overlap,
    suggest_vocal_safe_exit,
    _time_in_regions,
    _merge_close_regions,
    _frames_to_regions,
)


class TestEstimateVocalRegions:
    """Tests for vocal region estimation."""

    def test_silence_no_vocals(self):
        sr = 22050
        y = np.zeros(sr * 5, dtype=np.float32)
        regions = estimate_vocal_regions(y, sr)
        assert regions == []

    def test_empty_audio(self):
        regions = estimate_vocal_regions(np.array([]), 22050)
        assert regions == []

    def test_returns_list_of_tuples(self):
        sr = 22050
        y = np.random.randn(sr * 10).astype(np.float32)
        regions = estimate_vocal_regions(y, sr)
        assert isinstance(regions, list)
        for r in regions:
            assert isinstance(r, tuple)
            assert len(r) == 2
            assert r[0] < r[1]

    def test_vocal_content_detected(self):
        sr = 22050
        duration = 5
        n = sr * duration
        t = np.linspace(0, duration, n, dtype=np.float32)
        # Simulate vocal-like signal: harmonic series in vocal band
        vocal = np.zeros(n, dtype=np.float32)
        for f in [300, 600, 900, 1200]:
            vocal += (0.3 * np.sin(2 * np.pi * f * t)).astype(np.float32)
        # Add vocal only in middle 2 seconds
        y = np.zeros(n, dtype=np.float32)
        start = sr * 2
        end = sr * 3
        y[start:end] = vocal[start:end]

        regions = estimate_vocal_regions(y, sr, threshold=0.3)
        # Should detect some vocal activity in the 2-3s range
        assert len(regions) > 0
        # At least one region should overlap with 2-3s
        has_overlap = any(
            end >= 2.0 and start <= 3.0 for start, end in regions
        )
        assert has_overlap

    def test_stereo_input(self):
        sr = 22050
        mono = np.random.randn(sr * 5).astype(np.float32)
        stereo = np.column_stack([mono, mono * 0.9])
        regions = estimate_vocal_regions(stereo, sr)
        assert isinstance(regions, list)


class TestScoreVocalOverlap:
    """Tests for vocal overlap scoring."""

    def test_no_vocals_safe(self):
        score = score_vocal_overlap([], [], 0.0, 0.0, 8.0)
        assert score == 1.0

    def test_zero_overlap_safe(self):
        regions = [(0.0, 2.0)]
        score = score_vocal_overlap(regions, [], 10.0, 0.0, 8.0)
        assert score == 1.0

    def test_both_vocal_clash(self):
        src_vocals = [(0.0, 20.0)]
        tgt_vocals = [(0.0, 20.0)]
        score = score_vocal_overlap(src_vocals, tgt_vocals, 5.0, 0.0, 8.0)
        assert score <= 0.6  # High clash risk

    def test_one_vocal_one_instrumental(self):
        src_vocals = [(0.0, 20.0)]
        score = score_vocal_overlap(src_vocals, [], 5.0, 0.0, 8.0)
        assert score >= 0.7  # Moderate to safe

    def test_short_overlap(self):
        score = score_vocal_overlap([(0, 2)], [(0, 2)], 5.0, 5.0, 1.0)
        # 1-second overlap with vocals in both = some risk
        assert 0.0 <= score <= 1.0


class TestSuggestVocalSafeExit:
    """Tests for vocal-safe exit suggestions."""

    def test_no_vocals_uses_default(self):
        exits = suggest_vocal_safe_exit([], 300.0)
        assert len(exits) > 0
        assert all(0 <= t <= 300 for t in exits)

    def test_prefers_after_vocals(self):
        vocals = [(30.0, 60.0), (90.0, 120.0)]
        exits = suggest_vocal_safe_exit(vocals, 300.0)
        assert len(exits) > 0
        # First suggested exit should be after the last vocal phrase
        assert exits[0] >= 120.0

    def test_avoids_mid_vocal(self):
        vocals = [(50.0, 100.0)]
        exits = suggest_vocal_safe_exit(vocals, 300.0)
        # No exit should be in the middle of the vocal region
        for t in exits:
            assert not (50.0 < t < 100.0), f"Exit {t} is in vocal region"


class TestTimeInRegions:
    """Tests for time-in-regions computation."""

    def test_no_overlap(self):
        t = _time_in_regions(5.0, 10.0, [(0.0, 2.0)])
        assert t == 0.0

    def test_full_overlap(self):
        t = _time_in_regions(5.0, 10.0, [(3.0, 12.0)])
        assert t == pytest.approx(5.0)

    def test_partial_overlap(self):
        t = _time_in_regions(5.0, 10.0, [(3.0, 7.0)])
        assert t == pytest.approx(2.0)

    def test_multiple_regions(self):
        regions = [(0.0, 3.0), (6.0, 12.0)]
        t = _time_in_regions(2.0, 8.0, regions)
        assert t == pytest.approx(3.0)  # 2-3 + 6-8


class TestMergeCloseRegions:
    def test_merge(self):
        regions = [(0.0, 1.0), (1.2, 2.0), (3.0, 4.0)]
        merged = _merge_close_regions(regions, min_gap_sec=0.5)
        assert len(merged) == 2
        assert merged[0] == (0.0, 2.0)
        assert merged[1] == (3.0, 4.0)

    def test_no_merge(self):
        regions = [(0.0, 1.0), (5.0, 6.0)]
        merged = _merge_close_regions(regions, min_gap_sec=0.5)
        assert len(merged) == 2

    def test_empty(self):
        assert _merge_close_regions([], 0.5) == []


class TestFramesToRegions:
    def test_basic(self):
        is_active = np.array([False, True, True, False, True, True, True])
        regions = _frames_to_regions(is_active, 1000, 1)
        # Each frame = 1/1000 sec
        assert regions == [(0.001, 0.003), (0.004, 0.007)]

    def test_all_active(self):
        is_active = np.array([True, True, True])
        regions = _frames_to_regions(is_active, 1000, 1)
        assert len(regions) == 1
        assert regions[0] == (0.0, 0.003)

    def test_none_active(self):
        is_active = np.array([False, False])
        regions = _frames_to_regions(is_active, 1000, 1)
        assert regions == []
