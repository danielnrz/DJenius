"""QA gate orchestrator.

Runs all QA checks in the correct order (fast metadata checks first,
audio-based checks last) and returns a single ``QAResult`` with full
provenance.

Pipeline integration point::

    from djenius.audio.qa.gate import run_qa_gate

    result = run_qa_gate(plan, pre_rendered_splices={...})
    if not result.passed:
        # reject plan, log provenance, trigger replan
        ...
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from djenius.audio.qa.models import QAResult, QAViolation
from djenius.audio.qa.macro_structure import (
    evaluate_macro_pacing,
    evaluate_macro_pacing_from_timeline,
)
from djenius.audio.qa.vocal_integrity import evaluate_edit_point
from djenius.audio.qa.loop_dsp import evaluate_loop_seamlessness

logger = logging.getLogger(__name__)


def _collect_edit_points(plan: Any) -> list[tuple[str, float, Any]]:
    """Extract (track_id, time, TransitionPlan) for each edit point."""
    edits: list[tuple[str, float, Any]] = []
    for trans in plan.transitions:
        source_exit = getattr(trans, "source_exit_time", 0.0)
        source_id = getattr(trans, "source_track_id", "")
        if source_exit > 0 and source_id:
            edits.append((source_id, source_exit, trans))

        target_entry = getattr(trans, "target_entry_time", 0.0)
        target_id = getattr(trans, "target_track_id", "")
        if target_entry > 0 and target_id:
            edits.append((target_id, target_entry, trans))
    return edits


def _collect_timeline_edit_points(plan: Any) -> list[tuple[str, float, Any]]:
    """Extract (track_id, time, PerformanceTransition) from timeline.

    Each timeline transition has TWO edit boundaries:
      - ``source_end_sec`` — the outgoing boundary on the source track
      - ``target_start_sec`` — the incoming boundary on the target track

    Both must be checked for vocal integrity.

    ``source_appearance_id`` / ``target_appearance_id`` are appearance IDs;
    we resolve them through the timeline's appearances list to get the
    actual ``track_id`` from ``appearance.segment.track_id``.
    """
    edits: list[tuple[str, float, Any]] = []
    timeline = getattr(plan, "performance_timeline", None)
    if timeline is None:
        return edits
    # Build appearance-id → track-id lookup
    appearance_map: dict[str, str] = {}
    for app in getattr(timeline, "appearances", []):
        app_id = getattr(app, "id", "")
        seg = getattr(app, "segment", None)
        track_id = getattr(seg, "track_id", "") if seg else ""
        if app_id and track_id:
            appearance_map[app_id] = track_id
    for trans in getattr(timeline, "transitions", []):
        # Source boundary (outgoing cut)
        source_end = getattr(trans, "source_end_sec", 0.0)
        source_app_id = getattr(trans, "source_appearance_id", "")
        source_track = appearance_map.get(source_app_id, "")
        if source_end > 0 and source_track:
            edits.append((source_track, source_end, trans))
        # Target boundary (incoming cut)
        target_start = getattr(trans, "target_start_sec", 0.0)
        target_app_id = getattr(trans, "target_appearance_id", "")
        target_track = appearance_map.get(target_app_id, "")
        if target_start > 0 and target_track:
            edits.append((target_track, target_start, trans))
    return edits


def _get_track_by_id(plan: Any, track_id: str) -> Any:
    """Retrieve a TrackProfile from the plan by id."""
    getter = getattr(plan, "get_track_by_id", None)
    if callable(getter):
        return getter(track_id)
    for t in getattr(plan, "tracks", []):
        if getattr(t, "id", "") == track_id:
            return t
    return None


def run_qa_gate(
    plan: Any,
    *,
    pre_rendered_splices: dict[str, tuple[np.ndarray, np.ndarray]] | None = None,
    sample_rate: int = 44100,
    max_fade_dominance: float | None = None,
    max_consecutive_complex: int | None = None,
) -> QAResult:
    """Run the full QA gate on a SetPlan.

    Parameters
    ----------
    plan : SetPlan
        The planned mix to evaluate.
    pre_rendered_splices : dict, optional
        Mapping of ``splice_id`` -> ``(tail_audio, head_audio)`` numpy
        arrays for loop/DSP continuity checks.  Keys are
        ``"{source_id}:{exit_time:.3f}"``.
    sample_rate : int
        Sample rate for audio-based checks.
    max_fade_dominance : float, optional
        Override for the macro-structure fade threshold.
    max_consecutive_complex : int, optional
        Override for the macro-structure complexity threshold.

    Returns
    -------
    QAResult
        Passed if every check passes.  Violations carry full provenance.
    """
    result = QAResult()

    # ── Phase 1: Macro-structure (metadata only, fastest) ─────────────
    macro_kwargs: dict[str, Any] = {}
    if max_fade_dominance is not None:
        macro_kwargs["max_fade_dominance"] = max_fade_dominance
    if max_consecutive_complex is not None:
        macro_kwargs["max_consecutive_complex"] = max_consecutive_complex

    result.merge(evaluate_macro_pacing(plan, **macro_kwargs))

    # Also check PerformanceTimeline if present
    timeline = getattr(plan, "performance_timeline", None)
    if timeline is not None:
        result.merge(evaluate_macro_pacing_from_timeline(timeline, **macro_kwargs))

    # ── Phase 2: Vocal integrity (metadata + optional stem cache) ─────
    # Combine edit points from both SetPlan transitions and PerformanceTimeline,
    # deduplicating by (track_id, time) to avoid evaluating the same edit twice.
    seen: set[tuple[str, float]] = set()
    edit_points: list[tuple[str, float, Any]] = []
    for pts in (_collect_edit_points(plan), _collect_timeline_edit_points(plan)):
        for track_id, cut_time, trans in pts:
            key = (track_id, cut_time)
            if key not in seen:
                seen.add(key)
                edit_points.append((track_id, cut_time, trans))
    for track_id, cut_time, _trans in edit_points:
        track = _get_track_by_id(plan, track_id)
        if track is None:
            continue
        lyrics = getattr(track, "lyrics", None)
        analysis = getattr(track, "analysis", None)

        segments = getattr(lyrics, "segments", []) if lyrics else []
        vocal_regions = getattr(analysis, "vocal_regions", []) if analysis else []
        phrase_boundaries = getattr(analysis, "phrase_boundaries", []) if analysis else []

        # Optionally load vocal stem chunk for stem bleed check
        vocal_stem_audio: np.ndarray | None = None
        stem_sr: int = sample_rate
        stem_loaded_start: float = 0.0
        stems_info = getattr(analysis, "stems", None) if analysis else None
        if stems_info and "vocals" in stems_info:
            try:
                import soundfile as sf
                vocal_path = stems_info["vocals"]
                # Load a 2-second window around the cut point
                info = sf.info(vocal_path)
                sr_file = info.samplerate
                start_frame = max(0, int((cut_time - 1.0) * sr_file))
                end_frame = min(info.frames, int((cut_time + 1.0) * sr_file))
                if end_frame > start_frame:
                    vocal_stem_audio, _ = sf.read(
                        vocal_path,
                        start=start_frame,
                        stop=end_frame,
                        dtype="float32",
                    )
                    stem_sr = sr_file
                    stem_loaded_start = start_frame / sr_file
            except Exception as exc:
                logger.debug("Could not load vocal stem for %s: %s", track_id, exc)

        result.merge(evaluate_edit_point(
            cut_time,
            segments=segments,
            vocal_regions=vocal_regions,
            phrase_boundaries=phrase_boundaries,
            vocal_stem_audio=vocal_stem_audio,
            sample_rate=stem_sr,
            stem_loaded_start=stem_loaded_start,
        ))

    # ── Phase 3: Loop/DSP continuity (requires audio chunks) ──────────
    if pre_rendered_splices:
        for splice_id, (tail, head) in pre_rendered_splices.items():
            result.merge(evaluate_loop_seamlessness(tail, head, sample_rate, strict_alignment=False))

    return result


def evaluate_rendered_transition(transition_audio: np.ndarray, sample_rate: int) -> QAResult:
    """Check the actual rendered transition at its source/target seam.

    The renderer supplies the post-processed transition waveform.  The
    midpoint is the only available stable boundary independent of raw source
    windows; correlation and spectral flux remain supporting metrics.
    """
    result = QAResult()
    if transition_audio.size < 4:
        return result
    mono = np.mean(transition_audio, axis=-1) if transition_audio.ndim > 1 else transition_audio
    jumps = np.abs(np.diff(mono.astype(np.float64)))
    scale = max(float(np.sqrt(np.mean(np.square(mono.astype(np.float64))))), 1e-6)
    observed = float(np.max(jumps) / scale) if jumps.size else 0.0
    if observed > 8.0:
        result.add(QAViolation(
            module="loop_dsp", metric="sample_discontinuity", threshold=8.0,
            observed=round(observed, 4), context={"max_adjacent_jump": round(float(np.max(jumps)), 6)},
        ))
    return result
