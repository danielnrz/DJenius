"""Transition DSP implementations.

Each transition function takes audio arrays and parameters, returning
the mixed result for the transition region.
"""

from __future__ import annotations

import logging

import numpy as np

from djenius.utils.audio_math import (
    equal_power_crossfade,
    linear_fade_in,
    linear_fade_out,
    db_to_linear,
)

logger = logging.getLogger(__name__)


def apply_transition(
    source_audio: np.ndarray,
    target_audio: np.ndarray,
    sr: int,
    transition_type: str,
    overlap_samples: int,
    source_exit_sample: int,
    target_entry_sample: int,
    target_bpm: float = 0.0,
    source_bpm: float = 0.0,
) -> np.ndarray:
    """Apply a transition between source and target audio.

    All operations happen on the overlap region. Outside the overlap,
    source and target play normally. Stereo is preserved end-to-end.

    Args:
        source_audio: Full source track audio (1D or 2D [samples, channels]).
        target_audio: Full target track audio (1D or 2D [samples, channels]).
        sr: Sample rate.
        transition_type: String matching TransitionType values.
        overlap_samples: Number of samples where both tracks overlap.
        source_exit_sample: Sample in source where transition starts.
        target_entry_sample: Sample in target where it starts playing.
        target_bpm: Target BPM for beatmatching (0 = don't stretch).
        source_bpm: Source BPM.

    Returns:
        Audio of the overlap region (source tail + target head mixed).
        Preserves channel count from input.
    """
    is_stereo = source_audio.ndim == 2 and source_audio.shape[1] >= 2
    n_channels = source_audio.shape[1] if is_stereo else 1

    # Process per-channel for stereo, keeping both channels intact
    if is_stereo:
        channel_results = []
        for ch in range(n_channels):
            ch_result = _apply_transition_mono(
                source_audio[:, ch],
                target_audio[:, ch] if target_audio.ndim == 2 else target_audio,
                sr, transition_type, overlap_samples,
                source_exit_sample, target_entry_sample,
                target_bpm, source_bpm,
            )
            channel_results.append(ch_result)
        return np.column_stack(channel_results).astype(np.float32)
    else:
        return _apply_transition_mono(
            source_audio.flatten(),
            target_audio.flatten(),
            sr, transition_type, overlap_samples,
            source_exit_sample, target_entry_sample,
            target_bpm, source_bpm,
        ).astype(np.float32)


