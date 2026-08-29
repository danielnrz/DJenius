"""Timing and beat-phase utilities for DJenius.

Provides BPM-to-sample conversion, beat phase alignment,
and phase error measurement for beatmatching.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as scipy_signal


def bpm_to_samples(bpm: float, sr: int) -> int:
    """Convert BPM to samples per beat.

    Args:
        bpm: Beats per minute.
        sr: Sample rate.

    Returns:
        Number of samples per beat.

    Raises:
        ValueError: If bpm <= 0.
    """
    if bpm <= 0:
        raise ValueError(f"BPM must be positive, got {bpm}")
    return int(round(sr * 60.0 / bpm))


def bpm_to_beat_period(bpm: float, sr: int) -> float:
    """Convert BPM to beat period in seconds."""
    if bpm <= 0:
        raise ValueError(f"BPM must be positive, got {bpm}")
    return 60.0 / bpm


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """Convert audio to mono by averaging channels.

    Unlike ``ndarray.flatten()`` which interleaves L/R samples for a
    ``(samples, 2)`` array and destroys temporal alignment, this function
    properly averages across channels while preserving the time axis.

    Args:
        audio: 1D mono array or 2D ``(samples, channels)`` array.

    Returns:
        1D mono float32 array.
    """
    if audio.ndim == 1:
        return audio
    return np.mean(audio, axis=1)


def _envelope(audio: np.ndarray, hop: int = 512) -> np.ndarray:
    """Compute a simple onset-strength envelope for transient detection.

    Uses half-wave rectified first-difference of RMS energy.

    Accepts mono or stereo audio; multi-channel input is properly mixed
    to mono via :func:`_to_mono` before analysis.
    """
    mono = _to_mono(audio)
    n_frames = max(1, len(mono) // hop)
    envelope = np.zeros(n_frames, dtype=np.float32)
    prev_rms = 0.0
    for i in range(n_frames):
        start = i * hop
        end = min(start + hop, len(mono))
        frame = mono[start:end]
        rms = float(np.sqrt(np.mean(frame ** 2))) if len(frame) > 0 else 0.0
        diff = rms - prev_rms
        envelope[i] = max(0.0, diff)
        prev_rms = rms
    return envelope


def calculate_phase_shift(
    source: np.ndarray,
    target: np.ndarray,
    sr: int,
    hop: int = 512,
    bpm: float | None = None,
) -> int:
    """Calculate the optimal sample shift to align target's beats with source.

    Uses cross-correlation on onset-strength envelopes to find the best
    alignment offset, then converts back to sample-level precision.

    When ``bpm`` is provided, the correlation is folded by the beat period
    to resolve the nearest musically equivalent phase offset, preventing
    ambiguous peaks that are one or more full beats apart.

    Args:
        source: Source audio (1D or 2D - properly mixed to mono for analysis).
        target: Target audio (1D or 2D).
        sr: Sample rate.
        hop: Hop size for envelope extraction.
        bpm: Known BPM of the tracks. When provided, constrains the
            alignment to within half a beat period of the best peak,
            preventing full-beat ambiguity on periodic signals.

    Returns:
        Optimal shift in samples (positive = shift target right,
        negative = shift target left).
    """
    # Get onset envelopes (mono conversion happens inside _envelope)
    src_env = _envelope(source, hop)
    tgt_env = _envelope(target, hop)

    # If either envelope is all zeros, return 0
    if src_env.max() == 0 or tgt_env.max() == 0:
        return 0

    # Cross-correlate envelopes
    correlation = scipy_signal.correlate(src_env, tgt_env, mode='full', method='fft')
    lags = np.arange(-len(tgt_env) + 1, len(src_env))

    if bpm is not None and bpm > 0:
        # Beat-period-aware: fold the correlation by the beat period
        # to find the best sub-beat phase offset.
        beat_period_sec = 60.0 / bpm
        beat_period_frames = max(1, int(round((beat_period_sec * sr) / hop)))

        # Wrap each lag into the range [0, beat_period_frames)
        folded = np.zeros(beat_period_frames, dtype=np.float64)
        for i, lag in enumerate(lags):
            idx = lag % beat_period_frames
            folded[idx] += correlation[i]

        best_folded_idx = int(np.argmax(folded))

        # Center the result to [-beat_period/2, +beat_period/2]
        if best_folded_idx > beat_period_frames // 2:
            best_lag = best_folded_idx - beat_period_frames
        else:
            best_lag = best_folded_idx

        shift_samples = int(best_lag * hop)
    else:
        # Fallback: standard global maximum
        best_idx = int(np.argmax(correlation))
        lag = lags[best_idx]
        shift_samples = int(lag * hop)

    return shift_samples


def apply_phase_shift(
    target: np.ndarray,
    shift_samples: int,
) -> np.ndarray:
    """Apply a sample-level phase shift to target audio.

    Shifts the audio in time by the given number of samples.
    Positive shift = delay (pad zeros at start).
    Negative shift = advance (trim from start, pad at end).

    Args:
        target: Audio array (1D or 2D [samples, channels]).
        shift_samples: Number of samples to shift. Positive delays, negative advances.

    Returns:
        Shifted audio of the same length as input.
    """
    n = len(target)

    if shift_samples == 0:
        return target.copy()

    if target.ndim == 1:
        if shift_samples > 0:
            # Delay: pad zeros at start, trim end
            result = np.zeros(n, dtype=target.dtype)
            copy_len = min(n, n - shift_samples)
            if copy_len > 0:
                result[shift_samples:shift_samples + copy_len] = target[:copy_len]
            return result
        else:
            # Advance: trim start, pad zeros at end
            abs_shift = abs(shift_samples)
            result = np.zeros(n, dtype=target.dtype)
            copy_len = min(n, n - abs_shift)
            if copy_len > 0:
                result[:copy_len] = target[abs_shift:abs_shift + copy_len]
            return result
    else:
        # Stereo/multi-channel
        if shift_samples > 0:
            result = np.zeros_like(target)
            copy_len = min(n, n - shift_samples)
            if copy_len > 0:
                result[shift_samples:shift_samples + copy_len] = target[:copy_len]
            return result
        else:
            abs_shift = abs(shift_samples)
            result = np.zeros_like(target)
            copy_len = min(n, n - abs_shift)
            if copy_len > 0:
                result[:copy_len] = target[abs_shift:abs_shift + copy_len]
            return result


def measure_phase_error(
    source: np.ndarray,
    target: np.ndarray,
    sr: int,
    hop: int = 512,
    bpm: float | None = None,
) -> float:
    """Measure the phase error between source and target beats.

    Returns the absolute offset in samples between the nearest transients.
    Lower values indicate better beat alignment.

    Args:
        source: Source audio.
        target: Target audio.
        sr: Sample rate.
        hop: Hop size for envelope extraction.
        bpm: Known BPM. When provided, enables beat-period-aware
            alignment that prevents full-beat ambiguity.

    Returns:
        Phase error in samples (always >= 0).
    """
    shift = calculate_phase_shift(source, target, sr, hop, bpm=bpm)
    return abs(shift)
