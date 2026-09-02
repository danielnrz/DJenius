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
from dataclasses import dataclass, asdict
from typing import Iterable

from djenius.core.models import (
    PerformanceAppearance,
    PerformanceSegment,
    PerformanceTimeline,
    PerformanceTransition,
    TrackProfile,
    TransitionType,
    EnergyProfile,
)
from djenius.core.intent import SetIntent
from djenius.core.intent_scoring import TrackIntentScore, score_track_intent
from djenius.core.transition_quality import score_transition_candidate


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
        # With only one or two viable tracks, longer appearances are more
        # musical than forcing an A/B/A/B showcase at ten cuts.  Larger
        # candidate pools retain the higher-turnover quick-mix behavior.
        cap = 4 if track_count <= 2 else 10
        return max(4, min(cap, int(round(target / 30.0))))
    if style == "club":
        return max(3, min(8, int(round(target / 48.0))))
    if style == "experimental":
        return max(4, min(10, int(round(target / 28.0))))
    return max(3, min(max(track_count, 3), int(round(target / 55.0))))


_ROLE_FLOW = {
    "intro": {"verse", "hook", "chorus"},
    "verse": {"pre_chorus", "chorus", "hook", "instrumental", "bridge"},
    "pre_chorus": {"chorus", "drop", "hook"},
    "chorus": {"instrumental", "hook", "breakdown", "verse", "outro"},
    "hook": {"hook", "chorus", "instrumental", "drop", "outro"},
    "instrumental": {"hook", "chorus", "build", "drop", "breakdown"},
    "breakdown": {"build", "drop", "chorus", "verse"},
    "build": {"drop", "chorus", "hook"},
    "drop": {"breakdown", "hook", "outro", "chorus"},
    "bridge": {"chorus", "verse", "outro", "instrumental"},
    "outro": {"intro", "verse", "hook", "chorus"},
}


def _role_progression_score(previous: str, current: str) -> float:
    previous = _clean_section(previous)
    current = _clean_section(current)
    if previous == "unknown" or current == "unknown":
        return 0.5
    if current in _ROLE_FLOW.get(previous, set()):
        return 1.0
    if previous == current:
        return 0.35
    return 0.65


def _style_diversity_target(style: str, target_duration_sec: float, track_count: int) -> int:
    if track_count <= 0:
        return 0
    if style == "quick_mix":
        return min(track_count, max(3, min(8, int(round(target_duration_sec / 75.0)))))
    if style == "club":
        return min(track_count, max(3, min(7, int(round(target_duration_sec / 120.0)))))
    if style == "experimental":
        return min(track_count, max(4, min(9, int(round(target_duration_sec / 60.0)))))
    if style == "story":
        return min(track_count, max(2, min(5, int(round(target_duration_sec / 150.0)))))
    return min(track_count, max(2, min(6, int(round(target_duration_sec / 120.0)))))


