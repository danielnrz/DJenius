from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from djenius.audio.reference_template_renderer import (
    ReferenceRenderInputs,
    coherent_time_fit,
    render_reference_template,
)
from djenius.core.models import TrackAnalysis
from djenius.core.performance_recipe import ActionType, validate_performance_recipe
from djenius.core.reference_templates import (
    ARCHETYPE_DEFINITIONS,
    ReferenceArchetype,
    ReferenceTemplateEligibilityError,
    assess_reference_template_pair,
    instantiate_reference_template,
)


SR = 4000
STEM_NAMES = ("drums", "bass", "other", "vocals")


def _analysis(*, source: bool, shift: float = 0.0) -> TrackAnalysis:
    grid = [shift + 2.0 * index for index in range(31)]
    energy = [.55] * 31
    if not source:
        energy[12], energy[13], energy[14], energy[15], energy[16], energy[17] = .85, .82, .54, .94, .88, .86
    sections = (
        [
            {"start_sec": shift, "end_sec": shift + 16, "label": "verse", "energy_mean": .63, "drum_density": .7},
            {"start_sec": shift + 16, "end_sec": shift + 44, "label": "outro", "energy_mean": .72, "drum_density": .68},
            {"start_sec": shift + 46, "end_sec": shift + 60, "label": "outro", "energy_mean": .22, "drum_density": .15},
        ]
        if source
        else [
            {"start_sec": shift, "end_sec": shift + 24, "label": "intro", "energy_mean": .35, "drum_density": .5},
            {"start_sec": shift + 24, "end_sec": shift + 28, "label": "build", "energy_mean": .58, "drum_density": .65},
            {"start_sec": shift + 28, "end_sec": shift + 48, "label": "drop", "energy_mean": .90, "drum_density": .82},
            {"start_sec": shift + 48, "end_sec": shift + 62, "label": "verse", "energy_mean": .65, "drum_density": .7},
        ]
    )
    vocals = [(shift + 18, shift + 21), (shift + 40, shift + 44)] if source else [(shift + 32, shift + 35)]
    return TrackAnalysis(
        bpm=120,
        bpm_confidence=.97,
        analysis_confidence=.96,
        downbeat_times=grid,
        bar_times=grid,
        bar_energies=energy,
        low_energy_curve=[.31 if source else (.18 if index < 28 else .57) for index in range(62)],
        section_profiles=sections,
        structural_sections=[
            (float(item["start_sec"]), float(item["end_sec"]), str(item["label"]))
            for item in sections
        ],
        vocal_regions=vocals,
        stems={name: f"/{name}.wav" for name in STEM_NAMES},
        stem_activity_profiles={
            "drums": {"active_fraction": .82, "activity_confidence": .95},
            "bass": {"active_fraction": .75, "activity_confidence": .95},
            "other": {"active_fraction": .86, "activity_confidence": .95},
            "vocals": {"active_fraction": .70, "activity_confidence": .95},
        },
    )


def _instance(archetype: ReferenceArchetype, *, shift: float = 0.0):
    return instantiate_reference_template(
        _analysis(source=True, shift=shift),
        _analysis(source=False, shift=shift),
        archetype,
        source_track_id="source-hash",
        target_track_id="target-hash",
        source_duration_sec=shift + 62,
        target_duration_sec=shift + 62,
    )


def _audio(frequency: float, length_sec: float = 64.0) -> np.ndarray:
    axis = np.arange(round(length_sec * SR), dtype=np.float64) / SR
    mono = (
        .18 * np.sin(2 * np.pi * frequency * axis)
        + .04 * np.sin(2 * np.pi * frequency * 2.013 * axis)
        + .015 * np.sign(np.sin(2 * np.pi * 2 * axis))
    ).astype(np.float32)
    return np.column_stack((mono, np.roll(mono, 3))).astype(np.float32)


def _render_inputs() -> ReferenceRenderInputs:
    source_audio, target_audio = _audio(110), _audio(137)
    source_stems = {
        "drums": _audio(190),
        "bass": _audio(82),
        "other": _audio(310),
        "vocals": _audio(440),
    }
    target_stems = {
        "drums": _audio(205),
        "bass": _audio(91),
        "other": _audio(350),
        "vocals": _audio(510),
    }
    return ReferenceRenderInputs(
        source_audio,
        target_audio,
        source_stems,
        target_stems,
        _analysis(source=True),
        _analysis(source=False),
        SR,
    )


