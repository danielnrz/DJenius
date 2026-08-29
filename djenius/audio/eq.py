"""Musical bass/EQ management for transitions.

Provides beat-aligned, energy-aware EQ curves that prevent bass clashes
and keep the midrange clean during transitions. The DJ Brain calls
these with track spectral profiles; the curves are then consumed by
the transition DSP.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def compute_bass_duck_curve(
    n_samples: int,
    sr: int,
    bpm: float,
    duck_phase: str = "outgoing",
) -> np.ndarray:
    """Compute a beat-aligned gain curve for ducking bass on one track.

    Args:
        n_samples: Number of samples in the transition region.
        sr: Sample rate.
        bpm: Current BPM for beat alignment.
        duck_phase: 'outgoing' (duck bass down) or 'incoming' (duck first then lift).

    Returns:
        Float32 gain curve, shape (n_samples,), values 0.0-1.0.
        1.0 = full volume, 0.0 = fully ducked.
    """
    if n_samples <= 0 or sr <= 0 or bpm <= 0:
        return np.ones(n_samples, dtype=np.float32)

    beat_samples = int(sr * 60.0 / bpm)

    # Time axis
    t = np.linspace(0.0, n_samples / sr, n_samples, dtype=np.float32)

    if duck_phase == "outgoing":
        # Smooth fade-out on bass, beat-aligned
        # Start at 1.0, end near 0.2 over the full region
        curve = np.clip(1.0 - (t / t[-1]) * 0.8, 0.2, 1.0).astype(np.float32)
        # Add subtle beat-synchronized dip (pumping feel)
        pump = 0.08 * np.abs(np.sin(np.pi * t / (beat_samples / sr)))
        curve = np.clip(curve - pump, 0.0, 1.0).astype(np.float32)
    else:
        # Incoming: start ducked, lift bass in
        curve = np.clip(0.2 + (t / t[-1]) * 0.8, 0.0, 1.0).astype(np.float32)
        # Beat-aligned lift
        pump = 0.08 * np.abs(np.sin(np.pi * t / (beat_samples / sr)))
        curve = np.clip(curve + pump, 0.0, 1.0).astype(np.float32)

    return curve


def compute_eq_sweep_curve(
    n_samples: int,
    sr: int,
    low_freq: float = 100.0,
    high_freq: float = 4000.0,
    direction: str = "highpass_sweep",
) -> np.ndarray:
    """Compute a log-swept cutoff frequency curve for filter transitions.

    Args:
        n_samples: Number of samples in the transition region.
        sr: Sample rate.
        low_freq: Starting cutoff frequency (Hz).
        high_freq: Ending cutoff frequency (Hz).
        direction: 'highpass_sweep' (outgoing loses bass first) or
                   'lowpass_sweep' (incoming opens up).

    Returns:
        Float32 cutoff curve, shape (n_samples,), in Hz.
    """
    if n_samples <= 0:
        return np.array([], dtype=np.float32)

    t = np.linspace(0.0, 1.0, n_samples, dtype=np.float32)

    if direction == "highpass_sweep":
        # Outgoing: sweep high-pass from low to high (removes bass progressively)
        freqs = low_freq * (high_freq / low_freq) ** t
    else:
        # Incoming: sweep low-pass from high to low (opens up progressively)
        freqs = high_freq * (low_freq / high_freq) ** t

    return freqs.astype(np.float32)


def compute_mid_duck_curve(
    n_samples: int,
    sr: int,
    source_mid_energy: float,
    target_mid_energy: float,
) -> np.ndarray:
    """Compute a midrange ducking curve to prevent muddy transitions.

    When both tracks have strong mid energy, duck the outgoing track's
    mids slightly to make room.

    Args:
        n_samples: Number of samples.
        sr: Sample rate.
        source_mid_energy: Source track's mid energy (0.0-1.0).
        target_mid_energy: Target track's mid energy (0.0-1.0).

    Returns:
        Float32 gain curve, shape (n_samples,). 1.0 = full, lower = ducked.
    """
    if n_samples <= 0:
        return np.ones(n_samples, dtype=np.float32)

    # Only duck if both tracks have significant mid energy
    mid_clash = min(source_mid_energy, target_mid_energy)
    if mid_clash < 0.3:
        return np.ones(n_samples, dtype=np.float32)

    # Duck amount proportional to clash severity
    duck_amount = (mid_clash - 0.3) * 0.5  # max ~35% duck

    # Smooth envelope: duck in, hold, duck out
    t = np.linspace(0.0, 1.0, n_samples, dtype=np.float32)

    # Raised cosine shape (smooth in and out)
    envelope = 0.5 * (1.0 - np.cos(np.pi * t))
    curve = 1.0 - duck_amount * envelope

    return np.clip(curve, 0.5, 1.0).astype(np.float32)


def apply_bass_management(
    source_region: np.ndarray,
    target_region: np.ndarray,
    sr: int,
    bpm: float,
    source_low_energy: float = 0.0,
    target_low_energy: float = 0.0,
    source_mid_energy: float = 0.0,
    target_mid_energy: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply full bass/EQ management to a transition region.

    Separates low and mid frequencies, applies ducking curves,
    and recombines. Returns managed (source, target) regions.

    This is the high-level function that transition code should call.

    Args:
        source_region: Source audio in the overlap region (1D).
        target_region: Target audio in the overlap region (1D).
        sr: Sample rate.
        bpm: BPM for beat alignment.
        source_low_energy: Source's low frequency energy (0-1).
        target_low_energy: Target's low frequency energy (0-1).
        source_mid_energy: Source's mid frequency energy (0-1).
        target_mid_energy: Target's mid frequency energy (0-1).

    Returns:
        (managed_source, managed_target) — same shapes as input.
    """
    from scipy import signal as scipy_signal

    n = len(source_region)
    nyq = sr / 2.0

    # Skip if no meaningful bass energy to manage
    has_bass_risk = (
        source_low_energy > 0.15 or target_low_energy > 0.15
        or source_mid_energy > 0.25 or target_mid_energy > 0.25
    )
    if not has_bass_risk:
        return source_region.copy(), target_region.copy()

    bass_cutoff = min(150.0, nyq * 0.8)
    mid_low = min(300.0, nyq * 0.8)
    mid_high = min(4000.0, nyq * 0.95)

    # Design filters
    try:
        bass_b, bass_a = scipy_signal.butter(3, bass_cutoff / nyq, btype='low')
        mid_b, mid_a = scipy_signal.butter(3, [mid_low / nyq, mid_high / nyq], btype='band')
    except Exception:
        logger.debug("EQ filter design failed, returning unmanaged audio")
        return source_region.copy(), target_region.copy()

    # Extract frequency bands
    try:
        source_bass = scipy_signal.filtfilt(bass_b, bass_a, source_region).astype(np.float32)
        target_bass = scipy_signal.filtfilt(bass_b, bass_a, target_region).astype(np.float32)
        source_mid = scipy_signal.filtfilt(mid_b, mid_a, source_region).astype(np.float32)
        target_mid = scipy_signal.filtfilt(mid_b, mid_a, target_region).astype(np.float32)
    except Exception:
        logger.debug("EQ filtering failed, returning unmanaged audio")
        return source_region.copy(), target_region.copy()

    # Non-bass/mid = highs + residual
    source_high = source_region - source_bass - source_mid
    target_high = target_region - target_bass - target_mid

    # Compute gain curves
    bass_duck_out = compute_bass_duck_curve(n, sr, bpm, "outgoing")
    bass_duck_in = compute_bass_duck_curve(n, sr, bpm, "incoming")
    mid_duck = compute_mid_duck_curve(n, sr, source_mid_energy, target_mid_energy)

    # Apply bass management
    managed_source = (
        source_bass * bass_duck_out
        + source_mid * mid_duck
        + source_high
    ).astype(np.float32)

    managed_target = (
        target_bass * bass_duck_in
        + target_mid  # no mid duck on incoming
        + target_high
    ).astype(np.float32)

    return managed_source, managed_target


def compute_lf_shelf_curve(
    n_samples: int,
    gain_db: float,
    freq: float = 80.0,
) -> np.ndarray:
    """Compute a simple LF shelf gain curve (constant over time).

    Useful for permanently adjusting bass levels during a transition.

    Args:
        n_samples: Number of samples.
        gain_db: Gain in dB (negative = cut, positive = boost).
        freq: Shelf frequency (informational, actual filtering done elsewhere).

    Returns:
        Float32 gain multiplier curve, shape (n_samples,).
    """
    linear_gain = 10.0 ** (gain_db / 20.0)
    return np.full(n_samples, linear_gain, dtype=np.float32)
