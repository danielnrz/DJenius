"""Transition diagnostics — audition WAV + JSON for each transition.

Generates WAV previews of each transition type with synthetic test signals,
along with JSON metadata describing the transition parameters and results.
Also provides V4 set-level diagnostics with phrase, vocal, and energy info.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from djenius.audio.transitions import (
    _crossfade,
    _beatmatched_blend,
    _bass_swap,
    _filter_sweep,
    _echo_out,
)

logger = logging.getLogger(__name__)

SR = 44100


def _make_synth_signal(
    duration_sec: float = 4.0,
    freq_hz: float = 440.0,
    sr: int = SR,
    stereo: bool = False,
) -> np.ndarray:
    """Generate a synthetic test signal for transition auditioning."""
    n = int(sr * duration_sec)
    t = np.linspace(0, duration_sec, n, endpoint=False, dtype=np.float32)
    audio = 0.8 * np.sin(2 * np.pi * freq_hz * t)
    # Add harmonic content
    audio += 0.3 * np.sin(2 * np.pi * freq_hz * 2 * t)
    audio += 0.15 * np.sin(2 * np.pi * freq_hz * 3 * t)
    audio = audio.astype(np.float32)

    if stereo:
        # Slightly different frequencies for left/right
        left = audio
        right = 0.8 * np.sin(2 * np.pi * freq_hz * 1.005 * t).astype(np.float32)
        right += 0.3 * np.sin(2 * np.pi * freq_hz * 2 * 1.003 * t).astype(np.float32)
        return np.column_stack([left, right])
    return audio


def _make_click_track(
    bpm: float = 120.0,
    duration_sec: float = 4.0,
    sr: int = SR,
) -> np.ndarray:
    """Generate a click track for beat alignment testing."""
    n = int(sr * duration_sec)
    audio = np.zeros(n, dtype=np.float32)
    samples_per_beat = int(sr * 60.0 / bpm)
    click_len = min(256, samples_per_beat // 4)
    for i in range(0, n, samples_per_beat):
        end = min(i + click_len, n)
        t = np.linspace(0, click_len / sr, click_len, endpoint=False, dtype=np.float32)
        click = 0.8 * np.sin(2 * np.pi * 1000 * t)
        click *= np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
        audio[i:end] = click[: end - i]
    return audio


def generate_transition_auditions(
    output_dir: str,
    stereo: bool = True,
    sr: int = SR,
) -> dict:
    """Generate audition WAV files and JSON diagnostics for all transition types.

    Creates:
    - <type>_mono.wav and <type>_stereo.wav for each transition type
    - transition_diagnostics.json with metadata

    Args:
        output_dir: Directory to write audition files.
        stereo: Whether to generate stereo auditions.
        sr: Sample rate.

    Returns:
        Dict with file paths and diagnostic info.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    overlap_sec = 2.0
    overlap_samples = int(overlap_sec * sr)

    # Generate test signals
    mono_a = _make_synth_signal(4.0, 440.0, sr, stereo=False)
    mono_b = _make_synth_signal(4.0, 523.25, sr, stereo=False)  # C5

    click_a_120 = _make_click_track(120.0, 6.0, sr)
    click_b_128 = _make_click_track(128.0, 6.0, sr)

    if stereo:
        stereo_a = _make_synth_signal(4.0, 440.0, sr, stereo=True)
        stereo_b = _make_synth_signal(4.0, 523.25, sr, stereo=True)

    diagnostics = []
    files_written = []

    # ── Crossfade ──────────────────────────────────────────────────────
    mid_mono = len(mono_a) // 2
    src_mono = mono_a[mid_mono - overlap_samples:mid_mono]
    tgt_mono = mono_b[mid_mono:mid_mono + overlap_samples]
    result_mono = _crossfade(src_mono, tgt_mono)
    wav_path = output_path / "crossfade_mono.wav"
    sf.write(str(wav_path), result_mono, sr)
    files_written.append(str(wav_path))

    diag = {
        "type": "crossfade",
        "file": str(wav_path),
        "overlap_samples": overlap_samples,
        "overlap_sec": overlap_sec,
        "source_freq_hz": 440.0,
        "target_freq_hz": 523.25,
        "channels": 1,
        "output_samples": len(result_mono),
        "rms_energy": round(float(np.sqrt(np.mean(result_mono ** 2))), 4),
        "peak_db": round(float(20 * np.log10(np.max(np.abs(result_mono)) + 1e-10)), 1),
    }
    diagnostics.append(diag)

    if stereo:
        mid_st = len(stereo_a) // 2
        src_st = stereo_a[mid_st - overlap_samples:mid_st]
        tgt_st = stereo_b[mid_st:mid_st + overlap_samples]
        result_st = _crossfade(src_st, tgt_st)
        wav_path = output_path / "crossfade_stereo.wav"
        sf.write(str(wav_path), result_st, sr)
        files_written.append(str(wav_path))

    # ── Beatmatched blend ──────────────────────────────────────────────
    n = min(len(click_a_120), len(click_b_128)) // 3
    src_beat = click_a_120[:n]
    tgt_beat = click_b_128[:n]
    result_beat = _beatmatched_blend(src_beat, tgt_beat, sr, source_bpm=120.0, target_bpm=128.0)
    wav_path = output_path / "beatmatched_blend_mono.wav"
    sf.write(str(wav_path), result_beat, sr)
    files_written.append(str(wav_path))

    diag = {
        "type": "beatmatched_blend",
        "file": str(wav_path),
        "source_bpm": 120.0,
        "target_bpm": 128.0,
        "stretch_rate": round(128.0 / 120.0, 4),
        "stretch_pct": round(abs(128.0 / 120.0 - 1.0) * 100, 1),
        "channels": 1,
        "output_samples": len(result_beat),
        "rms_energy": round(float(np.sqrt(np.mean(result_beat ** 2))), 4),
        "peak_db": round(float(20 * np.log10(np.max(np.abs(result_beat)) + 1e-10)), 1),
    }
    diagnostics.append(diag)

    # ── Bass swap ──────────────────────────────────────────────────────
    mid = len(mono_a) // 2
    src_bass = mono_a[mid - overlap_samples:mid]
    tgt_bass = mono_b[mid:mid + overlap_samples]
    result_bass = _bass_swap(src_bass, tgt_bass, sr)
    wav_path = output_path / "bass_swap_mono.wav"
    sf.write(str(wav_path), result_bass, sr)
    files_written.append(str(wav_path))

    diag = {
        "type": "bass_swap",
        "file": str(wav_path),
        "bass_cutoff_hz": 150.0,
        "overlap_samples": overlap_samples,
        "channels": 1,
        "output_samples": len(result_bass),
        "rms_energy": round(float(np.sqrt(np.mean(result_bass ** 2))), 4),
        "peak_db": round(float(20 * np.log10(np.max(np.abs(result_bass)) + 1e-10)), 1),
    }
    diagnostics.append(diag)

    # ── Filter sweep ───────────────────────────────────────────────────
    src_filter = mono_a[mid - overlap_samples:mid]
    tgt_filter = mono_b[mid:mid + overlap_samples]
    result_filter = _filter_sweep(src_filter, tgt_filter, sr)
    wav_path = output_path / "filter_sweep_mono.wav"
    sf.write(str(wav_path), result_filter, sr)
    files_written.append(str(wav_path))

    diag = {
        "type": "filter_sweep",
        "file": str(wav_path),
        "overlap_samples": overlap_samples,
        "channels": 1,
        "output_samples": len(result_filter),
        "rms_energy": round(float(np.sqrt(np.mean(result_filter ** 2))), 4),
        "peak_db": round(float(20 * np.log10(np.max(np.abs(result_filter)) + 1e-10)), 1),
    }
    diagnostics.append(diag)

    # ── Echo out ───────────────────────────────────────────────────────
    src_echo = mono_a[mid - overlap_samples:mid]
    tgt_echo = mono_b[mid:mid + overlap_samples]
    result_echo = _echo_out(src_echo, tgt_echo, sr)
    wav_path = output_path / "echo_out_mono.wav"
    sf.write(str(wav_path), result_echo, sr)
    files_written.append(str(wav_path))

    diag = {
        "type": "echo_out",
        "file": str(wav_path),
        "overlap_samples": overlap_samples,
        "channels": 1,
        "output_samples": len(result_echo),
        "rms_energy": round(float(np.sqrt(np.mean(result_echo ** 2))), 4),
        "peak_db": round(float(20 * np.log10(np.max(np.abs(result_echo)) + 1e-10)), 1),
    }
    diagnostics.append(diag)

    # Write JSON diagnostics
    json_path = output_path / "transition_diagnostics.json"
    with open(json_path, "w") as f:
        json.dump({
            "sample_rate": sr,
            "overlap_sec": overlap_sec,
            "stereo_generated": stereo,
            "transitions": diagnostics,
        }, f, indent=2)
    files_written.append(str(json_path))

    logger.info(
        "Transition auditions written: %d files to %s",
        len(files_written), output_dir,
    )

    return {
        "output_dir": str(output_path),
        "files": files_written,
        "diagnostics": diagnostics,
        "json_path": str(json_path),
    }