def _apply_transition_mono(
    source_mono: np.ndarray,
    target_mono: np.ndarray,
    sr: int,
    transition_type: str,
    overlap_samples: int,
    source_exit_sample: int,
    target_entry_sample: int,
    target_bpm: float = 0.0,
    source_bpm: float = 0.0,
) -> np.ndarray:
    """Apply a transition on a single channel."""
    # Extract the relevant regions
    source_end = min(source_exit_sample + overlap_samples, len(source_mono))
    source_region = source_mono[source_exit_sample:source_end]

    target_start = max(0, target_entry_sample - overlap_samples // 2)
    target_end = min(target_start + overlap_samples, len(target_mono))
    target_region = target_mono[target_start:target_end]

    # Match lengths
    min_len = min(len(source_region), len(target_region))
    if min_len == 0:
        return np.zeros(overlap_samples, dtype=np.float32)

    source_region = source_region[:min_len]
    target_region = target_region[:min_len]

    # Apply the specific transition type
    if transition_type == "phrase_cut":
        result = _phrase_cut(source_region, target_region)
    elif transition_type == "crossfade":
        result = _crossfade(source_region, target_region)
    elif transition_type == "beatmatched_blend":
        result = _beatmatched_blend(source_region, target_region)
    elif transition_type == "bass_swap":
        result = _bass_swap(source_region, target_region, sr)
    elif transition_type == "filter_sweep":
        result = _filter_sweep(source_region, target_region, sr)
    elif transition_type == "echo_out":
        result = _echo_out(source_region, target_region, sr)
    elif transition_type == "loop_blend":
        result = _loop_blend(source_region, target_region)
    else:
        result = _crossfade(source_region, target_region)

    return result.astype(np.float32)


def _phrase_cut(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Clean cut at a phrase boundary.

    Very brief crossfade (just a few samples) to avoid clicks.
    """
    n = len(source)
    click_guard = min(256, n // 4)  # ~6ms at 44100

    result = np.zeros(n, dtype=np.float32)

    # Source plays up to the cut point
    cut_point = n - click_guard
    result[:cut_point] = source[:cut_point]

    # Short crossfade for click prevention
    fade_out = linear_fade_out(click_guard * 2)
    fade_in = linear_fade_in(click_guard * 2)

    region = min(click_guard * 2, n)
    result[:region] = (
        source[:region] * fade_out[:region]
        + target[:region] * fade_in[:region]
    )

    # Target plays after
    result[region:] = target[region:]

    return result


def _crossfade(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Equal-power crossfade."""
    n = len(source)
    fade_out, fade_in = equal_power_crossfade(n)

    return (source * fade_out + target * fade_in).astype(np.float32)


def _beatmatched_blend(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Beatmatched blend using equal-power crossfade.

    In a full implementation, this would also align downbeats.
    For V1, we do the crossfade assuming the planner has aligned the regions.
    """
    n = len(source)
    fade_out, fade_in = equal_power_crossfade(n)

    return (source * fade_out + target * fade_in).astype(np.float32)


def _bass_swap(source: np.ndarray, target: np.ndarray, sr: int) -> np.ndarray:
    """Swap bass frequencies during the transition.

    The outgoing track loses its bass while the incoming track's bass fades in.
    This prevents two kick drums and bass lines from clashing.
    """
    from scipy import signal as scipy_signal

    n = len(source)
    bass_cutoff = 150.0  # Hz
    nyq = sr / 2.0

    if bass_cutoff >= nyq:
        return _crossfade(source, target)

    # Design low-pass filter
    try:
        b, a = scipy_signal.butter(4, bass_cutoff / nyq, btype='low')
    except Exception:
        return _crossfade(source, target)

    # Extract bass components
    source_bass = scipy_signal.filtfilt(b, a, source).astype(np.float32)
    target_bass = scipy_signal.filtfilt(b, a, target).astype(np.float32)

    # Non-bass components
    source_no_bass = source - source_bass
    target_no_bass = target - target_bass

    # Crossfade curves
    fade_out, fade_in = equal_power_crossfade(n)

    # Swap: source non-bass fades out, target non-bass fades in
    # Bass: source bass fades out quickly, target bass fades in
    mid_point = n // 2

    # Bass swap: hard swap at midpoint with click guard
    bass_fade = np.zeros(n, dtype=np.float32)
    bass_fade[:mid_point] = 1.0
    bass_fade[mid_point:mid_point + 512] = np.linspace(1.0, 0.0, min(512, n - mid_point))
    bass_fade[mid_point + 512:] = 0.0

    bass_fade_in = 1.0 - bass_fade

    # Mix
    result = (
        source_no_bass * fade_out
        + target_no_bass * fade_in
        + source_bass * bass_fade
        + target_bass * bass_fade_in
    )

    return result.astype(np.float32)


def _filter_sweep(source: np.ndarray, target: np.ndarray, sr: int) -> np.ndarray:
    """Filter sweep transition.

    High-pass sweep on outgoing track while bringing in the incoming track.
    """
    from scipy import signal as scipy_signal

    n = len(source)
    nyq = sr / 2.0

    fade_out, fade_in = equal_power_crossfade(n)

    # Create a time-varying high-pass for the source
    # Sweep from low to high cutoff over the transition
    result = np.zeros(n, dtype=np.float32)

    # For simplicity, do a stepped sweep
    n_steps = 8
    step_size = n // n_steps

    for i in range(n_steps):
        start = i * step_size
        end = min((i + 1) * step_size, n)
        if end <= start:
            continue

        # Progress through sweep
        progress = (i + 0.5) / n_steps

        # Cutoff frequency sweeps from 100Hz to 3000Hz
        cutoff = 100 * (3000 / 100) ** progress
        cutoff = min(cutoff, nyq * 0.9)

        try:
            b, a = scipy_signal.butter(2, cutoff / nyq, btype='high')
            source_filtered = scipy_signal.filtfilt(b, a, source[start:end])
        except Exception:
            source_filtered = source[start:end]

        result[start:end] = source_filtered * fade_out[start:end]

    # Add target
    result += target * fade_in

    return result.astype(np.float32)


def _echo_out(source: np.ndarray, target: np.ndarray, sr: int) -> np.ndarray:
    """Echo/delay tail on the outgoing track.

    Creates a musical echo effect on the source while fading in the target.
    """
    n = len(source)
    fade_out, fade_in = equal_power_crossfade(n)

    # Create echo effect
    delay_ms = int(60000 / 120)  # One beat at ~120 BPM (placeholder)
    delay_samples = int(sr * delay_ms / 1000)

    echo = np.zeros(n, dtype=np.float32)

    # Add multiple echo taps with decay
    decay = 0.5
    for tap in range(4):
        offset = delay_samples * tap
        gain = decay ** tap
        if offset >= n:
            break
        echo[offset:] += source[:n - offset] * gain * fade_out[offset:] / max(gain, 0.1)

    # Apply additional decay envelope to echo
    echo_envelope = np.exp(-np.linspace(0, 3, n)).astype(np.float32)
    echo *= echo_envelope

    # Mix echo tail with incoming target
    result = echo + target * fade_in

    return result.astype(np.float32)


def _loop_blend(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Loop-based blend.

    Loops a clean section of the source while bringing in the target.
    For V1, we approximate by extending the source region with a loop.
    """
    n = len(source)

    # Simple approach: use the first half as a loop point
    loop_len = min(n // 2, len(source) // 2)
    if loop_len < 1024:
        return _crossfade(source, target)

    # Create a looped version of the source
    looped = np.zeros(n, dtype=np.float32)
    for i in range(0, n, loop_len):
        end = min(i + loop_len, n)
        loop_len_actual = end - i
        looped[i:end] = source[:loop_len_actual]

    # Crossfade between looped source and target
    fade_out, fade_in = equal_power_crossfade(n)
    return (looped * fade_out + target * fade_in).astype(np.float32)
