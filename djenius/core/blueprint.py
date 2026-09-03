"""V14 whole-performance remix direction.

The blueprint is a small, deterministic creative plan.  It does not render
audio and it does not choose DSP parameters.  Its job is to decide what
musical role the next part of a performance should serve before the existing
V9-V13 timeline planner selects exact executable source intervals.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from djenius.core.models import PerformanceSegment, TrackProfile


MUSICAL_ROLES = (
    "INTRO", "GROOVE", "VOCAL_IDENTITY", "BUILD", "PEAK",
    "BREATHING_ROOM", "RELEASE", "CALLBACK", "OUTRO",
)


@dataclass
class BlueprintAct:
    """One intended musical idea in a whole-performance plan."""

    id: str = ""
    role: str = "GROOVE"
    start_fraction: float = 0.0
    end_fraction: float = 1.0
    state: str = "DEVELOP"
    energy_target: float = 0.5
    vocal_target: float = 0.5
    semantic_target: list[str] = field(default_factory=list)
    section_duration_target_sec: float = 30.0
    transition_role_in: str = "CONTINUE"
    transition_role_out: str = "CONTINUE"
    selected_track_id: str = ""
    selected_segment_id: str = ""
    selected_section: str = "unknown"
    role_score: float = 0.0
    meaning_score: float = 0.0
    sound_score: float = 0.0
    callback_to: str = ""
    callback_reason: str = ""
    stay_on_track: bool = False
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RemixBlueprint:
    """Whole-performance direction, separate from an executable timeline."""

    target_duration_sec: float = 0.0
    style: str = "experimental"
    narrative: str = ""
    acts: list[BlueprintAct] = field(default_factory=list)
    anchor_roles: list[str] = field(default_factory=list)
    callbacks: list[dict[str, str]] = field(default_factory=list)
    peak_count: int = 0
    strong_moment_budget: int = 0
    vocal_density_target: float = 0.5
    appearance_count_target: int = 0
    reasoning_summary: str = ""
    meaning_priority: float = 0.5
    sound_priority: float = 0.5
    vocal_importance: float = 0.5
    callback_preference: str = "balanced"
    director_version: str = "v14-blueprint-1"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["acts"] = [act.to_dict() for act in self.acts]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RemixBlueprint | None":
        if not data:
            return None
        values = dict(data)
        values["acts"] = [
            BlueprintAct(**{key: value for key, value in item.items() if key in BlueprintAct.__dataclass_fields__})
            for item in values.get("acts", [])
        ]
        known = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in values.items() if key in known})


def _meaning_labels(track: TrackProfile) -> set[str]:
    meaning = track.lyrics.meaning if track.lyrics else None
    if not meaning:
        return set()
    return set(meaning.primary_themes + meaning.secondary_themes + meaning.lyrical_moods)


def _sound_labels(track: TrackProfile) -> set[str]:
    semantic = track.semantic
    if not semantic:
        return set()
    return set(semantic.semantic_tags) | set(semantic.mood_scores) | set(semantic.activity_scores)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _role_score(
    role: str,
    track: TrackProfile,
    segment: PerformanceSegment,
    intent: Any,
    target_duration_sec: float = 30.0,
) -> tuple[float, float, float, str]:
    """Return role, meaning, and sound evidence plus an explanation."""
    section = str(segment.section_type or "unknown").lower()
    vocal = float(segment.vocal_density)
    energy = float(segment.energy)
    quality = float(segment.quality_score)
    meaning_labels = _meaning_labels(track)
    sound_labels = _sound_labels(track)
    wanted_meaning = set(getattr(intent, "desired_themes", []) or []) | set(getattr(intent, "desired_lyrical_moods", []) or [])
    wanted_sound = set(getattr(intent, "desired_moods", []) or []) | set(getattr(intent, "desired_activity", []) or [])
    meaning_score = 0.5 if not wanted_meaning else _clamp(len(meaning_labels & wanted_meaning) / max(1, len(wanted_meaning)))
    sound_score = 0.5 if not wanted_sound else _clamp(len(sound_labels & wanted_sound) / max(1, len(wanted_sound)))
    duration_fit = 1.0 - min(1.0, abs(segment.duration_sec - target_duration_sec) / max(target_duration_sec, 1.0))
    score = 0.24 * quality + 0.16 * meaning_score + 0.12 * sound_score + 0.30 * duration_fit
    evidence: list[str] = []
    if role == "VOCAL_IDENTITY":
        score += 0.38 * vocal + (0.12 if section in {"chorus", "hook", "verse"} else 0.0)
        evidence.append("vocal phrase" if vocal >= 0.45 else "available vocal material")
    elif role == "GROOVE":
        score += 0.22 * (1.0 - min(1.0, vocal)) + 0.20 * energy
        evidence.append("stable low-vocal groove")
    elif role == "BUILD":
        score += 0.18 * energy + (0.18 if section in {"build", "pre_chorus", "instrumental"} else 0.0)
        evidence.append("rising or preparatory section")
    elif role == "PEAK":
        score += 0.34 * energy + (0.18 if section in {"drop", "chorus", "hook"} else 0.0) + 0.10 * segment.bass_activity
        evidence.append("high-energy payoff section")
    elif role in {"BREATHING_ROOM", "RELEASE"}:
        score += 0.25 * (1.0 - vocal) + 0.12 * (1.0 - energy) + (0.15 if section in {"instrumental", "breakdown", "outro"} else 0.0)
        evidence.append("lower-vocal breathing room")
    elif role == "INTRO":
        score += 0.18 * (1.0 - vocal) + (0.20 if section in {"intro", "instrumental", "verse"} else 0.0)
        evidence.append("establishing section")
    elif role == "OUTRO":
        score += 0.20 * (1.0 - vocal) + (0.18 if section in {"outro", "instrumental", "breakdown"} else 0.0)
        evidence.append("closing section")
    elif role == "CALLBACK":
        score += 0.25 * vocal + (0.24 if section in {"chorus", "hook", "drop"} else 0.0)
        evidence.append("recognizable hook callback")
    return _clamp(score), _clamp(meaning_score), _clamp(sound_score), ", ".join(evidence)


def _role_template(style: str, duration: float, request: str) -> list[tuple[str, str, float, float]]:
    lower = request.lower()
    wants_callback = style in {"experimental", "story"} or any(token in lower for token in ("callback", "return", "opening vocal", "bring the", "recognizable"))
    meaning_first = any(token in lower for token in ("meaning", "lyrics", "heartbreak", "romantic", "emotional"))
    narrative_arc = any(token in lower for token in ("build", "peak", "release", "gradually", "slowly become")) and wants_callback
    if narrative_arc:
        roles = ["INTRO", "VOCAL_IDENTITY", "BREATHING_ROOM", "BUILD", "PEAK", "RELEASE", "CALLBACK", "OUTRO"]
    elif style == "club":
        roles = ["INTRO", "GROOVE", "BUILD", "PEAK", "GROOVE", "RELEASE", "PEAK", "OUTRO"]
    elif style in {"story", "smooth"} or meaning_first and "remix" not in lower:
        roles = ["INTRO", "VOCAL_IDENTITY", "BREATHING_ROOM", "BUILD", "CALLBACK", "OUTRO"]
    else:
        roles = ["INTRO", "GROOVE", "VOCAL_IDENTITY", "BUILD", "PEAK", "BREATHING_ROOM", "CALLBACK", "OUTRO"]
    # Longer requests need more room for stable musical ideas, but the count
    # is derived from duration and style rather than being a fixed showcase
    # size.  Extra acts are deliberately ordinary groove/release roles.
    if duration >= 360 and style == "club":
        roles.insert(-1, "GROOVE")
        roles.insert(-1, "RELEASE")
    if not wants_callback:
        roles = ["GROOVE" if role == "CALLBACK" else role for role in roles]
    if duration < 210 and len(roles) > 6:
        roles = roles[:6]
    if duration < 150 and len(roles) > 5:
        roles = roles[:5]
    result = []
    for index, role in enumerate(roles):
        start = index / len(roles)
        end = (index + 1) / len(roles)
        state = {
            "INTRO": "INTRO", "PEAK": "PEAK", "BUILD": "BUILD",
            "RELEASE": "RELEASE", "CALLBACK": "CALLBACK", "OUTRO": "OUTRO",
        }.get(role, "ESTABLISH" if index == 1 else "DEVELOP")
        result.append((role, state, start, end))
    return result


def _target_energy(role: str) -> float:
    return {
        "INTRO": 0.35, "GROOVE": 0.50, "VOCAL_IDENTITY": 0.58,
        "BUILD": 0.70, "PEAK": 0.86, "BREATHING_ROOM": 0.48,
        "RELEASE": 0.42, "CALLBACK": 0.68, "OUTRO": 0.36,
    }.get(role, 0.5)


def build_remix_blueprint(
    tracks: list[TrackProfile],
    target_duration_sec: float,
    intent: Any = None,
    *,
    performance_style: str = "experimental",
    segments_by_track: dict[str, list[PerformanceSegment]] | None = None,
) -> RemixBlueprint:
    """Build a compact role-first plan from existing analysis evidence."""
    request = str(getattr(intent, "raw_text", "") or "")
    template = _role_template(performance_style, target_duration_sec, request)
    if not template:
        return RemixBlueprint(target_duration_sec=target_duration_sec, style=performance_style)
    if segments_by_track is None:
        from djenius.core.performance import extract_performance_segments
        segments_by_track = {track.id: extract_performance_segments(track) for track in tracks}
    all_candidates = [(track, segment) for track in tracks for segment in segments_by_track.get(track.id, [])]
    used: dict[str, list[tuple[float, float]]] = {track.id: [] for track in tracks}
    acts: list[BlueprintAct] = []
    anchor_track = ""
    anchor_segment = ""
    callbacks: list[dict[str, str]] = []
    for index, (role, state, start, end) in enumerate(template):
        choices: list[tuple[float, float, float, TrackProfile, PerformanceSegment, str]] = []
        for track, segment in all_candidates:
            overlap = any(max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5 for left, right in used[track.id])
            if overlap:
                continue
            # A transition consumes part of adjacent appearances.  Long club
            # performances also need enough source material for sustained
            # grooves; other styles should not be inflated just to chase the
            # duration target.
            duration_factor = 1.25 if performance_style == "club" and target_duration_sec >= 360.0 else 1.0
            target_act_duration = (target_duration_sec / max(
                len(template) - 0.18 * (len(template) - 1), 1.0,
            )) * duration_factor
            role_score, meaning_score, sound_score, reason = _role_score(
                role, track, segment, intent, target_act_duration,
            )
            if role == "CALLBACK" and anchor_track and track.id == anchor_track:
                role_score += 0.30
            if role == "CALLBACK" and anchor_track and track.id != anchor_track:
                role_score -= 0.15
            if role == "VOCAL_IDENTITY" and not anchor_track and segment.vocal_density >= 0.45:
                role_score += 0.12
            # Keep the role's source material varied without making novelty
            # more important than meaning or a usable musical section.
            if track.id not in used or not used[track.id]:
                role_score += 0.04
            choices.append((role_score, meaning_score, sound_score, track, segment, reason))
        if not choices:
            continue
        choices.sort(key=lambda item: (item[0], item[1], item[2], item[4].quality_score, item[3].id, item[4].id), reverse=True)
        _score, meaning_score, sound_score, track, segment, reason = choices[0]
        used[track.id].append((segment.source_start_sec, segment.source_end_sec))
        if role == "VOCAL_IDENTITY" and not anchor_track:
            anchor_track, anchor_segment = track.id, segment.id
        callback_to = anchor_segment if role == "CALLBACK" and anchor_segment else ""
        callback_reason = "return to the opening vocal identity" if callback_to else ""
        if callback_to:
            callbacks.append({"act_id": f"act-{index + 1}", "callback_to": callback_to, "reason": callback_reason})
        act = BlueprintAct(
            id=f"act-{index + 1}", role=role, start_fraction=round(start, 4), end_fraction=round(end, 4),
            state=state, energy_target=_target_energy(role), vocal_target=0.78 if role == "VOCAL_IDENTITY" else 0.20 if role in {"GROOVE", "BREATHING_ROOM", "RELEASE"} else 0.45,
            semantic_target=list(getattr(intent, "desired_themes", []) or []) + list(getattr(intent, "desired_lyrical_moods", []) or []),
            section_duration_target_sec=round(max(12.0, target_duration_sec * (end - start)), 2),
            transition_role_in="REVEAL" if role in {"PEAK", "VOCAL_IDENTITY"} else "BUILD" if role == "BUILD" else "CALLBACK" if role == "CALLBACK" else "CONTINUE",
            transition_role_out="BUILD" if role == "BUILD" else "RELEASE" if role == "PEAK" else "CALLBACK" if role == "CALLBACK" else "CONTINUE",
            selected_track_id=track.id, selected_segment_id=segment.id, selected_section=segment.section_type,
            role_score=round(_score, 4), meaning_score=round(meaning_score, 4), sound_score=round(sound_score, 4),
            callback_to=callback_to, callback_reason=callback_reason,
            stay_on_track=bool(acts and acts[-1].selected_track_id == track.id),
            reasoning=reason,
        )
        acts.append(act)
    peak_count = sum(act.role == "PEAK" for act in acts)
    strong_budget = max(1, min(3, peak_count + (1 if performance_style in {"club", "experimental"} else 0)))
    narrative = " -> ".join(act.role for act in acts)
    meaning_requested = bool(
        getattr(intent, "desired_themes", []) or getattr(intent, "desired_lyrical_moods", [])
        or any(token in request.lower() for token in ("lyrics", "meaning", "heartbreak", "romantic", "emotional"))
    )
    sound_requested = bool(
        getattr(intent, "desired_moods", []) or getattr(intent, "desired_activity", [])
        or any(token in request.lower() for token in ("energetic", "dance", "club", "groove"))
    )
    instrumental_requested = "instrumental" in request.lower() or "lyrics do not matter" in request.lower()
    callback_preference = "callback" if callbacks else "balanced"
    return RemixBlueprint(
        target_duration_sec=round(target_duration_sec, 3), style=performance_style,
        narrative=narrative, acts=acts, anchor_roles=["VOCAL_IDENTITY", "GROOVE"],
        callbacks=callbacks, peak_count=peak_count, strong_moment_budget=strong_budget,
        vocal_density_target=round(sum(act.vocal_target for act in acts) / max(1, len(acts)), 3),
        appearance_count_target=len(acts),
        reasoning_summary="Roles were assigned before exact transitions so identity, groove, payoff, breathing room, and callbacks can shape the set.",
        meaning_priority=0.9 if meaning_requested else 0.25,
        sound_priority=0.9 if sound_requested else 0.5,
        vocal_importance=0.12 if instrumental_requested else 0.9 if meaning_requested else 0.5,
        callback_preference=callback_preference,
    )


def compile_blueprint(blueprint: RemixBlueprint, tracks: list[TrackProfile]) -> dict[str, Any]:
    """Validate the data-only blueprint before timeline compilation."""
    track_ids = {track.id for track in tracks}
    errors: list[str] = []
    previous_end = 0.0
    for act in blueprint.acts:
        if act.role not in MUSICAL_ROLES:
            errors.append(f"unknown role: {act.role}")
        if act.selected_track_id and act.selected_track_id not in track_ids:
            errors.append(f"unknown track for {act.id}")
        if act.start_fraction < previous_end - 0.001 or act.end_fraction <= act.start_fraction:
            errors.append(f"invalid time range for {act.id}")
        previous_end = act.end_fraction
    if errors:
        raise ValueError("Invalid RemixBlueprint: " + "; ".join(errors))
    return blueprint.to_dict()


__all__ = ["MUSICAL_ROLES", "BlueprintAct", "RemixBlueprint", "build_remix_blueprint", "compile_blueprint"]
