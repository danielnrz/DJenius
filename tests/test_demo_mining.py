"""Tests for conservative shadow-only DJ demonstration evidence."""

from pathlib import Path

import numpy as np
import pytest

from djenius.research import demo_mining
from djenius.research.demo_mining import (
    alignment_intervals,
    cached_waveform_repeats,
    evidence_near_region,
    repeat_evidence,
    signal_patterns,
    waveform_repeat_evidence,
)


def test_repetition_is_never_declared_a_dj_loop() -> None:
    rng = np.random.default_rng(3)
    motif = rng.normal(size=(4, 24)).astype(np.float32)
    motif /= np.linalg.norm(motif, axis=1, keepdims=True)
    chroma = np.vstack([rng.normal(size=(20, 24)), motif, motif, rng.normal(size=(20, 24))])
    result = repeat_evidence(chroma, 26)
    assert result["status"] == "STRONG_REPEAT_LIKE_AUDIO_NOT_DJ_INTENT"
    assert result["period_sec"] == 4


def test_exact_waveform_repeat_is_still_not_declared_dj_intent() -> None:
    rng = np.random.default_rng(42)
    noise = rng.normal(0, .2, 2000 * 30).astype(np.float32)
    motif = rng.normal(0, .2, 2000 * 4).astype(np.float32)
    wave = np.concatenate([noise, motif, motif, noise])
    result = waveform_repeat_evidence(wave, 36)
    assert result["status"] == "EXACT_LIKE_AUDIO_REPEAT_NOT_PROOF_OF_DJ_LOOP"
    assert result["normalized_waveform_correlation"] > .99


def test_repeat_cache_contains_only_scalar_evidence(tmp_path, monkeypatch) -> None:
    rng = np.random.default_rng(9)
    wave = rng.normal(0, .1, 2000 * 50).astype(np.float32)
    monkeypatch.setattr(demo_mining, "decode_reference_wave_for_ephemeral_checks", lambda path: wave)
    candidates = [{"center_sec": 30}]
    first = cached_waveform_repeats(tmp_path / "private_ref.mp3", "source-hash", candidates, tmp_path / "derived")

    def forbidden_decode(path):
        raise AssertionError("valid scalar cache must avoid decoding raw audio")

    monkeypatch.setattr(demo_mining, "decode_reference_wave_for_ephemeral_checks", forbidden_decode)
    second = cached_waveform_repeats(tmp_path / "private_ref.mp3", "source-hash", candidates, tmp_path / "derived")
    assert first == second
    cache_files = list((tmp_path / "derived").glob("*.json"))
    assert len(cache_files) == 1
    assert len(cache_files[0].read_text()) < 1000


def test_signal_patterns_are_unattributed() -> None:
    candidate = {"axis_evidence": {
        "log_rms": {"delta": 3},
        "low_fraction": {"delta": .2},
        "transient_activity": {"delta": .05},
        "high_fraction": {"delta": -.04},
        "centroid_hz": {"delta": -240},
    }}
    patterns = signal_patterns(candidate)
    assert "ENERGY_AND_LOW_END_ARRIVAL_SIGNAL" in patterns
    assert all(value.endswith("_SIGNAL") for value in patterns)


def test_original_turnover_remains_candidate_not_proven_handoff() -> None:
    alignment = {"rows": [
        {"source_index": 0, "matches": [{
            "reference_index": 0, "status": "HIGH_CONFIDENCE_AUDIO_ALIGNMENT",
            "verified_hits": [{"reference_start_sec": 5, "source_start_sec": 20, "tempo_ratio": 1.0, "mean_frame_cosine": .9}]},
        ]},
        {"source_index": 1, "matches": [{
            "reference_index": 0, "status": "HIGH_CONFIDENCE_AUDIO_ALIGNMENT",
            "verified_hits": [{"reference_start_sec": 32, "source_start_sec": 10, "tempo_ratio": 1.0, "mean_frame_cosine": .9}]},
        ]},
    ]}
    intervals = alignment_intervals(alignment)
    result = evidence_near_region(intervals[0], 30)
    assert result["distinct_original_change_candidate"] is True
    assert "does not prove DJ handoff" in result["meaning"]


def test_mining_cli_rejects_private_output_inside_repository(monkeypatch) -> None:
    in_repo = Path(__file__).resolve().parents[1] / "should_not_write_private_research"
    monkeypatch.setattr("sys.argv", ["demo_mining", "--inventory", "unused.json",
                                    "--regions", "unused.json", "--alignment", "unused.json",
                                    "--output-dir", str(in_repo)])
    with pytest.raises(ValueError, match="outside repository"):
        demo_mining.main()
