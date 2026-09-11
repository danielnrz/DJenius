from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from djenius.core.analysis_v2 import (
    V2_ANALYSIS_SCHEMA,
    build_beat_positions,
    build_cue_candidates,
    build_section_profiles,
    build_tempo_hypotheses,
    build_vocal_activity_curve,
    compute_groove_profile,
    compute_stem_activity_profiles,
    estimate_tempo_zones,
)
from djenius.core.models import TrackAnalysis


def regular_beats(bpm: float, seconds: float) -> list[float]:
    step = 60.0 / bpm
    return [round(i * step, 6) for i in range(int(seconds / step))]


def test_beat_positions_expose_bar_and_beat_indices():
    beats = regular_beats(120.0, 8.0)
    positions = build_beat_positions(beats, beats[::4])
    assert positions[0]["bar_index"] == 1
    assert positions[0]["beat_in_bar"] == 1
    assert positions[3]["beat_in_bar"] == 4
    assert positions[4]["bar_index"] == 2
    assert positions[4]["is_downbeat"] is True


def test_tempo_hypotheses_keep_half_double_relation():
    hypotheses = build_tempo_hypotheses(72.0, 0.8)
    by_relation = {item["relation"]: item for item in hypotheses}
    assert by_relation["primary"]["bpm"] == 72.0
    assert by_relation["double"]["bpm"] == 144.0
    assert by_relation["double"]["confidence"] < by_relation["primary"]["confidence"]


def test_regular_tempo_collapses_to_one_zone():
    zones = estimate_tempo_zones(regular_beats(120.0, 40.0), 120.0)
    assert len(zones) == 1
    assert abs(zones[0]["bpm"] - 120.0) < 0.5
    assert zones[0]["confidence"] > 0.9


def test_tempo_change_produces_multiple_zones():
    first = regular_beats(120.0, 20.0)
    offset = first[-1] + 0.5
    second = [offset + i * (60.0 / 100.0) for i in range(36)]
    zones = estimate_tempo_zones(first + second, 110.0, window_beats=6)
    assert len(zones) >= 2
    bpms = [zone["bpm"] for zone in zones]
    assert any(abs(value - 120.0) < 3.0 for value in bpms)
    assert any(abs(value - 100.0) < 3.0 for value in bpms)


def test_vocal_activity_curve_measures_partial_seconds():
    curve = build_vocal_activity_curve([(0.25, 1.5), (3.0, 4.0)], 5.0)
    assert len(curve) == 5
    assert curve[0] == 0.75
    assert curve[1] == 0.5
    assert curve[2] == 0.0
    assert curve[3] == 1.0


def test_groove_profile_from_click_track_is_finite():
    sr = 22050
    duration = 8.0
    y = np.zeros(int(sr * duration), dtype=np.float32)
    beats = regular_beats(120.0, duration)
    for t in beats:
        start = int(t * sr)
        y[start:start + 120] += np.hanning(120).astype(np.float32)
    profile, curve = compute_groove_profile(y, sr, beats)
    assert profile["confidence"] > 0.0
    assert 0.0 <= profile["syncopation_index"] <= 1.0
    assert 0.5 <= profile["swing_ratio"] <= 2.0
    assert curve
    assert all(np.isfinite(value) for value in curve)


def test_section_profiles_include_local_densities_and_scores():
    sections = [
        SimpleNamespace(start_sec=0.0, end_sec=8.0, label="intro"),
        SimpleNamespace(start_sec=8.0, end_sec=16.0, label="chorus"),
    ]
    profiles = build_section_profiles(
        sections,
        duration=16.0,
        bpm=120.0,
        energy_curve=[0.2] * 8 + [0.8] * 8,
        vocal_curve=[0.0] * 8 + [0.7] * 8,
        bass_curve=[0.3] * 8 + [0.8] * 8,
        rhythmic_density_curve=[0.2] * 8 + [0.9] * 8,
        phrase_confidences={8.0: 0.9},
    )
    assert len(profiles) == 2
    assert profiles[1]["energy_mean"] > profiles[0]["energy_mean"]
    assert profiles[1]["drum_density"] > profiles[0]["drum_density"]
    assert 0.0 <= profiles[1]["mix_in_score"] <= 1.0
    assert 0.0 <= profiles[1]["landing_strength"] <= 1.0


def test_cues_are_quantized_and_bounded():
    beats = regular_beats(120.0, 16.0)
    beat_positions = build_beat_positions(beats, beats[::4])
    sections = [
        {
            "start_sec": 0.0, "end_sec": 8.0, "label": "intro",
            "boundary_confidence": 0.8, "mix_in_score": 0.8, "mix_out_score": 0.3,
        },
        {
            "start_sec": 8.0, "end_sec": 16.0, "label": "drop",
            "boundary_confidence": 0.9, "mix_in_score": 0.7, "mix_out_score": 0.7,
        },
    ]
    cues = build_cue_candidates(
        beat_positions, sections,
        [{"time_sec": 4.0, "confidence": 0.7}],
        [0.2] * 8 + [0.8] * 8,
        [0.0] * 16,
        16.0,
    )
    assert cues
    assert all(0.0 <= cue["time_sec"] < 16.0 for cue in cues)
    assert all(cue["beat_in_bar"] in {1, 2, 3, 4} for cue in cues)
    assert any("drop_landing" in cue["use_cases"] for cue in cues)


def test_track_analysis_roundtrip_keeps_v2_event_lists():
    analysis = TrackAnalysis(
        analysis_schema_version=V2_ANALYSIS_SCHEMA,
        beat_positions=[{"time_sec": i * 0.5, "beat_index": i + 1} for i in range(500)],
        tempo_zones=[{"start_sec": 0.0, "end_sec": 10.0, "bpm": 120.0}],
        cue_candidates=[{"time_sec": 4.0, "bar_index": 3}],
    )
    data = analysis.to_dict()
    assert len(data["beat_positions"]) == 500
    restored = TrackAnalysis.from_dict(data)
    assert restored.analysis_schema_version == V2_ANALYSIS_SCHEMA
    assert len(restored.beat_positions) == 500
    assert restored.cue_candidates[0]["bar_index"] == 3


def test_stem_activity_profiles_are_bounded_and_informative():
    sr = 4000
    t = np.arange(sr * 4, dtype=np.float32) / sr
    active = (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    sparse = np.zeros_like(active)
    sparse[sr:2 * sr] = active[sr:2 * sr]
    profiles = compute_stem_activity_profiles({"vocals": sparse, "drums": active}, sr)
    assert set(profiles) == {"vocals", "drums"}
    assert 0.0 <= profiles["vocals"]["active_fraction"] <= 1.0
    assert profiles["drums"]["active_fraction"] > profiles["vocals"]["active_fraction"]
    assert profiles["drums"]["quality_method"] == "activity_only_no_bleed_claim"
    assert np.isfinite(profiles["drums"]["mean_rms_db"])
