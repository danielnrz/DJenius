"""Deterministic procedural Groove / Sampler DSP for DJenius V2 Phase 4."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from djenius.core.groove import PerformanceSampleEvent, SUPPORTED_PROCEDURAL_GENERATORS
from djenius.utils.audio_math import db_to_linear


_DEFAULT_DURATION_SEC = {
    "kick_v1": 0.36,
    "snare_v1": 0.28,
    "clap_v1": 0.34,
    "closed_hat_v1": 0.12,
    "open_hat_v1": 0.50,
    "noise_riser_v1": 2.00,
    "downlifter_v1": 2.00,
    "impact_v1": 0.80,
    "reverse_cymbal_v1": 1.00,
}


def _highpass_noise(noise: np.ndarray, width: int = 17) -> np.ndarray:
    width = max(3, int(width) | 1)
    kernel = np.ones(width, dtype=np.float32) / width
    low = np.convolve(noise, kernel, mode="same").astype(np.float32)
    return (noise - low).astype(np.float32)


def _phase_from_frequency(freq: np.ndarray, sample_rate: int) -> np.ndarray:
    return (2.0 * np.pi * np.cumsum(freq, dtype=np.float64) / sample_rate).astype(np.float32)


def _bounded(signal: np.ndarray, level: float) -> np.ndarray:
    signal = np.asarray(signal, dtype=np.float32)
    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    if peak <= 1e-12:
        return np.zeros_like(signal, dtype=np.float32)
    return (signal * (float(level) / peak)).astype(np.float32)


def _apply_edge_envelope(signal: np.ndarray, sample_rate: int, attack_sec: float, release_sec: float) -> np.ndarray:
    result = np.asarray(signal, dtype=np.float32).copy()
    n = len(result)
    if n == 0:
        return result
    attack = min(n, max(0, int(round(attack_sec * sample_rate))))
    release = min(n, max(0, int(round(release_sec * sample_rate))))
    if attack > 1:
        result[:attack] *= np.linspace(0.0, 1.0, attack, dtype=np.float32)
    if release > 1:
        result[-release:] *= np.linspace(1.0, 0.0, release, dtype=np.float32)
    return result


def synthesize_procedural_sound(
    generator: str,
    sample_rate: int,
    *,
    duration_sec: float | None = None,
    level: float = 0.035,
    seed: int = 0,
    channels: int = 2,
) -> np.ndarray:
    """Synthesize one deterministic project-owned sound with bounded peak."""
    if generator not in SUPPORTED_PROCEDURAL_GENERATORS:
        raise ValueError(f"unsupported procedural generator: {generator}")
    if not 1000 <= int(sample_rate) <= 384000:
        raise ValueError("sample_rate must be in [1000, 384000]")
    if channels not in {1, 2}:
        raise ValueError("channels must be 1 or 2")
    if not 0.0 < float(level) <= 0.05:
        raise ValueError("level must be in (0, 0.05]")
    duration = float(duration_sec if duration_sec is not None else _DEFAULT_DURATION_SEC[generator])
    if not 0.005 <= duration <= 16.0:
        raise ValueError("duration_sec must be in [0.005, 16]")

    if isinstance(seed, bool):
        raise ValueError("seed must be an integer in [0, 2147483647]")
    try:
        parsed_seed = int(seed)
        if float(seed) != parsed_seed or not 0 <= parsed_seed <= 2**31 - 1:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("seed must be an integer in [0, 2147483647]") from exc

    n = max(2, int(round(duration * sample_rate)))
    t = np.arange(n, dtype=np.float32) / float(sample_rate)
    progress = np.linspace(0.0, 1.0, n, dtype=np.float32)
    rng = np.random.default_rng(parsed_seed)
    noise = rng.standard_normal(n).astype(np.float32)

    if generator == "kick_v1":
        freq = 46.0 + 105.0 * np.exp(-t * 28.0)
        body = np.sin(_phase_from_frequency(freq, sample_rate)) * np.exp(-t * 12.0)
        click = _highpass_noise(noise, 9) * np.exp(-t * 85.0) * 0.16
        signal = body + click
    elif generator == "snare_v1":
        bright = _highpass_noise(noise, 23)
        body = np.sin(2.0 * np.pi * 185.0 * t).astype(np.float32) * np.exp(-t * 17.0)
        signal = (0.82 * bright + 0.18 * body) * np.exp(-t * 13.5)
    elif generator == "clap_v1":
        bright = _highpass_noise(noise, 19)
        signal = np.zeros(n, dtype=np.float32)
        for burst_index, offset_sec in enumerate((0.0, 0.014, 0.029)):
            start = int(round(offset_sec * sample_rate))
            if start >= n:
                continue
            burst_len = min(n - start, max(4, int(round(0.045 * sample_rate))))
            env = np.exp(-np.arange(burst_len, dtype=np.float32) / max(sample_rate * 0.012, 1.0))
            signal[start:start + burst_len] += bright[:burst_len] * env * (1.0 - burst_index * 0.12)
        signal += bright * np.exp(-t * 15.0) * 0.30
    elif generator in {"closed_hat_v1", "open_hat_v1"}:
        bright = _highpass_noise(noise, 31)
        metallic = (
            0.38 * np.sin(2.0 * np.pi * 6131.0 * t)
            + 0.31 * np.sin(2.0 * np.pi * 8243.0 * t + 0.7)
            + 0.23 * np.sin(2.0 * np.pi * 10337.0 * t + 1.1)
        ).astype(np.float32)
        decay = 42.0 if generator == "closed_hat_v1" else 9.5
        signal = (0.68 * bright + 0.32 * metallic) * np.exp(-t * decay)
    elif generator == "noise_riser_v1":
        bright = _highpass_noise(noise, 41)
        smooth = noise - bright
        spectral = smooth * (1.0 - progress) + bright * progress
        signal = spectral * np.power(progress, 1.7).astype(np.float32)
    elif generator == "downlifter_v1":
        bright = _highpass_noise(noise, 41)
        smooth = noise - bright
        spectral = bright * (1.0 - progress) + smooth * progress
        signal = spectral * np.power(1.0 - progress, 1.35).astype(np.float32)
    elif generator == "impact_v1":
        freq = 92.0 - 48.0 * progress
        body = np.sin(_phase_from_frequency(freq, sample_rate)) * np.exp(-t * 7.0)
        transient = _highpass_noise(noise, 15) * np.exp(-t * 32.0)
        tail = _highpass_noise(rng.standard_normal(n).astype(np.float32), 45) * np.exp(-t * 4.5)
        signal = 0.60 * body + 0.30 * transient + 0.10 * tail
    else:  # reverse_cymbal_v1
        bright = _highpass_noise(noise, 37)
        metallic = (
            np.sin(2.0 * np.pi * 4871.0 * t)
            + 0.7 * np.sin(2.0 * np.pi * 7349.0 * t + 0.5)
        ).astype(np.float32)
        signal = (0.72 * bright + 0.28 * metallic) * np.power(progress, 1.9).astype(np.float32)

    signal = _bounded(signal, level)
    if generator in {"kick_v1", "snare_v1", "clap_v1", "closed_hat_v1", "open_hat_v1", "impact_v1"}:
        signal = _apply_edge_envelope(signal, sample_rate, 0.0015, min(0.025, duration * 0.20))
    else:
        signal = _apply_edge_envelope(signal, sample_rate, 0.004, min(0.04, duration * 0.10))
    if not np.isfinite(signal).all() or float(np.max(np.abs(signal))) > float(level) + 1e-6:
        raise RuntimeError("procedural generator violated finite/peak safety")
    if channels == 1:
        return signal.astype(np.float32)
    return np.column_stack([signal, signal]).astype(np.float32)


def render_performance_sample_layer(
    base_audio: np.ndarray,
    sample_rate: int,
    events: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    output_start_sample: int = 0,
    peak_ceiling: float = 0.95,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Mix compiled procedural events onto a transition buffer deterministically."""
    base = np.asarray(base_audio, dtype=np.float32)
    was_mono = base.ndim == 1
    if was_mono:
        work = base[:, None]
    elif base.ndim == 2 and base.shape[1] in {1, 2}:
        work = base.copy()
    else:
        raise ValueError("base_audio must be mono or stereo")
    if not np.isfinite(work).all():
        raise ValueError("base_audio contains non-finite samples")
    if not 0.1 <= float(peak_ceiling) <= 1.0:
        raise ValueError("peak_ceiling must be in [0.1, 1.0]")

    layer = np.zeros_like(work, dtype=np.float32)
    provenance: list[dict[str, Any]] = []
    ordered = sorted(events, key=lambda item: (float(item.get("time_sec", 0.0)), str(item.get("event_id", ""))))
    for raw_event in ordered:
        event_model = PerformanceSampleEvent.from_dict(raw_event)
        event_errors = event_model.validate()
        if event_errors:
            raise ValueError("invalid sample event: " + "; ".join(event_errors))
        event = event_model.to_dict()
        generator = str(event.get("generator", ""))
        if generator not in SUPPORTED_PROCEDURAL_GENERATORS:
            raise ValueError(f"unsupported procedural generator: {generator}")
        start = int(round(float(event.get("time_sec", -1.0)) * sample_rate))
        duration_sec = float(event.get("duration_sec", 0.0))
        if start < 0 or duration_sec <= 0.0:
            raise ValueError("sample event has invalid time or duration")
        level = float(event.get("level", 0.0)) * float(event.get("velocity", 1.0))
        gain_db = float(event.get("gain_db", 0.0))
        if not 0.0 < level <= 0.05 or not -24.0 <= gain_db <= 0.0:
            raise ValueError("sample event gain is outside safe bounds")
        sound = synthesize_procedural_sound(
            generator,
            sample_rate,
            duration_sec=duration_sec,
            level=level,
            seed=int(event.get("seed", 0)),
            channels=work.shape[1],
        )
        envelope = dict(event.get("envelope", {}) or {})
        attack_sec = float(envelope.get("attack_sec", 0.0))
        release_sec = float(envelope.get("release_sec", 0.0))
        if attack_sec < 0.0 or release_sec < 0.0 or attack_sec + release_sec > duration_sec + 1e-9:
            raise ValueError("sample event envelope is outside event duration")
        if attack_sec or release_sec:
            if sound.ndim == 1:
                sound = _apply_edge_envelope(sound, sample_rate, attack_sec, release_sec)
            else:
                for channel in range(sound.shape[1]):
                    sound[:, channel] = _apply_edge_envelope(sound[:, channel], sample_rate, attack_sec, release_sec)
        sound = np.asarray(sound, dtype=np.float32) * db_to_linear(gain_db)
        dc_offset = float(np.max(np.abs(np.mean(sound, axis=0)))) if sound.size else 0.0
        if dc_offset > max(0.005, level * 0.35):
            raise RuntimeError("sample event produced unsafe DC offset")
        end = start + len(sound)
        if end > len(layer):
            raise ValueError("sample event extends beyond transition buffer")
        if float(np.max(np.abs(sound))) <= 1e-8:
            raise RuntimeError("valid sample event rendered accidental silence")
        layer[start:end] += sound
        provenance.append({
            "source_type": str(event.get("source_type", "")),
            "operation_owner": "groove_sample_layer",
            "generator": generator,
            "seed": int(event.get("seed", 0)),
            "event_id": str(event.get("event_id", "")),
            "recipe_id": str(event.get("recipe_id", "")),
            "action_id": str(event.get("action_id", "")),
            "pattern_id": str(event.get("pattern_id", "")),
            "musical_position": dict(event.get("musical_position", {}) or {}),
            "subdivision": int(event.get("subdivision", 1)),
            "declared_provenance": dict(event.get("provenance", {}) or {}),
            "safety": dict(event.get("safety", {}) or {}),
            "output_start_sample": output_start_sample + start,
            "output_end_sample": output_start_sample + end,
            "level": float(event.get("level", 0.0)),
            "velocity": float(event.get("velocity", 1.0)),
            "gain_db": gain_db,
        })

    layer_peak = float(np.max(np.abs(layer))) if layer.size else 0.0
    layer_scale = 1.0
    if layer_peak > 0.35:
        layer_scale = 0.35 / layer_peak
        layer *= layer_scale
    mixed = work + layer
    mixed_peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    safety_gain = 1.0
    if mixed_peak > peak_ceiling:
        safety_gain = float(peak_ceiling) / mixed_peak
        mixed *= safety_gain
    if not np.isfinite(mixed).all() or float(np.max(np.abs(mixed))) > peak_ceiling + 1e-6:
        raise RuntimeError("sample layer violated output safety")
    for item in provenance:
        item["layer_scale"] = round(layer_scale, 9)
        item["safety_gain"] = round(safety_gain, 9)
    if was_mono:
        return mixed[:, 0].astype(np.float32), provenance
    return mixed.astype(np.float32), provenance
