"""V9 segment-performance planning.

This module is intentionally separate from the accepted classic planner.  It
chooses phrase-sized source regions and composes an explicit timeline; the
existing technical transition scorer and renderer remain the compatibility
path for classic plans.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from typing import Iterable

from djenius.core.models import (
    PerformanceAppearance,
    PerformanceSegment,
    PerformanceTimeline,
    PerformanceTransition,
    TrackProfile,
    TransitionType,
)
from djenius.core.intent import SetIntent
from djenius.core.intent_scoring import TrackIntentScore, score_track_intent
from djenius.core.scorer import score_compatibility


SECTION_NAMES = {
    "intro", "verse", "pre_chorus", "pre-chorus", "chorus", "hook",
    "breakdown", "build", "drop", "instrumental", "outro", "bridge",
}


def _clean_section(value: str) -> str:
    value = str(value or "unknown").strip().lower().replace(" ", "_")
    return value if value in SECTION_NAMES else "unknown"


def _mean_curve(curve: list[float], start: float, end: float) -> float:
    if not curve:
        return 0.0
    left = max(0, int(math.floor(start)))
    right = min(len(curve), max(left + 1, int(math.ceil(end))))
    values = curve[left:right]
    return float(sum(values) / len(values)) if values else 0.0


def _vocal_density(track: TrackProfile, start: float, end: float) -> float:
    length = max(end - start, 0.001)
    covered = sum(max(0.0, min(end, right) - max(start, left)) for left, right in track.analysis.vocal_regions)
    return max(0.0, min(1.0, covered / length))


def _section_at(track: TrackProfile, point: float) -> str:
    for start, end, name in track.analysis.structural_sections:
        if float(start) <= point <= float(end):
            return _clean_section(name)
    return "unknown"


def _boundary_grid(track: TrackProfile) -> list[float]:
    duration = max(0.0, float(track.duration_sec))
    values = {0.0, round(duration, 4)}
    values.update(float(value) for value in track.analysis.bar_times)
    values.update(float(value) for value in track.analysis.phrase_boundaries)
    values.update(float(value) for value in track.analysis.possible_entry_points)
    values.update(float(value) for value in track.analysis.possible_exit_points)
    return sorted(round(value, 4) for value in values if 0.0 <= value <= duration)


def extract_performance_segments(
    track: TrackProfile,
    *,
    min_bars: int = 4,
    max_candidates: int = 48,
) -> list[PerformanceSegment]:
    """Extract bounded phrase/bar-aligned candidate regions.

    Bar indexes are preferred when available.  Phrase boundaries and a
    conservative BPM grid provide a fallback for older or incomplete caches.
    Candidate generation is capped per track to keep short-form planning
    practical for ordinary local libraries.
    """
    duration = max(0.0, float(track.duration_sec))
    if duration <= 0.0:
        return []
    bpm = float(track.bpm) if track.bpm > 0 else 120.0
    bar_seconds = 4.0 * 60.0 / max(bpm, 60.0)
    bars = [float(value) for value in track.analysis.bar_times if 0.0 <= value < duration]
    starts_ends: set[tuple[float, float, int]] = set()
    if len(bars) >= min_bars + 1:
        for index in range(len(bars)):
            for bar_count in (4, 8, 16, 32):
                end_index = index + bar_count
                if end_index < len(bars):
                    start, end = bars[index], bars[end_index]
                    if end - start >= min_bars * bar_seconds * 0.65:
                        starts_ends.add((round(start, 4), round(end, 4), bar_count))
    boundaries = _boundary_grid(track)
    if not starts_ends and len(boundaries) >= 2:
        # Pair actual phrase/bar boundaries.  This remains musical even when
        # the analyzer did not return a complete bar sequence.
        for index, start in enumerate(boundaries[:-1]):
            for end in boundaries[index + 1:index + 5]:
                if end - start >= min_bars * bar_seconds * 0.65:
                    count = max(min_bars, int(round((end - start) / bar_seconds)))
                    starts_ends.add((start, end, count))
    if not starts_ends:
        # Last-resort grid is still beat/bar based, never an arbitrary slice.
        step = max(min_bars * bar_seconds, 4.0)
        for start in [0.0, step, 2 * step, 3 * step]:
            if start >= duration:
                continue
            end = min(duration, start + step * 2)
            if end - start >= min(2 * bar_seconds, duration * 0.15):
                starts_ends.add((round(start, 4), round(end, 4), max(min_bars, 2 * min_bars)))

    candidates: list[PerformanceSegment] = []
    for start, end, bar_count in starts_ends:
        if end <= start or end > duration + 0.01:
            continue
        section = _section_at(track, (start + end) / 2.0)
        energy = _mean_curve(track.analysis.energy_curve, start, end)
        vocal = _vocal_density(track, start, end)
        # Stable, complete phrase candidates are preferred.  A section label
        # is descriptive only; unknown is valid when structure is uncertain.
        quality = 0.45 + min(0.25, bar_count / 64.0) + (0.15 if section != "unknown" else 0.0)
        if start in boundaries:
            quality += 0.08
        if end in boundaries:
            quality += 0.08
        quality -= 0.08 if end - start < min_bars * bar_seconds else 0.0
        segment_id = hashlib.sha1(f"{track.id}:{start:.4f}:{end:.4f}".encode()).hexdigest()[:16]
        candidates.append(PerformanceSegment(
            id=segment_id,
            track_id=track.id,
            source_start_sec=round(start, 4),
            source_end_sec=round(end, 4),
            section_type=section,
            phrase_start=round(start, 4),
            phrase_end=round(end, 4),
            bar_count=int(bar_count),
            energy=round(energy, 4),
            vocal_density=round(vocal, 4),
            bass_activity=round(_mean_curve(track.analysis.low_energy_curve, start, end), 4),
            semantic_role=section,
            confidence=round(min(1.0, track.analysis.analysis_confidence), 3),
            quality_score=round(max(0.0, min(1.0, quality)), 4),
        ))
    candidates.sort(key=lambda item: (item.quality_score, item.duration_sec), reverse=True)
    # Keep role diversity where the analyzer supplied roles, then fill by
    # quality.  This prevents candidate explosion without losing hooks,
    # breakdowns, or intros.
    chosen: list[PerformanceSegment] = []
    for role in sorted({item.section_type for item in candidates}):
        role_items = [candidate for candidate in candidates if candidate.section_type == role]
        chosen.extend(role_items[:4])
    # Preserve several durations.  Keeping only the globally highest quality
    # windows would fill the cache with 32-bar regions and make quick mixes
    # behave like long-form playback.
    for bar_count in (4, 8, 16, 32):
        duration_items = [candidate for candidate in candidates if candidate.bar_count == bar_count]
        for item in duration_items[:max(2, max_candidates // 8)]:
            if item not in chosen:
                chosen.append(item)
    for item in candidates:
        if item not in chosen:
            chosen.append(item)
        if len(chosen) >= max_candidates:
            break
    return chosen[:max_candidates]


def _target_energy(intent: SetIntent | None, position: int, count: int) -> float:
    if not intent:
        return 0.5
    name = intent.effective_energy_profile().value
    x = position / max(count - 1, 1)
    if name in {"slow_build", "warmup_to_peak"}:
        return 0.25 + 0.55 * x
    if name == "cooldown":
        return 0.75 - 0.45 * x
    if name in {"peak_early", "peak_late"}:
        return 0.65 if (name == "peak_early" and x < 0.55) or (name == "peak_late" and x > 0.45) else 0.45
    return 0.5


def _appearance_count(target: float, style: str, track_count: int) -> int:
    if style == "quick_mix":
        return max(4, min(10, int(round(target / 30.0))))
    if style == "club":
        return max(3, min(8, int(round(target / 48.0))))
    if style == "experimental":
        return max(4, min(10, int(round(target / 28.0))))
    return max(3, min(max(track_count, 3), int(round(target / 55.0))))


def plan_performance_timeline(
    tracks: list[TrackProfile],
    target_duration_sec: float,
    intent: SetIntent | None = None,
    *,
    seed: int | None = None,
    intent_scores: dict[str, TrackIntentScore] | None = None,
    performance_style: str = "quick_mix",
) -> tuple[PerformanceTimeline, dict[str, TrackIntentScore]]:
    """Create an intent-aware, deterministic segment performance timeline."""
    if not tracks:
        raise ValueError("No tracks are available for segment performance")
    rng = random.Random(seed if seed is not None else 0)
    scores = intent_scores or {
        track.id: score_track_intent(track, intent) if intent else TrackIntentScore(track.id, track.title, overall_intent_score=0.5, status="strong", evidence_reliability=1.0)
        for track in tracks
    }
    segments = {track.id: extract_performance_segments(track) for track in tracks}
    available = [track for track in tracks if segments.get(track.id)]
    if not available:
        raise ValueError("No phrase-aligned performance segments were found")
    count = _appearance_count(target_duration_sec, performance_style, len(available))
    if performance_style == "quick_mix":
        short_durations = sorted(
            segment.duration_sec
            for track in available
            for segment in segments[track.id]
            if 12.0 <= segment.duration_sec <= 60.0
        )
        if short_durations:
            median = short_durations[len(short_durations) // 2]
            count = max(4, min(10, int(round(target_duration_sec / max(median - 0.55, 15.0)))))
    target_each = target_duration_sec / max(count - 0.045 * (count - 1), 1.0)
    used_regions: dict[str, list[tuple[float, float]]] = defaultdict(list)
    seen_counts: dict[str, int] = defaultdict(int)
    appearances: list[PerformanceAppearance] = []
    last_track_id = ""

    for position in range(count):
        desired_energy = _target_energy(intent, position, count)
        ranked_tracks = sorted(
            available,
            key=lambda track: (
                scores[track.id].status_rank,
                scores[track.id].overall_intent_score,
                -seen_counts[track.id],
                -abs(track.mean_energy - desired_energy),
                track.id,
            ),
            reverse=True,
        )
        # Controlled seed variation changes ties/alternative paths, but never
        # turns the plan into a random shuffle.
        if len(ranked_tracks) > 1:
            offset = rng.randrange(min(2, len(ranked_tracks))) if position else 0
            ranked_tracks = ranked_tracks[offset:] + ranked_tracks[:offset]
        selected_track = next((track for track in ranked_tracks if track.id != last_track_id), ranked_tracks[0])
        candidates = segments[selected_track.id]
        usable = [
            segment for segment in candidates
            if not any(max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5 for left, right in used_regions[selected_track.id])
        ]
        if not usable:
            # A reprise is allowed only through a source region that is
            # genuinely disjoint.  A shorter valid performance is safer than
            # repeating or substantially overlapping an old slice.
            continue
        if not usable:
            continue
        if performance_style == "quick_mix":
            bounded = [
                segment for segment in usable
                if target_each * 0.35 <= segment.duration_sec <= min(60.0, target_each * 1.6)
                and not any(max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5 for left, right in used_regions[selected_track.id])
            ]
            if not bounded:
                bounded = [
                    segment for segment in usable
                    if segment.duration_sec <= 60.0
                    and not any(max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5 for left, right in used_regions[selected_track.id])
                ]
            if bounded:
                usable = bounded
            else:
                continue
        segment = max(
            usable,
            key=lambda item: (
                0.48 * scores[selected_track.id].overall_intent_score
                + 0.22 * item.quality_score
                + 0.18 * (1.0 - min(1.0, abs(item.duration_sec - target_each) / max(target_each, 1.0)))
                + 0.12 * (1.0 - min(1.0, abs(item.energy - desired_energy))),
                item.quality_score,
            ),
        )
        repeated = bool(used_regions[selected_track.id])
        appearances.append(PerformanceAppearance(
            id=f"appearance-{position + 1}-{segment.id}",
            segment=segment,
            reprise=repeated,
            reuse_reason="intentional reprise using a different source region" if repeated else "",
            intent_score=round(scores[selected_track.id].overall_intent_score, 4),
            intent_status=scores[selected_track.id].status,
        ))
        used_regions[selected_track.id].append((segment.source_start_sec, segment.source_end_sec))
        seen_counts[selected_track.id] += 1
        last_track_id = selected_track.id

    # If phrase lengths made the first pass materially short, add one more
    # suitable appearance instead of padding a quick mix with silence or
    # silently stretching a source region.  This keeps target duration a
    # useful target while preserving musical boundaries.
    estimated_duration = sum(item.segment.duration_sec for item in appearances)
    estimated_duration -= 0.55 * max(0, len(appearances) - 1)
    if performance_style == "quick_mix" and estimated_duration < target_duration_sec * 0.9 and len(appearances) < 10:
        additions = [
            (track, segment) for track in available
            for segment in segments[track.id]
            if track.id != last_track_id and not any(
                max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5
                for left, right in used_regions[track.id]
            )
        ]
        if additions:
            track, segment = min(
                additions,
                key=lambda item: abs(item[1].duration_sec - max(12.0, target_duration_sec - estimated_duration)),
            )
            repeated = bool(used_regions[track.id])
            appearances.append(PerformanceAppearance(
                id=f"appearance-{len(appearances) + 1}-{segment.id}",
                segment=segment,
                reprise=repeated,
                reuse_reason="intentional reprise using a different source region" if repeated else "",
                intent_score=round(scores[track.id].overall_intent_score, 4),
                intent_status=scores[track.id].status,
            ))
            used_regions[track.id].append((segment.source_start_sec, segment.source_end_sec))

    if len(appearances) < 2:
        raise ValueError("The library does not contain two distinct safe performance appearances")

    overlap = 0.55 if performance_style in {"quick_mix", "experimental"} else 1.25
    current_output = 0.0
    transitions: list[PerformanceTransition] = []
    for index, appearance in enumerate(appearances):
        if index == 0:
            appearance.output_start_sec = 0.0
        else:
            previous = appearances[index - 1]
            actual_overlap = min(overlap, previous.duration_sec * 0.2, appearance.segment.duration_sec * 0.2)
            previous_track = next(track for track in tracks if track.id == previous.segment.track_id)
            current_track = next(track for track in tracks if track.id == appearance.segment.track_id)
            technical = score_compatibility(previous_track, current_track)
            appearance.output_start_sec = max(0.0, previous.output_end_sec - actual_overlap)
            transitions.append(PerformanceTransition(
                position=index,
                source_appearance_id=previous.id,
                target_appearance_id=appearance.id,
                transition_type=(TransitionType.PHRASE_CUT if performance_style in {"quick_mix", "experimental"} else TransitionType.CROSSFADE),
                overlap_duration_sec=round(actual_overlap, 4),
                source_start_sec=round(previous.segment.source_end_sec - actual_overlap, 4),
                source_end_sec=round(previous.segment.source_end_sec, 4),
                target_start_sec=round(appearance.segment.source_start_sec, 4),
                target_end_sec=round(appearance.segment.source_start_sec + actual_overlap, 4),
                confidence=round(min(previous.segment.confidence, appearance.segment.confidence), 3),
                technical_score=round(technical.overall_score, 3),
                explanation=f"Phrase-aligned handoff; technical compatibility {technical.overall_score:.2f}.",
            ))
        appearance.output_end_sec = round(appearance.output_start_sec + appearance.segment.duration_sec, 4)
        current_output = appearance.output_end_sec
    timeline = PerformanceTimeline(
        appearances=appearances,
        transitions=transitions,
        total_duration_sec=round(current_output, 3),
        target_duration_sec=round(target_duration_sec, 3),
        performance_style=performance_style,
    )
    validate_performance_timeline(timeline, {track.id: track.duration_sec for track in tracks})
    return timeline, scores


def validate_performance_timeline(
    timeline: PerformanceTimeline,
    track_durations: dict[str, float],
    *,
    source_overlap_tolerance_sec: float = 0.5,
) -> list[str]:
    """Return violations for a segment timeline; raise only at call sites."""
    violations: list[str] = []
    by_id = {item.id: item for item in timeline.appearances}
    if len(timeline.transitions) != max(0, len(timeline.appearances) - 1):
        violations.append("transition count does not match appearance count")
    for index, appearance in enumerate(timeline.appearances):
        segment = appearance.segment
        duration = track_durations.get(segment.track_id)
        if duration is None:
            violations.append(f"appearance {appearance.id} references unknown track")
        elif segment.source_start_sec < -0.001 or segment.source_end_sec > duration + 0.001:
            violations.append(f"appearance {appearance.id} exceeds source bounds")
        if segment.source_end_sec <= segment.source_start_sec:
            violations.append(f"appearance {appearance.id} has no source duration")
        if appearance.output_end_sec <= appearance.output_start_sec:
            violations.append(f"appearance {appearance.id} has no output duration")
        if index and appearance.output_start_sec > timeline.appearances[index - 1].output_end_sec + 0.01:
            violations.append(f"appearance {appearance.id} leaves an output gap")
    regions: dict[str, list[tuple[float, float, bool]]] = defaultdict(list)
    for appearance in timeline.appearances:
        start, end = appearance.segment.source_start_sec, appearance.segment.source_end_sec
        for old_start, old_end, _old_reprise in regions[appearance.segment.track_id]:
            overlap = max(0.0, min(end, old_end) - max(start, old_start))
            exact = abs(start - old_start) <= 0.001 and abs(end - old_end) <= 0.001
            if exact:
                violations.append(f"duplicate source region for {appearance.segment.track_id}")
            elif overlap > source_overlap_tolerance_sec:
                violations.append(f"excessive source overlap for {appearance.segment.track_id}")
            elif not appearance.reprise:
                violations.append(f"repeated track appearance is not declared as reprise: {appearance.id}")
        regions[appearance.segment.track_id].append((start, end, appearance.reprise))
    for index, transition in enumerate(timeline.transitions):
        source = by_id.get(transition.source_appearance_id)
        target = by_id.get(transition.target_appearance_id)
        if source is None or target is None:
            violations.append(f"transition {index + 1} references unknown appearance")
            continue
        if not (source.segment.source_start_sec - 0.01 <= transition.source_start_sec <= transition.source_end_sec <= source.segment.source_end_sec + 0.01):
            violations.append(f"transition {index + 1} source interval is outside segment")
        if not (target.segment.source_start_sec - 0.01 <= transition.target_start_sec <= transition.target_end_sec <= target.segment.source_end_sec + 0.01):
            violations.append(f"transition {index + 1} target interval is outside segment")
    if abs(timeline.total_duration_sec - max((item.output_end_sec for item in timeline.appearances), default=0.0)) > 0.01:
        violations.append("timeline duration does not match appearances")
    return violations


def require_valid_performance_timeline(timeline: PerformanceTimeline, track_durations: dict[str, float]) -> None:
    violations = validate_performance_timeline(timeline, track_durations)
    if violations:
        raise ValueError("Invalid performance timeline: " + "; ".join(violations))


def reorder_performance_timeline(
    timeline: PerformanceTimeline,
    appearance_ids: list[str],
    track_durations: dict[str, float],
) -> PerformanceTimeline:
    """Reorder existing appearances and rebuild only their safe handoffs."""
    by_id = {item.id: item for item in timeline.appearances}
    if len(appearance_ids) < 2 or len(set(appearance_ids)) != len(appearance_ids) or not set(appearance_ids).issubset(by_id):
        raise ValueError("Edited performance order must keep at least two known appearances")
    ordered = [by_id[item] for item in appearance_ids]
    seen_tracks: set[str] = set()
    for index, appearance in enumerate(ordered):
        if appearance.segment.track_id in seen_tracks:
            appearance.reprise = True
            appearance.reuse_reason = "intentional reprise after user reorder"
        seen_tracks.add(appearance.segment.track_id)
        overlap = 0.55 if timeline.performance_style in {"quick_mix", "experimental"} else 1.25
        if index == 0:
            appearance.output_start_sec = 0.0
        else:
            previous = ordered[index - 1]
            overlap = min(overlap, previous.segment.duration_sec * 0.2, appearance.segment.duration_sec * 0.2)
            appearance.output_start_sec = previous.output_end_sec - overlap
        appearance.output_end_sec = appearance.output_start_sec + appearance.segment.duration_sec
    transitions: list[PerformanceTransition] = []
    for index in range(1, len(ordered)):
        previous, current = ordered[index - 1], ordered[index]
        overlap = previous.output_end_sec - current.output_start_sec
        transitions.append(PerformanceTransition(
            position=index,
            source_appearance_id=previous.id,
            target_appearance_id=current.id,
            transition_type=TransitionType.PHRASE_CUT if timeline.performance_style in {"quick_mix", "experimental"} else TransitionType.CROSSFADE,
            overlap_duration_sec=round(overlap, 4),
            source_start_sec=round(previous.segment.source_end_sec - overlap, 4),
            source_end_sec=round(previous.segment.source_end_sec, 4),
            target_start_sec=round(current.segment.source_start_sec, 4),
            target_end_sec=round(current.segment.source_start_sec + overlap, 4),
            confidence=round(min(previous.segment.confidence, current.segment.confidence), 3),
            technical_score=0.0,
            explanation="Revalidated after a user appearance reorder.",
        ))
    updated = PerformanceTimeline(
        appearances=ordered,
        transitions=transitions,
        total_duration_sec=round(ordered[-1].output_end_sec, 3),
        target_duration_sec=timeline.target_duration_sec,
        performance_style=timeline.performance_style,
        validation_notes=list(timeline.validation_notes),
    )
    require_valid_performance_timeline(updated, track_durations)
    return updated


def performance_intent_coverage(appearances: Iterable[PerformanceAppearance], scores: dict[str, TrackIntentScore]) -> dict:
    items = list(appearances)
    def status(item: PerformanceAppearance) -> str:
        return scores.get(item.segment.track_id, TrackIntentScore(item.segment.track_id, item.segment.track_id)).status
    strong = sum(status(item) == "strong" for item in items)
    partial = sum(status(item) == "partial" for item in items)
    unknown = sum(status(item) == "unknown" for item in items)
    contradiction = sum(status(item) == "contradiction" for item in items)
    total = len(items)
    coverage = (strong + 0.6 * partial) / total if total else 0.0
    return {
        "label": "Strong" if total and strong == total else "Good" if coverage >= 0.6 else "Limited",
        "coverage": round(coverage, 3),
        "selected_count": total,
        "strong_match_count": strong,
        "partial_match_count": partial,
        "unknown_count": unknown,
        "contradiction_count": contradiction,
        "appearance_count": total,
    }
