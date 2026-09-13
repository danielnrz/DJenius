from __future__ import annotations

import numpy as np
import pytest

from djenius.core.analysis_v2 import build_tempo_hypotheses
from djenius.audio.set_director_renderer import render_set_director_mix
from djenius.core.audition_lab import audition_candidate, rank_auditions
from djenius.core.candidate_composer import CandidateSetContext, compose_transition_candidates
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile
from djenius.core.set_director import (
    EdgeAuditionCache,
    SetArc,
    SetDirectorConfig,
    SetDirectorEdgeChoice,
    SetDirectorComputeStats,
    TrackAudio,
    _estimate_overlap_sec,
    _family_diverse_order,
    arc_energy_target,
    bpm_relationship,
    compare_to_shuffled_baselines,
    evaluate_edge,
    measure_set_quality,
    plan_set_v2,
)

SR = 6000
DURATION = 60.0


def _track(
    track_id: str,
    *,
    bpm: float = 120.0,
    camelot: str = "8A",
    mean_energy: float = 0.5,
    vocal: float = 0.08,
    artist: str = "",
    duration: float = DURATION,
    bpm_confidence: float = 0.97,
) -> TrackProfile:
    third = duration / 3.0
    sections = [
        {
            "start_sec": 0.0, "end_sec": third, "label": "intro",
            "boundary_confidence": 0.9, "mix_in_score": 0.9, "mix_out_score": 0.35,
            "landing_strength": 0.3, "bass_density": 0.55, "energy_mean": mean_energy,
        },
        {
            "start_sec": third, "end_sec": 2 * third, "label": "drop",
            "boundary_confidence": 0.9, "mix_in_score": 0.88, "mix_out_score": 0.78,
            "landing_strength": 0.75, "bass_density": 0.65, "energy_mean": mean_energy,
        },
        {
            "start_sec": 2 * third, "end_sec": duration, "label": "outro",
            "boundary_confidence": 0.9, "mix_in_score": 0.3, "mix_out_score": 0.96,
            "landing_strength": 0.25, "bass_density": 0.50, "energy_mean": mean_energy,
        },
    ]
    cues = [
        {
            "time_sec": 0.0, "bar_index": 1, "beat_in_bar": 1, "confidence": 0.9,
            "section": "intro", "use_cases": ["mix_in"], "mix_in_score": 0.9, "mix_out_score": 0.2,
        },
        {
            "time_sec": third, "bar_index": 17, "beat_in_bar": 1, "confidence": 0.9,
            "section": "drop", "use_cases": ["mix_in", "phrase_cut", "drop_landing"],
            "mix_in_score": 0.88, "mix_out_score": 0.78,
        },
        {
            "time_sec": 2 * third, "bar_index": 33, "beat_in_bar": 1, "confidence": 0.9,
            "section": "outro", "use_cases": ["mix_out", "phrase_cut"],
            "mix_in_score": 0.3, "mix_out_score": 0.96,
        },
    ]
    analysis = TrackAnalysis(
        bpm=bpm,
        bpm_confidence=bpm_confidence,
        camelot=camelot,
        analysis_confidence=0.95,
        tempo_hypotheses=build_tempo_hypotheses(bpm, bpm_confidence),
        section_profiles=sections,
        cue_candidates=cues,
        vocal_activity_curve=[vocal] * int(duration),
        energy_curve=[mean_energy] * int(duration),
        mean_energy=mean_energy,
        low_energy=0.55,
        groove_profile={
            "confidence": 0.9, "syncopation_index": 0.25, "swing_ratio": 1.0,
            "percussion_density_mean": 0.55,
        },
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=f"/synthetic/{track_id}.wav", duration_sec=duration, artist=artist),
        analysis=analysis,
    )


def _pulse_audio(*, bpm: float, duration: float = DURATION, gain: float = 0.30) -> np.ndarray:
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


def _clipped_audio(*, bpm: float, duration: float = DURATION) -> np.ndarray:
    # Deliberately over-driven so any transition touching this track hard-rejects
    # on clipping/oversampled-peak, no matter how compatible it looks on paper.
    audio = _pulse_audio(bpm=bpm, duration=duration, gain=0.30)
    return (audio * 4.5).astype(np.float32)


