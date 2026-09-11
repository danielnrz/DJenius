"""Backward-compatible V2 musical-intelligence feature builders.

The renderer still works in seconds, but these descriptors make beat, bar,
phrase, section, tempo ambiguity, groove and cue intent explicit for planners.
The functions are deterministic and dependency-light beyond NumPy/librosa.
"""
from __future__ import annotations

from typing import Iterable

import librosa
import numpy as np

V2_ANALYSIS_SCHEMA = "2.0"


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def build_beat_positions(
    beat_times: list[float],
    downbeat_times: list[float] | None = None,
) -> list[dict]:
    """Represent detected beats explicitly in 4/4 musical time."""
    if not beat_times:
        return []
    beats = sorted(float(t) for t in beat_times if float(t) >= 0.0)
    if not beats:
        return []
    downbeats = sorted(float(t) for t in (downbeat_times or []))
    phase_offset = 0
    if downbeats and len(beats) >= 4:
        median_interval = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.5
        tolerance = max(0.04, median_interval * 0.25)
        best = None
        for idx in range(min(4, len(beats))):
            error = min(abs(beats[idx] - d) for d in downbeats)
            if best is None or error < best[0]:
                best = (error, idx)
        if best and best[0] <= tolerance:
            phase_offset = best[1]

    result = []
    for index, time_sec in enumerate(beats):
        relative = index - phase_offset
        bar_index = max(0, relative // 4) + 1
        beat_in_bar = relative % 4 + 1
        result.append({
            "time_sec": round(time_sec, 6),
            "beat_index": index + 1,
            "bar_index": int(bar_index),
            "beat_in_bar": int(beat_in_bar),
            "is_downbeat": bool(beat_in_bar == 1),
        })
    return result


def build_tempo_hypotheses(bpm: float, confidence: float) -> list[dict]:
    """Keep plausible primary/half/double tempo interpretations."""
    if bpm <= 0:
        return []
    candidates = [("primary", bpm, confidence), ("half", bpm / 2.0, confidence * 0.62), ("double", bpm * 2.0, confidence * 0.62)]
    result = []
    seen: set[int] = set()
    for relation, value, score in candidates:
        if not 40.0 <= value <= 220.0:
            continue
        bucket = int(round(value * 10))
        if bucket in seen:
            continue
        seen.add(bucket)
        result.append({
            "relation": relation,
            "bpm": round(float(value), 3),
            "confidence": round(_clip01(float(score)), 3),
        })
    return result


def estimate_tempo_zones(
    beat_times: list[float],
    global_bpm: float,
    *,
    window_beats: int = 8,
    change_ratio: float = 0.035,
    min_zone_beats: int = 24,
) -> list[dict]:
    """Estimate contiguous local-tempo zones from detected beat intervals."""
    beats = np.asarray(sorted(float(t) for t in beat_times if float(t) >= 0.0), dtype=float)
    if len(beats) < 3:
        return [] if global_bpm <= 0 else [{
            "start_sec": round(float(beats[0]) if len(beats) else 0.0, 6),
            "end_sec": round(float(beats[-1]) if len(beats) else 0.0, 6),
            "bpm": round(float(global_bpm), 3),
            "confidence": 0.3,
            "beat_start": 1,
            "beat_end": int(len(beats)),
        }]

    intervals = np.diff(beats)
    valid = (intervals > 0.20) & (intervals < 1.55)
    local = np.full(len(intervals), np.nan, dtype=float)
    local[valid] = 60.0 / intervals[valid]
    fallback = float(global_bpm if global_bpm > 0 else np.nanmedian(local))
    local = np.where(np.isfinite(local), local, fallback)

    radius = max(1, window_beats // 2)
    smooth = np.asarray([
        float(np.median(local[max(0, i - radius):min(len(local), i + radius + 1)]))
        for i in range(len(local))
    ])
    threshold_floor = 2.5
    starts = [0]
    anchor = smooth[0]
    for i in range(1, len(smooth)):
        threshold = max(threshold_floor, abs(anchor) * change_ratio)
        if abs(smooth[i] - anchor) > threshold:
            starts.append(i)
            anchor = smooth[i]
        else:
            anchor = 0.8 * anchor + 0.2 * smooth[i]
    starts.append(len(smooth))

    zones = []
    for zi in range(len(starts) - 1):
        lo, hi = starts[zi], starts[zi + 1]
        values = local[lo:hi]
        if len(values) == 0:
            continue
        median_bpm = float(np.median(values))
        cv = float(np.std(values) / max(np.mean(values), 1e-6))
        confidence = _clip01(1.0 - cv * 6.0)
        end_beat_index = min(hi, len(beats) - 1)
        zones.append({
            "start_sec": round(float(beats[lo]), 6),
            "end_sec": round(float(beats[end_beat_index]), 6),
            "bpm": round(median_bpm, 3),
            "confidence": round(confidence, 3),
            "beat_start": int(lo + 1),
            "beat_end": int(end_beat_index + 1),
        })

    def zone_beats(zone: dict) -> int:
        return max(1, int(zone["beat_end"] - zone["beat_start"] + 1))

    def combine(left: dict, right: dict) -> dict:
        lw, rw = zone_beats(left), zone_beats(right)
        return {
            "start_sec": left["start_sec"],
            "end_sec": right["end_sec"],
            "bpm": round((left["bpm"] * lw + right["bpm"] * rw) / (lw + rw), 3),
            "confidence": round(min(left["confidence"], right["confidence"]), 3),
            "beat_start": left["beat_start"],
            "beat_end": right["beat_end"],
        }

    # Beat trackers often produce a few doubled/missed intervals around fills.
    # A V2 tempo zone must be sustained long enough to matter musically, so
    # absorb short islands into the closer neighbouring tempo before the
    # final near-equal merge.
    merged = [dict(zone) for zone in zones]
    while len(merged) > 1:
        short_index = next(
            (i for i, zone in enumerate(merged) if zone_beats(zone) < min_zone_beats),
            None,
        )
        if short_index is None:
            break
        i = short_index
        if i == 0:
            merged[0:2] = [combine(merged[0], merged[1])]
        elif i == len(merged) - 1:
            merged[-2:] = [combine(merged[-2], merged[-1])]
        else:
            left_delta = abs(merged[i]["bpm"] - merged[i - 1]["bpm"])
            right_delta = abs(merged[i]["bpm"] - merged[i + 1]["bpm"])
            if left_delta <= right_delta:
                merged[i - 1:i + 1] = [combine(merged[i - 1], merged[i])]
            else:
                merged[i:i + 2] = [combine(merged[i], merged[i + 1])]

    stable: list[dict] = []
    for zone in merged:
        if stable and abs(zone["bpm"] - stable[-1]["bpm"]) <= max(2.0, stable[-1]["bpm"] * 0.02):
            stable[-1] = combine(stable[-1], zone)
        else:
            stable.append(dict(zone))
    return stable


def build_vocal_activity_curve(vocal_regions: list[tuple[float, float]], duration: float, resolution_hz: float = 1.0) -> list[float]:
    if duration <= 0 or resolution_hz <= 0:
        return []
    n = max(1, int(np.ceil(duration * resolution_hz)))
    frame = 1.0 / resolution_hz
    curve = np.zeros(n, dtype=float)
    for start, end in vocal_regions:
        start = max(0.0, float(start)); end = min(duration, float(end))
        if end <= start:
            continue
        first = max(0, int(np.floor(start * resolution_hz)))
        last = min(n - 1, int(np.floor(max(start, end - 1e-9) * resolution_hz)))
        for idx in range(first, last + 1):
            fs, fe = idx * frame, min(duration, (idx + 1) * frame)
            curve[idx] += max(0.0, min(end, fe) - max(start, fs)) / max(fe - fs, 1e-9)
    return np.clip(curve, 0.0, 1.0).round(4).tolist()


def compute_groove_profile(audio: np.ndarray, sample_rate: int, beat_times: list[float]) -> tuple[dict, list[float]]:
    """Compute compact onset/groove descriptors and a 1 Hz density curve."""
    if len(audio) == 0 or sample_rate <= 0:
        return {}, []
    y = np.asarray(audio, dtype=np.float32)
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    onset_env = librosa.onset.onset_strength(y=y, sr=sample_rate)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sample_rate, backtrack=False, units="frames")
    onset_times = librosa.frames_to_time(onset_frames, sr=sample_rate)
    duration = len(y) / sample_rate
    bins = max(1, int(np.ceil(duration)))
    density = np.histogram(onset_times, bins=np.arange(bins + 1, dtype=float))[0].astype(float)
    p95 = float(np.percentile(density, 95)) if len(density) else 1.0
    density_curve = (density / max(p95, 1.0)).clip(0.0, 1.0).round(4).tolist()

    phases = []
    beats = np.asarray(sorted(beat_times), dtype=float)
    if len(beats) >= 2:
        for t in onset_times:
            idx = int(np.searchsorted(beats, t, side="right") - 1)
            if idx < 0 or idx >= len(beats) - 1:
                continue
            interval = beats[idx + 1] - beats[idx]
            if interval > 1e-6:
                phases.append(float((t - beats[idx]) / interval))
    phases_arr = np.asarray(phases, dtype=float)
    onbeat = int(np.sum((phases_arr <= 0.15) | (phases_arr >= 0.85))) if len(phases_arr) else 0
    offbeat_mask = (phases_arr >= 0.35) & (phases_arr <= 0.70) if len(phases_arr) else np.asarray([], dtype=bool)
    offbeat = int(np.sum(offbeat_mask)) if len(phases_arr) else 0
    total_quantized = onbeat + offbeat
    syncopation = float(offbeat / total_quantized) if total_quantized else 0.0
    swing_ratio = 1.0
    if len(phases_arr) and np.any(offbeat_mask):
        median_phase = float(np.median(phases_arr[offbeat_mask]))
        swing_ratio = median_phase / max(1.0 - median_phase, 1e-6)
        swing_ratio = float(np.clip(swing_ratio, 0.5, 2.0))

    profile = {
        "onset_density_hz": round(float(len(onset_times) / max(duration, 1e-6)), 4),
        "onbeat_fraction": round(float(onbeat / max(len(phases_arr), 1)), 4),
        "offbeat_fraction": round(float(offbeat / max(len(phases_arr), 1)), 4),
        "syncopation_index": round(_clip01(syncopation), 4),
        "swing_ratio": round(swing_ratio, 4),
        "percussion_density_mean": round(float(np.mean(density_curve)) if density_curve else 0.0, 4),
        "confidence": round(_clip01(len(phases_arr) / 32.0), 3),
    }
    return profile, density_curve


def _curve_stats(curve: list[float], start: float, end: float, duration: float) -> tuple[float, float]:
    if not curve or duration <= 0 or end <= start:
        return 0.0, 0.0
    n = len(curve)
    lo = max(0, min(n - 1, int(np.floor(start / duration * n))))
    hi = max(lo + 1, min(n, int(np.ceil(end / duration * n))))
    values = np.asarray(curve[lo:hi], dtype=float)
    mean = float(np.mean(values)) if len(values) else 0.0
    slope = 0.0
    if len(values) >= 2:
        x = np.linspace(0.0, 1.0, len(values))
        slope = float(np.polyfit(x, values, 1)[0])
    return mean, slope


def build_section_profiles(
    sections: Iterable,
    *,
    duration: float,
    bpm: float,
    energy_curve: list[float],
    vocal_curve: list[float],
    bass_curve: list[float],
    rhythmic_density_curve: list[float],
    phrase_confidences: dict[float, float] | None = None,
) -> list[dict]:
    phrase_confidences = phrase_confidences or {}
    global_energy = float(np.mean(energy_curve)) if energy_curve else 0.5
    result = []
    for index, section in enumerate(sections):
        start = float(section.start_sec); end = float(section.end_sec)
        energy, slope = _curve_stats(energy_curve, start, end, duration)
        vocal, _ = _curve_stats(vocal_curve, start, end, duration)
        bass, _ = _curve_stats(bass_curve, start, end, duration)
        drums, _ = _curve_stats(rhythmic_density_curve, start, end, duration)
        bar_duration = 4.0 * 60.0 / max(bpm, 60.0)
        bar_count = max(1, int(round((end - start) / max(bar_duration, 1e-6))))
        original = str(section.label)
        label = original
        if original in {"verse", "bridge"} and slope > 0.10:
            label = "build"
        elif original in {"verse", "bridge"} and energy < global_energy * 0.72 and vocal < 0.45:
            label = "break"
        elif original == "chorus" and energy > global_energy * 1.08 and index > 0:
            label = "drop"
        boundary_conf = phrase_confidences.get(round(start, 4), 0.55 if start > 0 else 0.75)
        length_conf = min(1.0, bar_count / 8.0)
        confidence = _clip01(0.65 * boundary_conf + 0.35 * length_conf)
        mix_in = _clip01(0.60 * (1.0 - vocal) + 0.25 * confidence + 0.15 * (1.0 - min(1.0, drums)))
        mix_out = _clip01(0.45 * (1.0 - vocal) + 0.30 * confidence + 0.25 * (1.0 if slope <= 0 else 0.4))
        landing = _clip01(0.55 * energy + 0.25 * drums + 0.20 * confidence)
        result.append({
            "start_sec": round(start, 4), "end_sec": round(end, 4),
            "label": label, "source_label": original,
            "boundary_confidence": round(confidence, 3), "label_confidence": round(confidence * (0.9 if label != original else 1.0), 3),
            "bar_count": int(bar_count), "energy_mean": round(energy, 4), "energy_slope": round(slope, 4),
            "vocal_density": round(vocal, 4), "bass_density": round(bass, 4), "drum_density": round(drums, 4),
            "mix_in_score": round(mix_in, 4), "mix_out_score": round(mix_out, 4), "landing_strength": round(landing, 4),
        })
    return result


def build_cue_candidates(
    beat_positions: list[dict], section_profiles: list[dict], phrase_profiles: list[dict], energy_curve: list[float], vocal_curve: list[float], duration: float,
) -> list[dict]:
    if duration <= 0:
        return []
    times: dict[float, dict] = {}
    for section in section_profiles:
        t = float(section["start_sec"])
        uses = ["mix_in"]
        if section["label"] in {"drop", "chorus"}: uses += ["drop_landing", "phrase_cut"]
        if section["label"] in {"break", "build"}: uses += ["echo_reset", "stem_overlay"]
        times[round(t, 4)] = {"section": section["label"], "confidence": section["boundary_confidence"], "use_cases": uses, "mix_in_score": section["mix_in_score"], "mix_out_score": section["mix_out_score"]}
        end = float(section["end_sec"])
        if end < duration - 0.05:
            times.setdefault(round(end, 4), {"section": section["label"], "confidence": section["boundary_confidence"], "use_cases": ["mix_out"], "mix_in_score": section["mix_in_score"], "mix_out_score": section["mix_out_score"]})
    for phrase in phrase_profiles:
        t = round(float(phrase["time_sec"]), 4)
        times.setdefault(t, {"section": "phrase", "confidence": phrase["confidence"], "use_cases": ["mix_in", "mix_out", "phrase_cut"], "mix_in_score": 0.6, "mix_out_score": 0.6})

    beat_times = [float(item["time_sec"]) for item in beat_positions]
    result = []
    for t in sorted(times):
        info = times[t]
        if not 0.0 <= t < duration:
            continue
        if beat_times:
            idx = min(range(len(beat_times)), key=lambda i: abs(beat_times[i] - t))
            beat = beat_positions[idx]
            snapped = beat["time_sec"]
        else:
            beat = {"beat_index": 0, "bar_index": 0, "beat_in_bar": 0}; snapped = t
        curve_idx = min(len(energy_curve) - 1, max(0, int(t))) if energy_curve else 0
        vocal_idx = min(len(vocal_curve) - 1, max(0, int(t))) if vocal_curve else 0
        result.append({
            "time_sec": round(float(snapped), 4), "beat_index": int(beat["beat_index"]), "bar_index": int(beat["bar_index"]), "beat_in_bar": int(beat["beat_in_bar"]),
            "section": info["section"], "confidence": round(_clip01(float(info["confidence"])), 3),
            "vocal_state": "active" if vocal_curve and vocal_curve[vocal_idx] >= 0.35 else "sparse",
            "energy": round(float(energy_curve[curve_idx]) if energy_curve else 0.5, 4),
            "use_cases": sorted(set(info["use_cases"])), "mix_in_score": round(float(info["mix_in_score"]), 4), "mix_out_score": round(float(info["mix_out_score"]), 4),
        })
    # Deduplicate after beat snapping, keeping the stronger cue.
    by_time: dict[float, dict] = {}
    for cue in result:
        key = cue["time_sec"]
        existing = by_time.get(key)
        if existing is None or cue["confidence"] > existing["confidence"]:
            by_time[key] = cue
    return [by_time[key] for key in sorted(by_time)]


def compute_stem_activity_profiles(stems: dict[str, np.ndarray], sample_rate: int) -> dict[str, dict]:
    """Summarize local stem activity without claiming separation quality ground truth."""
    if sample_rate <= 0:
        return {}
    result: dict[str, dict] = {}
    for name, audio in stems.items():
        values = np.asarray(audio, dtype=np.float32)
        if values.size == 0:
            continue
        if values.ndim > 1:
            values = np.mean(values, axis=1)
        frame = max(1, sample_rate)
        rms_db = []
        for start in range(0, len(values), frame):
            chunk = values[start:start + frame]
            if len(chunk):
                rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
                rms_db.append(20.0 * np.log10(max(rms, 1e-10)))
        if not rms_db:
            continue
        rms_arr = np.asarray(rms_db, dtype=float)
        active = rms_arr > -40.0
        duration = len(values) / sample_rate
        onset_env = librosa.onset.onset_strength(y=values, sr=sample_rate)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sample_rate, units="frames")
        result[str(name)] = {
            "active_fraction": round(float(np.mean(active)), 4),
            "mean_rms_db": round(float(np.mean(rms_arr)), 3),
            "peak_rms_db": round(float(np.max(rms_arr)), 3),
            "dynamic_range_db": round(float(np.percentile(rms_arr, 90) - np.percentile(rms_arr, 10)), 3),
            "onset_density_hz": round(float(len(onset_frames) / max(duration, 1e-6)), 4),
            "activity_confidence": round(_clip01(duration / 30.0), 3),
            "quality_method": "activity_only_no_bleed_claim",
        }
    return result
