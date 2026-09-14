"""Reference-backed, explicitly selected DJ performance templates.

This layer deliberately does not choose an archetype.  It converts one named,
human-approved choreography into a deterministic :class:`PerformanceRecipe`
and analysis-derived source/target anchors.  Candidate Composer and Set
Director integration remain a later human-gated step.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any

import numpy as np

from djenius.core.models import TrackAnalysis
from djenius.core.performance_recipe import (
    ActionType,
    MusicalPosition,
    PerformanceRecipe,
    Quantization,
    RecipeAction,
    TrackRole,
)


REFERENCE_TEMPLATE_SCHEMA_VERSION = "1.0"
REQUIRED_STEMS = frozenset({"drums", "bass", "other", "vocals"})


class ReferenceArchetype(str, Enum):
    RESET_RELEASE = "reset_release"
    STEM_ECHO_HANDOFF = "stem_echo_handoff"
    LOOP_BUILD_COHERENT_HANDOFF = "loop_build_coherent_handoff"
    RESTRAINED_OWNERSHIP_BLEND = "restrained_ownership_blend"


class ReferenceTemplateEligibilityError(ValueError):
    """Raised when an explicitly requested archetype is unsafe for the pair."""


@dataclass(frozen=True)
class ArchetypeDefinition:
    archetype: ReferenceArchetype
    reference_label: str
    technique: str
    transition_bars: int
    postlanding_bars: int
    suitable_source_sections: tuple[str, ...]
    suitable_target_sections: tuple[str, ...]
    bpm_relationship: str
    max_tempo_delta_pct: float | None
    min_bpm_confidence: float
    min_analysis_confidence: float
    vocal_requirements: tuple[str, ...]
    required_source_stems: tuple[str, ...]
    required_target_stems: tuple[str, ...]
    target_cue_requirements: tuple[str, ...]
    entry_timing: str
    source_side_actions: tuple[str, ...]
    shared_territory_actions: tuple[str, ...]
    bass_ownership: str
    target_reveal_sequence: tuple[str, ...]
    source_release: str
    post_release_tail: str
    landing_behavior: str
    target_establishment: str
    failure_conditions: tuple[str, ...]
    variable_parameters: tuple[str, ...]
    fixed_parameters: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["archetype"] = self.archetype.value
        return result


ARCHETYPE_DEFINITIONS: dict[ReferenceArchetype, ArchetypeDefinition] = {
    ReferenceArchetype.RESET_RELEASE: ArchetypeDefinition(
        archetype=ReferenceArchetype.RESET_RELEASE,
        reference_label="REFERENCE_F",
        technique="echo_release",
        transition_bars=4,
        postlanding_bars=8,
        suitable_source_sections=("bridge", "build", "drop", "outro"),
        suitable_target_sections=("intro", "verse"),
        bpm_relationship="large or incompatible tempo relationship; no forced beatmatch",
        max_tempo_delta_pct=None,
        min_bpm_confidence=.80,
        min_analysis_confidence=.75,
        vocal_requirements=("usable source-vocal capture in the final source bar", "target pickup may be vocal but must begin sparsely"),
        required_source_stems=("vocals",),
        required_target_stems=(),
        target_cue_requirements=("one natural target pickup bar", "adjacent target master at landing", "clear phrase/section entrance"),
        entry_timing="four intact source bars, then one natural target pickup/reset bar",
        source_side_actions=("play intact source phrase", "80 ms release", "capture final-bar vocal fragment"),
        shared_territory_actions=("filtered/diffused vocal taps decay over a single target-context fade",),
        bass_ownership="source until release; deliberate reset space; target at landing",
        target_reveal_sequence=("target pickup fades from silence to unity", "adjacent full master lands"),
        source_release="dry source reaches zero before reset completes",
        post_release_tail="five bounded vocal-echo taps; final tap must end before landing",
        landing_behavior="clean adjacent-master entrance after the reset",
        target_establishment="at least four postlanding target bars; default eight",
        failure_conditions=("no source vocal stem", "no one-bar target pickup", "target pickup and landing are non-adjacent", "tail reaches landing"),
        variable_parameters=("capture position within final source bar", "tap damping", "target trim within safe loudness bounds"),
        fixed_parameters=("sequential source-then-reset story", "one pickup bar", "five decreasing taps", "tail clears before landing"),
    ),
    ReferenceArchetype.STEM_ECHO_HANDOFF: ArchetypeDefinition(
        archetype=ReferenceArchetype.STEM_ECHO_HANDOFF,
        reference_label="REFERENCE_C3",
        technique="stem_handoff",
        transition_bars=8,
        postlanding_bars=8,
        suitable_source_sections=("verse", "build", "drop", "outro"),
        suitable_target_sections=("intro", "drop"),
        bpm_relationship="beatmatchable, normally within 12 percent",
        max_tempo_delta_pct=12.0,
        min_bpm_confidence=.85,
        min_analysis_confidence=.80,
        vocal_requirements=("source vocal available for a late capture", "target vocal withheld until landing"),
        required_source_stems=("drums", "other", "vocals"),
        required_target_stems=("drums", "other", "vocals"),
        target_cue_requirements=("stable four-bar drum phrase", "strong landing cue", "coherent intro-to-body target clock"),
        entry_timing="target drum air begins immediately; bass changes owner at transition midpoint",
        source_side_actions=("release drums, other, vocal, and low end sequentially", "capture vocal before dry release"),
        shared_territory_actions=("four-bar target drums establish groove", "filtered vocal taps bridge the late handoff"),
        bass_ownership="source through bar 4; target from bar 5",
        target_reveal_sequence=("drum rhythm", "low end", "upper context", "full master at landing"),
        source_release="dry source is gone before the final echo sequence",
        post_release_tail="four damped/diffused taps; final tap ends before landing",
        landing_behavior="target already owns rhythm and bass before full reveal",
        target_establishment="full target for at least four bars; default eight",
        failure_conditions=("missing stems", "tempo delta above safe range", "weak target drum phrase", "source and target vocals overlap"),
        variable_parameters=("capture location", "echo cutoffs", "small target gain trim"),
        fixed_parameters=("eight bars", "four-bar drum phrase", "midpoint bass handoff", "target vocal withheld", "echo clears before landing"),
    ),
    ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF: ArchetypeDefinition(
        archetype=ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
        reference_label="B8_RESIDUAL_FIX",
        technique="loop_shortening",
        transition_bars=8,
        postlanding_bars=8,
        suitable_source_sections=("build", "drop", "outro"),
        suitable_target_sections=("intro", "drop"),
        bpm_relationship="beatmatchable, normally within 12 percent",
        max_tempo_delta_pct=12.0,
        min_bpm_confidence=.85,
        min_analysis_confidence=.80,
        vocal_requirements=("source vocal stem available to remove from loop capture", "target vocal onset measurable for tail bound"),
        required_source_stems=("vocals",),
        required_target_stems=("drums", "other", "vocals"),
        target_cue_requirements=("strong sustained landing bar", "stable two-bar low cadence", "coherent intro-to-body target clock"),
        entry_timing="target air/context precedes body; source loop begins at bar 5; target low arrives late",
        source_side_actions=("release dry source", "shorten one captured motif 4 beats to 2 to 1", "two-bar riser"),
        shared_territory_actions=("target rhythm/identity rises behind one uninterrupted loop state", "riser residue crosses landing"),
        bass_ownership="source through bar 4; target owns bass from late bar 6 onward",
        target_reveal_sequence=("air/high context", "drum body and identity", "low end", "full master at landing"),
        source_release="dry source clears early; loop state crosses landing without restart",
        post_release_tail="rhythmic tail and airy riser residue end before first target vocal",
        landing_behavior="full target appears on cue with shared stretch map and no false prelanding bass pocket",
        target_establishment="full target for at least four bars; default eight",
        failure_conditions=("missing stems", "tempo delta above safe range", "no vocal onset bound", "unstable two-bar target low cadence", "tail overlaps target vocal"),
        variable_parameters=("loop capture bar", "safe target trim", "tail endpoint before measured target vocal"),
        fixed_parameters=("eight bars", "4/2/1-beat sequence", "two-bar low preview", "shared target time map", "bounded stateful tail"),
    ),
    ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND: ArchetypeDefinition(
        archetype=ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND,
        reference_label="REFERENCE_D2",
        technique="eq_blend",
        transition_bars=12,
        postlanding_bars=8,
        suitable_source_sections=("verse", "outro"),
        suitable_target_sections=("intro", "build", "verse"),
        bpm_relationship="close/beatmatchable, normally within 8 percent",
        max_tempo_delta_pct=8.0,
        min_bpm_confidence=.85,
        min_analysis_confidence=.80,
        vocal_requirements=("source and target vocals have a sequential handoff",),
        required_source_stems=("vocals",),
        required_target_stems=("drums", "other", "vocals"),
        target_cue_requirements=("long coherent runway", "real bass and drum material available at landing"),
        entry_timing="target highs/mids develop gradually; bass and drums wait until bars 9-10",
        source_side_actions=("retain source bass for eight bars", "release source bands and vocal on separate ramps"),
        shared_territory_actions=("long upper-band blend", "one explicit late bass transfer", "target drums/vocal follow bass"),
        bass_ownership="source through bar 8; half-bar transfer; target thereafter",
        target_reveal_sequence=("highs", "mids", "bass", "drums", "vocal", "full master"),
        source_release="source bands reach zero progressively by landing",
        post_release_tail="none; this archetype relies on continuous ownership ramps",
        landing_behavior="restrained completion of an already-established target",
        target_establishment="full target for at least four bars; default eight",
        failure_conditions=("missing stems", "tempo delta above safe range", "target runway too short", "simultaneous vocal ownership"),
        variable_parameters=("safe deck trim", "minor band-ramp offsets", "12-to-16-bar phrase length after future human validation"),
        fixed_parameters=("source bass held eight bars", "late bass-before-drums sequence", "sequential vocal handoff", "no decorative FX"),
    ),
}


@dataclass(frozen=True)
class TemplateAnchors:
    source_start_sec: float
    source_end_sec: float
    target_runway_start_sec: float
    target_landing_sec: float
    target_post_end_sec: float
    source_start_bar_index: int
    source_end_bar_index: int
    target_runway_bar_index: int
    target_landing_bar_index: int
    target_post_end_bar_index: int
    source_section: str
    target_runway_section: str
    target_landing_section: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReferenceTemplateInstance:
    archetype: ReferenceArchetype
    recipe: PerformanceRecipe
    anchors: TemplateAnchors
    definition: ArchetypeDefinition
    eligibility: dict[str, Any]
    choreography: dict[str, Any]
    instance_id: str
    schema_version: str = REFERENCE_TEMPLATE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "instance_id": self.instance_id,
            "archetype": self.archetype.value,
            "recipe": self.recipe.to_dict(),
            "anchors": self.anchors.to_dict(),
            "definition": self.definition.to_dict(),
            "eligibility": self.eligibility,
            "choreography": self.choreography,
        }


def _grid(analysis: TrackAnalysis) -> np.ndarray:
    values = analysis.downbeat_times or analysis.bar_times
    grid = np.asarray(values, dtype=float)
    if len(grid) < 3 or np.any(np.diff(grid) <= 0):
        raise ReferenceTemplateEligibilityError("archetype requires a stable ordered downbeat grid")
    return grid


def _section_at(analysis: TrackAnalysis, time_sec: float) -> str:
    for section in analysis.section_profiles:
        if float(section.get("start_sec", 0.0)) <= time_sec < float(section.get("end_sec", 0.0)):
            return str(section.get("label", "unknown"))
    for start, end, label in analysis.structural_sections:
        if float(start) <= time_sec < float(end):
            return str(label)
    return "unknown"


def _vocal_coverage(analysis: TrackAnalysis, start: float, end: float) -> float:
    if end <= start:
        return 0.0
    covered = sum(
        max(0.0, min(end, float(right)) - max(start, float(left)))
        for left, right in analysis.vocal_regions
    )
    return max(0.0, min(1.0, covered / (end - start)))


def _source_window(analysis: TrackAnalysis, bars: int, reset: bool) -> tuple[int, int]:
    grid = _grid(analysis)
    energetic_outros = [
        section for section in analysis.section_profiles
        if str(section.get("label", "")) == "outro" and float(section.get("energy_mean", 0.0)) >= .5
    ]
    if reset:
        quiet_outros = [
            section for section in analysis.section_profiles
            if str(section.get("label", "")) == "outro" and float(section.get("energy_mean", 1.0)) < .5
        ]
        if quiet_outros:
            boundary = float(quiet_outros[0]["start_sec"])
            end_index = max(1, int(np.searchsorted(grid, boundary, side="left") - 1))
            if end_index - bars >= 0:
                return end_index - bars, end_index
    if energetic_outros:
        boundary = float(energetic_outros[0]["start_sec"])
        start_index = int(np.argmin(np.abs(grid - boundary)))
        if start_index + bars < len(grid):
            return start_index, start_index + bars
    # Deterministic fallback: use the latest complete phrase whose first bar
    # is locally energetic, never an arbitrary second timestamp.
    energies = analysis.bar_energies
    candidates = range(0, len(grid) - bars)
    start_index = max(candidates, key=lambda index: (energies[index] if index < len(energies) else 0.0, index))
    return start_index, start_index + bars


def _first_section(analysis: TrackAnalysis, labels: tuple[str, ...], *, exclude_intro: bool = False) -> dict[str, Any]:
    for section in analysis.section_profiles:
        label = str(section.get("label", "unknown"))
        if (not exclude_intro or label != "intro") and label in labels:
            return section
    raise ReferenceTemplateEligibilityError(f"target has no suitable section in {','.join(labels)}")


def _target_landing_index(analysis: TrackAnalysis, archetype: ReferenceArchetype) -> int:
    grid = _grid(analysis)
    if archetype == ReferenceArchetype.RESET_RELEASE:
        section = _first_section(analysis, ("verse", "build", "drop", "bridge", "chorus"), exclude_intro=True)
        return int(np.argmin(np.abs(grid - float(section["start_sec"]))))
    if archetype == ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND:
        section = _first_section(analysis, ("build", "verse", "bridge", "drop"), exclude_intro=True)
        return int(np.argmin(np.abs(grid - float(section["start_sec"]))))

    section = _first_section(analysis, ("drop", "chorus"))
    start, end = float(section["start_sec"]), float(section["end_sec"])
    indexes = [index for index, value in enumerate(grid[:-1]) if start - .25 <= value < end]
    if not indexes:
        raise ReferenceTemplateEligibilityError("target drop has no downbeat")
    early = indexes[:4]
    section_energy = float(section.get("energy_mean", 0.0))
    threshold = max(.72, section_energy * .84)
    for index in early:
        energy = analysis.bar_energies[index] if index < len(analysis.bar_energies) else 0.0
        vocal = _vocal_coverage(analysis, float(grid[index]), float(grid[index + 1]))
        if energy >= threshold and vocal <= .80:
            return index
    return max(
        early,
        key=lambda index: (
            analysis.bar_energies[index] if index < len(analysis.bar_energies) else 0.0,
            -_vocal_coverage(analysis, float(grid[index]), float(grid[index + 1])),
            -index,
        ),
    )


def _position(bar_axis: float, bars: int) -> MusicalPosition:
    sixteenth = round(float(bar_axis) * 16.0) / 16.0
    sixteenth = max(0.0, min(sixteenth, bars - 1 / 16))
    whole_beat = int(sixteenth * 4)
    fraction = sixteenth * 4 - whole_beat
    subdivision = int(round(fraction * 4))
    if subdivision == 4:
        whole_beat += 1
        subdivision = 0
    return MusicalPosition(
        bar=whole_beat // 4 + 1,
        beat=whole_beat % 4 + 1,
        subdivision=subdivision,
        subdivisions_per_beat=4,
    )


def _recipe_action(
    action: ActionType,
    bar_axis: float,
    bars: int,
    role: TrackRole,
    *,
    order: int = 0,
    duration_beats: float = 0.0,
    **parameters: Any,
) -> RecipeAction:
    return RecipeAction(
        action=action,
        position=_position(bar_axis, bars),
        track_role=role,
        parameters=parameters,
        duration_beats=duration_beats,
        quantization=Quantization.SIXTEENTH,
        order=order,
    )


def _recipe_actions(archetype: ReferenceArchetype, bars: int) -> tuple[RecipeAction, ...]:
    a = _recipe_action
    if archetype == ReferenceArchetype.RESET_RELEASE:
        actions = (
            a(ActionType.START, 0, bars, TrackRole.SOURCE, gain_db=0.0),
            a(ActionType.ECHO, 3.0, bars, TrackRole.SOURCE, wet=.62, feedback=.43, duration_beats=4.0),
            a(ActionType.FADE, 3.875, bars, TrackRole.SOURCE, gain_db=-60.0),
            a(ActionType.START, 3.9375, bars, TrackRole.TARGET, order=1, gain_db=-60.0),
            a(ActionType.RELEASE, 3.9375, bars, TrackRole.SOURCE, order=2),
        )
    elif archetype == ReferenceArchetype.STEM_ECHO_HANDOFF:
        actions = (
            a(ActionType.STEM_GAIN, 0, bars, TrackRole.TARGET, stem="drums", gain_db=-26.0),
            a(ActionType.EQ_LOW, 4.0, bars, TrackRole.SOURCE, gain_db=-60.0),
            a(ActionType.STEM_GAIN, 4.5, bars, TrackRole.TARGET, order=1, stem="bass", gain_db=0.0),
            a(ActionType.STEM_MUTE, 4.6, bars, TrackRole.SOURCE, stem="drums"),
            a(ActionType.STEM_MUTE, 5.3, bars, TrackRole.SOURCE, stem="other"),
            a(ActionType.ECHO, 6.92, bars, TrackRole.SOURCE, wet=.54, feedback=.0, duration_beats=1.2),
            a(ActionType.STEM_MUTE, 6.88, bars, TrackRole.SOURCE, stem="vocals"),
            a(ActionType.RELEASE, 7.94, bars, TrackRole.SOURCE),
        )
    elif archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        actions = (
            a(ActionType.START, 0, bars, TrackRole.TARGET, gain_db=-34.0),
            a(ActionType.LOOP_START, 4.0, bars, TrackRole.SOURCE, length_beats=4.0),
            a(ActionType.LOOP_LENGTH, 6.0, bars, TrackRole.SOURCE, length_beats=2.0),
            a(ActionType.RISER, 6.35, bars, TrackRole.GENERATED, duration_beats=6.5, level=.05, gain_db=-2.5),
            a(ActionType.LOOP_LENGTH, 7.0, bars, TrackRole.SOURCE, length_beats=1.0),
            a(ActionType.EQ_LOW, 5.3, bars, TrackRole.TARGET, gain_db=-60.0),
            a(ActionType.EQ_LOW, 5.65, bars, TrackRole.TARGET, gain_db=-12.4),
            a(ActionType.LOOP_END, 7.9375, bars, TrackRole.SOURCE),
            a(ActionType.RELEASE, 7.9375, bars, TrackRole.SOURCE, order=1),
        )
    else:
        actions = (
            a(ActionType.START, 0, bars, TrackRole.TARGET, gain_db=-30.5),
            a(ActionType.EQ_HIGH, 3.0, bars, TrackRole.SOURCE, gain_db=-1.0),
            a(ActionType.EQ_LOW, 8.0, bars, TrackRole.SOURCE, gain_db=0.0),
            a(ActionType.EQ_LOW, 8.5, bars, TrackRole.SOURCE, gain_db=-60.0),
            a(ActionType.EQ_LOW, 8.5, bars, TrackRole.TARGET, order=1, gain_db=-.35),
            a(ActionType.STEM_GAIN, 9.3, bars, TrackRole.TARGET, stem="drums", gain_db=-8.4),
            a(ActionType.STEM_MUTE, 9.35, bars, TrackRole.SOURCE, stem="vocals"),
            a(ActionType.STEM_GAIN, 9.4, bars, TrackRole.TARGET, order=1, stem="vocals", gain_db=-16.5),
            a(ActionType.RELEASE, 11.9375, bars, TrackRole.SOURCE),
        )
    return tuple(sorted(actions, key=lambda item: (item.position.beat_offset, item.order, item.action.value)))


def _choreography(archetype: ReferenceArchetype) -> dict[str, Any]:
    if archetype == ReferenceArchetype.RESET_RELEASE:
        return {
            "source_active_bars": 4,
            "target_reset_bars": 1,
            "target_stream": "adjacent_natural_master",
            "bass_ownership": ((0.0, 4.0, "source"), (4.0, 5.0, "reset_to_target")),
            "tail": {"kind": "vocal_echo", "taps": 5, "must_end_before_landing": True},
            "target_establishment_bars": 8,
        }
    if archetype == ReferenceArchetype.STEM_ECHO_HANDOFF:
        return {
            "transition_bars": 8,
            "target_stream": "single_coherent_runway_and_body_time_map",
            "bass_ownership": ((0.0, 4.0, "source"), (4.0, 4.5, "handoff"), (4.5, 8.0, "target")),
            "target_vocal_before_landing": False,
            "tail": {"kind": "four_damped_vocal_taps", "must_end_before_landing": True},
            "target_establishment_bars": 8,
        }
    if archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        return {
            "transition_bars": 8,
            "target_stream": "single_coherent_runway_and_body_time_map",
            "loop_lengths_beats": (4.0, 2.0, 1.0),
            "target_low_preview_bars": 2,
            "bass_ownership": ((0.0, 4.0, "source"), (4.0, 5.65, "none_or_target_tease"), (5.65, 8.0, "target")),
            "tail": {"kind": "rhythmic_plus_airy_release", "must_end_before_target_vocal": True, "margin_sec": .020},
            "target_establishment_bars": 8,
        }
    return {
        "transition_bars": 12,
        "target_stream": "single_coherent_runway_and_body_time_map",
        "bass_ownership": ((0.0, 8.0, "source"), (8.0, 8.5, "handoff"), (8.5, 12.0, "target")),
        "tail": {"kind": "none"},
        "target_establishment_bars": 8,
    }


def instantiate_reference_template(
    source: TrackAnalysis,
    target: TrackAnalysis,
    archetype: ReferenceArchetype | str,
    *,
    source_track_id: str,
    target_track_id: str,
    source_duration_sec: float,
    target_duration_sec: float,
) -> ReferenceTemplateInstance:
    """Instantiate one explicitly requested reference-backed performance.

    Cue selection is derived only from analysis sections, downbeats, bar
    energy, and vocal regions.  Absolute reference timestamps are not stored
    in this module.
    """
    archetype = ReferenceArchetype(archetype)
    definition = ARCHETYPE_DEFINITIONS[archetype]
    if source_track_id == target_track_id or not source_track_id or not target_track_id:
        raise ReferenceTemplateEligibilityError("templates require two distinct track ids")
    failures: list[str] = []
    for role, analysis in (("source", source), ("target", target)):
        if analysis.analysis_confidence < definition.min_analysis_confidence:
            failures.append(f"{role} analysis confidence below {definition.min_analysis_confidence:.2f}")
        if analysis.bpm_confidence < definition.min_bpm_confidence:
            failures.append(f"{role} beatgrid confidence below {definition.min_bpm_confidence:.2f}")
        if analysis.bpm <= 0:
            failures.append(f"{role} BPM unavailable")
    tempo_delta = abs(source.bpm - target.bpm) / max(min(source.bpm, target.bpm), 1e-9) * 100.0
    if definition.max_tempo_delta_pct is not None and tempo_delta > definition.max_tempo_delta_pct:
        failures.append(f"tempo delta {tempo_delta:.2f}% exceeds {definition.max_tempo_delta_pct:.2f}%")
    for role, analysis, required in (
        ("source", source, definition.required_source_stems),
        ("target", target, definition.required_target_stems),
    ):
        available = set((analysis.stems or {}).keys())
        missing = set(required) - available
        if missing:
            failures.append(f"{role} stems missing: {','.join(sorted(missing))}")
    if failures:
        raise ReferenceTemplateEligibilityError("; ".join(failures))

    source_grid, target_grid = _grid(source), _grid(target)
    source_start_index, source_end_index = _source_window(
        source, definition.transition_bars, archetype == ReferenceArchetype.RESET_RELEASE,
    )
    landing_index = _target_landing_index(target, archetype)
    runway_bars = 1 if archetype == ReferenceArchetype.RESET_RELEASE else definition.transition_bars
    runway_index = landing_index - runway_bars
    post_index = landing_index + definition.postlanding_bars
    if runway_index < 0 or post_index >= len(target_grid):
        raise ReferenceTemplateEligibilityError("target does not contain the required runway/body bars")
    if source_end_index >= len(source_grid):
        raise ReferenceTemplateEligibilityError("source does not contain the required exit phrase")
    if source_grid[source_end_index] > source_duration_sec + .01 or target_grid[post_index] > target_duration_sec + .01:
        raise ReferenceTemplateEligibilityError("analysis-derived template anchors exceed track duration")

    anchors = TemplateAnchors(
        source_start_sec=round(float(source_grid[source_start_index]), 6),
        source_end_sec=round(float(source_grid[source_end_index]), 6),
        target_runway_start_sec=round(float(target_grid[runway_index]), 6),
        target_landing_sec=round(float(target_grid[landing_index]), 6),
        target_post_end_sec=round(float(target_grid[post_index]), 6),
        source_start_bar_index=source_start_index,
        source_end_bar_index=source_end_index,
        target_runway_bar_index=runway_index,
        target_landing_bar_index=landing_index,
        target_post_end_bar_index=post_index,
        source_section=_section_at(source, float(source_grid[source_start_index])),
        target_runway_section=_section_at(target, float(target_grid[runway_index])),
        target_landing_section=_section_at(target, float(target_grid[landing_index])),
    )
    choreography = _choreography(archetype)
    recipe = PerformanceRecipe(
        technique=definition.technique,
        source_track_id=source_track_id,
        target_track_id=target_track_id,
        bars=definition.transition_bars,
        actions=_recipe_actions(archetype, definition.transition_bars),
        clock_role=TrackRole.SOURCE,
        provenance_version="reference-template-1",
        metadata={
            "phase": 11,
            "purpose": "reference_backed_reproduction",
            "reference_archetype": archetype.value,
            "reference_label": definition.reference_label,
            "template_schema_version": REFERENCE_TEMPLATE_SCHEMA_VERSION,
            "anchors": anchors.to_dict(),
            "choreography": choreography,
            "autonomous_selection_allowed": False,
        },
    ).with_deterministic_ids()
    payload = {
        "schema": REFERENCE_TEMPLATE_SCHEMA_VERSION,
        "archetype": archetype.value,
        "recipe_id": recipe.recipe_id,
        "anchors": anchors.to_dict(),
    }
    instance_id = "rti_" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return ReferenceTemplateInstance(
        archetype=archetype,
        recipe=recipe,
        anchors=anchors,
        definition=definition,
        eligibility={
            "eligible": True,
            "tempo_delta_pct": round(tempo_delta, 4),
            "source_bpm_confidence": round(source.bpm_confidence, 4),
            "target_bpm_confidence": round(target.bpm_confidence, 4),
            "source_analysis_confidence": round(source.analysis_confidence, 4),
            "target_analysis_confidence": round(target.analysis_confidence, 4),
            "required_source_stems": list(definition.required_source_stems),
            "required_target_stems": list(definition.required_target_stems),
        },
        choreography=choreography,
        instance_id=instance_id,
    )


def archetype_catalog() -> dict[str, dict[str, Any]]:
    """Return the explicit template catalog without choosing from it."""
    return {key.value: value.to_dict() for key, value in ARCHETYPE_DEFINITIONS.items()}