def _provider(audio_by_id: dict[str, np.ndarray]) -> callable:
    def provide(track: TrackProfile) -> TrackAudio:
        return TrackAudio(audio=audio_by_id[track.id], sample_rate=SR)
    return provide


def _small_config(**overrides) -> SetDirectorConfig:
    base = dict(beam_width=3, shortlist_width=3, max_candidates_audited_per_edge=2)
    base.update(overrides)
    return SetDirectorConfig(**base)


# ---------------------------------------------------------------------------
# Pure arc-shape tests (no audio, no audition)
# ---------------------------------------------------------------------------

def test_energy_arc_shapes():
    smooth = [arc_energy_target(SetArc.SMOOTH, p / 10) for p in range(11)]
    assert max(smooth) - min(smooth) < 0.20  # modest movement

    warmup = [arc_energy_target(SetArc.WARMUP_TO_PEAK, p / 10) for p in range(11)]
    assert warmup[0] < warmup[5] < warmup[7]  # rises toward the final third
    peak_index = max(range(len(warmup)), key=lambda i: warmup[i])
    assert peak_index / 10 >= 0.6  # peak sits in the back half
    assert warmup[-1] < warmup[peak_index]  # cools down after the peak

    peak_time = [arc_energy_target(SetArc.PEAK_TIME, p / 10) for p in range(11)]
    assert min(peak_time) >= 0.65  # sustained high energy throughout

    wave = [arc_energy_target(SetArc.WAVE, p / 100) for p in range(101)]
    local_maxima = sum(
        1 for i in range(1, len(wave) - 1) if wave[i] > wave[i - 1] and wave[i] > wave[i + 1]
    )
    assert local_maxima >= 2  # at least two build/peak cycles

    open_format = [arc_energy_target(SetArc.OPEN_FORMAT, p / 10) for p in range(11)]
    assert max(open_format) - min(open_format) < 1e-9  # flat; de-emphasized on purpose


def test_reset_budget_differs_by_arc():
    config = _small_config()
    smooth = config.effective_max_reset_budget(SetArc.SMOOTH)
    default_arc = config.effective_max_reset_budget(SetArc.PEAK_TIME)
    open_format = config.effective_max_reset_budget(SetArc.OPEN_FORMAT)
    assert smooth < default_arc < open_format  # a smooth journey tolerates the fewest resets


def test_bpm_relationship_half_double_and_reset():
    slow = _track("slow", bpm=72.0)
    fast_double = _track("fast_double", bpm=144.0)
    unrelated = _track("unrelated", bpm=101.0)

    doubled = bpm_relationship(slow, fast_double)
    assert doubled["relation"] != "primary"  # resolved via target's half/double hypothesis
    assert doubled["delta_pct"] < 3.0
    assert doubled["is_reset"] is False

    jump = bpm_relationship(slow, unrelated)
    assert jump["relation"] == "primary"
    assert jump["delta_pct"] > 12.0
    assert jump["is_reset"] is True


# ---------------------------------------------------------------------------
# measure_set_quality: independent, audition-optional facts
# ---------------------------------------------------------------------------

def test_measure_set_quality_vocal_pacing_and_artist_spacing():
    heavy_a = _track("heavy_a", vocal=0.75, artist="Same Artist")
    heavy_b = _track("heavy_b", vocal=0.80, artist="Same Artist")
    calm = _track("calm", vocal=0.05, artist="Other Artist")

    clashing = measure_set_quality([heavy_a, heavy_b, calm], edges=(), arc=SetArc.SMOOTH)
    assert clashing.consecutive_vocal_heavy_count == 1

    spaced = measure_set_quality([heavy_a, calm, heavy_b], edges=(), arc=SetArc.SMOOTH)
    assert spaced.consecutive_vocal_heavy_count == 0

    repeated_artist = measure_set_quality(
        [heavy_a, calm, heavy_b], edges=(), arc=SetArc.SMOOTH, artist_spacing_min_tracks=3,
    )
    assert repeated_artist.artist_spacing_violations == 1

    no_repeat_needed = measure_set_quality(
        [heavy_a, calm, heavy_b], edges=(), arc=SetArc.SMOOTH, artist_spacing_min_tracks=2,
    )
    assert no_repeat_needed.artist_spacing_violations == 0


