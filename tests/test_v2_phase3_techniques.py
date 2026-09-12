from __future__ import annotations

import json
import time

import numpy as np
import pytest
import soundfile as sf

from djenius.application import LocalAppService
from djenius.audio.creative_fx import (
    apply_creative_operations,
    loop_shorten,
    procedural_fx,
    reverb_wash,
)
from djenius.audio.performance_renderer import (
    _prepare_transition_stem_windows,
    render_performance_mix,
)
from djenius.audio.transitions import apply_transition
from djenius.core.models import (
    PerformanceAppearance,
    PerformanceSegment,
    PerformanceTimeline,
    SetPlan,
    TrackAnalysis,
    TrackMetadata,
    TrackProfile,
    TransitionType,
)
from djenius.core.performance_recipe import (
    RecipeCompileContext,
    compile_performance_recipe,
    compiled_recipe_to_transition,
    phase3_recipe,
    validate_performance_recipe,
)

ALL_TECHNIQUES = (
    "eq_blend",
    "bass_swap",
    "filter_blend",
    "phrase_cut",
    "echo_release",
    "reverb_wash",
    "loop_transition",
    "loop_shortening",
    "drum_overlay",
    "riser_impact",
    "tempo_reset",
    "stem_handoff",
)

EXPECTED_TYPES = {
    "eq_blend": TransitionType.BEATMATCHED_BLEND,
    "bass_swap": TransitionType.BASS_SWAP,
    "filter_blend": TransitionType.FILTER_SWEEP,
    "phrase_cut": TransitionType.PHRASE_CUT,
    "echo_release": TransitionType.ECHO_OUT,
    "reverb_wash": TransitionType.CROSSFADE,
    "loop_transition": TransitionType.LOOP_BLEND,
    "loop_shortening": TransitionType.CROSSFADE,
    "drum_overlay": TransitionType.CROSSFADE,
    "riser_impact": TransitionType.CROSSFADE,
    "tempo_reset": TransitionType.ECHO_OUT,
    "stem_handoff": TransitionType.MASHUP,
}


def _context(technique: str, *, source_bpm: float = 120.0, target_bpm: float = 120.0) -> RecipeCompileContext:
    source_stems: frozenset[str] = frozenset()
    target_stems: frozenset[str] = frozenset()
    if technique == "drum_overlay":
        target_stems = frozenset({"drums"})
    elif technique == "stem_handoff":
        source_stems = frozenset({"vocals"})
        target_stems = frozenset({"drums", "bass", "other"})
    return RecipeCompileContext(
        source_appearance_id="source-app",
        target_appearance_id="target-app",
        source_segment_start_sec=0.0,
        source_segment_end_sec=16.0,
        target_segment_start_sec=0.0,
        target_segment_end_sec=16.0,
        source_track_duration_sec=20.0,
        target_track_duration_sec=20.0,
        source_bpm=source_bpm,
        target_bpm=target_bpm,
        available_source_stems=source_stems,
        available_target_stems=target_stems,
    )


@pytest.mark.parametrize("technique", ALL_TECHNIQUES)
def test_phase3_complete_technique_matrix_validates_and_compiles(technique):
    recipe = phase3_recipe(technique, "source", "target", bars=2)
    ctx = _context(technique)
    assert validate_performance_recipe(recipe, ctx) == []
    compiled = compile_performance_recipe(recipe, ctx)
    transition = compiled_recipe_to_transition(compiled, ctx)
    assert transition.transition_type == EXPECTED_TYPES[technique]
    assert transition.performance_recipe == recipe.to_dict()
    assert transition.recipe_action_schedule == list(compiled.action_schedule)
    assert transition.overlap_duration_sec == pytest.approx(4.0)
    assert transition.target_consumed_duration_sec > 0


@pytest.mark.parametrize(
    "technique, operation_type",
    [
        ("reverb_wash", "reverb_wash"),
        ("loop_shortening", "loop_shorten"),
        ("riser_impact", "riser_impact"),
        ("tempo_reset", "tape_stop"),
    ],
)
def test_phase3_compiler_assigns_new_dsp_to_explicit_operations(technique, operation_type):
    compiled = compile_performance_recipe(
        phase3_recipe(technique, "source", "target", bars=2),
        _context(technique),
    )
    assert [item["type"] for item in compiled.technique_operations] == [operation_type]


