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


def _envelope(signal: np.ndarray, hop: int = 512) -> np.ndarray:
    """Compute a simple onset-strength envelope for transient detection.

    Uses half-wave rectified first-difference of RMS energy.
    """
    n_frames = max(1, len(signal) // hop)
    envelope = np.zeros(n_frames, dtype=np.float32)
    prev_rms = 0.0
    for i in range(n_frames):
        start = i * hop
        end = min(start + hop, len(signal))
        frame = signal[start:end]
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
) -> int:
    """Calculate the optimal sample shift to align target's beats with source.

    Uses cross-correlation on onset-strength envelopes to find the best
    alignment offset, then converts back to sample-level precision.

    Args:
        source: Source audio (1D or 2D - uses first channel or mix).
        target: Target audio (1D or 2D).
        sr: Sample rate.
        hop: Hop size for envelope extraction.

    Returns:
        Optimal shift in samples (positive = shift target right,
        negative = shift target left).
    """
    # Flatten to mono for envelope extraction
    src_mono = source.flatten() if source.ndim > 1 else source
    tgt_mono = target.flatten() if target.ndim > 1 else target

    # Get onset envelopes
    src_env = _envelope(src_mono, hop)
    tgt_env = _envelope(tgt_mono, hop)

    # If either envelope is all zeros, return 0
    if src_env.max() == 0 or tgt_env.max() == 0:
        return 0

    # Cross-correlate envelopes
    correlation = scipy_signal.correlate(src_env, tgt_env, mode='full', method='fft')
    lag = np.argmax(correlation) - (len(tgt_env) - 1)

    # Convert envelope lag to sample lag
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
) -> float:
    """Measure the phase error between source and target beats.

    Returns the absolute offset in samples between the nearest transients.
    Lower values indicate better beat alignment.

    Args:
        source: Source audio.
        target: Target audio.
        sr: Sample rate.
        hop: Hop size for envelope extraction.

    Returns:
        Phase error in samples (always >= 0).
    """
    shift = calculate_phase_shift(source, target, sr, hop)
    return abs(shift)
