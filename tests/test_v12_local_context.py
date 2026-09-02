"""Synthetic tests for V12 exact-window musical context matching."""

from pathlib import Path

import numpy as np
import soundfile as sf

from djenius.core.local_context import (
    LOCAL_CONTEXT_VERSION,
    build_local_context,
    compute_local_context_curves,
    score_local_context,
)
from djenius.core.models import PerformanceSegment, TrackAnalysis, TrackMetadata, TrackProfile
from djenius.core.performance import score_segment_pair


def _profile(tmp_path: Path, track_id: str, *, local_rows=None, times=None, energy=None, low=None, vocals=None, camelot="8A") -> TrackProfile:
    path = tmp_path / f"{track_id}.wav"
    sf.write(path, np.zeros((20 * 8000, 2), dtype=np.float32), 8000)
    analysis = TrackAnalysis(
        bpm=120.0, bpm_confidence=0.95, camelot=camelot, key_confidence=0.95,
        analysis_confidence=0.95, bar_times=[float(i * 2) for i in range(11)],
        phrase_boundaries=[0.0, 8.0, 16.0], energy_curve=energy or [0.5] * 20,
        low_energy_curve=low or [0.3] * 20, vocal_regions=vocals or [],
        local_context_times=times or [2.0, 6.0, 10.0, 14.0, 18.0],
        local_chroma_curve=(local_rows or [[1.0] + [0.0] * 11] * 5),
        local_rhythm_curve=[[0.4, 0.2, 0.3]] * 5,
        local_spectral_curve=[[0.2, 0.5, 0.3, 0.4, 0.4]] * 5,
        local_context_version=LOCAL_CONTEXT_VERSION,
    )
    return TrackProfile(
        id=track_id, metadata=TrackMetadata(filepath=str(path), title=track_id, duration_sec=20), analysis=analysis,
    )


def _segment(track_id: str, start: float, end: float, vocal: float = 0.0) -> PerformanceSegment:
    return PerformanceSegment(
        id=f"{track_id}-{start}", track_id=track_id, source_start_sec=start,
        source_end_sec=end, bar_count=8, energy=0.5, vocal_density=vocal,
    )


def test_real_context_sampling_spans_whole_audio():
    sample_rate = 8000
    audio = np.sin(2 * np.pi * 220 * np.arange(40 * sample_rate) / sample_rate).astype(np.float32)
    times, chroma, rhythm, spectral = compute_local_context_curves(audio, sample_rate)
    assert times[0] >= 1.9
    assert times[-1] >= 38.0
    assert len(times) == len(chroma) == len(rhythm) == len(spectral)


def test_context_uses_exact_source_window_bounds(tmp_path: Path):
    track = _profile(tmp_path, "a")
    context = build_local_context(track, 6.25, 12.75)
    assert context.source_start_sec == 6.25
    assert context.source_end_sec == 12.75


def test_different_sections_of_same_track_get_different_harmonic_scores(tmp_path: Path):
    rows = [[1.0] + [0.0] * 11, [1.0] + [0.0] * 11, [0.0, 1.0] + [0.0] * 10, [0.0, 1.0] + [0.0] * 10, [0.0, 1.0] + [0.0] * 10]
    source = _profile(tmp_path, "source")
    target = _profile(tmp_path, "target", local_rows=rows)
    first, second = _segment("target", 0, 4), _segment("target", 12, 18)
    first_score, first_details = score_local_context(source, _segment("source", 0, 4), target, first)
    second_score, second_details = score_local_context(source, _segment("source", 0, 4), target, second)
    assert first_details["local_harmonic_score"] > second_details["local_harmonic_score"]
    assert first_score > second_score


def test_matching_harmony_scores_above_a_clash(tmp_path: Path):
    source = _profile(tmp_path, "source")
    matching = _profile(tmp_path, "matching")
    clash = _profile(tmp_path, "clash", local_rows=[[0.0, 1.0] + [0.0] * 10] * 5)
    source_segment = _segment("source", 0, 8)
    match_score, match = score_local_context(source, source_segment, matching, _segment("matching", 0, 8))
    clash_score, clash_data = score_local_context(source, source_segment, clash, _segment("clash", 0, 8))
    assert match["local_harmonic_score"] > clash_data["local_harmonic_score"]
    assert match_score > clash_score


