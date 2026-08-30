"""Regression tests derived from the real V5.1 repeated-ending failures."""

from __future__ import annotations

import json
from unittest import mock

import numpy as np
import pytest

from djenius.audio.provenance import audit_source_provenance
from djenius.audio.renderer import render_mix
from djenius.audio.transitions import _echo_out, _loop_blend, apply_transition
from djenius.core.intent import make_intent
from djenius.core.models import EnergyProfile, SetPlan, TransitionType
from djenius.core.planner import plan_set
from tests.test_renderer_v51 import _make_track, _make_transition


SR = 1000


def _time_coded_audio(seconds: float, identity: float) -> np.ndarray:
    """Create a non-periodic signal whose values encode source position."""
    count = round(seconds * SR)
    positions = np.arange(count, dtype=np.float32)
    return (
        identity
        + positions / max(count, 1) * 0.1
        + 0.01 * np.sin(positions * positions * 0.00017)
    ).astype(np.float32)


def _mock_loader(audio_by_path: dict[str, np.ndarray]):
    def load(path: str, target_sr: int):
        return audio_by_path[path], target_sr
    return load


def test_production_like_three_track_provenance_is_forward(tmp_path):
    tracks = [
        _make_track("a", "A", "/a.wav", 4.0, bpm=120.0),
        _make_track("b", "B", "/b.wav", 5.0, bpm=120.0),
        _make_track("c", "C", "/c.wav", 4.0, bpm=120.0),
    ]
    transitions = [
        _make_transition("a", "b", 3.0, 0.5, 0.5),
        _make_transition("b", "c", 4.0, 0.25, 0.5),
    ]
    plan = SetPlan(tracks=tracks, transitions=transitions, energy_profile=EnergyProfile.STEADY)
    audio = {
        "/a.wav": _time_coded_audio(4.0, 0.1),
        "/b.wav": _time_coded_audio(5.0, 0.3),
        "/c.wav": _time_coded_audio(4.0, 0.5),
    }

    with mock.patch("djenius.audio.renderer._load_audio", side_effect=_mock_loader(audio)):
        result = render_mix(plan, str(tmp_path / "abc.wav"), sample_rate=SR)

    assert result["provenance_audit"]["clean"] is True
    with open(result["timeline_diagnostics_path"]) as handle:
        events = json.load(handle)["events"]
    b_events = [
        event for event in events
        if event.get("track_id") == "b"
        or event.get("source_track_id") == "b"
        or event.get("target_track_id") == "b"
    ]
    b_intervals = []
    for event in b_events:
        if event["type"] == "track":
            b_intervals.append((event["source_start_sample"], event["source_end_sample"]))
        elif event["target_track_id"] == "b":
            b_intervals.append((event["target_start_sample"], event["target_end_sample"]))
        else:
            b_intervals.append((event["source_start_sample"], event["source_end_sample"]))
    assert b_intervals == [(500, 1000), (1000, 4000), (4000, 4500)]


def test_old_full_body_then_transition_replay_is_detected():
    old_buggy_events = [
        {
            "type": "track", "track_id": "b",
            "source_start_sample": 1000, "source_end_sample": 10000,
            "output_start_sample": 0, "output_end_sample": 9000,
            "planned_source_exit_sample": 7000,
        },
        {
            "type": "transition", "transition_type": "crossfade",
            "source_track_id": "b", "source_start_sample": 7000,
            "source_end_sample": 8000, "target_track_id": "c",
            "target_start_sample": 0, "target_end_sample": 1000,
            "output_start_sample": 9000, "output_end_sample": 10000,
        },
    ]
    audit = audit_source_provenance(old_buggy_events, {"b": 10000, "c": 10000})
    kinds = {violation["kind"] for violation in audit["violations"]}
    assert "body_past_planned_exit" in kinds
    assert "unexpected_backwards_source_jump" in kinds
    assert "duplicate_source_interval" in kinds


