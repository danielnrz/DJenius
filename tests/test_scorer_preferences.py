"""Tests for V5 preference bonuses in scorer."""

import pytest
from djenius.core.intent import make_intent
from djenius.core.models import (
    TrackProfile, CompatibilityScore, TrackMetadata, TrackAnalysis,
)
from djenius.core.scorer import (
    score_compatibility, score_with_preferences,
    PreferenceBonuses, compute_preference_bonuses,
)


def make_mock_track(
    name: str = "test",
    bpm: float = 120.0,
    camelot: str = "8A",
    energy: float = 0.5,
    duration: float = 240.0,
) -> TrackProfile:
    return TrackProfile(
        id=name,
        metadata=TrackMetadata(
            filepath=f"testMusic/{name}.mp3",
            title=name,
            artist="test",
            duration_sec=duration,
        ),
        analysis=TrackAnalysis(
            bpm=bpm,
            camelot=camelot,
            mean_energy=energy,
        ),
    )


class TestPreferenceBonuses:
    """Test PreferenceBonuses dataclass."""

    def test_default_bonuses(self):
        bonuses = PreferenceBonuses()
        assert bonuses.liked_track_bonus == 0.0
        assert bonuses.disliked_track_penalty == 0.0
        assert bonuses.bpm_in_range_bonus == 0.0
        assert bonuses.energy_in_range_bonus == 0.0
        assert bonuses.preferred_trans_bonus == 0.0
        assert bonuses.disliked_trans_penalty == 0.0

    def test_compute_total_zero(self):
        bonuses = PreferenceBonuses()
        total = bonuses.compute_total()
        assert total == pytest.approx(0.0)

    def test_compute_total_clamped_positive(self):
        # Large positive bonuses should clamp to 0.15
        bonuses = PreferenceBonuses(
            liked_track_bonus=0.2,
            bpm_in_range_bonus=0.2,
        )
        total = bonuses.compute_total()
        assert total == pytest.approx(0.15)

    def test_compute_total_clamped_negative(self):
        # Large negative penalties should clamp to -0.15
        # disliked_track_penalty and disliked_trans_penalty are SUBTRACTED
        bonuses = PreferenceBonuses(
            disliked_track_penalty=0.2,
            disliked_trans_penalty=0.2,
        )
        total = bonuses.compute_total()
        assert total == pytest.approx(-0.15)

    def test_compute_total_mixed(self):
        bonuses = PreferenceBonuses(
            liked_track_bonus=0.05,
            bpm_in_range_bonus=0.05,
            disliked_track_penalty=0.03,
        )
        total = bonuses.compute_total()
        # raw = 0.05 + 0.05 - 0.03 = 0.07
        assert total == pytest.approx(0.07)


class TestScoreWithPreferences:
    """Test score_with_preferences function."""

    def test_no_preferences(self):
        result = score_with_preferences(0.7, PreferenceBonuses())
        assert result == pytest.approx(0.7)

    def test_positive_preferences(self):
        # Use values within the 0.15 clamp
        bonuses = PreferenceBonuses(liked_track_bonus=0.1)
        result = score_with_preferences(0.7, bonuses)
        assert result == pytest.approx(0.8)

    def test_negative_preferences(self):
        bonuses = PreferenceBonuses(disliked_track_penalty=0.1)
        result = score_with_preferences(0.7, bonuses)
        # raw bonus = -0.1 (subtracted), result = 0.7 - 0.1 = 0.6
        assert result == pytest.approx(0.6)

    def test_clamped_to_0(self):
        bonuses = PreferenceBonuses(disliked_track_penalty=0.3)
        result = score_with_preferences(0.1, bonuses)
        # raw bonus = -0.15 (clamped), result = max(0, 0.1 - 0.15) = 0.0
        assert result >= 0.0

    def test_clamped_to_1(self):
        bonuses = PreferenceBonuses(liked_track_bonus=0.3)
        result = score_with_preferences(0.9, bonuses)
        # raw bonus = +0.15 (clamped), result = min(1.0, 0.9 + 0.15) = 1.0
        assert result <= 1.0


class TestComputePreferenceBonuses:
    """Test compute_preference_bonuses function."""

    def test_no_context(self):
        target = make_mock_track("target")
        bonuses = compute_preference_bonuses(target=target)
        assert bonuses.liked_track_bonus == 0.0
        assert bonuses.disliked_track_penalty == 0.0

    def test_liked_track(self):
        target = make_mock_track("track1")
        bonuses = compute_preference_bonuses(
            target=target,
            liked_tracks={"track1"},
        )
        assert bonuses.liked_track_bonus > 0

    def test_disliked_track(self):
        target = make_mock_track("track1")
        bonuses = compute_preference_bonuses(
            target=target,
            disliked_tracks={"track1"},
        )
        # disliked_track_penalty is a positive number (the penalty amount)
        assert bonuses.disliked_track_penalty > 0

    def test_bpm_in_range(self):
        target = make_mock_track("track1", bpm=125.0)
        bonuses = compute_preference_bonuses(
            target=target,
            preferred_bpm_range=(120.0, 130.0),
        )
        assert bonuses.bpm_in_range_bonus > 0

    def test_energy_in_range(self):
        target = make_mock_track("track1", energy=0.5)
        bonuses = compute_preference_bonuses(
            target=target,
            preferred_energy_range=(0.3, 0.7),
        )
        assert bonuses.energy_in_range_bonus > 0


class TestScoreCompatibility:
    """Test scoring transitions."""

    def test_basic_scoring(self):
        source = make_mock_track("source", bpm=120.0, camelot="8A", energy=0.5)
        target = make_mock_track("target", bpm=120.0, camelot="8A", energy=0.5)
        result = score_compatibility(source, target)
        assert 0.0 <= result.overall_score <= 1.0

    def test_same_tracks_high_score(self):
        source = make_mock_track("source", bpm=120.0, camelot="8A", energy=0.5)
        target = make_mock_track("target", bpm=120.0, camelot="8A", energy=0.5)
        result = score_compatibility(source, target)
        assert result.overall_score > 0.5

    def test_mismatched_lower_score(self):
        source = make_mock_track("source", bpm=100.0, camelot="1A", energy=0.2)
        target = make_mock_track("target", bpm=140.0, camelot="8A", energy=0.9)
        result = score_compatibility(source, target)
        assert result.overall_score < 0.6