def test_drum_overlay_owns_target_percussion_preparation():
    compiled = compile_performance_recipe(
        phase3_recipe("drum_overlay", "source", "target", bars=2),
        _context("drum_overlay"),
    )
    assert compiled.preparation_duration_sec == pytest.approx(2.0)
    assert compiled.preparation_operations == ({"type": "target_percussion_tease"},)


def test_phase3_new_creative_fx_are_bounded_shape_preserving_and_deterministic():
    sr = 8000
    t = np.arange(sr * 4, dtype=np.float32) / sr
    audio = np.column_stack([
        0.16 * np.sin(2 * np.pi * 137 * t),
        0.14 * np.sin(2 * np.pi * 181 * t),
    ]).astype(np.float32)

    wash_a = reverb_wash(audio, sr, wet=0.3, decay_sec=1.2)
    wash_b = reverb_wash(audio, sr, wet=0.3, decay_sec=1.2)
    shorten_a = loop_shorten(audio, sr, 120.0, sequence=(4, 2, 1))
    shorten_b = loop_shorten(audio, sr, 120.0, sequence=(4, 2, 1))
    fx_a = procedural_fx(len(audio), sr, "riser_impact", level=0.02, seed=23)
    fx_b = procedural_fx(len(audio), sr, "riser_impact", level=0.02, seed=23)

    for rendered in (wash_a, shorten_a, fx_a):
        assert rendered.shape == audio.shape
        assert np.isfinite(rendered).all()
        assert float(np.max(np.abs(rendered))) < 1.0
    assert np.array_equal(wash_a, wash_b)
    assert np.array_equal(shorten_a, shorten_b)
    assert np.array_equal(fx_a, fx_b)
    assert not np.allclose(wash_a, audio)
    assert not np.allclose(shorten_a, audio)
    assert float(np.sqrt(np.mean(fx_a ** 2))) > 1e-5


def test_tempo_reset_tape_stop_is_renderer_reachable_and_changes_audio():
    sr = 8000
    n = sr * 4
    t = np.arange(n, dtype=np.float32) / sr
    source = 0.14 * np.sin(2 * np.pi * (110.0 + 8.0 * t) * t)
    target = 0.11 * np.sin(2 * np.pi * 240.0 * t)
    plain = apply_transition(
        source, target, sr, "echo_out", sr * 2, sr, 0,
        source_bpm=120.0, target_bpm=120.0,
    )
    reset = apply_transition(
        source, target, sr, "echo_out", sr * 2, sr, 0,
        source_bpm=120.0, target_bpm=120.0,
        technique_operations=[{"type": "tape_stop", "strength": 0.72}],
    )
    assert reset.shape == plain.shape
    assert np.isfinite(reset).all()
    assert not np.allclose(reset, plain, atol=1e-6)


def test_creative_operation_dispatch_is_fail_closed_for_unknown_operations():
    audio = np.ones((800, 2), dtype=np.float32) * 0.01
    with pytest.raises(ValueError, match="unknown creative operation"):
        apply_creative_operations(
            audio,
            np.zeros_like(audio),
            sample_rate=8000,
            source_bpm=120.0,
            operations=[{"type": "invented_phase3_effect"}],
        )


def test_transition_stem_windows_align_full_track_cache_to_segment_local_buffers():
    n = 5000
    source_bass = np.column_stack([
        np.linspace(0.001, 0.2, n, dtype=np.float32),
        np.linspace(0.002, 0.18, n, dtype=np.float32),
    ])
    target_bass = source_bass[::-1].copy()
    source, target, reason = _prepare_transition_stem_windows(
        {"source": {"bass": source_bass}, "target": {"bass": target_bass}},
        "bass_swap",
        source_track_id="source",
        target_track_id="target",
        source_start_sample=1000,
        source_length=2000,
        target_start_sample=500,
        target_length=2500,
    )
    assert reason == ""
    assert source is not None and target is not None
    np.testing.assert_array_equal(source["bass"], source_bass[1000:3000])
    np.testing.assert_array_equal(target["bass"], target_bass[500:3000])


