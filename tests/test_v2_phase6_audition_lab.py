from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from djenius.audio.audition_renderer import (
    AuditionPreviewConfig,
    RenderedCandidatePreview,
    render_candidate_preview,
)
from djenius.audio.transitions import phrase_cut_seam_samples
from djenius.core.audition_lab import (
    AuditionRanking,
    CandidateAudition,
    audition_candidate,
    evaluate_candidate_preview,
    rank_auditions,
)
from djenius.core.analysis_v2 import build_tempo_hypotheses
from djenius.core.candidate_composer import (
    CandidateComposerConfig,
    TransitionCandidate,
    compose_transition_candidates,
)
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile

SR = 8000
DURATION = 96.0


def _track(
    track_id: str,
    *,
    bpm: float = 120.0,
    vocal: float = 0.08,
    stems: bool = False,
    bpm_confidence: float = 0.98,
    drop_strength: float = 0.9,
) -> TrackProfile:
    duration = DURATION
    third = duration / 3.0
    sections = [
        {
            "start_sec": 0.0, "end_sec": third, "label": "intro",
            "boundary_confidence": 0.9, "mix_in_score": 0.9, "mix_out_score": 0.35,
            "landing_strength": 0.3, "bass_density": 0.55, "energy_mean": 0.35,
        },
        {
            "start_sec": third, "end_sec": 2 * third,
            "label": "drop" if drop_strength >= 0.62 else "verse",
            "boundary_confidence": 0.9, "mix_in_score": 0.88, "mix_out_score": 0.78,
            "landing_strength": drop_strength, "bass_density": 0.65, "energy_mean": 0.82,
        },
        {
            "start_sec": 2 * third, "end_sec": duration, "label": "outro",
            "boundary_confidence": 0.9, "mix_in_score": 0.3, "mix_out_score": 0.96,
            "landing_strength": 0.25, "bass_density": 0.50, "energy_mean": 0.4,
        },
    ]
    cues = [
        {
            "time_sec": 0.0, "bar_index": 1, "beat_in_bar": 1, "confidence": 0.9,
            "section": "intro", "use_cases": ["mix_in"], "mix_in_score": 0.9, "mix_out_score": 0.2,
        },
        {
            "time_sec": third, "bar_index": 17, "beat_in_bar": 1, "confidence": 0.9,
            "section": "drop" if drop_strength >= 0.62 else "verse",
            "use_cases": ["mix_in", "phrase_cut"] + (["drop_landing"] if drop_strength >= 0.62 else []),
            "mix_in_score": 0.88, "mix_out_score": 0.78,
        },
        {
            "time_sec": 2 * third, "bar_index": 33, "beat_in_bar": 1, "confidence": 0.9,
            "section": "outro", "use_cases": ["mix_out", "phrase_cut"],
            "mix_in_score": 0.3, "mix_out_score": 0.96,
        },
    ]
    declared = (
        {name: f"/synthetic/{track_id}/{name}.wav" for name in ("vocals", "drums", "bass", "other")}
        if stems else None
    )
    analysis = TrackAnalysis(
        bpm=bpm,
        bpm_confidence=bpm_confidence,
        analysis_confidence=0.95,
        tempo_hypotheses=build_tempo_hypotheses(bpm, bpm_confidence),
        section_profiles=sections,
        cue_candidates=cues,
        vocal_activity_curve=[vocal] * int(duration),
        energy_curve=[0.6] * int(duration),
        low_energy=0.55,
        groove_profile={
            "confidence": 0.9,
            "syncopation_index": 0.25,
            "swing_ratio": 1.0,
            "percussion_density_mean": 0.55,
        },
        stems=declared,
        stem_activity_profiles={"vocals": {"active_fraction": 0.8}} if stems else {},
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=f"/synthetic/{track_id}.wav", duration_sec=duration),
        analysis=analysis,
    )


