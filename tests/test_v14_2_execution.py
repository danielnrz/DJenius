"""V14.2 blueprint-to-execution contract tests."""

import numpy as np
import soundfile as sf
import json

from djenius.audio.performance_renderer import render_performance_mix
from djenius.core.models import (
    PerformanceAppearance,
    PerformanceSegment,
    PerformanceTimeline,
    PerformanceTransition,
    SetPlan,
    TrackMetadata,
    TrackProfile,
    TrackAnalysis,
    TransitionType,
)
from djenius.core.performance import plan_performance_timeline
from djenius.core.performance_direction import (
    PerformanceDirective,
    build_performance_directive,
)
from djenius.core.techniques import MusicalSituation, rank_techniques

from tests.test_v9_performance import profile


def test_blueprint_roles_compile_into_executable_directive():
    directive = build_performance_directive(
        {"role": "BUILD", "state": "BUILD", "transition_role_out": "BUILD"},
        {"role": "PEAK", "state": "PEAK", "transition_role_in": "REVEAL", "decision": "SWITCH"},
        "experimental",
    )
    assert isinstance(directive, PerformanceDirective)
    assert directive.transition_role == "REVEAL"
    assert directive.require_payoff is True
    assert directive.musical_goal == "deliver a prepared payoff"


def test_payoff_directive_changes_existing_technique_ranking():
    situation = MusicalSituation(
        source_bpm=120, target_bpm=121, harmonic_fit=.92, rhythm_fit=.92,
        timbre_fit=.8, source_energy=.65, target_energy=.9,
        energy_direction="build", phrase_alignment=.9,
        downbeat_alignment=.9, local_context_score=.9,
    )
    ranked = rank_techniques(
        situation, TransitionType.BEATMATCHED_BLEND,
        style="experimental", intensity="moderate",
        transition_role="REVEAL",
        directive={
            "blueprint_decision": "SWITCH",
            "require_payoff": True,
            "allow_strong_technique": True,
        },
    )
    assert ranked[0].tier == "strong"
    assert any(item.name == "loop-roll drop" for item in ranked)


def test_timeline_transitions_retain_blueprint_directive():
    tracks = [profile("a", duration=180, energy=.55), profile("b", duration=180, energy=.85)]
    blueprint = {
        "acts": [
            {"id": "one", "role": "BUILD", "state": "BUILD", "selected_track_id": "a", "selected_segment_id": "", "transition_role_out": "BUILD", "decision": "SWITCH"},
            {"id": "two", "role": "PEAK", "state": "PEAK", "selected_track_id": "b", "selected_segment_id": "", "transition_role_in": "REVEAL", "decision": "SWITCH"},
        ]
    }
    timeline, _ = plan_performance_timeline(
        tracks, 120, performance_style="experimental", blueprint=blueprint,
    )
    transition = timeline.transitions[0]
    assert transition.execution_directive["transition_role"] == "REVEAL"
    assert transition.blueprint_source_role == "BUILD"
    assert transition.blueprint_target_role == "PEAK"
    assert transition.musical_goal == "deliver a prepared payoff"
    assert transition.transition_role == "REVEAL"
    assert timeline.transition_roles == [transition.transition_role]


def test_contiguous_stay_renders_without_a_conventional_transition(tmp_path):
    sample_rate = 8000
    t = np.arange(sample_rate * 4, dtype=np.float32) / sample_rate
    source_path = tmp_path / "source.wav"
    sf.write(source_path, np.column_stack([.15 * np.sin(2 * np.pi * 220 * t)] * 2), sample_rate)
    track = TrackProfile(
        id="a", metadata=TrackMetadata(filepath=str(source_path), title="a", duration_sec=4),
        analysis=TrackAnalysis(bpm=120, bpm_confidence=.9, analysis_confidence=.9),
    )
    first = PerformanceSegment(id="one", track_id="a", source_start_sec=0, source_end_sec=2, confidence=.9)
    second = PerformanceSegment(id="two", track_id="a", source_start_sec=2, source_end_sec=4, confidence=.9)
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=2),
            PerformanceAppearance(id="two", segment=second, output_start_sec=2, output_end_sec=4),
        ],
        transitions=[PerformanceTransition(
            source_appearance_id="one", target_appearance_id="two",
            transition_type=TransitionType.CROSSFADE, execution_mode="continuation",
            blueprint_decision="STAY", musical_goal="continue the current musical idea",
        )],
        total_duration_sec=4,
    )
    result = render_performance_mix(
        SetPlan(tracks=[track], performance_timeline=timeline),
        str(tmp_path / "stay.wav"), sample_rate=sample_rate,
    )
    assert result["provenance_audit"]["clean"]
    assert result["duration_sec"] == 4.0
    diagnostics = json.loads((tmp_path / "stay_diagnostics.json").read_text())
    assert any(item["type"] == "performance_continuation" for item in diagnostics["events"])


def test_section_edit_execution_mode_selects_phrase_cut_at_runtime(tmp_path):
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
    assert event["execution_operation"] == "phrase_cut_internal_section_edit"
    assert event["transition_type"] == "phrase_cut"
    assert event["planned_transition_type"] == "beatmatched_blend"


def test_section_edit_runtime_records_safety_fallback(tmp_path):
    sample_rate = 8000
    t = np.arange(sample_rate * 8, dtype=np.float32) / sample_rate
    source_path = tmp_path / "fallback.wav"
    sf.write(source_path, np.column_stack([.1 * np.sin(2 * np.pi * 220 * t)] * 2), sample_rate)
    track = TrackProfile(
        id="a", metadata=TrackMetadata(filepath=str(source_path), title="a", duration_sec=8),
        analysis=TrackAnalysis(bpm=120, bpm_confidence=.9, analysis_confidence=.9),
    )
    first = PerformanceSegment(id="one", track_id="a", source_start_sec=0, source_end_sec=3, confidence=.9)
    second = PerformanceSegment(id="two", track_id="a", source_start_sec=4, source_end_sec=7, confidence=.9)
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=3),
            PerformanceAppearance(id="two", segment=second, output_start_sec=2, output_end_sec=5, reprise=True),
        ],
        transitions=[PerformanceTransition(
            source_appearance_id="one", target_appearance_id="two",
            transition_type=TransitionType.BEATMATCHED_BLEND,
            overlap_duration_sec=1.0, source_start_sec=2.0, source_end_sec=3.0,
            target_start_sec=4.0, target_end_sec=5.0,
            technical_score=.4, local_context_score=.4, phase_error_ms=200.0,
            execution_mode="section_edit", blueprint_decision="VARIATE",
        )], total_duration_sec=5,
    )
    render_performance_mix(
        SetPlan(tracks=[track], performance_timeline=timeline),
        str(tmp_path / "fallback.wav"), sample_rate=sample_rate,
    )
    diagnostics = json.loads((tmp_path / "fallback_diagnostics.json").read_text())
    event = next(item for item in diagnostics["events"] if item["type"] == "performance_transition")
    assert event["execution_operation"] == "declared_transition_fallback"
    assert "safety gates" in event["execution_fallback_reason"]
