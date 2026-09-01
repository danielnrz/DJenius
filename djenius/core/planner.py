"""Set planner - constructs an optimal DJ set from a library of tracks.

Uses beam search to find a high-scoring track ordering that forms
a coherent musical journey.
"""

from __future__ import annotations

import logging
import random
from typing import Optional

import numpy as np

from djenius.core.models import (
    TrackProfile, SetPlan, TransitionPlan, TransitionType,
    CompatibilityScore, EnergyProfile,
)
from djenius.core.scorer import (
    score_compatibility,
    compute_preference_bonuses,
    score_with_preferences,
)
from djenius.core.intent import SetIntent

logger = logging.getLogger(__name__)


def plan_set(
    tracks: list[TrackProfile],
    target_duration_sec: float = 1800.0,  # 30 minutes
    energy_profile: EnergyProfile = EnergyProfile.STEADY,
    beam_width: int = 15,
    max_transition_length_bars: int = 16,
    preferred_bpm_range: Optional[tuple[float, float]] = None,
    max_tracks: Optional[int] = None,
    seed: Optional[int] = None,
    intent: Optional[SetIntent] = None,
    preference_bonuses: Optional[dict] = None,
) -> SetPlan:
    """Plan an optimal set from available tracks.

    Args:
        tracks: Available tracks to choose from.
        target_duration_sec: Target set length in seconds.
        energy_profile: How the set energy should evolve.
        beam_width: Number of candidate paths to keep at each step.
        max_transition_length_bars: Max bars for any transition.
        preferred_bpm_range: Optional BPM range to prefer.
        max_tracks: Maximum number of tracks in the set.
        seed: Random seed for reproducibility.
        intent: Optional SetIntent with user preferences and constraints.
        preference_bonuses: Optional dict from PreferenceProfile.get_scoring_bonuses().

    Returns:
        A SetPlan with ordered tracks and transition plans.
    """
    if len(tracks) < 2:
        return SetPlan(tracks=tracks)

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Derive parameters from intent if provided
    effective_energy_profile = energy_profile
    effective_bpm_range = preferred_bpm_range
    effective_max_tracks = max_tracks
    allowed_transition_types = None
    effective_max_transition_bars = max_transition_length_bars

    if intent:
        effective_energy_profile = intent.effective_energy_profile()
        effective_bpm_range = preferred_bpm_range or (
            (intent.bpm_min, intent.bpm_max) if intent.bpm_min and intent.bpm_max else None
        )
        # Apply hard constraints: filter tracks by intent constraints
        tracks = _filter_tracks_by_intent(tracks, intent)
        if len(tracks) < 2:
            logger.warning("Intent filtering left fewer than 2 tracks. Using all tracks.")
            tracks = tracks  # Fall back to all tracks
        effective_max_tracks = max_tracks  # Keep original max_tracks
        allowed_transition_types = intent.allowed_transition_types()
        _, intent_max_bars = intent.effective_transition_length_bars()
        effective_max_transition_bars = min(max_transition_length_bars, intent_max_bars)

    # Merge preference bonuses
    prefs = preference_bonuses or {}
    liked = prefs.get("liked_tracks", set())
    disliked = prefs.get("disliked_tracks", set())
    bpm_pref = prefs.get("preferred_bpm_range")
    energy_pref = prefs.get("preferred_energy_range")
    preferred_trans = prefs.get("preferred_transition_types", {})
    disliked_trans = prefs.get("disliked_transition_types", {})

    # Pre-compute compatibility matrix
    logger.info("Computing compatibility matrix for %d tracks...", len(tracks))
    compat_matrix = _build_compatibility_matrix(tracks)
    musical_edge_matrix = _build_musical_edge_matrix(
        tracks,
        effective_energy_profile,
        intent,
        allowed_transition_types,
    )

    # Beam search for optimal ordering
    logger.info("Running beam search (width=%d)...", beam_width)
    best_path = _beam_search(
        tracks=tracks,
        compat_matrix=compat_matrix,
        target_duration=target_duration_sec,
        beam_width=beam_width,
        max_tracks=effective_max_tracks or len(tracks),
        energy_profile=effective_energy_profile,
        liked_tracks=liked,
        disliked_tracks=disliked,
        preferred_bpm_range=bpm_pref or effective_bpm_range,
        preferred_energy_range=energy_pref,
        preferred_transition_types=preferred_trans,
        disliked_transition_types=disliked_trans,
        musical_edge_matrix=musical_edge_matrix,
    )

    # Build the set plan with transition details
    logger.info("Building transition plans for %d tracks...", len(best_path))
    set_plan = _build_set_plan(
        best_path=best_path,
        compat_matrix=compat_matrix,
        target_duration=target_duration_sec,
        energy_profile=effective_energy_profile,
        max_transition_bars=effective_max_transition_bars,
        allowed_transition_types=allowed_transition_types,
        intent=intent,
    )

    # Attach intent to plan
    set_plan.intent_used = intent

    return set_plan