@pytest.mark.parametrize("archetype", list(ReferenceArchetype))
def test_reference_template_instantiation_is_deterministic_and_bar_relative(archetype):
    first, second = _instance(archetype), _instance(archetype)
    assert first.to_dict() == second.to_dict()
    assert first.instance_id == second.instance_id
    assert first.recipe.recipe_id == second.recipe.recipe_id
    assert validate_performance_recipe(first.recipe) == []
    assert all(0 <= item.position.beat_offset < first.recipe.bars * 4 for item in first.recipe.actions)
    assert first.recipe.metadata["autonomous_selection_allowed"] is False


def test_analysis_shift_moves_anchors_without_changing_choreography_schedule():
    baseline = _instance(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF)
    shifted = _instance(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF, shift=1.25)
    assert shifted.anchors.source_start_sec == pytest.approx(baseline.anchors.source_start_sec + 1.25)
    assert shifted.anchors.target_landing_sec == pytest.approx(baseline.anchors.target_landing_sec + 1.25)
    assert [item.position for item in shifted.recipe.actions] == [item.position for item in baseline.recipe.actions]


def test_loop_build_schedule_and_bass_ownership_are_constrained():
    instance = _instance(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF)
    loop_actions = [
        (item.action, item.position.beat_offset, item.parameters.get("length_beats"))
        for item in instance.recipe.actions
        if item.action in {ActionType.LOOP_START, ActionType.LOOP_LENGTH, ActionType.LOOP_END}
    ]
    assert loop_actions == [
        (ActionType.LOOP_START, 16.0, 4.0),
        (ActionType.LOOP_LENGTH, 24.0, 2.0),
        (ActionType.LOOP_LENGTH, 28.0, 1.0),
        (ActionType.LOOP_END, 31.75, None),
    ]
    ownership = instance.choreography["bass_ownership"]
    assert ownership == ((0.0, 4.0, "source"), (4.0, 5.65, "none_or_target_tease"), (5.65, 8.0, "target"))
    assert ownership[0][1] <= ownership[1][0] and ownership[1][1] <= ownership[2][0]


def test_eligibility_rejects_missing_stems_low_confidence_and_unsafe_tempo():
    source, target = _analysis(source=True), _analysis(source=False)
    with pytest.raises(ReferenceTemplateEligibilityError, match="source stems missing"):
        instantiate_reference_template(
            replace(source, stems={}), target, ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
            source_track_id="a", target_track_id="b", source_duration_sec=62, target_duration_sec=62,
        )
    with pytest.raises(ReferenceTemplateEligibilityError, match="beatgrid confidence"):
        instantiate_reference_template(
            replace(source, bpm_confidence=.1), target, ReferenceArchetype.STEM_ECHO_HANDOFF,
            source_track_id="a", target_track_id="b", source_duration_sec=62, target_duration_sec=62,
        )
    with pytest.raises(ReferenceTemplateEligibilityError, match="tempo delta"):
        instantiate_reference_template(
            source, replace(target, bpm=150), ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND,
            source_track_id="a", target_track_id="b", source_duration_sec=62, target_duration_sec=62,
        )


def test_shared_time_fit_preserves_master_stem_clock_and_reconstruction():
    axis = np.linspace(0, 8 * np.pi, 4000, endpoint=False, dtype=np.float32)
    left = np.column_stack((np.sin(axis), np.cos(axis))).astype(np.float32)
    right = np.column_stack((np.sin(axis * 1.7), np.cos(axis * 1.7))).astype(np.float32)
    rendered, backend = coherent_time_fit(
        {"master": left + right, "left": left, "right": right}, 4600, SR, backend="scipy",
    )
    assert backend == "scipy_shared_multichannel_fallback"
    assert {name: values.shape for name, values in rendered.items()} == {
        "master": (4600, 2), "left": (4600, 2), "right": (4600, 2),
    }
    np.testing.assert_allclose(rendered["master"], rendered["left"] + rendered["right"], atol=2e-5)