def _pulse_audio(*, bpm: float = 120.0, phase_sec: float = 0.0, low_boost: float = 0.0) -> np.ndarray:
    n = int(round(DURATION * SR))
    t = np.arange(n, dtype=np.float64) / SR
    mono = 0.035 * np.sin(2 * np.pi * 220.0 * t) + 0.02 * np.sin(2 * np.pi * 880.0 * t)
    if low_boost:
        mono += low_boost * np.sin(2 * np.pi * 65.0 * t)
    beat = 60.0 / bpm
    pulse_len = max(8, int(round(0.012 * SR)))
    for beat_time in np.arange(phase_sec, DURATION, beat):
        start = int(round(beat_time * SR))
        if start < 0 or start >= n:
            continue
        end = min(n, start + pulse_len)
        envelope = np.linspace(1.0, 0.0, end - start, dtype=np.float64)
        mono[start:end] += 0.30 * envelope
    return np.column_stack([mono, mono]).astype(np.float32)


def _candidate(family: str = "eq_blend", *, vocal: float = 0.08, stems: bool = False, bpm_confidence: float = 0.98) -> TransitionCandidate:
    source = _track("source", vocal=vocal, stems=stems, bpm_confidence=bpm_confidence)
    target = _track("target", vocal=vocal, stems=stems, bpm_confidence=bpm_confidence)
    result = compose_transition_candidates(
        source,
        target,
        seed=606,
        config=CandidateComposerConfig(min_candidates=3, max_candidates=8),
    )
    try:
        return next(item for item in result.candidates if item.technique_family == family)
    except StopIteration as exc:
        raise AssertionError(f"synthetic fixture did not generate family {family}: {[x.technique_family for x in result.candidates]}") from exc


def _special_candidate(family: str) -> TransitionCandidate:
    if family == "drum_bridge":
        source = _track("source", vocal=0.9)
        target = _track("target", vocal=0.85)
    elif family == "stem_handoff":
        source = _track("source", vocal=0.9, stems=True)
        target = _track("target", vocal=0.85, stems=True)
    else:
        return _candidate(family)
    result = compose_transition_candidates(
        source, target, seed=607,
        config=CandidateComposerConfig(min_candidates=3, max_candidates=8),
    )
    return next(item for item in result.candidates if item.technique_family == family)


def _render(candidate: TransitionCandidate, *, config: AuditionPreviewConfig | None = None, stems: bool = False) -> RenderedCandidatePreview:
    audio = _pulse_audio()
    stem_payload = None
    if stems:
        stem_payload = {
            "vocals": audio * 0.35,
            "drums": audio * 0.45,
            "bass": audio * 0.30,
            "other": audio * 0.25,
        }
    return render_candidate_preview(
        candidate, audio, audio, SR, config=config,
        source_stems=stem_payload, target_stems=stem_payload,
    )


def _replace_transition(preview: RenderedCandidatePreview, transition_audio: np.ndarray) -> RenderedCandidatePreview:
    audio = np.asarray(preview.audio).copy()
    start, end = preview.transition_start_sample, preview.transition_end_sample
    assert len(transition_audio) == end - start
    values = transition_audio
    if values.ndim == 1:
        values = np.column_stack([values, values])
    audio[start:end] = values
    return replace(preview, audio=audio)


def _shifted_transition(preview: RenderedCandidatePreview, offset_ms: float) -> np.ndarray:
    length = preview.transition_end_sample - preview.transition_start_sample
    duration = length / SR
    t = np.arange(length, dtype=np.float64) / SR
    mono = 0.02 * np.sin(2 * np.pi * 220.0 * t)
    pulse_len = max(8, int(round(0.012 * SR)))
    for beat_time in np.arange(offset_ms / 1000.0, duration, 0.5):
        start = int(round(beat_time * SR))
        if start < 0 or start >= length:
            continue
        end = min(length, start + pulse_len)
        mono[start:end] += 0.30 * np.linspace(1.0, 0.0, end - start)
    return np.column_stack([mono, mono]).astype(np.float32)