def test_measure_set_quality_technique_repetition():
    tracks = [_track(f"t{i}") for i in range(4)]

    def edge(a, b, family):
        from djenius.core.set_director import HandoffSummary
        summary = HandoffSummary(
            source_track_id=a, target_track_id=b, context_key="k",
            candidate_count=1, rejected_count=0, audited_count=1, survivor_count=1,
            hard_rejected_count=0, selected_candidate_id="cand", selected_family=family,
            selected_score=0.7,
        )
        return SetDirectorEdgeChoice(a, b, summary, {})

    repeated = (
        edge("t0", "t1", "eq_blend"),
        edge("t1", "t2", "eq_blend"),
        edge("t2", "t3", "eq_blend"),
    )
    metrics = measure_set_quality(tracks, repeated, arc=SetArc.SMOOTH)
    assert metrics.dominant_technique_share == 1.0
    assert metrics.max_technique_run == 3

    varied = (
        edge("t0", "t1", "eq_blend"),
        edge("t1", "t2", "loop_shortening"),
        edge("t2", "t3", "echo_out"),
    )
    metrics_varied = measure_set_quality(tracks, varied, arc=SetArc.SMOOTH)
    assert metrics_varied.dominant_technique_share < 0.5
    assert metrics_varied.max_technique_run == 1


# ---------------------------------------------------------------------------
# evaluate_edge: exact Phase 6 integration
# ---------------------------------------------------------------------------

def test_evaluate_edge_matches_direct_phase5_phase6_call():
    source = _track("source", bpm=120.0)
    target = _track("target", bpm=121.0)
    audio = _provider({
        "source": _pulse_audio(bpm=120.0),
        "target": _pulse_audio(bpm=121.0),
    })
    context = CandidateSetContext()
    config = _small_config()
    cache = EdgeAuditionCache()
    stats = SetDirectorComputeStats()

    summary = evaluate_edge(
        source, target, audio_provider=audio, set_context=context,
        config=config, cache=cache, stats=stats,
    )

    composition = compose_transition_candidates(source, target, set_context=context, config=config.composer_config, seed=config.seed)
    ordered = _family_diverse_order(composition.candidates)[: config.max_candidates_audited_per_edge]
    auditions = [
        audition_candidate(c, _pulse_audio(bpm=120.0), _pulse_audio(bpm=121.0), SR, config=config.audition_config)
        for c in ordered
    ]
    ranking = rank_auditions(auditions, config=config.audition_config)
    expected_selected = next((a for a in ranking.auditions if a.selected), None)

    assert summary.selected_candidate_id == (expected_selected.candidate_id if expected_selected else None)
    assert summary.selected_score == pytest.approx(expected_selected.final_score if expected_selected else 0.0)
    assert summary.survivor_count == ranking.survivor_count
    assert stats.cache_misses == 1
    assert stats.cache_hits == 0

    # Repeating the identical call must be a pure cache hit with an identical result.
    summary_again = evaluate_edge(
        source, target, audio_provider=audio, set_context=context,
        config=config, cache=cache, stats=stats,
    )
    assert summary_again.selected_candidate_id == summary.selected_candidate_id
    assert summary_again.cache_hit is True
    assert stats.cache_hits == 1


# ---------------------------------------------------------------------------
# plan_set_v2: end-to-end behavior
# ---------------------------------------------------------------------------

def _library(n: int, *, bpm: float = 120.0, camelot: str = "8A") -> tuple[list[TrackProfile], dict[str, np.ndarray]]:
    tracks = []
    audio = {}
    for i in range(n):
        track_id = f"lib{i}"
        tracks.append(_track(track_id, bpm=bpm + i * 0.3, camelot=camelot, artist=f"Artist {i}"))
        audio[track_id] = _pulse_audio(bpm=bpm + i * 0.3)
    return tracks, audio


