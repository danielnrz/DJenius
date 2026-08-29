"""Tests for V5 set plan explanations."""

import pytest
from djenius.core.intent import make_intent
from djenius.core.models import (
    TrackProfile, CompatibilityScore, TransitionType,
    TransitionPlan, SetPlan, TrackMetadata, TrackAnalysis,
    EnergyProfile,
)
from djenius.core.explanations import (
    explain_set_plan, explain_transition, format_plan_explanation,
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


def make_mock_score(
    tempo: float = 0.8,
    key: float = 0.9,
    energy: float = 0.7,
    spectral: float = 0.6,
    vocal: float = 1.0,
    overall: float = 0.75,
) -> CompatibilityScore:
    return CompatibilityScore(
        tempo_score=tempo,
        key_score=key,
        energy_score=energy,
        spectral_score=spectral,
        vocal_safety=vocal,
        overall_score=overall,
    )


def make_mock_transition(
    trans_type: TransitionType = TransitionType.CROSSFADE,
    score: CompatibilityScore = None,
) -> TransitionPlan:
    return TransitionPlan(
        source_track_id="source",
        target_track_id="target",
        transition_type=trans_type,
        compatibility_score=score or make_mock_score(),
        confidence=0.8,
    )


class TestExplainTransition:
    """Test explain_transition function."""

    def test_basic_explanation(self):
        transition = make_mock_transition()
        explanation = explain_transition(transition)
        assert isinstance(explanation, str)
        assert "crossfade" in explanation

    def test_different_types(self):
        for trans_type in TransitionType:
            transition = make_mock_transition(trans_type=trans_type)
            explanation = explain_transition(transition)
            assert isinstance(explanation, str)
            assert trans_type.value in explanation

    def test_high_confidence(self):
        transition = make_mock_transition()
        transition.confidence = 0.9
        explanation = explain_transition(transition)
        assert "high confidence" in explanation

    def test_low_confidence(self):
        transition = make_mock_transition()
        transition.confidence = 0.3
        explanation = explain_transition(transition)
        assert "low confidence" in explanation


class TestExplainSetPlan:
    """Test explain_set_plan function."""

    def test_basic_explanation(self):
        tracks = [make_mock_track(f"track{i}") for i in range(3)]
        transitions = [
            TransitionPlan(
                source_track_id="track0",
                target_track_id="track1",
                transition_type=TransitionType.CROSSFADE,
                compatibility_score=make_mock_score(),
            ),
            TransitionPlan(
                source_track_id="track1",
                target_track_id="track2",
                transition_type=TransitionType.BEATMATCHED_BLEND,
                compatibility_score=make_mock_score(),
            ),
        ]
        plan = SetPlan(
            tracks=tracks,
            transitions=transitions,
            total_duration_sec=720.0,
        )
        reasons = explain_set_plan(plan)
        assert isinstance(reasons, list)
        assert len(reasons) > 0

    def test_empty_set(self):
        plan = SetPlan()
        reasons = explain_set_plan(plan)
        assert isinstance(reasons, list)

    def test_with_intent(self):
        tracks = [make_mock_track(f"track{i}") for i in range(4)]
        intent = make_intent("chill")
        plan = SetPlan(
            tracks=tracks,
            total_duration_sec=960.0,
            intent_used=intent,
        )
        reasons = explain_set_plan(plan)
        # Should include intent alignment reasons
        assert any("preset" in r.lower() for r in reasons)


class TestFormatPlanExplanation:
    """Test format_plan_explanation function."""

    def test_formatting(self):
        tracks = [make_mock_track(f"track{i}") for i in range(3)]
        plan = SetPlan(
            tracks=tracks,
            total_duration_sec=720.0,
        )
        formatted = format_plan_explanation(plan)
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert "-" in formatted  # formatted as bullet list