def plan_ordered_set(
    tracks: list[TrackProfile],
    ordered_ids: list[str],
    target_duration_sec: float = 1800.0,
    intent: Optional[SetIntent] = None,
    max_transition_length_bars: int = 16,
) -> SetPlan:
    """Build a validated plan for a user-selected track order.

    This is the small editing seam used by the local application.  It keeps
    the planner's existing transition candidate search and safety rules while
    fixing only the track order chosen by the user.
    """
    by_id = {track.id: track for track in tracks}
    if len(ordered_ids) < 2:
        raise ValueError("A set needs at least two tracks")
    if len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError("A set cannot contain duplicate tracks")
    missing = [track_id for track_id in ordered_ids if track_id not in by_id]
    if missing:
        raise ValueError("Edited plan contains tracks that are not in the library")

    ordered_tracks = [by_id[track_id] for track_id in ordered_ids]
    energy_profile = (
        intent.effective_energy_profile() if intent else EnergyProfile.STEADY
    )
    allowed_types = intent.allowed_transition_types() if intent else None
    max_bars = max_transition_length_bars
    if intent:
        _minimum, intent_max = intent.effective_transition_length_bars()
        max_bars = min(max_bars, intent_max)

    plan = _build_set_plan(
        best_path=ordered_tracks,
        compat_matrix=_build_compatibility_matrix(ordered_tracks),
        target_duration=target_duration_sec,
        energy_profile=energy_profile,
        max_transition_bars=max_bars,
        allowed_transition_types=allowed_types,
        intent=intent,
    )
    plan.intent_used = intent
    return plan


def _build_compatibility_matrix(
    tracks: list[TrackProfile],
) -> dict[tuple[str, str], CompatibilityScore]:
    """Pre-compute compatibility scores for all track pairs."""
    matrix = {}
    for i, t1 in enumerate(tracks):
        for j, t2 in enumerate(tracks):
            if i != j:
                score = score_compatibility(t1, t2)
                matrix[(t1.id, t2.id)] = score
    return matrix


def _build_musical_edge_matrix(
    tracks: list[TrackProfile],
    energy_profile: EnergyProfile,
    intent: Optional[SetIntent],
    allowed_transition_types: Optional[list[TransitionType]],
) -> dict[tuple[str, str], float]:
    """Estimate each edge using local transition and landing context."""
    from djenius.core.transition_quality import (
        playtime_bounds,
        score_transition_candidate,
        target_entry_limit,
    )

    transition_types = allowed_transition_types or [
        TransitionType.CROSSFADE,
        TransitionType.BEATMATCHED_BLEND,
        TransitionType.FILTER_SWEEP,
        TransitionType.PHRASE_CUT,
    ]
    matrix = {}
    for source in tracks:
        minimum, preferred, maximum = playtime_bounds(source)
        source_points = [
            point for point in _musical_points(source, is_exit=True)
            if minimum <= point <= min(maximum, source.duration_sec - 8.0)
        ]
        if not source_points:
            continue
        source_exit = min(source_points, key=lambda point: abs(point - preferred))
        for target in tracks:
            if source.id == target.id:
                continue
            target_points = [
                point for point in _musical_points(target, is_exit=False)
                if 0.0 <= point <= target_entry_limit(target)
            ]
            if not target_points:
                continue
            best = 0.0
            for target_entry in target_points[:24]:
                for transition_type in transition_types:
                    bars = 4 if transition_type in (
                        TransitionType.PHRASE_CUT,
                        TransitionType.ECHO_OUT,
                        TransitionType.LOOP_BLEND,
                    ) else 8
                    overlap = bars * 4 * 60.0 / max((source.bpm + target.bpm) / 2, 60)
                    if source_exit + overlap > source.duration_sec:
                        continue
                    quality, _recipe, _details = score_transition_candidate(
                        source,
                        target,
                        source_exit,
                        target_entry,
                        overlap,
                        transition_type,
                        intent=intent,
                        energy_profile=energy_profile,
                    )
                    best = max(best, quality.overall_score)
            matrix[(source.id, target.id)] = best
    return matrix