def test_phrase_cut_splice_consumes_only_the_click_safe_target_seam():
    candidate = _candidate("phrase_cut")
    preview = _render(candidate)
    overlap = preview.transition_end_sample - preview.transition_start_sample
    seam = phrase_cut_seam_samples(SR, overlap)

    actual_advance = (
        preview.target_consumed_end_sec - preview.target_transition_start_sec
    ) * SR
    assert actual_advance == pytest.approx(seam, abs=1e-5)
    assert preview.renderer_provenance["actual_target_cursor_advance_sec"] == pytest.approx(
        seam / SR
    )
    assert seam < overlap * 0.01, "phrase cut must not silently skip a multi-bar target phrase"


def test_phase5_riser_mix_choreography_is_not_crossfade_plus_tiny_fx():
    candidate = _candidate("riser_impact")
    performed = _render(candidate)

    # Retain the same typed riser/impact events and exact anchors, but lower
    # the metadata phase so only the historical crossfade foundation remains.
    # This isolates the new two-deck build/landing choreography from merely
    # making the generated effects louder.
    baseline_recipe = replace(
        candidate.recipe,
        recipe_id="",
        metadata={**candidate.recipe.metadata, "phase": 4},
    ).with_deterministic_ids()
    baseline_candidate = replace(
        candidate,
        candidate_id="",
        recipe=baseline_recipe,
    ).with_deterministic_id()
    baseline = _render(baseline_candidate)

    a = performed.audio[performed.transition_start_sample:performed.transition_end_sample]
    b = baseline.audio[baseline.transition_start_sample:baseline.transition_end_sample]
    difference_rms = float(np.sqrt(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)))
    baseline_rms = float(np.sqrt(np.mean(b.astype(np.float64) ** 2)))
    correlation = float(np.corrcoef(a.reshape(-1), b.reshape(-1))[0, 1])
    assert difference_rms > baseline_rms * 0.20
    assert correlation < 0.995


@pytest.fixture(scope="module")
def eq_candidate() -> TransitionCandidate:
    return _candidate("eq_blend")


@pytest.fixture(scope="module")
def eq_preview(eq_candidate: TransitionCandidate) -> RenderedCandidatePreview:
    return _render(eq_candidate)


def test_preview_config_rejects_unbounded_context():
    with pytest.raises(ValueError, match="before_context_sec"):
        AuditionPreviewConfig(before_context_sec=40.0).validate()


def test_preview_bounds_identity_and_duration_are_deterministic(eq_candidate, eq_preview):
    second = _render(eq_candidate)
    assert eq_preview.to_dict() == second.to_dict()
    assert eq_preview.audio_sha256 == second.audio_sha256
    assert eq_preview.candidate_id == eq_candidate.candidate_id
    assert eq_preview.recipe_id == eq_candidate.recipe.recipe_id
    assert eq_preview.transition_start_sample > 0
    assert eq_preview.transition_end_sample > eq_preview.transition_start_sample
    assert eq_preview.exact_duration_sec == pytest.approx(len(eq_preview.audio) / SR)
    assert eq_preview.renderer_provenance["mastering_applied"] is False
    assert eq_preview.renderer_provenance["soft_clip_applied"] is False


def test_preview_context_is_configurable_and_bounded(eq_candidate):
    preview = _render(eq_candidate, config=AuditionPreviewConfig(before_context_sec=16.0, after_context_sec=20.0))
    assert preview.transition_start_sample == 16 * SR
    assert preview.render_config["before_context_sec"] == 16.0
    assert preview.render_config["after_context_sec"] == 20.0


def test_preview_serialized_metadata_contains_exact_binding_and_hash(eq_preview):
    payload = eq_preview.to_dict()
    assert payload["candidate_id"] == eq_preview.candidate_id
    assert payload["recipe_id"] == eq_preview.recipe_id
    assert payload["audio_sha256"] == eq_preview.audio_sha256
    assert payload["sample_rate"] == SR
    assert payload["channels"] == 2