def test_plan_is_deterministic_and_repeatable():
    tracks, audio = _library(5)
    provider = _provider(audio)
    config = _small_config()

    plan_a = plan_set_v2(tracks, audio_provider=provider, target_duration_sec=200.0, arc=SetArc.SMOOTH, config=config, cache=EdgeAuditionCache())
    plan_b = plan_set_v2(tracks, audio_provider=provider, target_duration_sec=200.0, arc=SetArc.SMOOTH, config=config, cache=EdgeAuditionCache())

    assert plan_a.to_dict() == plan_b.to_dict()


def test_plan_has_no_duplicate_tracks_and_uses_known_ids():
    tracks, audio = _library(5)
    provider = _provider(audio)
    plan = plan_set_v2(tracks, audio_provider=provider, target_duration_sec=200.0, arc=SetArc.SMOOTH, config=_small_config())

    assert len(plan.track_ids) == len(set(plan.track_ids))
    known_ids = {track.id for track in tracks}
    assert set(plan.track_ids).issubset(known_ids)
    assert len(plan.edges) == len(plan.track_ids) - 1


def test_plan_duration_handling_and_stopping():
    tracks, audio = _library(6)
    provider = _provider(audio)
    plan = plan_set_v2(tracks, audio_provider=provider, target_duration_sec=140.0, arc=SetArc.SMOOTH, config=_small_config())

    assert 2 <= len(plan.track_ids) <= 6
    assert plan.total_duration_sec > 0
    assert plan.compute_stats["candidates_rendered"] > 0


def test_stable_tie_breaking_on_identical_openers():
    tied_a = _track("z_tied", bpm=120.0, mean_energy=0.5)
    tied_b = _track("a_tied", bpm=120.0, mean_energy=0.5)
    other = _track("m_other", bpm=150.0, mean_energy=0.9)
    tracks = [tied_a, tied_b, other]
    audio = _provider({
        "z_tied": _pulse_audio(bpm=120.0), "a_tied": _pulse_audio(bpm=120.0), "m_other": _pulse_audio(bpm=150.0),
    })
    plan = plan_set_v2(tracks, audio_provider=audio, target_duration_sec=200.0, arc=SetArc.SMOOTH, config=_small_config(beam_width=1))
    # With a tied start score, the lexicographically smaller id must win deterministically.
    assert plan.track_ids[0] == "a_tied"


def test_small_and_insufficient_library():
    empty_plan = plan_set_v2([], audio_provider=_provider({}), target_duration_sec=100.0)
    assert empty_plan.track_ids == ()
    assert "Fewer than two" in empty_plan.human_readable_reasons[0]

    one = _track("solo")
    one_plan = plan_set_v2([one], audio_provider=_provider({}), target_duration_sec=100.0)
    assert one_plan.track_ids == ("solo",)
    assert one_plan.edges == ()

    a, b = _track("a2"), _track("b2", bpm=121.0)
    audio = _provider({"a2": _pulse_audio(bpm=120.0), "b2": _pulse_audio(bpm=121.0)})
    two_plan = plan_set_v2([a, b], audio_provider=audio, target_duration_sec=100.0, config=_small_config())
    assert set(two_plan.track_ids) == {"a2", "b2"}
    assert len(two_plan.edges) == 1


def test_missing_metadata_does_not_crash():
    bare = TrackProfile(
        id="bare",
        metadata=TrackMetadata(filepath="/synthetic/bare.wav", duration_sec=DURATION, artist=""),
        analysis=TrackAnalysis(bpm=120.0, bpm_confidence=0.9, camelot="", mean_energy=0.5),
    )
    normal = _track("normal", bpm=121.0)
    audio = _provider({"bare": _pulse_audio(bpm=120.0), "normal": _pulse_audio(bpm=121.0)})
    plan = plan_set_v2([bare, normal], audio_provider=audio, target_duration_sec=90.0, config=_small_config())
    assert set(plan.track_ids) == {"bare", "normal"}