def _filter_tracks_by_intent(
    tracks: list[TrackProfile],
    intent: SetIntent,
) -> list[TrackProfile]:
    """Apply hard constraints from SetIntent to filter tracks.

    This removes tracks that violate non-negotiable constraints:
    - BPM range (if both min and max specified)
    - Energy range (if both min and max specified)
    - must_exclude list
    - must_include tracks are always kept

    Returns the filtered list. If filtering removes all tracks,
    returns the original list as a safety fallback.
    """
    must_include_ids = set(intent.must_include)
    must_exclude_ids = set(intent.must_exclude)

    filtered = []
    for track in tracks:
        # Always keep must_include tracks
        if track.id in must_include_ids or track.metadata.filepath in must_include_ids:
            filtered.append(track)
            continue

        # Remove must_exclude tracks
        if track.id in must_exclude_ids or track.metadata.filepath in must_exclude_ids:
            continue

        # BPM constraint
        if intent.bpm_min is not None and track.bpm < intent.bpm_min:
            continue
        if intent.bpm_max is not None and track.bpm > intent.bpm_max:
            continue

        # Energy constraint
        if intent.energy_min is not None and track.mean_energy < intent.energy_min:
            continue
        if intent.energy_max is not None and track.mean_energy > intent.energy_max:
            continue

        filtered.append(track)

    # Safety: if filtering removed everything, return original
    if len(filtered) < 2:
        logger.warning(
            "Intent filtering reduced tracks from %d to %d. Using all tracks.",
            len(tracks), len(filtered),
        )
        return tracks

    return filtered


