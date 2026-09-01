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
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from djenius.core.models import SetPlan, TransitionPlan, TrackProfile, TransitionType
from djenius.core.errors import DecodeError
from djenius.audio.transitions import (
    apply_transition,
    source_consumed_samples,
    target_consumed_samples,
)
from djenius.audio.provenance import audit_source_provenance
from djenius.utils.audio_math import normalize_lufs, soft_clip, db_to_linear
from djenius.utils.timing import seconds_to_samples

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
    track_gain_db = _compute_track_gain_db(plan)
    stem_track_ids = {
        track_id
        for transition in plan.transitions
        if transition.transition_type in (TransitionType.BASS_SWAP, TransitionType.MASHUP)
        for track_id in (transition.source_track_id, transition.target_track_id)
    }
    for i, track in enumerate(plan.tracks):
        if progress_callback:
            progress_callback(
                i / max(len(plan.tracks), 1) * 30,
                f"Loading track {i+1}/{len(plan.tracks)}: {track.title}",
            )
        try:
            y, sr = _load_audio(track.filepath, sample_rate)
            y = y * db_to_linear(track_gain_db[track.id])
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
        if track.id in stem_track_ids and track.analysis.stems:
            try:
                from djenius.audio.stems import load_stems
                stem_dir = "stems"
                if track.analysis.stems:
                    stem_dir = str(Path(next(iter(track.analysis.stems.values()))).parent)
                stems = load_stems(track.filepath, sr=sample_rate, stem_dir=stem_dir)
                if stems:
                    gain = db_to_linear(track_gain_db[track.id])
                    stems = {name: audio * gain for name, audio in stems.items()}
                    # load_stems returns dict[str, np.ndarray] — already audio arrays
                    track_stems[track.id] = stems
            except Exception as e:
                logger.debug("Could not load stems for %s: %s", track.title, e)

    if progress_callback:
        progress_callback(30, "Assembling mix...")

    transition_specs = _validate_render_plan(
        plan, track_audio, sample_rate, use_time_stretch,
    )

    # Calculate total duration needed
    total_duration = _estimate_total_duration(plan, track_audio, sample_rate)

    # Initialize output buffer (stereo)
    mix = np.zeros((total_duration, 2), dtype=np.float32)
    current_sample = 0

    diagnostics = []
    transitions_rendered = 0

    timeline_events = []
    source_cursors = {track.id: 0 for track in plan.tracks}
    landing_gain_states = {}

    for i, spec in enumerate(transition_specs):
        source = plan.tracks[i]
        target = plan.tracks[i + 1]
        transition = plan.transitions[i]
        source_audio = track_audio[source.id][0]
        target_audio = track_audio[target.id][0]

        body_start = source_cursors[source.id]
        body_end = spec["source_start_sample"]
        if body_end > body_start:
            output_end = current_sample + body_end - body_start
            body_audio = source_audio[body_start:body_end]
            body_audio = _apply_landing_gain(
                body_audio,
                body_start,
                landing_gain_states.get(source.id),
            )
            mix[current_sample:output_end] += _to_stereo(body_audio)
            timeline_events.append(_track_event(
                source, body_start, body_end, current_sample, output_end,
                incoming_transition=plan.transitions[i - 1] if i > 0 else None,
                outgoing_transition=transition,
                planned_exit_sample=spec["source_start_sample"],
                track_gain_db=track_gain_db[source.id],
            ))
            current_sample = output_end

        effective_type = transition.transition_type.value
        effective_source_end = (
            spec["source_start_sample"]
            + source_consumed_samples(
                effective_type,
                spec["requested_overlap_samples"],
                sample_rate,
                source.bpm,
            )
        )
        effective_target_end = spec["target_end_sample"]
        try:
            transition_audio = apply_transition(
                source_audio=source_audio,
                target_audio=target_audio,
                sr=sample_rate,
                transition_type=effective_type,
                overlap_samples=spec["requested_overlap_samples"],
                source_exit_sample=spec["source_start_sample"],
                target_entry_sample=spec["target_start_sample"],
                source_bpm=source.bpm,
                target_bpm=target.bpm,
                source_low_energy=transition.context.get(
                    "source_bass", source.analysis.low_energy,
                ),
                source_mid_energy=source.analysis.mid_energy,
                target_low_energy=transition.context.get(
                    "target_bass", target.analysis.low_energy,
                ),
                target_mid_energy=target.analysis.mid_energy,
                source_stems=track_stems.get(source.id),
                target_stems=track_stems.get(target.id),
                use_time_stretch=spec["use_time_stretch"],
                source_gain_db=(transition.recipe.source_gain_db if transition.recipe else 0.0),
                target_gain_db=(transition.recipe.target_gain_db if transition.recipe else 0.0),
                transition_floor_db=(
                    transition.recipe.transition_floor_db if transition.recipe else 4.5
                ),
                max_transition_boost_db=(
                    transition.recipe.max_transition_boost_db if transition.recipe else 6.0
                ),
            )
        except Exception as transition_error:
            logger.warning(
                "%s transition failed for %s -> %s; using source-continuous crossfade: %s",
                effective_type, source.title, target.title, transition_error,
            )
            effective_type = "crossfade"
            effective_source_end = spec["source_end_sample"]
            effective_target_end = (
                spec["target_start_sample"] + spec["requested_overlap_samples"]
            )
            try:
                transition_audio = apply_transition(
                    source_audio=source_audio,
                    target_audio=target_audio,
                    sr=sample_rate,
                    transition_type=effective_type,
                    overlap_samples=spec["requested_overlap_samples"],
                    source_exit_sample=spec["source_start_sample"],
                    target_entry_sample=spec["target_start_sample"],
                    source_bpm=source.bpm,
                    target_bpm=target.bpm,
                    use_time_stretch=False,
                    source_gain_db=(
                        transition.recipe.source_gain_db if transition.recipe else 0.0
                    ),
                    target_gain_db=(
                        transition.recipe.target_gain_db if transition.recipe else 0.0
                    ),
                    transition_floor_db=(
                        transition.recipe.transition_floor_db if transition.recipe else 4.5
                    ),
                    max_transition_boost_db=(
                        transition.recipe.max_transition_boost_db if transition.recipe else 6.0
                    ),
                )
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Transition and safe crossfade both failed for "
                    f"{source.title} -> {target.title}"
                ) from fallback_error

        if len(transition_audio) != spec["requested_overlap_samples"]:
            raise RuntimeError(
                f"Transition {source.title} -> {target.title} produced "
                f"{len(transition_audio)} samples; expected {spec['requested_overlap_samples']}"
            )

        output_start = current_sample
        output_end = output_start + len(transition_audio)
        mix[output_start:output_end] += _to_stereo(transition_audio)
        timeline_events.append({
            "type": "transition",
            "source_track_id": source.id,
            "source_track_title": source.title,
            "target_track_id": target.id,
            "target_track_title": target.title,
            "from_track_id": source.id,
            "from_track_title": source.title,
            "to_track_id": target.id,
            "to_track_title": target.title,
            "transition_type": effective_type,
            "requested_transition_type": transition.transition_type.value,
            "source_start_sample": spec["source_start_sample"],
            "source_end_sample": effective_source_end,
            "target_start_sample": spec["target_start_sample"],
            "target_end_sample": effective_target_end,
            "output_start_sample": output_start,
            "output_end_sample": output_end,
            "mix_start_sample": output_start,
            "mix_end_sample": output_end,
            "requested_overlap_samples": spec["requested_overlap_samples"],
            "actual_overlap_samples": len(transition_audio),
            "overlap_duration_sec": transition.overlap_duration,
            "incoming_transition": None,
            "outgoing_transition": transition.transition_type.value,
            "confidence": transition.confidence,
            "source_reuse": "intentional_loop" if effective_type == "loop_blend" else None,
            "source_track_gain_db": track_gain_db[source.id],
            "target_track_gain_db": track_gain_db[target.id],
            "quality_score": asdict(transition.quality_score) if transition.quality_score else None,
            "recipe": asdict(transition.recipe) if transition.recipe else None,
            **transition.context,
        })
        current_sample = output_end
        source_cursors[source.id] = effective_source_end
        source_cursors[target.id] = effective_target_end
        if transition.recipe and abs(transition.recipe.target_gain_db) > 0.01:
            landing_gain_states[target.id] = {
                "start_sample": effective_target_end,
                "gain_db": transition.recipe.target_gain_db,
                "duration_samples": seconds_to_samples(
                    transition.recipe.landing_gain_decay_sec, sample_rate,
                ),
            }
        transitions_rendered += 1
        diagnostics.append({
            "from": source.title,
            "to": target.title,
            "type": effective_type,
            "requested_type": transition.transition_type.value,
            "overlap_sec": transition.overlap_duration,
            "confidence": transition.confidence,
        })

        if progress_callback:
            progress = 30 + ((i + 1) / max(len(transition_specs), 1)) * 60
            progress_callback(progress, f"Rendering transition {i+1}/{len(transition_specs)}")

    final_track = plan.tracks[-1]
    final_audio = track_audio[final_track.id][0]
    final_start = source_cursors[final_track.id]
    final_end = (
        min(
            len(final_audio),
            seconds_to_samples(plan.final_track_end_time, sample_rate),
        )
        if plan.final_track_end_time is not None else len(final_audio)
    )
    if final_end > final_start:
        output_end = current_sample + final_end - final_start
        final_body = _apply_landing_gain(
            final_audio[final_start:final_end],
            final_start,
            landing_gain_states.get(final_track.id),
        )
        mix[current_sample:output_end] += _to_stereo(final_body)
        timeline_events.append(_track_event(
            final_track, final_start, final_end, current_sample, output_end,
            incoming_transition=plan.transitions[-1] if plan.transitions else None,
            outgoing_transition=None,
            planned_exit_sample=None,
            track_gain_db=track_gain_db[final_track.id],
        ))
        current_sample = output_end

    track_lengths = {track_id: len(audio) for track_id, (audio, _) in track_audio.items()}
    provenance_audit = audit_source_provenance(timeline_events, track_lengths)
    if not provenance_audit["clean"]:
        raise RuntimeError(
            f"Source provenance audit failed before WAV writing: "
            f"{provenance_audit['violations']}"
        )

    # Trim mix to actual content
    actual_end = current_sample
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
                event_with_sec["output_start_sec"] = round(event["output_start_sample"] / sr, 3)
                event_with_sec["output_end_sec"] = round(event["output_end_sample"] / sr, 3)
            if "source_start_sample" in event:
                event_with_sec["source_start_sec"] = round(event["source_start_sample"] / sr, 3)
                event_with_sec["source_end_sec"] = round(event["source_end_sample"] / sr, 3)
            if "target_start_sample" in event:
                event_with_sec["target_start_sec"] = round(event["target_start_sample"] / sr, 3)
                event_with_sec["target_end_sec"] = round(event["target_end_sample"] / sr, 3)
            timeline_events_with_sec.append(event_with_sec)
        
        with open(diagnostics_path, "w") as f:
            json.dump({
                "output_path": output_path,
                "sample_rate": sr,
                "total_samples": len(mix),
                "total_duration_sec": round(duration_sec, 3),
                "events": timeline_events_with_sec,
                "provenance_audit": provenance_audit,
                "track_gain_db": track_gain_db,
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
        "provenance_audit": provenance_audit,
        "track_gain_db": track_gain_db,
        "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 1),
    }

    logger.info("Mix rendered: %s (%.1fs, %.1f dB peak)", output_path, duration_sec, peak_db)

    return result


def _compute_track_gain_db(plan: SetPlan, maximum_correction_db: float = 4.0) -> dict[str, float]:
    """Apply bounded per-track normalization while preserving local dynamics."""
    valid_loudness = [
        track.analysis.integrated_lufs
        for track in plan.tracks
        if -60.0 < track.analysis.integrated_lufs < -1.0
    ]
    if not valid_loudness:
        return {track.id: 0.0 for track in plan.tracks}
    reference = float(np.median(valid_loudness))
    return {
        track.id: round(float(np.clip(
            reference - track.analysis.integrated_lufs,
            -maximum_correction_db,
            maximum_correction_db,
        )), 3)
        if -60.0 < track.analysis.integrated_lufs < -1.0 else 0.0
        for track in plan.tracks
    }


def _apply_landing_gain(
    audio: np.ndarray,
    source_start_sample: int,
    state: Optional[dict],
) -> np.ndarray:
    """Decay a target's bounded transition gain smoothly into its body."""
    if not state or not len(audio) or state["duration_samples"] <= 0:
        return audio
    positions = source_start_sample - state["start_sample"] + np.arange(len(audio))
    progress = np.clip(positions / state["duration_samples"], 0.0, 1.0)
    gain_db = state["gain_db"] * (1.0 - progress)
    gain = np.power(10.0, gain_db / 20.0).astype(np.float32)
    if audio.ndim == 2:
        gain = gain[:, np.newaxis]
    return (audio * gain).astype(np.float32)


def _track_event(
    track: TrackProfile,
    source_start: int,
    source_end: int,
    output_start: int,
    output_end: int,
    *,
    incoming_transition: Optional[TransitionPlan],
    outgoing_transition: Optional[TransitionPlan],
    planned_exit_sample: Optional[int],
    track_gain_db: float,
) -> dict:
    return {
        "type": "track",
        "track_id": track.id,
        "track_title": track.title,
        "source_start_sample": source_start,
        "source_end_sample": source_end,
        "output_start_sample": output_start,
        "output_end_sample": output_end,
        "mix_start_sample": output_start,
        "mix_end_sample": output_end,
        "transition_type": None,
        "requested_overlap_samples": None,
        "actual_overlap_samples": None,
        "incoming_transition": (
            incoming_transition.transition_type.value if incoming_transition else None
        ),
        "outgoing_transition": (
            outgoing_transition.transition_type.value if outgoing_transition else None
        ),
        "planned_source_exit_sample": planned_exit_sample,
        "track_gain_db": track_gain_db,
    }


def _validate_render_plan(
    plan: SetPlan,
    track_audio: dict[str, tuple[np.ndarray, int]],
    sample_rate: int,
    use_time_stretch: bool,
) -> list[dict]:
    """Resolve transition sample intervals and reject unsafe timelines."""
    expected_transitions = max(0, len(plan.tracks) - 1)
    if len(plan.transitions) != expected_transitions:
        raise ValueError(
            f"Set plan has {len(plan.transitions)} transitions for "
            f"{len(plan.tracks)} tracks; expected {expected_transitions}"
        )
    track_ids = [track.id for track in plan.tracks]
    if len(set(track_ids)) != len(track_ids):
        raise ValueError("Set plan contains duplicate track IDs")

    cursors = {track.id: 0 for track in plan.tracks}
    specs = []
    for index, transition in enumerate(plan.transitions):
        source = plan.tracks[index]
        target = plan.tracks[index + 1]
        if (
            transition.source_track_id != source.id
            or transition.target_track_id != target.id
        ):
            raise ValueError(
                f"Transition {index + 1} IDs do not match adjacent plan tracks"
            )

        overlap = seconds_to_samples(transition.overlap_duration, sample_rate)
        source_start = seconds_to_samples(transition.source_exit_time, sample_rate)
        target_start = seconds_to_samples(transition.target_entry_time, sample_rate)
        stretch_enabled = use_time_stretch and transition.requires_stretch
        target_consumed = target_consumed_samples(
            transition.transition_type.value,
            overlap,
            source.bpm,
            target.bpm,
            stretch_enabled,
        )
        source_end = source_start + overlap
        target_end = target_start + target_consumed
        source_length = len(track_audio[source.id][0])
        target_length = len(track_audio[target.id][0])

        if overlap <= 0:
            raise ValueError(f"Transition {index + 1} has no overlap")
        if source_start < cursors[source.id]:
            raise ValueError(
                f"Transition {index + 1} moves {source.title} backwards: "
                f"exit sample {source_start}, cursor {cursors[source.id]}"
            )
        if source_end > source_length:
            raise ValueError(
                f"Transition {index + 1} exceeds source EOF for {source.title}: "
                f"{source_end} > {source_length}"
            )
        if target_start < 0 or target_end > target_length:
            raise ValueError(
                f"Transition {index + 1} exceeds target bounds for {target.title}: "
                f"[{target_start}, {target_end}) vs {target_length} samples"
            )
        if target_start + overlap > target_length:
            raise ValueError(
                f"Transition {index + 1} leaves no safe crossfade fallback in {target.title}"
            )

        specs.append({
            "source_start_sample": source_start,
            "source_end_sample": source_end,
            "target_start_sample": target_start,
            "target_end_sample": target_end,
            "requested_overlap_samples": overlap,
            "use_time_stretch": stretch_enabled,
        })
        cursors[source.id] = source_end
        cursors[target.id] = target_end

    return specs


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
            total += seconds_to_samples(track.duration_sec, sr)

        # Subtract overlaps from transitions
        if i < len(plan.transitions):
            total -= seconds_to_samples(plan.transitions[i].overlap_duration, sr)

    # Add 10% buffer
    return int(total * 1.1) + sr  # +1 second buffer
