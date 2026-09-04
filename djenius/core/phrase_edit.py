"""Small deterministic helpers for phrase-continuous internal edits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InternalEditAlignment:
    source_boundary_sec: float
    target_boundary_sec: float
    source_grid: str
    target_grid: str
    source_shift_sec: float
    target_shift_sec: float
    aligned: bool


@dataclass(frozen=True)
class InternalEditQuality:
    score: float
    quality_class: str
    reason: str


def _nearest(
    grids: tuple[tuple[str, list[float]], ...],
    value: float,
    max_shift_sec: float,
) -> tuple[float, str] | None:
    # A bar is the primary edit grid.  Downbeats and detected phrase starts
    # are progressively weaker fallbacks when the analysis is incomplete.
    for grid_name, grid in grids:
        if not grid:
            continue
        nearest = min((float(item) for item in grid), key=lambda item: abs(item - value))
        if abs(nearest - value) <= max_shift_sec:
            return nearest, grid_name
    return None


def align_internal_edit_boundaries(
    source_track,
    target_track,
    source_end_sec: float,
    target_start_sec: float,
    *,
    max_shift_sec: float = 0.75,
) -> InternalEditAlignment:
    """Snap only within a local window, preferring actual bar boundaries."""
    source_grids = tuple(
        (name, list(getattr(source_track.analysis, field, []) or []))
        for name, field in (("bar", "bar_times"), ("downbeat", "downbeat_times"), ("phrase", "phrase_boundaries"))
    )
    target_grids = tuple(
        (name, list(getattr(target_track.analysis, field, []) or []))
        for name, field in (("bar", "bar_times"), ("downbeat", "downbeat_times"), ("phrase", "phrase_boundaries"))
    )
    source = _nearest(source_grids, source_end_sec, max_shift_sec)
    target = _nearest(target_grids, target_start_sec, max_shift_sec)
    if source is None:
        source = (float(source_end_sec), "original")
    if target is None:
        target = (float(target_start_sec), "original")
    aligned = source[1] != "original" and target[1] != "original"
    return InternalEditAlignment(
        source_boundary_sec=round(source[0], 4),
        target_boundary_sec=round(target[0], 4),
        source_grid=source[1],
        target_grid=target[1],
        source_shift_sec=round(source[0] - source_end_sec, 4),
        target_shift_sec=round(target[0] - target_start_sec, 4),
        aligned=aligned,
    )


def assess_internal_edit(pair, alignment: InternalEditAlignment) -> InternalEditQuality:
    """Gate an internal edit using evidence already computed for the pair."""
    phase = max(0.0, 1.0 - min(abs(float(getattr(pair, "phase_error_ms", 1000.0))) / 250.0, 1.0))
    local = float(getattr(pair, "local_context_score", 0.0))
    technical = float(getattr(pair, "technical_score", 0.0))
    loudness = float(getattr(pair, "loudness_score", 0.5))
    bass = float(getattr(pair, "bass_score", 0.5))
    vocal = float(getattr(pair, "vocal_score", 0.5))
    score = (
        0.30 * local
        + 0.23 * phase
        + 0.18 * technical
        + 0.11 * loudness
        + 0.09 * bass
        + 0.09 * vocal
    )
    if not alignment.aligned:
        score -= 0.15
    score = max(0.0, min(1.0, score))
    if score >= 0.78 and alignment.aligned:
        quality_class = "SEAMLESS"
    elif score >= 0.70 and alignment.aligned:
        quality_class = "GOOD"
    elif score >= 0.60:
        quality_class = "MARGINAL"
    else:
        quality_class = "REJECT"
    reason = (
        f"{quality_class.lower()} internal seam: grid={alignment.source_grid}->{alignment.target_grid}, "
        f"local={local:.2f}, phase={phase:.2f}, technical={technical:.2f}"
    )
    return InternalEditQuality(round(score, 4), quality_class, reason)


def internal_edit_overlap_sec() -> float:
    """A bounded edit seam, distinct from a multi-bar DJ overlap."""
    return 0.02
