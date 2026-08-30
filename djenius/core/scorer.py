"""Compatibility scoring between tracks and transition quality assessment."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from djenius.core.models import TrackProfile, CompatibilityScore, TransitionType
from djenius.utils.camelot import score_key_compatibility, parse_camelot

logger = logging.getLogger(__name__)


# ---- Preference Bonuses ----

@dataclass
class PreferenceBonuses:
    """Bonuses derived from user preferences to bias compatibility scores.

    All bonuses are bounded: they modify the final score but cannot
    override safety-critical signals like key clashes or extreme BPM
    differences.
    """
    # Track-level bonuses
    liked_track_bonus: float = 0.0      # Bonus if target is a liked track
    disliked_track_penalty: float = 0.0 # Penalty if target is disliked

    # BPM preference bonus
    bpm_in_range_bonus: float = 0.0     # Bonus if target BPM is in preferred range

    # Energy preference bonus
    energy_in_range_bonus: float = 0.0  # Bonus if target energy is in preferred range

    # Transition type preference
    preferred_trans_bonus: float = 0.0  # Bonus if transition type is preferred
    disliked_trans_penalty: float = 0.0 # Penalty if transition type is disliked

    # Combined bonus (sum of all, clamped)
    total_bonus: float = 0.0

    def compute_total(self) -> float:
        """Compute the total bonus, clamped to [-0.15, +0.15].

        This ensures preferences influence but never overpower
        the core compatibility signals.
        """
        raw = (
            self.liked_track_bonus
            + self.bpm_in_range_bonus
            + self.energy_in_range_bonus
            + self.preferred_trans_bonus
            - self.disliked_track_penalty
            - self.disliked_trans_penalty
        )
        self.total_bonus = max(-0.15, min(0.15, raw))
        return self.total_bonus


def compute_preference_bonuses(
    target: TrackProfile,
    liked_tracks: Optional[set[str]] = None,
    disliked_tracks: Optional[set[str]] = None,
    preferred_bpm_range: Optional[tuple[float, float]] = None,
    preferred_energy_range: Optional[tuple[float, float]] = None,
    preferred_transition_types: Optional[dict[str, float]] = None,
    disliked_transition_types: Optional[dict[str, float]] = None,
    transition_type: Optional[TransitionType] = None,
) -> PreferenceBonuses:
    """Compute preference bonuses for scoring a target track.

    Args:
        target: The candidate next track.
        liked_tracks: Set of track IDs the user likes.
        disliked_tracks: Set of track IDs the user dislikes.
        preferred_bpm_range: (min, max) BPM the user prefers.
        preferred_energy_range: (min, max) energy the user prefers.
        preferred_transition_types: Transition types the user rates positively.
        disliked_transition_types: Transition types the user rates negatively.
        transition_type: The transition type being considered.

    Returns:
        A PreferenceBonuses with individual and total bonuses.
    """
    bonuses = PreferenceBonuses()

    liked = liked_tracks or set()
    disliked = disliked_tracks or set()

    # Track-level bonuses
    if target.id in liked:
        bonuses.liked_track_bonus = 0.08
    if target.id in disliked:
        bonuses.disliked_track_penalty = 0.12

    # BPM preference
    if preferred_bpm_range and target.bpm > 0:
        bpm_min, bpm_max = preferred_bpm_range
        if bpm_min <= target.bpm <= bpm_max:
            bonuses.bpm_in_range_bonus = 0.05
        else:
            # Small penalty for being outside preferred range
            bonuses.bpm_in_range_bonus = -0.03

    # Energy preference
    if preferred_energy_range:
        e_min, e_max = preferred_energy_range
        if e_min <= target.mean_energy <= e_max:
            bonuses.energy_in_range_bonus = 0.05
        else:
            bonuses.energy_in_range_bonus = -0.02

    # Transition type preference
    if transition_type:
        tt_name = transition_type.value
        if preferred_transition_types and tt_name in preferred_transition_types:
            bonuses.preferred_trans_bonus = 0.04
        if disliked_transition_types and tt_name in disliked_transition_types:
            bonuses.disliked_trans_penalty = 0.06

    bonuses.compute_total()
    return bonuses


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


def score_with_preferences(
    base_score: float,
    bonuses: PreferenceBonuses,
) -> float:
    """Apply preference bonuses to a base score.

    Returns a score in [0.0, 1.0]. Safety-critical signals (key clashes,
    extreme BPM) cannot be overridden by preferences.

    The bonus is clamped to [-0.15, +0.15] to prevent preferences
    from overpowering the core compatibility calculation.
    """
    bonus = bonuses.compute_total()
    return max(0.0, min(1.0, base_score + bonus))


def recommend_transition_type(
    source: TrackProfile,
    target: TrackProfile,
    allowed_types: Optional[list[TransitionType]] = None,
    source_exit_time: Optional[float] = None,
    target_entry_time: Optional[float] = None,
) -> tuple[TransitionType, float, str]:
    """Recommend the best transition type for a pair of tracks.

    Uses phrase/structural awareness, energy patterns, and section context.
    Returns (transition_type, confidence, reasoning).
    """
    compat = score_compatibility(source, target)
    bpm_delta = abs(source.bpm - target.bpm) / max(source.bpm, 1.0)

    # Gather structural context
    source_sections = source.analysis.structural_sections or []
    target_sections = target.analysis.structural_sections or []

    # Determine source section type at exit
    source_exit_section = "verse"  # default
    if source_sections:
        # Find the section that contains the exit point
        exit_points = source.analysis.possible_exit_points
        exit_t = source_exit_time
        if exit_t is None:
            exit_t = exit_points[-1] if exit_points else source.duration_sec * 0.85
        for start, end, label in source_sections:
            if start <= exit_t <= end:
                source_exit_section = label
                break

    # Determine target section type at entry
    target_entry_section = "verse"  # default
    if target_sections:
        entry_points = target.analysis.possible_entry_points
        entry_t = target_entry_time
        if entry_t is None:
            entry_t = entry_points[0] if entry_points else target.analysis.intro_end + 5
        for start, end, label in target_sections:
            if start <= entry_t <= end:
                target_entry_section = label
                break

    # Score energy change direction
    energy_change = target.mean_energy - source.mean_energy
    is_energy_rising = energy_change > 0.1
    is_energy_dropping = energy_change < -0.1
    is_energy_similar = abs(energy_change) <= 0.1

    # Vocal context: penalize transitions that are risky during vocals
    source_has_vocals = bool(source.analysis.vocal_regions)
    target_has_vocals = bool(target.analysis.vocal_regions)

    candidates = []

    # Check if both tracks have stems available (enables stem-based transitions)
    source_has_stems = bool(source.analysis.stems)
    target_has_stems = bool(target.analysis.stems)
    both_have_stems = source_has_stems and target_has_stems

    # Evaluate each transition type with context-aware scoring
    transition_types = allowed_types if allowed_types is not None else list(TransitionType)
    for ttype in transition_types:
        q = score_transition_quality(source, target, ttype, overlap_duration=8.0)

        # --- Phrase/Structure modifiers ---
        if ttype == TransitionType.BEATMATCHED_BLEND:
            # Best when: similar energy, both in verse/groove sections
            if is_energy_similar:
                q *= 1.2
            if source_exit_section == "verse" and target_entry_section == "verse":
                q *= 1.1

        elif ttype == TransitionType.BASS_SWAP:
            # Best when: energy is rising (bass swap creates energy lift)
            if is_energy_rising:
                q *= 1.2
            # Good for chorus-to-chorus or verse-to-chorus
            if target_entry_section == "chorus":
                q *= 1.15
            # Risky if source has very heavy bass and target does too
            if (source.analysis.low_energy > 0.45 and target.analysis.low_energy > 0.45):
                q *= 0.6

        elif ttype == TransitionType.FILTER_SWEEP:
            # Good for building tension (energy rising into chorus)
            if is_energy_rising and target_entry_section == "chorus":
                q *= 1.3
            # Good for verse-to-verse transitions
            if source_exit_section == "verse" and target_entry_section == "verse":
                q *= 1.1

        elif ttype == TransitionType.ECHO_OUT:
            # Best when: energy is dropping, or source is in outro
            if is_energy_dropping:
                q *= 1.2
            if source_exit_section == "outro":
                q *= 1.3
            # Good fallback when BPM mismatch is large
            if bpm_delta > 0.10:
                q *= 1.15

        elif ttype == TransitionType.PHRASE_CUT:
            # Clean cut at phrase boundary — good for contrasting sections
            if source_exit_section != target_entry_section:
                q *= 1.1
            # Works well when both tracks have clear phrase boundaries
            if (len(source.analysis.phrase_boundaries) > 3 and
                    len(target.analysis.phrase_boundaries) > 3):
                q *= 1.1

        elif ttype == TransitionType.CROSSFADE:
            # Safe fallback — penalize slightly when better options exist
            if bpm_delta < 0.05 and is_energy_similar:
                q *= 0.85  # Blend would be better

        elif ttype == TransitionType.LOOP_BLEND:
            # Needs very stable energy and similar structure
            if is_energy_similar and source_exit_section == "verse":
                q *= 1.15

        elif ttype == TransitionType.MASHUP:
            # MASHUP requires stems — give it a strong bonus when both have stems
            if both_have_stems:
                q *= 1.4  # Strong bonus: stem separation makes this transition viable
                # Extra bonus when both have vocals (mashup shines when combining vocals + instrumentals)
                if source_has_vocals and target_has_vocals:
                    q *= 1.2
                # Bonus when energy levels are complementary
                if abs(source.mean_energy - target.mean_energy) > 0.15:
                    q *= 1.1
            else:
                # No stems — cannot do a real mashup, only crossfade fallback
                q *= 0.3

        # --- Vocal safety modifiers ---
        if source_has_vocals and target_has_vocals:
            # Both tracks have vocals — prefer transitions that handle overlap well
            if ttype == TransitionType.BASS_SWAP:
                q *= 1.1  # Bass swap allows vocals to coexist
            elif ttype == TransitionType.PHRASE_CUT:
                q *= 1.1  # Clean cut avoids vocal overlap
            elif ttype == TransitionType.CROSSFADE:
                q *= 0.8  # Crossfade overlaps vocals
            elif ttype == TransitionType.LOOP_BLEND:
                q *= 0.75  # Loop blend also overlaps vocals

        candidates.append((ttype, q))

    candidates.sort(key=lambda x: x[1], reverse=True)

    if not candidates:
        return (TransitionType.PHRASE_CUT, 0.3, "No suitable transition found")

    best_type, best_score = candidates[0]

    # Build reasoning with structural context
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

    if is_energy_rising:
        reasoning_parts.append("energy rising")
    elif is_energy_dropping:
        reasoning_parts.append("energy dropping")
    else:
        reasoning_parts.append("similar energy")

    if source_exit_section != "verse":
        reasoning_parts.append(f"source in {source_exit_section}")
    if target_entry_section != "verse":
        reasoning_parts.append(f"target in {target_entry_section}")

    reasoning = f"{best_type.value}: {', '.join(reasoning_parts)}"

    return (best_type, min(1.0, best_score), reasoning)


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

    Uses spectral mid-energy heuristic for compatibility scoring,
    plus the detailed vocal_regions data when available for transition-specific scoring.
    """
    # Quick spectral heuristic for compatibility scoring
    s1_mid = source.analysis.mid_energy
    s2_mid = target.analysis.mid_energy

    if s1_mid > 0.5 and s2_mid > 0.5:
        base_score = 0.6
    elif s1_mid > 0.5 or s2_mid > 0.5:
        base_score = 0.75
    else:
        base_score = 0.9

    # If both have vocal_regions, use the detailed heuristic for better accuracy
    if source.analysis.vocal_regions and target.analysis.vocal_regions:
        from djenius.audio.vocals import score_vocal_overlap
        # Use default transition timing estimate
        src_exit = source.analysis.possible_exit_points[-1] if source.analysis.possible_exit_points else source.duration_sec * 0.85
        tgt_entry = target.analysis.possible_entry_points[0] if target.analysis.possible_entry_points else target.analysis.intro_end + 5
        overlap = 8.0  # typical overlap estimate
        detailed_score = score_vocal_overlap(
            source.analysis.vocal_regions,
            target.analysis.vocal_regions,
            src_exit, tgt_entry, overlap,
        )
        # Blend: weighted average favoring the detailed score
        base_score = 0.4 * base_score + 0.6 * detailed_score

    return base_score


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
