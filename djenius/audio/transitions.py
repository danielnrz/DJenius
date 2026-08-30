"""Transition DSP implementations.

Each transition function takes audio arrays and parameters, returning
the mixed result for the transition region.

When stems are available (Phase 14-15), transitions can work directly
on separated source signals for cleaner results:
- bass_swap: swap actual bass stems instead of filtering
- mashup: mix source vocals over target drums/bass/other

Timing Semantics (V5.1):
    The transition operates on two intervals extracted from full-track audio:

    Source interval: source[source_exit_sample : source_exit_sample + overlap_samples]
        The outgoing track's tail during the crossfade.

    Target interval: target[target_entry_sample : target_entry_sample + overlap_samples]
        The incoming track's head during the crossfade.

    Both intervals are clamped to available audio length.  The output is
    exactly min(len(source_region), len(target_region)) samples long.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import soundfile as sf

from djenius.utils.audio_math import (
    equal_power_crossfade,
    linear_fade_in,
    linear_fade_out,
    db_to_linear,
)

# Alias for local use in ffmpeg fallback
sf_write = sf.write
sf_read = sf.read

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
    source_low_energy: float = 0.0,
    source_mid_energy: float = 0.0,
    target_low_energy: float = 0.0,
    target_mid_energy: float = 0.0,
    source_stems: Optional[dict[str, np.ndarray]] = None,
    target_stems: Optional[dict[str, np.ndarray]] = None,
) -> np.ndarray:
    """Apply a transition between source and target audio.

    All operations happen on the overlap region. Outside the overlap,
    source and target play normally. Stereo is preserved end-to-end.
    Bass/EQ management is applied when energy profiles indicate risk.

    When stems are available (Phase 14-15), stem-aware transitions are
    used automatically: bass_swap swaps actual bass stems, mashup mixes
    source vocals over target instrumentation.

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
        source_low_energy: Source low frequency energy (0-1).
        source_mid_energy: Source mid frequency energy (0-1).
        target_low_energy: Target low frequency energy (0-1).
        target_mid_energy: Target mid frequency energy (0-1).
        source_stems: Optional dict of stem arrays for source track.
        target_stems: Optional dict of stem arrays for target track.

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
                source_low_energy, source_mid_energy,
                target_low_energy, target_mid_energy,
                source_stems=source_stems,
                target_stems=target_stems,
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
            source_low_energy, source_mid_energy,
            target_low_energy, target_mid_energy,
            source_stems=source_stems,
            target_stems=target_stems,
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
    source_low_energy: float = 0.0,
    source_mid_energy: float = 0.0,
    target_low_energy: float = 0.0,
    target_mid_energy: float = 0.0,
    source_stems: Optional[dict[str, np.ndarray]] = None,
    target_stems: Optional[dict[str, np.ndarray]] = None,
) -> np.ndarray:
    """Apply a transition on a single channel."""
    # Extract the relevant regions
    source_end = min(source_exit_sample + overlap_samples, len(source_mono))
    source_region = source_mono[source_exit_sample:source_end]

    target_end = min(target_entry_sample + overlap_samples, len(target_mono))
    target_region = target_mono[target_entry_sample:target_end]

    # Match lengths
    min_len = min(len(source_region), len(target_region))
    if min_len == 0:
        return np.zeros(overlap_samples, dtype=np.float32)

    source_region = source_region[:min_len]
    target_region = target_region[:min_len]

    # Apply bass/EQ management for transitions that mix both tracks
    needs_bass_mgmt = transition_type not in ("phrase_cut",)
    if needs_bass_mgmt:
        has_bass_risk = (
            source_low_energy > 0.25 or target_low_energy > 0.25
            or source_mid_energy > 0.35 or target_mid_energy > 0.35
        )
        if has_bass_risk:
            from djenius.audio.eq import apply_bass_management
            bpm_for_eq = source_bpm if source_bpm > 0 else target_bpm
            if bpm_for_eq > 0:
                source_region, target_region = apply_bass_management(
                    source_region, target_region, sr, bpm_for_eq,
                    source_low_energy, target_low_energy,
                    source_mid_energy, target_mid_energy,
                )

    # Apply the specific transition type
    # Helper: convert stereo stem arrays to mono for use in mono processing
    def _stem_mono(stem: np.ndarray) -> np.ndarray:
        if stem.ndim == 2:
            return stem.mean(axis=1).astype(np.float32)
        return stem

    if transition_type == "phrase_cut":
        result = _phrase_cut(source_region, target_region)
    elif transition_type == "crossfade":
        result = _crossfade(source_region, target_region)
    elif transition_type == "beatmatched_blend":
        result = _beatmatched_blend(
            source_region, target_region, sr,
            source_bpm=source_bpm, target_bpm=target_bpm,
        )
    elif transition_type == "bass_swap":
        # Prefer stem-based bass swap when stem data is available
        if (source_stems is not None and target_stems is not None
                and "bass" in source_stems and "bass" in target_stems):
            src_bass = _stem_mono(source_stems["bass"])
            tgt_bass = _stem_mono(target_stems["bass"])
            src_bass_r = src_bass[source_exit_sample:source_exit_sample + min_len] if len(src_bass) > source_exit_sample else source_region
            tgt_bass_r = tgt_bass[target_entry_sample:target_entry_sample + min_len] if len(tgt_bass) > target_entry_sample else target_region
            result = _bass_swap_stems(
                source_region, target_region, sr,
                source_bass=src_bass_r,
                target_bass=tgt_bass_r,
            )
        else:
            result = _bass_swap(source_region, target_region, sr)
    elif transition_type == "filter_sweep":
        result = _filter_sweep(source_region, target_region, sr)
    elif transition_type == "echo_out":
        result = _echo_out(source_region, target_region, sr)
    elif transition_type == "loop_blend":
        result = _loop_blend(source_region, target_region)
    elif transition_type == "mashup":
        # Convert stems to mono for _mashup's mono processing
        mono_source_stems = None
        mono_target_stems = None
        if source_stems is not None:
            mono_source_stems = {k: _stem_mono(v) for k, v in source_stems.items()}
        if target_stems is not None:
            mono_target_stems = {k: _stem_mono(v) for k, v in target_stems.items()}
        result = _mashup(
            source_region, target_region, sr,
            source_stems=mono_source_stems,
            target_stems=mono_target_stems,
            source_exit_sample=source_exit_sample,
            target_entry_sample=target_entry_sample,
        )
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
    """Equal-power crossfade (mono or stereo)."""
    n = len(source)
    fade_out, fade_in = equal_power_crossfade(n)

    # Reshape fade curves for stereo broadcasting
    if source.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    return (source * fade_out + target * fade_in).astype(np.float32)


