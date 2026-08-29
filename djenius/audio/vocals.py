"""Vocal activity heuristic for avoiding vocal-on-vocal clashes.

Uses spectral analysis to estimate where vocals are present in a track,
without requiring stem separation. The DJ Brain uses these regions to
avoid overlapping vocal sections during transitions.

Key insight: vocals occupy ~300-3000Hz with specific spectral flatness
and harmonic patterns. We detect these regions via:
1. Spectral flatness in the vocal band (vocals are harmonic = low flatness)
2. Mid-energy ratio relative to broadband energy
3. Temporal continuity (vocals come in phrases, not single frames)
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def estimate_vocal_regions(
    y: np.ndarray,
    sr: int,
    hop_length: int = 512,
    vocal_band_hz: tuple[float, float] = (300.0, 3000.0),
    threshold: float = 0.4,
) -> list[tuple[float, float]]:
    """Estimate time regions where vocals are likely present.

    Args:
        y: Audio signal (1D mono or 2D stereo — will be flattened).
        sr: Sample rate.
        hop_length: FFT hop size in samples.
        vocal_band_hz: Frequency range for vocal detection.
        threshold: Detection threshold (0-1). Lower = more sensitive.

    Returns:
        List of (start_sec, end_sec) tuples for detected vocal regions.
    """
    if len(y) == 0 or sr <= 0:
        return []

    # Flatten to mono
    if y.ndim == 2:
        audio = np.mean(y, axis=1)
    else:
        audio = y.astype(np.float32)

    n_fft = 2048
    if len(audio) < n_fft:
        return []

    # Compute STFT
    try:
        import librosa
        S = np.abs(librosa.stft(audio, n_fft=n_fft, hop_length=hop_length))
    except Exception:
        return []

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)

    # Isolate vocal band
    vocal_mask = (freqs >= vocal_band_hz[0]) & (freqs <= vocal_band_hz[1])
    if not np.any(vocal_mask):
        return []

    vocal_energy = np.sum(S[vocal_mask] ** 2, axis=0)
    total_energy = np.sum(S ** 2, axis=0) + 1e-10

    # Vocal prominence: ratio of vocal band energy to total
    vocal_ratio = vocal_energy / total_energy

    # Spectral flatness in vocal band (vocals = harmonic = low flatness)
    try:
        flatness = librosa.feature.spectral_flatness(
            y=audio, n_fft=n_fft, hop_length=hop_length,
        )[0]
    except Exception:
        flatness = np.ones_like(vocal_ratio)

    # Combine: vocals have high ratio AND low flatness (harmonic content)
    vocal_score = vocal_ratio * (1.0 - flatness * 0.5)

    # Smooth over time (vocals come in phrases, ~0.5-2 second windows)
    smooth_window = max(1, int(sr / hop_length * 0.5))  # ~0.5 sec
    kernel = np.ones(smooth_window) / smooth_window
    vocal_score_smooth = np.convolve(vocal_score, kernel, mode="same")

    # Detect active regions
    is_vocal = vocal_score_smooth > threshold

    # Convert frame indices to time ranges
    regions = _frames_to_regions(is_vocal, sr, hop_length)

    # Merge close regions (gap < 0.5 sec)
    regions = _merge_close_regions(regions, min_gap_sec=0.5)

    return regions


def score_vocal_overlap(
    source_vocal_regions: list[tuple[float, float]],
    target_vocal_regions: list[tuple[float, float]],
    source_exit_time: float,
    target_entry_time: float,
    overlap_duration: float,
) -> float:
    """Score the vocal clash risk for a specific transition point.

    Args:
        source_vocal_regions: Vocal regions of the source track.
        target_vocal_regions: Vocal regions of the target track.
        source_exit_time: Time in source where transition starts.
        target_entry_time: Time in target where it starts playing.
        overlap_duration: Duration of the overlap region.

    Returns:
        0.0 = high vocal clash risk, 1.0 = safe (no vocal overlap).
    """
    if overlap_duration <= 0:
        return 1.0

    # Compute the overlap time window
    source_start = source_exit_time
    source_end = source_exit_time + overlap_duration
    target_start = target_entry_time
    target_end = target_entry_time + overlap_duration

    # Check how much of source overlap has vocals
    source_vocal_time = _time_in_regions(
        source_start, source_end, source_vocal_regions
    )
    target_vocal_time = _time_in_regions(
        target_start, target_end, target_vocal_regions
    )

    # Both tracks have vocals simultaneously = high risk
    source_vocal_frac = source_vocal_time / max(overlap_duration, 1e-6)
    target_vocal_frac = target_vocal_time / max(overlap_duration, 1e-6)

    # Overlap: both vocal at same time = worst case
    overlap_risk = source_vocal_frac * target_vocal_frac

    # Even one vocal over instrumental can be ok, but both vocal = bad
    if overlap_risk > 0.5:
        return 0.3  # High clash risk
    elif overlap_risk > 0.25:
        return 0.6  # Moderate risk
    elif overlap_risk > 0.1:
        return 0.8  # Low risk
    else:
        return 1.0  # Safe


def suggest_vocal_safe_exit(
    vocal_regions: list[tuple[float, float]],
    duration: float,
    min_exit_sec: float = 0.0,
    prefer_outro: bool = True,
) -> list[float]:
    """Suggest exit points that avoid cutting off vocals.

    Args:
        vocal_regions: Vocal regions of the track.
        duration: Track duration in seconds.
        min_exit_sec: Earliest acceptable exit time.
        prefer_outro: Prefer points in the outro region.

    Returns:
        List of suggested exit times (seconds), sorted best-first.
    """
    if duration <= 0:
        return []

    candidates = []

    # Check the gaps between vocal phrases
    # Good exit points are right after a vocal phrase ends
    for start, end in vocal_regions:
        if end >= min_exit_sec and end < duration - 3.0:
            # Exit right after vocals end
            candidates.append(end)

    # Also consider the outro region (after all vocals)
    outro_start = vocal_regions[-1][1] if vocal_regions else duration * 0.7
    outro_start = max(outro_start, duration * 0.65)

    if outro_start < duration - 5.0:
        candidates.append(outro_start)
        candidates.append(outro_start + 4.0)  # 4 bars into outro

    # Filter
    candidates = [
        round(t, 3) for t in candidates
        if min_exit_sec <= t < duration - 2.0
    ]

    if prefer_outro:
        # Sort: prefer later points (outro region)
        candidates.sort(reverse=True)
    else:
        candidates.sort()

    return list(dict.fromkeys(candidates))  # deduplicate preserving order


def _frames_to_regions(
    is_active: np.ndarray, sr: int, hop_length: int,
) -> list[tuple[float, float]]:
    """Convert a boolean frame array to time regions."""
    regions = []
    in_region = False
    start_frame = 0

    for i, val in enumerate(is_active):
        if val and not in_region:
            in_region = True
            start_frame = i
        elif not val and in_region:
            in_region = False
            start_sec = start_frame * hop_length / sr
            end_sec = i * hop_length / sr
            regions.append((start_sec, end_sec))

    # Close final region
    if in_region:
        start_sec = start_frame * hop_length / sr
        end_sec = len(is_active) * hop_length / sr
        regions.append((start_sec, end_sec))

    return regions


def _merge_close_regions(
    regions: list[tuple[float, float]], min_gap_sec: float = 0.5,
) -> list[tuple[float, float]]:
    """Merge regions that are separated by less than min_gap_sec."""
    if not regions:
        return []

    merged = [list(regions[0])]
    for start, end in regions[1:]:
        if start - merged[-1][1] < min_gap_sec:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    return [(s, e) for s, e in merged]


def _time_in_regions(
    start: float, end: float, regions: list[tuple[float, float]],
) -> float:
    """Compute how many seconds of [start, end] overlap with regions."""
    total = 0.0
    for rs, re in regions:
        overlap_start = max(start, rs)
        overlap_end = min(end, re)
        if overlap_end > overlap_start:
            total += overlap_end - overlap_start
    return total
