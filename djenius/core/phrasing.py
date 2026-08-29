"""Phrase and structural analysis for DJ transitions.

Detects musical phrases, structural sections, and reliable transition points
from beat/bar grids and energy curves. This is DJ Brain logic — it decides
WHAT should happen, not HOW to execute it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PhraseBoundary:
    """A detected phrase boundary with timing and confidence."""
    time_sec: float
    bar_index: int          # which bar this falls on
    confidence: float       # 0.0 to 1.0
    energy_change: float    # magnitude of energy discontinuity


@dataclass
class StructuralSection:
    """A labeled structural section of a track."""
    start_sec: float
    end_sec: float
    label: str              # "intro", "verse", "chorus", "bridge", "outro", "drop"
    energy_level: float     # relative energy (0-1)
    bar_count: int          # number of bars in this section


def build_bar_grid(
    beat_times: list[float],
    bpm: float,
    duration: float,
) -> list[float]:
    """Build a regular bar grid from beat times and BPM.

    Returns evenly-spaced bar onset times covering the full duration.
    This is more reliable than just every-4th-beat because it fills gaps
    where beat detection may have failed.
    """
    if bpm <= 0 or duration <= 0:
        return []

    beat_interval = 60.0 / bpm
    bar_duration = beat_interval * 4  # 4/4 time

    # Use the first beat as phase reference
    if beat_times:
        phase = beat_times[0]
    else:
        phase = 0.0

    bars = []
    t = phase
    while t < duration:
        if t >= 0.0:
            bars.append(round(t, 4))
        t += bar_duration

    return bars


def compute_bar_energies(
    energy_curve: np.ndarray,
    bar_times: list[float],
    bpm: float,
    resolution_hz: float = 1.0,
) -> list[float]:
    """Compute mean energy for each bar from the energy curve.

    Args:
        energy_curve: 1Hz resolution energy values (0-1).
        bar_times: Bar onset times in seconds.
        bpm: BPM for bar duration calculation.
        resolution_hz: Resolution of the energy curve in Hz.

    Returns:
        Mean energy for each bar.
    """
    if not bar_times or bpm <= 0 or len(energy_curve) == 0:
        return []

    beat_interval = 60.0 / bpm
    bar_duration = beat_interval * 4

    bar_energies = []
    for bar_time in bar_times:
        # Convert time to frame index in the energy curve
        start_frame = int(bar_time * resolution_hz)
        end_frame = int((bar_time + bar_duration) * resolution_hz)
        start_frame = max(0, start_frame)
        end_frame = min(len(energy_curve), end_frame)

        if start_frame < end_frame:
            bar_energies.append(float(np.mean(energy_curve[start_frame:end_frame])))
        else:
            bar_energies.append(0.5)

    return bar_energies


def detect_bar_grouped_phrases(
    bar_times: list[float],
    bar_energies: list[float],
    bpm: float,
    min_phrase_bars: int = 8,
    max_phrase_bars: int = 32,
    energy_change_threshold: float = 0.15,
) -> list[PhraseBoundary]:
    """Detect phrase boundaries using energy discontinuities between bars.

    Looks for large energy changes at bar boundaries — these are the most
    musically meaningful places for transitions.

    Args:
        bar_times: Bar onset times in seconds.
        bar_energies: Mean energy per bar.
        bpm: BPM for the track.
        min_phrase_bars: Minimum bars between phrase boundaries.
        max_phrase_bars: Maximum bars between phrase boundaries.
        energy_change_threshold: Minimum absolute energy change to consider.

    Returns:
        List of PhraseBoundary objects sorted by time.
    """
    n_bars = min(len(bar_times), len(bar_energies))
    if n_bars < 3:
        return []

    bar_times = bar_times[:n_bars]
    bar_energies = bar_energies[:n_bars]

    # Compute energy changes between consecutive bars
    energy_changes = np.diff(bar_energies)

    # Find significant energy discontinuities
    candidates = []
    for i, change in enumerate(energy_changes):
        abs_change = abs(change)
        bar_idx = i + 1  # boundary is AT bar i+1 (change from bar i to bar i+1)
        if abs_change >= energy_change_threshold and bar_idx < n_bars:
            candidates.append((bar_idx, abs_change, change))

    # Sort by magnitude (biggest changes first)
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Select boundaries ensuring minimum spacing
    selected = []
    for bar_idx, magnitude, direction in candidates:
        # Check minimum spacing from existing boundaries
        too_close = False
        for sel in selected:
            if abs(bar_idx - sel.bar_index) < min_phrase_bars:
                too_close = True
                break
        if not too_close:
            # Confidence based on magnitude and how clean the change is
            confidence = min(1.0, magnitude / 0.4)  # 0.4 energy change = max confidence
            selected.append(PhraseBoundary(
                time_sec=bar_times[bar_idx],
                bar_index=bar_idx,
                confidence=round(confidence, 3),
                energy_change=round(magnitude, 4),
            ))

    # Sort by time
    selected.sort(key=lambda b: b.time_sec)

    # Ensure maximum spacing: insert boundaries between gaps that are too long
    if selected and bar_times:
        max_gap = max_phrase_bars * (4 * 60.0 / bpm)
        filled = [selected[0]]

        for i in range(1, len(selected)):
            gap = selected[i].time_sec - filled[-1].time_sec
            if gap > max_gap:
                # Insert a boundary in the middle of the gap
                mid_time = (filled[-1].time_sec + selected[i].time_sec) / 2
                mid_bar_idx = int((filled[-1].bar_index + selected[i].bar_index) / 2)
                filled.append(PhraseBoundary(
                    time_sec=round(mid_time, 4),
                    bar_index=mid_bar_idx,
                    confidence=0.4,  # lower confidence for inserted boundaries
                    energy_change=0.0,
                ))
            filled.append(selected[i])

        selected = filled

    return selected


def label_structural_sections(
    bar_times: list[float],
    bar_energies: list[float],
    phrase_boundaries: list[PhraseBoundary],
    duration: float,
) -> list[StructuralSection]:
    """Label structural sections based on energy patterns and phrase boundaries.

    Labels sections as intro/verse/chorus/bridge/outro based on:
    - Energy level relative to the track mean
    - Position within the track (beginning/end)
    - Energy stability (stable = verse, volatile = chorus)

    Args:
        bar_times: Bar onset times in seconds.
        bar_energies: Mean energy per bar.
        phrase_boundaries: Detected phrase boundaries.
        duration: Total track duration in seconds.

    Returns:
        List of StructuralSection objects.
    """
    if not bar_times or not bar_energies:
        return []

    mean_energy = float(np.mean(bar_energies)) if bar_energies else 0.5
    max_energy = float(np.max(bar_energies)) if bar_energies else 1.0

    # Build section boundaries from phrase boundaries + start/end
    boundaries_sec = [0.0]
    for pb in phrase_boundaries:
        if pb.time_sec > 0 and pb.time_sec < duration:
            boundaries_sec.append(pb.time_sec)
    boundaries_sec.append(duration)

    # Don't aggressively filter — trust the phrase detector that found these.
    # Just ensure start (0.0) and end (duration) are present.
    if not boundaries_sec or boundaries_sec[0] != 0.0:
        boundaries_sec.insert(0, 0.0)
    if boundaries_sec[-1] < duration:
        boundaries_sec.append(duration)

    sections = []
    for i in range(len(boundaries_sec) - 1):
        start = boundaries_sec[i]
        end = boundaries_sec[i + 1]

        # Compute section energy
        start_bar = int(start * (len(bar_energies) / max(duration, 1)))
        end_bar = int(end * (len(bar_energies) / max(duration, 1)))
        start_bar = max(0, min(start_bar, len(bar_energies) - 1))
        end_bar = max(start_bar + 1, min(end_bar, len(bar_energies)))

        section_energies = bar_energies[start_bar:end_bar]
        section_energy = float(np.mean(section_energies)) if section_energies else 0.5
        energy_stability = float(np.std(section_energies)) if len(section_energies) > 1 else 0.0

        # Count bars in this section
        bar_duration = 4 * 60.0 / max(mean_energy * 120, 60)  # rough
        section_duration = end - start
        bar_count = max(1, int(round(section_duration / max(bar_duration, 0.1))))

        # Label based on position and energy
        position = (start + end) / 2 / max(duration, 1)
        is_near_start = start < duration * 0.15
        is_near_end = end > duration * 0.85

        if is_near_start and section_energy < mean_energy * 0.9:
            label = "intro"
        elif is_near_end and section_energy < mean_energy * 0.9:
            label = "outro"
        elif position > 0.88:
            label = "outro"
        elif section_energy > mean_energy * 1.15 and energy_stability < 0.08:
            label = "chorus"
        elif section_energy < mean_energy * 0.85:
            label = "verse"
        elif energy_stability > 0.1:
            label = "bridge"
        else:
            label = "verse"

        sections.append(StructuralSection(
            start_sec=round(start, 4),
            end_sec=round(end, 4),
            label=label,
            energy_level=round(section_energy, 3),
            bar_count=bar_count,
        ))

    return sections


def score_entry_point(
    time_sec: float,
    bar_times: list[float],
    bar_energies: list[float],
    intro_end: float,
    duration: float,
    bpm: float,
) -> float:
    """Score how good a time position is for a target track to enter.

    Higher scores = better entry points. Factors:
    - Must be after intro
    - Prefer bar boundaries
    - Prefer energy stability (not mid-phrase)
    - Prefer positions with moderate energy

    Returns 0.0 to 1.0.
    """
    if time_sec < intro_end or time_sec >= duration:
        return 0.0

    score = 0.5  # base

    # Bonus for being after intro
    if time_sec > intro_end + 4 * 60.0 / max(bpm, 60):
        score += 0.1

    # Bonus for being on a bar boundary
    bar_duration = 4 * 60.0 / max(bpm, 60)
    for bt in bar_times:
        if abs(time_sec - bt) < bar_duration * 0.1:
            score += 0.2
            break

    # Bonus for energy stability around this point
    if bar_energies and bpm > 0:
        frame = int(time_sec * (len(bar_energies) / max(duration, 1)))
        frame = max(0, min(frame, len(bar_energies) - 1))
        # Look at nearby bars
        window = bar_energies[max(0, frame - 2):min(len(bar_energies), frame + 3)]
        if len(window) > 1:
            stability = 1.0 - min(1.0, float(np.std(window)) * 5)
            score += stability * 0.2

    return min(1.0, max(0.0, score))


def score_exit_point(
    time_sec: float,
    bar_times: list[float],
    bar_energies: list[float],
    outro_start: float,
    duration: float,
    bpm: float,
) -> float:
    """Score how good a time position is for a source track to exit.

    Higher scores = better exit points. Factors:
    - Must be in the outro region or at a phrase boundary
    - Prefer bar boundaries
    - Prefer energy drop-off points (natural ending feel)
    - Don't exit too early (need enough overlap time)

    Returns 0.0 to 1.0.
    """
    if time_sec <= 0 or time_sec >= duration - 2.0:
        return 0.0

    score = 0.3  # base

    # Bonus for being in outro region
    if time_sec >= outro_start:
        score += 0.3
    elif time_sec >= duration * 0.6:
        score += 0.1

    # Bonus for being on a bar boundary
    bar_duration = 4 * 60.0 / max(bpm, 60)
    for bt in bar_times:
        if abs(time_sec - bt) < bar_duration * 0.1:
            score += 0.2
            break

    # Bonus for energy drop at this point (natural exit feel)
    if bar_energies and bpm > 0:
        frame = int(time_sec * (len(bar_energies) / max(duration, 1)))
        frame = max(0, min(frame, len(bar_energies) - 2))
        if frame + 1 < len(bar_energies):
            drop = bar_energies[frame] - bar_energies[frame + 1]
            if drop > 0.05:
                score += min(0.2, drop * 2)

    # Penalty for being too early (need overlap time), but not if already in outro
    min_exit_time = duration * 0.3
    if time_sec < min_exit_time and time_sec < outro_start:
        score *= 0.5

    return min(1.0, max(0.0, score))


def compute_transition_length_bars(
    source_score: float,
    target_score: float,
    bpm: float,
    max_bars: int = 16,
    min_bars: int = 4,
) -> int:
    """Decide transition length in bars based on entry/exit scores.

    High scores on both sides → longer transition (smooth blend).
    Low scores → shorter transition (quick cut).

    Returns number of bars (always even, 4-16).
    """
    avg_score = (source_score + target_score) / 2

    if avg_score > 0.75:
        bars = 16
    elif avg_score > 0.6:
        bars = 12
    elif avg_score > 0.45:
        bars = 8
    else:
        bars = 4

    # Round to even number
    bars = max(min_bars, min(max_bars, bars))
    if bars % 2 != 0:
        bars -= 1

    return bars