def test_similar_rhythm_scores_above_incompatible_groove(tmp_path: Path):
    source = _profile(tmp_path, "source")
    similar = _profile(tmp_path, "similar")
    similar.analysis.local_rhythm_curve = [[0.4, 0.2, 0.3]] * 5
    different = _profile(tmp_path, "different")
    different.analysis.local_rhythm_curve = [[1.0, 4.0, 4.0]] * 5
    _, same = score_local_context(source, _segment("source", 0, 8), similar, _segment("similar", 0, 8))
    _, other = score_local_context(source, _segment("source", 0, 8), different, _segment("different", 0, 8))
    assert same["local_rhythm_score"] > other["local_rhythm_score"]


def test_energy_slope_and_bass_are_window_specific(tmp_path: Path):
    source = _profile(tmp_path, "source", energy=[0.2] * 20, low=[0.1] * 20)
    target = _profile(tmp_path, "target", energy=[0.8] * 10 + [0.2] * 10, low=[0.8] * 10 + [0.1] * 10)
    _, details = score_local_context(source, _segment("source", 0, 8), target, _segment("target", 0, 8))
    assert 0.0 <= details["local_energy_slope_score"] <= 1.0
    assert 0.0 <= details["local_bass_score"] <= 1.0
    assert details["target_window"]["source_start_sec"] == 0.0


def test_vocal_vocal_context_is_penalized(tmp_path: Path):
    source = _profile(tmp_path, "source", vocals=[(0.0, 20.0)])
    target = _profile(tmp_path, "target", vocals=[(0.0, 20.0)])
    _, details = score_local_context(source, _segment("source", 0, 8, 1.0), target, _segment("target", 0, 8, 1.0))
    assert details["local_vocal_score"] == 0.0


def test_style_changes_local_matching_emphasis(tmp_path: Path):
    source = _profile(tmp_path, "source")
    target = _profile(tmp_path, "target", local_rows=[[0.0, 1.0] + [0.0] * 10] * 5)
    segment_a, segment_b = _segment("source", 0, 8), _segment("target", 0, 8)
    smooth, _ = score_local_context(source, segment_a, target, segment_b, style="smooth")
    experimental, _ = score_local_context(source, segment_a, target, segment_b, style="experimental")
    assert 0.0 <= smooth <= 1.0
    assert 0.0 <= experimental <= 1.0
    assert smooth != experimental


def test_local_score_is_present_in_pair_and_transition_data(tmp_path: Path):
    source = _profile(tmp_path, "source")
    target = _profile(tmp_path, "target")
    pair = score_segment_pair(source, _segment("source", 0, 8), target, _segment("target", 0, 8), style="smooth")
    assert 0.0 <= pair.local_context_score <= 1.0
    assert pair.source_context_window["source_start_sec"] <= pair.source_context_window["source_end_sec"]
    assert pair.target_context_window["source_start_sec"] <= pair.target_context_window["source_end_sec"]


def test_local_window_cache_is_versioned_and_bounded(tmp_path: Path):
    track = _profile(tmp_path, "a")
    first = build_local_context(track, 0, 8)
    second = build_local_context(track, 0, 8)
    assert first.to_dict() == second.to_dict()
    assert any(f":{LOCAL_CONTEXT_VERSION}:0.0000:8.0000" in key for key in track.analysis.local_context_cache)
    for index in range(300):
        build_local_context(track, index * 0.01, index * 0.01 + 1.0)
    assert len(track.analysis.local_context_cache) <= 256


def test_global_key_remains_fallback_when_local_context_is_missing(tmp_path: Path):
    left = _profile(tmp_path, "left", camelot="8A")
    right = _profile(tmp_path, "right", camelot="8A")
    left.analysis.local_context_times = []
    right.analysis.local_context_times = []
    score, details = score_local_context(left, _segment("left", 0, 8), right, _segment("right", 0, 8))
    assert details["local_confidence"] < 1.0
    assert score > 0.0
