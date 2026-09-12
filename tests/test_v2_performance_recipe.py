from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest
import soundfile as sf

from djenius.audio.performance_renderer import render_performance_mix
from djenius.core.models import (
    PerformanceAppearance,
    PerformanceSegment,
    PerformanceTimeline,
    PerformanceTransition,
    SetPlan,
    TrackAnalysis,
    TrackMetadata,
    TrackProfile,
    TransitionType,
)
from djenius.core.performance_recipe import (
    ActionType,
    MusicalPosition,
    PerformanceRecipe,
    Quantization,
    RecipeAction,
    RecipeCompileContext,
    TrackRole,
    compile_performance_recipe,
    compiled_recipe_to_transition,
    proof_recipe,
    require_valid_performance_recipe,
    validate_performance_recipe,
)

TECHNIQUES = ("eq_blend", "bass_swap", "phrase_cut", "loop_transition", "echo_release")
EXPECTED_TYPES = {
    "eq_blend": TransitionType.BEATMATCHED_BLEND,
    "bass_swap": TransitionType.BASS_SWAP,
    "phrase_cut": TransitionType.PHRASE_CUT,
    "loop_transition": TransitionType.LOOP_BLEND,
    "echo_release": TransitionType.ECHO_OUT,
}


def context(*, source_bpm=120.0, target_bpm=120.0, source=(0.0, 16.0), target=(0.0, 16.0), source_duration=20.0, target_duration=20.0, source_stems=frozenset(), target_stems=frozenset()):
    return RecipeCompileContext(
        source_appearance_id="source-app",
        target_appearance_id="target-app",
        source_segment_start_sec=source[0],
        source_segment_end_sec=source[1],
        target_segment_start_sec=target[0],
        target_segment_end_sec=target[1],
        source_track_duration_sec=source_duration,
        target_track_duration_sec=target_duration,
        source_bpm=source_bpm,
        target_bpm=target_bpm,
        available_source_stems=source_stems,
        available_target_stems=target_stems,
    )


def test_all_five_proof_recipes_validate_and_have_deterministic_ids():
    ctx = context()
    for technique in TECHNIQUES:
        first = proof_recipe(technique, "source", "target", bars=2)
        second = proof_recipe(technique, "source", "target", bars=2)
        assert validate_performance_recipe(first, ctx) == []
        assert first.recipe_id == second.recipe_id
        assert [item.action_id for item in first.actions] == [item.action_id for item in second.actions]
        assert first.recipe_id.startswith("r2_")
        assert all(item.action_id.startswith("a2_") for item in first.actions)


def test_recipe_roundtrip_preserves_ids_and_payload():
    recipe = proof_recipe("eq_blend", "source", "target", bars=4)
    restored = PerformanceRecipe.from_dict(json.loads(json.dumps(recipe.to_dict())))
    assert restored.to_dict() == recipe.to_dict()
    assert restored.with_deterministic_ids().to_dict() == recipe.to_dict()


def test_ids_are_canonical_across_dictionary_insertion_order():
    action_a = RecipeAction(ActionType.GAIN, MusicalPosition(1, 1), TrackRole.TARGET, {"gain_db": -6.0, "curve": "smooth"})
    action_b = RecipeAction(ActionType.GAIN, MusicalPosition(1, 1), TrackRole.TARGET, {"curve": "smooth", "gain_db": -6.0})
    left = PerformanceRecipe("eq_blend", "a", "b", 2, (action_a,), metadata={"z": 1, "a": 2}).with_deterministic_ids()
    right = PerformanceRecipe("eq_blend", "a", "b", 2, (action_b,), metadata={"a": 2, "z": 1}).with_deterministic_ids()
    assert left.recipe_id == right.recipe_id
    assert left.actions[0].action_id == right.actions[0].action_id


def test_tampered_recipe_and_action_ids_are_rejected():
    recipe = proof_recipe("bass_swap", "a", "b", bars=2)
    bad_recipe = replace(recipe, recipe_id="r2_deadbeef")
    assert "recipe_id does not match" in " ".join(validate_performance_recipe(bad_recipe, context()))
    actions = list(recipe.actions)
    actions[0] = replace(actions[0], action_id="a2_deadbeef")
    bad_action = replace(recipe, actions=tuple(actions))
    assert "action 1 id does not match" in " ".join(validate_performance_recipe(bad_action, context()))


