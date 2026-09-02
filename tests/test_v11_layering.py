"""V11 safety tests for the narrow vocal-over-instrumental primitive."""

from pathlib import Path

import numpy as np
import soundfile as sf

from djenius.audio.performance_renderer import render_performance_mix
from djenius.audio.provenance import audit_performance_provenance
from djenius.core.layering import prepare_layered_events, score_layer_candidate
from djenius.core.models import (
    LayeredAppearance,
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


def _profile(tmp_path: Path, track_id: str, *, bpm: float = 120.0, vocal: float = 0.8, target_vocal: float = 0.05) -> TrackProfile:
    path = tmp_path / f"{track_id}.wav"
    sf.write(path, np.zeros((30 * 8000, 2), dtype=np.float32), 8000)
    analysis = TrackAnalysis(
        bpm=bpm,
        bpm_confidence=0.95,
        camelot="8A",
        key_confidence=0.95,
        bar_times=[float(i * 2) for i in range(16)],
        phrase_boundaries=[float(i * 8) for i in range(8)],
        analysis_confidence=0.95,
        vocal_regions=[(0.0, 20.0)] if vocal > 0.5 else [],
    )
    profile = TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=str(path), title=track_id, duration_sec=30),
        analysis=analysis,
    )
    profile._test_vocal_density = vocal
    return profile


def _segment(track_id: str, start: float, end: float, *, vocal: float, bars: int = 8) -> PerformanceSegment:
    return PerformanceSegment(
        id=f"{track_id}-{start}", track_id=track_id, source_start_sec=start,
        source_end_sec=end, bar_count=bars, vocal_density=vocal,
        energy=0.6, confidence=0.95, quality_score=0.9,
    )


def test_layer_gate_requires_stems_and_rejects_bad_pair(tmp_path: Path):
    source = _profile(tmp_path, "vocals")
    target = _profile(tmp_path, "backing", bpm=160, vocal=0.05)
    source_segment = _segment("vocals", 0, 16, vocal=0.8)
    target_segment = _segment("backing", 0, 16, vocal=0.05)
    score = score_layer_candidate(source, source_segment, target, target_segment)
    assert not score.accepted
    assert "stem" in score.rejection_reason or "tempo" in score.rejection_reason


def test_layer_gate_accepts_complete_compatible_stems(tmp_path: Path):
    source = _profile(tmp_path, "vocals")
    target = _profile(tmp_path, "backing", vocal=0.05)
    for profile in (source, target):
        profile.analysis.stems = {}
        for name in ("vocals", "drums", "bass", "other"):
            stem_path = tmp_path / f"{profile.id}-{name}.wav"
            sf.write(stem_path, np.zeros((30 * 8000, 2), dtype=np.float32), 8000)
            profile.analysis.stems[name] = str(stem_path)
    score = score_layer_candidate(source, _segment("vocals", 0, 16, vocal=0.8), target, _segment("backing", 0, 16, vocal=0.05))
    assert score.accepted
    assert score.score >= 0.72


def test_layering_preference_off_has_no_events(tmp_path: Path):
    source = _profile(tmp_path, "a")
    target = _profile(tmp_path, "b", vocal=0.05)
    timeline = PerformanceTimeline(performance_style="experimental")
    plan = SetPlan(tracks=[source, target], performance_timeline=timeline)
    from djenius.core.intent import SetIntent
    plan.intent_used = SetIntent(layering_preference="off")
    events, audit = prepare_layered_events(plan)
    assert events == []
    assert audit == []


def test_layered_provenance_declares_each_stem_and_rejects_hidden_sources():
    event = {
        "type": "layered", "output_start_sample": 10, "output_end_sample": 20,
        "sources": [
            {"track_id": "a", "stem": "vocals", "start_sample": 100, "end_sample": 110},
            {"track_id": "b", "stem": "drums", "start_sample": 50, "end_sample": 60},
            {"track_id": "b", "stem": "bass", "start_sample": 50, "end_sample": 60},
            {"track_id": "b", "stem": "other", "start_sample": 50, "end_sample": 60},
        ],
    }
    result = audit_performance_provenance([event], {"a": 200, "b": 200})
    assert result["clean"]
    event["sources"].pop()
    assert not audit_performance_provenance([event], {"a": 200, "b": 200})["clean"]


def test_layered_provenance_rejects_out_of_bounds_and_duplicate_regions():
    event = {
        "type": "layered", "output_start_sample": 10, "output_end_sample": 20,
        "sources": [
            {"track_id": "a", "stem": "vocals", "start_sample": 100, "end_sample": 110},
            {"track_id": "b", "stem": "drums", "start_sample": 50, "end_sample": 60},
            {"track_id": "b", "stem": "bass", "start_sample": 50, "end_sample": 60},
            {"track_id": "b", "stem": "other", "start_sample": 50, "end_sample": 60},
        ],
    }
    event["sources"][0]["end_sample"] = 210
    result = audit_performance_provenance([event, event], {"a": 200, "b": 200})
    kinds = {item["kind"] for item in result["violations"]}
    assert "layer_source_out_of_bounds" in kinds
    assert "duplicate_layer_source_region" in kinds


def test_layered_model_roundtrips_explicit_stem_contract():
    event = LayeredAppearance(
        id="layer", vocal_track_id="a", instrumental_track_id="b",
        vocal_source_start_sec=1, vocal_source_end_sec=9,
        instrumental_source_start_sec=2, instrumental_source_end_sec=10,
        output_start_sec=20, output_end_sec=28, instrumental_stems=("drums", "bass", "other"),
    )
    restored = LayeredAppearance.from_dict(event.to_dict())
    assert restored.instrumental_stems == ("drums", "bass", "other")
    assert restored.duration_sec == 8


