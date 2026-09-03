"""Focused V13 tests for adaptive technique direction and bounded FX."""

import numpy as np

from djenius.audio.creative_fx import apply_creative_operations, loop_roll, procedural_fx, tape_stop
from djenius.audio.provenance import audit_performance_provenance
from djenius.core.models import TransitionType
from djenius.core.nl_parser import parse_deterministic
from djenius.core.techniques import MusicalSituation, choose_technique, rank_techniques
from djenius.application import LocalAppService


def situation(**changes):
    values = dict(
        source_bpm=124.0,
        target_bpm=126.0,
        harmonic_fit=0.88,
        rhythm_fit=0.86,
        timbre_fit=0.78,
        source_energy=0.55,
        target_energy=0.72,
        source_vocal_state="light",
        target_vocal_state="light",
        source_bass=0.55,
        target_bass=0.58,
        phrase_alignment=0.92,
        downbeat_alignment=0.92,
        local_context_score=0.84,
        desired_style="club",
    )
    values.update(changes)
    return MusicalSituation(**values)


def test_ranker_considers_multiple_techniques_and_is_deterministic():
    ranked = rank_techniques(
        situation(), TransitionType.BEATMATCHED_BLEND,
        style="club", intensity="strong",
    )
    assert len(ranked) >= 3
    assert ranked[0].score >= ranked[-1].score
    assert ranked[0].to_dict() == rank_techniques(
        situation(), TransitionType.BEATMATCHED_BLEND,
        style="club", intensity="strong",
    )[0].to_dict()


def test_large_tempo_gap_gets_reset_candidate_instead_of_beatmatched_blend():
    ranked = rank_techniques(
        situation(source_bpm=100.0, target_bpm=140.0, source_vocal_state="light"),
        TransitionType.CROSSFADE,
        style="experimental", intensity="strong",
    )
    names = {item.name for item in ranked}
    assert "tape-stop reset" in names
    assert choose_technique(
        situation(source_bpm=100.0, target_bpm=140.0, source_vocal_state="light"),
        TransitionType.CROSSFADE, style="experimental", intensity="strong",
    ).name == "tape-stop reset"


def test_smooth_style_does_not_select_aggressive_effects():
    selected = choose_technique(
        situation(source_bpm=110.0, target_bpm=128.0),
        TransitionType.CROSSFADE, style="smooth", intensity="strong",
    )
    assert selected.name not in {"tape-stop reset", "loop-roll drop", "drop switch"}


def test_recent_technique_history_can_choose_another_valid_recipe():
    first = choose_technique(
        situation(), TransitionType.BEATMATCHED_BLEND,
        style="club", intensity="strong",
    )
    second = choose_technique(
        situation(), TransitionType.BEATMATCHED_BLEND,
        style="club", intensity="strong", recent_techniques=(first.name,) * 3,
    )
    assert second.name != first.name or second.score < first.score


def test_no_fx_request_keeps_valid_clean_transition():
    intent = parse_deterministic("Make a simple mix without special effects")
    selected = choose_technique(
        situation(), TransitionType.BEATMATCHED_BLEND,
        style="experimental", allow_creative_fx=intent.allow_creative_fx,
        intensity=intent.technique_intensity,
    )
    assert not selected.operations
    assert selected.transition_type == TransitionType.BEATMATCHED_BLEND


def test_remix_language_selects_segment_performance_in_app_service(tmp_path):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    intent, _ = service._intent(
        "Make an energetic remix-style performance", None, 5, False,
    )
    assert intent.performance_mode == "segment"
    assert intent.performance_style == "experimental"


def test_bounded_creative_operations_preserve_stereo_shape_and_are_deterministic():
    sr = 8000
    t = np.arange(sr, dtype=np.float32) / sr
    audio = np.column_stack((0.2 * np.sin(2 * np.pi * 220 * t), 0.18 * np.sin(2 * np.pi * 221 * t)))
    stopped = tape_stop(audio, 1.0)
    rolled = loop_roll(audio, sr, 120, beats=1, repeats=3)
    assert stopped.shape == audio.shape
    assert rolled.shape == audio.shape
    assert np.isfinite(stopped).all() and np.isfinite(rolled).all()
    fx_a = procedural_fx(len(audio), sr, "riser", seed=13)
    fx_b = procedural_fx(len(audio), sr, "riser", seed=13)
    assert fx_a.shape == audio.shape
    assert np.array_equal(fx_a, fx_b)
    transformed, generated = apply_creative_operations(
        audio, np.zeros_like(audio), sample_rate=sr, source_bpm=120,
        operations=[{"type": "loop_roll", "beats": 1, "repeats": 2},
                    {"type": "generated_fx", "effect": "impact", "seed": 17}],
    )
    assert transformed.shape == audio.shape
    assert generated[0]["source_type"] == "generated_fx"
    mono, _ = apply_creative_operations(
        audio[:, 0], np.zeros(len(audio), dtype=np.float32), sample_rate=sr,
        source_bpm=120, operations=[{"type": "generated_fx", "effect": "riser"}],
    )
    assert mono.shape == (len(audio),)


def test_loop_roll_is_explicitly_auditable_not_a_hidden_replay():
    event = {
        "type": "transition",
        "transition_type": "crossfade",
        "source_track_id": "a", "target_track_id": "b",
        "source_start_sample": 100, "source_end_sample": 200,
        "target_start_sample": 300, "target_end_sample": 400,
        "output_start_sample": 0, "output_end_sample": 100,
        "technique_operations": [{"type": "loop_roll", "beats": 1, "repeats": 2}],
    }
    from djenius.audio.provenance import audit_source_provenance
    audit = audit_source_provenance([event], {"a": 1000, "b": 1000})
    assert audit["clean"]
    assert audit["intentional_loops"]
    assert audit["intentional_loops"][0]["kind"] == "intentional_loop_roll"


def test_generated_fx_provenance_stays_inside_transition_output():
    event = {
        "type": "performance_transition", "source_track_id": "a", "target_track_id": "b",
        "source_start_sample": 10, "source_end_sample": 20,
        "target_start_sample": 30, "target_end_sample": 40,
        "output_start_sample": 100, "output_end_sample": 200,
        "generated_fx_provenance": [{
            "source_type": "generated_fx", "output_start_sample": 100,
            "output_end_sample": 200,
        }],
    }
    assert audit_performance_provenance([event], {"a": 100, "b": 100})["clean"]
    event["generated_fx_provenance"][0]["output_end_sample"] = 201
    assert not audit_performance_provenance([event], {"a": 100, "b": 100})["clean"]
