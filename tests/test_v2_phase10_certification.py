from __future__ import annotations

import numpy as np
import pytest

from djenius.audio.set_director_renderer import (
    SetDirectorRenderError,
    render_set_director_mix,
)
from djenius.core.analysis_v2 import build_tempo_hypotheses
from djenius.core.candidate_composer import CandidateSetContext, compose_transition_candidates
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile
from djenius.core.set_director import (
    EdgeAuditionCache,
    HandoffSummary,
    SetArc,
    SetDirectorConfig,
    SetDirectorEdgeChoice,
    SetDirectorPlan,
    TrackAudio,
    plan_set_v2,
)

SR = 6000
# Long enough, with enough spread-out cues, that a target-entry anchor
# (near the start) and a later source-exit anchor (near the end) never
# compete for the same stretch of a shared middle track -- see
# test_render_full_mix_is_continuous_and_finite's docstring note on the
# real architectural limitation this fixture is deliberately avoiding.
DURATION = 180.0


def _track(track_id: str, *, bpm: float = 120.0, vocal: float = 0.08, stems: bool = False, duration: float = DURATION) -> TrackProfile:
    fifth = duration / 5.0
    sections = [
        {"start_sec": 0.0, "end_sec": fifth, "label": "intro", "boundary_confidence": 0.9,
         "mix_in_score": 0.9, "mix_out_score": 0.35, "landing_strength": 0.3, "bass_density": 0.55, "energy_mean": 0.5},
        {"start_sec": fifth, "end_sec": 3 * fifth, "label": "drop", "boundary_confidence": 0.9,
         "mix_in_score": 0.88, "mix_out_score": 0.78, "landing_strength": 0.75, "bass_density": 0.65, "energy_mean": 0.75},
        {"start_sec": 3 * fifth, "end_sec": duration, "label": "outro", "boundary_confidence": 0.9,
         "mix_in_score": 0.3, "mix_out_score": 0.96, "landing_strength": 0.25, "bass_density": 0.5, "energy_mean": 0.5},
    ]
    cues = [
        {"time_sec": 0.0, "bar_index": 1, "beat_in_bar": 1, "confidence": 0.9, "section": "intro",
         "use_cases": ["mix_in"], "mix_in_score": 0.9, "mix_out_score": 0.2},
        {"time_sec": fifth, "bar_index": 17, "beat_in_bar": 1, "confidence": 0.9, "section": "drop",
         "use_cases": ["mix_in", "phrase_cut", "drop_landing"], "mix_in_score": 0.88, "mix_out_score": 0.4},
        {"time_sec": 3 * fifth, "bar_index": 33, "beat_in_bar": 1, "confidence": 0.9, "section": "outro",
         "use_cases": ["mix_out", "phrase_cut"], "mix_in_score": 0.3, "mix_out_score": 0.96},
    ]
    declared = {name: f"/synthetic/{track_id}/{name}.wav" for name in ("vocals", "drums", "bass", "other")} if stems else None
    analysis = TrackAnalysis(
        bpm=bpm, bpm_confidence=0.97, camelot="8A", analysis_confidence=0.95,
        tempo_hypotheses=build_tempo_hypotheses(bpm, 0.97),
        section_profiles=sections, cue_candidates=cues,
        vocal_activity_curve=[vocal] * int(duration), energy_curve=[0.6] * int(duration),
        mean_energy=0.6, low_energy=0.55, stems=declared,
        stem_activity_profiles={"vocals": {"active_fraction": 0.8}} if stems else {},
        groove_profile={"confidence": 0.9, "syncopation_index": 0.25, "swing_ratio": 1.0, "percussion_density_mean": 0.55},
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=f"/synthetic/{track_id}.wav", duration_sec=duration),
        analysis=analysis,
    )


def _pulse_audio(*, bpm: float, gain: float = 0.30, duration: float = DURATION) -> np.ndarray:
    n = int(round(duration * SR))
    t = np.arange(n, dtype=np.float64) / SR
    mono = 0.035 * np.sin(2 * np.pi * 220.0 * t) + 0.02 * np.sin(2 * np.pi * 880.0 * t)
    beat = 60.0 / bpm
    pulse_len = max(6, int(round(0.012 * SR)))
    for beat_time in np.arange(0.0, duration, beat):
        start = int(round(beat_time * SR))
        if start >= n:
            continue
        end = min(n, start + pulse_len)
        envelope = np.linspace(1.0, 0.0, end - start, dtype=np.float64)
        mono[start:end] += gain * envelope
    return np.column_stack([mono, mono]).astype(np.float32)


def _provider(audio_by_id: dict[str, np.ndarray]):
    def provide(track: TrackProfile) -> TrackAudio:
        return TrackAudio(audio=audio_by_id[track.id], sample_rate=SR)
    return provide


