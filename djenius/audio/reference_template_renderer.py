"""Renderer for explicitly requested, human-reference-backed templates.

The renderer is intentionally outside autonomous selection.  It executes the
four frozen choreography contracts in ``core.reference_templates`` while
preserving coherent target timing, declared bass ownership, and bounded FX
tails across the landing.
"""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy import signal as scipy_signal

from djenius.audio.groove_sampler import synthesize_procedural_sound
from djenius.core.models import TrackAnalysis
from djenius.core.reference_templates import ReferenceArchetype, ReferenceTemplateInstance
from djenius.utils.audio_math import normalize_lufs, soft_clip


REFERENCE_RENDERER_VERSION = "reference-template-renderer-1"
SEAM_SAMPLES = 128


@dataclass(frozen=True)
class ReferenceRenderInputs:
    source_audio: np.ndarray
    target_audio: np.ndarray
    source_stems: dict[str, np.ndarray]
    target_stems: dict[str, np.ndarray]
    source_analysis: TrackAnalysis
    target_analysis: TrackAnalysis
    sample_rate: int = 44100


@dataclass(frozen=True)
class RenderedReferenceTemplate:
    audio: np.ndarray
    sample_rate: int
    landing_sample: int
    provenance: dict[str, Any]

    @property
    def landing_sec(self) -> float:
        return self.landing_sample / self.sample_rate


def _stereo(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    if values.ndim == 1:
        return np.column_stack([values, values]).astype(np.float32)
    if values.ndim != 2 or values.shape[1] not in {1, 2}:
        raise ValueError("reference-template audio must be mono or stereo")
    return np.repeat(values, 2, axis=1) if values.shape[1] == 1 else values


def _fit(audio: np.ndarray, length: int) -> np.ndarray:
    values = _stereo(audio)
    if len(values) >= length:
        return values[:length]
    return np.pad(values, ((0, length - len(values)), (0, 0)))


def _repeat_fit(audio: np.ndarray, length: int) -> np.ndarray:
    values = _stereo(audio)
    if not len(values):
        return np.zeros((length, 2), dtype=np.float32)
    copies = int(np.ceil(length / len(values)))
    return np.tile(values, (copies, 1))[:length].astype(np.float32)


def _dbfs(audio: np.ndarray) -> float:
    values = np.asarray(audio, dtype=np.float64)
    return float(20 * np.log10(np.sqrt(np.mean(values * values) + 1e-20)))


def _filter(audio: np.ndarray, cutoff_hz: float, sample_rate: int, kind: str) -> np.ndarray:
    values = _stereo(audio)
    nyquist = sample_rate / 2
    cutoff = min(max(20.0, cutoff_hz), nyquist * .90)
    if cutoff <= 20.0 or len(values) < 32:
        return values.copy()
    sos = scipy_signal.butter(3, cutoff / nyquist, btype=kind, output="sos")
    try:
        return scipy_signal.sosfiltfilt(sos, values, axis=0).astype(np.float32)
    except ValueError:
        return scipy_signal.sosfilt(sos, values, axis=0).astype(np.float32)


def _lowpass(audio: np.ndarray, cutoff_hz: float, sample_rate: int) -> np.ndarray:
    return _filter(audio, cutoff_hz, sample_rate, "lowpass")


def _highpass(audio: np.ndarray, cutoff_hz: float, sample_rate: int) -> np.ndarray:
    return _filter(audio, cutoff_hz, sample_rate, "highpass")


def _three_bands(audio: np.ndarray, sample_rate: int, low_hz: float = 155, high_hz: float = 3000):
    values = _stereo(audio)
    low = _lowpass(values, low_hz, sample_rate)
    high = _highpass(values, high_hz, sample_rate)
    return low, (values - low - high).astype(np.float32), high


def _cosine_envelope(bar_axis: np.ndarray, points: list[tuple[float, float]]) -> np.ndarray:
    result = np.full(len(bar_axis), points[-1][1], dtype=np.float32)
    result[bar_axis <= points[0][0]] = points[0][1]
    for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
        mask = (bar_axis >= x0) & (bar_axis <= x1)
        if x1 == x0:
            result[mask] = y1
        else:
            phase = (bar_axis[mask] - x0) / (x1 - x0)
            result[mask] = y0 + (y1 - y0) * (.5 - .5 * np.cos(np.pi * phase))
    return result[:, None]


def coherent_time_fit(
    bundle: dict[str, np.ndarray],
    output_length: int,
    sample_rate: int,
    *,
    backend: str = "auto",
) -> tuple[dict[str, np.ndarray], str]:
    """Fit master/stems together under one render clock.

    Stacking all signals into one multichannel operation is the permanent B7
    structural fix: a master and stems may never launch independent adaptive
    stretch jobs when they later meet at a splice.
    """
    if not bundle or output_length <= 0 or sample_rate <= 0:
        raise ValueError("coherent time fit requires audio, length, and sample rate")
    return _coherent_fit_preserve_channels(bundle, output_length, sample_rate, backend)


def _coherent_fit_preserve_channels(
    bundle: dict[str, np.ndarray], output_length: int, sample_rate: int, backend: str,
) -> tuple[dict[str, np.ndarray], str]:
    """Internal wrapper avoiding stereo coercion after the shared operation."""
    names = tuple(bundle)
    values = [_stereo(bundle[name]) for name in names]
    common = min(len(item) for item in values)
    stacked = np.column_stack([item[:common, ch] for item in values for ch in range(2)])
    if not common or output_length <= 0:
        raise ValueError("coherent target bundle is empty")
    rendered = None
    used = ""
    rate = common / output_length
    if backend in {"auto", "ffmpeg"} and .5 <= rate <= 2.0:
        try:
            with tempfile.TemporaryDirectory(prefix="djenius-reference-clock-") as tmp:
                source, target = Path(tmp) / "source.wav", Path(tmp) / "target.wav"
                sf.write(source, stacked, sample_rate, subtype="FLOAT")
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
                     "-filter:a", f"atempo={rate:.9f}", "-c:a", "pcm_f32le",
                     "-ar", str(sample_rate), str(target)],
                    check=True, capture_output=True, timeout=60,
                )
                rendered, rendered_sr = sf.read(target, dtype="float32", always_2d=True)
            if rendered_sr != sample_rate or rendered.shape[1] != stacked.shape[1]:
                rendered = None
            else:
                used = "ffmpeg_atempo_shared_multichannel"
        except (OSError, subprocess.SubprocessError, RuntimeError):
            if backend == "ffmpeg":
                raise ValueError("shared FFmpeg time fit failed")
    if rendered is None:
        rendered = scipy_signal.resample(stacked, output_length, axis=0).astype(np.float32)
        used = "scipy_shared_multichannel_fallback"
    if len(rendered) < output_length:
        rendered = np.pad(rendered, ((0, output_length - len(rendered)), (0, 0)))
    rendered = rendered[:output_length]
    return {
        name: rendered[:, index * 2:(index + 1) * 2].astype(np.float32)
        for index, name in enumerate(names)
    }, used


