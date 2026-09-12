from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest
import soundfile as sf

from djenius.audio.groove_sampler import (
    render_performance_sample_layer,
    synthesize_procedural_sound,
)
from djenius.audio.performance_renderer import render_performance_mix
from djenius.audio.provenance import audit_performance_provenance
from djenius.core.groove import (
    GroovePattern,
    MusicalSubdivision,
    PatternStep,
    PerformanceSampleEvent,
    backbeat_pattern,
    builtin_groove_pattern,
    four_on_floor_pattern,
    offbeat_hats_pattern,
    percussion_bridge_pattern,
    short_drum_fill_pattern,
)
from djenius.core.models import (
    PerformanceAppearance,
    PerformanceSegment,
    PerformanceTimeline,
    PerformanceTransition,
    SetPlan,
    TrackAnalysis,
    TrackMetadata,
    TrackProfile,
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
    phase3_recipe,
    validate_performance_recipe,
)

SR = 4000
ALL_GENERATORS = (
    "kick_v1", "snare_v1", "clap_v1", "closed_hat_v1", "open_hat_v1",
    "noise_riser_v1", "downlifter_v1", "impact_v1", "reverse_cymbal_v1",
)


def _context(*, bpm: float = 120.0) -> RecipeCompileContext:
    return RecipeCompileContext(
        source_appearance_id="source-app",
        target_appearance_id="target-app",
        source_segment_start_sec=0.0,
        source_segment_end_sec=8.0,
        target_segment_start_sec=0.0,
        target_segment_end_sec=8.0,
        source_track_duration_sec=10.0,
        target_track_duration_sec=10.0,
        source_bpm=bpm,
        target_bpm=bpm,
    )


def _recipe(actions, *, bars: int = 2, technique: str = "eq_blend") -> PerformanceRecipe:
    ordered = tuple(sorted(actions, key=lambda item: (item.position.beat_offset, item.order, item.action.value)))
    return PerformanceRecipe(
        technique=technique,
        source_track_id="source",
        target_track_id="target",
        bars=bars,
        actions=ordered,
        metadata={"phase": 4, "purpose": "phase4_test"},
    ).with_deterministic_ids()


def _sample_action(
    generator: str,
    *,
    bar: int = 1,
    beat: int = 1,
    subdivision: int = 0,
    grid: int = 1,
    duration_beats: float = 0.0,
    quantization: Quantization = Quantization.BEAT,
    order: int = 0,
    seed: int = 123,
    gain_db: float = -3.0,
    level: float = 0.03,
) -> RecipeAction:
    return RecipeAction(
        action=ActionType.SAMPLE,
        position=MusicalPosition(
            bar=bar, beat=beat, subdivision=subdivision,
            subdivisions_per_beat=grid,
        ),
        track_role=TrackRole.GENERATED,
        parameters={
            "generator": generator,
            "seed": seed,
            "gain_db": gain_db,
            "level": level,
        },
        duration_beats=duration_beats,
        quantization=quantization,
        order=order,
    )


def _pattern_action(name: str, *, bar: int = 1, beat: int = 1, repetitions: int = 1, seed: int = 33) -> RecipeAction:
    return RecipeAction(
        action=ActionType.DRUM_PATTERN,
        position=MusicalPosition(bar=bar, beat=beat),
        track_role=TrackRole.GENERATED,
        parameters={
            "pattern_name": name,
            "repetitions": repetitions,
            "seed": seed,
            "gain_db": -2.0,
            "level": 0.03,
            "velocity": 0.9,
        },
    )


def _event(generator: str = "kick_v1", **changes) -> PerformanceSampleEvent:
    base = PerformanceSampleEvent(
        event_id="",
        source_type="procedural_percussion" if generator.endswith(("kick_v1", "snare_v1", "clap_v1", "hat_v1")) else "generated_fx",
        generator=generator,
        time_sec=0.25,
        duration_sec=0.25,
        level=0.03,
        gain_db=-3.0,
        velocity=0.8,
        seed=123,
        recipe_id="r2_test",
        action_id="a2_test",
        musical_position={"bar": 1, "beat": 1, "subdivision": 1, "subdivisions_per_beat": 4},
        subdivision=4,
        provenance={"bar": 1, "beat": 1},
    )
    return replace(base, **changes).with_deterministic_id()


def test_deterministic_event_and_pattern_ids():
    assert _event().event_id == _event().event_id
    assert four_on_floor_pattern().pattern_id == four_on_floor_pattern().pattern_id
    assert _event(seed=124).event_id != _event(seed=123).event_id


