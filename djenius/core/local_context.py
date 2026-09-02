"""Compact local musical context descriptors for segment handoffs.

The V12 layer compares bounded outgoing and incoming windows.  It uses
ordinary librosa features computed during acoustic analysis; no second
transition engine or large model is involved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from djenius.core.models import PerformanceSegment, TrackProfile


LOCAL_CONTEXT_VERSION = "1"
CONTEXT_WINDOW_SEC = 4.0
CONTEXT_HOP_SEC = 2.0
CONTEXT_STATS = {"requests": 0, "cache_hits": 0}


def reset_context_stats() -> None:
    CONTEXT_STATS["requests"] = 0
    CONTEXT_STATS["cache_hits"] = 0


@dataclass
class LocalMusicalContext:
    """Evidence from one exact source window."""

    source_start_sec: float = 0.0
    source_end_sec: float = 0.0
    harmonic_profile: list[float] | None = None
    harmonic_confidence: float = 0.0
    rhythm_profile: list[float] | None = None
    rhythm_confidence: float = 0.0
    energy_level: float = 0.0
    energy_slope: float = 0.0
    bass_activity: float = 0.0
    bass_rhythm: float = 0.0
    vocal_density: float = 0.0
    spectral_character: list[float] | None = None
    spectral_confidence: float = 0.0
    section_role: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_vector(values, size: int = 0) -> np.ndarray:
    result = np.asarray(values if values is not None else [], dtype=float).reshape(-1)
    result = np.nan_to_num(result, nan=0.0, posinf=0.0, neginf=0.0)
    if size and len(result) != size:
        result = np.resize(result, size)
    return result


def _normalise(values: np.ndarray) -> np.ndarray:
    total = float(np.sum(np.maximum(values, 0.0)))
    if total <= 1e-9:
        return np.ones(len(values), dtype=float) / max(len(values), 1)
    return np.maximum(values, 0.0) / total


def compute_local_context_curves(audio: np.ndarray, sample_rate: int) -> tuple[list[float], list[list[float]], list[list[float]], list[list[float]]]:
    """Compute compact descriptors at two-second hops across the whole track."""
    import librosa

    mono = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(mono) or sample_rate <= 0:
        return [], [], [], []
    window = max(512, int(round(CONTEXT_WINDOW_SEC * sample_rate)))
    hop = max(256, int(round(CONTEXT_HOP_SEC * sample_rate)))
    n_fft = min(2048, max(256, 2 ** int(math.floor(math.log2(max(256, min(window, 2048)))))))
    hop_length = max(64, n_fft // 4)
    times: list[float] = []
    chroma_rows: list[list[float]] = []
    rhythm_rows: list[list[float]] = []
    spectral_rows: list[list[float]] = []
    for start in range(0, len(mono), hop):
        end = min(len(mono), start + window)
        clip = mono[start:end]
        if len(clip) < max(256, sample_rate // 2):
            clip = np.pad(clip, (0, max(0, min(window, sample_rate) - len(clip))))
        if not len(clip):
            continue
        spectrum = np.abs(librosa.stft(clip, n_fft=n_fft, hop_length=hop_length))
        power = spectrum * spectrum
        freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=n_fft)
        total = float(np.sum(power)) + 1e-12
        chroma = librosa.feature.chroma_stft(S=power, sr=sample_rate, n_fft=n_fft).mean(axis=1)
        chroma_rows.append(_normalise(chroma).round(5).tolist())

        onset = librosa.onset.onset_strength(S=spectrum, sr=sample_rate, hop_length=hop_length)
        onset = _safe_vector(onset)
        flux = np.maximum(0.0, np.diff(spectrum, axis=1)).mean(axis=0) if spectrum.shape[1] > 1 else np.zeros(1)
        rhythm = np.array([
            float(np.mean(onset)) / (float(np.max(onset)) + 1e-9),
            float(np.std(onset)) / (float(np.mean(onset)) + 1e-9),
            float(np.mean(flux)) / (float(np.mean(spectrum)) + 1e-9),
        ])
        rhythm_rows.append(np.clip(np.nan_to_num(rhythm), 0.0, 4.0).round(5).tolist())

        band_values = [
            float(np.sum(power[freqs < 180.0])) / total,
            float(np.sum(power[(freqs >= 180.0) & (freqs < 4000.0)])) / total,
            float(np.sum(power[freqs >= 4000.0])) / total,
        ]
        centroid = float(np.sum(freqs[:, None] * power)) / total
        bandwidth = float(np.sqrt(np.sum(((freqs[:, None] - centroid) ** 2) * power)) / total)
        spectral_rows.append(np.clip(band_values + [centroid / max(sample_rate / 2.0, 1.0), bandwidth / max(sample_rate / 2.0, 1.0)], 0.0, 1.0).round(5).tolist())
        times.append(round((start + min(end, len(mono))) / (2.0 * sample_rate), 4))
        if end >= len(mono):
            break
    return times, chroma_rows, rhythm_rows, spectral_rows


def _window_rows(track: TrackProfile, start: float, end: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    analysis = track.analysis
    times = _safe_vector(getattr(analysis, "local_context_times", []))
    row_count = min(
        len(times), len(getattr(analysis, "local_chroma_curve", [])),
        len(getattr(analysis, "local_rhythm_curve", [])),
        len(getattr(analysis, "local_spectral_curve", [])),
    )
    if row_count:
        indexes = np.where((times[:row_count] >= start - CONTEXT_WINDOW_SEC / 2) & (times[:row_count] <= end + CONTEXT_WINDOW_SEC / 2))[0]
    else:
        indexes = np.array([], dtype=int)
    chroma = np.asarray([analysis.local_chroma_curve[i] for i in indexes], dtype=float) if len(indexes) else np.empty((0, 12))
    rhythm = np.asarray([analysis.local_rhythm_curve[i] for i in indexes], dtype=float) if len(indexes) else np.empty((0, 3))
    spectral = np.asarray([analysis.local_spectral_curve[i] for i in indexes], dtype=float) if len(indexes) else np.empty((0, 5))
    if chroma.ndim != 2 or chroma.shape[1] != 12:
        chroma = np.empty((0, 12))
    if rhythm.ndim != 2 or rhythm.shape[1] != 3:
        rhythm = np.empty((0, 3))
    if spectral.ndim != 2 or spectral.shape[1] != 5:
        spectral = np.empty((0, 5))
    return chroma, rhythm, spectral, float(len(indexes))


def _curve_slice(curve: list[float], start: float, end: float, duration: float) -> np.ndarray:
    values = _safe_vector(curve)
    if not len(values) or duration <= 0:
        return np.array([], dtype=float)
    left = max(0, min(len(values) - 1, int(start / duration * len(values))))
    right = max(left + 1, min(len(values), int(math.ceil(end / duration * len(values)))))
    return values[left:right]


def _fallback_harmonic(track: TrackProfile) -> np.ndarray:
    """Represent a Camelot key as a circular twelve-bin local fallback."""
    value = str(track.analysis.camelot or "")
    try:
        number = int(value[:-1])
        mode = value[-1].upper()
        pitch = ((number - 1) * 7 + (3 if mode == "B" else 0)) % 12
    except (ValueError, IndexError):
        return np.ones(12, dtype=float) / 12.0
    result = np.zeros(12, dtype=float)
    result[pitch] = 1.0
    return result


def _slope(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    x = np.arange(len(values), dtype=float)
    return float(np.polyfit(x, values, 1)[0])


def build_local_context(track: TrackProfile, start: float, end: float) -> LocalMusicalContext:
    """Build one context from the exact requested source bounds."""
    start = max(0.0, float(start))
    end = min(max(start, float(end)), track.duration_sec)
    CONTEXT_STATS["requests"] += 1
    cache_key = f"{track.id}:{LOCAL_CONTEXT_VERSION}:{start:.4f}:{end:.4f}"
    cached = getattr(track.analysis, "local_context_cache", {}).get(cache_key)
    if cached:
        CONTEXT_STATS["cache_hits"] += 1
        return LocalMusicalContext(**cached)
    chroma_rows, rhythm_rows, spectral_rows, row_count = _window_rows(track, start, end)
    energy = _curve_slice(track.analysis.energy_curve, start, end, track.duration_sec)
    low = _curve_slice(track.analysis.low_energy_curve, start, end, track.duration_sec)
    if row_count:
        harmonic = _normalise(np.mean(chroma_rows, axis=0))
        rhythm = np.mean(rhythm_rows, axis=0)
        spectral = np.mean(spectral_rows, axis=0)
        harmonic_confidence = min(1.0, row_count / 3.0)
        rhythm_confidence = min(1.0, row_count / 3.0)
        spectral_confidence = min(1.0, row_count / 3.0)
        bass_rhythm = float(np.std(spectral_rows[:, 0]))
    else:
        harmonic = _fallback_harmonic(track)
        rhythm = np.array([0.5, 0.5, 0.5])
        spectral = np.array([
            track.analysis.low_energy,
            track.analysis.mid_energy,
            track.analysis.high_energy,
            track.analysis.spectral_centroid_mean / max(1.0, 11025.0),
            0.5,
        ])
        harmonic_confidence = float(track.analysis.key_confidence) * 0.55
        rhythm_confidence = float(track.analysis.bpm_confidence) * 0.55
        spectral_confidence = float(track.analysis.analysis_confidence) * 0.45
        bass_rhythm = 0.0
    role = "unknown"
    for section_start, section_end, section_role in track.analysis.structural_sections:
        if section_start <= (start + end) / 2.0 <= section_end:
            role = str(section_role)
            break
    context = LocalMusicalContext(
        source_start_sec=round(start, 4),
        source_end_sec=round(end, 4),
        harmonic_profile=np.clip(harmonic, 0.0, 1.0).round(5).tolist(),
        harmonic_confidence=round(float(harmonic_confidence), 4),
        rhythm_profile=np.clip(rhythm, 0.0, 4.0).round(5).tolist(),
        rhythm_confidence=round(float(rhythm_confidence), 4),
        energy_level=round(float(np.mean(energy)) if len(energy) else float(track.mean_energy), 4),
        energy_slope=round(_slope(energy), 5),
        bass_activity=round(float(np.mean(low)) if len(low) else float(track.analysis.low_energy), 4),
        bass_rhythm=round(bass_rhythm, 4),
        vocal_density=round(float(np.clip(sum(max(0.0, min(end, right) - max(start, left)) for left, right in track.analysis.vocal_regions) / max(end - start, 0.001), 0.0, 1.0)), 4),
        spectral_character=np.clip(spectral, 0.0, 1.0).round(5).tolist(),
        spectral_confidence=round(float(spectral_confidence), 4),
        section_role=role,
    )
    cache = getattr(track.analysis, "local_context_cache", {})
    cache[cache_key] = context.to_dict()
    # Keep the serialized cache bounded when a user repeatedly regenerates
    # plans with many nearby segment windows.
    if len(cache) > 256:
        for old_key in list(cache)[: len(cache) - 256]:
            cache.pop(old_key, None)
    track.analysis.local_context_cache = cache
    return context


def _cosine(left: list[float] | None, right: list[float] | None) -> float:
    a, b = _safe_vector(left), _safe_vector(right)
    if not len(a) or len(a) != len(b):
        return 0.5
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.clip(np.dot(a, b) / denominator if denominator else 0.5, 0.0, 1.0))


def _distance_score(left: list[float] | None, right: list[float] | None, scale: float = 1.0) -> float:
    a, b = _safe_vector(left), _safe_vector(right)
    if not len(a) or len(a) != len(b):
        return 0.5
    return float(np.clip(1.0 - np.mean(np.abs(a - b)) / max(scale, 1e-9), 0.0, 1.0))


def _role_score(source: str, target: str) -> float:
    source, target = str(source), str(target)
    if "unknown" in {source, target}:
        return 0.5
    flow = {
        "intro": {"verse", "hook", "chorus"}, "verse": {"pre_chorus", "chorus", "hook", "instrumental"},
        "pre_chorus": {"chorus", "hook", "drop"}, "chorus": {"hook", "instrumental", "breakdown", "outro"},
        "hook": {"hook", "chorus", "instrumental", "drop", "outro"}, "breakdown": {"build", "drop", "chorus"},
        "build": {"drop", "chorus", "hook"}, "drop": {"breakdown", "hook", "outro", "chorus"},
        "outro": {"intro", "verse", "hook", "chorus"},
    }
    if target in flow.get(source, set()):
        return 1.0
    if source == target:
        return 0.45
    return 0.65


def score_local_context(
    source: TrackProfile,
    source_segment: PerformanceSegment,
    target: TrackProfile,
    target_segment: PerformanceSegment,
    *,
    style: str = "quick_mix",
) -> tuple[float, dict]:
    """Score the exact outgoing/incoming windows for one segment pair."""
    window = min(8.0, max(4.0, source_segment.duration_sec * 0.35, target_segment.duration_sec * 0.35))
    source_context = build_local_context(source, max(source_segment.source_start_sec, source_segment.source_end_sec - window), source_segment.source_end_sec)
    target_context = build_local_context(target, target_segment.source_start_sec, min(target_segment.source_end_sec, target_segment.source_start_sec + window))
    harmonic = _cosine(source_context.harmonic_profile, target_context.harmonic_profile)
    rhythm = _distance_score(source_context.rhythm_profile, target_context.rhythm_profile, scale=2.0)
    energy = _distance_score([source_context.energy_level], [target_context.energy_level], scale=1.0)
    slope = _distance_score([source_context.energy_slope], [target_context.energy_slope], scale=0.15)
    timbre = _distance_score(source_context.spectral_character, target_context.spectral_character, scale=0.7)
    bass = _distance_score([source_context.bass_activity], [target_context.bass_activity], scale=0.7)
    vocal = float(np.clip(1.0 - source_context.vocal_density * target_context.vocal_density, 0.0, 1.0))
    role = _role_score(source_context.section_role, target_context.section_role)
    weights = {
        "smooth": (0.20, 0.18, 0.18, 0.12, 0.14, 0.10, 0.05, 0.03),
        "club": (0.18, 0.24, 0.14, 0.08, 0.08, 0.20, 0.05, 0.03),
        "quick_mix": (0.15, 0.22, 0.18, 0.10, 0.12, 0.12, 0.08, 0.03),
        "story": (0.15, 0.12, 0.18, 0.15, 0.10, 0.05, 0.18, 0.07),
        "experimental": (0.12, 0.16, 0.12, 0.08, 0.10, 0.10, 0.08, 0.04),
    }.get(style, (0.17, 0.18, 0.17, 0.10, 0.12, 0.12, 0.08, 0.06))
    values = (harmonic, rhythm, energy, slope, timbre, bass, vocal, role)
    confidence = min(source_context.harmonic_confidence, target_context.harmonic_confidence, source_context.spectral_confidence, target_context.spectral_confidence)
    score = float(np.clip(sum(value * weight for value, weight in zip(values, weights)) * (0.65 + 0.35 * confidence), 0.0, 1.0))
    return round(score, 4), {
        "source_window": source_context.to_dict(),
        "target_window": target_context.to_dict(),
        "local_harmonic_score": round(harmonic, 4),
        "local_rhythm_score": round(rhythm, 4),
        "local_energy_score": round(energy, 4),
        "local_energy_slope_score": round(slope, 4),
        "local_timbre_score": round(timbre, 4),
        "local_bass_score": round(bass, 4),
        "local_vocal_score": round(vocal, 4),
        "local_role_score": round(role, 4),
        "local_confidence": round(confidence, 4),
        "style": style,
    }
