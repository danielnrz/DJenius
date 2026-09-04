"""Vocal edit integrity evaluator.

Detects edits, splices, or loops that cut through active sung words,
syllables, or dense vocal phrases.  Uses whisper word timings from
``LyricsProfile.segments``, vocal regions from ``TrackAnalysis``,
and optional stem RMS at the cut point.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from djenius.audio.qa.models import QAResult, QAViolation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Minimum gap (seconds) between a cut point and the nearest word boundary
# for the cut to be considered safe.
WORD_SAFE_MARGIN_SEC: float = 0.050  # 50 ms

# Minimum distance (seconds) between a cut point and the nearest phrase
# boundary for the cut to be considered safe inside a vocal region.
PHRASE_SAFE_MARGIN_SEC: float = 0.200  # 200 ms

# If the vocal stem RMS (linear, 0-1) at a supposed-silent cut point
# exceeds this, the cut is still inside audible vocals.
STEM_SILENCE_THRESHOLD: float = 0.03  # ≈ -30 dBFS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rms(arr: np.ndarray) -> float:
    """Root-mean-square of a (possibly stereo) array."""
    if arr.size == 0:
        return 0.0
    mono = np.mean(arr, axis=-1) if arr.ndim > 1 else arr
    return float(np.sqrt(np.mean(np.square(mono.astype(np.float64)))))


def _rms_dbfs(arr: np.ndarray) -> float:
    rms = _rms(arr)
    if rms <= 0:
        return -120.0
    return 20.0 * math.log10(rms)


def _word_timings_from_segments(segments: list[dict]) -> list[tuple[str, float, float]]:
    """Extract (text, start_sec, end_sec) from whisper segment dicts."""
    timings: list[tuple[str, float, float]] = []
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        if text and end > start:
            timings.append((text, start, end))
    return timings


def _nearest_word_margin(cut: float, words: list[tuple[str, float, float]]) -> tuple[float, str, bool]:
    """Return (min_distance_sec, word_text, inside) of the closest word to *cut*.

    ``inside`` is True when *cut* falls strictly inside a word (start <= cut < end).
    ``min_distance_sec`` is the unsigned distance to the nearest word boundary.
    A cut at the exact word boundary returns (0.0, word, False).
    A cut at the exact word midpoint returns (word_duration/2, word, True).
    """
    best_dist = float("inf")
    best_word = ""
    best_inside = False
    for text, wstart, wend in words:
        if wstart <= cut < wend:
            # Inside the word — distance is to the nearest boundary
            dist = min(cut - wstart, wend - cut)
            inside = True
        elif cut < wstart:
            dist = wstart - cut
            inside = False
        else:
            dist = cut - wend
            inside = False
        if dist < best_dist:
            best_dist = dist
            best_word = text
            best_inside = inside
    return best_dist, best_word, best_inside


def _in_vocal_region(
    cut: float,
    vocal_regions: list[tuple[float, float]],
) -> bool:
    for start, end in vocal_regions:
        if start <= cut <= end:
            return True
    return False


def _nearest_phrase_boundary(cut: float, boundaries: list[float]) -> float:
    if not boundaries:
        return float("inf")
    return min(abs(cut - b) for b in boundaries)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_edit_point(
    cut_time: float,
    *,
    segments: list[dict] | None = None,
    vocal_regions: list[tuple[float, float]] | None = None,
    phrase_boundaries: list[float] | None = None,
    vocal_stem_audio: np.ndarray | None = None,
    sample_rate: int = 44100,
    stem_loaded_start: float = 0.0,
    tolerance_sec: float = WORD_SAFE_MARGIN_SEC,
    phrase_margin_sec: float = PHRASE_SAFE_MARGIN_SEC,
    stem_threshold: float = STEM_SILENCE_THRESHOLD,
) -> QAResult:
    """Evaluate a single transition/edit point for vocal integrity.

    Parameters
    ----------
    cut_time : float
        The timeline position (seconds) where the edit/splice occurs.
    segments : list[dict], optional
        Whisper transcription segments (``start``, ``end``, ``text``).
    vocal_regions : list[tuple[float, float]], optional
        Detected vocal time regions from ``TrackAnalysis.vocal_regions``.
    phrase_boundaries : list[float], optional
        Phrase boundary timestamps from ``TrackAnalysis.phrase_boundaries``.
    vocal_stem_audio : np.ndarray, optional
        A short chunk of the Demucs vocal stem around the cut point.
        If provided, RMS at the cut is checked against *stem_threshold*.
    sample_rate : int
        Sample rate of *vocal_stem_audio*.
    stem_loaded_start : float
        Timeline position (seconds) of the first sample in *vocal_stem_audio*.
    tolerance_sec : float
        Minimum safe margin around word boundaries (default 50 ms).
    phrase_margin_sec : float
        Minimum safe margin around phrase boundaries (default 200 ms).
    stem_threshold : float
        Vocal stem RMS threshold for "silence" (default 0.03 ≈ -30 dBFS).

    Returns
    -------
    QAResult
        Passed if no vocal integrity violations are found.
    """
    result = QAResult()

    # ── Word splitting check ──────────────────────────────────────────
    if segments:
        words = _word_timings_from_segments(segments)
        if words:
            margin, word_text, inside = _nearest_word_margin(cut_time, words)
            if inside or (0 < margin < tolerance_sec):
                result.add(QAViolation(
                    module="vocal_integrity",
                    metric="word_midpoint_cut",
                    threshold=tolerance_sec,
                    observed=round(margin, 6),
                    timestamp=cut_time,
                    context={
                        "word": word_text,
                        "cut_time": cut_time,
                        "margin_sec": round(margin, 6),
                    },
                ))

    # ── Dense phrase interruption ──────────────────────────────────────
    if vocal_regions and phrase_boundaries:
        if _in_vocal_region(cut_time, vocal_regions):
            phrase_dist = _nearest_phrase_boundary(cut_time, phrase_boundaries)
            if phrase_dist > phrase_margin_sec:
                result.add(QAViolation(
                    module="vocal_integrity",
                    metric="phrase_interruption",
                    threshold=phrase_margin_sec,
                    observed=round(phrase_dist, 6),
                    timestamp=cut_time,
                    context={
                        "cut_time": cut_time,
                        "phrase_distance_sec": round(phrase_dist, 6),
                    },
                ))

    # ── Stem bleed check ──────────────────────────────────────────────
    if vocal_stem_audio is not None and vocal_stem_audio.size > 0:
        sr = sample_rate
        # Compute the exact sample index of the cut point within the
        # loaded stem window, clamped to valid bounds.
        cut_sample = int(round((cut_time - stem_loaded_start) * sr))
        cut_sample = max(0, min(cut_sample, vocal_stem_audio.shape[0] - 1))
        # Use a 5 ms window around the cut sample
        half_win = max(1, sr // 200)  # ≈ 5 ms
        lo = max(0, cut_sample - half_win)
        hi = min(vocal_stem_audio.shape[0], cut_sample + half_win)
        window = vocal_stem_audio[lo:hi]
        rms_val = _rms(window)
        if rms_val > stem_threshold:
            result.add(QAViolation(
                module="vocal_integrity",
                metric="stem_bleed_at_cut",
                threshold=stem_threshold,
                observed=round(float(rms_val), 6),
                timestamp=cut_time,
                context={
                    "cut_time": cut_time,
                    "stem_rms": round(float(rms_val), 6),
                    "stem_rms_dbfs": round(_rms_dbfs(window), 2),
                },
            ))

    return result


def evaluate_multiple_edit_points(
    cut_times: list[float],
    *,
    segments: list[dict] | None = None,
    vocal_regions: list[tuple[float, float]] | None = None,
    phrase_boundaries: list[float] | None = None,
    vocal_stem_audio: np.ndarray | None = None,
    sample_rate: int = 44100,
    stem_loaded_start: float = 0.0,
    tolerance_sec: float = WORD_SAFE_MARGIN_SEC,
    phrase_margin_sec: float = PHRASE_SAFE_MARGIN_SEC,
    stem_threshold: float = STEM_SILENCE_THRESHOLD,
) -> QAResult:
    """Evaluate multiple edit points in a single call."""
    combined = QAResult()
    for cut in cut_times:
        combined.merge(evaluate_edit_point(
            cut,
            segments=segments,
            vocal_regions=vocal_regions,
            phrase_boundaries=phrase_boundaries,
            vocal_stem_audio=vocal_stem_audio,
            sample_rate=sample_rate,
            stem_loaded_start=stem_loaded_start,
            tolerance_sec=tolerance_sec,
            phrase_margin_sec=phrase_margin_sec,
            stem_threshold=stem_threshold,
        ))
    return combined
