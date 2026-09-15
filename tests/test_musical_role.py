from __future__ import annotations

from djenius.core.models import (
    SemanticProfile,
    TrackAnalysis,
    TrackMetadata,
    TrackProfile,
)
from djenius.core.musical_role import (
    SetRole,
    assess_musical_flow,
    derive_musical_role,
    initial_set_flow_state,
)
from djenius.core.reference_templates import ReferenceArchetype


def _track(
    track_id: str,
    *,
    bpm: float = 120.0,
    energy: float = 0.74,
    rhythmic: str = "straight",
    mood: tuple[str, float] | None = None,
) -> TrackProfile:
    groove = {
        "percussion_density_mean": 0.68,
        "onset_density_hz": 4.0,
        "syncopation_index": 0.35,
        "onbeat_fraction": 0.55,
        "swing_ratio": 1.0,
        "confidence": 0.9,
    }
    hypotheses = []
    if rhythmic == "compound":
        hypotheses = [{"relation": "double", "confidence": 0.7}]
        bpm = min(bpm, 90.0)
    analysis = TrackAnalysis(
        bpm=bpm,
        bpm_confidence=0.95,
        analysis_confidence=0.95,
        mean_energy=energy,
        camelot="8A",
        bar_times=[float(index * 2) for index in range(65)],
        downbeat_times=[float(index * 2) for index in range(65)],
        bar_energies=[energy - 0.03, energy, energy + 0.03] * 8,
        groove_profile=groove,
        tempo_hypotheses=hypotheses,
        section_profiles=[
            {
                "start_sec": 0.0,
                "end_sec": 128.0,
                "label": "intro",
                "vocal_density": 0.4,
                "drum_density": 0.7,
                "bass_density": 0.7,
            }
        ],
    )
    semantic = None
    if mood is not None:
        label, reliability = mood
        semantic = SemanticProfile(
            model_name="test-local-model",
            mood_scores={label: 0.9, "neutral": 0.1},
            reliability_by_group={"mood_scores": reliability},
        )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=f"/{track_id}.wav", duration_sec=128.0),
        analysis=analysis,
        semantic=semantic,
    )


def test_low_reliability_mood_is_explicitly_deferred():
    role = derive_musical_role(_track("A", mood=("sad", 0.3)))
    assert role.mood["label"] is None
    assert role.mood["top_estimate"] == "sad"
    assert role.mood["status"] == "deferred_low_reliability"
    assert any("no mood label" in item for item in role.evidence_limits)


def test_transitionable_but_rhythmically_inappropriate_pair_is_rejected():
    source = _track("A", bpm=120.0)
    target = _track("B", bpm=86.0, rhythmic="compound", energy=0.76)
    result = assess_musical_flow(
        source,
        target,
        state=initial_set_flow_state(source),
        target_phase=SetRole.HOLD,
        archetype=ReferenceArchetype.STEM_ECHO_HANDOFF,
        tempo_delta_pct=28.0,
        groove_distance=0.2,
        max_energy_jump=0.22,
        max_contrast_events=1,
    )
    assert result.accepted is False
    assert result.relationship == "UNJUSTIFIED_DISCONTINUITY"
    assert (
        "incompatible rhythmic role lacks a supported bridge"
        in result.rejection_reasons
    )


def test_reset_can_communicate_one_phase_supported_peak_shift():
    source = _track("A", bpm=120.0, energy=0.72)
    target = _track("B", bpm=86.0, rhythmic="compound", energy=0.78)
    result = assess_musical_flow(
        source,
        target,
        state=initial_set_flow_state(source),
        target_phase=SetRole.PEAK,
        archetype=ReferenceArchetype.RESET_RELEASE,
        tempo_delta_pct=28.0,
        groove_distance=0.2,
        max_energy_jump=0.22,
        max_contrast_events=1,
    )
    assert result.accepted is True
    assert result.relationship == "INTENTIONAL_ENERGY_MOOD_SHIFT"
    assert result.state_after.contrast_events == 1


def test_intentional_contrast_budget_prevents_repeated_unexplained_turns():
    source = _track("A", bpm=120.0, energy=0.72)
    target = _track("B", bpm=86.0, rhythmic="compound", energy=0.78)
    state = initial_set_flow_state(source)
    state = type(state)(**{**state.__dict__, "contrast_events": 1})
    result = assess_musical_flow(
        source,
        target,
        state=state,
        target_phase=SetRole.PEAK,
        archetype=ReferenceArchetype.RESET_RELEASE,
        tempo_delta_pct=28.0,
        groove_distance=0.2,
        max_energy_jump=0.22,
        max_contrast_events=1,
    )
    assert result.accepted is False
    assert result.intentional_shift_evidence["contrast_budget_available"] is False