def test_transition_stem_validation_falls_back_on_missing_nonfinite_and_low_signal():
    valid = np.ones((4000, 2), dtype=np.float32) * 0.02
    zero = np.zeros((4000, 2), dtype=np.float32)
    bad = valid.copy()
    bad[100, 0] = np.nan

    _, _, reason = _prepare_transition_stem_windows(
        {"source": {"vocals": valid}, "target": {"drums": valid}},
        "mashup",
        source_track_id="source",
        target_track_id="target",
        source_start_sample=0,
        source_length=2000,
        target_start_sample=0,
        target_length=2000,
    )
    assert "missing required" in reason

    _, _, reason = _prepare_transition_stem_windows(
        {"source": {"vocals": zero}, "target": {"drums": valid, "bass": valid, "other": valid}},
        "mashup",
        source_track_id="source",
        target_track_id="target",
        source_start_sample=0,
        source_length=2000,
        target_start_sample=0,
        target_length=2000,
    )
    assert "insufficient signal" in reason

    _, _, reason = _prepare_transition_stem_windows(
        {"source": {"bass": bad}, "target": {"bass": valid}},
        "bass_swap",
        source_track_id="source",
        target_track_id="target",
        source_start_sample=0,
        source_length=2000,
        target_start_sample=0,
        target_length=2000,
    )
    assert "non-finite" in reason


def test_mashup_executes_without_optional_target_vocals_and_differs_from_fallback():
    sr = 8000
    n = sr * 4
    t = np.arange(n, dtype=np.float32) / sr
    source = 0.1 * np.sin(2 * np.pi * 120 * t)
    target = 0.1 * np.sin(2 * np.pi * 240 * t)
    source_stems = {"vocals": 0.08 * np.sin(2 * np.pi * 330 * t)}
    target_stems = {
        "drums": 0.04 * np.sign(np.sin(2 * np.pi * 4 * t)),
        "bass": 0.04 * np.sin(2 * np.pi * 70 * t),
        "other": 0.03 * np.sin(2 * np.pi * 420 * t),
    }
    stemmed = apply_transition(
        source, target, sr, "mashup", sr * 2, sr, 0,
        source_bpm=120, target_bpm=120,
        source_stems=source_stems, target_stems=target_stems,
    )
    fallback = apply_transition(
        source, target, sr, "mashup", sr * 2, sr, 0,
        source_bpm=120, target_bpm=120,
    )
    assert stemmed.shape == fallback.shape
    assert np.isfinite(stemmed).all()
    assert not np.allclose(stemmed, fallback)


def _write_track(path, frequency: float, sr: int = 8000, seconds: int = 20) -> None:
    t = np.arange(sr * seconds, dtype=np.float32) / sr
    signal = 0.12 * np.sin(2 * np.pi * frequency * t)
    signal += 0.025 * np.sin(2 * np.pi * (frequency * 2.0) * t)
    sf.write(path, np.column_stack([signal, signal * 0.97]).astype(np.float32), sr)


def _track(track_id: str, path, bpm: float = 120.0, duration: float = 20.0) -> TrackProfile:
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(
            filepath=str(path), title=track_id, duration_sec=duration,
            sample_rate=8000, channels=2,
        ),
        analysis=TrackAnalysis(
            bpm=bpm, bpm_confidence=0.99, analysis_confidence=0.99,
            energy_curve=[0.5] * int(duration),
            low_energy_curve=[0.3] * int(duration),
        ),
    )