def test_musical_position_uses_one_based_bar_and_beat_clock():
    assert MusicalPosition(1, 1).beat_offset == 0
    assert MusicalPosition(1, 4).beat_offset == 3
    assert MusicalPosition(2, 1).beat_offset == 4
    assert MusicalPosition(3, 2).beat_offset == 9


def test_quantization_rules_reject_off_grid_actions():
    bar_action = RecipeAction(ActionType.GAIN, MusicalPosition(2, 2), TrackRole.TARGET, {"gain_db": -3.0}, quantization=Quantization.BAR)
    phrase_action = RecipeAction(ActionType.GAIN, MusicalPosition(2, 1), TrackRole.TARGET, {"gain_db": -3.0}, quantization=Quantization.PHRASE)
    recipe = PerformanceRecipe("eq_blend", "a", "b", 4, (bar_action, phrase_action)).with_deterministic_ids()
    errors = " ".join(validate_performance_recipe(recipe, context()))
    assert "bar quantization off the downbeat" in errors
    assert "phrase quantization requires a phrase index" in errors


def test_phrase_quantization_accepts_labeled_downbeat():
    action = RecipeAction(ActionType.GAIN, MusicalPosition(3, 1, phrase=2), TrackRole.TARGET, {"gain_db": -3.0}, quantization=Quantization.PHRASE)
    recipe = PerformanceRecipe("eq_blend", "a", "b", 4, (action,)).with_deterministic_ids()
    assert validate_performance_recipe(recipe, context()) == []


@pytest.mark.parametrize(
    "action, expected",
    [
        (RecipeAction(ActionType.START, MusicalPosition(), TrackRole.TARGET, {"gain_db": 20.0}), "gain_db outside"),
        (RecipeAction(ActionType.ECHO, MusicalPosition(), TrackRole.SOURCE, {"wet": 1.2, "feedback": 0.4}), "wet outside"),
        (RecipeAction(ActionType.ECHO, MusicalPosition(), TrackRole.SOURCE, {"wet": 0.2, "feedback": 0.95}), "feedback outside"),
        (RecipeAction(ActionType.FILTER_HP, MusicalPosition(), TrackRole.SOURCE, {"cutoff_hz": 25000}), "cutoff_hz outside"),
        (RecipeAction(ActionType.LOOP_START, MusicalPosition(), TrackRole.SOURCE, {"length_beats": 64}), "length_beats outside"),
    ],
)
def test_parameter_validation_rejects_unsafe_values(action, expected):
    recipe = PerformanceRecipe("eq_blend", "a", "b", 2, (action,)).with_deterministic_ids()
    assert expected in " ".join(validate_performance_recipe(recipe, context()))


def test_invalid_structure_and_action_order_are_rejected():
    later = RecipeAction(ActionType.GAIN, MusicalPosition(2, 1), TrackRole.TARGET, {"gain_db": -3.0})
    earlier = RecipeAction(ActionType.GAIN, MusicalPosition(1, 1), TrackRole.TARGET, {"gain_db": -6.0})
    recipe = PerformanceRecipe("unknown", "a", "a", 0, (later, earlier)).with_deterministic_ids()
    errors = " ".join(validate_performance_recipe(recipe))
    assert "unsupported V2 technique" in errors
    assert "two different tracks" in errors
    assert "bars must be" in errors
    assert "actions are not in deterministic musical-time order" in errors


def test_segment_bounds_and_track_bounds_are_independently_validated():
    recipe = proof_recipe("eq_blend", "a", "b", bars=4)
    too_short = context(source=(0, 6), target=(0, 8))
    assert "recipe exceeds source segment bounds" in validate_performance_recipe(recipe, too_short)
    out_of_track = context(source=(-1, 10), target=(0, 21), source_duration=20, target_duration=20)
    errors = validate_performance_recipe(recipe, out_of_track)
    assert "source segment exceeds track bounds" in errors
    assert "target segment exceeds track bounds" in errors
    empty = context(source=(4, 4), target=(3, 2))
    errors = validate_performance_recipe(proof_recipe("eq_blend", "a", "b", bars=2), empty)
    assert "source segment has no duration" in errors
    assert "target segment has no duration" in errors


