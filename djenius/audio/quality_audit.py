"""Full-context audio auditing for rendered DJ transitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf


def audit_rendered_mix(
    mix_path: str,
    diagnostics_path: str,
    report_path: Optional[str] = None,
) -> dict:
    """Measure approach, transition, and landing context in a rendered mix."""
    audio, sample_rate = sf.read(mix_path, dtype="float32", always_2d=True)
    diagnostics = json.loads(Path(diagnostics_path).read_text())
    transition_events = [
        event for event in diagnostics.get("events", [])
        if event.get("type") == "transition"
    ]
    transitions = []
    for index, event in enumerate(transition_events, 1):
        start = int(event["output_start_sample"])
        end = int(event["output_end_sample"])
        approach = _audio_slice(audio, start - 30 * sample_rate, start)
        transition_audio = _audio_slice(audio, start, end)
        landing = _audio_slice(audio, end, end + 30 * sample_rate)
        before = _audio_slice(audio, start - 10 * sample_rate, start)
        after = _audio_slice(audio, end, end + 10 * sample_rate)
        before_metrics = audio_metrics(before, sample_rate)
        after_metrics = audio_metrics(after, sample_rate)
        transition_metrics = audio_metrics(
            transition_audio, sample_rate, include_curve=True,
        )
        loudness_delta = after_metrics["lufs"] - before_metrics["lufs"]
        energy_delta = after_metrics["rms_dbfs"] - before_metrics["rms_dbfs"]
        bass_delta = after_metrics["low_energy_ratio"] - before_metrics["low_energy_ratio"]
        transition_curve = transition_metrics["one_second_curve"]
        transition_min_rms = min(
            (point["rms_dbfs"] for point in transition_curve),
            default=transition_metrics["rms_dbfs"],
        )
        surrounding_rms = (
            before_metrics["rms_dbfs"] + after_metrics["rms_dbfs"]
        ) / 2.0
        transition_trough_db = max(0.0, surrounding_rms - transition_min_rms)
        transition_floor_score = max(
            0.0, 1.0 - max(0.0, transition_trough_db - 1.5) / 7.5,
        )
        planned_quality = (event.get("quality_score") or {}).get("overall_score")
        actual_continuity = (
            0.30 * max(0.0, 1.0 - abs(loudness_delta) / 8.0)
            + 0.25 * max(0.0, 1.0 - abs(energy_delta) / 8.0)
            + 0.15 * max(0.0, 1.0 - abs(bass_delta) / 0.45)
            + 0.30 * transition_floor_score
        )
        ranking_score = (
            0.60 * planned_quality + 0.40 * actual_continuity
            if planned_quality is not None else actual_continuity
        )
        transitions.append({
            "index": index,
            "source": event.get("source_track_title"),
            "target": event.get("target_track_title"),
            "transition_type": event.get("transition_type"),
            "output_start_sec": round(start / sample_rate, 3),
            "output_end_sec": round(end / sample_rate, 3),
            "overlap_sec": round((end - start) / sample_rate, 3),
            "approach": audio_metrics(approach, sample_rate, include_curve=True),
            "transition": transition_metrics,
            "landing": audio_metrics(landing, sample_rate, include_curve=True),
            "before_10_sec": before_metrics,
            "after_10_sec": after_metrics,
            "actual_loudness_delta_db": round(loudness_delta, 3),
            "actual_energy_delta_db": round(energy_delta, 3),
            "actual_bass_delta": round(bass_delta, 4),
            "transition_trough_db": round(transition_trough_db, 3),
            "transition_floor_score": round(transition_floor_score, 4),
            "planned_quality": event.get("quality_score"),
            "planned_context": {
                key: event.get(key) for key in (
                    "source_section",
                    "target_section",
                    "source_phrase_alignment_error_ms",
                    "target_phrase_alignment_error_ms",
                    "source_bar_index",
                    "target_bar_index",
                    "source_vocal_fraction",
                    "target_vocal_fraction",
                    "vocal_collision",
                )
            },
            "actual_continuity_score": round(actual_continuity, 4),
            "ranking_score": round(float(ranking_score), 4),
        })

    whole_mix = audio_metrics(audio, sample_rate)
    near_silence = longest_near_silent_interval(audio, sample_rate)
    provenance = diagnostics.get("provenance_audit", {})
    report = {
        "mix_path": str(Path(mix_path).resolve()),
        "diagnostics_path": str(Path(diagnostics_path).resolve()),
        "channels": int(audio.shape[1]),
        "sample_rate": sample_rate,
        "duration_sec": round(len(audio) / sample_rate, 3),
        "peak_dbfs": whole_mix["peak_dbfs"],
        "lufs": whole_mix["lufs"],
        "finite_samples": bool(np.isfinite(audio).all()),
        "clipped_samples": int(np.count_nonzero(np.abs(audio) >= 1.0)),
        "longest_near_silent_interval_sec": near_silence,
        "transition_count": len(transitions),
        "provenance_audit": provenance,
        "transitions": transitions,
        "worst_transition_indices": [
            item["index"] for item in sorted(
                transitions, key=lambda item: item["ranking_score"],
            )[:3]
        ],
    }
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, indent=2))
    return report


def render_transition_previews(
    mix_path: str,
    diagnostics_path: str,
    output_dir: str,
    prefix: str,
    context_sec: float = 30.0,
) -> list[str]:
    """Write approach + complete transition + landing review WAV files."""
    audio, sample_rate = sf.read(mix_path, dtype="float32", always_2d=True)
    diagnostics = json.loads(Path(diagnostics_path).read_text())
    events = [
        event for event in diagnostics.get("events", [])
        if event.get("type") == "transition"
    ]
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    context_samples = round(context_sec * sample_rate)
    for index, event in enumerate(events, 1):
        start = max(0, int(event["output_start_sample"]) - context_samples)
        end = min(
            len(audio), int(event["output_end_sample"]) + context_samples,
        )
        path = destination / f"{prefix}_transition_{index:02d}.wav"
        sf.write(path, audio[start:end], sample_rate, subtype="PCM_16")
        paths.append(str(path.resolve()))
    return paths


def audio_metrics(
    audio: np.ndarray,
    sample_rate: int,
    include_curve: bool = False,
) -> dict:
    """Return compact loudness, energy, bass, and brightness measurements."""
    mono = _mono(audio)
    if not len(mono):
        result = {
            "rms": 0.0,
            "rms_dbfs": -120.0,
            "lufs": -120.0,
            "peak_dbfs": -120.0,
            "low_energy_ratio": 0.0,
            "spectral_centroid_hz": 0.0,
        }
        if include_curve:
            result["one_second_curve"] = []
        return result
    rms = float(np.sqrt(np.mean(np.square(mono, dtype=np.float64))))
    peak = float(np.max(np.abs(audio)))
    low_ratio, centroid = _spectral_summary(mono, sample_rate)
    result = {
        "rms": round(rms, 7),
        "rms_dbfs": round(_amplitude_db(rms), 3),
        "lufs": round(_loudness(audio, sample_rate), 3),
        "peak_dbfs": round(_amplitude_db(peak), 3),
        "low_energy_ratio": round(low_ratio, 4),
        "spectral_centroid_hz": round(centroid, 1),
    }
    if include_curve:
        result["one_second_curve"] = _one_second_curve(mono, sample_rate)
    return result


def longest_near_silent_interval(
    audio: np.ndarray,
    sample_rate: int,
    threshold_dbfs: float = -50.0,
) -> float:
    """Return the longest consecutive one-second near-silent run."""
    mono = _mono(audio)
    longest = current = 0
    for start in range(0, len(mono), sample_rate):
        frame = mono[start:start + sample_rate]
        rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64)))) if len(frame) else 0.0
        if _amplitude_db(rms) <= threshold_dbfs:
            current += len(frame)
            longest = max(longest, current)
        else:
            current = 0
    return round(longest / sample_rate, 3)


def _one_second_curve(audio: np.ndarray, sample_rate: int) -> list[dict]:
    curve = []
    for index, start in enumerate(range(0, len(audio), sample_rate)):
        frame = audio[start:start + sample_rate]
        if len(frame) < round(sample_rate * 0.8):
            continue
        rms = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
        spectrum = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
        frequencies = np.fft.rfftfreq(len(frame), 1.0 / sample_rate)
        power = np.square(spectrum, dtype=np.float64)
        curve.append({
            "time_sec": float(index),
            "rms_dbfs": round(_amplitude_db(rms), 3),
            "low_energy_ratio": round(
                float(np.sum(power[frequencies < 180.0]) / max(np.sum(power), 1e-12)),
                4,
            ),
            "spectral_centroid_hz": round(
                float(np.sum(frequencies * spectrum) / max(np.sum(spectrum), 1e-12)),
                1,
            ),
        })
    return curve


def _spectral_summary(audio: np.ndarray, sample_rate: int) -> tuple[float, float]:
    """Aggregate one-second spectra without a full-mix FFT allocation."""
    frequencies = np.fft.rfftfreq(sample_rate, 1.0 / sample_rate)
    magnitude_sum = np.zeros(len(frequencies), dtype=np.float64)
    power_sum = np.zeros(len(frequencies), dtype=np.float64)
    starts = list(range(0, max(1, len(audio) - sample_rate + 1), sample_rate))
    if len(starts) > 120:
        selected = np.linspace(0, len(starts) - 1, 120, dtype=int)
        starts = [starts[index] for index in selected]
    window = np.hanning(sample_rate)
    for start in starts:
        frame = audio[start:start + sample_rate]
        if len(frame) < sample_rate:
            frame = np.pad(frame, (0, sample_rate - len(frame)))
        magnitude = np.abs(np.fft.rfft(frame * window))
        magnitude_sum += magnitude
        power_sum += np.square(magnitude, dtype=np.float64)
    low_ratio = float(
        np.sum(power_sum[frequencies < 180.0]) / max(np.sum(power_sum), 1e-12)
    )
    centroid = float(
        np.sum(frequencies * magnitude_sum) / max(np.sum(magnitude_sum), 1e-12)
    )
    return low_ratio, centroid


def _audio_slice(audio: np.ndarray, start: int, end: int) -> np.ndarray:
    return audio[max(0, start):min(len(audio), end)]


def _mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio.astype(np.float32, copy=False)
    return np.mean(audio, axis=1, dtype=np.float32)


def _amplitude_db(value: float) -> float:
    return float(20.0 * np.log10(max(value, 1e-6)))


def _loudness(audio: np.ndarray, sample_rate: int) -> float:
    if len(audio) < round(0.4 * sample_rate):
        return _amplitude_db(float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))))
    try:
        import pyloudnorm as pyln
        return float(pyln.Meter(sample_rate).integrated_loudness(audio))
    except Exception:
        return _amplitude_db(float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))))