def test_required_stem_candidate_fails_closed_when_audio_stems_missing():
    candidate = _special_candidate("stem_handoff")
    with pytest.raises(ValueError, match="requires stems"):
        _render(candidate, stems=False)


def test_required_stem_candidate_renders_when_stems_are_supplied():
    candidate = _special_candidate("stem_handoff")
    preview = _render(candidate, stems=True)
    assert preview.renderer_provenance["required_stems_rendered"] is True
    assert {"vocals"} <= set(preview.renderer_provenance["supplied_source_stems"])
    assert {"drums", "bass", "other"} <= set(preview.renderer_provenance["supplied_target_stems"])


def test_groove_candidate_binds_sample_layer_provenance_to_recipe():
    candidate = _special_candidate("drum_bridge")
    preview = _render(candidate)
    assert preview.sample_layer_provenance
    assert {item["recipe_id"] for item in preview.sample_layer_provenance} == {candidate.recipe.recipe_id}
    assert preview.renderer_provenance["sample_layer_event_count"] > 0


def test_riser_preview_tolerates_one_sample_boundary_rounding_at_fractional_bpm():
    source = _track("source_riser_fractional", bpm=117.5)
    target = _track("target_riser_fractional", bpm=117.5)
    result = compose_transition_candidates(
        source, target, seed=608,
        config=CandidateComposerConfig(min_candidates=3, max_candidates=8),
    )
    candidate = next(item for item in result.candidates if item.technique_family == "riser_impact")
    fractional_sr = 22050
    audio = np.zeros((int(round(DURATION * fractional_sr)), 2), dtype=np.float32)
    preview = render_candidate_preview(candidate, audio, audio, fractional_sr)
    assert preview.sample_layer_provenance
    # The impact now lands on the final bar's downbeat rather than being
    # scheduled at the transition's last beat/end boundary, so this exact
    # recipe no longer needs the historical one-sample trim. The generic
    # bounded rounding safeguard remains covered by Phase 4 tests.
    assert all(item.get("rounding_trim_samples", 0) <= 1 for item in preview.sample_layer_provenance)
    assert preview.transition_end_sample <= len(preview.audio)


def test_good_preview_survives_and_has_transparent_components(eq_candidate, eq_preview):
    audition = evaluate_candidate_preview(eq_candidate, eq_preview)
    assert audition.hard_rejected is False
    assert 0.0 < audition.final_score <= 1.0
    assert {"technical_margin", "spectral_cleanliness", "vocal_safety", "energy_goal_fit"} <= set(audition.metrics.normalized_components)
    assert audition.metrics.harmonic["status"] == "deferred"
    assert audition.metrics.technical["true_peak_status"] == "not_itu_certified_use_oversampled_peak_proxy"
    assert "not_human_quality_truth" in audition.provenance["score_semantics"]




def test_render_failure_is_typed_hard_rejection(eq_candidate):
    too_short = np.zeros((SR, 2), dtype=np.float32)
    audition = audition_candidate(eq_candidate, too_short, too_short, SR)
    assert audition.render_status == "render_failed"
    assert audition.hard_rejected is True
    assert audition.final_score == 0.0
    assert [item.code for item in audition.failures] == ["render_failure"]


def test_spectral_report_names_bass_masking_and_hole_proxies(eq_candidate, eq_preview):
    audition = evaluate_candidate_preview(eq_candidate, eq_preview)
    assert "bass_masking_proxy" in audition.metrics.spectral
    assert "spectral_hole_depth_db" in audition.metrics.spectral
    assert 0.0 <= audition.metrics.spectral["bass_masking_proxy"] <= 1.0

def test_audition_round_trip_serialization(eq_candidate, eq_preview):
    audition = evaluate_candidate_preview(eq_candidate, eq_preview)
    restored = CandidateAudition.from_dict(audition.to_dict())
    assert restored.to_dict() == audition.to_dict()


