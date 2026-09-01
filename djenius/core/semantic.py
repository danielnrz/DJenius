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
