"""V14.3 phrase-continuous edit and loop seam tests."""

from types import SimpleNamespace

import numpy as np

from djenius.audio.creative_fx import apply_creative_operations, loop_roll
from djenius.audio.transitions import _phrase_cut
from djenius.core.phrase_edit import (
    assess_internal_edit,
    align_internal_edit_boundaries,
    internal_edit_overlap_sec,
)
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile


def _track(bars):
    return TrackProfile(
        id="track",
        metadata=TrackMetadata(filepath="track.wav", duration_sec=20),
        analysis=TrackAnalysis(bpm=120, bar_times=bars),
    )


def test_phrase_cut_keeps_outgoing_audio_until_the_actual_seam():
    source = np.ones(1000, dtype=np.float32)
    target = np.full(1000, 0.25, dtype=np.float32)
    result = _phrase_cut(source, target)
    assert result.shape == source.shape
    assert result[0] > 0.99
    assert result[-1] < 0.30
    assert np.all(np.diff(result[-256:]) <= 1e-6)


def test_internal_edit_uses_a_bounded_micro_seam():
    assert 0.005 <= internal_edit_overlap_sec() <= 0.080


def test_internal_edit_snaps_to_nearby_bar_boundaries():
    source = _track([0.0, 2.0, 4.0, 6.0])
    target = _track([0.0, 2.0, 4.0, 6.0])
    alignment = align_internal_edit_boundaries(source, target, 4.03, 2.04)
    assert alignment.aligned
    assert alignment.source_boundary_sec == 4.0
    assert alignment.target_boundary_sec == 2.0
    assert alignment.source_grid == "bar"


def test_internal_edit_quality_rejects_missing_grid_evidence():
    alignment = align_internal_edit_boundaries(_track([]), _track([]), 4.0, 2.0)
    pair = SimpleNamespace(
        phase_error_ms=0.0,
        local_context_score=0.9,
        technical_score=0.9,
        loudness_score=0.9,
        bass_score=0.9,
        vocal_score=0.9,
    )
    quality = assess_internal_edit(pair, alignment)
    assert quality.quality_class in {"MARGINAL", "REJECT"}


def test_loop_roll_treats_each_repeat_boundary_and_preserves_stereo():
    sr = 1000
    t = np.arange(6000, dtype=np.float32) / sr
    mono = 0.35 * np.sin(2.0 * np.pi * 1.7 * t)
    audio = np.column_stack([mono, mono * 0.8]).astype(np.float32)
    rolled = loop_roll(audio, sr, 60, beats=1, repeats=2)
    assert rolled.shape == audio.shape
    # The loop starts at 4 seconds and wraps at 5 seconds.  Both joins are
    # bounded by the treated seam instead of a full-scale discontinuity.
    assert float(np.max(np.abs(np.diff(rolled[3990:4020, 0])))) < 0.15
    assert float(np.max(np.abs(np.diff(rolled[4990:5020, 0])))) < 0.15


def test_loop_roll_accepts_musical_bar_length_operation():
    audio = np.zeros((8000, 2), dtype=np.float32)
    transformed, _ = apply_creative_operations(
        audio,
        np.zeros_like(audio),
        sample_rate=1000,
        source_bpm=60,
        operations=[{"type": "loop_roll", "bars": 1, "repeats": 2}],
    )
    assert transformed.shape == audio.shape