def _synthetic_stems(sr: int = 8000, seconds: int = 20) -> dict[str, dict[str, np.ndarray]]:
    t = np.arange(sr * seconds, dtype=np.float32) / sr
    stereo = lambda x: np.column_stack([x, x * 0.97]).astype(np.float32)
    return {
        "source": {
            "vocals": stereo(0.07 * np.sin(2 * np.pi * 330 * t)),
            "bass": stereo(0.05 * np.sin(2 * np.pi * 72 * t)),
            "drums": stereo(0.03 * np.sign(np.sin(2 * np.pi * 4 * t))),
            "other": stereo(0.025 * np.sin(2 * np.pi * 510 * t)),
        },
        "target": {
            "vocals": stereo(0.03 * np.sin(2 * np.pi * 390 * t)),
            "bass": stereo(0.055 * np.sin(2 * np.pi * 84 * t)),
            "drums": stereo(0.035 * np.sign(np.sin(2 * np.pi * 4 * t + 0.2))),
            "other": stereo(0.03 * np.sin(2 * np.pi * 620 * t)),
        },
    }


def _render_recipe(tmp_path, technique: str, *, stems: dict | None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    sr = 8000
    source_path = tmp_path / f"source-{technique}.wav"
    target_path = tmp_path / f"target-{technique}.wav"
    _write_track(source_path, 110, sr=sr)
    _write_track(target_path, 176, sr=sr)
    tracks = [_track("source", source_path), _track("target", target_path)]
    ctx = _context(technique)
    recipe = phase3_recipe(technique, "source", "target", bars=2)
    compiled = compile_performance_recipe(recipe, ctx)
    transition = compiled_recipe_to_transition(compiled, ctx)
    overlap = compiled.overlap_duration_sec
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(
                id="source-app",
                segment=PerformanceSegment(
                    id="source-segment", track_id="source",
                    source_start_sec=0.0, source_end_sec=16.0, confidence=0.99,
                ),
                output_start_sec=0.0, output_end_sec=16.0,
            ),
            PerformanceAppearance(
                id="target-app",
                segment=PerformanceSegment(
                    id="target-segment", track_id="target",
                    source_start_sec=0.0, source_end_sec=16.0, confidence=0.99,
                ),
                output_start_sec=16.0 - overlap, output_end_sec=32.0 - overlap,
            ),
        ],
        transitions=[transition],
        total_duration_sec=32.0 - overlap,
        target_duration_sec=32.0 - overlap,
        performance_style="experimental",
    )
    plan = SetPlan(
        tracks=tracks, performance_mode="segment", performance_style="experimental",
        performance_timeline=timeline,
    )
    output = tmp_path / f"phase3-{technique}.wav"
    result = render_performance_mix(
        plan, str(output), sample_rate=sr, stem_audio=stems,
    )
    diagnostics = json.loads(
        (tmp_path / f"phase3-{technique}_diagnostics.json").read_text()
    )
    event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    return output, result, event


@pytest.mark.parametrize("technique", ALL_TECHNIQUES)
def test_all_twelve_phase3_families_render_safe_synthetic_stereo(tmp_path, technique):
    stems = _synthetic_stems() if technique in {"bass_swap", "drum_overlay", "stem_handoff"} else None
    output, result, event = _render_recipe(tmp_path, technique, stems=stems)
    audio, sr = sf.read(output, dtype="float32")
    assert sr == 8000
    assert audio.ndim == 2 and audio.shape[1] == 2
    assert np.isfinite(audio).all()
    assert len(audio) > sr
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    jump = float(np.max(np.abs(np.diff(audio, axis=0))))
    assert 0.0 < peak <= 1.05
    assert rms > 1e-4
    assert jump < 1.2
    assert result["provenance_audit"]["clean"]
    assert result["transitions_rendered"] == 1
    assert event["transition_type"] == EXPECTED_TYPES[technique].value
    assert event["target_consumed_duration_sec"] > 0
    assert event["target_body_start_sec"] > event["target_start_sec"]
    if technique in {"bass_swap", "stem_handoff"}:
        assert event["stem_path_requested"] is True
        assert event["stem_path_rendered"] is True
        assert event["stem_path_fallback_reason"] == ""
    if technique == "drum_overlay":
        assert event["preparation_rendered"] is True
        assert event["preparation_target_provenance"]["stem"] == "drums"
    if technique == "riser_impact":
        assert event["generated_fx_provenance"][0]["effect_type"] == "riser_impact"


