"""Loop and DSP continuity evaluator.

Measures objective audio continuity at loop boundaries and splice points.
Detects clicks, pops, bass discontinuities, and spectral jumps that
indicate a broken loop or poorly aligned splice.
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

# Maximum allowable RMS jump (dB) across a splice boundary.
RMS_DISCONTINUITY_DB: float = 3.0

# Minimum cross-correlation (0-1) at a loop seam for identical beats.
MIN_CORRELATION: float = 0.85

# Low-pass cutoff (Hz) for bass continuity checks.
BASS_CUTOFF_HZ: float = 150.0

# Maximum allowable spectral flux across a boundary (normalised).
MAX_SPECTRAL_FLUX: float = 0.15


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rms_dbfs(arr: np.ndarray) -> float:
    mono = np.mean(arr, axis=-1) if arr.ndim > 1 else arr
    rms = float(np.sqrt(np.mean(np.square(mono.astype(np.float64)))))
    if rms <= 0:
        return -120.0
    return 20.0 * math.log10(rms)


def _cross_correlation(a: np.ndarray, b: np.ndarray) -> float:
    """Normalised cross-correlation between two 1-D signals."""
    a = _to_mono(a)
    b = _to_mono(b)
    if a.size == 0 or b.size == 0:
        return 0.0
    a = a.astype(np.float64).flatten()
    b = b.astype(np.float64).flatten()
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    a = a - np.mean(a)
    b = b - np.mean(b)
    denom = math.sqrt(float(np.sum(a * a)) * float(np.sum(b * b)))
    if denom < 1e-12:
        return 0.0
    return float(np.sum(a * b) / denom)


def _to_mono(arr: np.ndarray) -> np.ndarray:
    """Downmix stereo/multi-channel audio to mono."""
    if arr.ndim == 1:
        return arr
    return np.mean(arr, axis=-1)


def _spectral_flux(a: np.ndarray, b: np.ndarray, n_fft: int = 1024) -> float:
    """Approximate spectral flux between two short windows.

    Returns the mean L1 distance between their magnitude spectra,
    normalised by the mean energy so the metric is scale-invariant.
    Typical range: 0 (identical) to ~2 (completely different).
    """
    a = _to_mono(a)
    b = _to_mono(b)
    if a.size < n_fft or b.size < n_fft:
        return 0.0
    window = np.hanning(n_fft)
    spec_a = np.abs(np.fft.rfft(a[:n_fft] * window))
    spec_b = np.abs(np.fft.rfft(b[:n_fft] * window))
    # Normalise by mean energy of both spectra for scale invariance
    mean_energy = (np.mean(spec_a) + np.mean(spec_b)) / 2.0
    if mean_energy < 1e-12:
        return 0.0
    return float(np.mean(np.abs(spec_a - spec_b)) / mean_energy)


def _lowpass(arr: np.ndarray, sr: int, cutoff_hz: float) -> np.ndarray:
    """Simple low-pass filter using only numpy (moving-average).

    Window size is chosen so the -3dB point is approximately at
    *cutoff_hz*.  Reflective padding is used to minimise edge effects
    at the seam boundary.
    """
    arr = _to_mono(arr)
    win = max(1, int(sr / cutoff_hz))
    kernel = np.ones(win, dtype=np.float64) / win
    pad_len = win // 2
    # Reflect-pad to reduce startup/transient edge artefacts
    padded = np.pad(arr.astype(np.float64), pad_len, mode='reflect')
    filtered = np.convolve(padded, kernel, mode='same')
    start = pad_len
    end = start + arr.size
    return filtered[start:end]


def _bass_derivative_sign_change(
    tail_bass: np.ndarray, head_bass: np.ndarray,
) -> bool:
    """Detect abrupt bass derivative sign flip at the seam.

    Returns True if the last derivative of the tail and the first
    derivative of the head have opposite signs — indicating a bass
    'suck out' or pop.
    """
    if tail_bass.size < 2 or head_bass.size < 2:
        return False
    # Guard: avoid sign-flip false positives when bass values are near-zero
    tail_last2 = tail_bass[-2:]
    head_first2 = head_bass[:2]
    if abs(tail_bass[-1]) < 1e-4 and abs(tail_bass[-2]) < 1e-4:
        # Both tail samples are near-silent → not a real bass transition
        return False
    if abs(head_bass[1]) < 1e-4 and abs(head_bass[0]) < 1e-4:
        # Both head samples are near-silent → not a real bass transition
        return False
    tail_deriv = float(tail_bass[-1] - tail_bass[-2])
    head_deriv = float(head_bass[1] - head_bass[0])
    return (tail_deriv * head_deriv) < 0 and abs(tail_deriv) > 1e-6 and abs(head_deriv) > 1e-6


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_loop_seamlessness(
    tail_audio: np.ndarray,
    head_audio: np.ndarray,
    sample_rate: int,
    *,
    rms_threshold_db: float = RMS_DISCONTINUITY_DB,
    min_correlation: float = MIN_CORRELATION,
    max_spectral_flux: float = MAX_SPECTRAL_FLUX,
    bass_cutoff_hz: float = BASS_CUTOFF_HZ,
) -> QAResult:
    """Evaluate continuity across a splice / loop boundary.

    Parameters
    ----------
    tail_audio : np.ndarray
        Audio chunk ending at the splice point (e.g. last 500 ms).
    head_audio : np.ndarray
        Audio chunk starting at the splice point (e.g. first 500 ms).
    sample_rate : int
        Sample rate of both chunks.
    rms_threshold_db : float
        Maximum allowable RMS jump across the boundary.
    min_correlation : float
        Minimum cross-correlation for a valid loop.
    max_spectral_flux : float
        Maximum normalised spectral flux across the boundary.
    bass_cutoff_hz : float
        Low-pass cutoff for bass discontinuity detection.

    Returns
    -------
    QAResult
        Passed if all continuity checks are within thresholds.
    """
    result = QAResult()

    if tail_audio.size == 0 or head_audio.size == 0:
        return result

    # ── RMS discontinuity ─────────────────────────────────────────────
    rms_tail = _rms_dbfs(tail_audio)
    rms_head = _rms_dbfs(head_audio)
    rms_jump = abs(rms_tail - rms_head)
    if rms_jump > rms_threshold_db:
        result.add(QAViolation(
            module="loop_dsp",
            metric="rms_discontinuity",
            threshold=rms_threshold_db,
            observed=round(rms_jump, 3),
            context={
                "tail_rms_dbfs": round(rms_tail, 3),
                "head_rms_dbfs": round(rms_head, 3),
                "jump_db": round(rms_jump, 3),
            },
        ))

    # ── Phase / cross-correlation ─────────────────────────────────────
    # Use a 50 ms window for stable alignment; skip if either chunk is too quiet.
    n_corr = max(2, sample_rate // 20)  # ~50 ms minimum
    # Ensure we have enough non-silence energy for meaningful correlation
    tail_energy = float(np.sum(tail_audio ** 2)) if tail_audio.size > 0 else 0.0
    head_energy = float(np.sum(head_audio ** 2)) if head_audio.size > 0 else 0.0
    min_energy = sample_rate * 1e-6  # approximate energy floor
    if tail_energy < min_energy or head_energy < min_energy:
        # Too quiet to evaluate; record and skip correlation check (no violation)
        pass
    else:
        tail_end = tail_audio[-n_corr:] if tail_audio.size >= n_corr else tail_audio
        head_start = head_audio[:n_corr] if head_audio.size >= n_corr else head_audio
        corr = _cross_correlation(tail_end, head_start)
        if corr < min_correlation:
            result.add(QAViolation(
                module="loop_dsp",
                metric="phase_alignment",
                threshold=min_correlation,
                observed=round(corr, 4),
                context={
                    "correlation": round(corr, 4),
                    "window_ms": 50,
                },
            ))

    # ── Spectral flux ─────────────────────────────────────────────────
    n_fft = min(1024, tail_audio.size, head_audio.size)
    if n_fft >= 64:
        flux = _spectral_flux(tail_audio[-n_fft:], head_audio[:n_fft], n_fft)
        if flux > max_spectral_flux:
            result.add(QAViolation(
                module="loop_dsp",
                metric="spectral_flux",
                threshold=max_spectral_flux,
                observed=round(flux, 6),
                context={"flux": round(flux, 6)},
            ))

    # ── Bass continuity ───────────────────────────────────────────────
    n_bass = max(sample_rate // 2, 512)  # ~12 ms minimum
    tail_bass = _lowpass(
        tail_audio[-n_bass:] if tail_audio.size >= n_bass else tail_audio,
        sample_rate, bass_cutoff_hz,
    )
    head_bass = _lowpass(
        head_audio[:n_bass] if head_audio.size >= n_bass else head_audio,
        sample_rate, bass_cutoff_hz,
    )
    if _bass_derivative_sign_change(tail_bass, head_bass):
        result.add(QAViolation(
            module="loop_dsp",
            metric="bass_discontinuity",
            threshold=0.0,
            observed=1.0,
            context={
                "tail_bass_last": round(float(tail_bass[-1]), 6),
                "head_bass_first": round(float(head_bass[0]), 6),
                "bass_cutoff_hz": bass_cutoff_hz,
            },
        ))

    return result


def evaluate_loop_seam_from_arrays(
    full_audio: np.ndarray,
    loop_start_sample: int,
    loop_end_sample: int,
    sample_rate: int,
    **kwargs,
) -> QAResult:
    """Convenience wrapper: extract tail/head from a single array.

    A loop seam compares audio approaching the loop end (tail) with
    audio leaving the loop start (head).
    """
    loop_len = loop_end_sample - loop_start_sample
    tail_len = min(loop_len, loop_end_sample)
    head_len = min(loop_len, full_audio.size - loop_start_sample)
    if tail_len <= 0 or head_len <= 0:
        return QAResult()
    tail = full_audio[loop_end_sample - tail_len:loop_end_sample]
    head = full_audio[loop_start_sample:loop_start_sample + head_len]
    return evaluate_loop_seamlessness(tail, head, sample_rate, **kwargs)