def test_event_and_pattern_round_trip_serialization():
    event = _event("impact_v1", source_type="generated_fx")
    assert PerformanceSampleEvent.from_dict(event.to_dict()).to_dict() == event.to_dict()
    pattern = percussion_bridge_pattern()
    assert GroovePattern.from_dict(pattern.to_dict()).to_dict() == pattern.to_dict()


@pytest.mark.parametrize(
    "position,quantization,expected_sec",
    [
        (MusicalPosition(bar=1, beat=2), Quantization.BEAT, 0.5),
        (MusicalPosition(bar=1, beat=1, subdivision=1, subdivisions_per_beat=2), Quantization.EIGHTH, 0.25),
        (MusicalPosition(bar=1, beat=1, subdivision=3, subdivisions_per_beat=4), Quantization.SIXTEENTH, 0.375),
    ],
)
def test_quarter_eighth_sixteenth_compilation(position, quantization, expected_sec):
    action = replace(_sample_action("kick_v1"), position=position, quantization=quantization)
    compiled = compile_performance_recipe(_recipe([action]), _context())
    assert compiled.sample_layer_events[0]["time_sec"] == pytest.approx(expected_sec)


@pytest.mark.parametrize("grid", [0, 3, 8])
def test_invalid_subdivision_rejected(grid):
    action = replace(
        _sample_action("kick_v1"),
        position=MusicalPosition(bar=1, beat=1, subdivision=0, subdivisions_per_beat=grid),
    )
    assert "subdivisions_per_beat" in " ".join(validate_performance_recipe(_recipe([action]), _context()))
    with pytest.raises((ValueError, TypeError)):
        GroovePattern.from_dict({"name": "bad", "length_beats": 1, "subdivision": grid, "steps": []})


@pytest.mark.parametrize(
    "event,needle",
    [
        (_event(source_type="generated_fx"), "source_type"),
        (_event(gain_db=1.0), "gain_db"),
        (_event(duration_sec=0.0), "duration_sec"),
        (_event(seed=-1), "seed"),
        (_event(level=0.0), "level"),
    ],
)
def test_invalid_event_parameters_fail_closed(event, needle):
    assert needle in " ".join(event.validate())


def test_malformed_event_integer_fields_are_not_silently_coerced():
    payload = _event().to_dict()
    payload["seed"] = 1.25
    with pytest.raises(ValueError, match="seed must be an integer"):
        PerformanceSampleEvent.from_dict(payload)
    payload = four_on_floor_pattern().to_dict()
    payload["subdivision"] = 2.5
    with pytest.raises(ValueError, match="pattern subdivision must be an integer"):
        GroovePattern.from_dict(payload)


def test_recipe_sample_parameter_validation():
    bad_gain = replace(_sample_action("kick_v1"), parameters={"generator": "kick_v1", "gain_db": 3.0, "level": 0.03})
    bad_seed = replace(_sample_action("kick_v1"), parameters={"generator": "kick_v1", "seed": 1.5, "level": 0.03})
    bad_generator = _sample_action("invented_v1")
    errors = " ".join(validate_performance_recipe(_recipe([bad_gain, bad_seed, bad_generator]), _context()))
    assert "gain_db" in errors and "seed" in errors and "supported procedural generator" in errors


@pytest.mark.parametrize("generator", ALL_GENERATORS)
def test_all_procedural_generators_are_deterministic_finite_non_silent(generator):
    a = synthesize_procedural_sound(generator, SR, duration_sec=0.25, level=0.03, seed=17, channels=1)
    b = synthesize_procedural_sound(generator, SR, duration_sec=0.25, level=0.03, seed=17, channels=1)
    assert a.ndim == 1 and len(a) == round(0.25 * SR)
    assert np.array_equal(a, b)
    assert np.isfinite(a).all()
    assert 1e-6 < float(np.max(np.abs(a))) <= 0.030001


@pytest.mark.parametrize("generator", ["snare_v1", "clap_v1", "closed_hat_v1", "open_hat_v1", "noise_riser_v1", "downlifter_v1", "impact_v1", "reverse_cymbal_v1"])
def test_noise_based_generators_change_with_seed(generator):
    a = synthesize_procedural_sound(generator, SR, duration_sec=0.25, seed=7, channels=1)
    b = synthesize_procedural_sound(generator, SR, duration_sec=0.25, seed=8, channels=1)
    assert not np.array_equal(a, b)


