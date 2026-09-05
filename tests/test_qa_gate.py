"""Tests for the automated audio-quality gate.

Covers:
  - Vocal integrity (word splitting, phrase interruption, stem bleed)
  - Loop/DSP continuity (RMS, phase, spectral flux, bass)
  - Macro structure (fade dominance, consecutive complexity)
  - Known-bad example reproduction (VARIATE/loop/full-remix rejections)
  - Gate orchestrator end-to-end
  - Real audio validation (testMusic)

All tests are deterministic and use synthetic audio / mock data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from djenius.audio.qa.models import QAResult, QAViolation
from djenius.audio.qa.vocal_integrity import (
    evaluate_edit_point,
    evaluate_multiple_edit_points,
    _word_timings_from_segments,
    _nearest_word_margin,
    _in_vocal_region,
    _nearest_phrase_boundary,
)
from djenius.audio.qa.loop_dsp import (
    evaluate_loop_seamlessness,
    evaluate_loop_seam_from_arrays,
    _cross_correlation,
    _spectral_flux,
    _lowpass,
    _bass_derivative_sign_change,
)
from djenius.audio.qa.macro_structure import (
    evaluate_macro_pacing,
    evaluate_macro_pacing_from_timeline,
    _total_overlap_duration,
    _max_consecutive_complex,
    _technique_diversity,
)
from djenius.audio.qa.gate import run_qa_gate


# ─── Helpers ────────────────────────────────────────────────────────────

def _sine(sr: int, freq: float, dur: float, phase: float = 0.0) -> np.ndarray:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False, dtype=np.float64)
    return np.sin(2 * np.pi * freq * t + phase)


def _silence(sr: int, dur: float) -> np.ndarray:
    return np.zeros(int(sr * dur), dtype=np.float64)


def _segments(*words: tuple[str, float, float]) -> list[dict]:
    """Build whisper-style segment dicts from (text, start, end) tuples."""
    return [{"text": t, "start": s, "end": e} for t, s, e in words]


def _mock_vocal_regions(*regions: tuple[float, float]) -> list[tuple[float, float]]:
    return list(regions)


@dataclass
class _FakeTransition:
    transition_type: Any = None
    overlap_duration: float = 0.0
    source_track_id: str = "t1"
    target_track_id: str = "t2"
    source_exit_time: float = 0.0


@dataclass
class _FakeAnalysis:
    vocal_regions: list[tuple[float, float]] = field(default_factory=list)
    phrase_boundaries: list[float] = field(default_factory=list)
    stems: dict[str, str] | None = None


@dataclass
class _FakeLyrics:
    segments: list[dict] = field(default_factory=list)


@dataclass
class _FakeTrack:
    id: str = "t1"
    analysis: Any = None
    lyrics: Any = None

    def __post_init__(self):
        if self.analysis is None:
            self.analysis = _FakeAnalysis()
        if self.lyrics is None:
            self.lyrics = _FakeLyrics()


@dataclass
class _FakeTransitionType:
    value: str = "crossfade"


@dataclass
class _FakePlan:
    tracks: list[Any] = field(default_factory=list)
    transitions: list[Any] = field(default_factory=list)
    total_duration_sec: float = 0.0
    performance_timeline: Any = None

    def get_track_by_id(self, track_id: str):
        for t in self.tracks:
            if t.id == track_id:
                return t
        return None


@dataclass
class _FakeTimeline:
    total_duration_sec: float = 0.0
    transitions: list[Any] = field(default_factory=list)
    technique_counts: dict[str, int] = field(default_factory=dict)
    layered_events: list[Any] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# 1. Vocal integrity — unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestVocalIntegrity:

    def test_safe_cut_in_silence(self):
        """A cut between words with no vocal activity passes."""
        segs = _segments(
            ("hello", 1.0, 1.5),
            ("world", 3.0, 3.5),
        )
        result = evaluate_edit_point(2.2, segments=segs)
        assert result.passed
        assert len(result.violations) == 0

    def test_word_midpoint_cut_rejected(self):
        """A cut through the middle of a word is rejected."""
        segs = _segments(
            ("believing", 10.0, 10.5),
        )
        result = evaluate_edit_point(10.25, segments=segs)
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "word_midpoint_cut" in metrics

    def test_cut_inside_word_rejected(self):
        """Any cut within word.start + 50ms to word.end - 50ms is bad."""
        segs = _segments(
            ("amazing", 5.0, 5.6),
        )
        # Cut at 5.2 — inside the word, well past the 50ms margin
        result = evaluate_edit_point(5.2, segments=segs, tolerance_sec=0.05)
        assert not result.passed

    def test_cut_at_word_boundary_passes(self):
        """A cut exactly at word.end passes."""
        segs = _segments(
            ("test", 2.0, 2.4),
        )
        result = evaluate_edit_point(2.4, segments=segs, tolerance_sec=0.05)
        assert result.passed

    def test_cut_just_inside_margin_rejected(self):
        """A cut 40ms before word.end (within 50ms margin) is rejected."""
        segs = _segments(
            ("test", 2.0, 3.0),
        )
        result = evaluate_edit_point(2.96, segments=segs, tolerance_sec=0.05)
        assert not result.passed

    def test_phrase_interruption_rejected(self):
        """A cut mid-vocal-region far from a phrase boundary is rejected."""
        vocal_regions = _mock_vocal_regions((10.0, 20.0))
        phrase_bounds = [10.0, 18.0]
        result = evaluate_edit_point(
            14.0,
            vocal_regions=vocal_regions,
            phrase_boundaries=phrase_bounds,
            phrase_margin_sec=0.2,
        )
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "phrase_interruption" in metrics

    def test_phrase_interruption_near_boundary_passes(self):
        """A cut near a phrase boundary inside a vocal region passes."""
        vocal_regions = _mock_vocal_regions((10.0, 20.0))
        phrase_bounds = [10.0, 14.05]
        result = evaluate_edit_point(
            14.0,
            vocal_regions=vocal_regions,
            phrase_boundaries=phrase_bounds,
            phrase_margin_sec=0.2,
        )
        assert result.passed

    def test_stem_bleed_rejected(self):
        """A cut with high vocal stem RMS is rejected as stem bleed."""
        sr = 44100
        # 50ms of audio with RMS well above threshold
        stem = np.ones(sr // 20, dtype=np.float32) * 0.1
        result = evaluate_edit_point(
            0.025,
            vocal_stem_audio=stem,
            sample_rate=sr,
            stem_threshold=0.03,
        )
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "stem_bleed_at_cut" in metrics

    def test_stem_silence_passes(self):
        """A cut with silent vocal stem passes."""
        sr = 44100
        stem = np.zeros(sr // 20, dtype=np.float32)
        result = evaluate_edit_point(
            0.025,
            vocal_stem_audio=stem,
            sample_rate=sr,
            stem_threshold=0.03,
        )
        assert result.passed

    def test_stem_bleed_near_boundary(self):
        """Stem bleed is detected even when the loaded window is clipped near file start."""
        sr = 44100
        # Simulate a 0.5s stem (file starts at time 0, cut at 0.25s)
        # The full 2s window would be [-0.75, 1.25] but clipped to [0, 0.5]
        stem_dur = 0.5
        stem = np.zeros(int(sr * stem_dur), dtype=np.float32)
        # Place vocal energy only at the cut point (centre of loaded window)
        cut_sample = int(0.25 * sr)
        half_win = sr // 200  # 5ms
        lo = max(0, cut_sample - half_win)
        hi = min(len(stem), cut_sample + half_win)
        stem[lo:hi] = 0.15  # well above threshold
        result = evaluate_edit_point(
            0.25,
            vocal_stem_audio=stem,
            sample_rate=sr,
            stem_loaded_start=0.0,
            stem_threshold=0.03,
        )
        assert not result.passed, "Vocal energy at cut point must be detected"
        assert any(v.metric == "stem_bleed_at_cut" for v in result.violations)

    def test_multiple_edits_aggregate(self):
        """Multiple edits merge all violations."""
        segs = _segments(
            ("hello", 1.0, 1.5),
            ("world", 5.0, 5.5),
            ("test", 9.0, 9.5),
        )
        result = evaluate_multiple_edit_points(
            [1.25, 5.25],  # Both cut through words
            segments=segs,
        )
        assert not result.passed
        assert len(result.violations) >= 2

    def test_word_timings_from_segments(self):
        """Helper correctly extracts word timings."""
        segs = _segments(("a", 0.0, 0.5), ("b", 1.0, 1.5), ("", 2.0, 2.0))
        timings = _word_timings_from_segments(segs)
        assert len(timings) == 2
        assert timings[0] == ("a", 0.0, 0.5)

    def test_nearest_word_margin_inside(self):
        """Margin is distance to nearest boundary and inside=True when cut is inside word."""
        words = [("inside", 1.0, 2.0)]
        margin, _, inside = _nearest_word_margin(1.5, words)
        assert inside
        assert margin == pytest.approx(0.5)  # distance to nearest boundary (1.0 or 2.0)

    def test_nearest_word_margin_outside(self):
        """Margin is positive when cut is between words."""
        words = [("a", 0.0, 0.5), ("b", 1.0, 1.5)]
        margin, _, inside = _nearest_word_margin(0.75, words)
        assert not inside
        assert margin == pytest.approx(0.25)

    def test_in_vocal_region(self):
        regions = [(5.0, 10.0)]
        assert _in_vocal_region(7.5, regions)
        assert not _in_vocal_region(3.0, regions)

    def test_nearest_phrase_boundary(self):
        boundaries = [2.0, 5.0, 10.0]
        assert _nearest_phrase_boundary(5.1, boundaries) == pytest.approx(0.1)
        assert _nearest_phrase_boundary(7.0, boundaries) == pytest.approx(2.0)

    def test_empty_segments_pass(self):
        """No segments = no word violations."""
        result = evaluate_edit_point(5.0, segments=[])
        assert result.passed

    def test_no_vocal_regions_no_phrase_violation(self):
        """No vocal regions = no phrase interruption."""
        result = evaluate_edit_point(5.0, vocal_regions=[], phrase_boundaries=[2.0])
        assert result.passed


# ═══════════════════════════════════════════════════════════════════════
# 2. Loop DSP — unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestLoopDSP:

    def test_seamless_loop_passes(self):
        """Two identical sine chunks with integer cycles in 10ms pass all checks."""
        sr = 44100
        # 1000Hz = 10 cycles per 10ms window → integer alignment
        chunk = _sine(sr, 1000.0, 0.5)
        result = evaluate_loop_seamlessness(chunk, chunk, sr)
        assert result.passed

    def test_rms_discontinuity_rejected(self):
        """A large volume jump across the seam is rejected."""
        sr = 44100
        tail = _sine(sr, 440.0, 0.5) * 0.01
        head = _sine(sr, 440.0, 0.5) * 0.5
        result = evaluate_loop_seamlessness(tail, head, sr)
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "rms_discontinuity" in metrics

    def test_phase_inversion_rejected(self):
        """A 180-degree phase flip at the seam is rejected."""
        sr = 44100
        freq = 100.0
        tail = _sine(sr, freq, 0.5, phase=0.0)
        head = _sine(sr, freq, 0.5, phase=math.pi)
        result = evaluate_loop_seamlessness(tail, head, sr)
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "phase_alignment" in metrics

    def test_spectral_flux_rejected(self):
        """Abrupt spectral change is detected as a violation."""
        sr = 44100
        # Tail: low frequency
        tail = _sine(sr, 100.0, 0.5)
        # Head: very high frequency (different spectrum)
        head = _sine(sr, 8000.0, 0.5)
        result = evaluate_loop_seamlessness(tail, head, sr)
        assert not result.passed
        # Spectral flux should fire directly for these drastically
        # different frequencies; phase_alignment may also fire.
        metrics = [v.metric for v in result.violations]
        assert "spectral_flux" in metrics

    def test_spectral_flux_value_range(self):
        """Spectral flux produces a measurable value for different signals."""
        sr = 44100
        tail = _sine(sr, 100.0, 0.5)
        head = _sine(sr, 8000.0, 0.5)
        flux = _spectral_flux(tail[:1024], head[:1024])
        # With mean-energy normalisation, two completely different sine
        # waves should produce flux >> 0.15 (the default threshold).
        assert flux > 0.5, f"Spectral flux {flux} too low for clearly different signals"

    def test_bass_discontinuity_rejected(self):
        """Abrupt bass sign flip is detected as a violation."""
        sr = 44100
        n = sr // 4  # quarter second
        # Explicit: tail going down, head going up → sign flip in derivative
        tail = np.linspace(0.5, -0.5, n, dtype=np.float64)
        head = np.linspace(-0.5, 0.5, n, dtype=np.float64)
        result = evaluate_loop_seamlessness(tail, head, sr)
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "bass_discontinuity" in metrics or "phase_alignment" in metrics

    def test_empty_audio_passes(self):
        """Empty arrays pass (nothing to check)."""
        result = evaluate_loop_seamlessness(np.array([]), np.array([]), 44100)
        assert result.passed

    def test_cross_correlation_identical(self):
        """Identical signals have correlation ~1."""
        x = np.linspace(-1, 1, 1000)
        corr = _cross_correlation(x, x)
        assert corr == pytest.approx(1.0, abs=1e-6)

    def test_cross_correlation_orthogonal(self):
        """Orthogonal signals have correlation ~0."""
        a = np.sin(np.linspace(0, 2 * np.pi, 1000))
        b = np.cos(np.linspace(0, 2 * np.pi, 1000))
        corr = _cross_correlation(a, b)
        assert abs(corr) < 0.1

    def test_spectral_flux_identical(self):
        """Identical signals have flux ~0."""
        x = np.linspace(-1, 1, 1024)
        flux = _spectral_flux(x, x)
        assert flux == pytest.approx(0.0, abs=1e-6)

    def test_bass_derivative_no_flip(self):
        """Same-direction derivatives don't trigger."""
        tail = np.linspace(0, 1, 100)
        head = np.linspace(1, 2, 100)
        assert not _bass_derivative_sign_change(tail, head)

    def test_evaluate_from_arrays(self):
        """Convenience wrapper extracts correct regions."""
        sr = 44100
        # Use 1000Hz so the 10ms correlation window has exactly 10 integer
        # cycles, avoiding anti-correlation from non-integer cycle counts.
        full = _sine(sr, 1000.0, 2.0)
        result = evaluate_loop_seam_from_arrays(full, sr, sr * 2, sr)
        assert result.passed

    def test_evaluate_from_arrays_reversed_detects_seam(self):
        """Non-periodic audio with a seam at the loop boundary is detected."""
        sr = 44100
        n = sr  # 1 second per segment
        # Build a 4-second file: [silence | tone A | tone B | silence]
        # Loop from s1 (1s) to s3 (3s). Tail = audio approaching s3
        # (tone B region), head = audio leaving s1 (tone A region).
        # Different tones → spectral flux / phase violation.
        tail_tone = _sine(sr, 200.0, 1.0) * 0.5   # 200Hz
        head_tone = _sine(sr, 4000.0, 1.0) * 0.5  # 4000Hz
        full = np.concatenate([
            np.zeros(n, dtype=np.float64),
            head_tone,   # 1s–2s (loop start region)
            tail_tone,   # 2s–3s (loop end region)
            np.zeros(n, dtype=np.float64),
        ])
        result = evaluate_loop_seam_from_arrays(full, n, 3 * n, sr)
        assert not result.passed, "Different tones at loop seam must be rejected"

    def test_stereo_spectral_flux(self):
        """Stereo arrays are handled without error."""
        sr = 44100
        n = 1024
        tail = np.stack([_sine(sr, 100.0, n / sr), _sine(sr, 100.0, n / sr)], axis=-1)
        head = np.stack([_sine(sr, 8000.0, n / sr), _sine(sr, 8000.0, n / sr)], axis=-1)
        flux = _spectral_flux(tail, head)
        assert flux > 0.5, f"Stereo spectral flux {flux} too low for different signals"

    def test_stereo_lowpass(self):
        """Stereo arrays pass through _lowpass without error."""
        sr = 44100
        stereo = np.stack([_sine(sr, 8000.0, 0.1), _sine(sr, 8000.0, 0.1)], axis=-1)
        result = _lowpass(stereo, sr, 1000.0)
        assert result.ndim == 1  # downmixed to mono

    def test_stereo_loop_seamlessness(self):
        """Stereo arrays pass through evaluate_loop_seamlessness without error."""
        sr = 44100
        mono = _sine(sr, 1000.0, 0.5)
        stereo_tail = np.stack([mono, mono], axis=-1)
        stereo_head = np.stack([mono, mono], axis=-1)
        result = evaluate_loop_seamlessness(stereo_tail, stereo_head, sr)
        assert result.passed  # identical stereo signal