def test_stem_handoff_renderer_fallback_is_explicit_and_audio_differs_from_real_stem_path(tmp_path):
    stem_output, stem_result, stem_event = _render_recipe(
        tmp_path / "with-stems", "stem_handoff", stems=_synthetic_stems(),
    )
    fallback_output, fallback_result, fallback_event = _render_recipe(
        tmp_path / "without-stems", "stem_handoff", stems=None,
    )
    stem_audio, _ = sf.read(stem_output, dtype="float32")
    fallback_audio, _ = sf.read(fallback_output, dtype="float32")
    assert stem_event["stem_path_rendered"] is True
    assert fallback_event["stem_path_requested"] is True
    assert fallback_event["stem_path_rendered"] is False
    assert "unavailable" in fallback_event["stem_path_fallback_reason"]
    assert stem_result["provenance_audit"]["clean"]
    assert fallback_result["provenance_audit"]["clean"]
    assert stem_audio.shape == fallback_audio.shape
    assert not np.allclose(stem_audio, fallback_audio, atol=1e-5)


def _application_plan(tmp_path, technique: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    sr = 8000
    seconds = 8
    source_path = tmp_path / f"app-source-{technique}.wav"
    target_path = tmp_path / f"app-target-{technique}.wav"
    _write_track(source_path, 107, sr=sr, seconds=seconds)
    _write_track(target_path, 173, sr=sr, seconds=seconds)
    tracks = [
        _track("source", source_path, duration=float(seconds)),
        _track("target", target_path, duration=float(seconds)),
    ]
    source_stems: frozenset[str] = frozenset()
    target_stems: frozenset[str] = frozenset()
    if technique == "stem_handoff":
        source_stems = frozenset({"vocals"})
        target_stems = frozenset({"drums", "bass", "other"})
    elif technique == "drum_overlay":
        target_stems = frozenset({"drums"})
    ctx = RecipeCompileContext(
        source_appearance_id="source-app",
        target_appearance_id="target-app",
        source_segment_start_sec=1.0,
        source_segment_end_sec=7.0,
        target_segment_start_sec=0.5,
        target_segment_end_sec=6.5,
        source_track_duration_sec=float(seconds),
        target_track_duration_sec=float(seconds),
        source_bpm=120.0,
        target_bpm=120.0,
        available_source_stems=source_stems,
        available_target_stems=target_stems,
    )
    recipe = phase3_recipe(technique, "source", "target", bars=2)
    compiled = compile_performance_recipe(recipe, ctx)
    transition = compiled_recipe_to_transition(compiled, ctx)
    overlap = compiled.overlap_duration_sec
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(
                id="source-app",
                segment=PerformanceSegment(
                    id="source-segment", track_id="source",
                    source_start_sec=1.0, source_end_sec=7.0, confidence=0.99,
                ),
                output_start_sec=0.0, output_end_sec=6.0,
            ),
            PerformanceAppearance(
                id="target-app",
                segment=PerformanceSegment(
                    id="target-segment", track_id="target",
                    source_start_sec=0.5, source_end_sec=6.5, confidence=0.99,
                ),
                output_start_sec=6.0 - overlap, output_end_sec=12.0 - overlap,
            ),
        ],
        transitions=[transition],
        total_duration_sec=12.0 - overlap,
        target_duration_sec=12.0 - overlap,
        performance_style="experimental",
    )
    return SetPlan(
        tracks=tracks,
        performance_mode="segment",
        performance_style="experimental",
        performance_timeline=timeline,
    ), source_path, target_path


def _wait_service_job(service: LocalAppService, job_id: str, timeout_sec: float = 10.0):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        result = service.get_job(job_id)
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(0.01)
    raise AssertionError(f"job did not finish within {timeout_sec:.1f}s")


def _transition_event(job_result: dict) -> dict:
    diagnostics_path = job_result["result"]["timeline_diagnostics_path"]
    diagnostics = json.loads(open(diagnostics_path, encoding="utf-8").read())
    assert diagnostics["provenance_audit"]["clean"]
    return next(
        item for item in diagnostics["events"]
        if item["type"] == "performance_transition"
    )


