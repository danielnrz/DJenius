"""Behavioral tests for the V5.3 full-context transition planner."""

from __future__ import annotations

from djenius.core.intent import SetIntent, TransitionStyle, VocalPreference
from djenius.core.models import (
    CompatibilityScore,
    EnergyProfile,
    TrackAnalysis,
    TrackMetadata,
    TrackProfile,
    TransitionType,
)
from djenius.core.planner import _beam_search, _build_set_plan, _score_energy_trajectory
from djenius.core.scorer import score_compatibility
from djenius.core.transition_quality import playtime_bounds, score_transition_candidate


def _track(
    track_id: str,
    *,
    energy: float = 0.60,
    local_loudness: float = -14.0,
    bass: float = 0.32,
    camelot: str = "8A",
    confidence: float = 0.90,
    vocals: list[tuple[float, float]] | None = None,
    energy_curve: list[float] | None = None,
    loudness_curve: list[float] | None = None,
) -> TrackProfile:
    duration = 300.0
    bars = [float(value) for value in range(0, 300, 2)]
    phrases = [float(value) for value in range(0, 300, 16)]
    energy_values = energy_curve or [energy] * 300
    loudness_values = loudness_curve or [local_loudness] * 300
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(
            filepath=f"{track_id}.wav",
            title=track_id,
            artist="test artist",
            duration_sec=duration,
        ),
        analysis=TrackAnalysis(
            bpm=120.0,
            bpm_confidence=confidence,
            bar_times=bars,
            phrase_boundaries=phrases,
            possible_entry_points=phrases[:10],
            possible_exit_points=phrases[4:],
            camelot=camelot,
            key_confidence=confidence,
            integrated_lufs=-14.0,
            rms_energy=energy * 0.2,
            mean_energy=energy,
            energy_curve=energy_values,
            loudness_curve=loudness_values,
            low_energy_curve=[bass] * 300,
            low_energy=bass,
            mid_energy=0.30,
            structural_sections=[
                (0.0, 32.0, "intro"),
                (32.0, 144.0, "verse"),
                (144.0, 208.0, "chorus"),
                (208.0, 300.0, "outro"),
            ],
            intro_end=32.0,
            outro_start=208.0,
            vocal_regions=vocals or [],
            analysis_confidence=confidence,
        ),
    )


def _score(
    source: TrackProfile,
    target: TrackProfile,
    *,
    source_exit: float = 160.0,
    target_entry: float = 32.0,
    overlap: float = 16.0,
    transition_type: TransitionType = TransitionType.CROSSFADE,
    intent: SetIntent | None = None,
    profile: EnergyProfile = EnergyProfile.STEADY,
):
    return score_transition_candidate(
        source,
        target,
        source_exit,
        target_entry,
        overlap,
        transition_type,
        intent=intent,
        energy_profile=profile,
    )


def test_phrase_aligned_candidate_beats_unaligned_candidate():
    source = _track("source")
    target = _track("target")
    aligned, _, _ = _score(source, target)
    unaligned, _, _ = _score(source, target, source_exit=164.0, target_entry=36.0)

    assert aligned.phrase_alignment_score > unaligned.phrase_alignment_score
    assert aligned.overall_score > unaligned.overall_score


def test_severe_energy_drop_is_penalized():
    source = _track("source", energy=0.75)
    smooth_target = _track("smooth", energy=0.70)
    weak_target = _track("weak", energy=0.15)

    smooth, _, _ = _score(source, smooth_target)
    weak, _, _ = _score(source, weak_target)

    assert smooth.energy_continuity_score > weak.energy_continuity_score
    assert smooth.overall_score > weak.overall_score


def test_target_landing_lookahead_changes_candidate_quality():
    source = _track("source", energy=0.70)
    strong_curve = [0.70] * 300
    weak_curve = [0.70] * 48 + [0.08] * 20 + [0.70] * 232
    strong = _track("strong", energy=0.70, energy_curve=strong_curve)
    weak = _track("weak", energy=0.70, energy_curve=weak_curve)

    strong_quality, _, strong_context = _score(source, strong)
    weak_quality, _, weak_context = _score(source, weak)

    assert strong_context["target_entry_energy"] == weak_context["target_entry_energy"]
    assert strong_context["target_landing_energy"] > weak_context["target_landing_energy"]
    assert strong_quality.target_landing_score > weak_quality.target_landing_score


def test_transition_stage_trough_is_penalized_even_when_landing_recovers():
    source = _track("source", energy=0.70)
    stable = _track("stable", energy=0.70)
    trough_loudness = [-14.0] * 36 + [-28.0] * 8 + [-14.0] * 256
    trough = _track("trough", energy=0.70, loudness_curve=trough_loudness)

    stable_quality, _, _ = _score(source, stable)
    trough_quality, _, trough_context = _score(source, trough)

    assert stable_quality.target_landing_score == trough_quality.target_landing_score
    assert stable_quality.transition_floor_score > trough_quality.transition_floor_score
    assert trough_context["predicted_transition_trough_db"] > 5.5


def test_sudden_local_loudness_discontinuity_is_penalized():
    source = _track("source")
    matched = _track("matched")
    quiet_curve = [-14.0] * 48 + [-24.0] * 20 + [-14.0] * 232
    quiet = _track("quiet", loudness_curve=quiet_curve)

    matched_quality, matched_recipe, _ = _score(source, matched)
    quiet_quality, quiet_recipe, _ = _score(source, quiet)

    assert matched_quality.loudness_continuity_score > quiet_quality.loudness_continuity_score
    assert quiet_recipe.target_gain_db == 3.0
    assert matched_recipe.target_gain_db == 0.0