def test_nan_is_hard_rejected(eq_candidate, eq_preview):
    audio = eq_preview.audio.copy()
    audio[eq_preview.transition_start_sample + 10, 0] = np.nan
    audition = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=audio))
    assert audition.hard_rejected is True
    assert "non_finite_audio" in {item.code for item in audition.failures}
    assert audition.final_score == 0.0


def test_clipping_is_hard_rejected(eq_candidate, eq_preview):
    audio = eq_preview.audio.copy()
    audio[eq_preview.transition_start_sample:eq_preview.transition_start_sample + 100] = 1.08
    audition = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=audio))
    assert audition.hard_rejected is True
    assert "unsafe_sample_peak" in {item.code for item in audition.failures}


def test_preexisting_context_peak_does_not_reject_safe_candidate_transition(eq_candidate, eq_preview):
    audio = eq_preview.audio.copy()
    audio[100] = 1.05
    audition = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=audio))
    assert audition.hard_rejected is False
    assert audition.metrics.technical["sample_peak"] < 1.0
    assert audition.metrics.technical["preview_sample_peak"] > 1.0
    assert audition.metrics.technical["sample_peak_scope"] == "transition_only"
    assert "unsafe_sample_peak" not in {item.code for item in audition.failures}


def test_transition_only_catastrophic_silence_is_hard_rejected(eq_candidate, eq_preview):
    audio = eq_preview.audio.copy()
    audio[eq_preview.transition_start_sample:eq_preview.transition_end_sample] = 0.0
    audition = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=audio))
    assert audition.hard_rejected is True
    assert "catastrophic_silence" in {item.code for item in audition.failures}


def test_catastrophic_silence_is_hard_rejected(eq_candidate, eq_preview):
    audition = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=np.zeros_like(eq_preview.audio)))
    assert audition.hard_rejected is True
    assert "catastrophic_silence" in {item.code for item in audition.failures}


def test_broken_preview_bounds_are_hard_rejected(eq_candidate, eq_preview):
    broken = replace(eq_preview, transition_end_sample=len(eq_preview.audio) + 1)
    audition = evaluate_candidate_preview(eq_candidate, broken)
    assert audition.hard_rejected is True
    assert "broken_preview_bounds" in {item.code for item in audition.failures}


def test_identity_and_provenance_binding_fail_closed(eq_candidate, eq_preview):
    bad_provenance = dict(eq_preview.renderer_provenance)
    bad_provenance["recipe_id"] = "r2_wrong"
    broken = replace(eq_preview, candidate_id="tc6_wrong", renderer_provenance=bad_provenance)
    audition = evaluate_candidate_preview(eq_candidate, broken)
    codes = {item.code for item in audition.failures}
    assert {"identity_binding_mismatch", "renderer_provenance_mismatch"} <= codes
    assert audition.hard_rejected


def test_required_stem_provenance_failure_is_hard_rejected():
    candidate = _special_candidate("stem_handoff")
    preview = _render(candidate, stems=True)
    provenance = dict(preview.renderer_provenance)
    provenance["required_stems_rendered"] = False
    audition = evaluate_candidate_preview(candidate, replace(preview, renderer_provenance=provenance))
    assert "invalid_required_stem_use" in {item.code for item in audition.failures}


def test_unstable_declared_time_stretch_is_hard_rejected(eq_candidate, eq_preview):
    provenance = dict(eq_preview.renderer_provenance)
    provenance.update({"requires_stretch": True, "time_stretch_ratio": 1.5})
    audition = evaluate_candidate_preview(eq_candidate, replace(eq_preview, renderer_provenance=provenance))
    assert "unstable_time_stretch_ratio" in {item.code for item in audition.failures}


def test_severe_boundary_discontinuity_is_hard_rejected(eq_candidate, eq_preview):
    audio = eq_preview.audio.copy()
    boundary = eq_preview.transition_start_sample
    audio[boundary - 1] = -0.49
    audio[boundary] = 0.49
    audition = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=audio))
    assert "severe_boundary_discontinuity" in {item.code for item in audition.failures}


