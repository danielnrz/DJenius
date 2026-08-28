"""Audio math helpers - crossfade curves, LUFS utilities, DSP primitives."""

from __future__ import annotations

import numpy as np


def equal_power_crossfade(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Generate equal-power crossfade curves.

    Returns two arrays of length n that sum to unit power at every point.
    This sounds more natural than linear crossfades.
    """
    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    fade_out = np.cos(t).astype(np.float32)
    fade_in = np.sin(t).astype(np.float32)
    return fade_out, fade_in


def linear_fade_out(n: int) -> np.ndarray:
    """Linear fade out from 1.0 to 0.0."""
    return np.linspace(1.0, 0.0, n, dtype=np.float32)


def linear_fade_in(n: int) -> np.ndarray:
    """Linear fade in from 0.0 to 1.0."""
    return np.linspace(0.0, 1.0, n, dtype=np.float32)


def db_to_linear(db: float) -> float:
    """Convert decibels to linear amplitude."""
    return 10.0 ** (db / 20.0)


def linear_to_db(linear: float) -> float:
    """Convert linear amplitude to decibels."""
    if linear <= 0:
        return -120.0
    return 20.0 * np.log10(linear)


def soft_clip(audio: np.ndarray, threshold_db: float = -1.0) -> np.ndarray:
    """Apply soft clipping to prevent hard digital distortion.

    Uses a smooth tanh-based curve to gently compress peaks above threshold.
    """
    threshold = db_to_linear(threshold_db)
    result = audio.copy()
    mask = np.abs(result) > threshold
    # Apply tanh compression for values above threshold
    sign = np.sign(result[mask])
    excess = np.abs(result[mask]) / threshold
    result[mask] = sign * threshold * np.tanh(excess)
    return result


def compute_rms_energy(signal: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
    """Compute RMS energy over time.

    Args:
        signal: 1D audio signal
        frame_size: window size in samples
        hop_size: hop size in samples

    Returns:
        Array of RMS values
    """
    n_frames = 1 + (len(signal) - frame_size) // hop_size
    rms = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        start = i * hop_size
        frame = signal[start:start + frame_size]
        rms[i] = np.sqrt(np.mean(frame ** 2))
    return rms


def compute_spectral_energy_bands(
    signal: np.ndarray,
    sr: int,
    low_cutoff: float = 300.0,
    mid_cutoff: float = 4000.0,
    frame_size: int = 2048,
    hop_size: int = 512,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute average energy in low, mid, and high frequency bands.

    Returns (low_energy, mid_energy, high_energy) as scalar values 0-1.
    """
    from scipy import signal as scipy_signal

    nyq = sr / 2.0

    # Design bandpass filters
    if low_cutoff > 0 and low_cutoff < nyq:
        b_low, a_low = scipy_signal.butter(4, low_cutoff / nyq, btype='low')
        low = scipy_signal.filtfilt(b_low, a_low, signal)
        low_energy = float(np.sqrt(np.mean(low ** 2)))
    else:
        low_energy = 0.0

    if low_cutoff < mid_cutoff and mid_cutoff < nyq:
        b_mid, a_mid = scipy_signal.butter(
            4, [low_cutoff / nyq, mid_cutoff / nyq], btype='band'
        )
        mid = scipy_signal.filtfilt(b_mid, a_mid, signal)
        mid_energy = float(np.sqrt(np.mean(mid ** 2)))
    else:
        mid_energy = 0.0

    if mid_cutoff < nyq:
        b_high, a_high = scipy_signal.butter(4, mid_cutoff / nyq, btype='high')
        high = scipy_signal.filtfilt(b_high, a_high, signal)
        high_energy = float(np.sqrt(np.mean(high ** 2)))
    else:
        high_energy = 0.0

    # Normalize to 0-1 range
    total = low_energy + mid_energy + high_energy
    if total > 0:
        low_energy /= total
        mid_energy /= total
        high_energy /= total

    return (low_energy, mid_energy, high_energy)


def compute_energy_curve(
    signal: np.ndarray,
    sr: int,
    resolution_hz: float = 1.0,
) -> np.ndarray:
    """Compute a macro energy curve over time at the given resolution.

    Returns values normalized to 0-1 range.
    """
    hop = int(sr / resolution_hz)
    frame_size = hop * 2

    n_frames = max(1, (len(signal) - frame_size) // hop)
    energy = np.zeros(n_frames, dtype=np.float32)

    for i in range(n_frames):
        start = i * hop
        end = min(start + frame_size, len(signal))
        frame = signal[start:end]
        if len(frame) > 0:
            energy[i] = np.sqrt(np.mean(frame ** 2))

    # Normalize to 0-1
    max_e = energy.max()
    if max_e > 0:
        energy = energy / max_e

    return energy


def detect_intro_outro(
    energy_curve: np.ndarray,
    threshold: float = 0.3,
    min_bars: int = 4,
    bar_duration_hint: float = 2.0,
) -> tuple[float, float]:
    """Estimate intro end and outro start from the energy curve.

    Returns (intro_end_sec, outro_start_sec).
    """
    n = len(energy_curve)
    if n == 0:
        return (0.0, 0.0)

    # Find intro end: first point where energy sustains above threshold
    bar_frames = int(bar_duration_hint * 1.0)  # At 1Hz resolution

    intro_end_frames = 0
    for i in range(n):
        if energy_curve[i] > threshold:
            # Check if energy stays up for at least min_bars
            remaining = min(bar_frames * min_bars, n - i)
            if remaining >= bar_frames and np.mean(energy_curve[i:i + bar_frames]) > threshold:
                intro_end_frames = i
                break

    # Find outro start: last point where energy sustains above threshold
    outro_start_frames = n - 1
    for i in range(n - 1, -1, -1):
        if energy_curve[i] > threshold:
            check_start = max(0, i - bar_frames * min_bars + 1)
            remaining = i - check_start + 1
            if remaining >= bar_frames and np.mean(energy_curve[check_start:i + 1]) > threshold:
                outro_start_frames = i
                break

    intro_end = float(intro_end_frames)
    outro_start = float(outro_start_frames)

    return (intro_end, outro_start)


def normalize_lufs(audio: np.ndarray, sr: int, target_lufs: float = -14.0) -> np.ndarray:
    """Normalize audio to a target LUFS level.

    Uses simple gain adjustment based on integrated loudness.
    """
    import pyloudnorm as pyln

    # pyloudnorm expects 2D array for stereo
    if audio.ndim == 1:
        audio_2d = audio.reshape(-1, 1)
    else:
        audio_2d = audio

    meter = pyln.Meter(sr)

    try:
        current_lufs = meter.integrated_loudness(audio_2d)
        if np.isinf(current_lufs) or np.isnan(current_lufs):
            return audio
        normalized = pyln.normalize.loudness(audio_2d, current_lufs, target_lufs)
    except Exception:
        # Fallback to peak normalization
        peak = np.max(np.abs(audio))
        if peak > 0:
            target_peak = db_to_linear(-1.0)
            normalized = audio_2d * (target_peak / peak)
        else:
            return audio

    if audio.ndim == 1:
        return normalized.reshape(-1).astype(np.float32)
    return normalized.astype(np.float32)