def test_loop_state_machine_rejects_invalid_sequences():
    end_only = PerformanceRecipe("loop_transition", "a", "b", 2, (
        RecipeAction(ActionType.LOOP_END, MusicalPosition(1, 1), TrackRole.SOURCE),
    )).with_deterministic_ids()
    assert "ends a loop that is not active" in " ".join(validate_performance_recipe(end_only, context()))

    open_only = PerformanceRecipe("loop_transition", "a", "b", 2, (
        RecipeAction(ActionType.LOOP_START, MusicalPosition(1, 1), TrackRole.SOURCE, {"length_beats": 2}),
    )).with_deterministic_ids()
    assert "leaves a loop active" in " ".join(validate_performance_recipe(open_only, context()))

    nested = PerformanceRecipe("loop_transition", "a", "b", 2, (
        RecipeAction(ActionType.LOOP_START, MusicalPosition(1, 1), TrackRole.SOURCE, {"length_beats": 2}),
        RecipeAction(ActionType.LOOP_START, MusicalPosition(1, 2), TrackRole.SOURCE, {"length_beats": 1}),
        RecipeAction(ActionType.LOOP_END, MusicalPosition(1, 3), TrackRole.SOURCE),
    )).with_deterministic_ids()
    assert "starts a loop while another loop is open" in " ".join(validate_performance_recipe(nested, context()))


def test_loop_length_requires_active_loop():
    recipe = PerformanceRecipe("loop_transition", "a", "b", 2, (
        RecipeAction(ActionType.LOOP_LENGTH, MusicalPosition(1, 1), TrackRole.SOURCE, {"length_beats": 1}),
    )).with_deterministic_ids()
    assert "changes loop length without an active loop" in " ".join(validate_performance_recipe(recipe, context()))


def test_stem_validation_checks_role_name_and_availability():
    action = RecipeAction(ActionType.STEM_MUTE, MusicalPosition(1, 1), TrackRole.SOURCE, {"stem": "vocals"})
    recipe = PerformanceRecipe("eq_blend", "a", "b", 2, (action,)).with_deterministic_ids()
    assert "source stem unavailable: vocals" in validate_performance_recipe(recipe, context())
    assert validate_performance_recipe(recipe, context(source_stems=frozenset({"vocals"}))) == []

    bad_role = replace(action, track_role=TrackRole.MASTER)
    bad_recipe = replace(recipe, actions=(bad_role,)).with_deterministic_ids()
    assert "requires source or target track role" in " ".join(validate_performance_recipe(bad_recipe, context(source_stems=frozenset({"vocals"}))))

    bad_name = replace(action, parameters={"stem": "lead"})
    bad_recipe = replace(recipe, actions=(bad_name,)).with_deterministic_ids()
    assert "requires a known stem" in " ".join(validate_performance_recipe(bad_recipe, context()))


def test_compilation_is_deterministic_in_musical_time():
    recipe = proof_recipe("eq_blend", "a", "b", bars=4)
    ctx = context(source_bpm=120, target_bpm=120)
    first = compile_performance_recipe(recipe, ctx)
    second = compile_performance_recipe(recipe, ctx)
    assert first == second
    assert first.clock_bpm == 120.0
    assert first.recipe_duration_sec == 8.0
    assert first.overlap_duration_sec == 8.0
    assert first.source_start_sec == 8.0
    assert first.source_end_sec == 16.0
    assert first.target_start_sec == 0.0
    assert first.target_end_sec == 8.0
    assert first.action_schedule[0]["time_sec"] == 0.0
    assert any(item["time_sec"] == 2.0 for item in first.action_schedule if item["position"]["bar"] == 2)
    assert all("quantization" in item and "order" in item and "end_time_sec" in item for item in first.action_schedule)


def test_target_clock_changes_recipe_seconds_deterministically():
    recipe = replace(proof_recipe("eq_blend", "a", "b", bars=2), clock_role=TrackRole.TARGET).with_deterministic_ids()
    compiled = compile_performance_recipe(recipe, context(source_bpm=120, target_bpm=100))
    assert compiled.clock_bpm == 100.0
    assert compiled.recipe_duration_sec == 4.8
    assert compiled.overlap_duration_sec == 4.8


def test_eq_blend_compiler_declares_stretch_and_target_consumption():
    recipe = proof_recipe("eq_blend", "a", "b", bars=2)
    compiled = compile_performance_recipe(recipe, context(source_bpm=120, target_bpm=100))
    assert compiled.requires_stretch is True
    assert compiled.target_consumed_duration_sec == pytest.approx(4.8, abs=1e-6)
    transition = compiled_recipe_to_transition(compiled, context(source_bpm=120, target_bpm=100))
    assert transition.requires_stretch is True
    assert transition.target_consumed_duration_sec == pytest.approx(4.8, abs=1e-6)