def test_sample_peak_margin_degrades_monotonically_before_clipping(eq_candidate, eq_preview):
    good = evaluate_candidate_preview(eq_candidate, eq_preview)
    near_audio = eq_preview.audio.copy()
    near_audio[eq_preview.transition_start_sample + 100] = 0.96
    near = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=near_audio))
    clipped_audio = eq_preview.audio.copy()
    clipped_audio[eq_preview.transition_start_sample + 100] = 1.05
    clipped = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=clipped_audio))
    assert good.metrics.technical["score"] > near.metrics.technical["score"] > clipped.metrics.technical["score"]
    assert clipped.hard_rejected


def test_beat_offset_metric_is_monotonic(eq_candidate, eq_preview):
    auditions = []
    for offset in (0.0, 30.0, 100.0):
        damaged = _replace_transition(eq_preview, _shifted_transition(eq_preview, offset))
        auditions.append(evaluate_candidate_preview(eq_candidate, damaged))
    scores = [item.metrics.beat["score"] for item in auditions]
    errors = [item.metrics.beat["beat_grid_phase_error_ms"] for item in auditions]
    assert scores[0] > scores[1] > scores[2]
    assert errors[0] < errors[1] < errors[2]


def test_low_confidence_beat_metric_is_explicitly_inapplicable(eq_preview):
    candidate = _candidate("eq_blend")
    evidence = dict(candidate.diagnostics.evidence)
    evidence["source_bpm_confidence"] = 0.40
    evidence["target_bpm_confidence"] = 0.40
    candidate = replace(candidate, diagnostics=replace(candidate.diagnostics, evidence=evidence))
    rebound = replace(
        eq_preview,
        candidate_id=candidate.candidate_id,
        recipe_id=candidate.recipe.recipe_id,
        renderer_provenance={**eq_preview.renderer_provenance, "candidate_id": candidate.candidate_id, "recipe_id": candidate.recipe.recipe_id},
    )
    audition = evaluate_candidate_preview(candidate, rebound)
    assert audition.metrics.beat["applicable"] is False
    assert "beat_stability" not in audition.metrics.normalized_components


def test_low_frequency_collision_proxy_penalizes_damaged_transition(eq_candidate, eq_preview):
    good = evaluate_candidate_preview(eq_candidate, eq_preview)
    length = eq_preview.transition_end_sample - eq_preview.transition_start_sample
    t = np.arange(length) / SR
    collision = 0.72 * np.sin(2 * np.pi * 65.0 * t)
    collision = np.column_stack([collision, collision]).astype(np.float32)
    bad = evaluate_candidate_preview(eq_candidate, _replace_transition(eq_preview, collision))
    assert bad.hard_rejected is False
    assert bad.metrics.spectral["low_frequency_collision_excess_ratio"] > good.metrics.spectral["low_frequency_collision_excess_ratio"]
    assert bad.metrics.spectral["score"] < good.metrics.spectral["score"]


def test_vocal_collision_proxy_is_contextual_and_stem_handoff_allows_intentional_interaction(eq_preview):
    eq = _candidate("eq_blend")
    dense_eq = replace(eq, vocal_overlap_assumptions={"source_density": 0.9, "target_density": 0.9, "policy": "avoid_overlap"})
    eq_bound = replace(eq_preview, candidate_id=dense_eq.candidate_id, recipe_id=dense_eq.recipe.recipe_id,
                       renderer_provenance={**eq_preview.renderer_provenance, "candidate_id": dense_eq.candidate_id, "recipe_id": dense_eq.recipe.recipe_id})
    eq_audition = evaluate_candidate_preview(dense_eq, eq_bound)

    stem = _special_candidate("stem_handoff")
    dense_stem = replace(stem, vocal_overlap_assumptions={"source_density": 0.9, "target_density": 0.9, "policy": "compatible_overlap"})
    stem_bound = replace(eq_preview, candidate_id=dense_stem.candidate_id, recipe_id=dense_stem.recipe.recipe_id,
                         source_track_id=dense_stem.source_track_id, target_track_id=dense_stem.target_track_id,
                         renderer_provenance={**eq_preview.renderer_provenance, "candidate_id": dense_stem.candidate_id, "recipe_id": dense_stem.recipe.recipe_id, "required_stems_rendered": True})
    stem_audition = evaluate_candidate_preview(dense_stem, stem_bound)
    assert stem_audition.metrics.vocal["intentional_vocal_interaction"] is True
    assert stem_audition.metrics.vocal["score"] > eq_audition.metrics.vocal["score"]


