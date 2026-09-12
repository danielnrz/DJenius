from __future__ import annotations

from dataclasses import replace

import pytest

from djenius.core.analysis_v2 import build_tempo_hypotheses
from djenius.core.candidate_composer import (
    CandidateComposerConfig,
    CandidateComposition,
    CandidateDiagnostics,
    CandidateSetContext,
    TransitionCandidate,
    compose_transition_candidates,
)
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile
from djenius.core.performance_recipe import compile_performance_recipe


def _sections(duration: float, *, drop_strength: float = 0.9, confidence: float = 0.9):
    third = duration / 3.0
    return [
        {
            "start_sec": 0.0, "end_sec": third, "label": "intro",
            "boundary_confidence": confidence, "mix_in_score": 0.9,
            "mix_out_score": 0.35, "landing_strength": 0.3,
            "bass_density": 0.45, "energy_mean": 0.35,
        },
        {
            "start_sec": third, "end_sec": 2 * third,
            "label": "drop" if drop_strength >= 0.62 else "verse",
            "boundary_confidence": confidence, "mix_in_score": 0.88,
            "mix_out_score": 0.78, "landing_strength": drop_strength,
            "bass_density": 0.72, "energy_mean": 0.82,
        },
        {
            "start_sec": 2 * third, "end_sec": duration, "label": "outro",
            "boundary_confidence": confidence, "mix_in_score": 0.3,
            "mix_out_score": 0.96, "landing_strength": 0.25,
            "bass_density": 0.42, "energy_mean": 0.4,
        },
    ]


def _cues(duration: float, *, drop_strength: float = 0.9, confidence: float = 0.9):
    third = duration / 3.0
    return [
        {
            "time_sec": 0.0, "bar_index": 1, "beat_in_bar": 1,
            "confidence": confidence, "section": "intro", "use_cases": ["mix_in"],
            "mix_in_score": 0.9, "mix_out_score": 0.2,
        },
        {
            "time_sec": third, "bar_index": 9, "beat_in_bar": 1,
            "confidence": confidence,
            "section": "drop" if drop_strength >= 0.62 else "verse",
            "use_cases": ["mix_in", "phrase_cut"] + (["drop_landing"] if drop_strength >= 0.62 else []),
            "mix_in_score": 0.88, "mix_out_score": 0.78,
        },
        {
            "time_sec": 2 * third, "bar_index": 17, "beat_in_bar": 1,
            "confidence": confidence, "section": "outro",
            "use_cases": ["mix_out", "phrase_cut"],
            "mix_in_score": 0.3, "mix_out_score": 0.96,
        },
    ]


def _track(
    track_id: str,
    *,
    bpm: float = 120.0,
    duration: float = 96.0,
    vocal: float = 0.1,
    stems: bool = False,
    drop_strength: float = 0.9,
    phrase_confidence: float = 0.9,
    bass_density: float = 0.6,
) -> TrackProfile:
    sections = _sections(duration, drop_strength=drop_strength, confidence=phrase_confidence)
    for section in sections:
        section["bass_density"] = bass_density
    stem_paths = (
        {name: f"/private/{track_id}/{name}.wav" for name in ("vocals", "drums", "bass", "other")}
        if stems else None
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=f"/private/{track_id}.wav", duration_sec=duration),
        analysis=TrackAnalysis(
            bpm=bpm,
            bpm_confidence=0.98,
            analysis_confidence=0.95,
            tempo_hypotheses=build_tempo_hypotheses(bpm, 0.98),
            section_profiles=sections,
            cue_candidates=_cues(duration, drop_strength=drop_strength, confidence=phrase_confidence),
            vocal_activity_curve=[vocal] * max(1, int(duration)),
            energy_curve=[0.6] * max(1, int(duration)),
            low_energy=bass_density,
            groove_profile={
                "confidence": 0.9,
                "syncopation_index": 0.25,
                "swing_ratio": 1.0,
                "percussion_density_mean": 0.55,
            },
            stems=stem_paths,
            stem_activity_profiles={"vocals": {"active_fraction": 0.8}} if stems else {},
        ),
    )