def _beatmatched_blend(
    source: np.ndarray,
    target: np.ndarray,
    sr: int,
    source_bpm: float = 0.0,
    target_bpm: float = 0.0,
) -> np.ndarray:
    """Beatmatched blend with real time-stretching and beat phase alignment.

    Steps:
    1. If target_bpm != source_bpm and both are valid, time-stretch target
       via pyrubberband, ffmpeg atempo, or scipy resample fallback.
    2. Calculate beat phase shift and align transients.
    3. Apply equal-power crossfade with musical timing (beat-aligned length).

    Falls back to plain crossfade if no time-stretch backend is available.
    """
    n = len(source)

    # ── Step 1: Time-stretch target to match source BPM ───────────────
    stretched_target = target.copy()
    stretch_pct = 0.0

    if source_bpm > 0 and target_bpm > 0 and abs(source_bpm - target_bpm) > 0.5:
        rate = source_bpm / target_bpm
        stretched = None

        # Try pyrubberband first
        try:
            import pyrubberband as pyrb
            stretched = pyrb.time_stretch(target, sr, rate).astype(np.float32)
        except Exception:
            pass

        # Fallback: ffmpeg atempo via temp files
        if stretched is None:
            try:
                import subprocess
                import tempfile
                import os

                fd_in, infile = tempfile.mkstemp(suffix='.wav')
                os.close(fd_in)
                fd_out, outfile = tempfile.mkstemp(suffix='.wav')
                os.close(fd_out)

                sf_write(infile, target, sr)
                cmd = [
                    'ffmpeg', '-y', '-i', infile,
                    '-filter:a', f'atempo={rate}',
                    outfile,
                ]
                subprocess.run(cmd, capture_output=True, check=True, timeout=30)
                stretched, _ = sf_read(outfile)
                os.unlink(infile)
                os.unlink(outfile)
            except Exception:
                pass

        if stretched is not None:
            stretched_target = stretched
            stretch_pct = abs(rate - 1.0) * 100.0

    # Normalize stretched target to source length (trim or pad)
    if len(stretched_target) > n:
        stretched_target = stretched_target[:n]
    elif len(stretched_target) < n:
        if stretched_target.ndim == 2:
            pad = np.zeros((n - len(stretched_target), stretched_target.shape[1]),
                           dtype=np.float32)
        else:
            pad = np.zeros(n - len(stretched_target), dtype=np.float32)
        stretched_target = np.concatenate([stretched_target, pad], axis=0)

    # ── Step 2: Beat phase alignment ──────────────────────────────────
    from djenius.utils.timing import calculate_phase_shift, apply_phase_shift

    phase_shift = calculate_phase_shift(source, stretched_target, sr, bpm=source_bpm)
    aligned_target = apply_phase_shift(stretched_target, phase_shift)

    # ── Step 3: Musical timing crossfade ──────────────────────────────
    from djenius.utils.timing import bpm_to_samples

    if source_bpm > 0:
        beat_samples = bpm_to_samples(source_bpm, sr)
        # Round n down to nearest multiple of beats (at least 1 beat)
        crossfade_len = max(beat_samples, (n // beat_samples) * beat_samples)
        crossfade_len = min(crossfade_len, n)
    else:
        crossfade_len = n

    fade_out, fade_in = equal_power_crossfade(crossfade_len)

    # Reshape fade curves for stereo (samples,) -> (samples, 1) for broadcasting
    if source.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    result = np.zeros_like(source)
    result[:crossfade_len] = (
        source[:crossfade_len] * fade_out
        + aligned_target[:crossfade_len] * fade_in
    )
    # If crossfade is shorter than the overlap region, play target for the rest
    if crossfade_len < n:
        result[crossfade_len:] = aligned_target[crossfade_len:]

    return result.astype(np.float32)


def _bass_swap(source: np.ndarray, target: np.ndarray, sr: int) -> np.ndarray:
    """Swap bass frequencies during the transition.

    The outgoing track loses its bass while the incoming track's bass fades in.
    This prevents two kick drums and bass lines from clashing.

    When stem arrays are available as a dict with keys 'bass', 'drums', 'other',
    this function is bypassed in favour of ``_bass_swap_stems`` which operates on
    the actual separated bass stems for a cleaner result.
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

    # Reshape for stereo broadcasting
    if source.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]
        bass_fade = bass_fade[:, np.newaxis]
        bass_fade_in = bass_fade_in[:, np.newaxis]

    # Mix
    result = (
        source_no_bass * fade_out
        + target_no_bass * fade_in
        + source_bass * bass_fade
        + target_bass * bass_fade_in
    )

    return result.astype(np.float32)


def _bass_swap_stems(
    source: np.ndarray,
    target: np.ndarray,
    sr: int,
    source_bass: np.ndarray,
    target_bass: np.ndarray,
) -> np.ndarray:
    """Bass swap using actual separated bass stems.

    Much cleaner than filter-based bass swap because we're swapping the
    real bass signal rather than trying to isolate it with a low-pass filter.

    Args:
        source: Full source audio (overlap region, mono).
        target: Full target audio (overlap region, mono).
        sr: Sample rate.
        source_bass: Separated bass stem of source (overlap region).
        target_bass: Separated bass stem of target (overlap region).

    Returns:
        Mixed audio with bass swapped.
    """
    n = len(source)

    # Crossfade curves
    fade_out, fade_in = equal_power_crossfade(n)

    # Bass swap: crossfade at midpoint with smooth transition
    mid_point = n // 2

    bass_fade = np.zeros(n, dtype=np.float32)
    bass_fade[:mid_point] = 1.0
    bass_fade[mid_point:mid_point + 512] = np.linspace(1.0, 0.0, min(512, n - mid_point))
    bass_fade[mid_point + 512:] = 0.0

    bass_fade_in = 1.0 - bass_fade

    # Non-bass = full mix minus bass stem
    # Convert stereo bass to mono if needed, then pad/truncate to length n
    def _to_mono_bass(bass: np.ndarray, length: int) -> np.ndarray:
        """Convert bass stem to mono and pad to the target length."""
        mono = bass.mean(axis=1).astype(np.float32) if bass.ndim == 2 else bass.astype(np.float32)
        out = np.zeros(length, dtype=np.float32)
        out[: min(length, len(mono))] = mono[: min(length, len(mono))]
        return out

    sb = _to_mono_bass(source_bass, n)
    tb = _to_mono_bass(target_bass, n)
    source_no_bass = source - sb[:, np.newaxis] if source.ndim == 2 else source - sb
    target_no_bass = target - tb[:, np.newaxis] if target.ndim == 2 else target - tb

    # Reshape for stereo broadcasting
    if source.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]
        bass_fade = bass_fade[:, np.newaxis]
        bass_fade_in = bass_fade_in[:, np.newaxis]

    result = (
        source_no_bass * fade_out
        + target_no_bass * fade_in
        + (sb[:, np.newaxis] * bass_fade if source.ndim == 2 else sb * bass_fade)
        + (tb[:, np.newaxis] * bass_fade_in if source.ndim == 2 else tb * bass_fade_in)
    )

    return result.astype(np.float32)


def _mashup(
    source: np.ndarray,
    target: np.ndarray,
    sr: int,
    source_stems: Optional[dict[str, np.ndarray]] = None,
    target_stems: Optional[dict[str, np.ndarray]] = None,
    source_exit_sample: int = 0,
    target_entry_sample: int = 0,
) -> np.ndarray:
    """Controlled mashup transition using stem separation.

    Mixes source vocals over target instrumentation (drums + bass + other),
    with a smooth crossfade.  When stems are unavailable, falls back to
    a regular crossfade.

    The default mashup configuration is:
      - Source contributes: vocals
      - Target contributes: drums + bass + other

    This creates the classic mashup effect where one track's vocals sit
    cleanly over another track's instrumental.

    Args:
        source: Full source audio (overlap region, mono).
        target: Full target audio (overlap region, mono).
        sr: Sample rate.
        source_stems: Optional dict of stem arrays for source track.
        target_stems: Optional dict of stem arrays for target track.
        source_exit_sample: Sample offset in source where transition starts.
        target_entry_sample: Sample offset in target where transition starts.

    Returns:
        Mixed mashup audio for the overlap region.
    """
    n = len(source)

    if source_stems is None or target_stems is None:
        # No stems available — fall back to crossfade
        return _crossfade(source, target)

    src_vocals = source_stems.get("vocals")
    src_drums = source_stems.get("drums")
    src_bass = source_stems.get("bass")
    src_other = source_stems.get("other")

    tgt_vocals = target_stems.get("vocals")
    tgt_drums = target_stems.get("drums")
    tgt_bass = target_stems.get("bass")
    tgt_other = target_stems.get("other")

    if src_vocals is None or tgt_drums is None:
        # Missing critical stems — fall back to crossfade
        return _crossfade(source, target)

    # Extract overlap regions from each stem
    def _extract(stem: np.ndarray, exit_sample: int, length: int) -> np.ndarray:
        """Extract a region from a stem, handling shape mismatches."""
        if stem.ndim == 2:
            stem = stem.mean(axis=1)
        start = exit_sample
        end = min(start + length, len(stem))
        region = stem[start:end]
        if len(region) < length:
            pad = np.zeros(length - len(region), dtype=np.float32)
            region = np.concatenate([region, pad])
        return region[:length].astype(np.float32)

    src_vocals_r = _extract(src_vocals, source_exit_sample, n)
    tgt_vocals_r = _extract(tgt_vocals, target_entry_sample, n)

    # Build target instrumentation
    tgt_inst = np.zeros(n, dtype=np.float32)
    for stem in (tgt_drums, tgt_bass, tgt_other):
        if stem is not None:
            tgt_inst += _extract(stem, target_entry_sample, n)

    # Build source instrumentation (for fallback)
    src_inst = np.zeros(n, dtype=np.float32)
    for stem in (src_drums, src_bass, src_other):
        if stem is not None:
            src_inst += _extract(stem, source_exit_sample, n)

    # Crossfade curves for smooth transitions (always 1D — stems are mono)
    fade_out, fade_in = equal_power_crossfade(n)

    # Mashup mix: source vocals + target instrumentation
    # Fade source vocals in, target instrumentation stays
    # Also fade in target vocals at the end for continuity
    vocal_fade_in = np.linspace(0.0, 1.0, n, dtype=np.float32)
    vocal_fade_out = 1.0 - vocal_fade_in

    # Build the mashup:
    # - Source instrumentation fades out
    # - Source vocals fade out (they're strongest at start, transition away)
    # - Target instrumentation fades in
    # - Target vocals fade in at end (for continuity into the target track)
    result = (
        src_inst * fade_out            # source instrumental fades out
        + src_vocals_r * vocal_fade_out  # source vocals fade out
        + tgt_inst * fade_in           # target instrumental fades in
        + tgt_vocals_r * vocal_fade_in # target vocals fade in at end
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

    # Reshape for stereo broadcasting
    if source.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    # Create a time-varying high-pass for the source
    # Sweep from low to high cutoff over the transition
    result = np.zeros_like(source)

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

    # Reshape for stereo broadcasting
    if source.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    # Create echo effect
    delay_ms = int(60000 / 120)  # One beat at ~120 BPM (placeholder)
    delay_samples = int(sr * delay_ms / 1000)

    echo = np.zeros_like(source)

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
    if source.ndim == 2:
        echo_envelope = echo_envelope[:, np.newaxis]
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
    looped = np.zeros_like(source)
    for i in range(0, n, loop_len):
        end = min(i + loop_len, n)
        loop_len_actual = end - i
        looped[i:end] = source[:loop_len_actual]

    # Crossfade between looped source and target
    fade_out, fade_in = equal_power_crossfade(n)

    # Reshape for stereo broadcasting
    if source.ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]

    return (looped * fade_out + target * fade_in).astype(np.float32)