def test_changed_arc_changes_plan():
    tracks = [
        _track("open", bpm=120.0, mean_energy=0.2, artist="A"),
        _track("mid", bpm=121.0, mean_energy=0.5, artist="B"),
        _track("peak", bpm=122.0, mean_energy=0.9, artist="C"),
    ]
    audio = _provider({t.id: _pulse_audio(bpm=t.bpm) for t in tracks})

    warmup_plan = plan_set_v2(tracks, audio_provider=audio, target_duration_sec=200.0, arc=SetArc.WARMUP_TO_PEAK, config=_small_config())
    peak_time_plan = plan_set_v2(tracks, audio_provider=audio, target_duration_sec=200.0, arc=SetArc.PEAK_TIME, config=_small_config())

    assert warmup_plan.track_ids != peak_time_plan.track_ids or warmup_plan.component_totals != peak_time_plan.component_totals
    # A genuine warm-up-to-peak journey should not open on the highest-energy track.
    assert warmup_plan.track_ids[0] != "peak"


def test_search_avoids_repeating_artist_when_a_good_alternative_exists():
    opener = _track("opener", bpm=120.0, camelot="8A", artist="Same Act")
    # Identical BPM/key/vocal/energy to isolate artist repetition as the only
    # real difference between these two otherwise-equivalent next tracks.
    same_artist = _track("same_artist_next", bpm=121.0, camelot="8A", artist="Same Act")
    other_artist = _track("other_artist_next", bpm=121.0, camelot="8A", artist="Different Act")
    tracks = [opener, same_artist, other_artist]
    audio = _provider({
        "opener": _pulse_audio(bpm=120.0),
        "same_artist_next": _pulse_audio(bpm=121.0),
        "other_artist_next": _pulse_audio(bpm=121.0),
    })
    plan = plan_set_v2(
        tracks, audio_provider=audio, target_duration_sec=100.0, arc=SetArc.SMOOTH,
        config=_small_config(beam_width=2, shortlist_width=3),
    )
    assert plan.track_ids[0] == "opener"
    assert plan.track_ids[1] == "other_artist_next", (
        f"expected the same-artist repeat to be avoided in favor of the equally good alternative, got {plan.track_ids}"
    )


def test_edge_cache_reused_across_repeated_planning():
    tracks, audio = _library(5)
    provider = _provider(audio)
    config = _small_config()
    shared_cache = EdgeAuditionCache()

    first = plan_set_v2(tracks, audio_provider=provider, target_duration_sec=200.0, arc=SetArc.SMOOTH, config=config, cache=shared_cache)
    assert first.compute_stats["cache_misses"] > 0

    second = plan_set_v2(tracks, audio_provider=provider, target_duration_sec=200.0, arc=SetArc.SMOOTH, config=config, cache=shared_cache)
    assert second.track_ids == first.track_ids
    assert second.total_score == pytest.approx(first.total_score)
    assert all(edge.handoff.cache_hit is False for edge in first.edges)
    assert all(edge.handoff.cache_hit is True for edge in second.edges)
    assert second.compute_stats["cache_misses"] == 0
    assert second.compute_stats["cache_hits"] == second.compute_stats["edges_shortlisted"]


# ---------------------------------------------------------------------------
# The defining Phase 7 test: a globally-aware search beats a locally-greedy one.
# ---------------------------------------------------------------------------

