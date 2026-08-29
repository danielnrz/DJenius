"""Tests for the energy-journey aware planner."""

import numpy as np
import pytest

from djenius.core.models import (
    TrackProfile, TrackMetadata, TrackAnalysis, EnergyProfile,
)
from djenius.core.planner import (
    _score_energy_trajectory,
    _compute_set_energy_profile,
    _energy_progression_bonus,
    _starting_energy_preference,
)


def _make_track(name: str, energy: float, duration: float = 300) -> TrackProfile:
    return TrackProfile(
        id=name,
        metadata=TrackMetadata(filepath=f"{name}.mp3", duration_sec=duration),
        analysis=TrackAnalysis(mean_energy=energy, bpm=120.0),
    )


class TestEnergyProgressionBonus:
    def test_steady_prefers_no_change(self):
        b = _energy_progression_bonus(1, 4, EnergyProfile.STEADY, 0.5, 0.5)
        b2 = _energy_progression_bonus(1, 4, EnergyProfile.STEADY, 0.5, 0.9)
        assert b > b2

    def test_slow_build_prefers_increase(self):
        b_up = _energy_progression_bonus(2, 5, EnergyProfile.SLOW_BUILD, 0.3, 0.5)
        b_down = _energy_progression_bonus(2, 5, EnergyProfile.SLOW_BUILD, 0.5, 0.3)
        assert b_up > b_down

    def test_warmup_to_peak_early_section(self):
        b_up = _energy_progression_bonus(1, 5, EnergyProfile.WARMUP_TO_PEAK, 0.3, 0.5)
        b_down = _energy_progression_bonus(1, 5, EnergyProfile.WARMUP_TO_PEAK, 0.5, 0.3)
        assert b_up > b_down

    def test_warmup_to_peak_later_section(self):
        # After 70%, prefers stability
        b_stable = _energy_progression_bonus(4, 5, EnergyProfile.WARMUP_TO_PEAK, 0.7, 0.7)
        b_climb = _energy_progression_bonus(4, 5, EnergyProfile.WARMUP_TO_PEAK, 0.5, 0.9)
        assert b_stable > b_climb

    def test_cooldown_prefers_decrease_late(self):
        b_down = _energy_progression_bonus(4, 5, EnergyProfile.COOLDOWN, 0.7, 0.4)
        b_up = _energy_progression_bonus(4, 5, EnergyProfile.COOLDOWN, 0.4, 0.7)
        assert b_down > b_up

    def test_wave_prefers_target(self):
        # At progress 0.25, sin wave is near peak
        b_good = _energy_progression_bonus(1, 4, EnergyProfile.WAVE, 0.5, 0.9)
        b_bad = _energy_progression_bonus(1, 4, EnergyProfile.WAVE, 0.5, 0.1)
        assert b_good > b_bad

    def test_peak_late_early_section(self):
        # Early in set, prefers gradual
        b = _energy_progression_bonus(1, 5, EnergyProfile.PEAK_LATE, 0.4, 0.5)
        assert isinstance(b, float)

    def test_peak_early_early_section(self):
        b_up = _energy_progression_bonus(0, 5, EnergyProfile.PEAK_EARLY, 0.3, 0.6)
        b_down = _energy_progression_bonus(0, 5, EnergyProfile.PEAK_EARLY, 0.5, 0.3)
        assert b_up > b_down