# ── V4 Set-Level Diagnostics ─────────────────────────────────────────


def generate_set_diagnostic_report(
    set_plan,
    output_dir: str = "outputs/diagnostics",
) -> dict:
    """Generate a V4 diagnostic report for a complete set plan.

    Produces a JSON file with per-track analysis details and per-transition
    V4 info (phrase/structural context, vocal regions, energy profile,
    EQ/bass management status).

    Args:
        set_plan: A SetPlan object from the planner.
        output_dir: Directory to write the diagnostic JSON.

    Returns:
        Dict with paths and the full diagnostic data.
    """
    from djenius.core.planner import _compute_set_energy_profile

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Build track lookup
    track_by_id = {t.id: t for t in set_plan.tracks}

    # Per-track diagnostics
    track_diagnostics = []
    for track in set_plan.tracks:
        analysis = track.analysis
        td = {
            "id": track.id,
            "title": track.title,
            "filepath": track.filepath,
            "bpm": round(analysis.bpm, 1),
            "key": analysis.key,
            "camelot": analysis.camelot,
            "duration_sec": round(track.duration_sec, 1),
            "mean_energy": round(analysis.mean_energy, 3),
            "low_energy": round(analysis.low_energy, 3),
            "mid_energy": round(analysis.mid_energy, 3),
            "high_energy": round(analysis.high_energy, 3),
            "intro_end": round(analysis.intro_end, 1),
            "outro_start": round(analysis.outro_start, 1),
            "phrase_count": len(analysis.phrase_boundaries),
            "bar_count": len(analysis.bar_times),
            "structural_sections": [
                {"start": round(s, 1), "end": round(e, 1), "label": l}
                for s, e, l in analysis.structural_sections
            ],
            "vocal_regions": [
                {"start": round(s, 1), "end": round(e, 1)}
                for s, e in analysis.vocal_regions
            ],
            "exit_points_count": len(analysis.possible_exit_points),
            "entry_points_count": len(analysis.possible_entry_points),
        }
        track_diagnostics.append(td)

    # Per-transition diagnostics
    transition_diagnostics = []
    for trans in set_plan.transitions:
        source = track_by_id.get(trans.source_track_id)
        target = track_by_id.get(trans.target_track_id)

        td = {
            "source_title": source.title if source else "?",
            "target_title": target.title if target else "?",
            "transition_type": trans.transition_type.value,
            "source_exit_time": trans.source_exit_time,
            "target_entry_time": trans.target_entry_time,
            "overlap_duration": trans.overlap_duration,
            "length_bars": trans.length_bars,
            "confidence": trans.confidence,
            "reasoning": trans.reasoning,
            "bpm_match": {
                "source_bpm": round(source.bpm, 1) if source else 0,
                "target_bpm": round(target.bpm, 1) if target else 0,
                "requires_stretch": trans.requires_stretch,
                "stretch_pct": trans.stretch_amount_pct,
            },
            "energy": {
                "source_mean": round(source.mean_energy, 3) if source else 0,
                "target_mean": round(target.mean_energy, 3) if target else 0,
                "direction": (
                    "rising" if (target and source and target.mean_energy > source.mean_energy + 0.1)
                    else "dropping" if (target and source and target.mean_energy < source.mean_energy - 0.1)
                    else "similar"
                ),
            },
            "vocal": {
                "source_has_vocals": bool(source.analysis.vocal_regions) if source else False,
                "target_has_vocals": bool(target.analysis.vocal_regions) if target else False,
                "source_vocal_region_count": len(source.analysis.vocal_regions) if source else 0,
                "target_vocal_region_count": len(target.analysis.vocal_regions) if target else 0,
            },
            "structure": {
                "source_outro_region": source.mean_energy > 0 and source.analysis.outro_start < source.duration_sec if source else False,
                "target_intro_bypassed": target.analysis.intro_end > 0 and trans.target_entry_time > target.analysis.intro_end if target else False,
            },
        }
        transition_diagnostics.append(td)

    # Energy trajectory
    energy_trajectory = _compute_set_energy_profile(
        [t.id for t in set_plan.tracks], track_by_id,
    )

    report = {
        "set_plan_summary": {
            "track_count": len(set_plan.tracks),
            "transition_count": len(set_plan.transitions),
            "total_duration_sec": set_plan.total_duration_sec,
            "target_duration_sec": set_plan.target_duration_sec,
            "energy_profile": set_plan.energy_profile.value,
            "avg_confidence": set_plan.avg_transition_confidence,
            "overall_score": set_plan.score,
        },
        "energy_trajectory": energy_trajectory,
        "tracks": track_diagnostics,
        "transitions": transition_diagnostics,
    }

    # Write JSON
    json_path = output_path / "set_diagnostic_report.json"
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("Set diagnostic report written to %s", json_path)

    return {
        "json_path": str(json_path),
        "report": report,
    }