def _beam_search(
    tracks: list[TrackProfile],
    compat_matrix: dict[tuple[str, str], CompatibilityScore],
    target_duration: float,
    beam_width: int,
    max_tracks: int,
    energy_profile: EnergyProfile,
    liked_tracks: Optional[set[str]] = None,
    disliked_tracks: Optional[set[str]] = None,
    preferred_bpm_range: Optional[tuple[float, float]] = None,
    preferred_energy_range: Optional[tuple[float, float]] = None,
    preferred_transition_types: Optional[dict[str, float]] = None,
    disliked_transition_types: Optional[dict[str, float]] = None,
    musical_edge_matrix: Optional[dict[tuple[str, str], float]] = None,
) -> list[TrackProfile]:
    """Find the best track ordering using beam search.

    Applies preference bonuses to bias the search toward user taste
    while keeping safety-critical signals (key, BPM) dominant.
    """
    track_by_id = {t.id: t for t in tracks}

    # Initialize beam with all possible starting tracks
    # Score starting tracks by energy profile
    start_scores = []
    for t in tracks:
        energy_pref = _starting_energy_preference(t, energy_profile)
        start_scores.append((t, energy_pref))

    start_scores.sort(key=lambda x: x[1], reverse=True)
    opener_count = beam_width
    if energy_profile == EnergyProfile.WARMUP_TO_PEAK:
        opener_count = min(beam_width, max(2, int(np.ceil(len(tracks) / 3))))
    initial_tracks = [t for t, _ in start_scores[:opener_count]]

    # Each beam state: (track_ids, total_score, total_duration)
    beams = []
    start_score_by_id = {track.id: score for track, score in start_scores}
    for t in initial_tracks:
        beams.append(([t.id], start_score_by_id[t.id] * 0.35, t.duration_sec))

    best_paths = []

    for step in range(max_tracks - 1):
        candidates = []

        for path_ids, score, duration in beams:
            if len(path_ids) >= max_tracks:
                best_paths.append((path_ids, score, duration))
                continue

            last_id = path_ids[-1]
            last_track = track_by_id[last_id]

            # Get candidates
            for t in tracks:
                if t.id in path_ids:
                    continue

                compat = compat_matrix.get((last_id, t.id))
                if compat is None:
                    continue

                # Score this transition
                musical_edge = (musical_edge_matrix or {}).get(
                    (last_id, t.id), compat.overall_score,
                )
                edge_score = 0.45 * compat.overall_score + 0.55 * musical_edge

                # Apply preference bonuses (bounded to [-0.15, +0.15])
                pref_bonuses = compute_preference_bonuses(
                    target=t,
                    liked_tracks=liked_tracks,
                    disliked_tracks=disliked_tracks,
                    preferred_bpm_range=preferred_bpm_range,
                    preferred_energy_range=preferred_energy_range,
                    preferred_transition_types=preferred_transition_types,
                    disliked_transition_types=disliked_transition_types,
                )
                edge_score = score_with_preferences(edge_score, pref_bonuses)

                # Apply energy profile guidance
                energy_bonus = _energy_progression_bonus(
                    len(path_ids), max_tracks, energy_profile,
                    last_track.mean_energy, t.mean_energy
                )

                # Estimate overlap duration (~8 bars)
                avg_bpm = (last_track.bpm + t.bpm) / 2
                bar_duration = 4 * 60.0 / max(avg_bpm, 60)
                overlap = min(bar_duration * 16, t.duration_sec * 0.5)

                new_duration = duration + t.duration_sec - overlap
                new_score = score + edge_score + energy_bonus

                candidates.append(
                    (path_ids + [t.id], new_score, new_duration)
                )

        if not candidates:
            break

        # Sort by score and keep top beam_width
        candidates.sort(key=lambda x: x[1] / max(len(x[0]), 1), reverse=True)

        # Prune paths that exceed target duration
        active = []
        for path_ids, score, duration in candidates[:beam_width * 3]:
            if duration >= target_duration:
                best_paths.append((path_ids, score, duration))
            else:
                active.append((path_ids, score, duration))

        beams = active[:beam_width]

        if not beams:
            break

    # Add remaining beams to candidates
    for beam in beams:
        best_paths.append(beam)

    # Select best path
    if not best_paths:
        return list(tracks[:max_tracks])

    # Score paths: prefer those close to target duration with high quality
    def path_key(item):
        path_ids, score, duration = item
        duration_fit = 1.0 - abs(duration - target_duration) / max(target_duration, 1)
        avg_score = score / max(len(path_ids), 1)
        # Add energy trajectory bonus
        trajectory_bonus = _score_energy_trajectory(path_ids, track_by_id, energy_profile)
        warmup_end_penalty = 0.0
        if (
            energy_profile == EnergyProfile.WARMUP_TO_PEAK
            and track_by_id[path_ids[-1]].mean_energy
            < track_by_id[path_ids[0]].mean_energy + 0.02
        ):
            warmup_end_penalty = 0.30
        return (
            avg_score * 0.6
            + duration_fit * 0.15
            + trajectory_bonus * 0.25
            - warmup_end_penalty
        )

    best_paths.sort(key=path_key, reverse=True)
    best_path_ids = best_paths[0][0]

    return [track_by_id[tid] for tid in best_path_ids]


def _starting_energy_preference(
    track: TrackProfile,
    profile: EnergyProfile,
) -> float:
    """Score how suitable a track is as a set opener."""
    energy = track.mean_energy

    if profile == EnergyProfile.WARMUP_TO_PEAK:
        return max(0.0, 1.0 - energy)  # Prefer low energy start
    elif profile == EnergyProfile.PEAK_EARLY:
        return energy  # Prefer high energy start
    elif profile == EnergyProfile.COOLDOWN:
        return max(0.0, 1.0 - energy * 0.5)
    elif profile == EnergyProfile.SLOW_BUILD:
        return max(0.0, 1.0 - energy * 0.8)
    else:
        return 0.5 + (1.0 - abs(energy - 0.5)) * 0.5