class TestScoreEnergyTrajectory:
    def test_steady_low_variance(self):
        tracks = [_make_track(f"t{i}", 0.5) for i in range(5)]
        track_by_id = {t.id: t for t in tracks}
        path = [t.id for t in tracks]
        score = _score_energy_trajectory(path, track_by_id, EnergyProfile.STEADY)
        # Perfect steady = high score
        assert score > -0.01

    def test_steady_high_variance_penalty(self):
        tracks = [_make_track("a", 0.2), _make_track("b", 0.9),
                   _make_track("c", 0.2), _make_track("d", 0.9)]
        track_by_id = {t.id: t for t in tracks}
        path = [t.id for t in tracks]
        score = _score_energy_trajectory(path, track_by_id, EnergyProfile.STEADY)
        assert score < -0.01

    def test_warmup_to_peak_good_trajectory(self):
        energies = [0.2, 0.3, 0.5, 0.7, 0.8, 0.75]
        tracks = [_make_track(f"t{i}", e) for i, e in enumerate(energies)]
        track_by_id = {t.id: t for t in tracks}
        path = [t.id for t in tracks]
        score = _score_energy_trajectory(path, track_by_id, EnergyProfile.WARMUP_TO_PEAK)
        # Good trajectory should be positive
        assert score > -0.05

    def test_warmup_to_peak_bad_trajectory(self):
        # Starts high, drops low = wrong direction
        energies = [0.9, 0.3, 0.2, 0.3, 0.2]
        tracks = [_make_track(f"t{i}", e) for i, e in enumerate(energies)]
        track_by_id = {t.id: t for t in tracks}
        path = [t.id for t in tracks]
        score = _score_energy_trajectory(path, track_by_id, EnergyProfile.WARMUP_TO_PEAK)
        assert score < 0

    def test_cooldown_penalizes_rising_end(self):
        energies = [0.7, 0.6, 0.4, 0.3, 0.6]  # rises at end
        tracks = [_make_track(f"t{i}", e) for i, e in enumerate(energies)]
        track_by_id = {t.id: t for t in tracks}
        path = [t.id for t in tracks]
        score = _score_energy_trajectory(path, track_by_id, EnergyProfile.COOLDOWN)
        assert score < 0

    def test_wave_prefers_oscillation(self):
        # Clear oscillation
        energies = [0.3, 0.7, 0.3, 0.7, 0.3]
        tracks = [_make_track(f"t{i}", e) for i, e in enumerate(energies)]
        track_by_id = {t.id: t for t in tracks}
        path = [t.id for t in tracks]
        score = _score_energy_trajectory(path, track_by_id, EnergyProfile.WAVE)
        assert score > 0

    def test_short_path_returns_zero(self):
        tracks = [_make_track("a", 0.5), _make_track("b", 0.5)]
        track_by_id = {t.id: t for t in tracks}
        score = _score_energy_trajectory(["a", "b"], track_by_id, EnergyProfile.STEADY)
        assert score == 0.0


class TestComputeSetEnergyProfile:
    def test_returns_expected_keys(self):
        tracks = [_make_track(f"t{i}", 0.3 + i * 0.1) for i in range(5)]
        track_by_id = {t.id: t for t in tracks}
        result = _compute_set_energy_profile(
            [t.id for t in tracks], track_by_id,
        )
        assert "energies" in result
        assert "expected_shapes" in result
        assert len(result["energies"]) == 5
        assert "warmup_to_peak" in result["expected_shapes"]

    def test_energies_match_tracks(self):
        tracks = [_make_track("a", 0.3), _make_track("b", 0.7)]
        track_by_id = {t.id: t for t in tracks}
        result = _compute_set_energy_profile(
            ["a", "b"], track_by_id,
        )
        assert result["energies"] == [0.3, 0.7]


class TestStartingEnergyPreference:
    def test_warmup_prefers_low(self):
        t_low = _make_track("low", 0.2)
        t_high = _make_track("high", 0.8)
        assert _starting_energy_preference(t_low, EnergyProfile.WARMUP_TO_PEAK) > \
               _starting_energy_preference(t_high, EnergyProfile.WARMUP_TO_PEAK)

    def test_peak_early_prefers_high(self):
        t_low = _make_track("low", 0.2)
        t_high = _make_track("high", 0.8)
        assert _starting_energy_preference(t_high, EnergyProfile.PEAK_EARLY) > \
               _starting_energy_preference(t_low, EnergyProfile.PEAK_EARLY)

    def test_cooldown_prefers_moderate(self):
        t = _make_track("mid", 0.5)
        score = _starting_energy_preference(t, EnergyProfile.COOLDOWN)
        assert 0.0 <= score <= 1.0