def _stem_provider(audio_by_id: dict[str, np.ndarray]):
    def provide(track: TrackProfile) -> TrackAudio:
        audio = audio_by_id[track.id]
        return TrackAudio(
            audio=audio,
            sample_rate=SR,
            stems={
                "vocals": audio * 0.30,
                "drums": audio * 0.35,
                "bass": audio * 0.20,
                "other": audio * 0.15,
            },
        )
    return provide


def _small_config(**overrides) -> SetDirectorConfig:
    base = dict(beam_width=2, shortlist_width=3, max_candidates_audited_per_edge=3)
    base.update(overrides)
    return SetDirectorConfig(**base)


def test_render_full_mix_is_continuous_and_finite():
    tracks = [_track("a", bpm=120.0), _track("b", bpm=121.0), _track("c", bpm=119.0)]
    audio = _provider({t.id: _pulse_audio(bpm=t.bpm) for t in tracks})
    plan = plan_set_v2(
        tracks, audio_provider=audio, target_duration_sec=400.0, arc=SetArc.SMOOTH,
        config=_small_config(), cache=EdgeAuditionCache(),
    )
    assert len(plan.edges) == 2
    profiles = {t.id: t for t in tracks}

    mix = render_set_director_mix(plan, profiles, audio)
    assert np.isfinite(mix.audio).all()
    assert mix.audio.ndim == 2 and mix.audio.shape[1] == 2
    assert mix.sample_rate == SR
    assert mix.technique_sequence == tuple(e.handoff.selected_family for e in plan.edges)
    assert len(mix.provenance) == len(plan.edges)

    # Transitions must appear in non-overlapping, strictly increasing output
    # order, and the last one must end at or before the mix's own length --
    # proof the splice has no gap and no double-counted region.
    starts = [item["output_start_sample"] for item in mix.provenance]
    assert starts == sorted(starts)
    for i, item in enumerate(mix.provenance):
        end = item["output_start_sample"] + item["output_transition_samples"]
        assert end <= len(mix.audio)
        if i + 1 < len(mix.provenance):
            assert end <= mix.provenance[i + 1]["output_start_sample"]

    # Real overlap must have actually shortened the mix versus naively
    # concatenating every track's full duration back to back.
    naive_total = sum(t.duration_sec for t in tracks)
    assert mix.total_duration_sec < naive_total


def test_render_full_mix_honors_locked_override():
    tracks = [_track("a2", bpm=120.0), _track("b2", bpm=121.0)]
    audio = _provider({t.id: _pulse_audio(bpm=t.bpm) for t in tracks})
    plan = plan_set_v2(
        tracks, audio_provider=audio, target_duration_sec=280.0, arc=SetArc.SMOOTH,
        config=_small_config(max_candidates_audited_per_edge=8), cache=EdgeAuditionCache(),
    )
    assert len(plan.edges) == 1
    handoff = plan.edges[0].handoff
    survivors = [item for item in (handoff.ranking.auditions if handoff.ranking else ()) if not item.hard_rejected]
    if len(survivors) < 2:
        pytest.skip("fixture did not produce a second survivor to lock in this run")
    alternate_id = next(item.candidate_id for item in survivors if item.candidate_id != handoff.selected_candidate_id)
    alternate_family = handoff.candidates[alternate_id].technique_family

    profiles = {t.id: t for t in tracks}
    mix = render_set_director_mix(plan, profiles, audio, overrides={0: {"candidate_id": alternate_id}})
    assert mix.technique_sequence == (alternate_family,)


def _clipped_audio(*, bpm: float) -> np.ndarray:
    # Deliberately over-driven so every candidate touching this track
    # hard-rejects on clipping/oversampled-peak safety, regardless of family
    # -- the same technique used in the Phase 7 "globally bad path" test.
    return (_pulse_audio(bpm=bpm) * 4.5).astype(np.float32)


def test_render_full_mix_rejects_hard_rejected_override():
    tracks = [_track("a3", bpm=120.0), _track("b3", bpm=121.0)]
    audio = _provider({"a3": _pulse_audio(bpm=120.0), "b3": _clipped_audio(bpm=121.0)})
    plan = plan_set_v2(
        tracks, audio_provider=audio, target_duration_sec=280.0, arc=SetArc.SMOOTH,
        config=_small_config(max_candidates_audited_per_edge=8), cache=EdgeAuditionCache(),
    )
    handoff = plan.edges[0].handoff
    rejected = next(item for item in handoff.ranking.auditions if item.hard_rejected)

    profiles = {t.id: t for t in tracks}
    with pytest.raises(SetDirectorRenderError, match="hard-rejected"):
        render_set_director_mix(plan, profiles, audio, overrides={0: {"candidate_id": rejected.candidate_id}})