def _families(composition: CandidateComposition) -> list[str]:
    return [item.technique_family for item in composition.candidates]


def _rejections(composition: CandidateComposition) -> dict[str, tuple[str, ...]]:
    return {item.technique_family: item.diagnostics.reason_codes for item in composition.rejected}


def test_same_inputs_produce_identical_ordered_candidates_and_ids():
    source = _track("source", bpm=120)
    target = _track("target", bpm=122)
    first = compose_transition_candidates(source, target, seed=17)
    second = compose_transition_candidates(source, target, seed=17)
    assert first.to_dict() == second.to_dict()
    assert [c.candidate_id for c in first.candidates] == [c.candidate_id for c in second.candidates]
    assert all(c.candidate_id.startswith("tc5_") for c in first.candidates)


def test_candidate_and_composition_round_trip_serialization():
    result = compose_transition_candidates(_track("a"), _track("b", bpm=121), seed=5)
    restored = CandidateComposition.from_dict(result.to_dict())
    assert restored.to_dict() == result.to_dict()
    assert TransitionCandidate.from_dict(result.candidates[0].to_dict()).to_dict() == result.candidates[0].to_dict()


def test_every_emitted_candidate_compiles_and_stays_in_bounds():
    result = compose_transition_candidates(_track("a", bpm=118), _track("b", bpm=121), seed=3)
    assert result.candidates
    for candidate in result.candidates:
        assert candidate.validate() == []
        compiled = compile_performance_recipe(candidate.recipe, candidate.compile_context())
        assert compiled.source_start_sec >= candidate.source_segment.start_sec - 1e-6
        assert compiled.source_end_sec <= candidate.source_segment.end_sec + 1e-6
        assert compiled.target_start_sec >= candidate.target_segment.start_sec - 1e-6
        assert compiled.target_end_sec <= candidate.target_segment.end_sec + 1e-6


def test_invalid_candidate_identity_and_feasibility_fail_closed():
    candidate = compose_transition_candidates(_track("a"), _track("b"), seed=1).candidates[0]
    bad_id = replace(candidate, candidate_id="tc5_wrong")
    assert "candidate_id" in " ".join(bad_id.validate())
    infeasible = replace(candidate, diagnostics=CandidateDiagnostics(False, ("forced",), {}, "forced"), candidate_id="")
    infeasible = infeasible.with_deterministic_id()
    assert "infeasible candidate" in " ".join(infeasible.validate())


def test_easy_same_bpm_handoff_has_family_level_diversity():
    result = compose_transition_candidates(_track("a", bpm=120), _track("b", bpm=120), seed=9)
    families = _families(result)
    assert 3 <= len(families) <= 8
    assert len(families) == len(set(families))
    assert {"eq_blend", "filter_blend", "phrase_cut", "echo_out"} <= set(families)
    assert result.diagnostics["audition_ranking_performed"] is False


def test_moderate_tempo_difference_changes_blend_eligibility():
    result = compose_transition_candidates(_track("a", bpm=120), _track("b", bpm=128), seed=9)
    families = set(_families(result))
    rejected = _rejections(result)
    assert "eq_blend" not in families
    assert "primary_tempo_delta_too_large" in rejected["eq_blend"]
    assert "filter_blend" in families
    assert "loop_transition" in families


def test_large_tempo_jump_prefers_reset_eligible_families_and_rejects_long_blends():
    result = compose_transition_candidates(_track("a", bpm=90), _track("b", bpm=145), seed=9)
    families = _families(result)
    assert families[0] == "tempo_reset"
    assert "eq_blend" not in families
    assert "filter_blend" not in families
    assert "tempo_reset" in families