def _energy_progression_bonus(
    position: int,
    total: int,
    profile: EnergyProfile,
    from_energy: float,
    to_energy: float,
) -> float:
    """Score the energy change based on the set profile.

    Uses position-aware scoring to guide the energy journey.
    """
    progress = position / max(total - 1, 1)
    energy_change = to_energy - from_energy

    if profile == EnergyProfile.STEADY:
        # Prefer minimal change
        return max(0.0, 1.0 - abs(energy_change) * 2) * 0.1

    elif profile == EnergyProfile.SLOW_BUILD:
        # Prefer gradual increase
        if energy_change >= 0:
            return energy_change * 0.15 * (1 + progress)
        else:
            return energy_change * 0.1

    elif profile == EnergyProfile.WARMUP_TO_PEAK:
        # Build until 70% then maintain
        if progress < 0.7:
            return energy_change * 0.2 if energy_change >= 0 else -0.05
        else:
            return max(0.0, 1.0 - abs(energy_change) * 3) * 0.1

    elif profile == EnergyProfile.WAVE:
        # Oscillate
        target_wave = 0.5 + 0.4 * np.sin(2 * np.pi * progress)
        return -abs(to_energy - target_wave) * 0.1

    elif profile == EnergyProfile.PEAK_EARLY:
        if progress < 0.3:
            return energy_change * 0.2 if energy_change >= 0 else -0.05
        else:
            return -energy_change * 0.1 if energy_change > 0 else 0.05

    elif profile == EnergyProfile.PEAK_LATE:
        if progress > 0.6:
            return energy_change * 0.2 if energy_change >= 0 else -0.05
        else:
            return max(0.0, 1.0 - abs(energy_change) * 3) * 0.05

    elif profile == EnergyProfile.COOLDOWN:
        if progress > 0.5:
            return -energy_change * 0.15 if energy_change > 0 else 0.05
        else:
            return max(0.0, 1.0 - abs(energy_change) * 3) * 0.05

    return 0.0


def _score_energy_trajectory(
    path_ids: list[str],
    track_by_id: dict[str, TrackProfile],
    energy_profile: EnergyProfile,
) -> float:
    """Score the overall energy trajectory of a path against the profile.

    Computes the full energy curve and penalizes deviations from the
    expected shape. Returns a bonus/penalty to add to the path score.
    """
    if len(path_ids) < 3:
        return 0.0

    energies = [track_by_id[tid].mean_energy for tid in path_ids]
    n = len(energies)
    score = 0.0

    if energy_profile == EnergyProfile.STEADY:
        # Penalize variance
        variance = np.var(energies)
        score = float(0.15 - variance * 2.0)

    elif energy_profile == EnergyProfile.SLOW_BUILD:
        diffs = np.diff(energies)
        positive = float(np.mean(diffs >= -0.02)) if len(diffs) else 0.0
        severe_drops = float(np.sum(np.minimum(diffs + 0.08, 0.0)))
        net_change = energies[-1] - energies[0]
        score = positive * 0.18 + net_change * 0.35 + severe_drops * 1.2

    elif energy_profile == EnergyProfile.WARMUP_TO_PEAK:
        # Expect: start low, peak around 70%, stay or drop slightly
        peak_expected_pos = int(n * 0.7)
        # Penalty if peak is too early
        actual_peak_pos = int(np.argmax(energies))
        if actual_peak_pos < peak_expected_pos * 0.6:
            score -= 0.25  # Peaked too early
        # Penalty if start is too high
        if energies[0] > 0.6:
            score -= (energies[0] - 0.6) * 0.8
        # Reward gradual build
        diffs = np.diff(energies)
        early_increases = diffs[:peak_expected_pos]
        if len(early_increases) > 0:
            positive = np.sum(early_increases > 0) / len(early_increases)
            score += positive * 0.25
            early_drops = np.minimum(early_increases + 0.05, 0.0)
            score += float(np.sum(early_drops)) * 1.5
        score += (energies[min(peak_expected_pos, n - 1)] - energies[0]) * 0.35

    elif energy_profile == EnergyProfile.COOLDOWN:
        # Expect: peak early, then decrease
        # Penalty if energy rises at the end
        end_diff = energies[-1] - energies[-2] if len(energies) >= 2 else 0
        if end_diff > 0.1:
            score -= 0.15  # Energy rising in cooldown
        # Penalize if start is too low (should already be moderate-high)
        if energies[0] < 0.3:
            score -= (0.3 - energies[0]) * 0.2

    elif energy_profile == EnergyProfile.WAVE:
        # Reward oscillation
        diffs = np.diff(energies)
        sign_changes = np.sum(np.diff(np.sign(diffs)) != 0) if len(diffs) >= 2 else 0
        score = sign_changes * 0.02  # More oscillations = better

    elif energy_profile == EnergyProfile.PEAK_LATE:
        peak_expected_pos = int(n * 0.75)
        actual_peak_pos = int(np.argmax(energies))
        # Penalty if peak is too early
        if actual_peak_pos < peak_expected_pos * 0.5:
            score -= 0.12
        # Reward: energy should increase after midpoint
        mid = n // 2
        if len(energies) > mid + 1:
            late_trend = energies[-1] - energies[mid]
            if late_trend > 0:
                score += 0.08

    elif energy_profile == EnergyProfile.PEAK_EARLY:
        peak_expected_pos = int(n * 0.25)
        actual_peak_pos = int(np.argmax(energies))
        if actual_peak_pos > peak_expected_pos * 2:
            score -= 0.1  # Peak too late

    return score


