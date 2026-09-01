"""Small, explicit vocabulary and scoring helpers for semantic music intent."""

from __future__ import annotations

import math
from typing import Iterable

MOODS = (
    "happy", "sad", "melancholic", "romantic", "euphoric", "dark",
    "dreamy", "calm", "angry", "hopeful", "nostalgic",
)
ACTIVITIES = (
    "dance", "party", "workout", "driving", "late_night", "relaxing",
    "background", "focused",
)
INTENSITIES = ("soft", "moderate", "energetic", "aggressive")
STYLES = (
    "electronic", "pop", "rock", "hip_hop", "acoustic", "orchestral",
    "ambient",
)
SEMANTIC_LABELS = set(MOODS) | set(ACTIVITIES) | set(INTENSITIES) | set(STYLES)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalized_entropy(scores: dict[str, float]) -> float:
    """Return normalized entropy of a relative score distribution.

    This describes concentration within the tested vocabulary.  It is not a
    probability calibration measure.
    """
    values = [max(0.0, float(value)) for value in scores.values()]
    total = sum(values)
    if len(values) <= 1 or total <= 0:
        return 1.0
    entropy = -sum((value / total) * math.log(value / total) for value in values if value)
    return clamp(entropy / math.log(len(values)))


def score_separation(
    scores: dict[str, float],
    raw_scores: dict[str, float] | None = None,
    window_scores: list[dict[str, float]] | None = None,
) -> dict[str, float | str]:
    """Summarize evidence for a label without pretending it is calibrated.

    Reliability combines relative top-vs-second separation, concentration,
    raw cosine separation when available, and agreement between windows.  The
    output is intentionally named reliability rather than confidence.
    """
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_label, top = ordered[0] if ordered else ("", 0.0)
    second = ordered[1][1] if len(ordered) > 1 else 0.0
    margin = max(0.0, float(top) - float(second))
    entropy = normalized_entropy(scores)
    relative_signal = clamp(margin / 0.08)
    concentration_signal = 1.0 - entropy
    raw_margin = 0.0
    if raw_scores:
        raw_ordered = sorted(raw_scores.values(), reverse=True)
        raw_margin = max(0.0, raw_ordered[0] - (raw_ordered[1] if len(raw_ordered) > 1 else 0.0))
    raw_signal = clamp(raw_margin / 0.12) if raw_scores else relative_signal
    consistency = 1.0
    if window_scores:
        distances = []
        for window in window_scores:
            distance = sum(abs(float(window.get(label, 0.0)) - float(value)) for label, value in scores.items())
            distances.append(distance / max(len(scores), 1))
        consistency = clamp(1.0 - (sum(distances) / len(distances)) * 4.0) if distances else 1.0
    reliability = clamp(
        0.35 * relative_signal
        + 0.25 * concentration_signal
        + 0.20 * raw_signal
        + 0.20 * consistency
    )
    return {
        "top_label": top_label,
        "top_score": round(float(top), 6),
        "second_score": round(float(second), 6),
        "margin": round(margin, 6),
        "entropy": round(entropy, 6),
        "raw_margin": round(raw_margin, 6),
        "window_consistency": round(consistency, 6),
        "reliability": round(reliability, 6),
    }


def semantic_similarity_matrix(embeddings: dict[str, Iterable[float]]) -> dict[str, dict[str, float]]:
    """Build a symmetric [0, 1] semantic similarity matrix."""
    labels = list(embeddings)
    return {
        left: {right: round(cosine_similarity(embeddings[left], embeddings[right]), 6) for right in labels}
        for left in labels
    }


def cosine_similarity(first: Iterable[float], second: Iterable[float]) -> float:
    """Return a normalized cosine similarity in [0, 1]."""
    a = list(first)
    b = list(second)
    if not a or len(a) != len(b):
        return 0.5
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.5
    return clamp((dot / (norm_a * norm_b) + 1.0) / 2.0)


def distribution_similarity(first: dict[str, float], second: dict[str, float]) -> float:
    """Compare two score maps without penalizing missing/unknown labels."""
    labels = set(first) | set(second)
    if not labels:
        return 0.5
    distance = sum(abs(float(first.get(label, 0.0)) - float(second.get(label, 0.0))) for label in labels)
    return clamp(1.0 - distance / max(len(labels), 1))


def intent_match(scores: dict[str, float], desired: Iterable[str], avoided: Iterable[str] = ()) -> float:
    """Return a soft preference score for desired and avoided semantic labels."""
    wanted = [float(scores.get(label, 0.0)) for label in desired if label in scores]
    unwanted = [float(scores.get(label, 0.0)) for label in avoided if label in scores]
    if not wanted and not unwanted:
        return 0.5
    positive = sum(wanted) / len(wanted) if wanted else 0.5
    negative = sum(unwanted) / len(unwanted) if unwanted else 0.0
    return clamp(0.5 + 0.5 * positive - 0.35 * negative)