def test_half_double_tempo_hypothesis_prevents_unnecessary_reset():
    result = compose_transition_candidates(_track("a", bpm=70), _track("b", bpm=140), seed=9)
    assert "tempo_reset" not in _families(result)
    assert "half_double_relation_avoids_reset" in _rejections(result)["tempo_reset"]
    assert result.diagnostics["best_hypothesis_delta_pct"] == pytest.approx(0.0)


def test_vocal_heavy_overlap_suppresses_long_full_spectrum_blends():
    result = compose_transition_candidates(
        _track("a", vocal=0.9, stems=True), _track("b", bpm=121, vocal=0.85, stems=True), seed=11
    )
    families = set(_families(result))
    assert "eq_blend" not in families
    assert "filter_blend" not in families
    assert "loop_transition" not in families
    assert "phrase_cut" in families and "echo_out" in families
    assert result.candidates[0].intent.vocal_policy == "avoid_overlap"


def test_instrumental_friendly_overlap_keeps_long_blend_options():
    result = compose_transition_candidates(_track("a", vocal=0.0), _track("b", bpm=121, vocal=0.05), seed=11)
    assert "eq_blend" in _families(result)
    assert "filter_blend" in _families(result)


def test_stem_handoff_requires_declared_stems_without_silent_fallback():
    no_stems = compose_transition_candidates(
        _track("a", vocal=0.9), _track("b", bpm=121, vocal=0.8), seed=2
    )
    assert "stem_handoff" not in _families(no_stems)
    assert "required_stems_unavailable" in _rejections(no_stems)["stem_handoff"]

    with_stems = compose_transition_candidates(
        _track("a", vocal=0.9, stems=True), _track("b", bpm=121, vocal=0.8, stems=True), seed=2
    )
    stem = next(c for c in with_stems.candidates if c.technique_family == "stem_handoff")
    assert set(stem.stem_requirements) == {"source:vocals", "target:drums", "target:bass", "target:other"}
    assert stem.validate() == []


def test_strong_target_drop_enables_build_and_land_families():
    result = compose_transition_candidates(_track("a"), _track("b", drop_strength=0.92), seed=4)
    families = set(_families(result))
    assert "riser_impact" in families
    assert "loop_shortening" in families
    riser = next(c for c in result.candidates if c.technique_family == "riser_impact")
    assert riser.groove_requirements == ("noise_riser_v1", "impact_v1")
    assert riser.intent.target_anchor == "drop"


def test_weak_target_drop_rejects_drop_specific_families():
    result = compose_transition_candidates(_track("a"), _track("b", drop_strength=0.35), seed=4)
    families = set(_families(result))
    rejected = _rejections(result)
    assert "riser_impact" not in families
    assert "loop_shortening" not in families
    assert "target_drop_not_strong" in rejected["riser_impact"]


def test_weak_phrase_confidence_rejects_phrase_cut():
    result = compose_transition_candidates(
        _track("a", phrase_confidence=0.25), _track("b", phrase_confidence=0.25), seed=6
    )
    assert "phrase_cut" not in _families(result)
    assert "weak_or_non_downbeat_phrase_anchor" in _rejections(result)["phrase_cut"]


def test_groove_layer_config_controls_drum_bridge_eligibility():
    enabled = compose_transition_candidates(_track("a"), _track("b", bpm=121), seed=7)
    disabled = compose_transition_candidates(
        _track("a"), _track("b", bpm=121), seed=7,
        config=CandidateComposerConfig(enable_groove_layer=False),
    )
    assert "drum_bridge" in _families(enabled) or "candidate_cap_trimmed" in _rejections(enabled).get("drum_bridge", ())
    assert "drum_bridge" not in _families(disabled)
    assert "groove_layer_disabled" in _rejections(disabled)["drum_bridge"]


def test_candidate_count_cap_and_no_duplicate_family():
    result = compose_transition_candidates(
        _track("a", stems=True), _track("b", bpm=121, stems=True), seed=12,
        config=CandidateComposerConfig(max_candidates=5, min_candidates=3),
    )
    families = _families(result)
    assert 3 <= len(families) <= 5
    assert len(families) == len(set(families))
    assert len([c.candidate_id for c in result.candidates]) == len(set(c.candidate_id for c in result.candidates))