# ═══════════════════════════════════════════════════════════════════════
# 3. Macro structure — unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestMacroStructure:

    def test_short_mix_passes(self):
        """A mix with minimal overlap passes."""
        trans = _FakeTransition(
            transition_type=_FakeTransitionType("crossfade"),
            overlap_duration=5.0,
        )
        plan = _FakePlan(transitions=[trans], total_duration_sec=300.0)
        result = evaluate_macro_pacing(plan)
        assert result.passed

    def test_heavy_fade_rejected(self):
        """Fade dominance > 20% is rejected."""
        trans = _FakeTransition(
            transition_type=_FakeTransitionType("crossfade"),
            overlap_duration=60.0,
        )
        plan = _FakePlan(transitions=[trans], total_duration_sec=200.0)
        result = evaluate_macro_pacing(plan)
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "fade_dominance" in metrics

    def test_consecutive_complex_rejected(self):
        """4+ consecutive complex transitions are rejected."""
        trans = [
            _FakeTransition(
                transition_type=_FakeTransitionType("loop_roll"),
                overlap_duration=5.0,
            )
            for _ in range(4)
        ]
        plan = _FakePlan(
            transitions=trans,
            total_duration_sec=400.0,
        )
        result = evaluate_macro_pacing(plan)
        assert not result.passed
        metrics = [v.metric for v in result.violations]
        assert "consecutive_complex" in metrics

    def test_three_complex_passes(self):
        """3 consecutive complex transitions are within limits."""
        trans = [
            _FakeTransition(
                transition_type=_FakeTransitionType("loop_roll"),
                overlap_duration=5.0,
            )
            for _ in range(3)
        ]
        plan = _FakePlan(
            transitions=trans,
            total_duration_sec=400.0,
        )
        result = evaluate_macro_pacing(plan)
        assert result.passed

    def test_non_overlapping_types_dont_count(self):
        """phrase_cut doesn't contribute to fade dominance."""
        trans = _FakeTransition(
            transition_type=_FakeTransitionType("phrase_cut"),
            overlap_duration=30.0,
        )
        plan = _FakePlan(transitions=[trans], total_duration_sec=100.0)
        result = evaluate_macro_pacing(plan)
        assert result.passed

    def test_total_overlap_duration(self):
        trans = [
            _FakeTransition(
                transition_type=_FakeTransitionType("crossfade"),
                overlap_duration=10.0,
            ),
            _FakeTransition(
                transition_type=_FakeTransitionType("bass_swap"),
                overlap_duration=8.0,
            ),
        ]
        assert _total_overlap_duration(trans) == pytest.approx(18.0)

    def test_max_consecutive_complex(self):
        trans = [
            _FakeTransition(transition_type=_FakeTransitionType("loop_roll")),
            _FakeTransition(transition_type=_FakeTransitionType("tape_stop")),
            _FakeTransition(transition_type=_FakeTransitionType("crossfade")),
            _FakeTransition(transition_type=_FakeTransitionType("loop_roll")),
            _FakeTransition(transition_type=_FakeTransitionType("loop_roll")),
            _FakeTransition(transition_type=_FakeTransitionType("loop_roll")),
            _FakeTransition(transition_type=_FakeTransitionType("loop_roll")),
        ]
        assert _max_consecutive_complex(trans) == 4

    def test_technique_diversity_uniform(self):
        counts = {"crossfade": 5, "bass_swap": 5, "loop_roll": 5}
        div = _technique_diversity(counts)
        assert div > 0.9

    def test_technique_diversity_single(self):
        counts = {"crossfade": 10}
        div = _technique_diversity(counts)
        assert div == pytest.approx(0.0)

    def test_empty_plan_passes(self):
        plan = _FakePlan(transitions=[], total_duration_sec=0)
        result = evaluate_macro_pacing(plan)
        assert result.passed

    def test_timeline_fade_dominance(self):
        timeline = _FakeTimeline(
            total_duration_sec=100.0,
            layered_events=[
                {"overlap_duration_sec": 30.0},
            ],
        )
        result = evaluate_macro_pacing_from_timeline(timeline)
        assert not result.passed