@pytest.mark.parametrize("technique", TECHNIQUES)
def test_compilation_targets_existing_performance_transition_contract(technique):
    ctx = context()
    recipe = proof_recipe(technique, "source", "target", bars=2)
    compiled = compile_performance_recipe(recipe, ctx)
    transition = compiled_recipe_to_transition(compiled, ctx)
    assert transition.transition_type == EXPECTED_TYPES[technique]
    assert transition.performance_recipe == compiled.recipe.to_dict()
    assert transition.recipe_action_schedule == list(compiled.action_schedule)
    assert transition.execution_directive["compiler"] == "v2_phase2_legacy_transition_adapter"
    assert transition.execution_directive["recipe_id"] == recipe.recipe_id
    assert transition.length_bars == 2
    restored = PerformanceTransition.from_dict(transition.to_dict())
    assert restored.to_dict() == transition.to_dict()


def test_require_valid_recipe_raises_with_all_violations():
    recipe = PerformanceRecipe("eq_blend", "", "", 0, ()).with_deterministic_ids()
    with pytest.raises(ValueError, match="Invalid performance recipe"):
        require_valid_performance_recipe(recipe, context())


def _write_track(path, frequency, sr=8000, seconds=20):
    t = np.arange(sr * seconds, dtype=np.float32) / sr
    signal = 0.12 * np.sin(2 * np.pi * frequency * t)
    signal += 0.025 * np.sin(2 * np.pi * frequency * 2.0 * t)
    sf.write(path, np.column_stack([signal, signal * 0.97]).astype(np.float32), sr)


def _track(track_id, path, bpm=120.0, duration=20.0):
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=str(path), title=track_id, duration_sec=duration, sample_rate=8000, channels=2),
        analysis=TrackAnalysis(bpm=bpm, bpm_confidence=0.99, analysis_confidence=0.99, energy_curve=[0.5] * int(duration), low_energy_curve=[0.3] * int(duration)),
    )


@pytest.mark.parametrize("technique", TECHNIQUES)
def test_all_five_proof_recipes_render_synthetic_audio_with_clean_provenance(tmp_path, technique):
    sr = 8000
    source_path = tmp_path / f"source-{technique}.wav"
    target_path = tmp_path / f"target-{technique}.wav"
    _write_track(source_path, 110, sr=sr)
    _write_track(target_path, 176, sr=sr)
    tracks = [_track("source", source_path), _track("target", target_path)]

    ctx = context()
    recipe = proof_recipe(technique, "source", "target", bars=2)
    compiled = compile_performance_recipe(recipe, ctx)
    transition = compiled_recipe_to_transition(compiled, ctx)
    overlap = compiled.overlap_duration_sec
    first = PerformanceSegment(id="source-segment", track_id="source", source_start_sec=0.0, source_end_sec=16.0, confidence=0.99)
    second = PerformanceSegment(id="target-segment", track_id="target", source_start_sec=0.0, source_end_sec=16.0, confidence=0.99)
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="source-app", segment=first, output_start_sec=0.0, output_end_sec=16.0),
            PerformanceAppearance(id="target-app", segment=second, output_start_sec=16.0 - overlap, output_end_sec=32.0 - overlap),
        ],
        transitions=[transition],
        total_duration_sec=32.0 - overlap,
        target_duration_sec=32.0 - overlap,
        performance_style="experimental",
    )
    plan = SetPlan(tracks=tracks, performance_mode="segment", performance_style="experimental", performance_timeline=timeline)
    output = tmp_path / f"render-{technique}.wav"
    result = render_performance_mix(plan, str(output), sample_rate=sr)
    assert output.is_file()
    assert result["provenance_audit"]["clean"]
    assert result["transitions_rendered"] == 1
    assert result["duration_sec"] > 0
    diagnostics = json.loads((tmp_path / f"render-{technique}_diagnostics.json").read_text())
    event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    assert event["transition_type"] == EXPECTED_TYPES[technique].value
    assert event["technique_name"] == technique.replace("_", " ")


def test_recipe_fields_are_additive_for_old_performance_transition_payloads():
    old = PerformanceTransition(
        source_appearance_id="a",
        target_appearance_id="b",
        transition_type=TransitionType.CROSSFADE,
        overlap_duration_sec=2.0,
    )
    payload = old.to_dict()
    payload.pop("performance_recipe")
    payload.pop("recipe_action_schedule")
    restored = PerformanceTransition.from_dict(payload)
    assert restored.performance_recipe == {}
    assert restored.recipe_action_schedule == []