@pytest.mark.parametrize("archetype", list(ReferenceArchetype))
def test_reference_renderer_enforces_target_continuity_and_tail_contract(archetype):
    rendered = render_reference_template(_instance(archetype), _render_inputs(), time_fit_backend="scipy")
    assert rendered.audio.ndim == 2 and rendered.audio.shape[1] == 2
    assert np.isfinite(rendered.audio).all()
    assert np.max(np.abs(rendered.audio)) < .999
    assert 0 < rendered.landing_sample < len(rendered.audio)
    proof = rendered.provenance
    assert proof["target_stream_contract"] == _instance(archetype).choreography["target_stream"]
    assert proof["target_establishment_bars"] == 8
    if archetype == ReferenceArchetype.RESET_RELEASE:
        assert proof["target_time_map_backend"] == "natural_target_master_no_stretch"
        assert proof["fx_tail"]["fx_tail_end_sec_relative_landing"] <= 0
    else:
        assert proof["target_time_map_backend"] == "scipy_shared_multichannel_fallback"
    if archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        tail = proof["fx_tail"]
        assert tail["loop_state_continuous_at_landing"] is True
        assert tail["fx_tail_end_sec_relative_landing"] <= (
            tail["target_vocal_onset_sec_relative_landing"] - tail["tail_margin_before_target_vocal_sec"]
        )
    elif archetype != ReferenceArchetype.RESET_RELEASE:
        assert proof["fx_tail"]["fx_tail_end_sec_relative_landing"] <= 0


def test_loop_build_render_is_sample_deterministic():
    instance, inputs = _instance(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF), _render_inputs()
    first = render_reference_template(instance, inputs, time_fit_backend="scipy")
    second = render_reference_template(instance, inputs, time_fit_backend="scipy")
    np.testing.assert_array_equal(first.audio, second.audio)
    assert first.provenance == second.provenance


def test_target_trim_override_preserves_a_previously_approved_target_gain():
    rendered = render_reference_template(
        _instance(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF),
        replace(_render_inputs(), target_trim_db_override=-1.25),
        time_fit_backend="scipy",
    )
    assert rendered.provenance["target_trim_db"] == -1.25
    assert rendered.provenance["target_trim_source"] == "override"
    with pytest.raises(ValueError, match="target trim override"):
        render_reference_template(
            _instance(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF),
            replace(_render_inputs(), target_trim_db_override=20.0),
            time_fit_backend="scipy",
        )


def test_loop_build_tail_sample_quantization_never_exceeds_vocal_margin():
    target = replace(_analysis(source=False), vocal_regions=[(32.00019, 35.0)])
    instance = assess_reference_template_pair(
        _analysis(source=True),
        target,
        ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
        source_track_id="source-hash",
        target_track_id="target-hash",
        source_duration_sec=62,
        target_duration_sec=62,
    ).instance
    assert instance is not None
    inputs = replace(_render_inputs(), target_analysis=target)
    rendered = render_reference_template(instance, inputs, time_fit_backend="scipy")
    tail = rendered.provenance["fx_tail"]
    assert tail["fx_tail_end_sec_relative_landing"] <= (
        tail["target_vocal_onset_sec_relative_landing"] - tail["tail_margin_before_target_vocal_sec"]
    )


def test_catalog_documents_every_requested_archetype_constraint():
    assert set(ARCHETYPE_DEFINITIONS) == set(ReferenceArchetype)
    for definition in ARCHETYPE_DEFINITIONS.values():
        assert definition.suitable_source_sections
        assert definition.suitable_target_sections
        assert definition.vocal_requirements
        assert definition.target_cue_requirements
        assert definition.source_side_actions
        assert definition.shared_territory_actions
        assert definition.target_reveal_sequence
        assert definition.failure_conditions
        assert definition.variable_parameters
        assert definition.fixed_parameters


def _assessment(archetype, source=None, target=None):
    return assess_reference_template_pair(
        source or _analysis(source=True),
        target or _analysis(source=False),
        archetype,
        source_track_id="source-hash",
        target_track_id="target-hash",
        source_duration_sec=62,
        target_duration_sec=62,
    )


def test_pair_assessment_is_deterministic_and_is_not_an_audition_result():
    first = _assessment(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF)
    second = _assessment(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF)
    assert first == second
    assert first.eligible is True
    assert first.fit_score > 0
    assert first.instance is not None
    assert "target_vocal_onset_sec_after_landing" in first.evidence
    assert first.evidence["source_cue_bass_ratio"] == pytest.approx(.31)
    assert first.evidence["target_bass_change_at_landing"] > 0
    assert first.evidence["phrase_compatibility"]["target_runway_and_body_are_adjacent"] is True
    assert "audition" not in first.to_dict()