def test_vocal_on_vocal_collision_is_penalized_strongly_for_vocal_safe():
    source = _track("source", vocals=[(160.0, 176.0)])
    clear = _track("clear")
    vocal = _track("vocal", vocals=[(32.0, 48.0)])
    intent = SetIntent(vocal_preference=VocalPreference.VOCAL_SAFE)

    clear_quality, _, clear_context = _score(source, clear, intent=intent)
    vocal_quality, _, vocal_context = _score(source, vocal, intent=intent)

    assert clear_context["vocal_collision"] == 0.0
    assert vocal_context["vocal_collision"] == 1.0
    assert clear_quality.vocal_clash_score > vocal_quality.vocal_clash_score
    assert clear_quality.overall_score > vocal_quality.overall_score


def test_harmonic_compatibility_contributes_to_quality():
    source = _track("source", camelot="8A")
    compatible = _track("compatible", camelot="8A")
    clashing = _track("clashing", camelot="2B")

    compatible_quality, _, _ = _score(source, compatible)
    clashing_quality, _, _ = _score(source, clashing)

    assert compatible_quality.harmonic_compatibility_score > clashing_quality.harmonic_compatibility_score
    assert compatible_quality.overall_score > clashing_quality.overall_score


def test_chill_prefers_smooth_blend_over_phrase_cut():
    source = _track("source")
    target = _track("target")
    intent = SetIntent(transition_style=TransitionStyle.SMOOTH)

    crossfade, _, _ = _score(source, target, intent=intent)
    phrase_cut, _, _ = _score(
        source,
        target,
        intent=intent,
        transition_type=TransitionType.PHRASE_CUT,
    )

    assert crossfade.transition_style_fit_score > phrase_cut.transition_style_fit_score
    assert crossfade.overall_score > phrase_cut.overall_score


def test_energetic_allows_controlled_positive_energy_change():
    source = _track("source", energy=0.55)
    positive = _track("positive", energy=0.68)
    collapse = _track("collapse", energy=0.15)
    intent = SetIntent(transition_style=TransitionStyle.ENERGETIC)

    positive_quality, _, _ = _score(
        source, positive, intent=intent, profile=EnergyProfile.SLOW_BUILD,
    )
    collapse_quality, _, _ = _score(
        source, collapse, intent=intent, profile=EnergyProfile.SLOW_BUILD,
    )

    assert positive_quality.energy_continuity_score > collapse_quality.energy_continuity_score
    assert positive_quality.target_landing_score > collapse_quality.target_landing_score


def test_warmup_path_penalizes_strong_early_energy_regression():
    rising_tracks = [_track(f"r{i}", energy=value) for i, value in enumerate([0.2, 0.35, 0.5, 0.7])]
    falling_tracks = [_track(f"f{i}", energy=value) for i, value in enumerate([0.7, 0.3, 0.2, 0.5])]

    rising = _score_energy_trajectory(
        [track.id for track in rising_tracks],
        {track.id: track for track in rising_tracks},
        EnergyProfile.WARMUP_TO_PEAK,
    )
    falling = _score_energy_trajectory(
        [track.id for track in falling_tracks],
        {track.id: track for track in falling_tracks},
        EnergyProfile.WARMUP_TO_PEAK,
    )

    assert rising > falling


def test_warmup_search_uses_lowest_energy_track_as_opener():
    tracks = [_track(f"t{i}", energy=value) for i, value in enumerate([0.70, 0.20, 0.50, 0.35])]
    compatibility = {
        (source.id, target.id): CompatibilityScore(overall_score=0.8)
        for source in tracks for target in tracks if source.id != target.id
    }
    musical_edges = {pair: 0.8 for pair in compatibility}

    path = _beam_search(
        tracks,
        compatibility,
        target_duration=1200.0,
        beam_width=15,
        max_tracks=4,
        energy_profile=EnergyProfile.WARMUP_TO_PEAK,
        musical_edge_matrix=musical_edges,
    )

    assert path[0].mean_energy == 0.20
    assert path[-1].mean_energy >= path[0].mean_energy + 0.02


def test_minimum_useful_playtime_scales_with_track_duration():
    short = _track("short")
    short.metadata.duration_sec = 120.0
    long = _track("long")
    long.metadata.duration_sec = 1200.0

    short_minimum, _, _ = playtime_bounds(short)
    long_minimum, _, _ = playtime_bounds(long)

    assert short_minimum >= 55.0
    assert long_minimum > short_minimum


def test_low_confidence_pair_uses_conservative_transition():
    source = _track("source", confidence=0.30)
    target = _track("target", confidence=0.30)
    compat = score_compatibility(source, target)
    intent = SetIntent(transition_style=TransitionStyle.ENERGETIC)

    plan = _build_set_plan(
        [source, target],
        {(source.id, target.id): compat},
        600.0,
        EnergyProfile.STEADY,
        max_transition_bars=16,
        allowed_transition_types=intent.allowed_transition_types(),
        intent=intent,
    )

    assert plan.transitions[0].transition_type == TransitionType.BEATMATCHED_BLEND
    assert plan.final_track_end_time is not None
    assert plan.final_track_end_time < target.duration_sec


def test_bad_bass_handoff_is_penalized_for_unmanaged_style():
    source = _track("source", bass=0.50)
    target = _track("target", bass=0.50)

    managed, managed_recipe, _ = _score(
        source, target, transition_type=TransitionType.FILTER_SWEEP,
    )
    unmanaged, unmanaged_recipe, _ = _score(
        source, target, transition_type=TransitionType.BEATMATCHED_BLEND,
    )

    assert managed.bass_handoff_score > unmanaged.bass_handoff_score
    assert managed_recipe.bass_handoff_mode == "source_to_target"
    assert unmanaged_recipe.bass_handoff_mode == "source_to_target"
