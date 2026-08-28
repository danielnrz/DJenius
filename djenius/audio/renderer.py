"""Audio renderer - assembles the final mix from a SetPlan.

The renderer is the final stage: it takes a complete SetPlan and produces
a single continuous audio file.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from djenius.core.models import SetPlan, TransitionPlan, TrackProfile, TransitionType
from djenius.audio.transitions import apply_transition
from djenius.utils.audio_math import normalize_lufs, soft_clip, db_to_linear

logger = logging.getLogger(__name__)


def render_mix(
    plan: SetPlan,
    output_path: str,
    output_format: str = "wav",
    target_lufs: float = -14.0,
    sample_rate: int = 44100,
    use_time_stretch: bool = True,
    progress_callback=None,
) -> dict:
    """Render a complete DJ set to an audio file.

    Args:
        plan: The SetPlan with ordered tracks and transition plans.
        output_path: Where to write the output file.
        output_format: "wav" or "mp3".
        target_lufs: Target loudness in LUFS.
        sample_rate: Output sample rate.
        use_time_stretch: Whether to apply time-stretching.
        progress_callback: Optional function(percent, message) called during rendering.

    Returns:
        Dict with render statistics and diagnostics.
    """
    t0 = time.time()

    if not plan.tracks:
        raise ValueError("Set plan has no tracks")

    if progress_callback:
        progress_callback(0, "Starting render...")

    # Load all tracks
    logger.info("Loading %d tracks...", len(plan.tracks))
    track_audio = {}
    for i, track in enumerate(plan.tracks):
        if progress_callback:
            progress_callback(
                i / max(len(plan.tracks), 1) * 30,
                f"Loading track {i+1}/{len(plan.tracks)}: {track.title}",
            )
        try:
            y, sr = _load_audio(track.filepath, sample_rate)
            track_audio[track.id] = (y, sr)
        except Exception as e:
            logger.error("Failed to load %s: %s", track.filepath, e)
            # Create silence as placeholder
            duration_samples = int(track.duration_sec * sample_rate)
            track_audio[track.id] = (np.zeros(duration_samples, dtype=np.float32), sample_rate)

    if progress_callback:
        progress_callback(30, "Assembling mix...")

    # Calculate total duration needed
    total_duration = _estimate_total_duration(plan, track_audio, sample_rate)

    # Initialize output buffer (stereo)
    mix = np.zeros((total_duration, 2), dtype=np.float32)
    current_sample = 0

    diagnostics = []
    transitions_rendered = 0

    # Render each track with transitions
    for i, track in enumerate(plan.tracks):
        if track.id not in track_audio:
            continue

        audio, sr = track_audio[track.id]
        track_duration = len(audio)

        # Get transition plan for this track (if any)
        # transitions[i] = transition from track i to track i+1
        exit_transition = None
        if i < len(plan.transitions):
            exit_transition = plan.transitions[i]
        incoming_transition = None
        if i > 0 and i - 1 < len(plan.transitions):
            incoming_transition = plan.transitions[i - 1]

        if i == 0:
            # First track: play from start
            overlap_start = 0
            if exit_transition:
                # Calculate exit point in samples
                exit_sample = int(exit_transition.source_exit_time * sr)
                overlap_start = min(exit_sample, track_duration)
            else:
                overlap_start = track_duration

            # Add track to mix
            end_sample = min(current_sample + overlap_start, total_duration)
            length = end_sample - current_sample
            if length > 0:
                track_stereo = _to_stereo(audio)[:length]
                mix[current_sample:end_sample] += track_stereo
            current_sample = end_sample

        else:
            # Subsequent tracks: handle transition
            if incoming_transition and incoming_transition.transition_type:
                overlap_samples = int(incoming_transition.overlap_duration * sr)
                target_entry = int(incoming_transition.target_entry_time * sr)

                # Apply transition
                try:
                    prev_track = plan.tracks[i - 1]
                    prev_audio = track_audio.get(prev_track.id, (np.zeros(1, dtype=np.float32), sr))[0]

                    transition_audio = apply_transition(
                        source_audio=prev_audio,
                        target_audio=audio,
                        sr=sr,
                        transition_type=incoming_transition.transition_type.value,
                        overlap_samples=overlap_samples,
                        source_exit_sample=int(incoming_transition.source_exit_time * sr),
                        target_entry_sample=target_entry,
                        source_bpm=prev_track.bpm,
                        target_bpm=incoming_transition.target_bpm,
                    )

                    # Place transition in mix
                    trans_start = max(0, current_sample - overlap_samples // 2)
                    trans_end = min(trans_start + len(transition_audio), total_duration)
                    trans_len = trans_end - trans_start

                    if trans_len > 0:
                        trans_stereo = _to_stereo(transition_audio)[:trans_len]
                        mix[trans_start:trans_end] += trans_stereo
                        current_sample = trans_end
                        transitions_rendered += 1

                    # Place remaining target audio after transition
                    target_start_in_track = target_entry + overlap_samples // 2
                    remaining_start = current_sample
                    remaining_from_track = target_start_in_track
                    remaining_len = min(
                        track_duration - remaining_from_track,
                        total_duration - remaining_start,
                    )
                    if remaining_len > 0:
                        remaining_audio = audio[remaining_from_track:remaining_from_track + remaining_len]
                        remaining_stereo = _to_stereo(remaining_audio)
                        mix[remaining_start:remaining_start + remaining_len] += remaining_stereo
                        current_sample = remaining_start + remaining_len

                    diagnostics.append({
                        "from": prev_track.title,
                        "to": track.title,
                        "type": incoming_transition.transition_type.value,
                        "overlap_sec": incoming_transition.overlap_duration,
                        "confidence": incoming_transition.confidence,
                    })

                except Exception as e:
                    logger.warning("Transition failed, using cut: %s", e)
                    # Fallback: clean cut
                    remaining_len = min(track_duration, total_duration - current_sample)
                    if remaining_len > 0:
                        track_stereo = _to_stereo(audio)[:remaining_len]
                        mix[current_sample:current_sample + remaining_len] += track_stereo
                        current_sample += remaining_len
            else:
                # No transition: just append
                remaining_len = min(track_duration, total_duration - current_sample)
                if remaining_len > 0:
                    track_stereo = _to_stereo(audio)[:remaining_len]
                    mix[current_sample:current_sample + remaining_len] += track_stereo
                    current_sample += remaining_len

        if progress_callback:
            progress = 30 + (i / max(len(plan.tracks), 1)) * 60
            progress_callback(progress, f"Rendering track {i+1}/{len(plan.tracks)}")

    # Trim mix to actual content
    actual_end = min(current_sample, total_duration)
    mix = mix[:actual_end]

    if progress_callback:
        progress_callback(90, "Mastering...")

    # Mastering
    logger.info("Applying mastering...")

    # Convert to mono for LUFS measurement
    mix_mono = mix.mean(axis=1).astype(np.float32)

    # Normalize to target LUFS
    try:
        mix_stereo = normalize_lufs(mix, sr, target_lufs)
        if mix_stereo.ndim == 1:
            mix_stereo = _to_stereo(mix_stereo)
        mix = mix_stereo
    except Exception as e:
        logger.warning("LUFS normalization failed: %s, using peak normalization", e)
        peak = np.max(np.abs(mix))
        if peak > 0:
            target_peak = db_to_linear(-1.0)
            mix = mix * (target_peak / peak)

    # Soft clip to prevent digital distortion
    mix = soft_clip(mix, threshold_db=-1.0)

    # Final peak check
    peak_db = 20 * np.log10(np.max(np.abs(mix)) + 1e-10)

    if progress_callback:
        progress_callback(95, f"Writing output ({output_format})...")

    # Write output
    output_path = str(Path(output_path).absolute())
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if output_format.lower() == "mp3":
        # Write WAV first, then convert
        wav_path = output_path.rsplit(".", 1)[0] + ".wav"
        sf.write(wav_path, mix, sr, subtype="FLOAT")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-b:a", "320k", output_path],
                capture_output=True, check=True,
            )
            os.remove(wav_path)
        except Exception as e:
            logger.warning("MP3 conversion failed: %s, keeping WAV", e)
            if wav_path != output_path:
                os.rename(wav_path, output_path)
    else:
        sf.write(output_path, mix, sr, subtype="PCM_24")

    elapsed = time.time() - t0

    if progress_callback:
        progress_callback(100, f"Done in {elapsed:.1f}s")

    # Compute final stats
    duration_sec = len(mix) / sr
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        final_lufs = meter.integrated_loudness(mix)
    except Exception:
        final_lufs = -999.0

    result = {
        "output_path": output_path,
        "duration_sec": round(duration_sec, 1),
        "sample_rate": sr,
        "channels": 2,
        "format": output_format,
        "peak_db": round(peak_db, 1),
        "final_lufs": round(float(final_lufs), 1) if not np.isinf(final_lufs) else None,
        "transitions_rendered": transitions_rendered,
        "render_time_sec": round(elapsed, 1),
        "diagnostics": diagnostics,
        "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 1),
    }

    logger.info("Mix rendered: %s (%.1fs, %.1f dB peak)", output_path, duration_sec, peak_db)

    return result


def _load_audio(filepath: str, target_sr: int = 44100) -> tuple[np.ndarray, int]:
    """Load an audio file, returning (audio, sample_rate).

    Tries soundfile first, falls back to librosa.
    """
    try:
        y, sr = sf.read(filepath, dtype="float32")
        if y.ndim == 1:
            y = y.reshape(-1, 1)
        # Resample if needed
        if sr != target_sr:
            import librosa
            y_mono = y.mean(axis=1) if y.ndim > 1 else y
            y_resampled = librosa.resample(y_mono, orig_sr=sr, target_sr=target_sr)
            y = y_resampled.reshape(-1, 1)
            sr = target_sr
        return y[:, 0] if y.shape[1] == 1 else y, sr
    except Exception:
        import librosa
        y, sr = librosa.load(filepath, sr=target_sr, mono=False)
        if y.ndim == 1:
            y = y.reshape(-1, 1)
        return y, sr


def _to_stereo(audio: np.ndarray) -> np.ndarray:
    """Convert mono or stereo audio to stereo format."""
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=-1)
    elif audio.ndim == 2 and audio.shape[1] == 1:
        return np.concatenate([audio, audio], axis=1)
    elif audio.ndim == 2 and audio.shape[1] >= 2:
        return audio[:, :2]
    return audio.reshape(-1, 2)


def _estimate_total_duration(
    plan: SetPlan,
    track_audio: dict,
    sr: int,
) -> int:
    """Estimate total duration in samples for the output buffer."""
    total = 0
    for i, track in enumerate(plan.tracks):
        if track.id in track_audio:
            audio, _ = track_audio[track.id]
            total += len(audio)
        else:
            total += int(track.duration_sec * sr)

        # Subtract overlaps from transitions
        if i < len(plan.transitions):
            total -= int(plan.transitions[i].overlap_duration * sr)

    # Add 10% buffer
    return int(total * 1.1) + sr  # +1 second buffer