def test_short_track_boundary_never_generates_out_of_bounds_candidate():
    result = compose_transition_candidates(
        _track("a", duration=5.0), _track("b", duration=5.0, bpm=121), seed=15
    )
    assert result.diagnostics["available_bars"] <= 2
    for candidate in result.candidates:
        assert candidate.validate() == []
        assert candidate.duration_bars <= result.diagnostics["available_bars"]
    assert "eq_blend" not in _families(result)
    assert "insufficient_overlap_bars" in _rejections(result)["eq_blend"]


def test_changed_set_context_changes_candidate_set_deterministically():
    source = _track("a")
    target = _track("b", bpm=121)
    baseline = compose_transition_candidates(source, target, seed=21)
    changed = compose_transition_candidates(
        source, target, seed=21,
        set_context=CandidateSetContext(previous_technique_families=("eq_blend",), avoid_recent_repeats=True),
    )
    assert _families(baseline) != _families(changed)
    assert "eq_blend" not in _families(changed)
    assert "recent_family_repeat" in _rejections(changed)["eq_blend"]
    assert changed.to_dict() == compose_transition_candidates(
        source, target, seed=21,
        set_context=CandidateSetContext(previous_technique_families=("eq_blend",), avoid_recent_repeats=True),
    ).to_dict()


def test_generation_seed_changes_generated_recipe_identity_but_not_feasibility_families():
    source = _track("a")
    target = _track("b", bpm=121)
    a = compose_transition_candidates(source, target, seed=1)
    b = compose_transition_candidates(source, target, seed=2)
    assert _families(a) == _families(b)
    assert [c.candidate_id for c in a.candidates] != [c.candidate_id for c in b.candidates]


def test_explanations_and_reason_codes_are_present_without_quality_score():
    result = compose_transition_candidates(_track("a"), _track("b", bpm=121), seed=8)
    for candidate in result.candidates:
        assert candidate.generation_reason
        assert candidate.diagnostics.reason_codes
        payload = candidate.to_dict()
        assert "quality_score" not in payload
        assert "audition_score" not in payload


def test_low_bpm_confidence_blocks_beat_dependent_families():
    source = _track("a")
    target = _track("b", bpm=121)
    source.analysis.bpm_confidence = 0.25
    result = compose_transition_candidates(source, target, seed=31)
    families = set(_families(result))
    rejected = _rejections(result)
    for family in ("eq_blend", "bass_swap", "filter_blend", "loop_transition", "loop_shortening", "riser_impact", "drum_bridge"):
        assert family not in families
        assert "low_bpm_confidence" in rejected[family]
    assert "phrase_cut" in families and "echo_out" in families


def test_detected_bar_evidence_can_tighten_duration_derived_window():
    source = _track("a")
    target = _track("b", bpm=121)
    # Chosen source/target windows are roughly 32 seconds long, but the Phase 1
    # beat evidence below only certifies two downbeat bars inside each window.
    source.analysis.beat_positions = [
        {"time_sec": 32.1, "bar_index": 10, "beat_in_bar": 1, "is_downbeat": True},
        {"time_sec": 63.0, "bar_index": 11, "beat_in_bar": 1, "is_downbeat": True},
    ]
    target.analysis.beat_positions = [
        {"time_sec": 32.1, "bar_index": 10, "beat_in_bar": 1, "is_downbeat": True},
        {"time_sec": 63.0, "bar_index": 11, "beat_in_bar": 1, "is_downbeat": True},
    ]
    result = compose_transition_candidates(source, target, seed=32)
    assert result.diagnostics["duration_derived_bars"] >= 8
    assert result.diagnostics["source_detected_bars"] == 2
    assert result.diagnostics["target_detected_bars"] == 2
    assert result.diagnostics["available_bars"] == 2
    assert "eq_blend" not in _families(result)


