"""Deterministic short-preview rendering for V2 Phase 6 Audition Lab.

This module executes one already-feasible Phase 5 candidate.  It deliberately
contains no quality ranking policy; :mod:`djenius.core.audition_lab` owns
measurement, rejection, ranking, and selection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

import numpy as np

from djenius.audio.groove_sampler import render_performance_sample_layer
from djenius.audio.transitions import apply_transition
from djenius.core.candidate_composer import TransitionCandidate
from djenius.core.performance_recipe import compile_performance_recipe

PREVIEW_SCHEMA_VERSION = "6.0"


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canonical(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


@dataclass(frozen=True)
class AuditionPreviewConfig:
    """Bounded context requested around a candidate transition."""

    before_context_sec: float = 24.0
    after_context_sec: float = 24.0
    min_context_sec: float = 16.0
    max_context_sec: float = 32.0
    channels: int = 2

    def validate(self) -> None:
        if not 0.0 <= self.min_context_sec <= self.max_context_sec <= 60.0:
            raise ValueError("preview context bounds must satisfy 0 <= min <= max <= 60 seconds")
        if not self.min_context_sec <= self.before_context_sec <= self.max_context_sec:
            raise ValueError("before_context_sec must be inside configured context bounds")
        if not self.min_context_sec <= self.after_context_sec <= self.max_context_sec:
            raise ValueError("after_context_sec must be inside configured context bounds")
        if self.channels not in {1, 2}:
            raise ValueError("preview channels must be mono or stereo")

    def to_dict(self) -> dict[str, Any]:
        return _canonical(self.__dict__)


@dataclass(frozen=True)
class RenderedCandidatePreview:
    """Rendered preview plus exact identity/bounds/provenance binding."""

    candidate_id: str
    recipe_id: str
    source_track_id: str
    target_track_id: str
    sample_rate: int
    channels: int
    transition_start_sample: int
    transition_end_sample: int
    source_context_start_sec: float
    source_transition_start_sec: float
    source_transition_end_sec: float
    target_transition_start_sec: float
    target_consumed_end_sec: float
    target_context_end_sec: float
    render_config: dict[str, Any]
    renderer_provenance: dict[str, Any]
    sample_layer_provenance: tuple[dict[str, Any], ...] = ()
    audio: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), dtype=np.float32), repr=False, compare=False)
    schema_version: str = PREVIEW_SCHEMA_VERSION

    @property
    def exact_duration_sec(self) -> float:
        return len(self.audio) / self.sample_rate if self.sample_rate > 0 else 0.0

    @property
    def audio_sha256(self) -> str:
        data = np.asarray(self.audio, dtype=np.float32, order="C").tobytes()
        return hashlib.sha256(data).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "recipe_id": self.recipe_id,
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "transition_start_sample": self.transition_start_sample,
            "transition_end_sample": self.transition_end_sample,
            "source_context_start_sec": round(self.source_context_start_sec, 9),
            "source_transition_start_sec": round(self.source_transition_start_sec, 9),
            "source_transition_end_sec": round(self.source_transition_end_sec, 9),
            "target_transition_start_sec": round(self.target_transition_start_sec, 9),
            "target_consumed_end_sec": round(self.target_consumed_end_sec, 9),
            "target_context_end_sec": round(self.target_context_end_sec, 9),
            "exact_duration_sec": round(self.exact_duration_sec, 9),
            "audio_sha256": self.audio_sha256,
            "render_config": _canonical(self.render_config),
            "renderer_provenance": _canonical(self.renderer_provenance),
            "sample_layer_provenance": _canonical(self.sample_layer_provenance),
        }


def _as_channels(audio: np.ndarray, channels: int) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    if values.ndim == 1:
        values = values[:, None]
    if values.ndim != 2 or values.shape[1] not in {1, 2}:
        raise ValueError("audition source audio must be mono or stereo")
    if channels == 1:
        if values.shape[1] == 2:
            return np.mean(values, axis=1, dtype=np.float32)[:, None]
        return values.copy()
    if values.shape[1] == 1:
        return np.repeat(values, 2, axis=1)
    return values.copy()


def _slice_required_stems(
    candidate: TransitionCandidate,
    source_stems: dict[str, np.ndarray] | None,
    target_stems: dict[str, np.ndarray] | None,
    *,
    source_work_start: int,
    source_work_end: int,
    target_work_start: int,
    target_work_end: int,
    channels: int,
) -> tuple[dict[str, np.ndarray] | None, dict[str, np.ndarray] | None, dict[str, Any]]:
    source_required = {
        item.split(":", 1)[1] for item in candidate.stem_requirements if item.startswith("source:")
    }
    target_required = {
        item.split(":", 1)[1] for item in candidate.stem_requirements if item.startswith("target:")
    }
    if (source_required and not source_stems) or (target_required and not target_stems):
        raise ValueError("candidate requires stems but audition render did not receive them")

    def build(
        stems: dict[str, np.ndarray] | None,
        required: set[str],
        start: int,
        end: int,
        role: str,
    ) -> dict[str, np.ndarray] | None:
        if not stems:
            return None
        missing = sorted(required - set(stems))
        if missing:
            raise ValueError(f"{role} audition stems missing required: {','.join(missing)}")
        result: dict[str, np.ndarray] = {}
        for name, raw in stems.items():
            values = _as_channels(raw, channels)
            if end > len(values):
                if name in required:
                    raise ValueError(f"{role} audition stem {name} does not cover preview source range")
                continue
            region = np.asarray(values[start:end], dtype=np.float32)
            if not np.isfinite(region).all():
                if name in required:
                    raise ValueError(f"{role} audition stem {name} contains non-finite samples")
                continue
            if name in required and (not region.size or float(np.sqrt(np.mean(region.astype(np.float64) ** 2))) < 1e-7):
                raise ValueError(f"{role} audition stem {name} has insufficient signal")
            result[name] = region
        return result or None

    src = build(source_stems, source_required, source_work_start, source_work_end, "source")
    tgt = build(target_stems, target_required, target_work_start, target_work_end, "target")
    provenance = {
        "required_source_stems": sorted(source_required),
        "required_target_stems": sorted(target_required),
        "supplied_source_stems": sorted(src or {}),
        "supplied_target_stems": sorted(tgt or {}),
        "required_stems_rendered": bool(
            (not source_required or source_required <= set(src or {}))
            and (not target_required or target_required <= set(tgt or {}))
        ),
    }
    return src, tgt, provenance


def render_candidate_preview(
    candidate: TransitionCandidate,
    source_audio: np.ndarray,
    target_audio: np.ndarray,
    sample_rate: int,
    *,
    config: AuditionPreviewConfig | None = None,
    source_stems: dict[str, np.ndarray] | None = None,
    target_stems: dict[str, np.ndarray] | None = None,
) -> RenderedCandidatePreview:
    """Render one bounded candidate preview without mastering or ranking it."""
    config = config or AuditionPreviewConfig()
    config.validate()
    if sample_rate <= 1000:
        raise ValueError("audition sample_rate must be greater than 1000 Hz")
    errors = candidate.validate()
    if errors:
        raise ValueError("invalid audition candidate: " + "; ".join(errors))

    source = _as_channels(source_audio, config.channels)
    target = _as_channels(target_audio, config.channels)
    if not np.isfinite(source).all() or not np.isfinite(target).all():
        raise ValueError("audition source audio contains non-finite samples")

    compiled = compile_performance_recipe(candidate.recipe, candidate.compile_context())
    sr = int(sample_rate)
    source_transition_start = int(round(compiled.source_start_sec * sr))
    source_transition_end = int(round(compiled.source_end_sec * sr))
    target_transition_start = int(round(compiled.target_start_sec * sr))
    target_consumed_end = int(round((compiled.target_start_sec + compiled.target_consumed_duration_sec) * sr))
    overlap_samples = int(round(compiled.overlap_duration_sec * sr))
    if source_transition_start < 0 or source_transition_end > len(source):
        raise ValueError("compiled audition source transition is outside supplied audio")
    if target_transition_start < 0 or target_consumed_end > len(target):
        raise ValueError("compiled audition target transition is outside supplied audio")
    if source_transition_end - source_transition_start < overlap_samples:
        raise ValueError("compiled audition source range is shorter than transition")

    before_requested = int(round(config.before_context_sec * sr))
    after_requested = int(round(config.after_context_sec * sr))
    source_context_start = max(0, source_transition_start - before_requested)
    target_context_end = min(len(target), target_consumed_end + after_requested)
    source_work = source[source_context_start:source_transition_end]
    target_work = target[target_transition_start:target_context_end]
    source_exit = source_transition_start - source_context_start

    sliced_source_stems, sliced_target_stems, stem_provenance = _slice_required_stems(
        candidate, source_stems, target_stems,
        source_work_start=source_context_start,
        source_work_end=source_transition_end,
        target_work_start=target_transition_start,
        target_work_end=target_context_end,
        channels=config.channels,
    )

    transition = apply_transition(
        source_audio=source_work,
        target_audio=target_work,
        sr=sr,
        transition_type=compiled.transition_type,
        overlap_samples=overlap_samples,
        source_exit_sample=source_exit,
        target_entry_sample=0,
        source_bpm=candidate.source_bpm,
        target_bpm=candidate.target_bpm,
        source_low_energy=float(candidate.source_segment.energy),
        source_mid_energy=float(candidate.source_segment.energy),
        target_low_energy=float(candidate.target_segment.energy),
        target_mid_energy=float(candidate.target_segment.energy),
        source_stems=sliced_source_stems,
        target_stems=sliced_target_stems,
        use_time_stretch=compiled.requires_stretch,
        technique_operations=[dict(item) for item in compiled.technique_operations],
    )
    transition = _as_channels(transition, config.channels)
    if len(transition) != overlap_samples:
        raise ValueError("audition transition renderer returned unexpected duration")

    sample_layer_provenance: list[dict[str, Any]] = []
    if compiled.sample_layer_events:
        transition, sample_layer_provenance = render_performance_sample_layer(
            transition,
            sr,
            list(compiled.sample_layer_events),
            output_start_sample=source_exit,
            peak_ceiling=0.98,
        )
        transition = _as_channels(transition, config.channels)

    before = source[source_context_start:source_transition_start]
    after = target[target_consumed_end:target_context_end]
    preview_audio = np.concatenate([before, transition, after], axis=0).astype(np.float32, copy=False)
    transition_start_output = len(before)
    transition_end_output = transition_start_output + len(transition)
    stretch_ratio = (
        candidate.source_bpm / candidate.target_bpm
        if compiled.requires_stretch and candidate.target_bpm > 0 else 1.0
    )
    render_config = {
        **config.to_dict(),
        "sample_rate": sr,
    }
    renderer_provenance = {
        "renderer": "v2_phase6_candidate_preview_renderer",
        "candidate_id": candidate.candidate_id,
        "recipe_id": candidate.recipe.recipe_id,
        "transition_type": compiled.transition_type,
        "technique_family": candidate.technique_family,
        "overlap_samples": overlap_samples,
        "requires_stretch": compiled.requires_stretch,
        "time_stretch_ratio": round(float(stretch_ratio), 9),
        "target_consumed_duration_sec": compiled.target_consumed_duration_sec,
        "source_context_truncated": source_context_start == 0 and source_transition_start < before_requested,
        "target_context_truncated": target_context_end == len(target) and len(target) - target_consumed_end < after_requested,
        "mastering_applied": False,
        "soft_clip_applied": False,
        "sample_layer_event_count": len(compiled.sample_layer_events),
        **stem_provenance,
    }
    return RenderedCandidatePreview(
        candidate_id=candidate.candidate_id,
        recipe_id=candidate.recipe.recipe_id,
        source_track_id=candidate.source_track_id,
        target_track_id=candidate.target_track_id,
        sample_rate=sr,
        channels=config.channels,
        transition_start_sample=transition_start_output,
        transition_end_sample=transition_end_output,
        source_context_start_sec=source_context_start / sr,
        source_transition_start_sec=compiled.source_start_sec,
        source_transition_end_sec=compiled.source_end_sec,
        target_transition_start_sec=compiled.target_start_sec,
        target_consumed_end_sec=target_consumed_end / sr,
        target_context_end_sec=target_context_end / sr,
        render_config=render_config,
        renderer_provenance=renderer_provenance,
        sample_layer_provenance=tuple(sample_layer_provenance),
        audio=preview_audio,
    )
