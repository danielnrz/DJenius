"""Tests for rendered full-context transition auditing."""

from __future__ import annotations

import json

import numpy as np
import soundfile as sf

from djenius.audio.quality_audit import (
    audit_rendered_mix,
    longest_near_silent_interval,
    render_transition_previews,
)


def _fixture_files(tmp_path):
    sample_rate = 8000
    time = np.arange(sample_rate * 8) / sample_rate
    audio = np.column_stack([
        0.2 * np.sin(2 * np.pi * 220 * time),
        0.2 * np.sin(2 * np.pi * 220 * time),
    ]).astype(np.float32)
    mix_path = tmp_path / "mix.wav"
    diagnostics_path = tmp_path / "diagnostics.json"
    sf.write(mix_path, audio, sample_rate)
    diagnostics_path.write_text(json.dumps({
        "events": [{
            "type": "transition",
            "source_track_title": "A",
            "target_track_title": "B",
            "transition_type": "crossfade",
            "output_start_sample": sample_rate * 3,
            "output_end_sample": sample_rate * 5,
            "quality_score": {"overall_score": 0.8},
        }],
        "provenance_audit": {"clean": True, "violations": []},
    }))
    return mix_path, diagnostics_path


def test_full_context_audit_separates_approach_transition_and_landing(tmp_path):
    mix_path, diagnostics_path = _fixture_files(tmp_path)
    report = audit_rendered_mix(str(mix_path), str(diagnostics_path))

    assert report["transition_count"] == 1
    transition = report["transitions"][0]
    assert transition["approach"]["one_second_curve"]
    assert transition["transition"]["one_second_curve"]
    assert transition["landing"]["one_second_curve"]
    assert "transition_trough_db" in transition
    assert "transition_floor_score" in transition
    assert transition["ranking_score"] > 0.0
    assert report["provenance_audit"]["clean"] is True


def test_preview_contains_context_and_complete_transition(tmp_path):
    mix_path, diagnostics_path = _fixture_files(tmp_path)
    paths = render_transition_previews(
        str(mix_path), str(diagnostics_path), str(tmp_path / "previews"), "chill",
        context_sec=1.0,
    )

    preview, sample_rate = sf.read(paths[0])
    assert sample_rate == 8000
    assert len(preview) == sample_rate * 4


def test_longest_near_silent_interval_detects_consecutive_frames():
    sample_rate = 1000
    audio = np.concatenate([
        np.ones(sample_rate),
        np.zeros(sample_rate * 3),
        np.ones(sample_rate),
    ]).astype(np.float32)

    assert longest_near_silent_interval(audio, sample_rate) == 3.0