def test_transition_failure_fallback_keeps_target_cursor_forward(tmp_path):
    tracks = [
        _make_track("a", "A", "/a.wav", 4.0),
        _make_track("b", "B", "/b.wav", 5.0),
        _make_track("c", "C", "/c.wav", 4.0),
    ]
    transitions = [
        _make_transition("a", "b", 3.0, 0.5, 0.5, TransitionType.FILTER_SWEEP),
        _make_transition("b", "c", 4.0, 0.25, 0.5),
    ]
    plan = SetPlan(tracks=tracks, transitions=transitions)
    audio = {path: _time_coded_audio(duration, identity) for path, duration, identity in (
        ("/a.wav", 4.0, 0.1), ("/b.wav", 5.0, 0.3), ("/c.wav", 4.0, 0.5),
    )}
    real_apply = apply_transition

    def fail_filter_only(**kwargs):
        if kwargs["transition_type"] == "filter_sweep":
            raise RuntimeError("forced DSP failure")
        return real_apply(**kwargs)

    with (
        mock.patch("djenius.audio.renderer._load_audio", side_effect=_mock_loader(audio)),
        mock.patch("djenius.audio.renderer.apply_transition", side_effect=fail_filter_only),
    ):
        result = render_mix(plan, str(tmp_path / "fallback.wav"), sample_rate=SR)

    assert result["provenance_audit"]["clean"] is True
    with open(result["timeline_diagnostics_path"]) as handle:
        events = json.load(handle)["events"]
    b_body = next(event for event in events if event["type"] == "track" and event["track_id"] == "b")
    assert b_body["source_start_sample"] == 1000
    assert b_body["source_end_sample"] == 4000


def test_loop_blend_is_explicit_and_contained(tmp_path):
    render_sr = 4000
    tracks = [
        _make_track("a", "A", "/a.wav", 4.0, bpm=120.0),
        _make_track("b", "B", "/b.wav", 4.0, bpm=120.0),
    ]
    transition = _make_transition(
        "a", "b", 3.0, 0.0, 0.75, TransitionType.LOOP_BLEND,
    )
    plan = SetPlan(tracks=tracks, transitions=[transition])
    audio = {
        "/a.wav": np.linspace(0.1, 0.2, render_sr * 4, dtype=np.float32),
        "/b.wav": np.linspace(0.4, 0.5, render_sr * 4, dtype=np.float32),
    }

    with mock.patch("djenius.audio.renderer._load_audio", side_effect=_mock_loader(audio)):
        result = render_mix(plan, str(tmp_path / "loop.wav"), sample_rate=render_sr)

    audit = result["provenance_audit"]
    assert audit["clean"] is True
    assert len(audit["intentional_loops"]) == 1
    loop = audit["intentional_loops"][0]
    assert loop["source_end_sample"] - loop["source_start_sample"] == 2000
    assert loop["output_end_sample"] - loop["output_start_sample"] == 3000


def test_loop_blend_repeats_one_beat_not_old_half_overlap():
    sr = 4000
    overlap_samples = sr * 8
    beat_samples = sr // 2
    positions = np.arange(overlap_samples, dtype=np.float32)
    source = positions / overlap_samples + 0.1 * np.sin(positions * 0.017)
    target = np.zeros_like(source)

    result = _loop_blend(source, target, sr=sr, source_bpm=120.0)

    from djenius.utils.audio_math import equal_power_crossfade

    fade_out, _ = equal_power_crossfade(overlap_samples)
    recovered_source = result[:beat_samples * 3] / fade_out[:beat_samples * 3]
    assert np.allclose(
        recovered_source[beat_samples:beat_samples * 2],
        source[:beat_samples],
        atol=1e-6,
    )
    assert not np.allclose(
        recovered_source[beat_samples:beat_samples * 2],
        source[beat_samples:beat_samples * 2],
        atol=1e-3,
    )


def test_echo_taps_decay_instead_of_replaying_at_equal_strength():
    source = np.zeros(2500, dtype=np.float32)
    source[0] = 1.0
    target = np.zeros_like(source)
    result = _echo_out(source, target, SR, source_bpm=120.0)
    tap_levels = [abs(float(result[index])) for index in (0, 500, 1000, 1500)]
    assert tap_levels[0] > tap_levels[1] > tap_levels[2] > tap_levels[3] > 0
    assert tap_levels[1] < tap_levels[0] * 0.5


