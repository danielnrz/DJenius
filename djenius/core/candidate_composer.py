"""Feasibility-first deterministic transition candidate generation for V2 Phase 5.

The Candidate Composer proposes a small set of meaningfully different recipes.
It does not audition, score, or select the best-sounding candidate; Phase 6 owns
preview rendering and perceptual/technical ranking.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
from typing import Any

from djenius.core.models import TrackProfile
from djenius.core.performance_recipe import (
    ActionType,
    MusicalPosition,
    PerformanceRecipe,
    Quantization,
    RecipeAction,
    RecipeCompileContext,
    TrackRole,
    compile_performance_recipe,
    phase3_recipe,
    validate_performance_recipe,
)

CANDIDATE_SCHEMA_VERSION = "5.0"
FAMILY_ORDER = (
    "eq_blend", "bass_swap", "filter_blend", "phrase_cut", "echo_out",
    "loop_transition", "loop_shortening", "riser_impact", "drum_bridge",
    "stem_handoff", "tempo_reset",
)


class CandidateRole(str, Enum):
    SMOOTH_BLEND = "smooth_blend"
    FREQUENCY_HANDOFF = "frequency_handoff"
    PHRASE_SWITCH = "phrase_switch"
    RELEASE_RESET = "release_reset"
    BUILD_AND_LAND = "build_and_land"
    RHYTHMIC_BRIDGE = "rhythmic_bridge"
    STEM_MASHUP = "stem_mashup"
    TEMPO_RESET = "tempo_reset"


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canonicalize(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _stable_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(
        _canonicalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:16]}"


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


@dataclass(frozen=True)
class CandidateSegment:
    track_id: str
    start_sec: float
    end_sec: float
    anchor_sec: float
    track_duration_sec: float
    section: str = "unknown"
    phrase_confidence: float = 0.0
    vocal_density: float = 0.0
    energy: float = 0.0
    landing_strength: float = 0.0
    beat_in_bar: int = 0

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "start_sec": round(self.start_sec, 6),
            "end_sec": round(self.end_sec, 6),
            "anchor_sec": round(self.anchor_sec, 6),
            "track_duration_sec": round(self.track_duration_sec, 6),
            "section": self.section,
            "phrase_confidence": round(self.phrase_confidence, 4),
            "vocal_density": round(self.vocal_density, 4),
            "energy": round(self.energy, 4),
            "landing_strength": round(self.landing_strength, 4),
            "beat_in_bar": self.beat_in_bar,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateSegment":
        return cls(
            track_id=str(data.get("track_id", "")),
            start_sec=float(data.get("start_sec", 0.0)),
            end_sec=float(data.get("end_sec", 0.0)),
            anchor_sec=float(data.get("anchor_sec", 0.0)),
            track_duration_sec=float(data.get("track_duration_sec", 0.0)),
            section=str(data.get("section", "unknown")),
            phrase_confidence=float(data.get("phrase_confidence", 0.0)),
            vocal_density=float(data.get("vocal_density", 0.0)),
            energy=float(data.get("energy", 0.0)),
            landing_strength=float(data.get("landing_strength", 0.0)),
            beat_in_bar=int(data.get("beat_in_bar", 0)),
        )


@dataclass(frozen=True)
class CandidateIntent:
    transition_role: str = "CONTINUE"
    set_phase: str = "DEVELOP"
    energy_goal: float = 0.0
    vocal_policy: str = "avoid_overlap"
    target_anchor: str = "phrase"

    def to_dict(self) -> dict[str, Any]:
        return _canonicalize(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateIntent":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass(frozen=True)
class CandidateConstraints:
    min_bars: int = 1
    max_bars: int = 16
    max_primary_tempo_delta_pct: float = 100.0
    requires_phrase_anchor: bool = False
    requires_target_drop: bool = False
    requires_groove_layer: bool = False
    required_source_stems: tuple[str, ...] = ()
    required_target_stems: tuple[str, ...] = ()
    allows_stem_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _canonicalize(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateConstraints":
        values = dict(data)
        values["required_source_stems"] = tuple(values.get("required_source_stems", ()))
        values["required_target_stems"] = tuple(values.get("required_target_stems", ()))
        known = {k: values[k] for k in cls.__dataclass_fields__ if k in values}
        return cls(**known)


@dataclass(frozen=True)
class CandidateDiagnostics:
    feasible: bool
    reason_codes: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "feasible": self.feasible,
            "reason_codes": list(self.reason_codes),
            "evidence": _canonicalize(self.evidence),
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateDiagnostics":
        return cls(
            feasible=bool(data.get("feasible", False)),
            reason_codes=tuple(str(x) for x in data.get("reason_codes", [])),
            evidence=dict(data.get("evidence", {})),
            rejection_reason=str(data.get("rejection_reason", "")),
        )


@dataclass(frozen=True)
class CandidateRejection:
    technique_family: str
    diagnostics: CandidateDiagnostics

    def to_dict(self) -> dict[str, Any]:
        return {"technique_family": self.technique_family, "diagnostics": self.diagnostics.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateRejection":
        return cls(str(data.get("technique_family", "")), CandidateDiagnostics.from_dict(data.get("diagnostics", {})))


@dataclass(frozen=True)
class TransitionCandidate:
    candidate_id: str
    source_track_id: str
    target_track_id: str
    source_bpm: float
    target_bpm: float
    source_segment: CandidateSegment
    target_segment: CandidateSegment
    recipe: PerformanceRecipe
    technique_family: str
    intended_role: CandidateRole
    duration_bars: int
    complexity: int
    stem_requirements: tuple[str, ...]
    groove_requirements: tuple[str, ...]
    tempo_change_requirements: dict[str, Any]
    vocal_overlap_assumptions: dict[str, Any]
    intent: CandidateIntent
    constraints: CandidateConstraints
    diagnostics: CandidateDiagnostics
    generation_reason: str
    generation_seed: int
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = CANDIDATE_SCHEMA_VERSION

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "source_segment": self.source_segment.to_dict(),
            "target_segment": self.target_segment.to_dict(),
            "recipe": self.recipe.to_dict(),
            "technique_family": self.technique_family,
            "intended_role": self.intended_role.value,
            "duration_bars": self.duration_bars,
            "complexity": self.complexity,
            "stem_requirements": list(self.stem_requirements),
            "groove_requirements": list(self.groove_requirements),
            "tempo_change_requirements": _canonicalize(self.tempo_change_requirements),
            "vocal_overlap_assumptions": _canonicalize(self.vocal_overlap_assumptions),
            "intent": self.intent.to_dict(),
            "constraints": self.constraints.to_dict(),
            "diagnostic_reason_codes": list(self.diagnostics.reason_codes),
            "generation_seed": self.generation_seed,
        }

    def with_deterministic_id(self) -> "TransitionCandidate":
        return replace(self, candidate_id=_stable_id("tc5", self._identity_payload()))

    def compile_context(self) -> RecipeCompileContext:
        available_source = frozenset(str(x) for x in self.provenance.get("available_source_stems", []))
        available_target = frozenset(str(x) for x in self.provenance.get("available_target_stems", []))
        return RecipeCompileContext(
            source_appearance_id=f"candidate:{self.candidate_id or self.technique_family}:source",
            target_appearance_id=f"candidate:{self.candidate_id or self.technique_family}:target",
            source_segment_start_sec=self.source_segment.start_sec,
            source_segment_end_sec=self.source_segment.end_sec,
            target_segment_start_sec=self.target_segment.start_sec,
            target_segment_end_sec=self.target_segment.end_sec,
            source_track_duration_sec=self.source_segment.track_duration_sec,
            target_track_duration_sec=self.target_segment.track_duration_sec,
            source_bpm=self.source_bpm,
            target_bpm=self.target_bpm,
            available_source_stems=available_source,
            available_target_stems=available_target,
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.schema_version.split(".", 1)[0] != CANDIDATE_SCHEMA_VERSION.split(".", 1)[0]:
            errors.append("unsupported candidate schema")
        if self.technique_family not in FAMILY_ORDER:
            errors.append("unsupported technique family")
        if self.source_track_id == self.target_track_id or not self.source_track_id or not self.target_track_id:
            errors.append("candidate requires two different track ids")
        if self.source_segment.track_id != self.source_track_id or self.target_segment.track_id != self.target_track_id:
            errors.append("candidate segment ownership mismatch")
        if self.recipe.source_track_id != self.source_track_id or self.recipe.target_track_id != self.target_track_id:
            errors.append("candidate recipe ownership mismatch")
        if self.duration_bars != self.recipe.bars or not 1 <= self.duration_bars <= 64:
            errors.append("candidate duration_bars does not match recipe")
        if not 1 <= self.complexity <= 5:
            errors.append("candidate complexity must be in [1, 5]")
        if not self.diagnostics.feasible:
            errors.append("infeasible candidate must not enter candidate set")
        if self.source_segment.start_sec < 0 or self.source_segment.end_sec > self.source_segment.track_duration_sec + 1e-6:
            errors.append("source candidate segment exceeds track bounds")
        if self.target_segment.start_sec < 0 or self.target_segment.end_sec > self.target_segment.track_duration_sec + 1e-6:
            errors.append("target candidate segment exceeds track bounds")
        if self.source_segment.duration_sec <= 0 or self.target_segment.duration_sec <= 0:
            errors.append("candidate segments must have positive duration")
        expected = self.with_deterministic_id().candidate_id
        if self.candidate_id and self.candidate_id != expected:
            errors.append("candidate_id does not match deterministic candidate content")
        try:
            compile_performance_recipe(self.recipe, self.compile_context())
        except ValueError as exc:
            errors.append(f"candidate recipe is not compilable: {exc}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "source_bpm": self.source_bpm,
            "target_bpm": self.target_bpm,
            "source_segment": self.source_segment.to_dict(),
            "target_segment": self.target_segment.to_dict(),
            "recipe": self.recipe.to_dict(),
            "technique_family": self.technique_family,
            "intended_role": self.intended_role.value,
            "duration_bars": self.duration_bars,
            "complexity": self.complexity,
            "stem_requirements": list(self.stem_requirements),
            "groove_requirements": list(self.groove_requirements),
            "tempo_change_requirements": _canonicalize(self.tempo_change_requirements),
            "vocal_overlap_assumptions": _canonicalize(self.vocal_overlap_assumptions),
            "intent": self.intent.to_dict(),
            "constraints": self.constraints.to_dict(),
            "diagnostics": self.diagnostics.to_dict(),
            "generation_reason": self.generation_reason,
            "generation_seed": self.generation_seed,
            "provenance": _canonicalize(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TransitionCandidate":
        return cls(
            schema_version=str(data.get("schema_version", CANDIDATE_SCHEMA_VERSION)),
            candidate_id=str(data.get("candidate_id", "")),
            source_track_id=str(data.get("source_track_id", "")),
            target_track_id=str(data.get("target_track_id", "")),
            source_bpm=float(data.get("source_bpm", 0.0)),
            target_bpm=float(data.get("target_bpm", 0.0)),
            source_segment=CandidateSegment.from_dict(data.get("source_segment", {})),
            target_segment=CandidateSegment.from_dict(data.get("target_segment", {})),
            recipe=PerformanceRecipe.from_dict(data.get("recipe", {})),
            technique_family=str(data.get("technique_family", "")),
            intended_role=CandidateRole(str(data.get("intended_role", CandidateRole.SMOOTH_BLEND.value))),
            duration_bars=int(data.get("duration_bars", 0)),
            complexity=int(data.get("complexity", 1)),
            stem_requirements=tuple(str(x) for x in data.get("stem_requirements", [])),
            groove_requirements=tuple(str(x) for x in data.get("groove_requirements", [])),
            tempo_change_requirements=dict(data.get("tempo_change_requirements", {})),
            vocal_overlap_assumptions=dict(data.get("vocal_overlap_assumptions", {})),
            intent=CandidateIntent.from_dict(data.get("intent", {})),
            constraints=CandidateConstraints.from_dict(data.get("constraints", {})),
            diagnostics=CandidateDiagnostics.from_dict(data.get("diagnostics", {})),
            generation_reason=str(data.get("generation_reason", "")),
            generation_seed=int(data.get("generation_seed", 0)),
            provenance=dict(data.get("provenance", {})),
        )

@dataclass(frozen=True)
class CandidateSetContext:
    set_phase: str = "DEVELOP"
    transition_role: str = "CONTINUE"
    energy_goal: float = 0.0
    style: str = "balanced"
    previous_technique_families: tuple[str, ...] = ()
    avoid_recent_repeats: bool = True
    allow_tempo_reset: bool = True


@dataclass(frozen=True)
class CandidateComposerConfig:
    min_candidates: int = 3
    max_candidates: int = 8
    long_blend_tempo_delta_pct: float = 6.0
    filter_tempo_delta_pct: float = 8.0
    loop_tempo_delta_pct: float = 10.0
    large_jump_pct: float = 12.0
    vocal_heavy_threshold: float = 0.55
    phrase_confidence_threshold: float = 0.55
    bpm_confidence_threshold: float = 0.55
    tempo_hypothesis_confidence_threshold: float = 0.55
    strong_drop_threshold: float = 0.62
    groove_confidence_threshold: float = 0.30
    max_syncopation_delta: float = 0.55
    max_swing_delta: float = 0.65
    enable_groove_layer: bool = True
    allow_bass_eq_fallback: bool = True

    def validate(self) -> None:
        if not 1 <= self.min_candidates <= self.max_candidates <= 8:
            raise ValueError("candidate count bounds must satisfy 1 <= min <= max <= 8")
        if not 0.0 <= self.tempo_hypothesis_confidence_threshold <= 1.0:
            raise ValueError("tempo hypothesis confidence threshold must be in [0, 1]")


@dataclass(frozen=True)
class CandidateComposition:
    candidates: tuple[TransitionCandidate, ...]
    rejected: tuple[CandidateRejection, ...]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [item.to_dict() for item in self.candidates],
            "rejected": [item.to_dict() for item in self.rejected],
            "diagnostics": _canonicalize(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateComposition":
        return cls(
            candidates=tuple(TransitionCandidate.from_dict(x) for x in data.get("candidates", [])),
            rejected=tuple(CandidateRejection.from_dict(x) for x in data.get("rejected", [])),
            diagnostics=dict(data.get("diagnostics", {})),
        )


def _curve_mean(curve: list[float], start: float, end: float, duration: float) -> float:
    if not curve or duration <= 0 or end <= start:
        return 0.0
    n = len(curve)
    lo = max(0, min(n - 1, int(start / duration * n)))
    hi = max(lo + 1, min(n, int((end / duration) * n + 0.999999)))
    values = [float(x) for x in curve[lo:hi]]
    return sum(values) / len(values) if values else 0.0


def _section_at(track: TrackProfile, time_sec: float) -> dict[str, Any]:
    sections = track.analysis.section_profiles or []
    if not sections:
        return {}
    containing = [x for x in sections if float(x.get("start_sec", 0)) <= time_sec < float(x.get("end_sec", 0))]
    if containing:
        return dict(containing[0])
    return dict(min(sections, key=lambda x: abs(float(x.get("start_sec", 0)) - time_sec)))


def _cue_candidates(track: TrackProfile, *, source: bool) -> list[dict[str, Any]]:
    duration = float(track.duration_sec)
    cues = [dict(x) for x in track.analysis.cue_candidates if 0 <= float(x.get("time_sec", -1)) < duration]
    # Phase 1 normally materializes phrase boundaries into cue_candidates.  If an
    # older/partial analysis has phrase profiles but no cue list, retain that
    # evidence rather than silently falling all the way back to track edges.
    if not cues and track.analysis.phrase_profiles:
        positions = track.analysis.beat_positions or []
        for phrase in track.analysis.phrase_profiles:
            time_sec = float(phrase.get("time_sec", -1.0))
            if not 0.0 <= time_sec < duration:
                continue
            nearest = min(positions, key=lambda x: abs(float(x.get("time_sec", 0.0)) - time_sec)) if positions else {}
            cues.append({
                "time_sec": time_sec,
                "bar_index": int(nearest.get("bar_index", 0)),
                "beat_in_bar": int(nearest.get("beat_in_bar", 0)),
                "confidence": float(phrase.get("confidence", 0.0)),
                "section": "phrase",
                "use_cases": ["mix_in", "mix_out", "phrase_cut"],
                "mix_in_score": 0.6,
                "mix_out_score": 0.6,
            })
    if source:
        useful = [x for x in cues if "mix_out" in x.get("use_cases", []) or "phrase_cut" in x.get("use_cases", [])]
    else:
        useful = [x for x in cues if "mix_in" in x.get("use_cases", []) or "drop_landing" in x.get("use_cases", [])]
    return useful or cues


def _detected_bars_in_window(track: TrackProfile, start_sec: float, end_sec: float) -> int:
    if end_sec <= start_sec:
        return 0
    downbeats = sorted(
        (float(item.get("time_sec", -1.0)), int(item.get("bar_index", 0)))
        for item in (track.analysis.beat_positions or [])
        if start_sec - 1e-6 <= float(item.get("time_sec", -1.0)) < end_sec - 1e-6
        and (bool(item.get("is_downbeat", False)) or int(item.get("beat_in_bar", 0)) == 1)
        and int(item.get("bar_index", 0)) > 0
    )
    if not downbeats:
        return 0
    # Do not mistake a sparse/legacy partial beat-position list for a complete
    # census of the transition window.  Only tighten the duration-derived bar
    # bound when detected downbeats cover both ends to roughly one bar.
    expected_bar_sec = 4.0 * 60.0 / max(float(track.bpm), 1e-6)
    if downbeats[0][0] - start_sec > expected_bar_sec * 1.5:
        return 0
    if end_sec - downbeats[-1][0] > expected_bar_sec * 1.5:
        return 0
    return len({bar_index for _, bar_index in downbeats})


def _choose_anchor(track: TrackProfile, *, source: bool, minimum_lead_sec: float) -> dict[str, Any]:
    duration = float(track.duration_sec)
    cues = _cue_candidates(track, source=source)
    filtered = []
    for cue in cues:
        t = float(cue.get("time_sec", 0.0))
        room = t if source else duration - t
        if room + 1e-6 >= minimum_lead_sec:
            filtered.append(cue)
    cues = filtered or cues
    if cues:
        def score(cue: dict[str, Any]) -> tuple[float, float, float]:
            confidence = float(cue.get("confidence", 0.0))
            mix = float(cue.get("mix_out_score" if source else "mix_in_score", 0.0))
            downbeat = 0.15 if int(cue.get("beat_in_bar", 0)) == 1 else 0.0
            drop = 0.20 if (not source and "drop_landing" in cue.get("use_cases", [])) else 0.0
            position = float(cue.get("time_sec", 0.0)) / max(duration, 1e-6)
            directional = position if source else 1.0 - position
            return (confidence + mix + downbeat + drop, directional, -float(cue.get("time_sec", 0.0)))
        return dict(max(cues, key=score))

    sections = track.analysis.section_profiles or []
    if sections:
        if source:
            section = max(sections, key=lambda x: (float(x.get("mix_out_score", 0)), float(x.get("end_sec", 0))))
            time_sec = min(duration, float(section.get("end_sec", duration)))
        else:
            section = max(sections, key=lambda x: (float(x.get("mix_in_score", 0)) + 0.25 * float(x.get("landing_strength", 0)), -float(x.get("start_sec", 0))))
            time_sec = max(0.0, float(section.get("start_sec", 0.0)))
        return {
            "time_sec": time_sec,
            "beat_in_bar": 1,
            "confidence": float(section.get("boundary_confidence", 0.0)),
            "section": str(section.get("label", "unknown")),
            "mix_in_score": float(section.get("mix_in_score", 0.0)),
            "mix_out_score": float(section.get("mix_out_score", 0.0)),
            "use_cases": ["mix_out"] if source else ["mix_in"],
        }
    return {
        "time_sec": duration if source else 0.0,
        "beat_in_bar": 1,
        "confidence": 0.0,
        "section": "unknown",
        "mix_in_score": 0.0,
        "mix_out_score": 0.0,
        "use_cases": ["fallback_boundary"],
    }


def _tempo_hypothesis_delta(source: TrackProfile, target: TrackProfile) -> tuple[float, str, float]:
    source_h = source.analysis.tempo_hypotheses or [{"relation": "primary", "bpm": source.bpm, "confidence": source.analysis.bpm_confidence}]
    target_h = target.analysis.tempo_hypotheses or [{"relation": "primary", "bpm": target.bpm, "confidence": target.analysis.bpm_confidence}]
    best = (float("inf"), "primary-primary", 0.0)
    for a in source_h:
        for b in target_h:
            av = float(a.get("bpm", 0.0)); bv = float(b.get("bpm", 0.0))
            if av <= 0 or bv <= 0:
                continue
            delta = abs(av - bv) / av * 100.0
            confidence = min(float(a.get("confidence", 0.0)), float(b.get("confidence", 0.0)))
            if delta < best[0] or (abs(delta - best[0]) <= 1e-9 and confidence > best[2]):
                best = (delta, f"{a.get('relation','?')}-{b.get('relation','?')}", confidence)
    return (round(best[0], 4), best[1], round(_clip01(best[2]), 4))


def _declared_stems(track: TrackProfile) -> frozenset[str]:
    stems = track.analysis.stems or {}
    return frozenset(str(k) for k, v in stems.items() if v)


def _candidate_seed(seed: int, family: str, source_id: str, target_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{family}:{source_id}:{target_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31)


def _phase5_recipe(base: PerformanceRecipe, family: str) -> PerformanceRecipe:
    return replace(
        base,
        metadata={"phase": 5, "purpose": "candidate_composer", "candidate_family": family},
    ).with_deterministic_ids()


def _drum_bridge_recipe(source_id: str, target_id: str, *, bars: int, seed: int) -> PerformanceRecipe:
    base = _phase5_recipe(phase3_recipe("eq_blend", source_id, target_id, bars=bars), "drum_bridge")
    pattern = RecipeAction(
        action=ActionType.DRUM_PATTERN,
        position=MusicalPosition(1, 1),
        track_role=TrackRole.GENERATED,
        parameters={
            "pattern_name": "percussion_bridge",
            "repetitions": bars,
            "seed": seed,
            "gain_db": -4.0,
            "level": 0.025,
            "velocity": 0.78,
        },
        duration_beats=0.0,
        quantization=Quantization.BAR,
        order=5,
    )
    actions = tuple(sorted(base.actions + (pattern,), key=lambda x: (x.position.beat_offset, x.order, x.action.value)))
    return replace(base, actions=actions, recipe_id="").with_deterministic_ids()

def compose_transition_candidates(
    source: TrackProfile,
    target: TrackProfile,
    *,
    set_context: CandidateSetContext | None = None,
    config: CandidateComposerConfig | None = None,
    seed: int = 0,
) -> CandidateComposition:
    """Generate deterministic feasible alternatives; never audition or rank audio."""
    set_context = set_context or CandidateSetContext()
    config = config or CandidateComposerConfig()
    config.validate()
    if source.id == target.id or not source.id or not target.id:
        raise ValueError("Candidate Composer requires two different non-empty track ids")
    if source.duration_sec <= 0 or target.duration_sec <= 0:
        raise ValueError("Candidate Composer requires positive track durations")
    if not 40.0 <= source.bpm <= 220.0 or not 40.0 <= target.bpm <= 220.0:
        raise ValueError("Candidate Composer requires BPM in [40, 220]")

    max_window_sec = 16 * 4 * 60.0 / source.bpm
    source_anchor = _choose_anchor(source, source=True, minimum_lead_sec=min(max_window_sec, source.duration_sec * 0.25))
    target_anchor = _choose_anchor(target, source=False, minimum_lead_sec=min(max_window_sec, target.duration_sec * 0.25))
    source_anchor_sec = float(source_anchor.get("time_sec", source.duration_sec))
    target_anchor_sec = float(target_anchor.get("time_sec", 0.0))
    source_start = max(0.0, source_anchor_sec - max_window_sec)
    target_end = min(target.duration_sec, target_anchor_sec + max_window_sec)

    source_section = _section_at(source, max(0.0, source_anchor_sec - 1e-6))
    target_section = _section_at(target, target_anchor_sec)
    source_vocal = _curve_mean(source.analysis.vocal_activity_curve, source_start, source_anchor_sec, source.duration_sec)
    target_vocal = _curve_mean(target.analysis.vocal_activity_curve, target_anchor_sec, target_end, target.duration_sec)
    source_energy = _curve_mean(source.analysis.energy_curve, source_start, source_anchor_sec, source.duration_sec)
    target_energy = _curve_mean(target.analysis.energy_curve, target_anchor_sec, target_end, target.duration_sec)
    source_phrase_conf = max(float(source_anchor.get("confidence", 0.0)), float(source_section.get("boundary_confidence", 0.0)))
    target_phrase_conf = max(float(target_anchor.get("confidence", 0.0)), float(target_section.get("boundary_confidence", 0.0)))
    target_landing = max(float(target_section.get("landing_strength", 0.0)), 0.8 if "drop_landing" in target_anchor.get("use_cases", []) else 0.0)

    source_segment = CandidateSegment(
        source.id, source_start, source_anchor_sec, source_anchor_sec, source.duration_sec,
        str(source_section.get("label", source_anchor.get("section", "unknown"))), source_phrase_conf,
        source_vocal, source_energy, float(source_section.get("landing_strength", 0.0)), int(source_anchor.get("beat_in_bar", 0)),
    )
    target_segment = CandidateSegment(
        target.id, target_anchor_sec, target_end, target_anchor_sec, target.duration_sec,
        str(target_section.get("label", target_anchor.get("section", "unknown"))), target_phrase_conf,
        target_vocal, target_energy, target_landing, int(target_anchor.get("beat_in_bar", 0)),
    )
    source_stems = _declared_stems(source); target_stems = _declared_stems(target)
    raw_tempo_delta = abs(source.bpm - target.bpm) / source.bpm * 100.0
    hypothesis_delta, hypothesis_relation, hypothesis_confidence = _tempo_hypothesis_delta(source, target)
    half_double_supported = (
        hypothesis_relation != "primary-primary"
        and hypothesis_delta <= config.long_blend_tempo_delta_pct
        and hypothesis_confidence >= config.tempo_hypothesis_confidence_threshold
    )
    vocal_overlap = max(source_vocal, target_vocal)
    available_sec = min(source_segment.duration_sec, target_segment.duration_sec)
    duration_bars = int((available_sec * source.bpm) // (4.0 * 60.0) + 1e-9)
    source_detected_bars = _detected_bars_in_window(source, source_segment.start_sec, source_segment.end_sec)
    target_detected_bars = _detected_bars_in_window(target, target_segment.start_sec, target_segment.end_sec)
    detected_limits = [value for value in (source_detected_bars, target_detected_bars) if value > 0]
    available_bars = min([duration_bars, *detected_limits]) if detected_limits else duration_bars
    beat_confident = min(source.analysis.bpm_confidence, target.analysis.bpm_confidence) >= config.bpm_confidence_threshold
    source_groove = source.analysis.groove_profile or {}
    target_groove = target.analysis.groove_profile or {}
    source_groove_conf = float(source_groove.get("confidence", 0.0))
    target_groove_conf = float(target_groove.get("confidence", 0.0))
    groove_evidence_confident = min(source_groove_conf, target_groove_conf) >= config.groove_confidence_threshold
    syncopation_delta = abs(float(source_groove.get("syncopation_index", 0.0)) - float(target_groove.get("syncopation_index", 0.0)))
    swing_delta = abs(float(source_groove.get("swing_ratio", 1.0)) - float(target_groove.get("swing_ratio", 1.0)))
    groove_compatible = (not groove_evidence_confident) or (syncopation_delta <= config.max_syncopation_delta and swing_delta <= config.max_swing_delta)
    downbeat_aligned = source_segment.beat_in_bar in {0, 1} and target_segment.beat_in_bar in {0, 1}
    phrase_aligned = downbeat_aligned and min(source_phrase_conf, target_phrase_conf) >= config.phrase_confidence_threshold
    strong_drop = target_landing >= config.strong_drop_threshold or target_segment.section in {"drop", "chorus"}
    source_bass = float(source_section.get("bass_density", source.analysis.low_energy or 0.0))
    target_bass = float(target_section.get("bass_density", target.analysis.low_energy or 0.0))

    global_evidence = {
        "source_bpm": round(source.bpm, 4), "target_bpm": round(target.bpm, 4),
        "primary_tempo_delta_pct": round(raw_tempo_delta, 4),
        "best_hypothesis_delta_pct": hypothesis_delta, "tempo_hypothesis_relation": hypothesis_relation,
        "tempo_hypothesis_confidence": hypothesis_confidence, "half_double_supported": half_double_supported,
        "source_bpm_confidence": round(source.analysis.bpm_confidence, 4),
        "target_bpm_confidence": round(target.analysis.bpm_confidence, 4),
        "source_phrase_confidence": round(source_phrase_conf, 4), "target_phrase_confidence": round(target_phrase_conf, 4),
        "source_vocal_density": round(source_vocal, 4), "target_vocal_density": round(target_vocal, 4),
        "source_energy": round(source_energy, 4), "target_energy": round(target_energy, 4),
        "target_landing_strength": round(target_landing, 4), "available_bars": available_bars,
        "duration_derived_bars": duration_bars, "source_detected_bars": source_detected_bars,
        "target_detected_bars": target_detected_bars, "beatgrid_confident": beat_confident,
        "source_groove_confidence": round(source_groove_conf, 4),
        "target_groove_confidence": round(target_groove_conf, 4),
        "groove_syncopation_delta": round(syncopation_delta, 4),
        "groove_swing_delta": round(swing_delta, 4), "groove_compatible": groove_compatible,
    }
    intent = CandidateIntent(
        transition_role=set_context.transition_role,
        set_phase=set_context.set_phase,
        energy_goal=set_context.energy_goal,
        vocal_policy="avoid_overlap" if vocal_overlap >= config.vocal_heavy_threshold else "compatible_overlap",
        target_anchor="drop" if strong_drop else "phrase",
    )
    recent = set(set_context.previous_technique_families[-2:]) if set_context.avoid_recent_repeats else set()
    rejected: list[CandidateRejection] = []
    candidates: list[TransitionCandidate] = []
    deferred_recent_candidates: list[TransitionCandidate] = []

    def reject(family: str, *codes: str, detail: str = "") -> None:
        rejected.append(CandidateRejection(family, CandidateDiagnostics(False, tuple(codes), dict(global_evidence), detail or "; ".join(codes))))

    def choose_bars(maximum: int, minimum: int) -> int:
        for bars in (16, 8, 4, 2, 1):
            if minimum <= bars <= maximum and bars <= available_bars:
                return bars
        return 0

    def add_candidate(
        family: str,
        recipe: PerformanceRecipe,
        role: CandidateRole,
        complexity: int,
        constraints: CandidateConstraints,
        reason_codes: tuple[str, ...],
        reason: str,
        *,
        stem_requirements: tuple[str, ...] = (),
        groove_requirements: tuple[str, ...] = (),
    ) -> None:
        provenance = {
            "composer": "v2_phase5_candidate_composer",
            "available_source_stems": sorted(source_stems),
            "available_target_stems": sorted(target_stems),
            "source_anchor_use_cases": sorted(source_anchor.get("use_cases", [])),
            "target_anchor_use_cases": sorted(target_anchor.get("use_cases", [])),
            "generation_reason_codes": list(reason_codes),
        }
        diagnostics = CandidateDiagnostics(True, reason_codes, dict(global_evidence), "")
        candidate = TransitionCandidate(
            candidate_id="", source_track_id=source.id, target_track_id=target.id,
            source_bpm=source.bpm, target_bpm=target.bpm,
            source_segment=source_segment, target_segment=target_segment,
            recipe=recipe, technique_family=family, intended_role=role,
            duration_bars=recipe.bars, complexity=complexity,
            stem_requirements=stem_requirements, groove_requirements=groove_requirements,
            tempo_change_requirements={
                "primary_delta_pct": round(raw_tempo_delta, 4),
                "best_hypothesis_delta_pct": hypothesis_delta,
                "relation": hypothesis_relation,
            },
            vocal_overlap_assumptions={
                "source_density": round(source_vocal, 4), "target_density": round(target_vocal, 4),
                "policy": intent.vocal_policy,
            },
            intent=intent, constraints=constraints, diagnostics=diagnostics,
            generation_reason=reason, generation_seed=seed, provenance=provenance,
        ).with_deterministic_id()
        errors = candidate.validate()
        if errors:
            reject(family, "compile_or_candidate_validation_failed", detail="; ".join(errors))
            return
        if family in recent:
            deferred_recent_candidates.append(candidate)
        else:
            candidates.append(candidate)

    # Smooth blend families: primary tempo compatibility is intentionally strict.
    long_bars = choose_bars(16, 4)
    if not long_bars:
        reject("eq_blend", "insufficient_overlap_bars")
    elif not beat_confident:
        reject("eq_blend", "low_bpm_confidence")
    elif raw_tempo_delta > config.long_blend_tempo_delta_pct:
        reject("eq_blend", "primary_tempo_delta_too_large")
    elif vocal_overlap > config.vocal_heavy_threshold:
        reject("eq_blend", "vocal_overlap_too_dense")
    else:
        recipe = _phase5_recipe(phase3_recipe("eq_blend", source.id, target.id, bars=long_bars), "eq_blend")
        add_candidate("eq_blend", recipe, CandidateRole.SMOOTH_BLEND, 2,
            CandidateConstraints(4, 16, config.long_blend_tempo_delta_pct),
            ("tempo_close", "sufficient_overlap", "vocal_overlap_acceptable"),
            f"{long_bars}-bar EQ blend is feasible: primary BPM delta is {raw_tempo_delta:.1f}% with compatible overlap windows.")

    bass_bars = choose_bars(8, 4)
    if not bass_bars:
        reject("bass_swap", "insufficient_overlap_bars")
    elif not beat_confident:
        reject("bass_swap", "low_bpm_confidence")
    elif raw_tempo_delta > config.filter_tempo_delta_pct:
        reject("bass_swap", "primary_tempo_delta_too_large")
    elif min(source_bass, target_bass) < 0.10:
        reject("bass_swap", "insufficient_bass_activity")
    elif not config.allow_bass_eq_fallback and not ({"bass"} <= source_stems and {"bass"} <= target_stems):
        reject("bass_swap", "bass_stems_unavailable")
    else:
        fallback = not ({"bass"} <= source_stems and {"bass"} <= target_stems)
        codes = ("bass_activity_present", "tempo_compatible", "eq_fallback_available" if fallback else "bass_stems_available")
        recipe = _phase5_recipe(phase3_recipe("bass_swap", source.id, target.id, bars=bass_bars), "bass_swap")
        add_candidate("bass_swap", recipe, CandidateRole.FREQUENCY_HANDOFF, 3,
            CandidateConstraints(4, 8, config.filter_tempo_delta_pct, allows_stem_fallback=config.allow_bass_eq_fallback),
            codes, f"{bass_bars}-bar bass handoff is feasible with {'explicit EQ fallback' if fallback else 'declared bass stems'}.")

    filter_bars = choose_bars(8, 4)
    if not filter_bars:
        reject("filter_blend", "insufficient_overlap_bars")
    elif not beat_confident:
        reject("filter_blend", "low_bpm_confidence")
    elif raw_tempo_delta > config.filter_tempo_delta_pct:
        reject("filter_blend", "primary_tempo_delta_too_large")
    elif vocal_overlap > min(0.72, config.vocal_heavy_threshold + 0.12):
        reject("filter_blend", "vocal_overlap_too_dense")
    else:
        recipe = _phase5_recipe(phase3_recipe("filter_blend", source.id, target.id, bars=filter_bars), "filter_blend")
        add_candidate("filter_blend", recipe, CandidateRole.SMOOTH_BLEND, 2,
            CandidateConstraints(4, 8, config.filter_tempo_delta_pct),
            ("tempo_compatible", "filter_masking_available"),
            f"{filter_bars}-bar filter blend is feasible with {raw_tempo_delta:.1f}% primary BPM delta.")

    cut_bars = choose_bars(4, 2)
    if not cut_bars:
        reject("phrase_cut", "insufficient_boundary_room")
    elif not phrase_aligned:
        reject("phrase_cut", "weak_or_non_downbeat_phrase_anchor")
    else:
        recipe = _phase5_recipe(phase3_recipe("phrase_cut", source.id, target.id, bars=cut_bars), "phrase_cut")
        add_candidate("phrase_cut", recipe, CandidateRole.PHRASE_SWITCH, 1,
            CandidateConstraints(2, 4, 100.0, requires_phrase_anchor=True),
            ("strong_phrase_anchor", "downbeat_aligned"),
            f"Phrase cut targets a confident downbeat boundary ({source_phrase_conf:.2f}/{target_phrase_conf:.2f} confidence).")

    echo_bars = choose_bars(4, 2)
    if not echo_bars:
        reject("echo_out", "insufficient_boundary_room")
    elif target_segment.beat_in_bar not in {0, 1} and target_phrase_conf < config.phrase_confidence_threshold:
        reject("echo_out", "weak_target_landing")
    else:
        recipe = _phase5_recipe(phase3_recipe("echo_release", source.id, target.id, bars=echo_bars), "echo_out")
        add_candidate("echo_out", recipe, CandidateRole.RELEASE_RESET, 2,
            CandidateConstraints(2, 4),
            ("release_path_available", "bounded_target_landing"),
            f"Echo-out candidate uses a {echo_bars}-bar release into the selected target boundary.")

    loop_bars = choose_bars(8, 4)
    if not loop_bars:
        reject("loop_transition", "insufficient_loop_window")
    elif not beat_confident:
        reject("loop_transition", "low_bpm_confidence")
    elif raw_tempo_delta > config.loop_tempo_delta_pct:
        reject("loop_transition", "primary_tempo_delta_too_large")
    elif source_vocal > config.vocal_heavy_threshold:
        reject("loop_transition", "source_loop_vocal_density_too_high")
    else:
        recipe = _phase5_recipe(phase3_recipe("loop_transition", source.id, target.id, bars=loop_bars), "loop_transition")
        add_candidate("loop_transition", recipe, CandidateRole.BUILD_AND_LAND, 3,
            CandidateConstraints(4, 8, config.loop_tempo_delta_pct),
            ("loop_window_available", "source_vocal_density_acceptable"),
            f"Loop transition has {loop_bars} bars of bounded source material with manageable vocal density.")

    short_bars = choose_bars(4, 4)
    if not short_bars:
        reject("loop_shortening", "insufficient_loop_window")
    elif not beat_confident:
        reject("loop_shortening", "low_bpm_confidence")
    elif not strong_drop:
        reject("loop_shortening", "target_drop_not_strong")
    elif source_vocal > min(0.75, config.vocal_heavy_threshold + 0.15):
        reject("loop_shortening", "source_loop_vocal_density_too_high")
    else:
        recipe = _phase5_recipe(phase3_recipe("loop_shortening", source.id, target.id, bars=4), "loop_shortening")
        add_candidate("loop_shortening", recipe, CandidateRole.BUILD_AND_LAND, 4,
            CandidateConstraints(4, 4, 100.0, requires_target_drop=True),
            ("target_drop_strong", "loop_shortening_window_available"),
            "Four-bar loop shortening is feasible because the target has a strong landing and the source window is loopable enough.")

    if available_bars < 4:
        reject("riser_impact", "insufficient_riser_lead_time")
    elif not beat_confident:
        reject("riser_impact", "low_bpm_confidence")
    elif not strong_drop:
        reject("riser_impact", "target_drop_not_strong")
    elif set_context.style.lower() in {"subtle", "minimal"}:
        reject("riser_impact", "style_disallows_strong_fx")
    elif target_segment.beat_in_bar not in {0, 1}:
        reject("riser_impact", "target_landing_not_downbeat")
    else:
        recipe = _phase5_recipe(phase3_recipe("riser_impact", source.id, target.id, bars=4), "riser_impact")
        add_candidate("riser_impact", recipe, CandidateRole.BUILD_AND_LAND, 4,
            CandidateConstraints(4, 4, 100.0, requires_target_drop=True, requires_groove_layer=True),
            ("target_drop_strong", "four_bar_fx_lead_available", "groove_sample_layer_available"),
            "Riser-impact candidate has four bars of lead time and lands on a strong target downbeat.",
            groove_requirements=("noise_riser_v1", "impact_v1"))

    drum_bars = choose_bars(4, 4)
    if not config.enable_groove_layer:
        reject("drum_bridge", "groove_layer_disabled")
    elif not drum_bars:
        reject("drum_bridge", "insufficient_bridge_bars")
    elif not beat_confident:
        reject("drum_bridge", "low_bpm_confidence")
    elif raw_tempo_delta > config.loop_tempo_delta_pct:
        reject("drum_bridge", "primary_tempo_delta_too_large")
    elif set_context.style.lower() in {"minimal"}:
        reject("drum_bridge", "style_disallows_added_percussion")
    elif not groove_compatible:
        reject("drum_bridge", "groove_mismatch_too_large")
    else:
        recipe = _drum_bridge_recipe(source.id, target.id, bars=4, seed=_candidate_seed(seed, "drum_bridge", source.id, target.id))
        add_candidate("drum_bridge", recipe, CandidateRole.RHYTHMIC_BRIDGE, 4,
            CandidateConstraints(4, 4, config.loop_tempo_delta_pct, requires_groove_layer=True),
            ("groove_sample_layer_available", "four_bar_bridge_window", "tempo_compatible"),
            "Four-bar percussion bridge is feasible and uses the deterministic Phase 4 groove layer.",
            groove_requirements=("percussion_bridge",))

    required_source = ("vocals",); required_target = ("drums", "bass", "other")
    if available_bars < 4:
        reject("stem_handoff", "insufficient_overlap_bars")
    elif not beat_confident:
        reject("stem_handoff", "low_bpm_confidence")
    elif not set(required_source) <= source_stems or not set(required_target) <= target_stems:
        reject("stem_handoff", "required_stems_unavailable")
    elif source_vocal < 0.10 and float(source.analysis.stem_activity_profiles.get("vocals", {}).get("active_fraction", 0.0)) < 0.10:
        reject("stem_handoff", "source_vocal_material_too_sparse")
    else:
        recipe = _phase5_recipe(phase3_recipe("stem_handoff", source.id, target.id, bars=4), "stem_handoff")
        stem_req = tuple(f"source:{x}" for x in required_source) + tuple(f"target:{x}" for x in required_target)
        add_candidate("stem_handoff", recipe, CandidateRole.STEM_MASHUP, 5,
            CandidateConstraints(4, 4, 100.0, required_source_stems=required_source, required_target_stems=required_target),
            ("required_stems_declared", "stem_handoff_window_available"),
            "Stem handoff is feasible because source vocals and target drums/bass/other stems are declared available.",
            stem_requirements=stem_req)

    reset_bars = choose_bars(4, 2)
    if not set_context.allow_tempo_reset:
        reject("tempo_reset", "set_context_disallows_tempo_reset")
    elif not reset_bars:
        reject("tempo_reset", "insufficient_reset_window")
    elif raw_tempo_delta < config.large_jump_pct:
        reject("tempo_reset", "tempo_jump_not_large_enough")
    elif half_double_supported:
        reject("tempo_reset", "half_double_relation_avoids_reset")
    elif target_landing < 0.50 and target_segment.beat_in_bar not in {0, 1}:
        reject("tempo_reset", "target_reset_landing_too_weak")
    else:
        recipe = _phase5_recipe(phase3_recipe("tempo_reset", source.id, target.id, bars=reset_bars), "tempo_reset")
        add_candidate("tempo_reset", recipe, CandidateRole.TEMPO_RESET, 3,
            CandidateConstraints(2, 4, 100.0, requires_phrase_anchor=False),
            ("large_primary_tempo_jump", "reset_landing_available"),
            f"Tempo reset is justified by a {raw_tempo_delta:.1f}% primary BPM jump and a bounded target landing.")

    # Deterministic, context-sensitive generation order; this is not a quality rank.
    family_priority = list(FAMILY_ORDER)
    if raw_tempo_delta >= config.large_jump_pct:
        family_priority = ["tempo_reset", "phrase_cut", "echo_out", "riser_impact", "loop_shortening", "stem_handoff", "drum_bridge", "eq_blend", "bass_swap", "filter_blend", "loop_transition"]
    elif vocal_overlap >= config.vocal_heavy_threshold:
        family_priority = ["phrase_cut", "echo_out", "stem_handoff", "riser_impact", "loop_shortening", "drum_bridge", "bass_swap", "filter_blend", "eq_blend", "loop_transition", "tempo_reset"]
    priority = {name: i for i, name in enumerate(family_priority)}
    order_key = lambda item: (priority.get(item.technique_family, 999), item.candidate_id)
    candidates = sorted(candidates, key=order_key)
    deferred_recent_candidates = sorted(deferred_recent_candidates, key=order_key)
    memory_reintroduced: list[str] = []
    needed_for_floor = max(0, config.min_candidates - len(candidates))
    for candidate in deferred_recent_candidates[:needed_for_floor]:
        diagnostics = replace(
            candidate.diagnostics,
            reason_codes=candidate.diagnostics.reason_codes + ("recent_repeat_required_for_candidate_floor",),
        )
        provenance = {
            **candidate.provenance,
            "technique_memory": "repeat_allowed_to_meet_candidate_floor",
        }
        candidate = replace(
            candidate,
            candidate_id="",
            diagnostics=diagnostics,
            generation_reason=candidate.generation_reason + " Recent-family repetition is retained because harder feasibility constraints left too few alternatives.",
            provenance=provenance,
        ).with_deterministic_id()
        candidates.append(candidate)
        memory_reintroduced.append(candidate.technique_family)
    for candidate in deferred_recent_candidates[needed_for_floor:]:
        reject(candidate.technique_family, "recent_family_repeat", detail="Family was used in the recent technique memory window and enough feasible alternatives remained.")
    candidates = sorted(candidates, key=order_key)[:config.max_candidates]
    retained_families = {item.technique_family for item in candidates}
    for family in FAMILY_ORDER:
        if family not in retained_families and not any(x.technique_family == family for x in rejected):
            reject(family, "candidate_cap_trimmed", detail="Feasible family was omitted by the configured candidate cap.")

    ids = [item.candidate_id for item in candidates]
    families = [item.technique_family for item in candidates]
    if len(ids) != len(set(ids)) or len(families) != len(set(families)):
        raise RuntimeError("Candidate Composer produced duplicate candidate identity/family")
    if len(candidates) < config.min_candidates:
        floor_status = "candidate_floor_unmet_due_to_hard_feasibility"
    else:
        floor_status = "candidate_floor_met"
    diagnostics = {
        **global_evidence,
        "candidate_count": len(candidates),
        "candidate_families": families,
        "rejected_count": len(rejected),
        "candidate_floor_status": floor_status,
        "candidate_cap": config.max_candidates,
        "memory_reintroduced_families": memory_reintroduced,
        "audition_ranking_performed": False,
    }
    return CandidateComposition(tuple(candidates), tuple(rejected), diagnostics)
