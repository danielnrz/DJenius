"""Compatibility scoring between tracks and transition quality assessment."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from djenius.core.models import TrackProfile, CompatibilityScore, TransitionType
from djenius.utils.camelot import score_key_compatibility, parse_camelot

logger = logging.getLogger(__name__)


def score_compatibility(
    source: TrackProfile,
    target: TrackProfile,
    weights: Optional[dict[str, float]] = None,
) -> CompatibilityScore:
    """Score how well two tracks work together in a transition.

    Returns a CompatibilityScore with individual component scores and an overall score.
    """
    if weights is None:
        weights = {
            "tempo": 0.40,
            "key": 0.30,
            "energy": 0.20,
            "spectral": 0.10,
        }

    score = CompatibilityScore(
        source_id=source.id,
        target_id=target.id,
    )

    # --- Tempo Compatibility ---
    score.tempo_score = _score_tempo(source, target)

    # --- Key Compatibility ---
    score.key_score = _score_key(source, target)

    # --- Energy Compatibility ---
    score.energy_score = _score_energy(source, target)

    # --- Spectral Compatibility ---
    score.spectral_score = _score_spectral(source, target)

    # --- Vocal Safety ---
    score.vocal_safety = _score_vocal_safety(source, target)

    # --- Overall Score ---
    total_weight = sum(weights.values())
    score.overall_score = round(
        (
            weights["tempo"] * score.tempo_score
            + weights["key"] * score.key_score
            + weights["energy"] * score.energy_score
            + weights["spectral"] * score.spectral_score
        ) / total_weight,
        3,
    )

    # Build reasoning
    score.reasoning = _build_reasoning(source, target, score)

    return score


def score_transition_quality(
    source: TrackProfile,
    target: TrackProfile,
    transition_type: TransitionType,
    overlap_duration: float,
    target_bpm: float = 0.0,
) -> float:
    """Score how good a specific transition would be.

    Returns 0.0 to 1.0.
    """
    compat = score_compatibility(source, target)

    # Base score from compatibility
    base = compat.overall_score

    # Adjust for transition type suitability
    type_modifier = 1.0

    bpm_delta = abs(source.bpm - target.bpm) / max(source.bpm, 1.0)

    if transition_type == TransitionType.BEATMATCHED_BLEND:
        # Needs close BPM
        if bpm_delta > 0.08:
            type_modifier *= 0.3
        elif bpm_delta > 0.05:
            type_modifier *= 0.7
        # Penalize very short overlaps for blend
        if overlap_duration < 4.0:
            type_modifier *= 0.5

    elif transition_type == TransitionType.PHRASE_CUT:
        # Works best at phrase boundaries
        # Slight penalty if tempos are very close (blend would be better)
        if bpm_delta < 0.02:
            type_modifier *= 0.8

    elif transition_type == TransitionType.CROSSFADE:
        # General fallback
        if bpm_delta > 0.10:
            type_modifier *= 0.6

    elif transition_type == TransitionType.BASS_SWAP:
        # Needs similar tempo for the swap to work rhythmically
        if bpm_delta > 0.05:
            type_modifier *= 0.5
        # Penalize if both have high low energy (bass clash risk)
        if source.analysis.low_energy > 0.4 and target.analysis.low_energy > 0.4:
            type_modifier *= 0.7

    elif transition_type == TransitionType.FILTER_SWEEP:
        # Flexible but needs reasonable overlap
        if overlap_duration < 3.0:
            type_modifier *= 0.6

    elif transition_type == TransitionType.ECHO_OUT:
        # Works well when blend is risky
        if bpm_delta > 0.08:
            type_modifier *= 1.1  # Slight bonus as it's a good fallback

    elif transition_type == TransitionType.LOOP_BLEND:
        # Needs clean loops
        if bpm_delta > 0.06:
            type_modifier *= 0.5

    return round(min(1.0, max(0.0, base * type_modifier)), 3)


def recommend_transition_type(
    source: TrackProfile,
    target: TrackProfile,
) -> tuple[TransitionType, float, str]:
    """Recommend the best transition type for a pair of tracks.

    Returns (transition_type, confidence, reasoning).
    """
    compat = score_compatibility(source, target)
    bpm_delta = abs(source.bpm - target.bpm) / max(source.bpm, 1.0)

    candidates = []

    # Evaluate each transition type
    for ttype in TransitionType:
        q = score_transition_quality(source, target, ttype, overlap_duration=8.0)
        candidates.append((ttype, q))

    candidates.sort(key=lambda x: x[1], reverse=True)

    if not candidates:
        return (TransitionType.PHRASE_CUT, 0.3, "No suitable transition found")

    best_type, best_score = candidates[0]

    reasoning_parts = []
    if bpm_delta < 0.03:
        reasoning_parts.append("very close tempos")
    elif bpm_delta < 0.08:
        reasoning_parts.append("compatible tempos")
    else:
        reasoning_parts.append(f"tempo difference {bpm_delta*100:.1f}%")

    if compat.key_score > 0.8:
        reasoning_parts.append("harmonically compatible")
    elif compat.key_score < 0.3:
        reasoning_parts.append("key clash risk")

    if compat.energy_score > 0.8:
        reasoning_parts.append("similar energy levels")
    elif compat.energy_score < 0.4:
        reasoning_parts.append("energy level change")

    reasoning = f"{best_type.value}: {', '.join(reasoning_parts)}"

    return (best_type, best_score, reasoning)


def rank_candidates(
    source: TrackProfile,
    candidates: list[TrackProfile],
    limit: int = 5,
) -> list[tuple[TrackProfile, CompatibilityScore]]:
    """Rank candidate next tracks by compatibility.

    Returns the top N candidates with their scores.
    """
    scored = []
    for target in candidates:
        if target.id == source.id:
            continue
        score = score_compatibility(source, target)
        scored.append((target, score))

    scored.sort(key=lambda x: x[1].overall_score, reverse=True)
    return scored[:limit]


# --- Private helpers ---

def _score_tempo(source: TrackProfile, target: TrackProfile) -> float:
    """Score tempo compatibility."""
    if source.bpm <= 0 or target.bpm <= 0:
        return 0.5

    # Check for half/double time relationship
    bpm_ratios = [
        abs(source.bpm - target.bpm) / max(source.bpm, 1.0),
        abs(source.bpm * 2 - target.bpm) / max(source.bpm * 2, 1.0),
        abs(source.bpm - target.bpm * 2) / max(target.bpm * 2, 1.0),
    ]

    min_delta = min(bpm_ratios)

    if min_delta <= 0.02:
        return 1.0
    elif min_delta <= 0.05:
        return 0.9
    elif min_delta <= 0.08:
        # Linear decay from 0.9 to 0.5
        return 0.9 - (min_delta - 0.05) * (0.4 / 0.03)
    elif min_delta <= 0.15:
        # Linear decay from 0.5 to 0.1
        return 0.5 - (min_delta - 0.08) * (0.4 / 0.07)
    else:
        return max(0.05, 0.1 - (min_delta - 0.15) * 0.5)


def _score_key(source: TrackProfile, target: TrackProfile) -> float:
    """Score harmonic compatibility using Camelot wheel."""
    c1 = source.camelot
    c2 = target.camelot

    if not c1 or not c2:
        return 0.5  # Unknown keys, neutral score

    return score_key_compatibility(c1, c2)


def _score_energy(source: TrackProfile, target: TrackProfile) -> float:
    """Score energy level compatibility.

    Considers both mean energy and energy curve shapes.
    """
    e1 = source.mean_energy
    e2 = target.mean_energy

    if e1 <= 0 and e2 <= 0:
        return 0.8

    delta = abs(e1 - e2)

    if delta < 0.1:
        return 1.0
    elif delta < 0.2:
        return 0.85
    elif delta < 0.3:
        return 0.7
    elif delta < 0.5:
        return 0.5
    else:
        return max(0.2, 1.0 - delta)


def _score_spectral(source: TrackProfile, target: TrackProfile) -> float:
    """Score spectral compatibility (similarity of frequency content)."""
    s1 = source.analysis.spectral_centroid_mean
    s2 = target.analysis.spectral_centroid_mean

    if s1 <= 0 or s2 <= 0:
        return 0.5

    # Compare relative spectral positions
    ratio = min(s1, s2) / max(s1, s2)

    if ratio > 0.85:
        return 1.0
    elif ratio > 0.7:
        return 0.8
    elif ratio > 0.5:
        return 0.6
    else:
        return max(0.2, ratio)


def _score_vocal_safety(source: TrackProfile, target: TrackProfile) -> float:
    """Estimate risk of vocal-on-vocal clash.

    Without stem separation, we use heuristic spectral analysis.
    Vocal energy typically sits in the 300-3000Hz range with specific patterns.
    """
    # High mid energy suggests vocals
    s1_mid = source.analysis.mid_energy
    s2_mid = target.analysis.mid_energy

    # If both tracks have high mid energy, there's more vocal clash risk
    if s1_mid > 0.5 and s2_mid > 0.5:
        return 0.6
    elif s1_mid > 0.5 or s2_mid > 0.5:
        return 0.75
    else:
        return 0.9  # Low vocal presence in both


def _build_reasoning(
    source: TrackProfile,
    target: TrackProfile,
    score: CompatibilityScore,
) -> str:
    """Build a human-readable explanation of the score."""
    parts = []

    # BPM
    if score.tempo_score > 0.9:
        parts.append(f"very close BPM ({source.bpm:.0f} vs {target.bpm:.0f})")
    elif score.tempo_score > 0.7:
        parts.append(f"compatible BPM ({source.bpm:.0f} vs {target.bpm:.0f})")
    elif score.tempo_score > 0.4:
        parts.append(f"moderate BPM gap ({source.bpm:.0f} vs {target.bpm:.0f})")
    else:
        parts.append(f"large BPM gap ({source.bpm:.0f} vs {target.bpm:.0f})")

    # Key
    if score.key_score >= 0.9:
        parts.append(f"harmonically ideal ({source.camelot} -> {target.camelot})")
    elif score.key_score >= 0.7:
        parts.append(f"harmonically compatible ({source.camelot} -> {target.camelot})")
    elif score.key_score < 0.3:
        parts.append(f"key clash risk ({source.camelot} -> {target.camelot})")

    # Energy
    if score.energy_score > 0.8:
        parts.append("similar energy")
    elif score.energy_score < 0.4:
        direction = "rise" if target.mean_energy > source.mean_energy else "drop"
        parts.append(f"energy {direction}")

    return "; ".join(parts) if parts else "mixed compatibility"