def _compute_set_energy_profile(
    path_ids: list[str],
    track_by_id: dict[str, TrackProfile],
) -> dict:
    """Compute the energy trajectory of a set path for diagnostics.

    Returns a dict with energy values at each position plus expected
    trajectory for the given profile.
    """
    energies = [track_by_id[tid].mean_energy for tid in path_ids]
    n = len(energies)

    # Compute expected trajectory shape
    expected = [0.5] * n
    x = np.linspace(0, 1, n)

    return {
        "energies": energies,
        "expected_shapes": {
            "steady": [0.5] * n,
            "warmup_to_peak": list(
                np.clip(0.3 + 0.6 * np.minimum(x / 0.7, 1.0), 0, 1)
            ),
            "cooldown": list(
                np.clip(0.7 - 0.5 * np.maximum((x - 0.3) / 0.7, 0), 0, 1)
            ),
            "wave": list(0.5 + 0.3 * np.sin(2 * np.pi * x)),
            "slow_build": list(0.3 + 0.5 * x),
            "peak_early": list(
                np.clip(
                    0.4 + 0.5 * np.where(x < 0.3, x / 0.3, 1.0 - (x - 0.3) / 0.7),
                    0, 1,
                )
            ),
            "peak_late": list(
                np.clip(
                    0.4 + 0.5 * np.where(x < 0.6, x / 0.6 * 0.5, (x - 0.6) / 0.4),
                    0, 1,
                )
            ),
        },
    }