def test_phrase_profiles_are_used_when_cue_candidates_are_missing():
    source = _track("a")
    target = _track("b", bpm=121)
    source.analysis.cue_candidates = []
    target.analysis.cue_candidates = []
    source.analysis.phrase_profiles = [{"time_sec": 64.0, "confidence": 0.88}]
    target.analysis.phrase_profiles = [{"time_sec": 32.0, "confidence": 0.86}]
    source.analysis.beat_positions = [{"time_sec": 64.0, "bar_index": 17, "beat_in_bar": 1, "is_downbeat": True}]
    target.analysis.beat_positions = [{"time_sec": 32.0, "bar_index": 9, "beat_in_bar": 1, "is_downbeat": True}]
    result = compose_transition_candidates(source, target, seed=33)
    assert result.candidates
    assert all(c.source_segment.anchor_sec == pytest.approx(64.0) for c in result.candidates)
    assert all(c.target_segment.anchor_sec == pytest.approx(32.0) for c in result.candidates)
    assert "phrase_cut" in _families(result)


def test_groove_mismatch_rejects_added_percussion_bridge():
    source = _track("a", vocal=0.9)
    target = _track("b", bpm=121, vocal=0.85)
    source.analysis.groove_profile.update({"syncopation_index": 0.0, "swing_ratio": 0.6, "confidence": 0.95})
    target.analysis.groove_profile.update({"syncopation_index": 0.95, "swing_ratio": 1.6, "confidence": 0.95})
    result = compose_transition_candidates(source, target, seed=34)
    assert "drum_bridge" not in _families(result)
    assert "groove_mismatch_too_large" in _rejections(result)["drum_bridge"]
    assert result.diagnostics["groove_compatible"] is False


def test_groove_bridge_is_emitted_and_compiles_when_context_is_eligible():
    source = _track("a", vocal=0.9)
    target = _track("b", bpm=121, vocal=0.85)
    result = compose_transition_candidates(source, target, seed=35)
    bridge = next(c for c in result.candidates if c.technique_family == "drum_bridge")
    assert bridge.groove_requirements == ("percussion_bridge",)
    compiled = compile_performance_recipe(bridge.recipe, bridge.compile_context())
    assert compiled.sample_layer_events
    assert {item["generator"] for item in compiled.sample_layer_events} >= {"kick_v1", "clap_v1"}


def test_invalid_candidate_count_configuration_is_rejected():
    with pytest.raises(ValueError, match="candidate count bounds"):
        compose_transition_candidates(
            _track("a"), _track("b"), config=CandidateComposerConfig(min_candidates=4, max_candidates=3)
        )


def _half_double_pair_with_confidence(confidence: float) -> tuple[TrackProfile, TrackProfile]:
    source = _track("tempo_source", bpm=70.0)
    target = _track("tempo_target", bpm=140.0)
    source.analysis.tempo_hypotheses = [
        {"relation": "primary", "bpm": 70.0, "confidence": 0.98},
        {"relation": "double", "bpm": 140.0, "confidence": confidence},
    ]
    target.analysis.tempo_hypotheses = [
        {"relation": "primary", "bpm": 140.0, "confidence": 0.98},
        {"relation": "half", "bpm": 70.0, "confidence": confidence},
    ]
    return source, target


def test_high_confidence_half_double_relation_suppresses_unnecessary_tempo_reset():
    source, target = _half_double_pair_with_confidence(0.80)
    result = compose_transition_candidates(source, target, seed=40)
    assert result.diagnostics["tempo_hypothesis_relation"] == "primary-half"
    assert result.diagnostics["tempo_hypothesis_confidence"] == pytest.approx(0.80)
    assert result.diagnostics["half_double_supported"] is True
    assert "tempo_reset" not in _families(result)
    assert "half_double_relation_avoids_reset" in _rejections(result)["tempo_reset"]