def _strongest_capture(audio: np.ndarray, start: int, end: int, width: int) -> tuple[np.ndarray, int]:
    values = _stereo(audio)
    start, end = max(0, start), min(len(values), end)
    width = max(1, min(width, end - start))
    hop = max(1, width // 15)
    best, best_energy = start, -1.0
    mono = np.mean(values, axis=1)
    for position in range(start, max(start + 1, end - width + 1), hop):
        energy = float(np.mean(mono[position:position + width].astype(np.float64) ** 2))
        if energy > best_energy:
            best, best_energy = position, energy
    capture = values[best:best + width].copy()
    fade = min(256, len(capture))
    if fade:
        capture[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)[:, None]
    return capture, best


def _edge_fade(audio: np.ndarray, sample_rate: int, fade_in_ms: float = 3, fade_out_ms: float = 8) -> np.ndarray:
    result = _stereo(audio).copy()
    left = min(len(result), int(round(fade_in_ms * sample_rate / 1000)))
    right = min(len(result), int(round(fade_out_ms * sample_rate / 1000)))
    if left:
        result[:left] *= np.sin(np.linspace(0, np.pi / 2, left, dtype=np.float32))[:, None]
    if right:
        result[-right:] *= np.cos(np.linspace(0, np.pi / 2, right, dtype=np.float32))[:, None]
    return result


def _diffuse_echo(capture: np.ndarray, sample_rate: int, cutoff: float, gain: float, side: int) -> np.ndarray:
    tap = _lowpass(capture, cutoff, sample_rate) * gain
    result = tap.copy()
    delay_a, delay_b = int(.017 * sample_rate), int(.031 * sample_rate)
    if len(tap) > delay_a:
        result[delay_a:, side] += tap[:-delay_a, side] * .24
    if len(tap) > delay_b:
        result[delay_b:, 1 - side] += tap[:-delay_b, 1 - side] * .14
    result[:, 1 - side] *= .68
    return _edge_fade(result, sample_rate)


def _assemble(pre: np.ndarray, transition: np.ndarray, after: np.ndarray, overlay: np.ndarray | None = None):
    seam = min(SEAM_SAMPLES, len(transition), len(after))
    angle = np.linspace(0, np.pi / 2, seam, dtype=np.float32)
    fade_out, fade_in = np.cos(angle), np.sin(angle)
    boundary = transition[-seam:] * fade_out[:, None] + after[:seam] * fade_in[:, None]
    audio = np.concatenate([pre, transition[:-seam], boundary, after[seam:]]).astype(np.float32)
    landing = len(pre) + len(transition) - seam
    if overlay is not None:
        audio += _fit(overlay, len(audio))
    return audio, landing


def _master(audio: np.ndarray, sample_rate: int, target_lufs: float) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    try:
        values = normalize_lufs(values, sample_rate, target_lufs)
    except Exception:
        rms = np.sqrt(np.mean(values.astype(np.float64) ** 2) + 1e-20)
        values = values * min(4.0, 10 ** ((-18 - 20 * np.log10(rms + 1e-20)) / 20))
    values = soft_clip(values, threshold_db=-1.0).astype(np.float32)
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    if peak > .95:
        values *= .95 / peak
    return values.astype(np.float32)


def _validate_inputs(instance: ReferenceTemplateInstance, inputs: ReferenceRenderInputs) -> None:
    if inputs.sample_rate < 1000:
        raise ValueError("reference-template sample rate must be at least 1000 Hz")
    for role, audio in (("source", inputs.source_audio), ("target", inputs.target_audio)):
        values = _stereo(audio)
        if not len(values) or not np.isfinite(values).all():
            raise ValueError(f"{role} audio is empty or non-finite")
    for role, stems, required in (
        ("source", inputs.source_stems, instance.definition.required_source_stems),
        ("target", inputs.target_stems, instance.definition.required_target_stems),
    ):
        missing = set(required) - set(stems)
        if missing:
            raise ValueError(f"{role} renderer stems missing: {','.join(sorted(missing))}")


def _material(instance: ReferenceTemplateInstance, inputs: ReferenceRenderInputs, backend: str):
    sr = inputs.sample_rate
    anchors = instance.anchors
    source_grid = np.asarray(inputs.source_analysis.downbeat_times or inputs.source_analysis.bar_times, dtype=float)
    target_grid = np.asarray(inputs.target_analysis.downbeat_times or inputs.target_analysis.bar_times, dtype=float)
    s0, s1 = anchors.source_start_bar_index, anchors.source_end_bar_index
    source_bounds_abs = np.round(source_grid[s0:s1 + 1] * sr).astype(int)
    source_start, source_end = int(source_bounds_abs[0]), int(source_bounds_abs[-1])
    bounds = source_bounds_abs - source_start
    n = source_end - source_start
    pre_index = max(0, s0 - 4)
    pre = _stereo(inputs.source_audio)[int(round(source_grid[pre_index] * sr)):source_start]
    source_live = _stereo(inputs.source_audio)[source_start:source_end]
    source_stems = {
        name: _fit(_stereo(audio)[source_start:source_end], n)
        for name, audio in inputs.source_stems.items()
    }
    t0, t1, t2 = (
        anchors.target_runway_bar_index,
        anchors.target_landing_bar_index,
        anchors.target_post_end_bar_index,
    )
    target_start = int(round(target_grid[t0] * sr))
    target_landing = int(round(target_grid[t1] * sr))
    target_end = int(round(target_grid[t2] * sr))
    post_length = (
        n
        if instance.definition.postlanding_bars == instance.definition.transition_bars
        else int(round(float(np.median(np.diff(bounds))) * instance.definition.postlanding_bars))
    )
    target_bundle = {"master": _stereo(inputs.target_audio)[target_start:target_end]}
    target_bundle.update({
        name: _stereo(audio)[target_start:target_end]
        for name, audio in inputs.target_stems.items()
    })
    fitted, clock_backend = _coherent_fit_preserve_channels(
        target_bundle, n + post_length, sr, backend,
    )
    raw_after = _stereo(inputs.target_audio)[target_landing:target_end]
    trim_db = float(np.clip(_dbfs(source_live) - _dbfs(raw_after), -3.0, 7.0))
    trim = 10 ** (trim_db / 20)
    fitted = {name: values * trim for name, values in fitted.items()}
    intro = {name: values[:n] for name, values in fitted.items()}
    after = {name: values[n:] for name, values in fitted.items()}
    axis = np.interp(np.arange(n), bounds.astype(float), np.arange(len(bounds), dtype=float))
    return {
        "pre": pre,
        "source": source_live,
        "source_stems": source_stems,
        "target_intro": intro,
        "target_after": after,
        "bounds": bounds,
        "axis": axis,
        "n": n,
        "bar_samples": int(round(float(np.median(np.diff(bounds))))),
        "trim_db": trim_db,
        "clock_backend": clock_backend,
        "target_input_duration_sec": (target_end - target_start) / sr,
        "target_output_duration_sec": (n + post_length) / sr,
    }


def _render_c3(instance: ReferenceTemplateInstance, inputs: ReferenceRenderInputs, backend: str):
    m, sr = _material(instance, inputs, backend), inputs.sample_rate
    src, stems, target_intro, target_after = m["source"], m["source_stems"], m["target_intro"], m["target_after"]
    axis, bounds, n = m["axis"], m["bounds"], m["n"]
    source_low = _lowpass(src, 155, sr)
    source_drums = _highpass(stems["drums"], 155, sr)
    source_other = _highpass(stems["other"], 155, sr)
    source_vocal = _highpass(stems["vocals"], 170, sr)
    drum_trim = 10 ** (min(m["trim_db"], 3.2) / 20)
    target_drums = _repeat_fit(target_after["drums"][:bounds[4]] / (10 ** (m["trim_db"] / 20)) * drum_trim, n)
    target_low = _repeat_fit(_lowpass(target_after["master"][:bounds[2]], 155, sr), n)
    trim = 10 ** (m["trim_db"] / 20)
    target_upper = _highpass(target_intro["other"] / trim, 170, sr) * 2.4
    def env(points):
        return _cosine_envelope(axis, points)
    transition = (
        source_drums * env([(0, 1), (1, .92), (2.5, .66), (4, .26), (4.6, 0), (8, 0)])
        + source_other * env([(0, 1), (3, 1), (4.35, .62), (5.3, 0), (8, 0)])
        + source_vocal * env([(0, 1), (5.5, 1), (6.45, .82), (6.88, 0), (8, 0)])
        + source_low * env([(0, 1), (4, 1), (4.5, 0), (8, 0)])
        + target_drums * env([(0, .05), (1, .12), (2.5, .30), (4, .55), (5.3, .72), (7, .84), (8, .90)])
        + target_low * env([(0, 0), (4, 0), (4.5, .97), (8, 1)])
        + target_upper * env([(0, 0), (2, .04), (4, .16), (5.5, .34), (7, .62), (8, .88)])
    ).astype(np.float32)
    search_start = int(np.interp(6.0, np.arange(len(bounds)), bounds))
    search_end = int(np.interp(6.78, np.arange(len(bounds)), bounds))
    capture, capture_pos = _strongest_capture(source_vocal, search_start, search_end, int(round(.30 * sr)))
    echo_end = 0
    for number, (bar, gain, cutoff) in enumerate(((6.92, .54, 5600), (7.20, .37, 4700), (7.47, .25, 3900), (7.73, .15, 3100))):
        tap = _diffuse_echo(capture, sr, cutoff, gain, number % 2)
        start = int(np.interp(bar, np.arange(len(bounds)), bounds))
        count = min(len(tap), n - start)
        transition[start:start + count] += tap[:count]
        echo_end = max(echo_end, start + count)
    raw, landing = _assemble(m["pre"], transition, target_after["master"])
    return raw, landing, m, {
        "capture_bar": round(float(np.interp(capture_pos, bounds, np.arange(len(bounds)))), 4),
        "fx_tail_end_sec_relative_landing": round((echo_end - n) / sr, 6),
        "target_vocal_before_landing": False,
    }


def _human_loop(source_backing: np.ndarray, m: dict, sr: int) -> np.ndarray:
    bounds, axis, n = m["bounds"], m["axis"], m["n"]
    motif = _highpass(source_backing[bounds[1]:bounds[2]], 260, sr)
    result = np.zeros((n, 2), dtype=np.float32)
    for start_bar, end_bar, divisor in ((4.0, 6.0, 1), (6.0, 7.0, 2), (7.0, 7.78, 4)):
        start = int(np.interp(start_bar, np.arange(len(bounds)), bounds))
        end = int(np.interp(end_bar, np.arange(len(bounds)), bounds))
        result[start:end] = _repeat_fit(motif[:max(1, len(motif) // divisor)], end - start)
    gain = _cosine_envelope(axis, [(0, 0), (4, 0), (4.22, .90), (6, .98), (7, 1.12), (7.55, 1.25), (7.78, 1.18), (7.94, 0), (8, 0)])
    return (result * gain).astype(np.float32)


def _b8_continuous_loop_tail(m: dict, source_backing: np.ndarray, original_loop: np.ndarray, output_length: int, landing: int, end: int, sr: int):
    bounds = m["bounds"]
    stage_start = int(np.interp(7.0, np.arange(len(bounds)), bounds))
    extension_start = int(np.interp(7.78, np.arange(len(bounds)), bounds))
    global_stage = len(m["pre"]) + stage_start
    global_extension = len(m["pre"]) + extension_start
    raw_motif = source_backing[bounds[1]:bounds[2]]
    original_pattern = _highpass(raw_motif, 260, sr)[:max(1, len(raw_motif) // 4)]
    treated_pattern = _lowpass(_highpass(raw_motif, 520, sr), 5200, sr)[:len(original_pattern)]
    original = _repeat_fit(original_pattern, max(1, end - global_stage))
    treated = _repeat_fit(treated_pattern, max(1, end - global_stage))
    local_start, count = global_extension - global_stage, max(0, end - global_extension)
    morph = min(count, int(round(.012 * sr)))
    treatment = np.ones(count, dtype=np.float32)
    if morph:
        treatment[:morph] = np.sin(np.linspace(0, np.pi / 2, morph, dtype=np.float32)) ** 2
    continuation = original[local_start:local_start + count] * (1 - treatment[:, None]) + treated[local_start:local_start + count] * treatment[:, None]
    if count:
        prior, correction_count = original_loop[extension_start - 1], min(count, int(round(.012 * sr)))
        correction = np.cos(np.linspace(0, np.pi / 2, correction_count, dtype=np.float32)) ** 2
        continuation[:correction_count] += (prior / 1.18 - continuation[0]) * correction[:, None]
    tail = np.zeros((output_length, 2), dtype=np.float32)
    guard = min(int(round(.012 * sr)), extension_start)
    replacement_start = extension_start - guard
    ramp = np.sin(np.linspace(0, np.pi / 2, guard, dtype=np.float32)) ** 2
    tail[len(m["pre"]) + replacement_start:global_extension] = original_loop[replacement_start:extension_start] * ramp[:, None]
    if count:
        landing_gain = np.ones(count, dtype=np.float32)
        before = max(0, landing - global_extension)
        if before:
            landing_gain[:before] = np.linspace(1.18, .46, before, endpoint=False, dtype=np.float32)
        after = max(0, end - landing)
        if after:
            landing_gain[before:] = .46 * (np.cos(np.linspace(0, np.pi / 2, after, endpoint=False, dtype=np.float32)) ** 2)
        tail[global_extension:end] = continuation * landing_gain[:, None]
    remove = np.zeros((m["n"], 1), dtype=np.float32)
    remove[replacement_start:extension_start, 0] = ramp
    remove[extension_start:, 0] = 1
    return tail, original_loop * remove


def _b8_riser_tail(m: dict, riser: np.ndarray, output_length: int, landing: int, end: int, sr: int):
    dry = np.zeros((output_length, 2), dtype=np.float32)
    start = len(m["pre"])
    dry[start:start + len(riser)] = riser
    wet = np.zeros_like(dry)
    for number, (delay_sec, gain) in enumerate(((.041, .20), (.079, .18), (.137, .15), (.223, .12), (.337, .09), (.499, .06), (.641, .03))):
        delay = int(round(delay_sec * sr))
        shifted = np.zeros_like(dry)
        shifted[delay:] = dry[:-delay]
        shifted[:, number % 2] *= .70
        wet += shifted * gain
    wet = _lowpass(_highpass(wet, 3000, sr), 9000, sr)
    guard = int(round(.012 * sr))
    wet[:landing - guard] = 0
    wet[landing - guard:landing] *= (np.sin(np.linspace(0, np.pi / 2, guard, dtype=np.float32)) ** 2)[:, None]
    wet[landing:end] *= (np.cos(np.linspace(0, np.pi / 2, end - landing, endpoint=False, dtype=np.float32)) ** 2)[:, None]
    wet[end:] = 0
    return (wet * 10).astype(np.float32)


def _render_b8(instance: ReferenceTemplateInstance, inputs: ReferenceRenderInputs, backend: str):
    m, sr = _material(instance, inputs, backend), inputs.sample_rate
    src, stems, ti, ta = m["source"], m["source_stems"], m["target_intro"], m["target_after"]
    axis, bounds, n = m["axis"], m["bounds"], m["n"]
    source_low = _lowpass(src, 155, sr)
    source_upper = src - source_low
    source_vocal = _highpass(stems["vocals"], 170, sr)
    source_backing = source_upper - source_vocal
    loop = _human_loop(source_backing, m, sr)
    def env(points):
        return _cosine_envelope(axis, points)
    source = (
        source_low * env([(0, 1), (4, 1), (4.55, 0), (8, 0)])
        + source_upper * env([(0, 1), (3.7, .96), (4.22, 0), (8, 0)])
        + loop
    )
    riser_start = int(np.interp(6.35, np.arange(len(bounds)), bounds))
    riser = synthesize_procedural_sound("noise_riser_v1", sr, duration_sec=(n - riser_start) / sr, level=.05, seed=2701, channels=2)
    riser_gain = np.interp(axis[riser_start:], [6.35, 6.65, 7.4, 8], [0, .04, .48, 1]).astype(np.float32)[:, None]
    riser_layer = np.zeros_like(source)
    riser_layer[riser_start:] = _fit(riser, n - riser_start) * riser_gain * 7.5
    source += riser_layer
    drum_trim_correction = 10 ** ((min(m["trim_db"], 3.2) - m["trim_db"]) / 20)
    drums = _repeat_fit(ta["drums"][:bounds[4]] * drum_trim_correction, n)
    air, body = _highpass(drums, 3600, sr), None
    body = _highpass(drums, 135, sr) - air
    full2 = _repeat_fit(ta["master"][:bounds[2]], n)
    low = _lowpass(full2, 155, sr)
    trim = 10 ** (m["trim_db"] / 20)
    _, mid, high = _three_bands(_highpass(ti["other"] / trim, 170, sr) * 2.4, sr)
    vocal = _highpass(ti["vocals"], 170, sr)
    target = (
        air * env([(0, 0), (1, .03), (2, .12), (4, .26), (6, .42), (8, .52)])
        + body * env([(0, 0), (3, 0), (3.5, .05), (5, .22), (6.5, .48), (8, .72)])
        + high * env([(0, .02), (2, .11), (4, .26), (6, .50), (8, .80)])
        + mid * env([(0, 0), (2.5, 0), (3.5, .07), (5.5, .30), (7, .62), (8, .86)])
        + vocal * env([(0, 0), (5.2, 0), (5.6, .10), (6.5, .30), (7.4, .58), (8, .82)])
        + low * env([(0, 0), (5.3, 0), (5.65, .24), (6.15, .82), (7, .96), (8, 1)])
    ).astype(np.float32)
    after_gain = np.ones(len(ta["master"]), dtype=np.float32)
    ramp = min(len(after_gain), int(round(.62 * m["bar_samples"])))
    after_gain[:ramp] = .88 + .12 * (.5 - .5 * np.cos(np.linspace(0, np.pi, ramp, dtype=np.float32)))
    after = ta["master"] * after_gain[:, None]
    provisional, landing = _assemble(m["pre"], source + target, after)
    cue = instance.anchors.target_landing_sec
    vocal_starts = [max(0.0, float(left) - cue) for left, right in inputs.target_analysis.vocal_regions if right > cue]
    if not vocal_starts:
        raise ValueError("loop-build template requires a bounded target vocal onset")
    target_input = m["target_input_duration_sec"]
    target_output = m["target_output_duration_sec"]
    vocal_onset = min(vocal_starts) * target_output / target_input
    # Floor rather than round: the declared 20 ms vocal-clearance margin is a
    # hard upper bound, so sample quantization may only shorten the tail.
    release_end = landing + max(1, int(np.floor((vocal_onset - .020) * sr)))
    loop_tail, replaced = _b8_continuous_loop_tail(m, source_backing, loop, len(provisional), landing, release_end, sr)
    source -= replaced
    raw, landing = _assemble(m["pre"], source + target, after)
    riser_tail = _b8_riser_tail(m, riser_layer, len(raw), landing, release_end, sr)
    raw += loop_tail + riser_tail
    return raw, landing, m, {
        "fx_tail_end_sec_relative_landing": round((release_end - landing) / sr, 6),
        "target_vocal_onset_sec_relative_landing": round(vocal_onset, 6),
        "tail_margin_before_target_vocal_sec": .020,
        "loop_state_continuous_at_landing": True,
        "target_low_preview_bars": 2,
    }


def _render_d2(instance: ReferenceTemplateInstance, inputs: ReferenceRenderInputs, backend: str):
    m, sr = _material(instance, inputs, backend), inputs.sample_rate
    src, stems, ti, ta = m["source"], m["source_stems"], m["target_intro"], m["target_after"]
    axis, bounds, n = m["axis"], m["bounds"], m["n"]
    source_vocal = stems["vocals"]
    source_low, source_mid, source_high = _three_bands(src - source_vocal, sr)
    intro_music = (ti["drums"] + ti["other"]) * 1.30
    _, target_mid, target_high = _three_bands(intro_music, sr)
    target_vocal = ti["vocals"]
    target_low = _lowpass(_repeat_fit(ta["master"][:bounds[4]], n), 155, sr)
    target_drum = _highpass(_repeat_fit(ta["drums"][:bounds[4]], n), 155, sr)
    def env(points):
        return _cosine_envelope(axis, points)
    transition = (
        source_low * env([(0, 1), (8, 1), (8.5, 0), (12, 0)])
        + source_mid * env([(0, 1), (4, 1), (6, .88), (8, .66), (9.5, .48), (11.6, .10), (12, 0)])
        + source_high * env([(0, 1), (3, 1), (5, .88), (8, .68), (10, .46), (11.7, .08), (12, 0)])
        + source_vocal * env([(0, 1), (7.7, 1), (8.5, .62), (9.35, 0), (12, 0)])
        + target_high * env([(0, .03), (2, .12), (4, .25), (6, .42), (8, .62), (10, .79), (12, .92)])
        + target_mid * env([(0, 0), (3, 0), (4, .08), (6, .24), (8, .48), (10, .72), (12, .90)])
        + target_low * env([(0, 0), (8, 0), (8.5, .96), (12, 1)])
        + target_drum * env([(0, 0), (7.6, 0), (8.3, .12), (9.3, .38), (10.5, .66), (12, .88)])
        + target_vocal * env([(0, 0), (9, 0), (9.4, .15), (10.4, .52), (12, .90)])
    ).astype(np.float32)
    raw, landing = _assemble(m["pre"], transition, ta["master"])
    return raw, landing, m, {"fx_tail_end_sec_relative_landing": 0.0, "decorative_fx": False}


def _render_f(instance: ReferenceTemplateInstance, inputs: ReferenceRenderInputs):
    sr, anchors = inputs.sample_rate, instance.anchors
    sg = np.asarray(inputs.source_analysis.downbeat_times or inputs.source_analysis.bar_times, dtype=float)
    tg = np.asarray(inputs.target_analysis.downbeat_times or inputs.target_analysis.bar_times, dtype=float)
    s0, s1 = anchors.source_start_bar_index, anchors.source_end_bar_index
    source_start, source_end = int(round(sg[s0] * sr)), int(round(sg[s1] * sr))
    pre = _stereo(inputs.source_audio)[int(round(sg[max(0, s0 - 4)] * sr)):source_start]
    active = _stereo(inputs.source_audio)[source_start:source_end].copy()
    source_vocal = _stereo(inputs.source_stems["vocals"])[source_start:source_end]
    release = min(len(active), int(round(.08 * sr)))
    active[-release:] *= np.linspace(1, 0, release, dtype=np.float32)[:, None]
    target_start = int(round(tg[anchors.target_runway_bar_index] * sr))
    target_land = int(round(tg[anchors.target_landing_bar_index] * sr))
    target_end = int(round(tg[anchors.target_post_end_bar_index] * sr))
    intro = _stereo(inputs.target_audio)[target_start:target_land]
    after = _stereo(inputs.target_audio)[target_land:target_end]
    trim_db = float(np.clip(_dbfs(active) - _dbfs(after), -3, 7))
    trim = 10 ** (trim_db / 20)
    intro, after = intro * trim, after * trim
    reset = intro * np.linspace(0, 1, len(intro), dtype=np.float32)[:, None]
    bounds = np.round(sg[s0:s1 + 1] * sr).astype(int) - source_start
    capture, capture_pos = _strongest_capture(source_vocal, int(bounds[-2]), int(bounds[-1]), int(round(.30 * sr)))
    echo_end = 0
    beat = 60 / inputs.source_analysis.bpm
    for number, gain in enumerate((.62, .43, .30, .20, .12)):
        tap = _lowpass(_highpass(capture, 180, sr), 6200 - number * 650, sr) * gain
        tap[:, 1 if number % 2 == 0 else 0] *= .58
        start = int(round((.10 + number * beat) * sr))
        count = min(len(tap), len(reset) - start)
        if count > 0:
            reset[start:start + count] += tap[:count]
            echo_end = max(echo_end, start + count)
    transition = np.concatenate([active, reset])
    raw, landing = _assemble(pre, transition, after)
    return raw, landing, {
        "pre": pre,
        "source": active,
        "n": len(active),
        "bar_samples": int(round(float(np.median(np.diff(bounds))))),
        "trim_db": trim_db,
        "clock_backend": "natural_target_master_no_stretch",
    }, {
        "capture_bar": round(float(np.interp(capture_pos, bounds, np.arange(len(bounds)))), 4),
        "fx_tail_end_sec_relative_landing": round((echo_end - len(reset)) / sr, 6),
        "target_master_samples_adjacent": True,
        "reset_duration_sec": round(len(reset) / sr, 6),
    }


def render_reference_template(
    instance: ReferenceTemplateInstance,
    inputs: ReferenceRenderInputs,
    *,
    target_lufs: float = -14.0,
    time_fit_backend: str = "auto",
) -> RenderedReferenceTemplate:
    """Render one explicit template instance; never select an archetype."""
    _validate_inputs(instance, inputs)
    if instance.archetype == ReferenceArchetype.RESET_RELEASE:
        raw, landing, material, detail = _render_f(instance, inputs)
    elif instance.archetype == ReferenceArchetype.STEM_ECHO_HANDOFF:
        raw, landing, material, detail = _render_c3(instance, inputs, time_fit_backend)
    elif instance.archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        raw, landing, material, detail = _render_b8(instance, inputs, time_fit_backend)
    else:
        raw, landing, material, detail = _render_d2(instance, inputs, time_fit_backend)
    audio = _master(raw, inputs.sample_rate, target_lufs)
    delta = np.max(np.abs(np.diff(audio, axis=0)), axis=1) if len(audio) > 1 else np.zeros(1)
    seam_delta = float(np.max(delta[max(0, landing - 128):landing + 128]))
    global_p999 = float(np.quantile(delta, .999))
    tail_end = float(detail.get("fx_tail_end_sec_relative_landing", 0.0))
    if instance.archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        vocal_onset = float(detail["target_vocal_onset_sec_relative_landing"])
        if tail_end > vocal_onset - float(detail["tail_margin_before_target_vocal_sec"]) + 1e-6:
            raise RuntimeError("loop-build tail overlaps the target vocal")
    elif tail_end > 1e-6:
        raise RuntimeError("reference-backed FX tail exceeded its declared landing bound")
    if not np.isfinite(audio).all() or np.max(np.abs(audio)) >= .999:
        raise RuntimeError("reference-template render violated audio safety")
    provenance = {
        "renderer_version": REFERENCE_RENDERER_VERSION,
        "instance_id": instance.instance_id,
        "recipe_id": instance.recipe.recipe_id,
        "archetype": instance.archetype.value,
        "reference_label": instance.definition.reference_label,
        "anchors": instance.anchors.to_dict(),
        "bar_relative_actions": [item.to_dict() for item in instance.recipe.actions],
        "bass_ownership": instance.choreography["bass_ownership"],
        "target_stream_contract": instance.choreography["target_stream"],
        "target_time_map_backend": material["clock_backend"],
        "target_trim_db": round(float(material["trim_db"]), 6),
        "target_establishment_bars": instance.choreography["target_establishment_bars"],
        "landing_sample": landing,
        "landing_sec": round(landing / inputs.sample_rate, 6),
        "fx_tail": detail,
        "landing_max_sample_delta": round(seam_delta, 6),
        "global_sample_delta_p99_9": round(global_p999, 6),
        "sample_peak": round(float(np.max(np.abs(audio))), 6),
        "clipping_fraction": round(float(np.mean(np.abs(audio) >= .999)), 9),
    }
    return RenderedReferenceTemplate(audio, inputs.sample_rate, landing, provenance)
