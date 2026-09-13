"""Phase 10: render one continuous full mix from a Set Director plan.

Phases 5/6 only ever needed short bounded previews around one handoff at a
time (`djenius.audio.audition_renderer`). This module reuses the exact same
proven compile -> apply_transition -> splice pattern, just with "before"/
"after" windows that span each track's full usable range instead of a small
preview window, so consecutive edges concatenate into one continuous mix
with no gaps or duplicated audio.

Candidate anchors are chosen per edge in isolation (Phase 5 has no concept
of "the edge before" or "the edge after"), so a middle track's target-entry
point and its own later source-exit point are not guaranteed to land in
timeline order -- confirmed to happen on real music, not just contrived
fixtures. This renderer detects that and shifts the affected transition to
start exactly where the previous edge left off (see `anchor_shift_sec` in
each provenance entry), rather than failing the whole mix over what is
usually a few seconds of independently-reasonable anchor disagreement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from djenius.audio.groove_sampler import render_performance_sample_layer
from djenius.audio.transitions import apply_transition
from djenius.core.candidate_composer import TransitionCandidate
from djenius.core.performance_recipe import compile_performance_recipe
from djenius.core.set_director import SetDirectorPlan, TrackAudio


class SetDirectorRenderError(ValueError):
    """A plan could not be rendered as one continuous mix."""


@dataclass(frozen=True)
class RenderedSetDirectorMix:
    audio: np.ndarray
    sample_rate: int
    total_duration_sec: float
    technique_sequence: tuple[str, ...]
    provenance: tuple[dict[str, Any], ...]


def _resolve_selected_candidate(
    handoff, override: dict[str, Any] | None, index: int,
) -> TransitionCandidate:
    candidate_id = override["candidate_id"] if override else handoff.selected_candidate_id
    if not candidate_id or candidate_id not in handoff.candidates:
        raise SetDirectorRenderError(f"Handoff {index} has no renderable candidate")
    audition = next(
        (item for item in (handoff.ranking.auditions if handoff.ranking else ()) if item.candidate_id == candidate_id),
        None,
    )
    if audition is not None and audition.hard_rejected:
        raise SetDirectorRenderError(
            f"Handoff {index}'s selected candidate was hard-rejected by audition and cannot be rendered"
        )
    return handoff.candidates[candidate_id]


def render_set_director_mix(
    plan: SetDirectorPlan,
    profiles: dict[str, Any],
    audio_provider: Callable[[Any], TrackAudio],
    overrides: dict[int, dict[str, Any]] | None = None,
) -> RenderedSetDirectorMix:
    """Render `plan` end-to-end into one continuous mix.

    Raises `SetDirectorRenderError` with a specific handoff index if any
    selected/locked candidate cannot be rendered (e.g. it needs stems the
    audio provider does not supply, or it was hard-rejected by audition).
    """
    if len(plan.track_ids) < 2:
        raise SetDirectorRenderError("A mix needs at least two tracks")
    overrides = overrides or {}

    sample_rate: int | None = None
    audio_by_track_id: dict[str, np.ndarray] = {}

    def audio_for(track_id: str) -> np.ndarray:
        nonlocal sample_rate
        if track_id not in audio_by_track_id:
            bundle = audio_provider(profiles[track_id])
            if sample_rate is None:
                sample_rate = bundle.sample_rate
            elif bundle.sample_rate != sample_rate:
                raise SetDirectorRenderError("All tracks in a mix must share one sample rate")
            audio_by_track_id[track_id] = np.asarray(bundle.audio, dtype=np.float32)
        return audio_by_track_id[track_id]

    segments: list[np.ndarray] = []
    provenance: list[dict[str, Any]] = []
    technique_sequence: list[str] = []
    cursor_start_sample = 0

    for index, edge in enumerate(plan.edges):
        handoff = edge.handoff
        candidate = _resolve_selected_candidate(handoff, overrides.get(index), index)
        source_audio = audio_for(edge.source_track_id)
        target_audio = audio_for(edge.target_track_id)
        sr = sample_rate
        assert sr is not None

        try:
            compiled = compile_performance_recipe(candidate.recipe, candidate.compile_context())
        except ValueError as exc:
            raise SetDirectorRenderError(f"Handoff {index} recipe failed to compile: {exc}") from exc

        source_transition_start = int(round(compiled.source_start_sec * sr))
        source_transition_end = int(round(compiled.source_end_sec * sr))
        target_transition_start = int(round(compiled.target_start_sec * sr))
        target_consumed_end = int(round((compiled.target_start_sec + compiled.target_consumed_duration_sec) * sr))
        overlap_samples = int(round(compiled.overlap_duration_sec * sr))

        # Candidate anchors are chosen per edge in isolation (Phase 5): a
        # middle track's target-entry point (edge i-1) and its own
        # source-exit point (edge i) can therefore land in the "wrong" order
        # in the full timeline even though each is independently valid.
        # Rather than fail the whole mix over what is usually a few seconds
        # of anchor disagreement, shift this transition to start exactly
        # where the previous edge left off, preserving the technique's
        # overlap duration and DSP untouched -- only its absolute position
        # in this track moves.
        anchor_shift_sec = 0.0
        if source_transition_start < cursor_start_sample:
            anchor_shift_sec = (cursor_start_sample - source_transition_start) / sr
            source_transition_start = cursor_start_sample
            source_transition_end = source_transition_start + overlap_samples

        if source_transition_start < cursor_start_sample or source_transition_end > len(source_audio):
            raise SetDirectorRenderError(
                f"Handoff {index}'s compiled bounds are outside the available source audio "
                "even after shifting to the previous edge's endpoint"
            )
        if target_transition_start < 0 or target_consumed_end > len(target_audio):
            raise SetDirectorRenderError(f"Handoff {index}'s compiled bounds are outside the available target audio")

        source_work = source_audio[cursor_start_sample:source_transition_end]
        source_exit = source_transition_start - cursor_start_sample
        target_work = target_audio[target_transition_start:len(target_audio)]

        if candidate.stem_requirements:
            raise SetDirectorRenderError(
                f"Handoff {index}'s selected candidate ({candidate.technique_family}) requires stems, "
                "which this renderer does not supply; lock a non-stem alternative instead"
            )

        transition_audio = apply_transition(
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
            use_time_stretch=compiled.requires_stretch,
            technique_operations=[dict(item) for item in compiled.technique_operations],
        )
        if len(transition_audio) != overlap_samples:
            raise SetDirectorRenderError(f"Handoff {index} renderer returned an unexpected transition duration")

        sample_layer_provenance: tuple[dict[str, Any], ...] = ()
        if compiled.sample_layer_events:
            transition_audio, layer_provenance = render_performance_sample_layer(
                transition_audio, sr, list(compiled.sample_layer_events),
                output_start_sample=source_exit, peak_ceiling=0.98,
            )
            sample_layer_provenance = tuple(layer_provenance)

        before = source_audio[cursor_start_sample:source_transition_start]
        segments.append(before)
        segments.append(transition_audio.astype(np.float32, copy=False))
        technique_sequence.append(candidate.technique_family)
        provenance.append({
            "handoff_index": index,
            "source_track_id": edge.source_track_id,
            "target_track_id": edge.target_track_id,
            "candidate_id": candidate.candidate_id,
            "technique_family": candidate.technique_family,
            "transition_type": compiled.transition_type,
            "output_start_sample": sum(len(item) for item in segments[:-1]),
            "output_transition_samples": len(transition_audio),
            "sample_layer_event_count": len(sample_layer_provenance),
            "anchor_shift_sec": round(anchor_shift_sec, 6),
        })
        cursor_start_sample = target_consumed_end

    final_track_id = plan.track_ids[-1]
    segments.append(audio_for(final_track_id)[cursor_start_sample:])

    full_mix = np.concatenate(segments, axis=0).astype(np.float32, copy=False)
    if not np.isfinite(full_mix).all():
        raise SetDirectorRenderError("Rendered mix contains non-finite samples")
    assert sample_rate is not None
    return RenderedSetDirectorMix(
        audio=full_mix,
        sample_rate=sample_rate,
        total_duration_sec=len(full_mix) / sample_rate,
        technique_sequence=tuple(technique_sequence),
        provenance=tuple(provenance),
    )
