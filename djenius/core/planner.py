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
    recommend_transition_type,
    rank_candidates,
)

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

    Returns:
        A SetPlan with ordered tracks and transition plans.
    """
    if len(tracks) < 2:
        return SetPlan(tracks=tracks)

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Pre-compute compatibility matrix
    logger.info("Computing compatibility matrix for %d tracks...", len(tracks))
    compat_matrix = _build_compatibility_matrix(tracks)

    # Beam search for optimal ordering
    logger.info("Running beam search (width=%d)...", beam_width)
    best_path = _beam_search(
        tracks=tracks,
        compat_matrix=compat_matrix,
        target_duration=target_duration_sec,
        beam_width=beam_width,
        max_tracks=max_tracks or len(tracks),
        energy_profile=energy_profile,
    )

    # Build the set plan with transition details
    logger.info("Building transition plans for %d tracks...", len(best_path))
    set_plan = _build_set_plan(
        best_path=best_path,
        compat_matrix=compat_matrix,
        target_duration=target_duration_sec,
        energy_profile=energy_profile,
        max_transition_bars=max_transition_length_bars,
    )

    return set_plan


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


def _beam_search(
    tracks: list[TrackProfile],
    compat_matrix: dict[tuple[str, str], CompatibilityScore],
    target_duration: float,
    beam_width: int,
    max_tracks: int,
    energy_profile: EnergyProfile,
) -> list[TrackProfile]:
    """Find the best track ordering using beam search."""
    track_by_id = {t.id: t for t in tracks}

    # Initialize beam with all possible starting tracks
    # Score starting tracks by energy profile
    start_scores = []
    for t in tracks:
        energy_pref = _starting_energy_preference(t, energy_profile)
        start_scores.append((t, energy_pref))

    start_scores.sort(key=lambda x: x[1], reverse=True)
    initial_tracks = [t for t, _ in start_scores[:beam_width]]

    # Each beam state: (track_ids, total_score, total_duration)
    beams = []
    for t in initial_tracks:
        beams.append(([t.id], 0.0, t.duration_sec))

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
                edge_score = compat.overall_score

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
        return avg_score * 0.7 + duration_fit * 0.2 + trajectory_bonus * 0.1

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
        score = -variance * 0.2

    elif energy_profile == EnergyProfile.WARMUP_TO_PEAK:
        # Expect: start low, peak around 70%, stay or drop slightly
        peak_expected_pos = int(n * 0.7)
        # Penalty if peak is too early
        actual_peak_pos = int(np.argmax(energies))
        if actual_peak_pos < peak_expected_pos * 0.6:
            score -= 0.1  # Peaked too early
        # Penalty if start is too high
        if energies[0] > 0.6:
            score -= (energies[0] - 0.6) * 0.3
        # Reward gradual build
        diffs = np.diff(energies)
        early_increases = diffs[:peak_expected_pos]
        if len(early_increases) > 0:
            positive = np.sum(early_increases > 0) / len(early_increases)
            score += positive * 0.1

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
) -> SetPlan:
    """Convert a track ordering into a full SetPlan with transitions."""
    transitions = []
    total_duration = 0.0

    for i in range(len(best_path) - 1):
        source = best_path[i]
        target = best_path[i + 1]

        # Get compatibility
        compat = compat_matrix.get((source.id, target.id))
        if compat is None:
            compat = score_compatibility(source, target)

        # Recommend transition type
        ttype, conf, reasoning = recommend_transition_type(source, target)

        # Calculate timing
        avg_bpm = (source.bpm + target.bpm) / 2
        bar_duration = 4 * 60.0 / max(avg_bpm, 60)

        # Determine transition length using phrase-aware scoring
        from djenius.core.phrasing import (
            score_entry_point, score_exit_point, compute_transition_length_bars,
        )
        source_exit_candidates = source.analysis.possible_exit_points
        target_entry_candidates = target.analysis.possible_entry_points

        # Score the best exit/entry points
        best_exit_score = 0.0
        best_exit_time = source.duration_sec * 0.85
        for t in source_exit_candidates:
            s = score_exit_point(
                t, source.analysis.bar_times, source.analysis.bar_energies,
                source.analysis.outro_start, source.duration_sec, source.bpm,
            )
            if s > best_exit_score:
                best_exit_score = s
                best_exit_time = t

        best_entry_score = 0.0
        best_entry_time = target.analysis.intro_end + 5.0
        for t in target_entry_candidates:
            s = score_entry_point(
                t, target.analysis.bar_times, target.analysis.bar_energies,
                target.analysis.intro_end, target.duration_sec, target.bpm,
            )
            if s > best_entry_score:
                best_entry_score = s
                best_entry_time = t

        length_bars = compute_transition_length_bars(
            best_exit_score, best_entry_score, avg_bpm,
            max_bars=max_transition_bars,
        )
        overlap = bar_duration * length_bars

        # Use best scored points
        source_exit = best_exit_time
        target_entry = best_entry_time

        # Determine if time-stretching is needed
        bpm_delta_pct = abs(source.bpm - target.bpm) / max(source.bpm, 1.0) * 100
        requires_stretch = bpm_delta_pct > 1.0
        stretch_amount = 0.0
        target_bpm = 0.0

        if requires_stretch:
            # Determine stretch direction (prefer stretching the shorter/less prominent track)
            if compat.tempo_score > 0.5:
                target_bpm = source.bpm
                stretch_amount = bpm_delta_pct
            else:
                target_bpm = 0  # Don't stretch
                requires_stretch = False

        transition = TransitionPlan(
            source_track_id=source.id,
            target_track_id=target.id,
            transition_type=ttype,
            source_exit_time=round(source_exit, 3),
            target_entry_time=round(target_entry, 3),
            overlap_duration=round(overlap, 3),
            length_bars=length_bars,
            target_bpm=target_bpm,
            requires_stretch=requires_stretch,
            stretch_amount_pct=round(stretch_amount, 1),
            compatibility_score=compat,
            confidence=conf,
            reasoning=reasoning,
        )
        transitions.append(transition)

        # Track duration contribution
        if i == 0:
            total_duration += source.duration_sec
        total_duration += target.duration_sec - overlap

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
            float(np.mean([t.compatibility_score.overall_score for t in transitions
                          if t.compatibility_score])) if transitions else 0.0,
            3,
        ),
    )