def test_renderer_beatmatch_uses_native_bpm_and_source_mapping(tmp_path):
    source = _make_track("a", "A", "/a.wav", 4.0, bpm=120.0)
    target = _make_track("b", "B", "/b.wav", 4.0, bpm=100.0)
    transition = _make_transition(
        "a", "b", 3.0, 0.25, 0.5, TransitionType.BEATMATCHED_BLEND,
    )
    transition.requires_stretch = True
    transition.target_bpm = 120.0
    plan = SetPlan(tracks=[source, target], transitions=[transition])
    audio = {"/a.wav": _time_coded_audio(4.0, 0.1), "/b.wav": _time_coded_audio(4.0, 0.4)}
    captured = []

    def fake_apply(**kwargs):
        captured.append(kwargs)
        return np.zeros(kwargs["overlap_samples"], dtype=np.float32)

    with (
        mock.patch("djenius.audio.renderer._load_audio", side_effect=_mock_loader(audio)),
        mock.patch("djenius.audio.renderer.apply_transition", side_effect=fake_apply),
    ):
        result = render_mix(plan, str(tmp_path / "beatmatch.wav"), sample_rate=SR)

    assert captured[0]["source_bpm"] == 120.0
    assert captured[0]["target_bpm"] == 100.0
    with open(result["timeline_diagnostics_path"]) as handle:
        transition_event = next(
            event for event in json.load(handle)["events"] if event["type"] == "transition"
        )
    assert transition_event["target_start_sample"] == 250
    assert transition_event["target_end_sample"] == 850
    final_body = next(
        event for event in json.load(open(result["timeline_diagnostics_path"]))["events"]
        if event["type"] == "track" and event["track_id"] == "b"
    )
    assert final_body["source_start_sample"] == 850


def test_beatmatched_transition_handles_real_energy_profiles():
    source = _time_coded_audio(3.0, 0.1)
    target = _time_coded_audio(3.0, 0.4)
    result = apply_transition(
        source, target, SR, "beatmatched_blend", 500, 1000, 500,
        source_bpm=120.0, target_bpm=100.0,
        source_low_energy=0.7, target_low_energy=0.8,
        source_mid_energy=0.6, target_mid_energy=0.6,
    )
    assert len(result) == 500
    assert np.all(np.isfinite(result))


def test_stem_transition_receives_exact_source_offsets():
    source = _time_coded_audio(2.0, 0.1)
    target = _time_coded_audio(2.0, 0.4)
    stems = {
        name: _time_coded_audio(2.0, identity)
        for name, identity in (("vocals", 0.1), ("drums", 0.2), ("bass", 0.3), ("other", 0.4))
    }
    captured = {}

    def fake_mashup(source_region, target_region, sr, **kwargs):
        captured.update(kwargs)
        return np.zeros(len(source_region), dtype=np.float32)

    with mock.patch("djenius.audio.transitions._mashup", side_effect=fake_mashup):
        result = apply_transition(
            source, target, SR, "mashup", 400, 700, 300,
            source_stems=stems, target_stems=stems,
        )
    assert len(result) == 400
    assert captured["source_exit_sample"] == 700
    assert captured["target_entry_sample"] == 300


def test_planner_rejects_track_too_short_for_transition():
    tracks = [
        _make_track("a", "A", "/a.wav", 5.0, bpm=120.0),
        _make_track("b", "B", "/b.wav", 5.0, bpm=120.0),
    ]
    with pytest.raises(ValueError, match="No forward transition window"):
        plan_set(tracks, max_tracks=2)


def test_intent_transition_restrictions_are_enforced():
    tracks = [
        _make_track(f"track-{index}", f"Track {index}", f"/{index}.wav", 120.0, bpm=125.0)
        for index in range(4)
    ]
    intent = make_intent("energetic", bpm_min=None, bpm_max=None, energy_min=None, energy_max=None)
    plan = plan_set(tracks, max_tracks=4, intent=intent)
    allowed = set(intent.allowed_transition_types())
    assert plan.transitions
    assert all(transition.transition_type in allowed for transition in plan.transitions)
