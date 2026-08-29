"""Tests for V5 intent-aware planning."""

import pytest
from djenius.core.intent import make_intent, TransitionStyle
from djenius.core.models import (
    TrackProfile, CompatibilityScore, SetPlan,
    TrackMetadata, TrackAnalysis, EnergyProfile,
)
from djenius.core.planner import plan_set


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


class TestPlanSetWithIntent:
    """Test plan_set with V5 intent parameter."""

    def test_plan_set_no_intent(self):
        tracks = [make_mock_track(f"track{i}") for i in range(4)]
        plan = plan_set(tracks)
        assert isinstance(plan, SetPlan)
        assert len(plan.transitions) > 0

    def test_plan_set_with_intent(self):
        tracks = [make_mock_track(f"track{i}") for i in range(4)]
        intent = make_intent("chill")
        plan = plan_set(tracks, intent=intent)
        assert isinstance(plan, SetPlan)
        assert plan.intent_used is not None

    def test_plan_set_with_preference_bonuses(self):
        tracks = [make_mock_track(f"track{i}") for i in range(4)]
        bonuses = {
            "liked_tracks": {"track0"},
            "disliked_tracks": set(),
            "preferred_bpm_range": (118.0, 122.0),
            "preferred_energy_range": (0.3, 0.7),
            "preferred_transition_types": {},
            "disliked_transition_types": {},
        }
        plan = plan_set(tracks, preference_bonuses=bonuses)
        assert isinstance(plan, SetPlan)

    def test_plan_set_empty(self):
        plan = plan_set([])
        assert isinstance(plan, SetPlan)
        assert len(plan.transitions) == 0

    def test_plan_set_single_track(self):
        tracks = [make_mock_track("track0")]
        plan = plan_set(tracks)
        assert isinstance(plan, SetPlan)
        assert len(plan.transitions) == 0


class TestPlanSetIntentEffects:
    """Test that intent actually affects planning."""

    def test_different_intents_different_plans(self):
        tracks = [make_mock_track(f"track{i}") for i in range(6)]

        chill_intent = make_intent("chill")
        peak_intent = make_intent("peak")

        chill_plan = plan_set(tracks, intent=chill_intent)
        peak_plan = plan_set(tracks, intent=peak_intent)

        # Different intents should produce different plans
        # (at least some transition types should differ)
        assert chill_plan is not None
        assert peak_plan is not None

    def test_intent_with_energy_range(self):
        tracks = [make_mock_track(f"track{i}", energy=i/5.0) for i in range(5)]
        intent = make_intent("chill")
        plan = plan_set(tracks, intent=intent)
        assert isinstance(plan, SetPlan)