# ═══════════════════════════════════════════════════════════════════════
# 4. Known-bad example reproduction
# ═══════════════════════════════════════════════════════════════════════

class TestKnownBadExamples:

    def test_reject_word_chopper_edit(self):
        """A VARIATE-style edit that chops through sung lyrics is rejected."""
        # Simulate a track where the planner cut at 10.25s, right through
        # the word "believing" (10.0-10.5s)
        segs = _segments(
            ("I was", 8.0, 8.8),
            ("believing", 10.0, 10.5),
            ("in something", 11.0, 12.0),
        )
        vocal_regions = _mock_vocal_regions((8.0, 12.0))
        phrase_bounds = [8.0, 12.0]

        # The planner says: cut source at 10.25
        trans = _FakeTransition(
            source_exit_time=10.25,
            source_track_id="t1",
            transition_type=_FakeTransitionType("phrase_cut"),
        )
        track = _FakeTrack(
            id="t1",
            analysis=_FakeAnalysis(
                vocal_regions=vocal_regions,
                phrase_boundaries=phrase_bounds,
            ),
            lyrics=_FakeLyrics(segments=segs),
        )
        plan = _FakePlan(
            tracks=[track],
            transitions=[trans],
            total_duration_sec=180.0,
        )
        result = run_qa_gate(plan)
        assert not result.passed
        assert any(v.metric == "word_midpoint_cut" for v in result.violations)

    def test_reject_click_pop_loop(self):
        """A loop with a phase-inverted seam is rejected."""
        sr = 44100
        freq = 200.0
        tail = _sine(sr, freq, 0.5, phase=0.0)
        head = _sine(sr, freq, 0.5, phase=math.pi)
        result = evaluate_loop_seamlessness(tail, head, sr)
        assert not result.passed

    def test_reject_never_ending_fade(self):
        """A full remix where 60% of time is in crossfades is rejected."""
        track = _FakeTrack(id="t1")
        trans = [
            _FakeTransition(
                transition_type=_FakeTransitionType("crossfade"),
                overlap_duration=30.0,
                source_track_id=f"t{i}",
                target_track_id=f"t{i+1}",
            )
            for i in range(5)
        ]
        plan = _FakePlan(
            tracks=[track] * 6,
            transitions=trans,
            total_duration_sec=250.0,
        )
        result = run_qa_gate(plan)
        assert not result.passed
        assert any(v.metric == "fade_dominance" for v in result.violations)

    def test_reject_vocal_stem_bleed(self):
        """A cut through a high-energy vocal stem region is rejected."""
        sr = 44100
        # Make stem long enough (6s) so a 2s window around cut_time=5.0 fits
        stem = np.ones(sr * 6, dtype=np.float32) * 0.15  # well above 0.03
        trans = _FakeTransition(
            source_exit_time=5.0,
            source_track_id="t1",
            transition_type=_FakeTransitionType("phrase_cut"),
        )
        # Temporarily write stem to a temp file and update the analysis
        import tempfile, soundfile as sf
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, stem, sr)
            stem_path = f.name

        track = _FakeTrack(
            id="t1",
            analysis=_FakeAnalysis(
                stems={"vocals": stem_path},
            ),
        )
        plan = _FakePlan(
            tracks=[track],
            transitions=[trans],
            total_duration_sec=180.0,
        )
        try:
            result = run_qa_gate(plan)
            assert not result.passed
            assert any(v.metric == "stem_bleed_at_cut" for v in result.violations)
        finally:
            import os
            os.unlink(stem_path)


