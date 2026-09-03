"""Rendered, source-declared preparation operations for segment handoffs."""

from __future__ import annotations

import numpy as np


def _as_stereo(audio: np.ndarray) -> np.ndarray:
    data = np.asarray(audio, dtype=np.float32)
    if data.ndim == 1:
        return np.column_stack([data, data])
    if data.ndim != 2 or data.shape[1] not in {1, 2}:
        raise ValueError("preparation audio must be mono or stereo")
    return np.repeat(data, 2, axis=1) if data.shape[1] == 1 else data.copy()


def _lowpass(audio: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    """A bounded one-pole low-pass used only for gentle low-end automation."""
    data = _as_stereo(audio)
    cutoff = float(np.clip(cutoff_hz, 40.0, sample_rate * 0.40))
    alpha = float(np.exp(-2.0 * np.pi * cutoff / max(sample_rate, 1)))
    result = np.empty_like(data)
    for channel in range(2):
        previous = 0.0
        for index, value in enumerate(data[:, channel]):
            previous = (1.0 - alpha) * float(value) + alpha * previous
            result[index, channel] = previous
    return result


def apply_bass_automation(
    audio: np.ndarray,
    sample_rate: int,
    start_db: float,
    end_db: float,
    cutoff_hz: float = 180.0,
) -> np.ndarray:
    """Automate only the low band, preserving the source's upper content."""
    data = _as_stereo(audio)
    if len(data) == 0:
        return data
    low = _lowpass(data, sample_rate, cutoff_hz)
    high = data - low
    gain_db = np.linspace(float(start_db), float(end_db), len(data), dtype=np.float32)
    gain = np.power(10.0, gain_db / 20.0)[:, None]
    return (high + low * gain).astype(np.float32)


def apply_filter_automation(
    audio: np.ndarray,
    sample_rate: int,
    mode: str,
    start_hz: float,
    end_hz: float,
) -> np.ndarray:
    """Apply a gentle continuously changing low/high-pass envelope."""
    data = _as_stereo(audio)
    if len(data) == 0:
        return data
    # A sample-by-sample varying IIR cutoff is needlessly opaque.  Two short
    # filtered versions and a linear blend provide a stable, audible sweep.
    start = _lowpass(data, sample_rate, start_hz)
    end = _lowpass(data, sample_rate, end_hz)
    progress = np.linspace(0.0, 1.0, len(data), dtype=np.float32)[:, None]
    low = start * (1.0 - progress) + end * progress
    if str(mode).lower() == "lowpass":
        return low.astype(np.float32)
    return (data - low).astype(np.float32)


def render_preparation(
    audio: np.ndarray,
    sample_rate: int,
    operations: list[dict] | None,
) -> tuple[np.ndarray, list[dict]]:
    """Transform one already-declared pre-boundary source window.

    The returned audit contains no source coordinates because the caller owns
    the output/source mapping.  Unknown operations are declined rather than
    silently inventing DSP.
    """
    transformed = _as_stereo(audio)
    audit: list[dict] = []
    for operation in operations or []:
        kind = str(operation.get("type", ""))
        if kind == "bass_automation":
            transformed = apply_bass_automation(
                transformed,
                sample_rate,
                float(operation.get("start_db", 0.0)),
                float(operation.get("end_db", -6.0)),
                float(operation.get("cutoff_hz", 180.0)),
            )
        elif kind == "filter_automation":
            transformed = apply_filter_automation(
                transformed,
                sample_rate,
                str(operation.get("mode", "highpass")),
                float(operation.get("start_hz", 20.0)),
                float(operation.get("end_hz", 150.0)),
            )
        elif kind == "generated_fx":
            from djenius.audio.creative_fx import procedural_fx

            fx = procedural_fx(
                len(transformed),
                sample_rate,
                str(operation.get("effect", "riser")),
                level=float(operation.get("level", 0.012)),
                seed=int(operation.get("seed", 0)),
                channels=2,
            )
            transformed = transformed + fx
            audit.append({
                "source_type": "generated_fx",
                "effect_type": str(operation.get("effect", "riser")),
                "seed": int(operation.get("seed", 0)),
                "level": float(operation.get("level", 0.012)),
            })
        elif kind == "target_percussion_tease":
            # This needs cached target stems and is applied by the performance
            # renderer, where target source coordinates are available.
            continue
        else:
            raise ValueError(f"unknown preparation operation: {kind}")
    return transformed, audit
