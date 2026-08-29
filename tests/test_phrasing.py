"""Tests for phrase and structural analysis (core/phrasing.py)."""

from __future__ import annotations

import math

import pytest

from djenius.core.phrasing import (
    PhraseBoundary,
    StructuralSection,
    build_bar_grid,
    compute_bar_energies,
    detect_bar_grouped_phrases,
    label_structural_sections,
    score_entry_point,
    score_exit_point,
    compute_transition_length_bars,
)


# ---------------------------------------------------------------------------
# build_bar_grid
# ---------------------------------------------------------------------------

class TestBuildBarGrid:
    def test_regular_grid(self):
        """Bar grid should be evenly spaced at bar duration."""
        bpm = 120.0  # 0.5s per beat, 2.0s per bar
        grid = build_bar_grid(beat_times=[0.0, 0.5, 1.0, 1.5], bpm=bpm, duration=10.0)
        assert len(grid) == 5  # bars at 0, 2, 4, 6, 8
        for i in range(len(grid) - 1):
            assert abs((grid[i + 1] - grid[i]) - 2.0) < 0.01

    def test_grid_uses_first_beat_as_phase(self):
        """First bar should be aligned to the first beat."""
        bpm = 120.0
        grid = build_bar_grid(beat_times=[1.0, 1.5, 2.0, 2.5], bpm=bpm, duration=7.0)
        assert len(grid) > 0
        assert abs(grid[0] - 1.0) < 0.01

    def test_empty_beats(self):
        """Should still produce a grid starting at 0."""
        grid = build_bar_grid(beat_times=[], bpm=120.0, duration=10.0)
        assert len(grid) == 5
        assert grid[0] == 0.0

    def test_zero_bpm(self):
        """Zero BPM should return empty grid."""
        assert build_bar_grid(beat_times=[0.0], bpm=0.0, duration=10.0) == []

    def test_zero_duration(self):
        """Zero duration should return empty grid."""
        assert build_bar_grid(beat_times=[0.0], bpm=120.0, duration=0.0) == []

    def test_negative_times_excluded(self):
        """Negative bar times should be excluded."""
        grid = build_bar_grid(beat_times=[-1.0], bpm=120.0, duration=5.0)
        assert all(t >= 0.0 for t in grid)


# ---------------------------------------------------------------------------
# compute_bar_energies
# ---------------------------------------------------------------------------

class TestComputeBarEnergies:
    def test_uniform_energy(self):
        """Uniform energy should produce uniform bar energies."""
        energy = [0.5] * 20
        bar_times = [0.0, 2.0, 4.0, 6.0]
        bpm = 120.0
        result = compute_bar_energies(energy, bar_times, bpm)
        assert len(result) == 4
        assert all(abs(v - 0.5) < 0.01 for v in result)

    def test_energy_curve_as_numpy(self):
        """Should work with numpy array input."""
        import numpy as np
        energy = np.ones(20) * 0.3
        bar_times = [0.0, 2.0, 4.0]
        result = compute_bar_energies(energy, bar_times, 120.0)
        assert len(result) == 3
        assert all(abs(v - 0.3) < 0.01 for v in result)

    def test_empty_inputs(self):
        """Empty inputs should return empty list."""
        assert compute_bar_energies([], [], 120.0) == []
        assert compute_bar_energies([0.5], [], 120.0) == []

    def test_zero_bpm(self):
        """Zero BPM should return empty list."""
        assert compute_bar_energies([0.5], [0.0], 0.0) == []

    def test_varied_energy(self):
        """Bar energies should reflect energy curve values."""
        # Energy curve: first half 0.2, second half 0.8
        energy = [0.2] * 5 + [0.8] * 5
        bar_times = [0.0, 5.0]  # bar at t=0 gets first 5 frames, bar at t=5 gets last 5
        # With bpm=120, bar_duration=2s. Resolution=1Hz means 1 frame per second
        # Bar at t=0: frames 0-1 (2 frames at 0.2)
        # Bar at t=5: frames 5-6 (2 frames at 0.8)
        result = compute_bar_energies(energy, bar_times, 120.0, resolution_hz=1.0)
        assert len(result) == 2
        assert result[0] < result[1]  # first bar lower energy


# ---------------------------------------------------------------------------
# detect_bar_grouped_phrases
# ---------------------------------------------------------------------------

