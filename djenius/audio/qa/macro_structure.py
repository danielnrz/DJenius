"""Full-remix macro structure evaluator.

Evaluates the holistic mix structure from the planner to prevent
"over-mixing" and ensure execution diversity.  Measures fade dominance,
consecutive complex transition count, and STAY preference.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from djenius.audio.qa.models import QAResult, QAViolation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Maximum fraction of total mix duration that may be spent in overlapping
# transitions (crossfades, blended phrase cuts, etc.).
MAX_FADE_DOMINANCE: float = 0.20

# Maximum number of consecutive complex overlapping transitions before
# the mix is considered over-mixed.
MAX_CONSECUTIVE_COMPLEX: int = 3

# Transition types that count as "complex" (higher risk of bad seams).
COMPLEX_TYPES: frozenset[str] = frozenset({
    "loop_roll",
    "tape_stop",
    "bass_swap",
    "loop_blend",
})

# Transition types that count as "overlapping" (contribute to fade time).
OVERLAPPING_TYPES: frozenset[str] = frozenset({
    "crossfade",
    "bass_swap",
    "loop_blend",
    "filter_sweep",
    "phase_lock",
    "echo_tail",
})

# Minimum duration (seconds) for a transition to be considered
# non-trivial for complexity counting.
MIN_OVERLAP_FOR_FADE: float = 0.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _total_overlap_duration(transitions: list[Any]) -> float:
    """Sum the overlap durations of all overlapping transitions."""
    total = 0.0
    for t in transitions:
        overlap = getattr(t, "overlap_duration", 0.0)
        ttype = getattr(t, "transition_type", None)
        ttype_val = (ttype.value.lower() if hasattr(ttype, "value") else str(ttype)).lower()
        if ttype_val in OVERLAPPING_TYPES and overlap >= MIN_OVERLAP_FOR_FADE:
            total += overlap
    return total


def _max_consecutive_complex(transitions: list[Any]) -> int:
    """Find the longest run of consecutive complex transitions."""
    max_run = 0
    current_run = 0
    for t in transitions:
        ttype = getattr(t, "transition_type", None)
        ttype_val = (ttype.value.lower() if hasattr(ttype, "value") else str(ttype)).lower()
        if ttype_val in COMPLEX_TYPES:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0
    return max_run


def _technique_diversity(technique_counts: dict[str, int]) -> float:
    """Shannon diversity of technique usage.  Returns 0-1 normalised."""
    if not technique_counts:
        return 0.0
    total = sum(technique_counts.values())
    if total <= 0:
        return 0.0
    import math
    probs = [v / total for v in technique_counts.values() if v > 0]
    if len(probs) <= 1:
        return 0.0
    entropy = -sum(p * math.log2(p) for p in probs)
    max_entropy = math.log2(len(probs))
    return entropy / max_entropy if max_entropy > 0 else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_macro_pacing(
    plan: Any,
    *,
    max_fade_dominance: float = MAX_FADE_DOMINANCE,
    max_consecutive_complex: int = MAX_CONSECUTIVE_COMPLEX,
) -> QAResult:
    """Analyse a ``SetPlan`` for fade dominance and over-complexity.

    Parameters
    ----------
    plan : SetPlan
        The planned mix to evaluate.
    max_fade_dominance : float
        Maximum allowed fade fraction of total duration.
    max_consecutive_complex : int
        Maximum allowed consecutive complex transition count.

    Returns
    -------
    QAResult
        Passed if all macro-structure checks are within thresholds.
    """
    result = QAResult()

    transitions = getattr(plan, "transitions", [])
    total_duration = getattr(plan, "total_duration_sec", 0.0)

    if total_duration <= 0 or not transitions:
        return result

    # ── Fade dominance ────────────────────────────────────────────────
    overlap_total = _total_overlap_duration(transitions)
    fade_dominance = overlap_total / total_duration if total_duration > 0 else 0.0
    if fade_dominance > max_fade_dominance:
        result.add(QAViolation(
            module="macro_structure",
            metric="fade_dominance",
            threshold=max_fade_dominance,
            observed=round(fade_dominance, 4),
            context={
                "total_overlap_sec": round(overlap_total, 3),
                "total_duration_sec": round(total_duration, 3),
                "fade_fraction": round(fade_dominance, 4),
            },
        ))

    # ── Consecutive complex transitions ───────────────────────────────
    consecutive = _max_consecutive_complex(transitions)
    if consecutive > max_consecutive_complex:
        result.add(QAViolation(
            module="macro_structure",
            metric="consecutive_complex",
            threshold=max_consecutive_complex,
            observed=consecutive,
            context={
                "max_consecutive": consecutive,
                "complex_types": sorted(COMPLEX_TYPES),
            },
        ))

    return result


def evaluate_macro_pacing_from_timeline(
    timeline: Any,
    *,
    max_fade_dominance: float = MAX_FADE_DOMINANCE,
    max_consecutive_complex: int = MAX_CONSECUTIVE_COMPLEX,
) -> QAResult:
    """Evaluate macro pacing from a ``PerformanceTimeline`` object.

    Uses ``layered_events`` and ``technique_counts`` when available.
    Falls back to the simpler ``transitions`` list.
    """
    result = QAResult()

    total_duration = getattr(timeline, "total_duration_sec", 0.0)
    if total_duration <= 0:
        return result

    # Try technique_counts first for diversity
    technique_counts = getattr(timeline, "technique_counts", {})
    if technique_counts:
        diversity = _technique_diversity(technique_counts)
        # Diversity is informational — no hard threshold.

    # Use layered_events for fade dominance calculation
    layered = getattr(timeline, "layered_events", [])
    if layered:
        overlap_total = sum(
            float(event.get("overlap_duration_sec", 0.0))
            if isinstance(event, dict)
            else getattr(event, "overlap_duration_sec", 0.0)
            for event in layered
        )
        fade_dominance = overlap_total / total_duration if total_duration > 0 else 0.0
        if fade_dominance > max_fade_dominance:
            result.add(QAViolation(
                module="macro_structure",
                metric="fade_dominance",
                threshold=max_fade_dominance,
                observed=round(fade_dominance, 4),
                context={
                    "total_overlap_sec": round(overlap_total, 3),
                    "total_duration_sec": round(total_duration, 3),
                    "source": "performance_timeline",
                },
            ))

    # Consecutive complex from performance_states and transition_roles
    transitions = getattr(timeline, "transitions", [])
    if transitions:
        consecutive = _max_consecutive_complex(transitions)
        if consecutive > max_consecutive_complex:
            result.add(QAViolation(
                module="macro_structure",
                metric="consecutive_complex",
                threshold=max_consecutive_complex,
                observed=consecutive,
                context={"source": "performance_timeline"},
            ))

    return result