def test_layered_renderer_is_stereo_and_uses_vocals_plus_target_instrumental(tmp_path: Path):
    sr = 8000
    tracks = []
    stems = {}
    for track_id in ("a", "b"):
        source_path = tmp_path / f"{track_id}.wav"
        sf.write(source_path, np.zeros((30 * sr, 2), dtype=np.float32), sr)
        analysis = TrackAnalysis(bpm=120, bpm_confidence=0.95, camelot="8A", analysis_confidence=0.95)
        tracks.append(TrackProfile(
            id=track_id,
            metadata=TrackMetadata(filepath=str(source_path), title=track_id, duration_sec=30),
            analysis=analysis,
        ))
        stems[track_id] = {
            "vocals": np.full((30 * sr, 2), 0.1 if track_id == "a" else 0.0, dtype=np.float32),
            "drums": np.full((30 * sr, 2), 0.0 if track_id == "a" else 0.2, dtype=np.float32),
            "bass": np.full((30 * sr, 2), 0.0 if track_id == "a" else 0.1, dtype=np.float32),
            "other": np.zeros((30 * sr, 2), dtype=np.float32),
        }
    first = PerformanceSegment(id="s1", track_id="a", source_start_sec=0, source_end_sec=20, bar_count=8)
    second = PerformanceSegment(id="s2", track_id="b", source_start_sec=0, source_end_sec=20, bar_count=8)
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=20),
            PerformanceAppearance(id="two", segment=second, output_start_sec=18, output_end_sec=38),
        ],
        transitions=[PerformanceTransition(
            source_appearance_id="one", target_appearance_id="two", transition_type=TransitionType.CROSSFADE,
            overlap_duration_sec=2, source_start_sec=18, source_end_sec=20,
            target_start_sec=0, target_end_sec=2,
        )],
        total_duration_sec=38,
        target_duration_sec=38,
        performance_style="experimental",
        layered_events=[LayeredAppearance(
            id="layer-one-two", vocal_track_id="a", instrumental_track_id="b",
            vocal_source_start_sec=4, vocal_source_end_sec=12,
            instrumental_source_start_sec=2, instrumental_source_end_sec=10,
            output_start_sec=20, output_end_sec=28, target_appearance_id="two",
            bar_count=4, confidence=0.9,
        ).to_dict()],
    )
    plan = SetPlan(tracks=tracks, performance_timeline=timeline)
    result = render_performance_mix(plan, str(tmp_path / "layer.wav"), sample_rate=sr, stem_audio=stems)
    audio, out_sr = sf.read(str(tmp_path / "layer.wav"), dtype="float32")
    assert out_sr == sr
    assert audio.ndim == 2 and audio.shape[1] == 2
    assert result["layered_events"] == 1
    assert result["provenance_audit"]["clean"]


def test_same_track_vocal_and_backing_layer_is_rejected():
    from djenius.audio.performance_renderer import _apply_layered_event
    output = np.zeros((100, 2), dtype=np.float32)
    event = {"vocal_track_id": "a", "instrumental_track_id": "a"}
    try:
        _apply_layered_event(output, event, [], {}, 10)
    except ValueError as exc:
        assert "different" in str(exc)
    else:
        raise AssertionError("same-track layer was accepted")


def test_layered_render_without_stems_keeps_normal_performance_safe(tmp_path: Path):
    sr = 8000
    source_path = tmp_path / "source.wav"
    target_path = tmp_path / "target.wav"
    sf.write(source_path, np.zeros((20 * sr, 2), dtype=np.float32), sr)
    sf.write(target_path, np.zeros((20 * sr, 2), dtype=np.float32), sr)
    tracks = [
        TrackProfile(id="a", metadata=TrackMetadata(filepath=str(source_path), title="a", duration_sec=20), analysis=TrackAnalysis()),
        TrackProfile(id="b", metadata=TrackMetadata(filepath=str(target_path), title="b", duration_sec=20), analysis=TrackAnalysis()),
    ]
    first = PerformanceSegment(id="s1", track_id="a", source_start_sec=0, source_end_sec=10)
    second = PerformanceSegment(id="s2", track_id="b", source_start_sec=0, source_end_sec=10)
    timeline = PerformanceTimeline(
        appearances=[
            PerformanceAppearance(id="one", segment=first, output_start_sec=0, output_end_sec=10),
            PerformanceAppearance(id="two", segment=second, output_start_sec=9, output_end_sec=19),
        ],
        transitions=[PerformanceTransition(
            source_appearance_id="one", target_appearance_id="two", transition_type=TransitionType.CROSSFADE,
            overlap_duration_sec=1, source_start_sec=9, source_end_sec=10, target_start_sec=0, target_end_sec=1,
        )],
        performance_style="experimental", total_duration_sec=19, target_duration_sec=19,
        layered_events=[LayeredAppearance(
            id="optional", vocal_track_id="a", instrumental_track_id="b",
            vocal_source_start_sec=1, vocal_source_end_sec=5,
            instrumental_source_start_sec=1, instrumental_source_end_sec=5,
            output_start_sec=10, output_end_sec=14, target_appearance_id="two",
        ).to_dict()],
    )
    result = render_performance_mix(SetPlan(tracks=tracks, performance_timeline=timeline), str(tmp_path / "safe.wav"), sample_rate=sr)
    assert result["layered_events"] == 0
    assert result["provenance_audit"]["clean"]


def test_no_layer_request_overrides_experimental_default(tmp_path: Path):
    from djenius.application import LocalAppService

    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    intent, _ = service._intent(
        "Make me an experimental mix but do not use mashups or layered vocals",
        None, 5, False,
    )
    assert intent.performance_style == "experimental"
    assert intent.layering_preference == "off"