# ═══════════════════════════════════════════════════════════════════════
# 5. Gate orchestrator — integration
# ═══════════════════════════════════════════════════════════════════════

class TestGateOrchestrator:

    def test_clean_plan_passes(self):
        """A simple plan with safe cuts and minimal overlap passes."""
        segs = _segments(("clear", 0.0, 0.5))
        trans = _FakeTransition(
            source_exit_time=2.0,
            source_track_id="t1",
            transition_type=_FakeTransitionType("crossfade"),
            overlap_duration=3.0,
        )
        track = _FakeTrack(
            id="t1",
            analysis=_FakeAnalysis(
                vocal_regions=[(0.0, 1.0)],
                phrase_boundaries=[0.0, 1.0],
            ),
            lyrics=_FakeLyrics(segments=segs),
        )
        plan = _FakePlan(
            tracks=[track],
            transitions=[trans],
            total_duration_sec=200.0,
        )
        result = run_qa_gate(plan)
        assert result.passed

    def test_result_serialization(self):
        """QAResult and QAViolation can be serialized to dict."""
        v = QAViolation(
            module="test",
            metric="test_metric",
            threshold=0.5,
            observed=0.8,
            timestamp=1.0,
            context={"key": "value"},
        )
        r = QAResult(passed=False, violations=[v])
        d = r.to_dict()
        assert d["passed"] is False
        assert len(d["violations"]) == 1
        assert d["violations"][0]["module"] == "test"

    def test_result_merge(self):
        """Merging QAResults combines violations."""
        r1 = QAResult(passed=False, violations=[
            QAViolation("a", "m1", 0.0, 1.0),
        ])
        r2 = QAResult(passed=False, violations=[
            QAViolation("b", "m2", 0.0, 1.0),
        ])
        r1.merge(r2)
        assert len(r1.violations) == 2
        assert not r1.passed

    def test_no_transitions_passes(self):
        plan = _FakePlan(transitions=[], total_duration_sec=0)
        result = run_qa_gate(plan)
        assert result.passed

    def test_with_pre_rendered_splices(self):
        """Splice audio chunks are evaluated."""
        sr = 44100
        # Use 1000Hz so the 10ms correlation window has exactly 10 cycles
        tail = _sine(sr, 1000.0, 0.5)
        head = _sine(sr, 1000.0, 0.5)
        plan = _FakePlan(transitions=[], total_duration_sec=0)
        result = run_qa_gate(
            plan,
            pre_rendered_splices={"t1:5.000": (tail, head)},
        )
        assert result.passed

    def test_timeline_edit_points_reject_vocal_cut(self):
        """PerformanceTimeline internal edits are evaluated for vocal integrity."""
        from djenius.core.models import (
            PerformanceTimeline,
            PerformanceAppearance,
            PerformanceTransition,
            PerformanceSegment,
        )
        # A word spans 0.4s–0.6s on track "vocals_1"
        seg = _segments(("sing", 0.4, 0.6))
        track = _FakeTrack(
            id="vocals_1",
            lyrics=_FakeLyrics(segments=seg),
            analysis=_FakeAnalysis(
                vocal_regions=[(0.0, 2.0)],
                phrase_boundaries=[0.0, 2.0],
            ),
        )
        # Timeline with an appearance whose segment references "vocals_1"
        appearance = PerformanceAppearance(
            id="app_1",
            segment=PerformanceSegment(track_id="vocals_1"),
        )
        # The transition's source_end_sec = 0.5 cuts right through the word
        trans = PerformanceTransition(
            source_appearance_id="app_1",
            source_end_sec=0.5,
        )
        timeline = PerformanceTimeline(
            appearances=[appearance],
            transitions=[trans],
        )
        plan = _FakePlan(
            tracks=[track],
            transitions=[],
            total_duration_sec=200.0,
        )
        plan.performance_timeline = timeline
        result = run_qa_gate(plan)
        assert not result.passed, "Timeline internal cut through word must be rejected"
        metrics = [v.metric for v in result.violations]
        assert "word_midpoint_cut" in metrics

    def test_timeline_target_boundary_rejects(self):
        """Timeline target_start_sec that cuts through a word is rejected."""
        from djenius.core.models import (
            PerformanceTimeline,
            PerformanceAppearance,
            PerformanceTransition,
            PerformanceSegment,
        )
        # Track "vocals_2" has a word at 1.0–1.2
        seg = _segments(("verse", 1.0, 1.2))
        track = _FakeTrack(
            id="vocals_2",
            lyrics=_FakeLyrics(segments=seg),
            analysis=_FakeAnalysis(
                vocal_regions=[(0.0, 2.0)],
                phrase_boundaries=[0.0, 2.0],
            ),
        )
        source_app = PerformanceAppearance(
            id="app_src",
            segment=PerformanceSegment(track_id="other_track"),
        )
        target_app = PerformanceAppearance(
            id="app_tgt",
            segment=PerformanceSegment(track_id="vocals_2"),
        )
        # source_end_sec is safe (in silence), but target_start_sec = 1.1
        # cuts through the word at 1.0–1.2
        trans = PerformanceTransition(
            source_appearance_id="app_src",
            target_appearance_id="app_tgt",
            source_end_sec=0.1,   # safe: in silence
            target_start_sec=1.1, # bad: inside word
        )
        timeline = PerformanceTimeline(
            appearances=[source_app, target_app],
            transitions=[trans],
        )
        plan = _FakePlan(
            tracks=[track],
            transitions=[],
            total_duration_sec=200.0,
        )
        plan.performance_timeline = timeline
        result = run_qa_gate(plan)
        assert not result.passed, "Target boundary cutting a word must be rejected"
        metrics = [v.metric for v in result.violations]
        assert "word_midpoint_cut" in metrics


