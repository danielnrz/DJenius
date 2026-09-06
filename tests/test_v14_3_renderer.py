import json
import numpy as np
import soundfile as sf
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
from djenius.audio.performance_renderer import render_performance_mix
from djenius.audio.transitions import phrase_cut_seam_samples
from djenius.core.performance import plan_performance_timeline, validate_performance_timeline

def _generated_variate_track(path, *, vocal_regions=None):
    sample_rate = 8000
    samples = np.arange(sample_rate * 180, dtype=np.float32)
    signal = (samples / samples.max())[:, None]
    sf.write(path, np.repeat(signal, 2, axis=1), sample_rate)
    analysis = TrackAnalysis(
        bpm=120, bpm_confidence=.95, analysis_confidence=.95,
        bar_times=[float(index * 2) for index in range(90)],
        phrase_boundaries=[float(index * 8) for index in range(23)],
        vocal_regions=vocal_regions or [],
    )
    return TrackProfile(
        id="a", metadata=TrackMetadata(filepath=str(path), title="a", duration_sec=180),
        analysis=analysis,
    )


def _variate_blueprint():
    return {"acts": [
        {"id": "one", "role": "BUILD", "state": "BUILD", "selected_track_id": "a", "decision": "VARIATE"},
        {"id": "two", "role": "PEAK", "state": "PEAK", "selected_track_id": "a", "decision": "VARIATE", "stay_on_track": True},
    ]}


def test_generated_variate_planner_to_renderer_uses_resolved_boundaries(tmp_path):
    track = _generated_variate_track(tmp_path / "generated.wav")
    timeline, _ = plan_performance_timeline([track], 60, performance_style="experimental", blueprint=_variate_blueprint())
    transition = timeline.transitions[0]
    previous, current = timeline.appearances[:2]
    assert transition.blueprint_decision == "VARIATE"
    assert transition.execution_mode == "section_edit"
    assert transition.source_edit_boundary_sec >= 0.0
    assert transition.target_edit_boundary_sec >= 0.0
    result = render_performance_mix(SetPlan(tracks=[track], performance_timeline=timeline), str(tmp_path / "generated_render.wav"), sample_rate=8000)
    assert result["provenance_audit"]["clean"]
    diagnostics = json.loads((tmp_path / "generated_render_diagnostics.json").read_text())
    event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    assert event["execution_mode"] == "section_edit"
    assert event["source_edit_boundary_sec"] == transition.source_edit_boundary_sec
    assert event["target_edit_boundary_sec"] == transition.target_edit_boundary_sec
    assert event["source_start_sample"] == round(previous.segment.source_start_sec * 8000)
    assert event["target_start_sample"] == round(current.segment.source_start_sec * 8000)


def test_generated_variate_without_safe_edit_collapses_cleanly(tmp_path):
    track = _generated_variate_track(tmp_path / "unsafe.wav", vocal_regions=[(0.0, 180.0)])
    timeline, _ = plan_performance_timeline([track], 60, performance_style="experimental", blueprint=_variate_blueprint())
    assert len(timeline.appearances) == 1
    assert not timeline.transitions
    assert len(timeline.appearances) == 1


def test_section_edit_target_boundary_offset(tmp_path):
    sample_rate = 8000
    t = np.arange(sample_rate * 8, dtype=np.float32) / sample_rate
    source_path = tmp_path / "section.wav"
    signal = np.column_stack([
        0.18 * np.sin(2 * np.pi * 220 * t),
        0.12 * np.sin(2 * np.pi * 330 * t),
    ])
    sf.write(source_path, signal, sample_rate)
    track = TrackProfile(
        id="a", metadata=TrackMetadata(filepath=str(source_path), title="a", duration_sec=8),
        analysis=TrackAnalysis(bpm=120, bpm_confidence=.9, analysis_confidence=.9),
    )
    first = PerformanceSegment(id="one", track_id="a", source_start_sec=0, source_end_sec=3, confidence=.9)
    second = PerformanceSegment(id="two", track_id="a", source_start_sec=4, source_end_sec=7, confidence=.9)
    transition = PerformanceTransition(
        source_appearance_id="one", target_appearance_id="two",
        transition_type=TransitionType.BEATMATCHED_BLEND,
        overlap_duration_sec=1.0, source_start_sec=2.0, source_end_sec=3.0,
        target_start_sec=4.0, target_end_sec=5.0,
        target_edit_boundary_sec=4.5,  # Use a boundary inside the target appearance
        technical_score=.8, local_context_score=.8, phase_error_ms=0.0,
        execution_mode="section_edit", blueprint_decision="VARIATE",
        technique_name="section edit", technique_operations=[{"type": "section_edit"}],
    )
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=3),
            PerformanceAppearance(id="two", segment=second, output_start_sec=2, output_end_sec=5, reprise=True),
        ],
        transitions=[transition], total_duration_sec=5,
    )
    result = render_performance_mix(
        SetPlan(tracks=[track], performance_timeline=timeline),
        str(tmp_path / "section.wav"), sample_rate=sample_rate,
    )
    assert result["provenance_audit"]["clean"]
    diagnostics = json.loads((tmp_path / "section_diagnostics.json").read_text())
    event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    assert event["execution_mode"] == "section_edit"
    
    # target_start_sample should be the appearance's source_start_sec (4.0), not the edit boundary
    assert event["target_start_sample"] == int(round(second.source_start_sec * sample_rate))


def test_section_edit_source_boundary_offset(tmp_path):
    sample_rate = 8000
    t = np.arange(sample_rate * 8, dtype=np.float32) / sample_rate
    source_path = tmp_path / "section_src.wav"
    signal = np.column_stack([
        0.18 * np.sin(2 * np.pi * 220 * t),
        0.12 * np.sin(2 * np.pi * 330 * t),
    ])
    sf.write(source_path, signal, sample_rate)
    track = TrackProfile(
        id="a", metadata=TrackMetadata(filepath=str(source_path), title="a", duration_sec=8),
        analysis=TrackAnalysis(bpm=120, bpm_confidence=.9, analysis_confidence=.9),
    )
    first = PerformanceSegment(id="one", track_id="a", source_start_sec=0, source_end_sec=3, confidence=.9)
    second = PerformanceSegment(id="two", track_id="a", source_start_sec=4, source_end_sec=7, confidence=.9)
    transition = PerformanceTransition(
        source_appearance_id="one", target_appearance_id="two",
        transition_type=TransitionType.BEATMATCHED_BLEND,
        overlap_duration_sec=1.0, source_start_sec=2.0, source_end_sec=3.0,
        source_edit_boundary_sec=2.5,  # Non-standard boundary
        target_start_sec=4.0, target_end_sec=5.0,
        target_edit_boundary_sec=4.5,
        technical_score=.8, local_context_score=.8, phase_error_ms=0.0,
        execution_mode="section_edit", blueprint_decision="VARIATE",
        technique_name="section edit", technique_operations=[{"type": "section_edit"}],
    )
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=3),
            PerformanceAppearance(id="two", segment=second, output_start_sec=2, output_end_sec=5, reprise=True),
        ],
        transitions=[transition], total_duration_sec=5,
    )
    result = render_performance_mix(
        SetPlan(tracks=[track], performance_timeline=timeline),
        str(tmp_path / "section_src.wav"), sample_rate=sample_rate,
    )
    diagnostics = json.loads((tmp_path / "section_src_diagnostics.json").read_text())
    event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    assert event["source_start_sample"] == int(round(first.source_start_sec * sample_rate))