def test_low_confidence_apparent_half_double_relation_keeps_tempo_reset_eligible():
    source, target = _half_double_pair_with_confidence(0.54)
    result = compose_transition_candidates(source, target, seed=41)
    assert result.diagnostics["tempo_hypothesis_relation"] == "primary-half"
    assert result.diagnostics["tempo_hypothesis_confidence"] == pytest.approx(0.54)
    assert result.diagnostics["half_double_supported"] is False
    assert "tempo_reset" in _families(result)
    assert "half_double_relation_avoids_reset" not in _rejections(result).get("tempo_reset", ())


def test_close_primary_bpms_do_not_get_distorted_by_half_double_hypotheses():
    result = compose_transition_candidates(_track("close_a", bpm=120), _track("close_b", bpm=121), seed=42)
    assert result.diagnostics["tempo_hypothesis_relation"] == "primary-primary"
    assert result.diagnostics["tempo_hypothesis_confidence"] == pytest.approx(0.98)
    assert result.diagnostics["half_double_supported"] is False
    assert result.diagnostics["primary_tempo_delta_pct"] == pytest.approx(0.8333)
    assert "eq_blend" in _families(result)
    assert "tempo_jump_not_large_enough" in _rejections(result)["tempo_reset"]


@pytest.mark.parametrize(
    ("confidence", "supported", "reset_present"),
    [(0.549, False, True), (0.550, True, False), (0.551, True, False)],
)
def test_half_double_confidence_threshold_boundary_is_deterministic(
    confidence: float, supported: bool, reset_present: bool,
):
    source, target = _half_double_pair_with_confidence(confidence)
    result = compose_transition_candidates(source, target, seed=43)
    assert result.diagnostics["tempo_hypothesis_confidence"] == pytest.approx(confidence)
    assert result.diagnostics["half_double_supported"] is supported
    assert ("tempo_reset" in _families(result)) is reset_present


def test_half_double_relation_diagnostics_and_candidate_order_are_repeatable():
    source, target = _half_double_pair_with_confidence(0.55)
    first = compose_transition_candidates(source, target, seed=44)
    second = compose_transition_candidates(source, target, seed=44)
    assert first.to_dict() == second.to_dict()
    assert first.diagnostics["tempo_hypothesis_relation"] == second.diagnostics["tempo_hypothesis_relation"]
    assert first.diagnostics["tempo_hypothesis_confidence"] == second.diagnostics["tempo_hypothesis_confidence"]
    assert first.diagnostics["half_double_supported"] == second.diagnostics["half_double_supported"]
    assert _families(first) == _families(second)


def test_recent_family_is_deferred_when_non_recent_alternatives_meet_floor():
    context = CandidateSetContext(previous_technique_families=("eq_blend",), avoid_recent_repeats=True)
    result = compose_transition_candidates(_track("memory_a"), _track("memory_b", bpm=121), set_context=context, seed=45)
    assert "eq_blend" not in _families(result)
    assert "recent_family_repeat" in _rejections(result)["eq_blend"]
    assert result.diagnostics["memory_reintroduced_families"] == []
    assert result.diagnostics["candidate_floor_status"] == "candidate_floor_met"


def test_recent_family_returns_only_when_needed_to_meet_candidate_floor():
    context = CandidateSetContext(
        previous_technique_families=("phrase_cut", "echo_out"),
        avoid_recent_repeats=True,
    )
    result = compose_transition_candidates(
        _track("fallback_a", vocal=0.9),
        _track("fallback_b", bpm=121, vocal=0.85, drop_strength=0.35),
        set_context=context,
        seed=46,
    )
    assert _families(result) == ["phrase_cut", "drum_bridge", "bass_swap"]
    repeated = result.candidates[0]
    assert "recent_repeat_required_for_candidate_floor" in repeated.diagnostics.reason_codes
    assert repeated.provenance["technique_memory"] == "repeat_allowed_to_meet_candidate_floor"
    assert result.diagnostics["memory_reintroduced_families"] == ["phrase_cut"]
    assert "recent_family_repeat" in _rejections(result)["echo_out"]