def test_mono_and_stereo_synthesis_and_dc_offset_are_safe():
    mono = synthesize_procedural_sound("kick_v1", SR, duration_sec=0.3, seed=2, channels=1)
    stereo = synthesize_procedural_sound("kick_v1", SR, duration_sec=0.3, seed=2, channels=2)
    assert mono.shape == (round(0.3 * SR),)
    assert stereo.shape == (round(0.3 * SR), 2)
    assert float(np.max(np.abs(np.mean(stereo, axis=0)))) < 0.005


def test_exact_sample_placement_gain_and_provenance():
    base = np.zeros((SR, 2), dtype=np.float32)
    event = _event(time_sec=0.25, duration_sec=0.20, gain_db=-6.0).to_dict()
    mixed, provenance = render_performance_sample_layer(base, SR, [event], output_start_sample=500)
    start = round(0.25 * SR)
    end = start + round(0.20 * SR)
    assert np.allclose(mixed[:start], 0.0)
    assert float(np.max(np.abs(mixed[start:end]))) > 1e-5
    assert np.allclose(mixed[end:], 0.0)
    assert provenance[0]["output_start_sample"] == 500 + start
    assert provenance[0]["output_end_sample"] == 500 + end
    assert provenance[0]["gain_db"] == -6.0
    assert provenance[0]["operation_owner"] == "groove_sample_layer"


def test_overlapping_events_mix_safely_and_peak_protection_works():
    base = np.full((SR, 2), 0.90, dtype=np.float32)
    events = [
        _event(time_sec=0.10, duration_sec=0.40, level=0.05, gain_db=0.0, seed=seed).to_dict()
        for seed in range(6)
    ]
    mixed, provenance = render_performance_sample_layer(base, SR, events)
    assert len(provenance) == 6
    assert np.isfinite(mixed).all()
    assert float(np.max(np.abs(mixed))) <= 0.950001
    assert any(item["safety_gain"] < 1.0 for item in provenance)


def _audit_transition_event(sample_provenance, *, declared_count=None, technique_operations=None):
    return {
        "type": "performance_transition",
        "source_track_id": "source",
        "target_track_id": "target",
        "source_start_sample": 100,
        "source_end_sample": 500,
        "target_start_sample": 0,
        "target_end_sample": 400,
        "output_start_sample": 1000,
        "output_end_sample": 1400,
        "technique_operations": list(technique_operations or []),
        "sample_layer_provenance": list(sample_provenance),
        "sample_layer_event_count": len(sample_provenance) if declared_count is None else declared_count,
    }


def _audit_sample(event_id: str, *, generator: str = "kick_v1", source_type: str = "procedural_percussion"):
    return {
        "event_id": event_id,
        "generator": generator,
        "recipe_id": "recipe-phase4-audit",
        "action_id": f"action-{event_id}",
        "source_type": source_type,
        "operation_owner": "groove_sample_layer",
        "musical_position": {"bar": 1, "beat": 1},
        "output_start_sample": 1100,
        "output_end_sample": 1200,
    }


def test_provenance_auditor_rejects_duplicate_sample_event_ids():
    samples = [_audit_sample("dup"), _audit_sample("dup")]
    audit = audit_performance_provenance(
        [_audit_transition_event(samples)], {"source": 1000, "target": 1000}
    )
    assert not audit["clean"]
    assert "duplicate_sample_event_id" in {item["kind"] for item in audit["violations"]}


def test_provenance_auditor_rejects_sample_layer_count_mismatch():
    sample = _audit_sample("one")
    audit = audit_performance_provenance(
        [_audit_transition_event([sample], declared_count=2)], {"source": 1000, "target": 1000}
    )
    assert not audit["clean"]
    assert "sample_layer_count_mismatch" in {item["kind"] for item in audit["violations"]}


def test_provenance_auditor_rejects_phase3_phase4_riser_ownership_conflict():
    sample = _audit_sample("riser", generator="noise_riser_v1", source_type="generated_fx")
    audit = audit_performance_provenance(
        [_audit_transition_event([sample], technique_operations=[{"type": "riser_impact"}])],
        {"source": 1000, "target": 1000},
    )
    assert not audit["clean"]
    assert "duplicate_riser_impact_ownership" in {item["kind"] for item in audit["violations"]}


