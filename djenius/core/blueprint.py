"""V14 whole-performance remix direction.

The blueprint is a small, deterministic creative plan.  It does not render
audio and it does not choose DSP parameters.  Its job is to decide what
musical role the next part of a performance should serve before the existing
V9-V13 timeline planner selects exact executable source intervals.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from djenius.core.models import PerformanceSegment, TrackProfile


MUSICAL_ROLES = (
    "INTRO", "GROOVE", "VOCAL_IDENTITY", "BUILD", "PEAK",
    "BREATHING_ROOM", "RELEASE", "CALLBACK", "OUTRO",
)


@dataclass(frozen=True)
class DirectorIntent:
    """Normalized priorities used by the whole-performance director."""

    meaning_priority: float = 0.5
    sound_priority: float = 0.5
    groove_priority: float = 0.5
    vocal_priority: float = 0.5
    coherence_priority: float = 0.6
    variety_priority: float = 0.35
    callback_priority: float = 0.5

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


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
    decision: str = "SWITCH"  # STAY, VARIATE, LAYER, or SWITCH
    stay_value: float = 0.0
    switch_cost: float = 0.0
    role_fidelity: float = 0.0
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
    director_intent: dict[str, float] = field(default_factory=dict)
    candidate_blueprints: list[dict[str, Any]] = field(default_factory=list)
    whole_score_components: dict[str, float] = field(default_factory=dict)
    whole_score: float = 0.0
    primary_vocal_anchor: str = ""
    primary_groove_anchor: str = ""
    energetic_occupancy: float = 0.0
    stay_switch_decisions: list[dict[str, Any]] = field(default_factory=list)
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


def derive_director_intent(intent: Any = None, performance_style: str = "experimental") -> DirectorIntent:
    """Turn existing SetIntent evidence into normalized director priorities."""
    request = str(getattr(intent, "raw_text", "") or "").lower()
    meaning_requested = bool(
        getattr(intent, "desired_themes", [])
        or getattr(intent, "desired_lyrical_moods", [])
        or any(word in request for word in ("heartbreak", "romantic", "emotional", "lyrics", "meaning", "love"))
    )
    sound_requested = bool(
        getattr(intent, "desired_moods", [])
        or getattr(intent, "desired_activity", [])
        or any(word in request for word in ("energetic", "dance", "party", "club", "groove"))
    )
    energetic = "energetic" in request or "high energy" in request or any(
        label in {"energetic", "dance", "party", "workout"}
        for label in (getattr(intent, "desired_moods", []) or []) + (getattr(intent, "desired_activity", []) or [])
    )
    instrumental = "instrumental" in request or "lyrics do not matter" in request
    lyrical_priority = _clamp(float(getattr(intent, "lyrics_strength", 0.5) or 0.5))
    semantic_priority = _clamp(float(getattr(intent, "semantic_strength", 0.5) or 0.5))
    meaning = 0.92 if meaning_requested else 0.20
    meaning = _clamp(0.65 * meaning + 0.35 * lyrical_priority)
    sound = 0.88 if sound_requested else 0.35
    sound = _clamp(0.65 * sound + 0.35 * semantic_priority)
    if performance_style == "club" or energetic:
        groove = 0.92
    else:
        groove = 0.55
    if instrumental:
        vocal = 0.12
    elif meaning_requested:
        vocal = 0.92
    else:
        vocal = 0.50
    coherence = 0.88 if performance_style in {"story", "smooth"} or meaning_requested else 0.68
    variety = _clamp(float(getattr(intent, "desired_variety", 0.35) or 0.35))
    callback = 0.85 if getattr(intent, "reprise_preference", "balanced") == "callback" else 0.68 if performance_style in {"experimental", "story"} else 0.42
    if "callback" in request or "bring" in request or "return" in request:
        callback = 0.95
    return DirectorIntent(
        meaning_priority=round(meaning, 4), sound_priority=round(sound, 4),
        groove_priority=round(groove, 4), vocal_priority=round(vocal, 4),
        coherence_priority=round(coherence, 4), variety_priority=round(variety, 4),
        callback_priority=round(callback, 4),
    )


def _role_score(
    role: str,
    track: TrackProfile,
    segment: PerformanceSegment,
    intent: Any,
    target_duration_sec: float = 30.0,
    director_intent: DirectorIntent | None = None,
) -> tuple[float, float, float, str]:
    """Return role, meaning, and sound evidence plus an explanation."""
    section = str(segment.section_type or "unknown").lower()
    request = str(getattr(intent, "raw_text", "") or "").lower()
    vocal = float(segment.vocal_density)
    energy = float(segment.energy)
    quality = float(segment.quality_score)
    meaning_labels = _meaning_labels(track)
    sound_labels = _sound_labels(track)
    wanted_meaning = set(getattr(intent, "desired_themes", []) or []) | set(getattr(intent, "desired_lyrical_moods", []) or [])
    wanted_sound = set(getattr(intent, "desired_moods", []) or []) | set(getattr(intent, "desired_activity", []) or [])
    meaning_score = 0.5 if not wanted_meaning else _clamp(len(meaning_labels & wanted_meaning) / max(1, len(wanted_meaning)))
    sound_label_score = 0.5 if not wanted_sound else _clamp(len(sound_labels & wanted_sound) / max(1, len(wanted_sound)))
    duration_fit = 1.0 - min(1.0, abs(segment.duration_sec - target_duration_sec) / max(target_duration_sec, 1.0))
    priorities = director_intent or derive_director_intent(intent)
    groove_score = _clamp(0.48 * (1.0 - min(1.0, vocal)) + 0.32 * energy + 0.20 * float(segment.bass_activity))
    # Sound evidence is intentionally not just a repeated semantic-label
    # match.  Local section character keeps the sound axis distinct from the
    # lyrics axis even when every candidate has the same CLAP tag.
    sound_score = _clamp(0.72 * sound_label_score + 0.28 * groove_score)
    weight_total = 0.20 + 0.16 + 0.15 * priorities.meaning_priority + 0.19 * priorities.sound_priority + 0.12 * priorities.vocal_priority + 0.10 * priorities.groove_priority
    score = (
        0.20 * quality + 0.16 * duration_fit
        + 0.15 * meaning_score * priorities.meaning_priority
        + 0.19 * sound_score * priorities.sound_priority
        + 0.12 * vocal * priorities.vocal_priority
        + 0.10 * groove_score * priorities.groove_priority
    ) / max(weight_total, 1e-6)
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
    energy_requested = priorities.sound_priority >= 0.70 and "energetic" in request
    if energy_requested and role in {"GROOVE", "BUILD", "PEAK"}:
        minimum = {"GROOVE": 0.60, "BUILD": 0.55, "PEAK": 0.70}[role]
        if energy < minimum:
            score -= 0.28 * min(1.0, (minimum - energy) / max(minimum, 0.01))
            evidence.append("below requested energy for this role")
    if priorities.meaning_priority >= 0.75 and role == "VOCAL_IDENTITY" and not meaning_labels:
        score -= 0.18
        evidence.append("missing reliable lyrical meaning")
    if priorities.vocal_priority < 0.25 and role in {"GROOVE", "BREATHING_ROOM", "RELEASE"} and vocal > 0.78:
        score -= 0.18
        evidence.append("too vocal-heavy for instrumental request")
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


def _build_greedy_remix_blueprint(
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


def _region_overlaps(segment: PerformanceSegment, used: dict[str, list[tuple[float, float]]]) -> bool:
    return any(
        max(segment.source_start_sec, left) < min(segment.source_end_sec, right) - 0.5
        for left, right in used.get(segment.track_id, [])
    )


def _whole_score(acts: list[BlueprintAct], priorities: DirectorIntent) -> tuple[float, dict[str, float]]:
    """Score a complete role assignment, keeping component evidence visible."""
    if not acts:
        return 0.0, {}
    role_fidelity = sum(act.role_fidelity for act in acts) / len(acts)
    meaning = sum(act.meaning_score for act in acts) / len(acts)
    sound = sum(act.sound_score for act in acts) / len(acts)
    transitions = max(1, len(acts) - 1)
    switch_count = sum(act.decision == "SWITCH" for act in acts[1:])
    stay_count = sum(act.decision in {"STAY", "VARIATE"} for act in acts[1:])
    unique_tracks = len({act.selected_track_id for act in acts if act.selected_track_id})
    vocal_tracks = [act.selected_track_id for act in acts if act.role in {"VOCAL_IDENTITY", "CALLBACK"}]
    vocal_identity = 1.0 if not vocal_tracks else 1.0 - min(1.0, max(0, len(set(vocal_tracks)) - 1) / max(len(vocal_tracks), 1))
    energy_arc = 1.0
    for previous, current in zip(acts, acts[1:]):
        if current.role == "BUILD":
            energy_arc -= 0.18 * max(0.0, previous.energy_target - current.energy_target)
        elif current.role == "PEAK":
            energy_arc -= 0.20 * max(0.0, previous.energy_target - current.energy_target)
        elif current.role in {"RELEASE", "BREATHING_ROOM"} and previous.role == "PEAK":
            energy_arc -= 0.16 * max(0.0, current.energy_target - previous.energy_target)
    callback_quality = sum(bool(act.callback_to) for act in acts) / max(1, sum(act.role == "CALLBACK" for act in acts))
    switch_cost = 1.0 - min(1.0, sum(act.switch_cost for act in acts) / transitions)
    stable_idea = stay_count / transitions
    components = {
        "request_fidelity": _clamp(0.55 * role_fidelity + 0.25 * meaning + 0.20 * sound),
        "energy_arc": _clamp(energy_arc),
        "semantic_coherence": _clamp(meaning),
        "sound_coherence": _clamp(sound),
        "groove_continuity": _clamp(0.55 * stable_idea + 0.45 * sound),
        "vocal_identity": _clamp(vocal_identity),
        "callback_quality": _clamp(callback_quality),
        "switch_cost": _clamp(switch_cost),
        "stable_idea_duration": _clamp(stable_idea),
        "unique_track_coverage": _clamp(unique_tracks / max(3.0, len(acts) * 0.65)),
    }
    score = (
        0.30 * components["request_fidelity"]
        + 0.14 * components["energy_arc"]
        + 0.11 * components["semantic_coherence"] * priorities.meaning_priority
        + 0.11 * components["sound_coherence"] * priorities.sound_priority
        + 0.10 * components["groove_continuity"] * priorities.groove_priority
        + 0.08 * components["vocal_identity"] * priorities.coherence_priority
        + 0.06 * components["callback_quality"] * priorities.callback_priority
        + 0.06 * components["switch_cost"] * priorities.coherence_priority
        + 0.04 * components["unique_track_coverage"] * priorities.variety_priority
    )
    return _clamp(score), {key: round(value, 4) for key, value in components.items()}


def build_remix_blueprint(
    tracks: list[TrackProfile],
    target_duration_sec: float,
    intent: Any = None,
    *,
    performance_style: str = "experimental",
    segments_by_track: dict[str, list[PerformanceSegment]] | None = None,
    beam_width: int = 6,
) -> RemixBlueprint:
    """Search complete role assignments before compiling the timeline."""
    request = str(getattr(intent, "raw_text", "") or "")
    template = _role_template(performance_style, target_duration_sec, request)
    priorities = derive_director_intent(intent, performance_style)
    if segments_by_track is None:
        from djenius.core.performance import extract_performance_segments
        segments_by_track = {track.id: extract_performance_segments(track) for track in tracks}
    all_candidates = [(track, segment) for track in tracks for segment in segments_by_track.get(track.id, [])]
    if not template or not all_candidates:
        return RemixBlueprint(target_duration_sec=target_duration_sec, style=performance_style, director_intent=priorities.to_dict())

    target_act_duration = target_duration_sec / max(len(template) - 0.18 * (len(template) - 1), 1.0)
    role_options: dict[str, list[tuple[float, float, float, TrackProfile, PerformanceSegment, str]]] = {}
    for role, _state, _start, _end in template:
        options = []
        for track, segment in all_candidates:
            role_score, meaning_score, sound_score, reason = _role_score(
                role, track, segment, intent, target_act_duration, priorities,
            )
            options.append((role_score, meaning_score, sound_score, track, segment, reason))
        minimum_duration = max(12.0, target_act_duration * 0.65)
        maximum_duration = target_act_duration * 1.50
        duration_ready = [
            item for item in options
            if minimum_duration <= item[4].duration_sec <= maximum_duration
        ]
        if len(duration_ready) >= max(2, min(4, len(template) // 2)):
            options = duration_ready
        options.sort(key=lambda item: (item[0], item[1], item[2], item[4].quality_score, item[3].id, item[4].id), reverse=True)
        # Preserve broad library coverage while pruning the beam expansion.
        selected = options[:24]
        for track in tracks:
            # Keep several alternatives per track.  A global top-N cut can
            # otherwise remove every unused region of the vocal anchor and
            # make a requested callback disappear from an otherwise feasible
            # blueprint.
            per_track = [item for item in options if item[3].id == track.id][:8]
            for item in per_track:
                if item not in selected:
                    selected.append(item)
        role_options[role] = selected[: max(24, min(len(options), 24 + 8 * len(tracks)))]

    states: list[dict[str, Any]] = [{
        "acts": [], "used": {}, "score": 0.0, "vocal_anchor": "", "groove_anchor": "",
        "vocal_anchor_segment": "", "switch_count": 0,
    }]
    for index, (role, state_name, start, end) in enumerate(template):
        expanded: list[dict[str, Any]] = []
        for state in states:
            for base_score, meaning_score, sound_score, track, segment, reason in role_options[role]:
                if _region_overlaps(segment, state["used"]):
                    continue
                previous = state["acts"][-1] if state["acts"] else None
                same_track = bool(previous and previous.selected_track_id == track.id)
                track_uses = sum(act.selected_track_id == track.id for act in state["acts"])
                action = "SWITCH"
                stay_value = 0.0
                if same_track:
                    action = "STAY" if role in {"GROOVE", "BUILD", "BREATHING_ROOM", "RELEASE"} else "VARIATE"
                    stay_value = 0.10 + 0.08 * segment.quality_score
                switch_cost = 0.0 if same_track else 0.08 * state["acts"][-1].role_fidelity if previous else 0.0
                if previous and previous.selected_track_id != track.id and previous.vocal_target >= 0.7 and segment.vocal_density >= 0.78:
                    switch_cost += 0.08 * priorities.coherence_priority
                candidate_score = base_score + stay_value - switch_cost
                if track_uses >= 2 and role != "CALLBACK":
                    # Keep source material available for later development or
                    # a callback instead of letting the beam spend one track
                    # on every early act.
                    candidate_score -= 0.08 * min(3, track_uses - 1)
                if role != "CALLBACK" and state["vocal_anchor"] == track.id and track_uses >= 3:
                    candidate_score -= 0.12 * priorities.callback_priority
                if role == "VOCAL_IDENTITY" and state["vocal_anchor"]:
                    candidate_score += 0.10 if track.id == state["vocal_anchor"] else -0.08 * priorities.coherence_priority
                if role == "GROOVE" and state["groove_anchor"]:
                    candidate_score += 0.08 if track.id == state["groove_anchor"] else -0.03 * priorities.coherence_priority
                if role == "CALLBACK":
                    if state["vocal_anchor"] and track.id == state["vocal_anchor"]:
                        candidate_score += 0.22 * priorities.callback_priority
                    elif state["vocal_anchor"]:
                        candidate_score -= 0.16 * priorities.callback_priority
                if previous:
                    if role == "BUILD" and segment.energy + 0.04 < previous.energy_target:
                        candidate_score -= 0.18
                    if role == "PEAK" and segment.energy + 0.05 < previous.energy_target:
                        candidate_score -= 0.25
                    if role in {"RELEASE", "BREATHING_ROOM"} and previous.role == "PEAK" and segment.energy > previous.energy_target:
                        candidate_score -= 0.10
                vocal_anchor = state["vocal_anchor"] or (track.id if role == "VOCAL_IDENTITY" else "")
                vocal_anchor_segment = state["vocal_anchor_segment"] or (segment.id if role == "VOCAL_IDENTITY" else "")
                groove_anchor = state["groove_anchor"] or (track.id if role == "GROOVE" else "")
                callback_to = vocal_anchor_segment if role == "CALLBACK" and track.id == vocal_anchor else ""
                act = BlueprintAct(
                    id=f"act-{index + 1}", role=role, start_fraction=round(start, 4), end_fraction=round(end, 4),
                    state=state_name, energy_target=_target_energy(role),
                    vocal_target=0.78 if role == "VOCAL_IDENTITY" else 0.20 if role in {"GROOVE", "BREATHING_ROOM", "RELEASE"} else 0.45,
                    semantic_target=list(getattr(intent, "desired_themes", []) or []) + list(getattr(intent, "desired_lyrical_moods", []) or []),
                    section_duration_target_sec=round(max(12.0, target_duration_sec * (end - start)), 2),
                    transition_role_in="REVEAL" if role in {"PEAK", "VOCAL_IDENTITY"} else "BUILD" if role == "BUILD" else "CALLBACK" if role == "CALLBACK" else "CONTINUE",
                    transition_role_out="BUILD" if role == "BUILD" else "RELEASE" if role == "PEAK" else "CALLBACK" if role == "CALLBACK" else "CONTINUE",
                    selected_track_id=track.id, selected_segment_id=segment.id, selected_section=segment.section_type,
                    role_score=round(_clamp(candidate_score), 4), meaning_score=round(meaning_score, 4), sound_score=round(sound_score, 4),
                    callback_to=callback_to, callback_reason="return to the opening vocal identity" if callback_to else "",
                    stay_on_track=same_track, decision=action, stay_value=round(stay_value, 4), switch_cost=round(switch_cost, 4),
                    role_fidelity=round(_clamp(base_score), 4), reasoning=reason,
                )
                used = {key: list(value) for key, value in state["used"].items()}
                used.setdefault(track.id, []).append((segment.source_start_sec, segment.source_end_sec))
                expanded.append({
                    "acts": state["acts"] + [act], "used": used,
                    "score": state["score"] + candidate_score,
                    "vocal_anchor": vocal_anchor, "vocal_anchor_segment": vocal_anchor_segment,
                    "groove_anchor": groove_anchor,
                    "switch_count": state["switch_count"] + (action == "SWITCH"),
                })
        expanded.sort(key=lambda item: (item["score"], -item["switch_count"], tuple(act.selected_track_id for act in item["acts"])), reverse=True)
        states = expanded[:beam_width] or states

    ranked: list[tuple[float, dict[str, Any], dict[str, float]]] = []
    for state in states:
        total, components = _whole_score(state["acts"], priorities)
        ranked.append((total, state, components))
    ranked.sort(key=lambda item: (item[0], item[1]["score"], tuple(act.selected_segment_id for act in item[1]["acts"])), reverse=True)
    winner_score, winner, components = ranked[0]
    acts = winner["acts"]
    # Repair a requested callback after beam pruning if the anchor had a
    # usable region that was not retained in the role shortlist.  This keeps
    # callback intent honest without allowing source overlap.
    callback_acts = [act for act in acts if act.role == "CALLBACK"]
    if callback_acts and winner["vocal_anchor"] and not any(act.callback_to for act in callback_acts):
        callback_act = callback_acts[0]
        used_without_callback: dict[str, list[tuple[float, float]]] = {}
        for act in acts:
            if act is callback_act:
                continue
            used_without_callback.setdefault(act.selected_track_id, []).append((
                next((segment.source_start_sec for track, segment in all_candidates if track.id == act.selected_track_id and segment.id == act.selected_segment_id), 0.0),
                next((segment.source_end_sec for track, segment in all_candidates if track.id == act.selected_track_id and segment.id == act.selected_segment_id), 0.0),
            ))
        anchor_options = [
            item for item in all_candidates
            if item[0].id == winner["vocal_anchor"] and not _region_overlaps(item[1], used_without_callback)
        ]
        if anchor_options:
            anchor_options.sort(key=lambda item: (item[1].vocal_density, item[1].quality_score, item[1].energy, item[1].id), reverse=True)
            anchor_track, anchor_segment = anchor_options[0]
            callback_act = replace(
                callback_act, selected_track_id=anchor_track.id, selected_segment_id=anchor_segment.id,
                selected_section=anchor_segment.section_type, callback_to=winner["vocal_anchor_segment"],
                callback_reason="return to the opening vocal identity", decision="VARIATE",
                stay_on_track=anchor_track.id == acts[max(0, acts.index(callback_act) - 1)].selected_track_id,
                role_fidelity=round(anchor_segment.quality_score, 4),
                role_score=round(_clamp(callback_act.role_score + 0.12), 4),
                reasoning="recognizable hook callback repaired from an unused anchor region",
            )
            acts[acts.index(next(act for act in acts if act.id == callback_act.id))] = callback_act
            winner["vocal_anchor"] = anchor_track.id
            winner_score, components = _whole_score(acts, priorities)
    callbacks = [
        {"act_id": act.id, "callback_to": act.callback_to, "reason": act.callback_reason}
        for act in acts if act.callback_to
    ]
    candidate_summaries = []
    for score, candidate, candidate_components in ranked[:3]:
        candidate_summaries.append({
            "whole_score": round(score, 4), "components": candidate_components,
            "unique_tracks": len({act.selected_track_id for act in candidate["acts"]}),
            "appearances": len(candidate["acts"]),
            "tracks": [act.selected_track_id for act in candidate["acts"]],
            "roles": [act.role for act in candidate["acts"]],
            "primary_vocal_anchor": candidate["vocal_anchor"],
            "primary_groove_anchor": candidate["groove_anchor"],
            "callbacks": len([act for act in candidate["acts"] if act.callback_to]),
        })
    active_roles = [act for act in acts if act.role not in {"INTRO", "BREATHING_ROOM", "RELEASE", "OUTRO"}]
    occupancy = sum(act.sound_score >= 0.6 and act.role_fidelity >= 0.6 for act in active_roles) / max(1, len(active_roles))
    return RemixBlueprint(
        target_duration_sec=round(target_duration_sec, 3), style=performance_style,
        narrative=" -> ".join(act.role for act in acts), acts=acts,
        anchor_roles=["VOCAL_IDENTITY", "GROOVE"], callbacks=callbacks,
        peak_count=sum(act.role == "PEAK" for act in acts),
        strong_moment_budget=max(1, min(3, sum(act.role == "PEAK" for act in acts) + 1)),
        vocal_density_target=round(sum(act.vocal_target for act in acts) / max(1, len(acts)), 3),
        appearance_count_target=len(acts),
        reasoning_summary="A deterministic beam search compared complete role assignments before exact timeline execution.",
        meaning_priority=priorities.meaning_priority, sound_priority=priorities.sound_priority,
        vocal_importance=priorities.vocal_priority, callback_preference="callback" if callbacks else "balanced",
        director_intent=priorities.to_dict(), candidate_blueprints=candidate_summaries,
        whole_score_components=components, whole_score=round(winner_score, 4),
        primary_vocal_anchor=winner["vocal_anchor"], primary_groove_anchor=winner["groove_anchor"],
        energetic_occupancy=round(occupancy, 4),
        stay_switch_decisions=[
            {"act_id": act.id, "decision": act.decision, "stay_value": act.stay_value, "switch_cost": act.switch_cost}
            for act in acts[1:]
        ],
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


__all__ = [
    "MUSICAL_ROLES", "DirectorIntent", "BlueprintAct", "RemixBlueprint",
    "derive_director_intent", "build_remix_blueprint", "compile_blueprint",
]