def test_hard_infeasible_recent_family_is_never_reintroduced_for_floor():
    context = CandidateSetContext(previous_technique_families=("riser_impact",), avoid_recent_repeats=True)
    config = CandidateComposerConfig(min_candidates=5, max_candidates=8)
    result = compose_transition_candidates(
        _track("hard_a", vocal=0.9),
        _track("hard_b", bpm=121, vocal=0.85, drop_strength=0.35),
        set_context=context,
        config=config,
        seed=47,
    )
    assert "riser_impact" not in _families(result)
    assert "target_drop_not_strong" in _rejections(result)["riser_impact"]
    assert "recent_family_repeat" not in _rejections(result)["riser_impact"]
    assert "riser_impact" not in result.diagnostics["memory_reintroduced_families"]


def test_several_recent_families_use_deterministic_fallback_order():
    context = CandidateSetContext(
        previous_technique_families=("tempo_reset", "phrase_cut"),
        avoid_recent_repeats=True,
    )
    result = compose_transition_candidates(
        _track("order_a", bpm=90, vocal=0.9),
        _track("order_b", bpm=145, vocal=0.85, drop_strength=0.35),
        set_context=context,
        seed=48,
    )
    assert _families(result) == ["tempo_reset", "phrase_cut", "echo_out"]
    assert result.diagnostics["memory_reintroduced_families"] == ["tempo_reset", "phrase_cut"]
    for candidate in result.candidates[:2]:
        assert "recent_repeat_required_for_candidate_floor" in candidate.diagnostics.reason_codes
        assert candidate.provenance["technique_memory"] == "repeat_allowed_to_meet_candidate_floor"


def test_disabling_repeat_avoidance_restores_normal_family_eligibility():
    context = CandidateSetContext(previous_technique_families=("eq_blend",), avoid_recent_repeats=False)
    result = compose_transition_candidates(
        _track("repeat_a"), _track("repeat_b", bpm=121), set_context=context, seed=49,
    )
    eq = next(candidate for candidate in result.candidates if candidate.technique_family == "eq_blend")
    assert "recent_repeat_required_for_candidate_floor" not in eq.diagnostics.reason_codes
    assert "technique_memory" not in eq.provenance
    assert result.diagnostics["memory_reintroduced_families"] == []


def test_memory_fallback_candidate_order_and_diagnostics_are_repeatable():
    context = CandidateSetContext(
        previous_technique_families=("phrase_cut", "echo_out"),
        avoid_recent_repeats=True,
    )
    source = _track("repeatable_a", vocal=0.9)
    target = _track("repeatable_b", bpm=121, vocal=0.85, drop_strength=0.35)
    first = compose_transition_candidates(source, target, set_context=context, seed=50)
    second = compose_transition_candidates(source, target, set_context=context, seed=50)
    assert first.to_dict() == second.to_dict()
    assert first.diagnostics["memory_reintroduced_families"] == ["phrase_cut"]


def test_candidate_floor_can_remain_unmet_when_hard_feasibility_is_exhausted():
    context = CandidateSetContext(
        previous_technique_families=("phrase_cut", "echo_out"),
        avoid_recent_repeats=True,
    )
    config = CandidateComposerConfig(min_candidates=5, max_candidates=8)
    result = compose_transition_candidates(
        _track("floor_a", vocal=0.9),
        _track("floor_b", bpm=121, vocal=0.85, drop_strength=0.35),
        set_context=context,
        config=config,
        seed=51,
    )
    assert result.diagnostics["candidate_count"] == 4
    assert result.diagnostics["candidate_count"] < config.min_candidates
    assert result.diagnostics["candidate_floor_status"] == "candidate_floor_unmet_due_to_hard_feasibility"
    assert set(_families(result)) == {"phrase_cut", "echo_out", "drum_bridge", "bass_swap"}
    assert all(candidate.validate() == [] for candidate in result.candidates)