def test_sampler_rejects_unsafe_dc_offset(monkeypatch):
    import djenius.audio.groove_sampler as sampler

    def fake_sound(*_args, **_kwargs):
        return np.full((400, 2), 0.03, dtype=np.float32)

    monkeypatch.setattr(sampler, "synthesize_procedural_sound", fake_sound)
    with pytest.raises(RuntimeError, match="DC offset"):
        sampler.render_performance_sample_layer(
            np.zeros((SR, 2), dtype=np.float32), SR,
            [_event(time_sec=0.0, duration_sec=0.1).to_dict()],
        )


@pytest.mark.parametrize(
    "name,factory,expected_generators",
    [
        ("four_on_floor", four_on_floor_pattern, {"kick_v1"}),
        ("backbeat", backbeat_pattern, {"snare_v1", "clap_v1"}),
        ("offbeat_hats", offbeat_hats_pattern, {"closed_hat_v1"}),
        ("short_drum_fill", short_drum_fill_pattern, {"snare_v1", "clap_v1", "open_hat_v1"}),
        ("percussion_bridge", percussion_bridge_pattern, {"kick_v1", "clap_v1", "closed_hat_v1", "open_hat_v1"}),
    ],
)
def test_builtin_patterns_are_valid_and_named(name, factory, expected_generators):
    pattern = factory()
    assert builtin_groove_pattern(name).to_dict() == pattern.to_dict()
    assert pattern.validate() == []
    assert {step.generator for step in pattern.steps} == expected_generators


def test_pattern_repetition_and_recipe_compilation_are_deterministic():
    recipe = _recipe([_pattern_action("four_on_floor", repetitions=2)], bars=2)
    assert validate_performance_recipe(recipe, _context()) == []
    first = compile_performance_recipe(recipe, _context())
    second = compile_performance_recipe(recipe, _context())
    assert first.sample_layer_events == second.sample_layer_events
    assert len(first.sample_layer_events) == 8
    assert [item["time_sec"] for item in first.sample_layer_events] == pytest.approx([i * 0.5 for i in range(8)])


def test_sample_layer_events_reach_transition_and_old_payload_is_compatible():
    compiled = compile_performance_recipe(_recipe([_sample_action("reverse_cymbal_v1")]), _context())
    transition = compiled_recipe_to_transition(compiled, _context())
    assert transition.sample_layer_events == list(compiled.sample_layer_events)
    assert transition.execution_directive["operation_ownership"]["groove_sample_layer"].endswith("groove_sampler")
    payload = transition.to_dict()
    payload.pop("sample_layer_events")
    restored = PerformanceTransition.from_dict(payload)
    assert restored.sample_layer_events == []


def test_phase3_riser_impact_is_not_double_rendered_and_phase4_transfers_ownership():
    phase3 = phase3_recipe("riser_impact", "source", "target", bars=2)
    c3 = compile_performance_recipe(phase3, _context())
    assert c3.sample_layer_events == ()
    assert [item["type"] for item in c3.technique_operations] == ["riser_impact"]

    phase4 = replace(phase3, metadata={"phase": 4, "purpose": "phase4_ownership"})
    c4 = compile_performance_recipe(phase4, _context())
    assert c4.technique_operations == ()
    assert {item["generator"] for item in c4.sample_layer_events} == {"noise_riser_v1", "impact_v1"}


def _scenario_actions(name: str):
    if name == "percussion_bridge":
        return [_pattern_action("percussion_bridge")]
    if name == "backbeat":
        return [_pattern_action("backbeat")]
    if name == "offbeat_hats":
        return [_pattern_action("offbeat_hats")]
    if name == "drum_fill":
        return [_pattern_action("short_drum_fill", bar=2, beat=1)]
    if name == "riser_impact":
        return [
            RecipeAction(ActionType.RISER, MusicalPosition(1, 1), TrackRole.GENERATED, {"seed": 4, "level": 0.025}, duration_beats=4.0),
            RecipeAction(ActionType.IMPACT, MusicalPosition(2, 1), TrackRole.GENERATED, {"seed": 5, "level": 0.03}),
        ]
    if name == "downlifter":
        return [RecipeAction(ActionType.DOWNLIFTER, MusicalPosition(1, 1), TrackRole.GENERATED, {"seed": 6, "level": 0.025}, duration_beats=4.0)]
    if name == "reverse_impact":
        return [
            _sample_action("reverse_cymbal_v1", bar=1, beat=3, duration_beats=2.0, seed=7),
            RecipeAction(ActionType.IMPACT, MusicalPosition(2, 1), TrackRole.GENERATED, {"seed": 8, "level": 0.03}),
        ]
    if name == "stacked_percussion_riser":
        return [
            _pattern_action("four_on_floor"),
            RecipeAction(ActionType.RISER, MusicalPosition(1, 1), TrackRole.GENERATED, {"seed": 9, "level": 0.02}, duration_beats=4.0, order=1),
        ]
    raise AssertionError(name)