def _build_set_plan(
    best_path: list[TrackProfile],
    compat_matrix: dict[tuple[str, str], CompatibilityScore],
    target_duration: float,
    energy_profile: EnergyProfile,
    max_transition_bars: int,
    allowed_transition_types: Optional[list[TransitionType]] = None,
    intent: Optional[SetIntent] = None,
) -> SetPlan:
    """Jointly select musical exit, entry, length, and transition style."""
    from djenius.core.transition_quality import (
        playtime_bounds,
        score_transition_candidate,
        target_entry_limit,
    )

    transitions = []
    total_duration = 0.0
    transition_types = allowed_transition_types or list(TransitionType)

    for i in range(len(best_path) - 1):
        source = best_path[i]
        target = best_path[i + 1]
        compat = compat_matrix.get((source.id, target.id))
        if compat is None:
            compat = score_compatibility(source, target)
        avg_bpm = (source.bpm + target.bpm) / 2
        bar_duration = 4 * 60.0 / max(avg_bpm, 60)
        incoming_cursor = 0.0
        if transitions:
            previous = transitions[-1]
            previous_source = best_path[i - 1]
            incoming_cursor = previous.target_entry_time + _target_consumed_seconds(
                previous.transition_type,
                previous.overlap_duration,
                previous_source.bpm,
                source.bpm,
                previous.requires_stretch,
            )

        minimum_body, _preferred_body, maximum_body = playtime_bounds(source)
        source_candidates = _musical_points(source, is_exit=True)
        target_candidates = _musical_points(target, is_exit=False)
        candidate_plans = []
        pair_analysis_confidence = min(
            source.analysis.analysis_confidence,
            target.analysis.analysis_confidence,
            source.analysis.bpm_confidence,
            target.analysis.bpm_confidence,
        )
        candidate_types = transition_types
        if pair_analysis_confidence < 0.55:
            conservative_types = {
                TransitionType.CROSSFADE,
                TransitionType.BEATMATCHED_BLEND,
                TransitionType.FILTER_SWEEP,
            }
            candidate_types = [
                transition_type for transition_type in transition_types
                if transition_type in conservative_types
            ] or [TransitionType.CROSSFADE]

        for transition_type in candidate_types:
            for length_bars in _length_options(
                transition_type, intent, max_transition_bars,
            ):
                overlap = bar_duration * length_bars
                requires_stretch = (
                    transition_type == TransitionType.BEATMATCHED_BLEND
                    and abs(source.bpm - target.bpm) / max(source.bpm, 1.0) > 0.01
                    and compat.tempo_score > 0.5
                )
                target_bpm = source.bpm if requires_stretch else 0.0
                target_consumed = _target_consumed_seconds(
                    transition_type, overlap, source.bpm, target.bpm, requires_stretch,
                )
                earliest_exit = incoming_cursor + minimum_body
                latest_exit = min(
                    incoming_cursor + maximum_body,
                    source.duration_sec - overlap,
                )
                entry_limit = min(
                    target_entry_limit(target),
                    target.duration_sec - target_consumed - 20.0,
                )
                exits = [
                    point for point in source_candidates
                    if earliest_exit <= point <= latest_exit
                ]
                entries = [
                    point for point in target_candidates
                    if 0.0 <= point <= entry_limit
                ]
                for source_exit in exits:
                    for target_entry in entries:
                        quality, recipe, context = score_transition_candidate(
                            source,
                            target,
                            source_exit,
                            target_entry,
                            overlap,
                            transition_type,
                            incoming_source_cursor=incoming_cursor,
                            intent=intent,
                            energy_profile=energy_profile,
                        )
                        if (
                            intent
                            and intent.effective_vocal_preference() == "vocal_safe"
                            and context["vocal_collision"] > 0.16
                            and transition_type not in (
                                TransitionType.PHRASE_CUT,
                                TransitionType.MASHUP,
                            )
                        ):
                            continue
                        if (
                            intent
                            and intent.effective_transition_style() == "smooth"
                            and context["vocal_collision"] > 0.25
                        ):
                            continue
                        if context["predicted_transition_trough_db"] > 3.5:
                            continue
                        if (
                            energy_profile == EnergyProfile.WARMUP_TO_PEAK
                            and i < max(1, int((len(best_path) - 1) * 0.7))
                            and context["energy_delta_db"] < -2.5
                        ):
                            continue
                        aggressive = transition_type in (
                            TransitionType.BASS_SWAP,
                            TransitionType.PHRASE_CUT,
                            TransitionType.ECHO_OUT,
                            TransitionType.LOOP_BLEND,
                            TransitionType.MASHUP,
                        )
                        selection_score = quality.overall_score
                        if aggressive and recipe.confidence < 0.62:
                            selection_score *= 0.65
                        candidate_plans.append((
                            selection_score,
                            source_exit,
                            target_entry,
                            overlap,
                            length_bars,
                            transition_type,
                            requires_stretch,
                            target_bpm,
                            quality,
                            recipe,
                            context,
                        ))

        if not candidate_plans:
            raise ValueError(
                f"No forward transition window remains in {source.title}: "
                f"cursor {incoming_cursor:.3f}s, duration {source.duration_sec:.3f}s"
            )

        candidate_plans.sort(
            key=lambda item: (
                item[0],
                item[8].phrase_alignment_score,
                item[8].target_landing_score,
                -item[1],
            ),
            reverse=True,
        )
        (
            _selection_score,
            source_exit,
            target_entry,
            overlap,
            length_bars,
            transition_type,
            requires_stretch,
            target_bpm,
            quality,
            recipe,
            context,
        ) = candidate_plans[0]
        bpm_delta_pct = abs(source.bpm - target.bpm) / max(source.bpm, 1.0) * 100
        transitions.append(TransitionPlan(
            source_track_id=source.id,
            target_track_id=target.id,
            transition_type=transition_type,
            source_exit_time=round(source_exit, 3),
            target_entry_time=round(target_entry, 3),
            overlap_duration=round(overlap, 3),
            length_bars=length_bars,
            target_bpm=target_bpm,
            requires_stretch=requires_stretch,
            stretch_amount_pct=round(bpm_delta_pct if requires_stretch else 0.0, 1),
            compatibility_score=compat,
            confidence=recipe.confidence,
            reasoning=f"{transition_type.value}: {recipe.reasoning}",
            quality_score=quality,
            recipe=recipe,
            context=context,
        ))

    final_track_end_time = None
    if transitions:
        total_duration = transitions[0].source_exit_time
        for index, transition in enumerate(transitions):
            total_duration += transition.overlap_duration
            target = best_path[index + 1]
            source = best_path[index]
            target_cursor = transition.target_entry_time + _target_consumed_seconds(
                transition.transition_type,
                transition.overlap_duration,
                source.bpm,
                target.bpm,
                transition.requires_stretch,
            )
            if index + 1 < len(transitions):
                total_duration += max(0.0, transitions[index + 1].source_exit_time - target_cursor)
            else:
                _minimum, preferred_final, maximum_final = playtime_bounds(target)
                final_body = min(
                    maximum_final,
                    max(preferred_final, target_duration - total_duration),
                    max(0.0, target.duration_sec - target_cursor),
                )
                final_track_end_time = min(
                    target.duration_sec,
                    target_cursor + final_body,
                )
                total_duration += max(0.0, final_track_end_time - target_cursor)
    elif best_path:
        total_duration = best_path[0].duration_sec

    return SetPlan(
        tracks=best_path,
        transitions=transitions,
        total_duration_sec=round(total_duration, 1),
        target_duration_sec=target_duration,
        energy_profile=energy_profile,
        avg_transition_confidence=round(
            float(np.mean([t.confidence for t in transitions])) if transitions else 0.0,
            3,
        ),
        score=round(
            float(np.mean([t.quality_score.overall_score for t in transitions
                          if t.quality_score])) if transitions else 0.0,
            3,
        ),
        final_track_end_time=(
            round(final_track_end_time, 3) if final_track_end_time is not None else None
        ),
    )