def test_render_full_mix_rejects_stem_requiring_candidate():
    import dataclasses

    source = _track("stem_source", bpm=120.0)
    target = _track("stem_target", bpm=121.0)
    composition = compose_transition_candidates(
        source, target, set_context=CandidateSetContext(), config=SetDirectorConfig().composer_config, seed=0,
    )
    assert composition.candidates, "fixture must produce at least one feasible candidate"
    # Force a stem requirement onto an otherwise-ordinary candidate so this
    # test exercises the renderer's guard deterministically, independent of
    # whether stem_handoff itself happens to be feasible for a given fixture.
    base = composition.candidates[0]
    stem_candidate = dataclasses.replace(base, stem_requirements=("source:vocals",))

    handoff = HandoffSummary(
        source_track_id="stem_source", target_track_id="stem_target", context_key="k",
        candidate_count=1, rejected_count=0, audited_count=1, survivor_count=1,
        hard_rejected_count=0, selected_candidate_id=stem_candidate.candidate_id,
        selected_family=stem_candidate.technique_family, selected_score=0.8,
        candidates={stem_candidate.candidate_id: stem_candidate},
    )
    edge = SetDirectorEdgeChoice("stem_source", "stem_target", handoff, {})
    plan = SetDirectorPlan(arc=SetArc.SMOOTH, track_ids=("stem_source", "stem_target"), edges=(edge,))
    profiles = {"stem_source": source, "stem_target": target}
    audio = _provider({"stem_source": _pulse_audio(bpm=120.0), "stem_target": _pulse_audio(bpm=121.0)})

    with pytest.raises(SetDirectorRenderError, match="requires stems"):
        render_set_director_mix(plan, profiles, audio)


def test_render_full_mix_executes_selected_stem_handoff_when_provider_supplies_stems():
    source = _track("stem_live_source", bpm=120.0, vocal=0.8, stems=True)
    target = _track("stem_live_target", bpm=121.0, vocal=0.7, stems=True)
    composition = compose_transition_candidates(
        source,
        target,
        set_context=CandidateSetContext(avoid_recent_repeats=False),
        config=SetDirectorConfig().composer_config,
        seed=0,
    )
    candidate = next(item for item in composition.candidates if item.technique_family == "stem_handoff")
    handoff = HandoffSummary(
        source_track_id=source.id,
        target_track_id=target.id,
        context_key="stem-live",
        candidate_count=1,
        rejected_count=0,
        audited_count=1,
        survivor_count=1,
        hard_rejected_count=0,
        selected_candidate_id=candidate.candidate_id,
        selected_family=candidate.technique_family,
        selected_score=0.8,
        candidates={candidate.candidate_id: candidate},
    )
    plan = SetDirectorPlan(
        arc=SetArc.SMOOTH,
        track_ids=(source.id, target.id),
        edges=(SetDirectorEdgeChoice(source.id, target.id, handoff, {}),),
    )
    profiles = {source.id: source, target.id: target}
    provider = _stem_provider({
        source.id: _pulse_audio(bpm=source.bpm),
        target.id: _pulse_audio(bpm=target.bpm),
    })

    mix = render_set_director_mix(plan, profiles, provider)

    assert mix.technique_sequence == ("stem_handoff",)
    assert mix.provenance[0]["required_stems_rendered"] is True
    assert np.isfinite(mix.audio).all()


def test_planned_full_mix_needs_no_renderer_anchor_shift():
    # This fixture used to reproduce the per-edge anchor conflict reliably.
    # Set Director now carries the middle track's entry/establishment envelope
    # into Candidate Composer, so a newly planned set must be coherent before
    # it reaches this renderer. The renderer keeps its shift fallback only for
    # old/deserialized or manually assembled plans.
    short = 60.0
    tracks = [
        _track("short_a", bpm=120.0, duration=short),
        _track("short_b", bpm=121.0, duration=short),
        _track("short_c", bpm=119.0, duration=short),
    ]
    audio = _provider({t.id: _pulse_audio(bpm=t.bpm, duration=short) for t in tracks})
    plan = plan_set_v2(
        tracks, audio_provider=audio, target_duration_sec=140.0, arc=SetArc.SMOOTH,
        config=_small_config(), cache=EdgeAuditionCache(),
    )
    assert len(plan.edges) == 2
    profiles = {t.id: t for t in tracks}

    mix = render_set_director_mix(plan, profiles, audio)
    assert np.isfinite(mix.audio).all()
    shifts = [item["anchor_shift_sec"] for item in mix.provenance]
    assert shifts == [0.0] * len(shifts)
    for i in range(1, len(mix.provenance)):
        assert mix.provenance[i]["output_start_sample"] >= (
            mix.provenance[i - 1]["output_start_sample"] + mix.provenance[i - 1]["output_transition_samples"]
        )


def test_render_full_mix_requires_at_least_two_tracks():
    solo = _track("solo", bpm=120.0)
    plan = SetDirectorPlan(arc=SetArc.SMOOTH, track_ids=("solo",), edges=())
    with pytest.raises(SetDirectorRenderError):
        render_set_director_mix(plan, {"solo": solo}, _provider({"solo": _pulse_audio(bpm=120.0)}))