def test_locally_tempting_edge_loses_to_globally_better_path():
    """A -> B looks like the best possible next move on paper (near-identical
    BPM/key), but B's audio is over-driven and hard-rejects on audition no
    matter which candidate family is tried. A -> Z is a slightly less
    "perfect" pairing on paper but survives audition cleanly. A beam wide
    enough to keep both first moves alive must prefer Z; a beam narrowed to
    pure greedy (width=1) still must not be fooled into keeping the
    hard-rejected edge once it is actually auditioned.
    """
    # OPEN_FORMAT's flat energy target (0.55) is matched exactly only by the
    # opener, so it deterministically wins the start regardless of beam width;
    # the interesting decision is entirely which track it hands off to next.
    a = _track("a_open", bpm=120.0, camelot="8A", mean_energy=0.55)
    b_tempting = _track("b_tempting", bpm=121.0, camelot="8A", mean_energy=0.50)
    z_real = _track("z_real", bpm=118.0, camelot="9A", mean_energy=0.50)

    audio = _provider({
        "a_open": _pulse_audio(bpm=120.0),
        "b_tempting": _clipped_audio(bpm=121.0),
        "z_real": _pulse_audio(bpm=118.0),
    })
    tracks = [a, b_tempting, z_real]
    config = _small_config(beam_width=2, shortlist_width=3)

    plan = plan_set_v2(tracks, audio_provider=audio, target_duration_sec=100.0, arc=SetArc.OPEN_FORMAT, config=config)

    assert plan.track_ids[0] == "a_open"
    assert plan.track_ids[1] == "z_real", (
        f"expected the search to avoid the hard-rejected tempting edge, got {plan.track_ids}"
    )
    chosen_edge = plan.edges[0]
    assert chosen_edge.target_track_id == "z_real"
    assert chosen_edge.handoff.selected_candidate_id is not None
    assert chosen_edge.handoff.survivor_count > 0

    # Sanity-check the fixture itself: b_tempting's audio is genuinely over
    # driven, so any avoidance the plan shows is a real audition-driven
    # decision (the search actually rendered and rejected it), not luck.
    assert float(np.max(np.abs(audio(b_tempting).audio))) > 1.0


def test_plan_never_selects_a_hard_rejected_edge():
    """A plan must always be renderable.

    Confirmed as a real defect against this exact fixture: before this fix,
    the beam search would still score and select an edge whose every audited
    candidate hard-rejected on audition (e.g. `b_tempting`'s clipped audio
    against any neighbour), because nothing excluded a zero-survivor edge
    from `expanded` -- it just contributed a 0.0 handoff-quality component
    and rode the rest of the score. `render_set_director_mix` then raises
    `SetDirectorRenderError` for such a handoff, since there is no candidate
    to render. A plan must never be able to reach that state: every edge it
    contains must have a real, audition-surviving selected candidate, even
    when (as here) that means finishing with fewer tracks than the library
    holds rather than forcing in an unusable one.
    """
    a = _track("a_open", bpm=120.0, camelot="8A", mean_energy=0.55)
    b_tempting = _track("b_tempting", bpm=121.0, camelot="8A", mean_energy=0.50)
    z_real = _track("z_real", bpm=118.0, camelot="9A", mean_energy=0.50)

    audio = _provider({
        "a_open": _pulse_audio(bpm=120.0),
        "b_tempting": _clipped_audio(bpm=121.0),
        "z_real": _pulse_audio(bpm=118.0),
    })
    tracks = [a, b_tempting, z_real]
    profiles = {t.id: t for t in tracks}

    for beam_width in (1, 2, 3):
        config = _small_config(beam_width=beam_width, shortlist_width=3)
        plan = plan_set_v2(tracks, audio_provider=audio, target_duration_sec=100.0, arc=SetArc.OPEN_FORMAT, config=config)

        assert len(plan.edges) >= 1, f"beam_width={beam_width}: plan has no transitions at all"
        for edge in plan.edges:
            assert edge.handoff.selected_candidate_id is not None, (
                f"beam_width={beam_width}: edge {edge.source_track_id}->{edge.target_track_id} "
                "has no selected candidate and cannot be rendered"
            )
            assert edge.handoff.survivor_count > 0, (
                f"beam_width={beam_width}: edge {edge.source_track_id}->{edge.target_track_id} "
                "was included despite every candidate hard-rejecting on audition"
            )

        # The real end-to-end guarantee: rendering the plan must not raise.
        mix = render_set_director_mix(plan, profiles, audio)
        assert mix.total_duration_sec > 0.0