def _performance_arc(appearances: list[PerformanceAppearance]) -> str:
    if len(appearances) < 2:
        return "steady"
    energies = [item.segment.energy for item in appearances]
    first = sum(energies[:max(1, len(energies) // 3)]) / max(1, len(energies[:max(1, len(energies) // 3)]))
    last = sum(energies[-max(1, len(energies) // 3):]) / max(1, len(energies[-max(1, len(energies) // 3):]))
    peak = max(energies)
    if last - first > 0.12:
        return "build"
    if first - last > 0.12:
        return "release"
    if peak - min(energies) > 0.25:
        return "wave"
    return "steady"


def _diversity_level(unique_count: int, appearance_count: int, requested: float) -> str:
    if appearance_count <= 0:
        return "limited"
    ratio = unique_count / appearance_count
    if requested >= 0.65 and ratio >= 0.6:
        return "high"
    if ratio < 0.4:
        return "limited"
    return "moderate"


@dataclass
class SegmentPairQuality:
    """Pair-specific transition evidence used by the segment path search."""

    transition_type: TransitionType = TransitionType.CROSSFADE
    overlap_duration_sec: float = 0.0
    length_bars: int = 1
    overall_score: float = 0.0
    technical_score: float = 0.0
    phase_score: float = 0.0
    phrase_score: float = 0.0
    loudness_score: float = 0.0
    energy_score: float = 0.0
    bass_score: float = 0.0
    vocal_score: float = 0.0
    source_section: str = "unknown"
    target_section: str = "unknown"
    source_loudness: float = 0.0
    target_loudness: float = 0.0
    source_energy: float = 0.0
    target_energy: float = 0.0
    source_bass: float = 0.0
    target_bass: float = 0.0
    source_vocal: float = 0.0
    target_vocal: float = 0.0
    phase_error_ms: float = 0.0
    requires_stretch: bool = False
    target_consumed_duration_sec: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict:
        result = asdict(self)
        result["transition_type"] = self.transition_type.value
        return result


def _transition_bar_count(style: str) -> int:
    """Choose a musical handoff length; quick means short bodies, not hard cuts."""
    if style in {"quick_mix", "experimental"}:
        return 2
    if style in {"club", "smooth"}:
        return 4
    return 2


def _target_consumed_duration(
    transition_type: TransitionType,
    overlap: float,
    source_bpm: float,
    target_bpm: float,
    *,
    use_time_stretch: bool,
) -> float:
    if (
        transition_type == TransitionType.BEATMATCHED_BLEND
        and use_time_stretch
        and source_bpm > 0
        and target_bpm > 0
        and abs(source_bpm - target_bpm) > 0.5
    ):
        return overlap * source_bpm / target_bpm
    return overlap


def _pair_transition_types(style: str, intent: SetIntent | None) -> list[TransitionType]:
    """Limit segment recipes to safe, existing DSP paths."""
    allowed = intent.allowed_transition_types() if intent else []
    base = [
        TransitionType.BEATMATCHED_BLEND,
        TransitionType.CROSSFADE,
        TransitionType.FILTER_SWEEP,
        TransitionType.BASS_SWAP,
        TransitionType.PHRASE_CUT,
    ]
    if allowed:
        base = [item for item in base if item in allowed]
    # Mashup/echo/loop are deliberately not introduced by the V9.1 segment
    # handoff selector without explicit stem/timeline support.
    return base or [TransitionType.CROSSFADE]


def score_segment_pair(
    source: TrackProfile,
    source_segment: PerformanceSegment,
    target: TrackProfile,
    target_segment: PerformanceSegment,
    *,
    style: str = "quick_mix",
    intent: SetIntent | None = None,
) -> SegmentPairQuality:
    """Score and recipe-select one concrete A -> B segment handoff.

    This deliberately delegates boundary, local energy, loudness, bass and
    vocal calculations to the mature full-context transition evaluator.  The
    segment layer only supplies the actual source/target musical windows.
    """
    bars = _transition_bar_count(style)
    source_bpm = float(source.bpm) if source.bpm > 0 else 120.0
    target_bpm = float(target.bpm) if target.bpm > 0 else 120.0
    bar_seconds = 4.0 * 60.0 / source_bpm
    requested_overlap = bars * bar_seconds
    overlap = min(
        requested_overlap,
        source_segment.duration_sec * 0.30,
        target_segment.duration_sec * 0.30,
    )
    overlap = max(0.5, overlap)
    overlap = round(overlap, 4)

    best: tuple[float, object, dict, TransitionType, bool, float] | None = None
    for transition_type in _pair_transition_types(style, intent):
        # Bass swap has a deliberately short internal bass handoff.  It is
        # appropriate for close rhythmic pairs, but not for a quick mix with
        # a large tempo jump where a longer blend is safer.
        if (
            transition_type == TransitionType.BASS_SWAP
            and style in {"quick_mix", "experimental"}
            and abs(source_bpm - target_bpm) / max(source_bpm, 1.0) > 0.10
        ):
            continue
        use_stretch = (
            transition_type == TransitionType.BEATMATCHED_BLEND
            and source.analysis.bpm_confidence >= 0.55
            and target.analysis.bpm_confidence >= 0.55
            and abs(source_bpm - target_bpm) <= max(18.0, source_bpm * 0.14)
        )
        # A beatmatched recipe without actual beatmatching is misleading and
        # can create a rhythmic smear.  For wider tempo gaps prefer the
        # equal-power/filter paths, which are designed to hide the mismatch.
        if (
            transition_type == TransitionType.BEATMATCHED_BLEND
            and not use_stretch
            and abs(source_bpm - target_bpm) / max(source_bpm, 1.0) > 0.05
        ):
            continue
        target_consumed = _target_consumed_duration(
            transition_type, overlap, source_bpm, target_bpm,
            use_time_stretch=use_stretch,
        )
        if target_segment.source_start_sec + target_consumed > target_segment.source_end_sec + 0.01:
            continue
        quality, _recipe, details = score_transition_candidate(
            source,
            target,
            source_segment.source_end_sec - overlap,
            target_segment.source_start_sec,
            overlap,
            transition_type,
            intent=intent,
            energy_profile=intent.effective_energy_profile() if intent else EnergyProfile.STEADY,
        )
        phase_score = (quality.bar_alignment_score + quality.phrase_alignment_score) / 2.0
        # Phrase cuts are an earned exception, never the quick-mode default.
        phrase_safe = (
            transition_type != TransitionType.PHRASE_CUT
            or (
                quality.overall_score >= 0.78
                and quality.bar_alignment_score >= 0.82
                and quality.phrase_alignment_score >= 0.82
                and quality.vocal_clash_score >= 0.82
                and quality.loudness_continuity_score >= 0.78
                and abs(source_bpm - target_bpm) <= max(3.0, source_bpm * 0.025)
            )
        )
        if not phrase_safe:
            continue
        # The pair score prioritizes the actual transition context while
        # retaining the technical compatibility score as the largest single
        # component.  Intent remains a separate Stage-A concern.
        pair_score = (
            0.38 * quality.overall_score
            + 0.16 * quality.tempo_compatibility_score
            + 0.12 * quality.harmonic_compatibility_score
            + 0.10 * phase_score
            + 0.08 * quality.energy_continuity_score
            + 0.07 * quality.loudness_continuity_score
            + 0.05 * quality.bass_handoff_score
            + 0.04 * quality.vocal_clash_score
        )
        if transition_type == TransitionType.PHRASE_CUT:
            pair_score -= 0.05 if style in {"quick_mix", "experimental"} else 0.0
        if (
            transition_type == TransitionType.BEATMATCHED_BLEND
            and use_stretch
            and abs(source_bpm - target_bpm) / max(source_bpm, 1.0) <= 0.05
        ):
            # When a genuinely close pair can use the mature beatmatched
            # path, prefer it over a plain overlap of two unsynchronised
            # rhythmic regions.
            pair_score += 0.06
        candidate = (
            pair_score,
            quality,
            details,
            transition_type,
            use_stretch,
            target_consumed,
        )
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        # A bounded crossfade remains a valid safety fallback even for sparse
        # or incomplete analysis data.
        transition_type = TransitionType.CROSSFADE
        target_consumed = overlap
        quality, _recipe, details = score_transition_candidate(
            source, target, source_segment.source_end_sec - overlap,
            target_segment.source_start_sec, overlap, transition_type,
            intent=intent,
            energy_profile=intent.effective_energy_profile() if intent else EnergyProfile.STEADY,
        )
        best = (0.20, quality, details, transition_type, False, target_consumed)

    pair_score, quality, details, transition_type, use_stretch, target_consumed = best
    source_loudness = float(details.get("source_context_loudness", 0.0))
    target_loudness = float(details.get("target_landing_loudness", 0.0))
    source_energy = float(details.get("source_relative_energy", source_segment.energy))
    target_energy = float(details.get("target_landing_relative_energy", target_segment.energy))
    phase_error = max(
        abs(float(details.get("source_bar_alignment_error_ms", 1000.0))),
        abs(float(details.get("target_bar_alignment_error_ms", 1000.0))),
    )
    explanation = (
        f"{details.get('source_section', 'unknown')} -> {details.get('target_section', 'unknown')}; "
        f"{transition_type.value}, {max(1, round(overlap / bar_seconds))} bars; "
        f"technical {quality.overall_score:.2f}, phase error {phase_error:.0f}ms, "
        f"loudness {details.get('loudness_delta_db', 0.0):+.1f}dB, "
        f"vocals {details.get('vocal_collision', 0.0):.2f}."
    )
    return SegmentPairQuality(
        transition_type=transition_type,
        overlap_duration_sec=overlap,
        length_bars=max(1, round(overlap / bar_seconds)),
        overall_score=round(max(0.0, min(1.0, pair_score)), 4),
        technical_score=round(float(quality.overall_score), 4),
        phase_score=round((quality.bar_alignment_score + quality.phrase_alignment_score) / 2.0, 4),
        phrase_score=round(quality.phrase_alignment_score, 4),
        loudness_score=round(quality.loudness_continuity_score, 4),
        energy_score=round(quality.energy_continuity_score, 4),
        bass_score=round(quality.bass_handoff_score, 4),
        vocal_score=round(quality.vocal_clash_score, 4),
        source_section=str(details.get("source_section", "unknown")),
        target_section=str(details.get("target_section", "unknown")),
        source_loudness=round(source_loudness, 4),
        target_loudness=round(target_loudness, 4),
        source_energy=round(source_energy, 4),
        target_energy=round(target_energy, 4),
        source_bass=round(float(details.get("source_bass", source_segment.bass_activity)), 4),
        target_bass=round(float(details.get("target_bass", target_segment.bass_activity)), 4),
        source_vocal=round(float(details.get("source_vocal_fraction", source_segment.vocal_density)), 4),
        target_vocal=round(float(details.get("target_vocal_fraction", target_segment.vocal_density)), 4),
        phase_error_ms=round(phase_error, 2),
        requires_stretch=use_stretch,
        target_consumed_duration_sec=round(target_consumed, 4),
        explanation=explanation,
    )


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
        if short_durations and len(available) > 2:
            median = short_durations[len(short_durations) // 2]
            count = max(5, min(10, int(round(target_duration_sec / max(median - 3.0, 15.0)))))
    target_each = target_duration_sec / max(count - 0.15 * (count - 1), 1.0)
    used_regions: dict[str, list[tuple[float, float]]] = defaultdict(list)
    seen_counts: dict[str, int] = defaultdict(int)
    recent_track_ids: list[str] = []
    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    role_counts: dict[str, int] = defaultdict(int)
    unique_target = _style_diversity_target(performance_style, target_duration_sec, len(available))
    desired_variety = float(intent.desired_variety) if intent else 0.35
    appearances: list[PerformanceAppearance] = []
    track_by_id = {track.id: track for track in tracks}

    def usable_for(track: TrackProfile) -> list[PerformanceSegment]:
        result = []
        for segment in segments[track.id]:
            if any(
                max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5
                for left, right in used_regions[track.id]
            ):
                continue
            quick_max = max(60.0, min(90.0, target_each * 1.8))
            if performance_style == "quick_mix" and not (
                8.0 <= segment.duration_sec <= quick_max
                and segment.duration_sec >= target_each * 0.50
            ):
                continue
            result.append(segment)
        return result

    for position in range(count):
        desired_energy = _target_energy(intent, position, count)
        options: list[tuple[float, str, PerformanceSegment, SegmentPairQuality | None]] = []
        for track in available:
            if appearances and track.id == appearances[-1].segment.track_id:
                continue
            for segment in usable_for(track):
                fit_duration = 1.0 - min(1.0, abs(segment.duration_sec - target_each) / max(target_each, 1.0))
                fit_energy = 1.0 - min(1.0, abs(segment.energy - desired_energy))
                score = scores[track.id]
                pair = None
                pair_score = 0.0
                if appearances:
                    previous = appearances[-1].segment
                    pair = score_segment_pair(
                        track_by_id[previous.track_id], previous, track, segment,
                        style=performance_style, intent=intent,
                    )
                    pair_score = pair.overall_score
                is_new_track = track.id not in seen_counts
                recent_count = sum(item == track.id for item in recent_track_ids[-3:])
                repeated_edge = (
                    edge_counts[(appearances[-1].segment.track_id, track.id)]
                    if appearances else 0
                )
                role = _clean_section(segment.section_type)
                role_score = (
                    _role_progression_score(appearances[-1].segment.section_type, role)
                    if appearances else 0.5
                )
                future_role_score = 0.5
                # Small lookahead: prefer a section that leaves at least one
                # plausible role progression for the following appearance.
                if position < count - 1:
                    future_roles = {
                        _clean_section(candidate.section_type)
                        for future_track in available
                        for candidate in segments[future_track.id][:4]
                        if future_track.id != track.id
                    }
                    if future_roles:
                        future_role_score = max(
                            _role_progression_score(role, future_role)
                            for future_role in future_roles
                        )
                novelty_bonus = 0.0
                if is_new_track:
                    coverage_gap = max(0, unique_target - len(seen_counts))
                    novelty_bonus = 0.10 * (0.7 + 0.3 * min(1.0, coverage_gap / max(unique_target, 1)))
                recent_penalty = min(0.16, 0.055 * recent_count)
                edge_penalty = min(0.14, 0.07 * repeated_edge)
                role_penalty = min(0.08, 0.025 * role_counts[role])
                vocal_penalty = 0.0
                if appearances and previous.vocal_density >= 0.78 and segment.vocal_density >= 0.78:
                    vocal_penalty = 0.045
                reprise_penalty = 0.0
                reprise_bonus = 0.0
                if not is_new_track:
                    if intent and intent.reprise_preference == "avoid":
                        reprise_penalty = 0.08
                    elif intent and intent.reprise_preference == "callback" and role in {"hook", "chorus", "drop"}:
                        reprise_bonus = 0.035
                total = (
                    0.42 * score.overall_intent_score
                    + 0.10 * segment.quality_score
                    + 0.15 * fit_duration
                    + 0.08 * fit_energy
                    + 0.25 * pair_score
                    + desired_variety * novelty_bonus
                    + 0.035 * role_score
                    + 0.02 * future_role_score
                    - recent_penalty * (0.6 + desired_variety)
                    - edge_penalty * (0.6 + desired_variety)
                    - role_penalty * desired_variety
                    - vocal_penalty
                    - reprise_penalty
                    + reprise_bonus
                )
                options.append((total, track.id, segment, pair))
        if not options and performance_style == "quick_mix" and target_duration_sec >= 240.0:
            # A small library may exhaust all short phrase windows before a
            # five-minute request is filled.  Relax segment length only after
            # every bounded quick candidate is exhausted, and only for a
            # longer request where preserving the requested duration is more
            # useful than silently stopping at three minutes.
            for track in available:
                if appearances and track.id == appearances[-1].segment.track_id:
                    continue
                for segment in segments[track.id]:
                    if any(
                        max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5
                        for left, right in used_regions[track.id]
                    ) or segment.duration_sec > max(120.0, target_each * 4.0):
                        continue
                    pair = score_segment_pair(
                        track_by_id[appearances[-1].segment.track_id], appearances[-1].segment,
                        track, segment, style=performance_style, intent=intent,
                    ) if appearances else None
                    options.append((
                        0.40 * scores[track.id].overall_intent_score
                        + 0.12 * segment.quality_score
                        + 0.08 * (pair.overall_score if pair else 0.0),
                        track.id, segment, pair,
                    ))
        if not options:
            break
        options.sort(key=lambda item: (
            item[0], item[3].overall_score if item[3] else 0.0,
            item[2].quality_score, item[1], item[2].id,
        ), reverse=True)
        # Controlled diversity is limited to the two best pair-aware paths.
        choice = rng.randrange(min(2, len(options))) if len(options) > 1 else 0
        _total, selected_id, segment, _pair = options[choice]
        repeated = bool(used_regions[selected_id])
        if not repeated:
            performance_reason = "New track for variety and set development."
        elif segment.section_type in {"hook", "chorus", "drop"}:
            performance_reason = "Section callback/reprise chosen for an energy or thematic return."
        else:
            performance_reason = "Reprise chosen from a different source region while preserving the best available handoff."
        if appearances and appearances[-1].segment.vocal_density >= 0.78 and segment.vocal_density < 0.78:
            performance_reason = "Instrumental/low-vocal section chosen to give the vocal arc room to breathe."
        appearances.append(PerformanceAppearance(
            id=f"appearance-{position + 1}-{segment.id}",
            segment=segment,
            reprise=repeated,
            reuse_reason="intentional reprise using a different source region" if repeated else "",
            intent_score=round(scores[selected_id].overall_intent_score, 4),
            intent_status=scores[selected_id].status,
            performance_reason=performance_reason,
        ))
        used_regions[selected_id].append((segment.source_start_sec, segment.source_end_sec))
        seen_counts[selected_id] += 1
        if appearances[-1].reprise and appearances[-1].reuse_reason == "":
            appearances[-1].reuse_reason = performance_reason
        recent_track_ids.append(selected_id)
        role_counts[_clean_section(segment.section_type)] += 1
        if len(appearances) >= 2:
            edge_counts[(appearances[-2].segment.track_id, selected_id)] += 1
        if len(appearances) >= 2:
            estimated = sum(item.segment.duration_sec for item in appearances)
            estimated -= sum(
                score_segment_pair(
                    track_by_id[appearances[index - 1].segment.track_id],
                    appearances[index - 1].segment,
                    track_by_id[item.segment.track_id], item.segment,
                    style=performance_style, intent=intent,
                ).overlap_duration_sec
                for index, item in enumerate(appearances) if index > 0
            )
            if estimated >= target_duration_sec * 0.95:
                break

    # If phrase lengths made the first pass materially short, add one more
    # suitable appearance instead of padding a quick mix with silence or
    # silently stretching a source region.  This keeps target duration a
    # useful target while preserving musical boundaries.
    estimated_duration = sum(item.segment.duration_sec for item in appearances)
    estimated_duration -= sum(
        score_segment_pair(
            track_by_id[appearances[index - 1].segment.track_id],
            appearances[index - 1].segment,
            track_by_id[appearance.segment.track_id],
            appearance.segment,
            style=performance_style,
            intent=intent,
        ).overlap_duration_sec
        for index, appearance in enumerate(appearances) if index > 0
    )
    if performance_style == "quick_mix" and estimated_duration < target_duration_sec * 0.9 and len(appearances) < 10:
        additions = [
            (track, segment) for track in available
            if track.id != (appearances[-1].segment.track_id if appearances else "")
            for segment in usable_for(track)
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
                performance_reason="Additional compatible appearance added to approach the requested duration.",
            ))
            used_regions[track.id].append((segment.source_start_sec, segment.source_end_sec))
            seen_counts[track.id] += 1
            recent_track_ids.append(track.id)
            role_counts[_clean_section(segment.section_type)] += 1
            if len(appearances) >= 2:
                edge_counts[(appearances[-2].segment.track_id, track.id)] += 1

    if len(appearances) < 2:
        raise ValueError("The library does not contain two distinct safe performance appearances")

    current_output = 0.0
    transitions: list[PerformanceTransition] = []
    for index, appearance in enumerate(appearances):
        if index == 0:
            appearance.output_start_sec = 0.0
        else:
            previous = appearances[index - 1]
            previous_track = track_by_id[previous.segment.track_id]
            current_track = track_by_id[appearance.segment.track_id]
            pair = score_segment_pair(
                previous_track, previous.segment, current_track, appearance.segment,
                style=performance_style, intent=intent,
            )
            actual_overlap = round(min(
                pair.overlap_duration_sec,
                previous.segment.duration_sec * 0.30,
                appearance.segment.duration_sec * 0.30,
            ), 4)
            appearance.output_start_sec = max(0.0, previous.output_end_sec - actual_overlap)
            target_consumed = _target_consumed_duration(
                pair.transition_type, actual_overlap, previous_track.bpm,
                current_track.bpm, use_time_stretch=pair.requires_stretch,
            )
            transitions.append(PerformanceTransition(
                position=index,
                source_appearance_id=previous.id,
                target_appearance_id=appearance.id,
                transition_type=pair.transition_type,
                overlap_duration_sec=actual_overlap,
                source_start_sec=round(previous.segment.source_end_sec - actual_overlap, 4),
                source_end_sec=round(previous.segment.source_end_sec, 4),
                target_start_sec=round(appearance.segment.source_start_sec, 4),
                target_end_sec=round(appearance.segment.source_start_sec + target_consumed, 4),
                confidence=round(min(previous.segment.confidence, appearance.segment.confidence), 3),
                technical_score=pair.technical_score,
                explanation=pair.explanation,
                length_bars=pair.length_bars,
                phase_error_ms=pair.phase_error_ms,
                pair_quality=pair.overall_score,
                source_local_energy=pair.source_energy,
                target_local_energy=pair.target_energy,
                source_local_loudness=pair.source_loudness,
                target_local_loudness=pair.target_loudness,
                source_bass_activity=pair.source_bass,
                target_bass_activity=pair.target_bass,
                source_vocal_density=pair.source_vocal,
                target_vocal_density=pair.target_vocal,
                source_section=pair.source_section,
                target_section=pair.target_section,
                requires_stretch=pair.requires_stretch,
                target_consumed_duration_sec=target_consumed,
            ))
        playback_duration = appearance.segment.duration_sec
        if index > 0 and transitions:
            transition = transitions[-1]
            playback_duration -= max(
                0.0,
                transition.target_consumed_duration_sec - transition.overlap_duration_sec,
            )
        appearance.output_end_sec = round(appearance.output_start_sec + playback_duration, 4)
        current_output = appearance.output_end_sec
    reuse_counts = dict(sorted(seen_counts.items()))
    repeated_pairs = sum(max(0, count - 1) for count in edge_counts.values())
    role_diversity = len({_clean_section(item.segment.section_type) for item in appearances})
    timeline = PerformanceTimeline(
        appearances=appearances,
        transitions=transitions,
        total_duration_sec=round(current_output, 3),
        target_duration_sec=round(target_duration_sec, 3),
        performance_style=performance_style,
        reuse_counts=reuse_counts,
        repeated_pair_count=repeated_pairs,
        section_role_diversity=role_diversity,
        performance_arc=_performance_arc(appearances),
        diversity_level=_diversity_level(
            len(reuse_counts), len(appearances), desired_variety,
        ),
        layered_events=[],
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
        # An edited order has no source profiles available at this API seam;
        # use a conservative musical crossfade rather than recreating the V9
        # universal hard phrase-cut behavior.  A fresh regeneration performs
        # full pair-aware recipe selection.
        overlap = 2.0 if timeline.performance_style in {"quick_mix", "experimental"} else 3.0
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
            transition_type=TransitionType.CROSSFADE,
            overlap_duration_sec=round(overlap, 4),
            source_start_sec=round(previous.segment.source_end_sec - overlap, 4),
            source_end_sec=round(previous.segment.source_end_sec, 4),
            target_start_sec=round(current.segment.source_start_sec, 4),
            target_end_sec=round(current.segment.source_start_sec + overlap, 4),
            confidence=round(min(previous.segment.confidence, current.segment.confidence), 3),
            technical_score=0.0,
            explanation="Revalidated after a user appearance reorder.",
            length_bars=1,
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