def _musical_points(track: TrackProfile, is_exit: bool) -> list[float]:
    """Return phrase and grouped-bar candidates without arbitrary timestamps."""
    points = set(track.analysis.phrase_boundaries)
    points.update(
        time_sec for index, time_sec in enumerate(track.analysis.bar_times)
        if index % 4 == 0
    )
    points.update(
        track.analysis.possible_exit_points
        if is_exit else track.analysis.possible_entry_points
    )
    bar_duration = 4 * 60.0 / max(track.bpm, 60.0)
    if len(track.analysis.bar_times) < 8:
        points.update(np.arange(0.0, track.duration_sec, bar_duration * 4))
    return sorted(round(float(point), 4) for point in points if point >= 0.0)


def _length_options(
    transition_type: TransitionType,
    intent: Optional[SetIntent],
    max_transition_bars: int,
) -> list[int]:
    minimum, maximum = (
        intent.effective_transition_length_bars() if intent else (4, max_transition_bars)
    )
    maximum = min(maximum, max_transition_bars)
    if transition_type in (TransitionType.PHRASE_CUT, TransitionType.ECHO_OUT):
        preferred = [4]
    elif transition_type == TransitionType.LOOP_BLEND:
        preferred = [4, 8]
    elif transition_type in (TransitionType.BASS_SWAP, TransitionType.MASHUP):
        preferred = [4, 8]
    elif transition_type == TransitionType.FILTER_SWEEP:
        preferred = [8, 12, 16]
    else:
        preferred = [8, 12, 16]
    allowed = [bars for bars in preferred if bars <= maximum and bars >= min(minimum, 8)]
    return allowed or [max(4, min(maximum, 8))]


def _target_consumed_seconds(
    transition_type: TransitionType,
    overlap_duration: float,
    source_bpm: float,
    target_bpm: float,
    use_time_stretch: bool = True,
) -> float:
    if (
        transition_type == TransitionType.BEATMATCHED_BLEND
        and use_time_stretch
        and source_bpm > 0
        and target_bpm > 0
        and abs(source_bpm - target_bpm) > 0.5
    ):
        return overlap_duration * source_bpm / target_bpm
    return overlap_duration