def test_energy_dip_allowance_is_technique_aware(eq_preview):
    eq = _candidate("eq_blend")
    echo = _candidate("echo_out")
    quiet = _shifted_transition(eq_preview, 0.0) * 0.08
    eq_bad = evaluate_candidate_preview(eq, _replace_transition(eq_preview, quiet))
    echo_preview = replace(
        _replace_transition(eq_preview, quiet),
        candidate_id=echo.candidate_id,
        recipe_id=echo.recipe.recipe_id,
        renderer_provenance={**eq_preview.renderer_provenance, "candidate_id": echo.candidate_id, "recipe_id": echo.recipe.recipe_id},
    )
    echo_audition = evaluate_candidate_preview(echo, echo_preview)
    assert eq_bad.metrics.energy["deliberate_release_dip_allowance"] is False
    assert echo_audition.metrics.energy["deliberate_release_dip_allowance"] is True
    assert echo_audition.metrics.energy["score"] >= eq_bad.metrics.energy["score"]


def test_spectral_metrics_distinguish_intentional_riser_change_from_damage(eq_preview):
    length = eq_preview.transition_end_sample - eq_preview.transition_start_sample
    t = np.arange(length, dtype=np.float64) / SR
    bright_layer = 0.025 * np.sin(2 * np.pi * 3200.0 * t)
    bright_layer = np.column_stack([bright_layer, bright_layer]).astype(np.float32)
    bright = (
        eq_preview.audio[eq_preview.transition_start_sample:eq_preview.transition_end_sample]
        + bright_layer
    )

    eq = _candidate("eq_blend")
    eq_result = evaluate_candidate_preview(eq, _replace_transition(eq_preview, bright))
    riser = _candidate("riser_impact")
    riser_preview = replace(
        _replace_transition(eq_preview, bright),
        candidate_id=riser.candidate_id,
        recipe_id=riser.recipe.recipe_id,
        renderer_provenance={
            **eq_preview.renderer_provenance,
            "candidate_id": riser.candidate_id,
            "recipe_id": riser.recipe.recipe_id,
        },
    )
    riser_result = evaluate_candidate_preview(riser, riser_preview)

    assert eq_result.metrics.spectral["intentional_spectral_transform"] is False
    assert riser_result.metrics.spectral["intentional_spectral_transform"] is True
    assert riser_result.metrics.spectral["intentional_high_frequency_allowance"] == pytest.approx(0.10)
    assert riser_result.metrics.spectral["continuity_distance_allowance"] == pytest.approx(0.14)
    assert riser_result.metrics.spectral["score"] > eq_result.metrics.spectral["score"]


def test_fx_metrics_are_family_specific(eq_candidate, eq_preview):
    eq = evaluate_candidate_preview(eq_candidate, eq_preview)
    echo = _candidate("echo_out")
    echo_preview = _render(echo)
    echo_audition = evaluate_candidate_preview(echo, echo_preview)
    assert eq.metrics.fx["applicable"] is False
    assert echo_audition.metrics.fx["applicable"] is True
    assert "fx_safety" not in eq.metrics.normalized_components
    assert "fx_safety" in echo_audition.metrics.normalized_components