def _install_application_stem_fakes(monkeypatch, stem_by_path, separate_calls, load_calls):
    def fake_separate(filepath, stem_dir, **_kwargs):
        separate_calls.append(str(filepath))
        return {
            name: str(stem_dir / f"fake-{name}.wav")
            for name in stem_by_path[str(filepath)]
        }

    def fake_load(filepath, **_kwargs):
        load_calls.append(str(filepath))
        return stem_by_path[str(filepath)]

    monkeypatch.setattr("djenius.audio.stems.stems_available", lambda: True)
    monkeypatch.setattr("djenius.audio.stems.separate_stems", fake_separate)
    monkeypatch.setattr("djenius.audio.stems.load_stems", fake_load)


def _render_via_service(service, plan_id: str, plan: SetPlan, *, use_stems: bool):
    service._plans[plan_id] = plan
    job = _wait_service_job(service, service.start_render(plan_id, use_stems=use_stems))
    assert job["status"] == "completed", job.get("error")
    output, sr = sf.read(job["result"]["output_path"], dtype="float32")
    assert sr == 8000
    assert np.isfinite(output).all()
    return job, output


@pytest.mark.parametrize("technique", ["bass_swap", "stem_handoff"])
def test_local_app_loads_stems_and_reaches_real_stem_dsp(monkeypatch, tmp_path, technique):
    import djenius.audio.performance_renderer as renderer_module

    plan, source_path, target_path = _application_plan(tmp_path / "stemmed", technique)
    stems = _synthetic_stems(sr=8000, seconds=8)
    stem_by_path = {
        str(source_path): stems["source"],
        str(target_path): stems["target"],
    }
    separate_calls: list[str] = []
    load_calls: list[str] = []
    _install_application_stem_fakes(
        monkeypatch, stem_by_path, separate_calls, load_calls,
    )

    real_render = renderer_module.render_performance_mix
    real_apply = renderer_module.apply_transition
    captured: dict[str, dict[str, np.ndarray] | None] = {}

    def render_at_test_rate(*args, **kwargs):
        kwargs["sample_rate"] = 8000
        return real_render(*args, **kwargs)

    def spy_apply_transition(*args, **kwargs):
        captured["source"] = kwargs.get("source_stems")
        captured["target"] = kwargs.get("target_stems")
        return real_apply(*args, **kwargs)

    monkeypatch.setattr(renderer_module, "render_performance_mix", render_at_test_rate)
    monkeypatch.setattr(renderer_module, "apply_transition", spy_apply_transition)

    service = LocalAppService(
        data_dir=tmp_path / "data-stemmed",
        output_dir=tmp_path / "out-stemmed",
    )
    stem_job, stem_output = _render_via_service(
        service, f"stem-{technique}", plan, use_stems=True,
    )
    stem_event = _transition_event(stem_job)

    assert sorted(separate_calls) == sorted([str(source_path), str(target_path)])
    assert sorted(load_calls) == sorted([str(source_path), str(target_path)])
    assert stem_event["stem_path_requested"] is True
    assert stem_event["stem_path_rendered"] is True
    assert stem_event["stem_path_fallback_reason"] == ""
    assert captured["source"] is not None and captured["target"] is not None

    source_required = "bass" if technique == "bass_swap" else "vocals"
    np.testing.assert_array_equal(
        captured["source"][source_required],
        stems["source"][source_required][8000:56000],
    )
    target_required = "bass" if technique == "bass_swap" else "drums"
    np.testing.assert_array_equal(
        captured["target"][target_required],
        stems["target"][target_required][4000:52000],
    )

    fallback_plan, _, _ = _application_plan(tmp_path / "fallback", technique)
    fallback_service = LocalAppService(
        data_dir=tmp_path / "data-fallback",
        output_dir=tmp_path / "out-fallback",
    )
    fallback_job, fallback_output = _render_via_service(
        fallback_service, f"fallback-{technique}", fallback_plan, use_stems=False,
    )
    fallback_event = _transition_event(fallback_job)
    assert fallback_event["stem_path_requested"] is True
    assert fallback_event["stem_path_rendered"] is False
    assert "unavailable" in fallback_event["stem_path_fallback_reason"]
    assert stem_output.shape == fallback_output.shape
    assert not np.allclose(stem_output, fallback_output, atol=1e-5)


