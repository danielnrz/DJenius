"""Small deterministic creative transition operations.

These helpers are deliberately bounded and shape-preserving. They operate
only on already-declared transition audio and never read arbitrary files.
"""

from __future__ import annotations

import numpy as np


def _stereo(audio: np.ndarray) -> tuple[np.ndarray, bool]:
    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        return array[:, None], True
    if array.ndim != 2:
        raise ValueError("creative FX audio must be one- or two-dimensional")
    return array, False


def tape_stop(audio: np.ndarray, strength: float = 0.7) -> np.ndarray:
    """Slow the final part of a region while preserving output length.

    This is a controlled creative resampling effect, not a beatmatching
    operation. The admitted strength range is intentionally narrow.
    """
    data, was_mono = _stereo(audio)
    if len(data) < 8:
        return np.asarray(audio, dtype=np.float32)
    strength = float(np.clip(strength, 0.0, 1.0))
    output_axis = np.linspace(0.0, 1.0, len(data), dtype=np.float64)
    source_axis = 1.0 - np.power(1.0 - output_axis, 1.0 + 1.6 * strength)
    indices = source_axis * (len(data) - 1)
    result = np.column_stack([
        np.interp(indices, np.arange(len(data)), data[:, channel])
        for channel in range(data.shape[1])
    ]).astype(np.float32)
    # A gentle tail fade prevents a held final sample from becoming a click.
    tail = max(2, min(len(result) // 8, 2048))
    result[-tail:] *= np.linspace(1.0, 0.0, tail, dtype=np.float32)[:, None]
    return result[:, 0] if was_mono else result


def loop_roll(audio: np.ndarray, sample_rate: int, bpm: float, *, beats: int = 1, repeats: int = 2) -> np.ndarray:
    """Repeat a bounded final beat/phrase with treated wraparound seams.

    The operation remains shape-preserving and operates only on the already
    declared transition buffer.  Every repeat boundary receives a short
    overlap blend; this is deliberately a loop-construction improvement, not
    a new effect or an implicit source replay.
    """
    data, was_mono = _stereo(audio)
    if len(data) < 32 or sample_rate <= 0 or bpm <= 0:
        return np.asarray(audio, dtype=np.float32)
    beat_samples = max(16, int(round(sample_rate * 60.0 / bpm)))
    loop_length = min(len(data) // 3, beat_samples * max(1, min(4, int(beats))))
    if loop_length < 16:
        return np.asarray(audio, dtype=np.float32)
    repeats = max(1, min(3, int(repeats)))
    result = data.copy()
    start = max(0, len(data) - loop_length * repeats)
    loop = data[max(0, len(data) - loop_length):]
    for position in range(start, len(data), loop_length):
        count = min(loop_length, len(data) - position)
        result[position:position + count] = loop[:count]
    guard = min(loop_length // 8, max(2, int(round(sample_rate * 0.012))))
    guard = min(guard, loop_length // 4, len(result) // 10)
    if guard >= 2:
        fade_in = np.linspace(0.0, 1.0, guard, dtype=np.float32)[:, None]
        fade_out = 1.0 - fade_in
        for repeat_index in range(repeats):
            seam = start + repeat_index * loop_length
            if seam >= len(result):
                break
            pre_start = max(0, seam - guard)
            count = min(guard, seam - pre_start)
            if count <= 1 or seam + count > len(result):
                continue
            left = result[pre_start:seam].copy()
            right = loop[:count]
            # Crossfade over the final part of the previous cycle, then
            # continue with the loop interior.  This keeps the audio after
            # the seam at its original musical position while ensuring that
            # the first sample after the boundary is not a phase jump.
            result[pre_start:seam] = left * fade_out[:count] + right * fade_in[:count]
            interior_end = min(len(result), seam + count)
            interior_count = interior_end - seam
            if interior_count > 0:
                result[seam:interior_end] = loop[count:count + interior_count]
    return result[:, 0] if was_mono else result


def procedural_fx(
    length: int,
    sample_rate: int,
    effect: str,
    *,
    level: float = 0.02,
    seed: int = 0,
    channels: int = 2,
) -> np.ndarray:
    """Generate a subtle stereo riser or impact without external assets."""
    if length <= 0 or sample_rate <= 0:
        return np.zeros((max(0, length), channels), dtype=np.float32)
    rng = np.random.default_rng(int(seed))
    noise = rng.standard_normal(length).astype(np.float32)
    noise /= max(float(np.max(np.abs(noise))), 1e-6)
    progress = np.linspace(0.0, 1.0, length, dtype=np.float32)
    if effect == "impact":
        envelope = np.exp(-progress * 18.0) * (0.75 + 0.25 * np.cos(progress * np.pi))
        tone = np.sin(2.0 * np.pi * 72.0 * np.arange(length) / sample_rate).astype(np.float32)
        signal = 0.55 * tone + 0.45 * noise
    elif effect == "downlifter":
        envelope = np.exp(-progress * 5.0)
        signal = noise
    else:
        envelope = np.power(progress, 1.7)
        signal = noise
    signal = signal * envelope.astype(np.float32) * float(np.clip(level, 0.0, 0.05))
    if channels == 1:
        return signal[:, None]
    stereo = np.column_stack([signal, signal * 0.985]).astype(np.float32)
    return stereo


def apply_creative_operations(
    source: np.ndarray,
    result: np.ndarray,
    *,
    sample_rate: int,
    source_bpm: float,
    operations: list[dict] | None,
) -> tuple[np.ndarray, list[dict]]:
    """Apply declared operations and return transformed audio plus audit."""
    transformed = np.asarray(source, dtype=np.float32)
    generated: list[dict] = []
    for operation in operations or []:
        kind = str(operation.get("type", ""))
        if kind == "tape_stop":
            transformed = tape_stop(transformed, operation.get("strength", 0.7))
        elif kind == "loop_roll":
            loop_bars = operation.get("bars")
            loop_beats = (
                max(1, int(round(float(loop_bars) * 4.0)))
                if loop_bars is not None else operation.get("beats", 1)
            )
            transformed = loop_roll(
                transformed, sample_rate, source_bpm,
                beats=loop_beats, repeats=operation.get("repeats", 2),
            )
        elif kind == "generated_fx":
            fx = procedural_fx(
                len(result), sample_rate, str(operation.get("effect", "riser")),
                level=float(operation.get("level", 0.02)),
                seed=int(operation.get("seed", 0)),
                channels=result.shape[1] if result.ndim == 2 else 1,
            )
            if result.ndim == 1 and fx.ndim == 2:
                fx = fx[:, 0]
            result = result + fx
            generated.append({
                "source_type": "generated_fx",
                "effect_type": str(operation.get("effect", "riser")),
                "seed": int(operation.get("seed", 0)),
                "duration_samples": len(result),
                "level": float(operation.get("level", 0.02)),
            })
    return transformed, generated