class TestDetectBarGroupedPhrases:
    def _make_energy_profile(self, n_bars: int, pattern: str = "steady") -> list[float]:
        """Generate bar energies with a specific pattern."""
        if pattern == "steady":
            return [0.5] * n_bars
        elif pattern == "drop":
            return [0.7] * (n_bars // 2) + [0.3] * (n_bars - n_bars // 2)
        elif pattern == "build":
            return [i / n_bars for i in range(n_bars)]
        elif pattern == "alternating":
            return [0.7, 0.3] * (n_bars // 2 + 1)
        return [0.5] * n_bars

    def test_steady_energy_no_boundaries(self):
        """Steady energy should produce few or no boundaries."""
        bar_times = [i * 2.0 for i in range(16)]  # 16 bars at 120 BPM
        energies = self._make_energy_profile(16, "steady")
        boundaries = detect_bar_grouped_phrases(
            bar_times, energies, bpm=120.0,
            energy_change_threshold=0.15,
        )
        assert len(boundaries) == 0

    def test_energy_drop_detected(self):
        """A large energy drop should produce a phrase boundary."""
        bar_times = [i * 2.0 for i in range(16)]
        energies = self._make_energy_profile(16, "drop")
        boundaries = detect_bar_grouped_phrases(
            bar_times, energies, bpm=120.0,
            energy_change_threshold=0.15,
        )
        assert len(boundaries) >= 1
        # The drop happens at the midpoint
        assert boundaries[0].time_sec > 10.0

    def test_boundaries_sorted_by_time(self):
        """Boundaries should be returned sorted by time."""
        bar_times = [i * 2.0 for i in range(32)]
        # Create alternating high/low to get multiple boundaries
        energies = [0.7, 0.3] * 16
        boundaries = detect_bar_grouped_phrases(
            bar_times, energies, bpm=120.0,
            energy_change_threshold=0.15,
            min_phrase_bars=4,
        )
        times = [b.time_sec for b in boundaries]
        assert times == sorted(times)

    def test_min_spacing_respected(self):
        """Boundaries should respect minimum bar spacing."""
        bar_times = [i * 2.0 for i in range(32)]
        # Sharp alternation would give boundary at every bar
        energies = [0.8, 0.2, 0.8, 0.2, 0.8, 0.2] * 6
        boundaries = detect_bar_grouped_phrases(
            bar_times, energies, bpm=120.0,
            energy_change_threshold=0.15,
            min_phrase_bars=8,
        )
        for i in range(len(boundaries) - 1):
            assert boundaries[i + 1].bar_index - boundaries[i].bar_index >= 8

    def test_empty_inputs(self):
        """Empty bar times should return empty list."""
        assert detect_bar_grouped_phrases([], [], 120.0) == []

    def test_too_few_bars(self):
        """Fewer than 3 bars should return empty list."""
        bar_times = [0.0, 2.0]
        energies = [0.5, 0.3]
        assert detect_bar_grouped_phrases(bar_times, energies, 120.0) == []

    def test_confidence_range(self):
        """Confidence should be between 0 and 1."""
        bar_times = [i * 2.0 for i in range(32)]
        energies = [0.8, 0.2] * 16
        boundaries = detect_bar_grouped_phrases(
            bar_times, energies, bpm=120.0,
            energy_change_threshold=0.15,
            min_phrase_bars=8,
        )
        for b in boundaries:
            assert 0.0 <= b.confidence <= 1.0


# ---------------------------------------------------------------------------
# label_structural_sections
# ---------------------------------------------------------------------------

class TestLabelStructuralSections:
    def test_intro_and_outro_labeled(self):
        """Low-energy start/end should be labeled intro/outro."""
        bar_times = [i * 2.0 for i in range(20)]
        # Low energy at start and end, high in middle
        energies = [0.2] * 5 + [0.7] * 10 + [0.2] * 5
        boundaries = [
            PhraseBoundary(time_sec=10.0, bar_index=5, confidence=0.8, energy_change=0.5),
            PhraseBoundary(time_sec=30.0, bar_index=15, confidence=0.8, energy_change=0.5),
        ]
        sections = label_structural_sections(bar_times, energies, boundaries, duration=40.0)
        assert len(sections) >= 2
        assert sections[0].label == "intro"
        assert sections[-1].label == "outro"

    def test_section_energy_levels(self):
        """Sections should have meaningful energy levels."""
        bar_times = [i * 2.0 for i in range(12)]
        energies = [0.3] * 4 + [0.8] * 4 + [0.3] * 4
        sections = label_structural_sections(bar_times, energies, [], duration=24.0)
        for s in sections:
            assert 0.0 <= s.energy_level <= 1.0

    def test_empty_inputs(self):
        """Empty inputs should return empty list."""
        assert label_structural_sections([], [], [], 10.0) == []

    def test_sections_cover_full_duration(self):
        """Sections should span from 0 to duration."""
        bar_times = [i * 2.0 for i in range(16)]
        energies = [0.5] * 16
        sections = label_structural_sections(bar_times, energies, [], duration=32.0)
        assert len(sections) >= 1
        assert sections[0].start_sec == 0.0
        assert sections[-1].end_sec == 32.0


# ---------------------------------------------------------------------------
# score_entry_point / score_exit_point
# ---------------------------------------------------------------------------

class TestScoreEntryPoint:
    def _make_bar_data(self, n_bars: int, bpm: float = 120.0):
        bar_times = [i * (4 * 60.0 / bpm) for i in range(n_bars)]
        bar_energies = [0.5] * n_bars
        return bar_times, bar_energies

    def test_before_intro_is_zero(self):
        """Entry before intro end should score 0."""
        bar_times, bar_energies = self._make_bar_data(10, 120.0)
        assert score_entry_point(0.0, bar_times, bar_energies, intro_end=4.0, duration=120.0, bpm=120.0) == 0.0

    def test_after_duration_is_zero(self):
        """Entry at or after duration should score 0."""
        bar_times, bar_energies = self._make_bar_data(10, 120.0)
        assert score_entry_point(120.0, bar_times, bar_energies, intro_end=0.0, duration=120.0, bpm=120.0) == 0.0

    def test_reasonable_entry_scores_positive(self):
        """Entry after intro on a bar boundary should score well."""
        bpm = 120.0
        bar_times, bar_energies = self._make_bar_data(20, bpm)
        bar_duration = 4 * 60.0 / bpm
        # Entry at bar 4 (after intro of 2 bars)
        time_sec = bar_times[4]
        intro_end = bar_times[2]
        score = score_entry_point(time_sec, bar_times, bar_energies, intro_end, 240.0, bpm)
        assert score > 0.5

    def test_score_range(self):
        """Score should be between 0 and 1."""
        bar_times, bar_energies = self._make_bar_data(10, 120.0)
        score = score_entry_point(10.0, bar_times, bar_energies, 4.0, 120.0, 120.0)
        assert 0.0 <= score <= 1.0


class TestScoreExitPoint:
    def _make_bar_data(self, n_bars: int, bpm: float = 120.0):
        bar_times = [i * (4 * 60.0 / bpm) for i in range(n_bars)]
        bar_energies = [0.5] * n_bars
        return bar_times, bar_energies

    def test_exit_at_start_is_low(self):
        """Exit near the start should score low."""
        bar_times, bar_energies = self._make_bar_data(10, 120.0)
        score = score_exit_point(0.0, bar_times, bar_energies, outro_start=80.0, duration=120.0, bpm=120.0)
        assert score < 0.5

    def test_exit_in_outro_scores_high(self):
        """Exit in the outro region should score well."""
        bpm = 120.0
        bar_times, bar_energies = self._make_bar_data(20, bpm)
        outro_start = bar_times[14]
        time_sec = bar_times[16]
        score = score_exit_point(time_sec, bar_times, bar_energies, outro_start, 240.0, bpm)
        assert score > 0.5

    def test_exit_at_end_is_zero(self):
        """Exit at the very end should score 0."""
        bar_times, bar_energies = self._make_bar_data(10, 120.0)
        score = score_exit_point(120.0, bar_times, bar_energies, outro_start=80.0, duration=120.0, bpm=120.0)
        assert score == 0.0

    def test_energy_drop_bonus(self):
        """An energy drop at exit should boost the score."""
        bar_times = [i * 2.0 for i in range(20)]
        energies = [0.5] * 18 + [0.8, 0.3]  # big drop at bar 19
        # Exit at bar 18 where there's a drop
        score = score_exit_point(
            bar_times[18], bar_times, energies,
            outro_start=20.0, duration=40.0, bpm=120.0,
        )
        assert score > 0.3  # should get some bonus


# ---------------------------------------------------------------------------
# compute_transition_length_bars
# ---------------------------------------------------------------------------

class TestComputeTransitionLengthBars:
    def test_high_scores_long_transition(self):
        """High scores should produce long transitions."""
        bars = compute_transition_length_bars(0.9, 0.8, 120.0)
        assert bars == 16

    def test_low_scores_short_transition(self):
        """Low scores should produce short transitions."""
        bars = compute_transition_length_bars(0.2, 0.3, 120.0)
        assert bars == 4

    def test_mid_scores_medium_transition(self):
        """Medium scores should produce medium transitions."""
        bars = compute_transition_length_bars(0.6, 0.5, 120.0)
        assert bars in (8, 12)

    def test_result_is_even(self):
        """Result should always be even."""
        for s1 in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for s2 in [0.1, 0.3, 0.5, 0.7, 0.9]:
                bars = compute_transition_length_bars(s1, s2, 120.0)
                assert bars % 2 == 0

    def test_result_in_range(self):
        """Result should be between min and max bars."""
        bars = compute_transition_length_bars(0.0, 0.0, 120.0)
        assert 4 <= bars <= 16
        bars = compute_transition_length_bars(1.0, 1.0, 120.0)
        assert 4 <= bars <= 16

    def test_mashup_high_scores_get_24_bars(self):
        """With max_bars=24 and very high scores, should return 24 bars."""
        bars = compute_transition_length_bars(0.95, 0.90, 120.0, max_bars=24)
        assert bars == 24

    def test_mashup_medium_scores_get_20_bars(self):
        """With max_bars=24 and good scores, should return 20 bars."""
        bars = compute_transition_length_bars(0.85, 0.80, 120.0, max_bars=24)
        assert bars == 20

    def test_default_max_bars_caps_at_16(self):
        """Without extended max_bars, high scores still cap at 16."""
        bars = compute_transition_length_bars(0.95, 0.95, 120.0, max_bars=16)
        assert bars == 16
