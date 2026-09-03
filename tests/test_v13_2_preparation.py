"""V13.2 rendered preparation/landing regression tests."""

import json

import numpy as np
import soundfile as sf

from djenius.audio.performance_renderer import render_performance_mix
from djenius.audio.provenance import audit_performance_provenance
from djenius.audio.transition_preparation import (
    apply_bass_automation,
    apply_filter_automation,
    render_preparation,
)
from djenius.core.intent import SetIntent
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
from djenius.core.transition_phases import build_preparation_operations


def _track(track_id: str, path: str, duration: float = 20.0) -> TrackProfile:
    analysis = TrackAnalysis(
        bpm=120.0,
        bpm_confidence=0.95,
        bar_times=[float(i * 2) for i in range(10)],
        phrase_boundaries=[float(i * 8) for i in range(3)],
        energy_curve=[0.6] * int(duration),
        low_energy_curve=[0.7] * int(duration),
        analysis_confidence=0.95,
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=path, title=track_id, duration_sec=duration),
        analysis=analysis,
    )


def test_bass_automation_changes_only_a_bounded_source_window():
    sr = 8000
    t = np.arange(sr * 2) / sr
    source = np.column_stack([np.sin(2 * np.pi * 80 * t), np.sin(2 * np.pi * 80 * t)])
    changed = apply_bass_automation(source, sr, 0.0, -12.0)
    assert changed.shape == source.shape
    assert np.sqrt(np.mean(changed[-sr:, 0] ** 2)) < np.sqrt(np.mean(source[-sr:, 0] ** 2))
    assert np.max(np.abs(changed)) < 1.1


def test_filter_automation_is_continuous_and_stereo():
    sr = 8000
    source = np.ones((sr, 2), dtype=np.float32)
    changed = apply_filter_automation(source, sr, "highpass", 20, 180)
    assert changed.shape == source.shape
    assert not np.allclose(changed, source)
    assert np.allclose(changed[:, 0], changed[:, 1])


def test_drop_switch_gets_actual_preparation_operations():
    operations = build_preparation_operations("drop switch", "REVEAL", "experimental")
    assert [item["type"] for item in operations] == ["bass_automation", "generated_fx"]
    rendered, audit = render_preparation(np.ones((4000, 2), dtype=np.float32), 8000, operations)
    assert not np.allclose(rendered, 1.0)
    assert audit and audit[0]["source_type"] == "generated_fx"


def test_target_percussion_tease_is_declared_and_does_not_duplicate_transition_source():
    event = {
        "type": "performance_transition",
        "source_track_id": "a", "target_track_id": "b",
        "source_start_sample": 8000, "source_end_sample": 12000,
        "target_start_sample": 4000, "target_end_sample": 8000,
        "output_start_sample": 0, "output_end_sample": 4000,
        "preparation_start_sample": 0, "preparation_end_sample": 2000,
        "preparation_rendered": True,
        "preparation_source_start_sample": 6000,
        "preparation_source_end_sample": 8000,
        "preparation_target_provenance": {
            "track_id": "b", "stem": "drums", "source_start_sample": 0,
            "source_end_sample": 2000, "output_start_sample": 0, "output_end_sample": 2000,
        },
        "generated_fx_provenance": [], "preparation_generated_fx_provenance": [],
        "technique_operations": [],
    }
    audit = audit_performance_provenance([event], {"a": 20000, "b": 20000})
    assert audit["clean"]


def test_rendered_preparation_precedes_boundary_and_landing_is_reported(tmp_path):
    sr = 8000
    paths = []
    tracks = []
    for track_id, frequency in (("a", 80), ("b", 140)):
        path = tmp_path / f"{track_id}.wav"
        t = np.arange(sr * 20) / sr
        sf.write(path, (0.2 * np.sin(2 * np.pi * frequency * t)).astype(np.float32), sr)
        paths.append(str(path))
        tracks.append(_track(track_id, str(path)))
    first = PerformanceSegment(id="a-segment", track_id="a", source_start_sec=0, source_end_sec=12, energy=0.6, confidence=0.9)
    second = PerformanceSegment(id="b-segment", track_id="b", source_start_sec=0, source_end_sec=12, energy=0.7, confidence=0.9)
    appearances = [
        PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=12),
        PerformanceAppearance(id="two", segment=second, output_start_sec=10, output_end_sec=22),
    ]
    transition = PerformanceTransition(
        source_appearance_id="one", target_appearance_id="two", transition_type=TransitionType.CROSSFADE,
        overlap_duration_sec=2, source_start_sec=10, source_end_sec=12,
        target_start_sec=0, target_end_sec=2, preparation_duration_sec=2,
        landing_duration_sec=2, preparation_operations=[{"type": "bass_automation", "start_db": 0, "end_db": -12}],
    )
    timeline = PerformanceTimeline(appearances=appearances, transitions=[transition], total_duration_sec=22, target_duration_sec=22)
    result = render_performance_mix(SetPlan(tracks=tracks, performance_timeline=timeline), str(tmp_path / "out.wav"), sample_rate=sr)
    diagnostics = json.loads((tmp_path / "out_diagnostics.json").read_text())
    item = next(event for event in diagnostics["events"] if event["type"] == "performance_transition")
    assert item["preparation_rendered"] is True
    assert item["preparation_end_sec"] == item["boundary_sec"]
    assert item["landing_end_sec"] > item["landing_start_sec"]
    assert result["provenance_audit"]["clean"]


def test_stem_percussion_tease_advances_target_source_once(tmp_path):
    sr = 8000
    tracks = []
    for track_id, frequency in (("a", 80), ("b", 140)):
        path = tmp_path / f"{track_id}.wav"
        t = np.arange(sr * 20) / sr
        sf.write(path, (0.2 * np.sin(2 * np.pi * frequency * t)).astype(np.float32), sr)
        tracks.append(_track(track_id, str(path)))
    first = PerformanceSegment(id="a", track_id="a", source_start_sec=0, source_end_sec=12, confidence=0.9)
    second = PerformanceSegment(id="b", track_id="b", source_start_sec=0, source_end_sec=12, confidence=0.9)
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=12),
            PerformanceAppearance(id="two", segment=second, output_start_sec=10, output_end_sec=22),
        ],
        transitions=[PerformanceTransition(
            source_appearance_id="one", target_appearance_id="two", transition_type=TransitionType.CROSSFADE,
            overlap_duration_sec=2, source_start_sec=10, source_end_sec=12,
            target_start_sec=0, target_end_sec=2, preparation_duration_sec=2,
            landing_duration_sec=2,
            preparation_operations=[{"type": "target_percussion_tease"}],
        )],
        total_duration_sec=22,
    )
    stems = {"b": {name: np.ones((sr * 20, 2), dtype=np.float32) * 0.01 for name in ("drums", "bass", "other")}}
    result = render_performance_mix(SetPlan(tracks=tracks, performance_timeline=timeline), str(tmp_path / "tease.wav"), sample_rate=sr, stem_audio=stems)
    diagnostics = json.loads((tmp_path / "tease_diagnostics.json").read_text())
    event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    assert event["target_preparation_consumed_duration_sec"] == 2.0
    assert event["preparation_target_provenance"]["stem"] == "drums"
    assert event["target_start_sec"] > 0.0
    assert result["provenance_audit"]["clean"]