def test_local_app_drum_overlay_supplies_actual_target_drums(monkeypatch, tmp_path):
    import djenius.audio.performance_renderer as renderer_module

    plan, source_path, target_path = _application_plan(tmp_path / "drums", "drum_overlay")
    stems = _synthetic_stems(sr=8000, seconds=8)
    stem_by_path = {
        str(source_path): stems["source"],
        str(target_path): stems["target"],
    }
    separate_calls: list[str] = []
    load_calls: list[str] = []
    _install_application_stem_fakes(
        monkeypatch, stem_by_path, separate_calls, load_calls,
    )
    real_render = renderer_module.render_performance_mix

    def render_at_test_rate(*args, **kwargs):
        kwargs["sample_rate"] = 8000
        return real_render(*args, **kwargs)

    monkeypatch.setattr(renderer_module, "render_performance_mix", render_at_test_rate)
    service = LocalAppService(
        data_dir=tmp_path / "data-drums",
        output_dir=tmp_path / "out-drums",
    )
    stem_job, stem_output = _render_via_service(
        service, "drum-overlay-stemmed", plan, use_stems=True,
    )
    stem_event = _transition_event(stem_job)
    assert sorted(separate_calls) == sorted([str(source_path), str(target_path)])
    assert sorted(load_calls) == sorted([str(source_path), str(target_path)])
    assert stem_event["preparation_rendered"] is True
    assert stem_event["preparation_target_provenance"]["stem"] == "drums"
    assert stem_event["preparation_target_provenance"]["source_start_sample"] == 4000
    assert stem_event["preparation_target_provenance"]["source_end_sample"] == 20000

    fallback_plan, _, _ = _application_plan(tmp_path / "drums-fallback", "drum_overlay")
    fallback_service = LocalAppService(
        data_dir=tmp_path / "data-drums-fallback",
        output_dir=tmp_path / "out-drums-fallback",
    )
    fallback_job, fallback_output = _render_via_service(
        fallback_service, "drum-overlay-fallback", fallback_plan, use_stems=False,
    )
    fallback_event = _transition_event(fallback_job)
    assert fallback_event["preparation_rendered"] is False
    assert fallback_event["preparation_target_provenance"] is None
    assert len(fallback_output) - len(stem_output) == 16000
    common = min(len(stem_output), len(fallback_output))
    assert not np.allclose(stem_output[:common], fallback_output[:common], atol=1e-5)


def test_local_app_invalid_stem_audio_falls_back_explicitly(monkeypatch, tmp_path):
    import djenius.audio.performance_renderer as renderer_module

    plan, source_path, target_path = _application_plan(tmp_path / "invalid", "bass_swap")
    stems = _synthetic_stems(sr=8000, seconds=8)
    stems["source"]["bass"] = np.zeros_like(stems["source"]["bass"])
    stem_by_path = {
        str(source_path): stems["source"],
        str(target_path): stems["target"],
    }
    separate_calls: list[str] = []
    load_calls: list[str] = []
    _install_application_stem_fakes(
        monkeypatch, stem_by_path, separate_calls, load_calls,
    )
    real_render = renderer_module.render_performance_mix

    def render_at_test_rate(*args, **kwargs):
        kwargs["sample_rate"] = 8000
        return real_render(*args, **kwargs)

    monkeypatch.setattr(renderer_module, "render_performance_mix", render_at_test_rate)
    service = LocalAppService(
        data_dir=tmp_path / "data-invalid",
        output_dir=tmp_path / "out-invalid",
    )
    job, _output = _render_via_service(
        service, "bass-swap-invalid", plan, use_stems=True,
    )
    event = _transition_event(job)
    assert event["stem_path_requested"] is True
    assert event["stem_path_rendered"] is False
    assert "insufficient signal" in event["stem_path_fallback_reason"]
