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
    calibrate_musical_context,
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
    sample_windows = [{
        "start_sec": 48.0,
        "end_sec": 58.0,
        "scores": {
            "mood_scores": {"neutral": 1.0},
            "activity_scores": {"listening": 1.0},
            "intensity_scores": {"moderate": 1.0},
            "style_scores": {"electronic": 1.0},
        },
    }]
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
    semantic = SemanticProfile(
        model_name="test-local-model",
        embedding=[1.0, 0.0],
        sample_windows=sample_windows,
    )
    if mood is not None:
        label, reliability = mood
        semantic = SemanticProfile(
            model_name="test-local-model",
            embedding=[1.0, 0.0],
            sample_windows=sample_windows,
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
        source_context_sec=52.0,
        target_context_sec=52.0,
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
        source_context_sec=52.0,
        target_context_sec=52.0,
    )
    assert result.accepted is True
    assert result.relationship == "INTENTIONAL_BRIDGEABLE_CONTRAST"
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
        source_context_sec=52.0,
        target_context_sec=52.0,
    )
    assert result.accepted is False
    assert result.intentional_shift_evidence["contrast_budget_available"] is False


def test_reset_cannot_bridge_pool_relative_musical_territory_outlier():
    source = _track("A", bpm=120.0, energy=0.72)
    target = _track("B", bpm=86.0, rhythmic="compound", energy=0.78)
    target.semantic.embedding = [0.0, 1.0]
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
        source_context_sec=52.0,
        target_context_sec=52.0,
    )
    assert result.accepted is False
    assert result.relationship == "UNJUSTIFIED_DISCONTINUITY"
    context = result.evidence["musical_context"]
    assert context["contrast_axes"]["pool_relative_audio_embedding_outlier"] is True
    assert context["audio_embedding_interpretation"] == (
        "pool_relative_musical_territory_only; not a mood or genre label"
    )


def test_cue_local_style_and_intensity_split_is_not_masked_by_whole_track_similarity():
    source = _track("A", bpm=120.0, energy=0.74)
    target = _track("B", bpm=120.0, energy=0.75)
    target.semantic.sample_windows[0]["scores"]["style_scores"] = {"acoustic": 1.0}
    target.semantic.sample_windows[0]["scores"]["intensity_scores"] = {"soft": 1.0}
    result = assess_musical_flow(
        source,
        target,
        state=initial_set_flow_state(source),
        target_phase=SetRole.HOLD,
        archetype=ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND,
        tempo_delta_pct=0.0,
        groove_distance=0.05,
        max_energy_jump=0.22,
        max_contrast_events=1,
        source_context_sec=52.0,
        target_context_sec=52.0,
    )
    assert result.relationship == "UNJUSTIFIED_DISCONTINUITY"
    context = result.evidence["musical_context"]
    assert context["cue_context_split_unresolved"] is True
    assert context["contrast_axes"]["cue_style_and_intensity_shift_together"] is True
    assert result.accepted is False


def test_large_contrast_abstains_when_cue_context_evidence_is_unavailable():
    source = _track("A", bpm=120.0, energy=0.72)
    target = _track("B", bpm=86.0, rhythmic="compound", energy=0.78)
    source.semantic.sample_windows = []
    target.semantic.sample_windows = []
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
        source_context_sec=52.0,
        target_context_sec=52.0,
    )
    assert result.relationship == "UNJUSTIFIED_DISCONTINUITY"
    context = result.evidence["musical_context"]
    assert context["cue_context_available_for_contrast_decision"] is False
    assert result.intentional_shift_evidence[
        "context_has_at_least_two_continuity_anchors"
    ] is False


def test_context_calibration_is_deterministic_and_uses_unlabelled_pairs():
    tracks = [_track("A"), _track("B"), _track("C")]
    tracks[1].semantic.embedding = [0.8, 0.2]
    tracks[2].semantic.embedding = [0.2, 0.8]
    first = calibrate_musical_context(tracks)
    second = calibrate_musical_context(list(reversed(tracks)))
    assert first == second
    assert first.track_count == 3
    assert first.embedding_pair_count == 3
    assert first.source == "unlabelled_candidate_pool_quantiles"