def test_same_preview_produces_identical_metrics_and_score(eq_candidate, eq_preview):
    first = evaluate_candidate_preview(eq_candidate, eq_preview)
    second = evaluate_candidate_preview(eq_candidate, eq_preview)
    assert first.to_dict() == second.to_dict()


def test_deterministic_tie_breaking_uses_candidate_id(eq_candidate, eq_preview):
    base = evaluate_candidate_preview(eq_candidate, eq_preview)
    a = replace(base, candidate_id="tc5_a", recipe_id="r2_a", final_score=0.75)
    b = replace(base, candidate_id="tc5_b", recipe_id="r2_b", final_score=0.75)
    ranking = rank_auditions([b, a])
    assert ranking.ranking_order == ("tc5_a", "tc5_b")
    assert ranking.selected_candidate_id == "tc5_a"


def test_all_rejected_returns_no_selection(eq_candidate, eq_preview):
    audio = np.zeros_like(eq_preview.audio)
    rejected = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=audio))
    other = replace(rejected, candidate_id="tc5_other", recipe_id="r2_other")
    ranking = rank_auditions([rejected, other])
    assert ranking.selected_candidate_id is None
    assert ranking.survivor_count == 0
    assert ranking.rejected_count == 2
    assert ranking.ranking_order == ()


def test_single_survivor_is_selected(eq_candidate, eq_preview):
    good = evaluate_candidate_preview(eq_candidate, eq_preview)
    bad_audio = eq_preview.audio.copy()
    bad_audio[eq_preview.transition_start_sample + 10] = 1.1
    bad = evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=bad_audio))
    bad = replace(bad, candidate_id="tc5_bad", recipe_id="r2_bad")
    ranking = rank_auditions([bad, good])
    assert ranking.selected_candidate_id == good.candidate_id
    assert ranking.survivor_count == 1
    assert ranking.auditions[0].rank == 1
    assert ranking.auditions[0].selected is True


def test_known_bad_matrix_orders_valid_reference_above_damaged_versions(eq_candidate, eq_preview):
    good = evaluate_candidate_preview(eq_candidate, eq_preview)

    offset_preview = _replace_transition(eq_preview, _shifted_transition(eq_preview, 100.0))
    offset = replace(evaluate_candidate_preview(eq_candidate, offset_preview), candidate_id="tc5_bad_beat", recipe_id="r2_bad_beat")

    length = eq_preview.transition_end_sample - eq_preview.transition_start_sample
    t = np.arange(length) / SR
    lf = np.column_stack([0.72 * np.sin(2 * np.pi * 65.0 * t)] * 2).astype(np.float32)
    lf_bad = replace(evaluate_candidate_preview(eq_candidate, _replace_transition(eq_preview, lf)), candidate_id="tc5_bad_lf", recipe_id="r2_bad_lf")

    clip_audio = eq_preview.audio.copy()
    clip_audio[eq_preview.transition_start_sample + 50] = 1.1
    clipped = replace(evaluate_candidate_preview(eq_candidate, replace(eq_preview, audio=clip_audio)), candidate_id="tc5_bad_clip", recipe_id="r2_bad_clip")

    ranking = rank_auditions([offset, clipped, good, lf_bad])
    assert ranking.selected_candidate_id == good.candidate_id
    assert ranking.ranking_order[0] == good.candidate_id
    assert clipped.rank is None
    assert all(item.final_score <= good.final_score for item in (offset, lf_bad, clipped))


def test_ranking_round_trip_serialization(eq_candidate, eq_preview):
    good = evaluate_candidate_preview(eq_candidate, eq_preview)
    ranking = rank_auditions([good])
    restored = AuditionRanking.from_dict(ranking.to_dict())
    assert restored.to_dict() == ranking.to_dict()


def test_duplicate_candidate_ids_are_rejected_before_ranking(eq_candidate, eq_preview):
    audition = evaluate_candidate_preview(eq_candidate, eq_preview)
    with pytest.raises(ValueError, match="unique candidate IDs"):
        rank_auditions([audition, audition])