@pytest.mark.parametrize(
    "scenario",
    ["percussion_bridge", "backbeat", "offbeat_hats", "drum_fill", "riser_impact", "downlifter", "reverse_impact", "stacked_percussion_riser"],
)
def test_controlled_phase4_scenarios_compile_and_render_deterministically(scenario):
    recipe = _recipe(_scenario_actions(scenario), bars=2)
    assert validate_performance_recipe(recipe, _context()) == []
    compiled = compile_performance_recipe(recipe, _context())
    base = np.zeros((round(compiled.overlap_duration_sec * SR), 2), dtype=np.float32)
    first, provenance = render_performance_sample_layer(base, SR, compiled.sample_layer_events)
    second, provenance2 = render_performance_sample_layer(base, SR, compiled.sample_layer_events)
    assert np.array_equal(first, second)
    assert first.shape == base.shape
    assert provenance == provenance2
    assert np.isfinite(first).all()
    assert float(np.max(np.abs(first))) <= 0.95
    assert float(np.max(np.abs(first))) > 1e-5
    assert len(provenance) == len(compiled.sample_layer_events)
    for declared, rendered in zip(compiled.sample_layer_events, provenance):
        assert rendered["output_start_sample"] == round(declared["time_sec"] * SR)
        assert rendered["output_end_sample"] - rendered["output_start_sample"] == round(declared["duration_sec"] * SR)
        assert rendered["event_id"] == declared["event_id"]
        assert rendered["recipe_id"] == declared["recipe_id"]
        assert rendered["action_id"] == declared["action_id"]
        assert rendered["generator"] == declared["generator"]
        assert rendered["musical_position"] == declared["musical_position"]
        assert rendered["operation_owner"] == "groove_sample_layer"


def _write_track(path, frequency: float, *, seconds: int = 8):
    t = np.arange(SR * seconds, dtype=np.float32) / SR
    signal = 0.10 * np.sin(2 * np.pi * frequency * t) + 0.02 * np.sin(2 * np.pi * frequency * 2 * t)
    sf.write(path, np.column_stack([signal, signal * 0.97]).astype(np.float32), SR)


def _track(track_id: str, path) -> TrackProfile:
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=str(path), title=track_id, duration_sec=8.0, sample_rate=SR, channels=2),
        analysis=TrackAnalysis(bpm=120.0, bpm_confidence=0.99, analysis_confidence=0.99, energy_curve=[0.5] * 8, low_energy_curve=[0.2] * 8),
    )


def _render_recipe(tmp_path, recipe: PerformanceRecipe, *, label: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.wav"
    target_path = tmp_path / "target.wav"
    _write_track(source_path, 110.0)
    _write_track(target_path, 176.0)
    ctx = _context()
    compiled = compile_performance_recipe(recipe, ctx)
    transition = compiled_recipe_to_transition(compiled, ctx)
    overlap = compiled.overlap_duration_sec
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="source-app", segment=PerformanceSegment(id="source-seg", track_id="source", source_start_sec=0.0, source_end_sec=8.0, confidence=0.99), output_start_sec=0.0, output_end_sec=8.0),
            PerformanceAppearance(id="target-app", segment=PerformanceSegment(id="target-seg", track_id="target", source_start_sec=0.0, source_end_sec=8.0, confidence=0.99), output_start_sec=8.0 - overlap, output_end_sec=16.0 - overlap),
        ],
        transitions=[transition], total_duration_sec=16.0 - overlap,
        target_duration_sec=16.0 - overlap, performance_style="phase4_test",
    )
    plan = SetPlan(tracks=[_track("source", source_path), _track("target", target_path)], performance_mode="segment", performance_style="phase4_test", performance_timeline=timeline)
    output = tmp_path / f"{label}.wav"
    result = render_performance_mix(plan, str(output), sample_rate=SR)
    diagnostics = json.loads((tmp_path / f"{label}_diagnostics.json").read_text())
    transition_event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    audio, _ = sf.read(output, dtype="float32")
    return audio, result, transition_event, transition