def test_planned_duration_is_far_closer_to_the_actual_render_than_before():
    """The beam search's own `total_duration_sec` estimate must actually
    approximate how long the rendered mix comes out to be, not just be some
    unrelated number the search happens to compare against its target.

    Confirmed as a real defect against real music: the old `_estimate_overlap_sec`
    heuristic assumed every track contributes close to its full length once a
    flat ~16-bar overlap is subtracted, when in reality anchors routinely land
    deep inside a track -- only the slice between its entry anchor and its own
    exit anchor ends up playing. On one real 4-track plan this overstated the
    true duration by ~236s (664.0s planned vs 427.8s actually rendered). The
    fix derives the running estimate from each edge's own real chosen anchors
    instead of the flat heuristic.

    This does not make the estimate exact: a middle track's entry anchor (from
    the edge before it) and its own exit anchor (for the edge after it) are
    still chosen independently by Candidate Composer, which has no notion of
    "the edge before" or "the edge after" (see `set_director_renderer.py`'s
    module docstring). When those two independently-valid anchors conflict,
    the renderer's `anchor_shift_sec` correction (D044) consumes a few extra
    real seconds that the plan-time estimate cannot see in advance -- a
    separate, deeper architectural gap (Candidate Composer has no way to
    receive "this track is already consumed until X seconds" as an input)
    that is tracked on its own rather than papered over here.
    """
    t1 = _track("t1", bpm=120.0, camelot="8A", mean_energy=0.3, duration=90.0)
    t2 = _track("t2", bpm=121.0, camelot="8A", mean_energy=0.55, duration=90.0)
    t3 = _track("t3", bpm=119.0, camelot="9A", mean_energy=0.8, duration=90.0)
    tracks = [t1, t2, t3]
    by_id = {t.id: t for t in tracks}
    audio = _provider({t.id: _pulse_audio(bpm=t.bpm, duration=t.duration_sec) for t in tracks})

    config = _small_config(beam_width=3, shortlist_width=3)
    plan = plan_set_v2(tracks, audio_provider=audio, target_duration_sec=225.0, arc=SetArc.WARMUP_TO_PEAK, config=config)
    assert len(plan.track_ids) == 3

    mix = render_set_director_mix(plan, by_id, audio)

    # Reconstruct what the old "every track contributes close to its full
    # duration" heuristic would have estimated for this exact chosen order.
    ordered = [by_id[tid] for tid in plan.track_ids]
    naive_estimate = sum(t.duration_sec for t in ordered) - sum(
        _estimate_overlap_sec(a, b) for a, b in zip(ordered, ordered[1:])
    )
    old_error = abs(naive_estimate - mix.total_duration_sec)
    new_error = abs(plan.total_duration_sec - mix.total_duration_sec)
    assert new_error < old_error * 0.5, (
        f"expected the anchor-based estimate ({plan.total_duration_sec}, error={new_error}) "
        f"to be far closer to the actual render ({mix.total_duration_sec}) than the old flat "
        f"heuristic ({naive_estimate}, error={old_error})"
    )


# ---------------------------------------------------------------------------
# Shuffled-baseline gate: independent metrics, many seeded shuffles.
# ---------------------------------------------------------------------------

def test_planned_set_beats_shuffled_baselines_on_independent_metrics():
    energies = [0.10, 0.28, 0.46, 0.64, 0.82, 0.95]
    tracks = [
        _track(f"e{i}", bpm=120.0, camelot="8A", mean_energy=energy, artist=f"Artist {i}")
        for i, energy in enumerate(energies)
    ]
    audio = _provider({t.id: _pulse_audio(bpm=120.0) for t in tracks})
    config = _small_config(beam_width=3, shortlist_width=4, max_candidates_audited_per_edge=2)

    plan = plan_set_v2(tracks, audio_provider=audio, target_duration_sec=300.0, arc=SetArc.WARMUP_TO_PEAK, max_tracks=6, config=config)
    assert len(plan.track_ids) == 6  # every track fits; ordering is the only free variable

    result = compare_to_shuffled_baselines(
        tracks, plan.edges, SetArc.WARMUP_TO_PEAK, audio_provider=audio,
        config=config, shuffle_count=10, seed=7,
    )

    gate = result["planned_beats_baseline"]
    # This fixture holds BPM/key/vocal identical across every track on purpose,
    # isolating energy-arc placement as the only thing ordering can improve;
    # audition-family selection then follows from arc position/context rather
    # than from "better" vs "worse" ordering, so mean_selected_audition_score
    # is reported for visibility but is not a meaningful discriminator here.
    assert gate["energy_arc_error"] is True
    assert gate["peak_placement_error"] is True
    assert gate["viable_audition_edge_rate"] is True
    assert result["planned"]["mean_selected_audition_score"] > 0.0