def test_loop_build_pair_rejects_target_vocal_at_landing():
    target = replace(_analysis(source=False), vocal_regions=[(29.5, 35.0)])
    result = _assessment(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF, target=target)
    assert result.eligible is False
    assert "target vocal begins at landing" in " ".join(result.rejection_reasons)
    assert result.fit_score == 0


def test_reset_pair_requires_hook_space_reset_need_and_landing_lift():
    source = replace(_analysis(source=True), vocal_regions=[(40.0, 44.0)], bpm=160, camelot="1A")
    target = replace(_analysis(source=False), bpm=100, camelot="7B")
    accepted = _assessment(ReferenceArchetype.RESET_RELEASE, source=source, target=target)
    assert accepted.eligible is True
    rejected = _assessment(
        ReferenceArchetype.RESET_RELEASE,
        source=replace(source, vocal_regions=[]),
        target=target,
    )
    assert "no self-contained repeatable motif" in " ".join(rejected.rejection_reasons)


def test_restrained_pair_rejects_large_groove_difference():
    source = replace(
        _analysis(source=True),
        groove_profile={"onbeat_fraction": 0.0, "syncopation_index": 0.0, "percussion_density_mean": 0.0},
        camelot="8A",
    )
    target = replace(
        _analysis(source=False),
        groove_profile={"onbeat_fraction": 1.0, "syncopation_index": 1.0, "percussion_density_mean": 1.0},
        camelot="8A",
    )
    result = _assessment(ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND, source=source, target=target)
    assert result.eligible is False
    assert "groove difference" in " ".join(result.rejection_reasons)


def test_f_source_entry_moves_off_an_interrupted_vocal_unit():
    source = replace(
        _analysis(source=True),
        vocal_regions=[(18.0, 27.9), (38.0, 50.0)],
        bpm=160,
        camelot="1A",
    )
    target = replace(_analysis(source=False), bpm=100, camelot="7B")
    result = _assessment(ReferenceArchetype.RESET_RELEASE, source=source, target=target)
    assert result.eligible is True
    entry = result.evidence["source_entry"]
    assert entry["adjusted"] is True
    assert entry["baseline"]["active_vocal_remaining_sec"] > .75
    assert entry["selected"]["active_vocal_remaining_sec"] <= .75
    assert entry["selected"]["final_bar_vocal_coverage"] >= .25


def test_b8_source_entry_moves_to_instrumental_gap_when_baseline_is_unstable():
    source = replace(
        _analysis(source=True),
        vocal_regions=[(22.0, 31.0), (38.0, 44.0)],
    )
    result = _assessment(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF, source=source)
    assert result.eligible is True
    entry = result.evidence["source_entry"]
    assert entry["adjusted"] is True
    assert entry["selection_rule"] == "instrumental_gap"
    assert entry["baseline"]["vocal_active"] is True
    assert entry["selected"]["vocal_active"] is False
    assert entry["selected"]["distance_until_next_vocal_sec"] is None or (
        entry["selected"]["distance_until_next_vocal_sec"] >= .75
    )
    assert entry["source_phrase_duration_change_sec"] == 0
    rendered = render_reference_template(
        result.instance,
        replace(_render_inputs(), source_analysis=source),
        time_fit_backend="scipy",
    )
    assert rendered.provenance["fx_tail"]["source_loop_entry_crossfade"] == "adaptive_equal_power_4.00_to_4.22"


def test_restrained_pair_rejects_dense_harmonically_weak_shared_territory():
    source = replace(_analysis(source=True), camelot="8A")
    target = replace(_analysis(source=False), camelot="11A")
    source.section_profiles[1]["drum_density"] = .88
    target.section_profiles[1]["drum_density"] = .90
    result = _assessment(ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND, source=source, target=target)
    reasons = " ".join(result.rejection_reasons)
    assert result.eligible is False
    assert "global harmonic compatibility" in reasons
    assert "arrangement density" in reasons


def test_target_and_pair_context_remain_inspectable_not_opaque():
    result = _assessment(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF)
    assert result.eligible is True
    assert result.evidence["target_entry"]["landing_is_downbeat"] is True
    assert "runway_bass_ratio" in result.evidence["target_entry"]
    assert set(result.evidence["pair_context"]) >= {
        "tempo_delta_pct", "groove_distance", "harmonic_compatibility",
        "source_to_target_energy_change", "stem_quality_scope",
    }