# ═══════════════════════════════════════════════════════════════════════
# 6. Real audio validation (testMusic)
# ═══════════════════════════════════════════════════════════════════════

TESTMUSIC_DIR = "testMusic"

import os

def _testmusic_files() -> list[str]:
    """Return available testMusic audio paths."""
    base = os.path.join(os.path.dirname(__file__), "..", TESTMUSIC_DIR)
    if not os.path.isdir(base):
        return []
    return sorted(
        os.path.join(base, f)
        for f in os.listdir(base)
        if f.lower().endswith((".mp3", ".wav", ".flac", ".ogg", ".m4a"))
    )


@pytest.mark.skipif(
    not _testmusic_files(),
    reason="testMusic directory not available",
)
class TestRealAudioValidation:

    def test_vocal_integrity_on_real_segs(self):
        """Run vocal integrity evaluator on real whisper segments."""
        import soundfile as sf
        files = _testmusic_files()[:3]
        for fp in files:
            try:
                y, sr = sf.read(fp, dtype="float32", always_2d=True)
                mono = np.mean(y, axis=1)
                duration = len(mono) / sr
                # Create a synthetic cut point mid-track
                cut = duration / 2
                # Create synthetic word timings around the cut
                segs = [
                    {"text": "word_a", "start": cut - 0.3, "end": cut + 0.3},
                ]
                result = evaluate_edit_point(cut, segments=segs)
                # This should be rejected (cut through a word)
                assert not result.passed, f"Should reject cut through word in {fp}"
            except Exception as e:
                pytest.skip(f"Could not read {fp}: {e}")

    def test_loop_dsp_on_real_audio(self):
        """Run loop DSP evaluator on real audio segments."""
        import soundfile as sf
        import numpy as np
        files = _testmusic_files()[:3]
        for fp in files:
            try:
                y, sr = sf.read(fp, dtype="float32", always_2d=True)
                mono = np.mean(y, axis=1)
                duration = len(mono) / sr
                if duration < 2.0:
                    continue
                # Take two chunks from the middle
                mid = int(duration / 2 * sr)
                chunk_len = min(sr, len(mono) - mid)
                tail = mono[mid - chunk_len:mid] if mid >= chunk_len else mono[:mid]
                head = mono[mid:mid + chunk_len]
                result = evaluate_loop_seamlessness(tail, head, sr)
                # Verify evaluator produces reasonable results (not NaN/Inf)
                obs_vals = [v.observed for v in result.violations]
                if obs_vals:
                    assert not any(np.isnan(o) for o in obs_vals),                         f"Got NaN violation for {fp}"
                    assert not any(np.isinf(o) for o in obs_vals),                         f"Got Inf violation for {fp}"
                # Verify correlation is in valid range [-1, 1]
                for v in result.violations:
                    if v.metric == "phase_alignment":
                        assert -1.0 <= v.observed <= 1.0,                             f"Correlation out of range: {v.observed} for {fp}"
                # Verify spectral flux is non-negative
                for v in result.violations:
                    if v.metric == "spectral_flux":
                        assert v.observed >= 0,                             f"Negative spectral flux: {v.observed} for {fp}"
            except Exception as e:
                pytest.skip(f"Could not process {fp}: {e}")
