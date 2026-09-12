"""Typed musical-time performance recipes for DJenius V2.

Recipes describe *what the DJ does* in beat/bar time.  Compilation translates
that intent into the existing PerformanceTransition contract, so the proven V1
and segment renderers remain the execution boundary during the V2 migration.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
from typing import Any

RECIPE_SCHEMA_VERSION = "2.0"
BEATS_PER_BAR = 4
PHASE2_TECHNIQUES = {"eq_blend", "bass_swap", "phrase_cut", "loop_transition", "echo_release"}
PHASE3_TECHNIQUES = PHASE2_TECHNIQUES | {
    "filter_blend", "reverb_wash", "loop_shortening", "drum_overlay",
    "riser_impact", "tempo_reset", "stem_handoff",
}


class TrackRole(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    MASTER = "master"
    GENERATED = "generated"


class Quantization(str, Enum):
    BEAT = "beat"
    BAR = "bar"
    PHRASE = "phrase"
    NONE = "none"


class ActionType(str, Enum):
    START = "start"
    STOP = "stop"
    GAIN = "gain"
    FADE = "fade"
    CROSSFADER = "crossfader"
    EQ_LOW = "eq_low"
    EQ_MID = "eq_mid"
    EQ_HIGH = "eq_high"
    FILTER_LP = "filter_lp"
    FILTER_HP = "filter_hp"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"
    LOOP_LENGTH = "loop_length"
    BEAT_JUMP = "beat_jump"
    STEM_GAIN = "stem_gain"
    STEM_MUTE = "stem_mute"
    STEM_SOLO = "stem_solo"
    ECHO = "echo"
    DELAY = "delay"
    REVERB = "reverb"
    SAMPLE = "sample"
    RISER = "riser"
    IMPACT = "impact"
    TEMPO_RAMP = "tempo_ramp"
    RELEASE = "release"


@dataclass(frozen=True)
class MusicalPosition:
    """One-based transition-local musical position."""

    bar: int = 1
    beat: int = 1
    phrase: int | None = None
    section: str = ""

    @property
    def beat_offset(self) -> int:
        return (self.bar - 1) * BEATS_PER_BAR + (self.beat - 1)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"bar": self.bar, "beat": self.beat}
        if self.phrase is not None:
            result["phrase"] = self.phrase
        if self.section:
            result["section"] = self.section
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MusicalPosition":
        values = data or {}
        return cls(
            bar=int(values.get("bar", 1)),
            beat=int(values.get("beat", 1)),
            phrase=int(values["phrase"]) if values.get("phrase") is not None else None,
            section=str(values.get("section", "")),
        )


@dataclass(frozen=True)
class RecipeAction:
    """One deterministic action on the transition clock."""

    action: ActionType
    position: MusicalPosition
    track_role: TrackRole = TrackRole.MASTER
    parameters: dict[str, Any] = field(default_factory=dict)
    duration_beats: float = 0.0
    quantization: Quantization = Quantization.BEAT
    order: int = 0
    action_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action": self.action.value,
            "position": self.position.to_dict(),
            "track_role": self.track_role.value,
            "parameters": _canonicalize(self.parameters),
            "duration_beats": self.duration_beats,
            "quantization": self.quantization.value,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecipeAction":
        return cls(
            action=ActionType(str(data.get("action", "gain"))),
            position=MusicalPosition.from_dict(data.get("position")),
            track_role=TrackRole(str(data.get("track_role", "master"))),
            parameters=dict(data.get("parameters", {})),
            duration_beats=float(data.get("duration_beats", 0.0)),
            quantization=Quantization(str(data.get("quantization", "beat"))),
            order=int(data.get("order", 0)),
            action_id=str(data.get("action_id", "")),
        )


@dataclass(frozen=True)
class PerformanceRecipe:
    """Serializable multi-action DJ handoff expressed in musical time."""

    technique: str
    source_track_id: str
    target_track_id: str
    bars: int
    actions: tuple[RecipeAction, ...]
    clock_role: TrackRole = TrackRole.SOURCE
    schema_version: str = RECIPE_SCHEMA_VERSION
    recipe_id: str = ""
    provenance_version: str = "v2-recipe-provenance-1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_deterministic_ids(self) -> "PerformanceRecipe":
        provisional = replace(self, recipe_id="", actions=tuple(replace(item, action_id="") for item in self.actions))
        recipe_id = _stable_id("r2", provisional._identity_payload())
        actions = tuple(
            replace(item, action_id=_stable_id("a2", {
                "recipe_id": recipe_id,
                "index": index,
                "action": item.to_dict() | {"action_id": ""},
            }))
            for index, item in enumerate(provisional.actions)
        )
        return replace(provisional, recipe_id=recipe_id, actions=actions)

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "technique": self.technique,
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "bars": self.bars,
            "clock_role": self.clock_role.value,
            "provenance_version": self.provenance_version,
            "metadata": _canonicalize(self.metadata),
            "actions": [item.to_dict() | {"action_id": ""} for item in self.actions],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "recipe_id": self.recipe_id,
            "technique": self.technique,
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "bars": self.bars,
            "clock_role": self.clock_role.value,
            "provenance_version": self.provenance_version,
            "metadata": _canonicalize(self.metadata),
            "actions": [item.to_dict() for item in self.actions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PerformanceRecipe":
        return cls(
            schema_version=str(data.get("schema_version", RECIPE_SCHEMA_VERSION)),
            recipe_id=str(data.get("recipe_id", "")),
            technique=str(data.get("technique", "")),
            source_track_id=str(data.get("source_track_id", "")),
            target_track_id=str(data.get("target_track_id", "")),
            bars=int(data.get("bars", 0)),
            clock_role=TrackRole(str(data.get("clock_role", "source"))),
            provenance_version=str(data.get("provenance_version", "v2-recipe-provenance-1")),
            metadata=dict(data.get("metadata", {})),
            actions=tuple(RecipeAction.from_dict(item) for item in data.get("actions", [])),
        )


@dataclass(frozen=True)
class RecipeCompileContext:
    source_appearance_id: str
    target_appearance_id: str
    source_segment_start_sec: float
    source_segment_end_sec: float
    target_segment_start_sec: float
    target_segment_end_sec: float
    source_track_duration_sec: float
    target_track_duration_sec: float
    source_bpm: float
    target_bpm: float
    available_source_stems: frozenset[str] = frozenset()
    available_target_stems: frozenset[str] = frozenset()
    beats_per_bar: int = BEATS_PER_BAR

    def bpm_for(self, role: TrackRole) -> float:
        return self.target_bpm if role == TrackRole.TARGET else self.source_bpm


@dataclass(frozen=True)
class CompiledPerformanceRecipe:
    recipe: PerformanceRecipe
    transition_type: str
    clock_bpm: float
    recipe_duration_sec: float
    overlap_duration_sec: float
    source_start_sec: float
    source_end_sec: float
    target_start_sec: float
    target_end_sec: float
    requires_stretch: bool
    target_consumed_duration_sec: float
    action_schedule: tuple[dict[str, Any], ...]
    preparation_operations: tuple[dict[str, Any], ...] = ()
    technique_operations: tuple[dict[str, Any], ...] = ()
    landing_operations: tuple[dict[str, Any], ...] = ()
    preparation_duration_sec: float = 0.0


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def _stable_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(_canonicalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:16]}"


def _action_sort_key(action: RecipeAction) -> tuple[int, int, str]:
    return (action.position.beat_offset, action.order, action.action.value)


def _validate_parameter_bounds(action: RecipeAction) -> list[str]:
    errors: list[str] = []
    p = action.parameters

    def bounded(name: str, low: float, high: float) -> None:
        if name in p:
            try:
                value = float(p[name])
            except (TypeError, ValueError):
                errors.append(f"{action.action.value}.{name} is not numeric")
                return
            if not low <= value <= high:
                errors.append(f"{action.action.value}.{name} outside [{low}, {high}]")

    if action.action in {ActionType.START, ActionType.GAIN, ActionType.FADE, ActionType.EQ_LOW, ActionType.EQ_MID, ActionType.EQ_HIGH, ActionType.STEM_GAIN}:
        bounded("gain_db", -60.0, 12.0)
    if action.action == ActionType.CROSSFADER:
        bounded("value", -1.0, 1.0)
    if action.action in {ActionType.FILTER_LP, ActionType.FILTER_HP}:
        bounded("cutoff_hz", 20.0, 20000.0)
        bounded("resonance", 0.0, 1.0)
    if action.action in {ActionType.ECHO, ActionType.DELAY}:
        bounded("wet", 0.0, 1.0)
        bounded("feedback", 0.0, 0.85)
    if action.action == ActionType.REVERB:
        bounded("wet", 0.0, 1.0)
        bounded("decay_sec", 0.05, 20.0)
    if action.action in {ActionType.LOOP_START, ActionType.LOOP_LENGTH}:
        bounded("length_beats", 0.25, 32.0)
    if action.action == ActionType.BEAT_JUMP:
        bounded("beats", -64.0, 64.0)
    if action.action == ActionType.TEMPO_RAMP:
        bounded("target_bpm", 40.0, 220.0)
    if action.action in {ActionType.RISER, ActionType.IMPACT, ActionType.SAMPLE}:
        bounded("level", 0.0, 0.05)
    if action.action in {ActionType.STEM_GAIN, ActionType.STEM_MUTE, ActionType.STEM_SOLO}:
        if str(p.get("stem", "")) not in {"vocals", "drums", "bass", "other"}:
            errors.append(f"{action.action.value} requires a known stem")
    return errors


def validate_performance_recipe(recipe: PerformanceRecipe, context: RecipeCompileContext | None = None) -> list[str]:
    """Return deterministic structural/safety violations without mutating input."""
    errors: list[str] = []
    if recipe.schema_version.split(".", 1)[0] != RECIPE_SCHEMA_VERSION.split(".", 1)[0]:
        errors.append(f"unsupported recipe schema version: {recipe.schema_version}")
    if recipe.technique not in PHASE3_TECHNIQUES:
        errors.append(f"unsupported V2 technique: {recipe.technique}")
    if not recipe.source_track_id or not recipe.target_track_id:
        errors.append("recipe requires source and target track ids")
    if recipe.source_track_id == recipe.target_track_id:
        errors.append("V2 transition recipe requires two different tracks")
    if recipe.bars < 1 or recipe.bars > 64:
        errors.append("recipe bars must be in [1, 64]")
    if not recipe.actions:
        errors.append("recipe has no actions")

    expected = recipe.with_deterministic_ids()
    if recipe.recipe_id and recipe.recipe_id != expected.recipe_id:
        errors.append("recipe_id does not match deterministic recipe content")
    for index, action in enumerate(recipe.actions):
        if action.action_id and action.action_id != expected.actions[index].action_id:
            errors.append(f"action {index + 1} id does not match deterministic recipe content")
        if action.position.bar < 1 or action.position.bar > max(recipe.bars, 1):
            errors.append(f"action {index + 1} bar is outside recipe")
        if action.position.beat < 1 or action.position.beat > BEATS_PER_BAR:
            errors.append(f"action {index + 1} beat must be in [1, 4]")
        if action.position.phrase is not None and action.position.phrase < 1:
            errors.append(f"action {index + 1} phrase must be one-based")
        if action.duration_beats < 0 or action.duration_beats > recipe.bars * BEATS_PER_BAR:
            errors.append(f"action {index + 1} duration is outside recipe")
        if action.position.beat_offset + action.duration_beats > recipe.bars * BEATS_PER_BAR + 1e-9:
            errors.append(f"action {index + 1} extends beyond recipe")
        if action.quantization == Quantization.BAR and action.position.beat != 1:
            errors.append(f"action {index + 1} claims bar quantization off the downbeat")
        if action.quantization == Quantization.PHRASE:
            if action.position.beat != 1:
                errors.append(f"action {index + 1} claims phrase quantization off the downbeat")
            if action.position.phrase is None:
                errors.append(f"action {index + 1} phrase quantization requires a phrase index")
        if action.order < 0:
            errors.append(f"action {index + 1} order must be non-negative")
        errors.extend(f"action {index + 1}: {item}" for item in _validate_parameter_bounds(action))

    if list(recipe.actions) != sorted(recipe.actions, key=_action_sort_key):
        errors.append("actions are not in deterministic musical-time order")

    loop_open = False
    for index, action in enumerate(recipe.actions):
        if action.action == ActionType.LOOP_START:
            if loop_open:
                errors.append(f"action {index + 1} starts a loop while another loop is open")
            loop_open = True
        elif action.action == ActionType.LOOP_LENGTH and not loop_open:
            errors.append(f"action {index + 1} changes loop length without an active loop")
        elif action.action == ActionType.LOOP_END:
            if not loop_open:
                errors.append(f"action {index + 1} ends a loop that is not active")
            loop_open = False
    if loop_open:
        errors.append("recipe leaves a loop active at the end")

    for action in recipe.actions:
        if action.action in {ActionType.STEM_GAIN, ActionType.STEM_MUTE, ActionType.STEM_SOLO}:
            if action.track_role not in {TrackRole.SOURCE, TrackRole.TARGET}:
                errors.append(f"{action.action.value} requires source or target track role")
            elif context:
                stem = str(action.parameters.get("stem", ""))
                available = context.available_target_stems if action.track_role == TrackRole.TARGET else context.available_source_stems
                if stem not in available:
                    errors.append(f"{action.track_role.value} stem unavailable: {stem}")

    if context:
        if context.beats_per_bar != BEATS_PER_BAR:
            errors.append("Phase 2 compiler currently requires a 4/4 transition clock")
        clock_bpm = context.bpm_for(recipe.clock_role)
        if not 40.0 <= clock_bpm <= 220.0:
            errors.append("recipe clock BPM must be in [40, 220]")
        else:
            duration = recipe.bars * context.beats_per_bar * 60.0 / clock_bpm
            source_available = context.source_segment_end_sec - context.source_segment_start_sec
            target_available = context.target_segment_end_sec - context.target_segment_start_sec
            if duration > source_available + 1e-6:
                errors.append("recipe exceeds source segment bounds")
            if duration > target_available + 1e-6:
                errors.append("recipe exceeds target segment bounds")
        if context.source_segment_end_sec <= context.source_segment_start_sec:
            errors.append("source segment has no duration")
        if context.target_segment_end_sec <= context.target_segment_start_sec:
            errors.append("target segment has no duration")
        if context.source_segment_start_sec < -1e-6 or context.source_segment_end_sec > context.source_track_duration_sec + 1e-6:
            errors.append("source segment exceeds track bounds")
        if context.target_segment_start_sec < -1e-6 or context.target_segment_end_sec > context.target_track_duration_sec + 1e-6:
            errors.append("target segment exceeds track bounds")

    return errors


def require_valid_performance_recipe(recipe: PerformanceRecipe, context: RecipeCompileContext | None = None) -> None:
    errors = validate_performance_recipe(recipe, context)
    if errors:
        raise ValueError("Invalid performance recipe: " + "; ".join(errors))


def _position_seconds(position: MusicalPosition, bpm: float, beats_per_bar: int = BEATS_PER_BAR) -> float:
    return ((position.bar - 1) * beats_per_bar + (position.beat - 1)) * 60.0 / bpm


def compile_performance_recipe(recipe: PerformanceRecipe, context: RecipeCompileContext) -> CompiledPerformanceRecipe:
    """Compile typed musical actions into the stable renderer-facing contract."""
    recipe = recipe.with_deterministic_ids()
    require_valid_performance_recipe(recipe, context)
    clock_bpm = context.bpm_for(recipe.clock_role)
    recipe_duration = recipe.bars * context.beats_per_bar * 60.0 / clock_bpm
    overlap = recipe_duration
    source_end = context.source_segment_end_sec
    source_start = source_end - overlap
    target_start = context.target_segment_start_sec
    target_end = target_start + overlap

    transition_type = {
        "eq_blend": "beatmatched_blend",
        "bass_swap": "bass_swap",
        "filter_blend": "filter_sweep",
        "phrase_cut": "phrase_cut",
        "echo_release": "echo_out",
        "reverb_wash": "crossfade",
        "loop_transition": "loop_blend",
        "loop_shortening": "crossfade",
        "drum_overlay": "crossfade",
        "riser_impact": "crossfade",
        "tempo_reset": "echo_out",
        "stem_handoff": "mashup",
    }[recipe.technique]

    schedule = tuple({
        "action_id": action.action_id,
        "action": action.action.value,
        "track_role": action.track_role.value,
        "time_sec": round(_position_seconds(action.position, clock_bpm, context.beats_per_bar), 6),
        "end_time_sec": round(_position_seconds(action.position, clock_bpm, context.beats_per_bar) + action.duration_beats * 60.0 / clock_bpm, 6),
        "position": action.position.to_dict(),
        "duration_beats": action.duration_beats,
        "quantization": action.quantization.value,
        "order": action.order,
        "parameters": _canonicalize(action.parameters),
    } for action in recipe.actions)

    preparation_operations: list[dict[str, Any]] = []
    technique_operations: list[dict[str, Any]] = []
    preparation_duration = 0.0
    if recipe.technique == "reverb_wash":
        technique_operations.append({"type": "reverb_wash", "wet": 0.28, "decay_sec": 1.4})
    elif recipe.technique == "loop_shortening":
        technique_operations.append({"type": "loop_shorten", "sequence": [4.0, 2.0, 1.0]})
    elif recipe.technique == "drum_overlay":
        preparation_duration = min(recipe_duration * 0.5, context.beats_per_bar * 60.0 / clock_bpm)
        preparation_operations.append({"type": "target_percussion_tease"})
    elif recipe.technique == "riser_impact":
        technique_operations.append({"type": "riser_impact", "level": 0.02, "seed": 23})
    elif recipe.technique == "tempo_reset":
        technique_operations.append({"type": "tape_stop", "strength": 0.72})

    requires_stretch = (
        transition_type == "beatmatched_blend"
        and abs(context.source_bpm - context.target_bpm) > 0.5
    )
    target_consumed = (
        overlap * context.source_bpm / context.target_bpm
        if requires_stretch else overlap
    )

    return CompiledPerformanceRecipe(
        recipe=recipe,
        transition_type=transition_type,
        clock_bpm=round(clock_bpm, 6),
        recipe_duration_sec=round(recipe_duration, 6),
        overlap_duration_sec=round(overlap, 6),
        source_start_sec=round(source_start, 6),
        source_end_sec=round(source_end, 6),
        target_start_sec=round(target_start, 6),
        target_end_sec=round(target_end, 6),
        requires_stretch=requires_stretch,
        target_consumed_duration_sec=round(target_consumed, 6),
        action_schedule=schedule,
        preparation_operations=tuple(preparation_operations),
        technique_operations=tuple(technique_operations),
        preparation_duration_sec=round(preparation_duration, 6),
    )


def compiled_recipe_to_transition(compiled: CompiledPerformanceRecipe, context: RecipeCompileContext):
    """Create a backward-compatible PerformanceTransition from a V2 recipe."""
    from djenius.core.models import PerformanceTransition, TransitionType

    return PerformanceTransition(
        source_appearance_id=context.source_appearance_id,
        target_appearance_id=context.target_appearance_id,
        transition_type=TransitionType(compiled.transition_type),
        overlap_duration_sec=compiled.overlap_duration_sec,
        source_start_sec=compiled.source_start_sec,
        source_end_sec=compiled.source_end_sec,
        target_start_sec=compiled.target_start_sec,
        target_end_sec=compiled.target_end_sec,
        length_bars=compiled.recipe.bars,
        requires_stretch=compiled.requires_stretch,
        target_consumed_duration_sec=compiled.target_consumed_duration_sec,
        confidence=1.0,
        technical_score=1.0,
        explanation=f"Compiled from V2 {compiled.recipe.technique} recipe {compiled.recipe.recipe_id}.",
        technique_name=compiled.recipe.technique.replace("_", " "),
        technique_confidence=1.0,
        technique_reason="typed V2 musical-time performance recipe",
        technique_operations=[dict(item) for item in compiled.technique_operations],
        preparation_duration_sec=compiled.preparation_duration_sec,
        preparation_operations=[dict(item) for item in compiled.preparation_operations],
        landing_operations=[dict(item) for item in compiled.landing_operations],
        performance_recipe=compiled.recipe.to_dict(),
        recipe_action_schedule=[dict(item) for item in compiled.action_schedule],
        execution_directive={
            "recipe_id": compiled.recipe.recipe_id,
            "recipe_schema": compiled.recipe.schema_version,
            "compiler": (
                "v2_phase2_legacy_transition_adapter"
                if int(compiled.recipe.metadata.get("phase", 2)) <= 2
                else "v2_phase3_core_technique_adapter"
            ),
            "clock_bpm": compiled.clock_bpm,
            "recipe_duration_sec": compiled.recipe_duration_sec,
        },
    )


def _action(action: ActionType, bar: int, beat: int, role: TrackRole, *, order: int = 0, duration_beats: float = 0.0, quantization: Quantization = Quantization.BEAT, **parameters: Any) -> RecipeAction:
    return RecipeAction(action=action, position=MusicalPosition(bar=bar, beat=beat), track_role=role, parameters=parameters, duration_beats=duration_beats, quantization=quantization, order=order)


def proof_recipe(technique: str, source_track_id: str, target_track_id: str, *, bars: int = 4) -> PerformanceRecipe:
    """Return one deterministic Phase-2 proof recipe for the five gate techniques."""
    if bars < 2:
        raise ValueError("proof recipes require at least two bars")
    last = bars
    mid = max(2, (bars + 1) // 2)
    if technique == "eq_blend":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, order=0, gain_db=-12.0),
            _action(ActionType.EQ_LOW, 1, 1, TrackRole.TARGET, order=1, gain_db=-24.0),
            _action(ActionType.GAIN, mid, 1, TrackRole.TARGET, gain_db=-4.0),
            _action(ActionType.EQ_LOW, last, 1, TrackRole.SOURCE, order=0, gain_db=-24.0),
            _action(ActionType.EQ_LOW, last, 1, TrackRole.TARGET, order=1, gain_db=0.0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE),
        )
    elif technique == "bass_swap":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-10.0),
            _action(ActionType.EQ_LOW, 1, 1, TrackRole.TARGET, order=1, gain_db=-24.0),
            _action(ActionType.EQ_LOW, mid, 1, TrackRole.SOURCE, order=0, gain_db=-24.0),
            _action(ActionType.EQ_LOW, mid, 1, TrackRole.TARGET, order=1, gain_db=0.0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE),
        )
    elif technique == "phrase_cut":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-60.0),
            _action(ActionType.RELEASE, last, 1, TrackRole.SOURCE, order=0, quantization=Quantization.BAR),
            _action(ActionType.GAIN, last, 1, TrackRole.TARGET, order=1, gain_db=0.0, quantization=Quantization.BAR),
        )
    elif technique == "loop_transition":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-12.0),
            _action(ActionType.LOOP_START, mid, 1, TrackRole.SOURCE, order=0, length_beats=4.0),
            _action(ActionType.LOOP_LENGTH, last, 1, TrackRole.SOURCE, order=1, length_beats=2.0),
            _action(ActionType.LOOP_END, last, 4, TrackRole.SOURCE, order=0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE, order=1),
        )
    elif technique == "echo_release":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-10.0),
            _action(ActionType.ECHO, last, 1, TrackRole.SOURCE, wet=0.28, feedback=0.42, duration_beats=4.0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE),
        )
    else:
        raise ValueError(f"unsupported proof technique: {technique}")
    return PerformanceRecipe(
        technique=technique,
        source_track_id=source_track_id,
        target_track_id=target_track_id,
        bars=bars,
        actions=tuple(sorted(actions, key=_action_sort_key)),
        metadata={"phase": 2, "purpose": "initial_proof"},
    ).with_deterministic_ids()


def phase3_recipe(technique: str, source_track_id: str, target_track_id: str, *, bars: int = 4) -> PerformanceRecipe:
    """Build one typed recipe for each required Phase 3 core technique."""
    if technique in PHASE2_TECHNIQUES:
        return proof_recipe(technique, source_track_id, target_track_id, bars=bars)
    if bars < 2:
        raise ValueError("Phase 3 recipes require at least two bars")
    last = bars
    mid = max(2, (bars + 1) // 2)
    if technique == "filter_blend":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-10.0),
            _action(ActionType.FILTER_HP, 1, 1, TrackRole.SOURCE, cutoff_hz=40.0, resonance=0.15),
            _action(ActionType.FILTER_HP, last, 1, TrackRole.SOURCE, cutoff_hz=6000.0, resonance=0.20),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE),
        )
    elif technique == "reverb_wash":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-10.0),
            _action(ActionType.REVERB, mid, 1, TrackRole.SOURCE, wet=0.28, decay_sec=1.4, duration_beats=4.0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE),
        )
    elif technique == "loop_shortening":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-12.0),
            _action(ActionType.LOOP_START, mid, 1, TrackRole.SOURCE, order=0, length_beats=4.0),
            _action(ActionType.LOOP_LENGTH, last, 1, TrackRole.SOURCE, order=1, length_beats=2.0),
            _action(ActionType.LOOP_LENGTH, last, 3, TrackRole.SOURCE, order=0, length_beats=1.0),
            _action(ActionType.LOOP_END, last, 4, TrackRole.SOURCE, order=0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE, order=1),
        )
    elif technique == "drum_overlay":
        actions = (
            _action(ActionType.STEM_GAIN, 1, 1, TrackRole.TARGET, stem="drums", gain_db=-12.0),
            _action(ActionType.START, mid, 1, TrackRole.TARGET, gain_db=-8.0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE),
        )
    elif technique == "riser_impact":
        actions = (
            _action(ActionType.START, 1, 1, TrackRole.TARGET, gain_db=-10.0),
            _action(ActionType.RISER, mid, 1, TrackRole.GENERATED, level=0.018, duration_beats=4.0),
            _action(ActionType.IMPACT, last, 4, TrackRole.GENERATED, level=0.02),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE, order=1),
        )
    elif technique == "tempo_reset":
        actions = (
            _action(ActionType.RELEASE, mid, 1, TrackRole.SOURCE),
            _action(ActionType.START, last, 1, TrackRole.TARGET, gain_db=0.0, quantization=Quantization.BAR),
        )
    elif technique == "stem_handoff":
        actions = (
            _action(ActionType.STEM_SOLO, 1, 1, TrackRole.SOURCE, stem="vocals"),
            _action(ActionType.STEM_GAIN, 1, 1, TrackRole.TARGET, order=1, stem="drums", gain_db=-4.0),
            _action(ActionType.STEM_GAIN, 1, 1, TrackRole.TARGET, order=2, stem="bass", gain_db=-6.0),
            _action(ActionType.STEM_GAIN, 1, 1, TrackRole.TARGET, order=3, stem="other", gain_db=-6.0),
            _action(ActionType.RELEASE, last, 4, TrackRole.SOURCE),
        )
    else:
        raise ValueError(f"unsupported Phase 3 technique: {technique}")
    return PerformanceRecipe(
        technique=technique, source_track_id=source_track_id, target_track_id=target_track_id,
        bars=bars, actions=tuple(sorted(actions, key=_action_sort_key)),
        metadata={"phase": 3, "purpose": "core_technique"},
    ).with_deterministic_ids()
