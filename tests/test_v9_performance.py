"""Behavioral coverage for V9 segment performance and provenance."""

import pytest
import numpy as np
import soundfile as sf

from djenius.audio.provenance import audit_performance_provenance
from djenius.core.intent import SetIntent
from djenius.core.models import (
    PerformanceAppearance,
    PerformanceSegment,
    PerformanceTimeline,
    PerformanceTransition,
    TrackAnalysis,
    TrackMetadata,
    TrackProfile,
    TransitionType,
)
from djenius.core.performance import (
    extract_performance_segments,
    plan_performance_timeline,
    require_valid_performance_timeline,
    validate_performance_timeline,
    reorder_performance_timeline,
    score_segment_pair,
)
from djenius.audio.performance_renderer import render_performance_mix
from djenius.core.planner import plan_set
from djenius.application import LocalAppService


def profile(track_id: str, *, duration: float = 180.0, energy: float = 0.5, bpm: float = 120.0) -> TrackProfile:
    analysis = TrackAnalysis(
        bpm=bpm,
        bpm_confidence=0.95,
        bar_times=[float(index * 2) for index in range(int(duration // 2))],
        phrase_boundaries=[float(index * 8) for index in range(int(duration // 8))],
        energy_curve=[energy] * int(duration),
        low_energy_curve=[0.2] * int(duration),
        analysis_confidence=0.95,
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=f"/tmp/{track_id}.wav", title=track_id, duration_sec=duration),
        analysis=analysis,
    )


def test_quick_pair_uses_contextual_recipe_not_universal_phrase_cut():
    source = profile("source", bpm=160.0)
    target = profile("target", bpm=110.0)
    source_segment, target_segment = extract_performance_segments(source)[0], extract_performance_segments(target)[0]
    pair = score_segment_pair(source, source_segment, target, target_segment, style="quick_mix")
    assert pair.transition_type != TransitionType.PHRASE_CUT
    assert pair.length_bars >= 1
    assert pair.overlap_duration_sec > 0.55


def test_phrase_cut_requires_close_tempo_and_safe_boundaries():
    source = profile("source", bpm=160.0)
    target = profile("target", bpm=110.0)
    source_segment, target_segment = extract_performance_segments(source)[0], extract_performance_segments(target)[0]
    pair = score_segment_pair(source, source_segment, target, target_segment, style="quick_mix")
    assert pair.transition_type != TransitionType.PHRASE_CUT


def test_pair_transition_carries_local_handoff_evidence():
    source = profile("source", energy=0.25)
    target = profile("target", energy=0.75)
    source_segment, target_segment = extract_performance_segments(source)[0], extract_performance_segments(target)[0]
    pair = score_segment_pair(source, source_segment, target, target_segment, style="quick_mix")
    assert 0.0 <= pair.phase_score <= 1.0
    assert 0.0 <= pair.loudness_score <= 1.0
    assert 0.0 <= pair.bass_score <= 1.0
    assert pair.explanation


def test_beatmatched_transition_declares_target_source_consumption():
    source = profile("source", bpm=120.0)
    target = profile("target", bpm=110.0)
    source_segment, target_segment = extract_performance_segments(source)[0], extract_performance_segments(target)[0]
    pair = score_segment_pair(source, source_segment, target, target_segment, style="quick_mix")
    if pair.transition_type == TransitionType.BEATMATCHED_BLEND and pair.requires_stretch:
        assert pair.target_consumed_duration_sec >= pair.overlap_duration_sec


def test_segments_use_known_bar_boundaries_and_stay_inside_source():
    track = profile("a")
    segments = extract_performance_segments(track)
    assert segments
    for segment in segments:
        assert segment.source_start_sec in track.analysis.bar_times or segment.source_start_sec == 0
        assert segment.source_end_sec <= track.duration_sec
        assert segment.duration_sec >= 4 * 60 / track.bpm * 4 * 0.65


def test_segment_mode_hits_short_target_with_multiple_appearances():
    tracks = [profile(str(index)) for index in range(5)]
    intent = SetIntent(target_duration_sec=180, performance_mode="segment", performance_style="quick_mix")
    plan = plan_set(tracks, 180, intent=intent, seed=4)
    assert plan.performance_timeline is not None
    assert len(plan.performance_timeline.appearances) >= 4
    assert abs(plan.total_duration_sec - 180) <= 30
    require_valid_performance_timeline(plan.performance_timeline, {track.id: track.duration_sec for track in tracks})


def test_same_track_reprise_requires_a_different_source_region():
    tracks = [profile("a"), profile("b"), profile("c")]
    timeline, _ = plan_performance_timeline(tracks, 180, SetIntent(), seed=2, performance_style="experimental")
    repeated = [item for item in timeline.appearances if item.segment.track_id == "a"]
    if len(repeated) >= 2:
        assert repeated[1].reprise
        assert (repeated[0].segment.source_start_sec, repeated[0].segment.source_end_sec) != (
            repeated[1].segment.source_start_sec, repeated[1].segment.source_end_sec,
        )


def test_planner_never_reuses_an_identical_source_slice():
    tracks = [profile("a"), profile("b")]
    timeline, _ = plan_performance_timeline(
        tracks, 240, SetIntent(), seed=8, performance_style="quick_mix",
    )
    regions = {}
    for appearance in timeline.appearances:
        region = (appearance.segment.source_start_sec, appearance.segment.source_end_sec)
        assert region not in regions.setdefault(appearance.segment.track_id, set())
        regions[appearance.segment.track_id].add(region)


def test_duplicate_source_region_is_rejected_even_when_marked_reprise():
    first = PerformanceSegment(id="s1", track_id="a", source_start_sec=10, source_end_sec=30)
    second = PerformanceSegment(id="s2", track_id="a", source_start_sec=10, source_end_sec=30)
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_end_sec=20),
            PerformanceAppearance(id="two", segment=second, output_start_sec=19, output_end_sec=39, reprise=True),
        ],
        transitions=[PerformanceTransition(source_appearance_id="one", target_appearance_id="two", overlap_duration_sec=1, source_start_sec=29, source_end_sec=30, target_start_sec=10, target_end_sec=11)],
        total_duration_sec=39,
    )
    assert any("duplicate source region" in item for item in validate_performance_timeline(timeline, {"a": 60}))


def test_provenance_allows_declared_transition_but_catches_unplanned_replay():
    events = [
        {"type": "appearance", "track_id": "a", "source_start_sample": 0, "source_end_sample": 100, "output_start_sample": 0, "output_end_sample": 100, "reprise": False},
        {"type": "appearance", "track_id": "a", "source_start_sample": 200, "source_end_sample": 300, "output_start_sample": 90, "output_end_sample": 190, "reprise": True},
        {"type": "performance_transition", "source_track_id": "a", "target_track_id": "a", "source_start_sample": 90, "source_end_sample": 100, "target_start_sample": 200, "target_end_sample": 210},
    ]
    assert audit_performance_provenance(events, {"a": 400})["clean"]
    events[1]["source_start_sample"] = 0
    events[1]["source_end_sample"] = 100
    assert not audit_performance_provenance(events, {"a": 400})["clean"]


def test_classic_mode_has_no_performance_timeline():
    tracks = [profile("a"), profile("b")]
    plan = plan_set(tracks, 180, intent=SetIntent(target_duration_sec=180, performance_mode="classic"), seed=1)
    assert plan.performance_timeline is None
    assert plan.performance_mode == "classic"


def test_seed_is_reproducible_and_can_choose_an_alternative_path():
    tracks = [profile(str(index)) for index in range(6)]
    intent = SetIntent(target_duration_sec=180, performance_mode="segment", performance_style="quick_mix")
    first, _ = plan_performance_timeline(tracks, 180, intent, seed=11, performance_style="quick_mix")
    repeat, _ = plan_performance_timeline(tracks, 180, intent, seed=11, performance_style="quick_mix")
    alternative, _ = plan_performance_timeline(tracks, 180, intent, seed=12, performance_style="quick_mix")
    assert [item.segment.id for item in first.appearances] == [item.segment.id for item in repeat.appearances]
    assert [item.segment.id for item in first.appearances] != [item.segment.id for item in alternative.appearances]


def test_timeline_serialization_round_trip():
    tracks = [profile("a"), profile("b")]
    timeline, _ = plan_performance_timeline(tracks, 100, SetIntent(), seed=1)
    restored = PerformanceTimeline.from_dict(timeline.to_dict())
    assert restored is not None
    assert restored.total_duration_sec == timeline.total_duration_sec
    assert len(restored.appearances) == len(timeline.appearances)


def test_request_and_style_make_performance_mode_unambiguous(tmp_path):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    quick, _ = service._intent("Make a quick mix", None, 3, False)
    assert quick.performance_mode == "segment"
    assert quick.performance_style == "quick_mix"
    classic, _ = service._intent("Make a smooth set", None, 15, False, "classic")
    assert classic.performance_mode == "classic"
    assert classic.performance_style == "classic"
    explicit, _ = service._intent("Make a set", None, 3, False, "club")
    assert explicit.performance_mode == "segment"
    assert explicit.performance_style == "club"
    automatic, _ = service._intent(None, "auto", 3, False)
    assert automatic.performance_mode == "classic"


def test_edited_appearance_order_is_rebuilt_and_revalidated():
    tracks = [profile("a"), profile("b"), profile("c")]
    timeline, _ = plan_performance_timeline(tracks, 120, SetIntent(), seed=3, performance_style="quick_mix")
    reversed_timeline = reorder_performance_timeline(
        timeline,
        [item.id for item in reversed(timeline.appearances)],
        {track.id: track.duration_sec for track in tracks},
    )
    assert reversed_timeline.appearances[0].id == timeline.appearances[-1].id
    assert not validate_performance_timeline(reversed_timeline, {track.id: track.duration_sec for track in tracks})
    shortened = reorder_performance_timeline(
        timeline,
        [item.id for item in timeline.appearances[:-1]],
        {track.id: track.duration_sec for track in tracks},
    )
    assert len(shortened.appearances) == len(timeline.appearances) - 1


def test_performance_renderer_writes_explicit_timeline(tmp_path):
    tracks = []
    for index in range(3):
        filepath = tmp_path / f"track-{index}.wav"
        audio = (0.1 * np.sin(np.linspace(0, 2000, 40 * 8000))).astype(np.float32)
        sf.write(filepath, audio, 8000)
        tracks.append(profile(str(index), duration=40.0))
        tracks[-1].metadata.filepath = str(filepath)
        tracks[-1].metadata.sample_rate = 8000
    timeline, _ = plan_performance_timeline(
        tracks, 60, SetIntent(target_duration_sec=60, performance_mode="segment"), seed=5,
        performance_style="quick_mix",
    )
    plan = __import__("djenius.core.models", fromlist=["SetPlan"]).SetPlan(
        tracks=tracks, total_duration_sec=timeline.total_duration_sec,
        target_duration_sec=60, performance_mode="segment",
        performance_style="quick_mix", performance_timeline=timeline,
    )
    result = render_performance_mix(plan, str(tmp_path / "mix.wav"), sample_rate=8000)
    assert result["duration_sec"] > 0
    assert result["provenance_audit"]["clean"]
    assert (tmp_path / "mix.wav").is_file()
