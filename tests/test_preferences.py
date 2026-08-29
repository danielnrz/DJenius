"""Tests for V5 PreferenceProfile (SQLite-backed preference store)."""

import os
import tempfile
import pytest
from djenius.db.preferences import PreferenceProfile


@pytest.fixture
def profile(tmp_path):
    """Create a temporary PreferenceProfile for each test."""
    db_path = str(tmp_path / "test_prefs.db")
    p = PreferenceProfile(db_path=db_path)
    yield p
    p.close()


class TestPreferenceProfileLifecycle:
    """Test basic lifecycle."""

    def test_creates_db_file(self, tmp_path):
        db_path = str(tmp_path / "new.db")
        p = PreferenceProfile(db_path=db_path)
        assert os.path.exists(db_path)
        p.close()

    def test_close_idempotent(self, profile):
        profile.close()
        profile.close()  # Should not raise


class TestTransitionRatings:
    """Test transition rating storage and retrieval."""

    def test_rate_and_get_avg(self, profile):
        profile.rate_transition("src1", "tgt1", "crossfade", 0.8)
        avg = profile.get_transition_avg("src1", "tgt1")
        assert avg == pytest.approx(0.8)

    def test_rate_multiple(self, profile):
        profile.rate_transition("src1", "tgt1", "crossfade", 0.6)
        profile.rate_transition("src1", "tgt1", "crossfade", 0.9)
        avg = profile.get_transition_avg("src1", "tgt1")
        assert avg == pytest.approx(0.75)

    def test_rate_negative(self, profile):
        profile.rate_transition("src1", "tgt1", "crossfade", -0.5)
        avg = profile.get_transition_avg("src1", "tgt1")
        assert avg == pytest.approx(-0.5)

    def test_rate_clamped(self, profile):
        profile.rate_transition("src1", "tgt1", "crossfade", 5.0)
        avg = profile.get_transition_avg("src1", "tgt1")
        assert avg == pytest.approx(1.0)

    def test_no_ratings_returns_none(self, profile):
        avg = profile.get_transition_avg("nonexistent", "nonexistent")
        assert avg is None

    def test_filter_by_type(self, profile):
        profile.rate_transition("s", "t", "crossfade", 0.9)
        profile.rate_transition("s", "t", "bass_swap", -0.5)
        avg_cf = profile.get_transition_avg("s", "t", "crossfade")
        avg_bs = profile.get_transition_avg("s", "t", "bass_swap")
        assert avg_cf == pytest.approx(0.9)
        assert avg_bs == pytest.approx(-0.5)

    def test_preferred_transition_types(self, profile):
        # Need at least 3 samples (default min_samples)
        for _ in range(3):
            profile.rate_transition("s1", "t1", "crossfade", 0.8)
        for _ in range(3):
            profile.rate_transition("s1", "t1", "bass_swap", -0.3)
        prefs = profile.get_preferred_transition_types(min_samples=2)
        assert "crossfade" in prefs
        assert "bass_swap" in prefs
        assert prefs["crossfade"] > prefs["bass_swap"]


class TestTrackFeedback:
    """Test track like/dislike/play count."""

    def test_like_track(self, profile):
        profile.like_track("track_a")
        fb = profile.get_track_feedback("track_a")
        assert fb is not None
        assert fb["liked"] == 1
        assert fb["play_count"] >= 1

    def test_dislike_track(self, profile):
        profile.dislike_track("track_b")
        fb = profile.get_track_feedback("track_b")
        assert fb is not None
        assert fb["liked"] == -1

    def test_increment_play_count(self, profile):
        profile.increment_play_count("track_c")
        profile.increment_play_count("track_c")
        fb = profile.get_track_feedback("track_c")
        assert fb["play_count"] == 2

    def test_like_updates_play_count(self, profile):
        profile.like_track("track_d")
        profile.like_track("track_d")
        fb = profile.get_track_feedback("track_d")
        assert fb["liked"] == 1
        assert fb["play_count"] == 2

    def test_get_liked_tracks(self, profile):
        profile.like_track("track_e")
        profile.like_track("track_f")
        profile.dislike_track("track_g")
        liked = profile.get_liked_tracks()
        assert "track_e" in liked
        assert "track_f" in liked
        assert "track_g" not in liked

    def test_get_disliked_tracks(self, profile):
        profile.like_track("track_e")
        profile.dislike_track("track_f")
        disliked = profile.get_disliked_tracks()
        assert "track_f" in disliked
        assert "track_e" not in disliked

    def test_no_feedback_returns_none(self, profile):
        fb = profile.get_track_feedback("nonexistent")
        assert fb is None

    def test_most_played(self, profile):
        for _ in range(5):
            profile.increment_play_count("popular")
        for _ in range(2):
            profile.increment_play_count("less_popular")
        most = profile.get_most_played(2)
        assert len(most) >= 1
        assert most[0][0] == "popular"
        assert most[0][1] == 5


class TestBpmPreference:
    """Test BPM preference storage."""

    def test_set_and_get(self, profile):
        profile.set_bpm_preference(118.0, 128.0)
        bpm = profile.get_bpm_preference()
        assert bpm == (118.0, 128.0)

    def test_overwrite(self, profile):
        profile.set_bpm_preference(110.0, 130.0)
        profile.set_bpm_preference(120.0, 125.0)
        bpm = profile.get_bpm_preference()
        assert bpm == (120.0, 125.0)

    def test_not_set_returns_none(self, profile):
        bpm = profile.get_bpm_preference()
        assert bpm is None


class TestEnergyPreference:
    """Test energy preference storage."""

    def test_set_and_get(self, profile):
        profile.set_energy_preference(0.3, 0.7)
        energy = profile.get_energy_preference()
        assert energy == (0.3, 0.7)

    def test_not_set_returns_none(self, profile):
        energy = profile.get_energy_preference()
        assert energy is None


class TestScoringBonuses:
    """Test get_scoring_bonuses aggregate helper."""

    def test_empty_profile(self, profile):
        bonuses = profile.get_scoring_bonuses()
        assert bonuses["liked_tracks"] == set()
        assert bonuses["disliked_tracks"] == set()
        assert bonuses["preferred_bpm_range"] is None
        assert bonuses["preferred_energy_range"] is None

    def test_with_feedback(self, profile):
        profile.like_track("t1")
        profile.dislike_track("t2")
        profile.set_bpm_preference(120.0, 130.0)
        bonuses = profile.get_scoring_bonuses()
        assert "t1" in bonuses["liked_tracks"]
        assert "t2" in bonuses["disliked_tracks"]
        assert bonuses["preferred_bpm_range"] == (120.0, 130.0)


class TestSummary:
    """Test summary returns a string."""

    def test_summary_is_string(self, profile):
        s = profile.summary()
        assert isinstance(s, str)

    def test_summary_contains_profile(self, profile):
        s = profile.summary()
        assert "Preference Profile" in s
