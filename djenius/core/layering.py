"""Conservative selection of explicit vocal-over-instrumental moments.

The normal V10 performance path remains the default.  This module only
describes a layer when the evidence and cached stems satisfy a strict gate;
the renderer is responsible for applying the already validated audio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from pathlib import Path

from djenius.core.models import LayeredAppearance, PerformanceTimeline, SetPlan, TrackProfile
from djenius.core.scorer import score_compatibility


REQUIRED_STEMS = ("vocals", "drums", "bass", "other")


@dataclass
class LayerCompatibilityScore:
    """Inspectable evidence for one vocal/source -> instrumental/target pair."""

    accepted: bool = False
    score: float = 0.0
    tempo_score: float = 0.0
    key_score: float = 0.0
    phrase_score: float = 0.0
    vocal_quality: float = 0.0
    instrumental_quality: float = 0.0
    energy_score: float = 0.0
    stem_ready: bool = False
    rejection_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _stems_ready(track: TrackProfile) -> bool:
    paths = track.analysis.stems or {}
    return all(name in paths and Path(paths[name]).is_file() for name in REQUIRED_STEMS)


def _tempo_score(source: TrackProfile, target: TrackProfile) -> float:
    if source.bpm <= 0 or target.bpm <= 0:
        return 0.5
    delta = abs(source.bpm - target.bpm) / max(source.bpm, target.bpm)
    if delta <= 0.015:
        return 1.0
    if delta <= 0.04:
        return 0.9
    if delta <= 0.08:
        return 0.7
    return max(0.0, 0.35 - delta)


def score_layer_candidate(
    vocal_track: TrackProfile,
    vocal_segment,
    instrumental_track: TrackProfile,
    instrumental_segment,
) -> LayerCompatibilityScore:
    """Score and gate a narrow vocal-over-instrumental opportunity.

    Layering is intentionally stricter than a normal transition.  Unknown
    evidence is not promoted to a mashup: missing stems, weak vocals, a vocal
    target, a large tempo gap, or a clear key clash reject the candidate.
    """
    if vocal_track.id == instrumental_track.id:
        return LayerCompatibilityScore(rejection_reason="layering requires two different source tracks")
    stem_ready = _stems_ready(vocal_track) and _stems_ready(instrumental_track)
    tempo = _tempo_score(vocal_track, instrumental_track)
    compatibility = score_compatibility(vocal_track, instrumental_track)
    key = compatibility.key_score
    phrase = 1.0 if (
        vocal_segment.bar_count >= 4
        and instrumental_segment.bar_count >= 4
        and abs(vocal_segment.bar_count - instrumental_segment.bar_count) <= 4
    ) else 0.5
    vocal_quality = min(1.0, max(0.0, float(vocal_segment.vocal_density) * 1.4))
    instrumental_quality = min(1.0, max(0.0, 1.0 - float(instrumental_segment.vocal_density)))
    energy = max(0.0, 1.0 - abs(float(vocal_segment.energy) - float(instrumental_segment.energy)) * 1.5)
    score = (
        0.24 * tempo
        + 0.24 * key
        + 0.18 * phrase
        + 0.14 * vocal_quality
        + 0.12 * instrumental_quality
        + 0.08 * energy
    )
    reasons = []
    if not stem_ready:
        reasons.append("complete vocal and backing stem caches are required")
    if vocal_quality < 0.30:
        reasons.append("source segment has insufficient vocal material")
    if instrumental_quality < 0.65:
        reasons.append("target segment contains too much vocal material")
    # A small, explicitly declared vocal stretch is safe for this primitive;
    # wider gaps remain rejected rather than hiding a bad mashup behind DSP.
    if tempo < 0.20:
        reasons.append("tempo mismatch is too large for conservative layering")
    if key < 0.75:
        reasons.append("harmonic compatibility is below the layering gate")
    accepted = not reasons and score >= 0.72
    return LayerCompatibilityScore(
        accepted=accepted,
        score=round(score, 4),
        tempo_score=round(tempo, 4),
        key_score=round(key, 4),
        phrase_score=round(phrase, 4),
        vocal_quality=round(vocal_quality, 4),
        instrumental_quality=round(instrumental_quality, 4),
        energy_score=round(energy, 4),
        stem_ready=stem_ready,
        rejection_reason="; ".join(reasons),
    )


def _layer_duration(vocal_segment, instrumental_segment, target_bpm: float) -> tuple[float, int]:
    bpm = target_bpm if target_bpm > 0 else 120.0
    bars = 8 if min(vocal_segment.bar_count, instrumental_segment.bar_count) >= 8 else 4
    duration = bars * 4.0 * 60.0 / bpm
    return min(duration, vocal_segment.duration_sec, instrumental_segment.duration_sec), bars


def prepare_layered_events(
    plan: SetPlan,
    *,
    max_events: int | None = None,
) -> tuple[list[LayeredAppearance], list[dict]]:
    """Attach safe layer opportunities to an already planned timeline.

    The timeline path and accepted transition recipes are not rebuilt.  A
    layer is an occasional replacement of the target body with explicit
    source vocals plus target instrumentation.  If no adjacent pair passes,
    the result is an empty event list and V10 rendering proceeds unchanged.
    """
    timeline = plan.performance_timeline
    intent = plan.intent_used
    if timeline is None or intent is None or intent.layering_preference == "off":
        return [], []
    if timeline.performance_style not in {"experimental", "club", "mashup"}:
        return [], []
    tracks = {item.id: item for item in plan.tracks}
    events: list[LayeredAppearance] = []
    audits: list[dict] = []
    limit = max_events if max_events is not None else (2 if timeline.target_duration_sec >= 300 else 1)
    for index, transition in enumerate(timeline.transitions):
        if len(events) >= limit:
            break
        source_app = timeline.appearances[index]
        target_app = timeline.appearances[index + 1]
        source = tracks.get(source_app.segment.track_id)
        target = tracks.get(target_app.segment.track_id)
        if source is None or target is None:
            continue
        quality = score_layer_candidate(source, source_app.segment, target, target_app.segment)
        audits.append({
            "source_track_id": source.id,
            "target_track_id": target.id,
            "source_segment_id": source_app.segment.id,
            "target_segment_id": target_app.segment.id,
            "quality": quality.to_dict(),
        })
        if not quality.accepted:
            continue
        duration, bars = _layer_duration(source_app.segment, target_app.segment, target.bpm)
        if duration < 4.0:
            continue
        target_start = target_app.segment.source_start_sec + (transition.target_consumed_duration_sec or transition.overlap_duration_sec)
        target_end = target_start + duration
        if target_end > target_app.segment.source_end_sec + 0.01:
            continue
        source_bpm = source.bpm if source.bpm > 0 else target.bpm
        source_phrase_duration = bars * 4.0 * 60.0 / max(source_bpm, 60.0)
        vocal_end = source_app.segment.source_end_sec
        vocal_start = vocal_end - source_phrase_duration
        if vocal_start < source_app.segment.source_start_sec - 0.01:
            continue
        event = LayeredAppearance(
            id=f"layer-{source_app.id}-{target_app.id}",
            vocal_track_id=source.id,
            instrumental_track_id=target.id,
            vocal_source_start_sec=round(vocal_start, 4),
            vocal_source_end_sec=round(vocal_end, 4),
            instrumental_source_start_sec=round(target_start, 4),
            instrumental_source_end_sec=round(target_end, 4),
            output_start_sec=round(target_app.output_start_sec + transition.overlap_duration_sec, 4),
            output_end_sec=round(target_app.output_start_sec + transition.overlap_duration_sec + duration, 4),
            target_appearance_id=target_app.id,
            bar_count=bars,
            bpm=round(target.bpm, 3),
            key_relationship="compatible Camelot/key",
            # pyrubberband's rate is input/output duration.  A value close
            # to one preserves pitch while fitting the vocal phrase to the
            # target groove.
            time_stretch_ratio=round(source_phrase_duration / max(duration, 0.001), 5),
            confidence=quality.score,
            reason=(
                "High-confidence vocal phrase over target drums, bass, and other; "
                f"tempo {quality.tempo_score:.2f}, key {quality.key_score:.2f}, "
                f"phrase {quality.phrase_score:.2f}."
            ),
        )
        events.append(event)
    # A creative vocal callback does not have to be the immediately outgoing
    # track.  When no adjacent handoff is safe, look back through the already
    # heard appearances for a strong, explicit two-track layer.  The backing
    # still belongs to the current target appearance, so its output/source
    # mapping remains local and auditable.
    if not events:
        candidates: list[tuple[float, object, object, object, object, object]] = []
        for source_index, source_app in enumerate(timeline.appearances[:-1]):
            for target_index in range(source_index + 1, len(timeline.appearances)):
                target_app = timeline.appearances[target_index]
                source = tracks.get(source_app.segment.track_id)
                target = tracks.get(target_app.segment.track_id)
                if source is None or target is None or source.id == target.id:
                    continue
                quality = score_layer_candidate(source, source_app.segment, target, target_app.segment)
                audits.append({
                    "source_track_id": source.id,
                    "target_track_id": target.id,
                    "source_segment_id": source_app.segment.id,
                    "target_segment_id": target_app.segment.id,
                    "quality": quality.to_dict(),
                    "callback": True,
                })
                if quality.accepted:
                    candidates.append((quality.score, source_app, target_app, source, target, quality))
        candidates.sort(key=lambda item: item[0], reverse=True)
        for _score, source_app, target_app, source, target, quality in candidates[:limit]:
            duration, bars = _layer_duration(source_app.segment, target_app.segment, target.bpm)
            source_bpm = source.bpm if source.bpm > 0 else target.bpm
            source_phrase_duration = bars * 4.0 * 60.0 / max(source_bpm, 60.0)
            target_transition = timeline.transitions[timeline.appearances.index(target_app) - 1]
            target_start = target_app.segment.source_start_sec + (
                target_transition.target_consumed_duration_sec or target_transition.overlap_duration_sec
            )
            target_end = target_start + duration
            if duration < 4.0 or target_end > target_app.segment.source_end_sec + 0.01:
                continue
            vocal_end = source_app.segment.source_end_sec
            vocal_start = vocal_end - source_phrase_duration
            if vocal_start < source_app.segment.source_start_sec - 0.01:
                continue
            events.append(LayeredAppearance(
                id=f"layer-callback-{source_app.id}-{target_app.id}",
                vocal_track_id=source.id,
                instrumental_track_id=target.id,
                vocal_source_start_sec=round(vocal_start, 4),
                vocal_source_end_sec=round(vocal_end, 4),
                instrumental_source_start_sec=round(target_start, 4),
                instrumental_source_end_sec=round(target_end, 4),
                output_start_sec=round(target_app.output_start_sec + target_transition.overlap_duration_sec, 4),
                output_end_sec=round(target_app.output_start_sec + target_transition.overlap_duration_sec + duration, 4),
                target_appearance_id=target_app.id,
                bar_count=bars,
                bpm=round(target.bpm, 3),
                key_relationship="compatible Camelot/key",
                time_stretch_ratio=round(source_phrase_duration / max(duration, 0.001), 5),
                confidence=quality.score,
                reason=(
                    "Intentional vocal callback over a later target instrumental; "
                    f"tempo {quality.tempo_score:.2f}, key {quality.key_score:.2f}, phrase {quality.phrase_score:.2f}."
                ),
            ))
    timeline.layered_events = [item.to_dict() for item in events]
    return events, audits


def layer_candidate_track_ids(plan: SetPlan, limit: int = 8) -> list[str]:
    """Return bounded track IDs worth preparing for an optional layer."""
    timeline = plan.performance_timeline
    if timeline is None:
        return []
    ids: list[str] = []
    for appearance in timeline.appearances:
        track_id = appearance.segment.track_id
        if track_id not in ids:
            ids.append(track_id)
        if len(ids) >= limit:
            break
    return ids