def test_real_renderer_path_mixes_sample_events_with_exact_provenance(tmp_path):
    recipe = _recipe([
        _sample_action("kick_v1", bar=1, beat=2, seed=11, gain_db=-4.0),
        _sample_action("clap_v1", bar=1, beat=2, seed=12, gain_db=-8.0, order=1),
    ])
    audio, result, event, _ = _render_recipe(tmp_path / "with", recipe, label="with-samples")
    assert audio.ndim == 2 and audio.shape[1] == 2 and np.isfinite(audio).all()
    assert result["provenance_audit"]["clean"]
    assert event["sample_layer_event_count"] == 2
    assert event["operation_ownership"]["groove_sample_layer"]
    transition_start = event["output_start_sample"]
    for item in event["sample_layer_provenance"]:
        assert item["operation_owner"] == "groove_sample_layer"
        assert item["output_start_sample"] >= transition_start
        assert item["output_end_sample"] <= event["output_end_sample"]
        assert item["recipe_id"] == recipe.recipe_id
        assert item["action_id"]
        assert item["gain_db"] in {-4.0, -8.0}


def test_real_renderer_sample_layer_differs_from_no_event_baseline_and_legacy_path_is_unchanged(tmp_path):
    recipe = _recipe([_pattern_action("offbeat_hats")])
    sample_audio, _, _, transition = _render_recipe(tmp_path / "sample", recipe, label="sample")

    legacy_transition = PerformanceTransition.from_dict({key: value for key, value in transition.to_dict().items() if key != "sample_layer_events"})
    empty_transition = replace(transition, sample_layer_events=[])
    assert legacy_transition.to_dict() == empty_transition.to_dict()

    def render_with_transition(path, trans, label):
        source_path = path / "source.wav"; target_path = path / "target.wav"
        path.mkdir(parents=True, exist_ok=True)
        _write_track(source_path, 110.0); _write_track(target_path, 176.0)
        overlap = trans.overlap_duration_sec
        timeline = PerformanceTimeline(
            appearances=[
                PerformanceAppearance(id="source-app", segment=PerformanceSegment(id="s", track_id="source", source_start_sec=0.0, source_end_sec=8.0, confidence=0.99), output_start_sec=0.0, output_end_sec=8.0),
                PerformanceAppearance(id="target-app", segment=PerformanceSegment(id="t", track_id="target", source_start_sec=0.0, source_end_sec=8.0, confidence=0.99), output_start_sec=8.0-overlap, output_end_sec=16.0-overlap),
            ], transitions=[trans], total_duration_sec=16.0-overlap, target_duration_sec=16.0-overlap,
        )
        plan = SetPlan(tracks=[_track("source", source_path), _track("target", target_path)], performance_mode="segment", performance_timeline=timeline)
        out = path / f"{label}.wav"; render_performance_mix(plan, str(out), sample_rate=SR)
        return sf.read(out, dtype="float32")[0]

    legacy_audio = render_with_transition(tmp_path / "legacy", legacy_transition, "legacy")
    empty_audio = render_with_transition(tmp_path / "empty", empty_transition, "empty")
    assert np.array_equal(legacy_audio, empty_audio)
    assert sample_audio.shape == empty_audio.shape
    assert not np.allclose(sample_audio, empty_audio, atol=1e-6)


def test_renderer_fails_closed_for_malformed_sample_event(tmp_path):
    recipe = _recipe([_sample_action("kick_v1")])
    compiled = compile_performance_recipe(recipe, _context())
    transition = compiled_recipe_to_transition(compiled, _context())
    malformed = dict(transition.sample_layer_events[0]); malformed["gain_db"] = 4.0
    transition = replace(transition, sample_layer_events=[malformed])

    source_path = tmp_path / "source.wav"; target_path = tmp_path / "target.wav"
    _write_track(source_path, 110.0); _write_track(target_path, 176.0)
    overlap = transition.overlap_duration_sec
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="source-app", segment=PerformanceSegment(id="s", track_id="source", source_start_sec=0.0, source_end_sec=8.0, confidence=0.99), output_start_sec=0.0, output_end_sec=8.0),
            PerformanceAppearance(id="target-app", segment=PerformanceSegment(id="t", track_id="target", source_start_sec=0.0, source_end_sec=8.0, confidence=0.99), output_start_sec=8.0-overlap, output_end_sec=16.0-overlap),
        ], transitions=[transition], total_duration_sec=16.0-overlap, target_duration_sec=16.0-overlap,
    )
    plan = SetPlan(tracks=[_track("source", source_path), _track("target", target_path)], performance_mode="segment", performance_timeline=timeline)
    with pytest.raises(ValueError, match="invalid sample event"):
        render_performance_mix(plan, str(tmp_path / "bad.wav"), sample_rate=SR)
