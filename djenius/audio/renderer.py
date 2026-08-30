"""Audio renderer - assembles the final mix from a SetPlan.

The renderer is the final stage: it takes a complete SetPlan and produces
a single continuous audio file.

Timing Semantics (V5.1):
    The planner produces these per-transition fields:

    source_exit_time (float, seconds into source track):
        The moment the outgoing (source) track's solo playback ends and the
        transition crossfade begins.  The source contributes
        source[source_exit_sample .. source_exit_sample + overlap_samples]
        to the transition.

    target_entry_time (float, seconds into target track):
        The moment the incoming (target) track enters the mix.  The target
        contributes target[target_entry_sample .. target_entry_sample + overlap_samples]
        to the transition.

    overlap_duration (float, seconds):
        The musical length of the crossfade region.  Both tracks are mixed
        together for exactly this many samples (clamped to available audio).

    Mix output layout (strict forward cursor, no backtracking):
        1. T_0[0 .. SET_0]                           — first track solo
        2. transition(T_0, T_1) of length OD_0        — crossfade region
        3. T_1[TET_1 + OD_0 .. SET_1]                — middle track solo
        ...
        N. T_f[TET_f + OD_{f-1} .. end]              — final track plays to end
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
from djenius.core.errors import DecodeError
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
    track_stems = {}  # stem audio arrays per track (if available)
    for i, track in enumerate(plan.tracks):
        if progress_callback:
            progress_callback(
                i / max(len(plan.tracks), 1) * 30,
                f"Loading track {i+1}/{len(plan.tracks)}: {track.title}",
            )
        try:
            y, sr = _load_audio(track.filepath, sample_rate)
            track_audio[track.id] = (y, sr)
        except DecodeError:
            # Allow DecodeError to propagate - total failure should abort render
            raise
        except Exception as e:
            # _load_audio wraps all load failures into DecodeError, so reaching
            # here indicates a programming error (e.g. TypeError, KeyError).
            # Abort the render rather than inserting silent audio.
            raise DecodeError(
                f"Unexpected error loading {track.filepath}: {e}"
            ) from e

        # Load stem audio if available
        if track.analysis.stems:
            try:
                from djenius.audio.stems import load_stems
                stems = load_stems(track.filepath, sr=sample_rate)
                if stems:
                    # load_stems returns dict[str, np.ndarray] — already audio arrays
                    track_stems[track.id] = stems
            except Exception as e:
                logger.debug("Could not load stems for %s: %s", track.title, e)

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
    timeline_events = []
    
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
            # First track: play solo up to source_exit_sample where transition begins
            source_exit_sample = int(exit_transition.source_exit_time * sr) if exit_transition else track_duration
            source_exit_sample = min(source_exit_sample, track_duration)
            
            # Add track solo section to mix
            end_sample = min(current_sample + source_exit_sample, total_duration)
            length = end_sample - current_sample
            if length > 0:
                track_stereo = _to_stereo(audio)[:length]
                mix[current_sample:end_sample] += track_stereo
                timeline_events.append({
                    "type": "track",
                    "track_id": track.id,
                    "track_title": track.title,
                    "mix_start_sample": current_sample,
                    "mix_end_sample": end_sample,
                    "source_start_sample": 0,
                    "source_end_sample": length,
                })
            current_sample = end_sample

        else:
            # Subsequent tracks: handle transition
            if incoming_transition and incoming_transition.transition_type:
                overlap_samples = int(incoming_transition.overlap_duration * sr)
                target_entry_sample = int(incoming_transition.target_entry_time * sr)

                # Apply transition
                try:
                    prev_track = plan.tracks[i - 1]
                    prev_audio = track_audio.get(prev_track.id, (np.zeros(1, dtype=np.float32), sr))[0]

                    # Get stem audio for source and target (if available)
                    src_stems_audio = track_stems.get(prev_track.id)
                    tgt_stems_audio = track_stems.get(track.id)

                    transition_audio = apply_transition(
                        source_audio=prev_audio,
                        target_audio=audio,
                        sr=sr,
                        transition_type=incoming_transition.transition_type.value,
                        overlap_samples=overlap_samples,
                        source_exit_sample=int(incoming_transition.source_exit_time * sr),
                        target_entry_sample=target_entry_sample,
                        source_bpm=prev_track.bpm,
                        target_bpm=incoming_transition.target_bpm,
                        source_low_energy=prev_track.analysis.low_energy,
                        source_mid_energy=prev_track.analysis.mid_energy,
                        target_low_energy=track.analysis.low_energy,
                        target_mid_energy=track.analysis.mid_energy,
                        source_stems=src_stems_audio,
                        target_stems=tgt_stems_audio,
                    )

                    # Place transition in mix (strict forward cursor)
                    trans_len = len(transition_audio)
                    trans_start = current_sample
                    trans_end = min(trans_start + trans_len, total_duration)
                    actual_trans_len = trans_end - trans_start

                    if actual_trans_len > 0:
                        trans_stereo = _to_stereo(transition_audio)[:actual_trans_len]
                        mix[trans_start:trans_end] += trans_stereo
                        timeline_events.append({
                            "type": "transition",
                            "from_track_id": prev_track.id,
                            "from_track_title": prev_track.title,
                            "to_track_id": track.id,
                            "to_track_title": track.title,
                            "transition_type": incoming_transition.transition_type.value,
                            "mix_start_sample": trans_start,
                            "mix_end_sample": trans_end,
                            "overlap_duration_sec": incoming_transition.overlap_duration,
                            "confidence": incoming_transition.confidence,
                        })
                        current_sample = trans_end
                        transitions_rendered += 1

                    # Place remaining target audio after transition.
                    # The transition consumed `actual_trans_len` samples from the
                    # target starting at target_entry_sample, so we resume from
                    # target_entry_sample + actual_trans_len.
                    # Clamp both start and end to track bounds.
                    rem_start_sample = min(
                        target_entry_sample + actual_trans_len,
                        track_duration,
                    )
                    rem_end_sample = int(exit_transition.source_exit_time * sr) if exit_transition else track_duration
                    rem_end_sample = min(rem_end_sample, track_duration)
                    
                    if rem_end_sample > rem_start_sample:
                        rem_length = rem_end_sample - rem_start_sample
                        rem_start_in_mix = current_sample
                        rem_end_in_mix = min(rem_start_in_mix + rem_length, total_duration)
                        actual_rem_length = rem_end_in_mix - rem_start_in_mix
                        
                        if actual_rem_length > 0:
                            remaining_audio = audio[rem_start_sample:rem_start_sample + actual_rem_length]
                            remaining_stereo = _to_stereo(remaining_audio)
                            mix[rem_start_in_mix:rem_end_in_mix] += remaining_stereo
                            timeline_events.append({
                                "type": "track",
                                "track_id": track.id,
                                "track_title": track.title,
                                "mix_start_sample": rem_start_in_mix,
                                "mix_end_sample": rem_end_in_mix,
                                "source_start_sample": rem_start_sample,
                                "source_end_sample": rem_start_sample + actual_rem_length,
                            })
                            current_sample = rem_end_in_mix

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
                        timeline_events.append({
                            "type": "track",
                            "track_id": track.id,
                            "track_title": track.title,
                            "mix_start_sample": current_sample,
                            "mix_end_sample": current_sample + remaining_len,
                            "source_start_sample": 0,
                            "source_end_sample": remaining_len,
                        })
                        current_sample += remaining_len
            else:
                # No transition: just append
                remaining_len = min(track_duration, total_duration - current_sample)
                if remaining_len > 0:
                    track_stereo = _to_stereo(audio)[:remaining_len]
                    mix[current_sample:current_sample + remaining_len] += track_stereo
                    timeline_events.append({
                        "type": "track",
                        "track_id": track.id,
                        "track_title": track.title,
                        "mix_start_sample": current_sample,
                        "mix_end_sample": current_sample + remaining_len,
                        "source_start_sample": 0,
                        "source_end_sample": remaining_len,
                    })
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

    # Write timeline diagnostics JSON
    diagnostics_path = Path(output_path).with_name(Path(output_path).stem + "_diagnostics.json")
    try:
        import json
        # Convert sample counts to seconds for readability
        timeline_events_with_sec = []
        for event in timeline_events:
            event_with_sec = event.copy()
            if "mix_start_sample" in event:
                event_with_sec["mix_start_sec"] = round(event["mix_start_sample"] / sr, 3)
                event_with_sec["mix_end_sec"] = round(event["mix_end_sample"] / sr, 3)
            if "source_start_sample" in event:
                event_with_sec["source_start_sec"] = round(event["source_start_sample"] / sr, 3)
                event_with_sec["source_end_sec"] = round(event["source_end_sample"] / sr, 3)
            timeline_events_with_sec.append(event_with_sec)
        
        with open(diagnostics_path, "w") as f:
            json.dump({
                "output_path": output_path,
                "sample_rate": sr,
                "total_samples": len(mix),
                "total_duration_sec": round(duration_sec, 3),
                "events": timeline_events_with_sec,
            }, f, indent=2)
        logger.info("Timeline diagnostics written to %s", diagnostics_path)
    except Exception as e:
        logger.warning("Failed to write timeline diagnostics: %s", e)

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
        "timeline_diagnostics_path": str(diagnostics_path),
        "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 1),
    }

    logger.info("Mix rendered: %s (%.1fs, %.1f dB peak)", output_path, duration_sec, peak_db)

    return result


def _load_audio(filepath: str, target_sr: int = 44100) -> tuple[np.ndarray, int]:
    """Load an audio file, returning (audio, sample_rate).

    Preserves stereo if present. Tries soundfile first, falls back to ffmpeg.
    Raises DecodeError if all methods fail.
    """
    try:
        y, sr = sf.read(filepath, dtype="float32")
        if y.ndim == 1:
            y = y.reshape(-1, 1)
        # Resample if needed - preserve channels
        if sr != target_sr:
            import librosa
            if y.ndim == 2:
                # Resample each channel separately
                channels = []
                for ch in range(y.shape[1]):
                    channels.append(librosa.resample(y[:, ch], orig_sr=sr, target_sr=target_sr))
                y = np.column_stack(channels)
            else:
                y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
                y = y.reshape(-1, 1)
            sr = target_sr
        # Return stereo if 2+ channels, else mono
        if y.shape[1] >= 2:
            return y[:, :2], sr  # Take first 2 channels
        elif y.shape[1] == 1:
            return y[:, 0], sr  # Return 1D mono
        return y, sr
    except Exception as sf_err:
        logger.debug("soundfile failed for %s: %s. Falling back to ffmpeg.", filepath, sf_err)
        try:
            # FFmpeg fallback: decode to raw PCM float32 via subprocess
            cmd = [
                "ffmpeg", "-v", "error", "-y",
                "-i", filepath,
                "-f", "f32le",
                "-acodec", "pcm_f32le",
                "-ac", "2",
                "-ar", str(target_sr),
                "pipe:1",
            ]
            result = subprocess.run(cmd, capture_output=True, check=True)
            audio_data = np.frombuffer(result.stdout, dtype=np.float32)
            if len(audio_data) == 0:
                raise ValueError("FFmpeg returned empty audio data")
            # Interleaved stereo: reshape to (N, 2)
            y = audio_data.reshape(-1, 2)
            return y, target_sr
        except Exception as ffmpeg_err:
            raise DecodeError(
                f"Total audio load failure for {filepath}. "
                f"soundfile: {sf_err}, ffmpeg: {ffmpeg_err}"
            ) from ffmpeg_err


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
