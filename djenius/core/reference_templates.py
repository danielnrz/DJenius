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
from djenius.utils.camelot import score_key_compatibility


REFERENCE_TEMPLATE_SCHEMA_VERSION = "1.2"
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
        suitable_source_sections=("verse", "bridge", "build", "drop", "outro"),
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
        failure_conditions=("no self-contained final-bar vocal/musical unit", "release interrupts a continuing vocal unit", "no one-bar target pickup", "target pickup and landing are non-adjacent", "tail reaches landing"),
        variable_parameters=("analysis-selected four-bar source window", "capture position within final source bar", "tap damping", "target trim within safe loudness bounds"),
        fixed_parameters=("release within 0.75 seconds of the motif vocal boundary", "sequential source-then-reset story", "one pickup bar", "five decreasing taps", "tail clears before landing"),
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
        failure_conditions=("missing stems", "tempo delta above safe range", "weak target drum phrase", "source and target vocals overlap", "dense source plus near-limit tempo/groove change is only borderline"),
        variable_parameters=("capture location", "echo cutoffs", "small target gain trim"),
        fixed_parameters=("eight bars", "four-bar drum phrase", "midpoint bass handoff", "target vocal withheld", "echo clears before landing"),
    ),
    ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF: ArchetypeDefinition(
        archetype=ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
        reference_label="B8_RESIDUAL_FIX",
        technique="loop_shortening",
        transition_bars=8,
        postlanding_bars=8,
        suitable_source_sections=("verse", "build", "drop", "outro"),
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
        failure_conditions=("missing stems", "tempo delta above safe range", "source manipulation interrupts an unpredictable vocal phrase", "no vocal onset bound", "unstable two-bar target low cadence", "tail overlaps target vocal"),
        variable_parameters=("analysis-selected source phrase", "loop capture bar", "safe target trim", "tail endpoint before measured target vocal"),
        fixed_parameters=("source entry uses a vocal gap/phrase end or proven repeated-hook context", "eight bars", "4/2/1-beat sequence", "two-bar low preview", "shared target time map", "bounded stateful tail"),
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
        failure_conditions=("missing stems", "tempo delta above safe range", "target runway too short", "global harmonic compatibility below 0.50", "combined arrangement-density pressure above 1.65", "simultaneous vocal ownership"),
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


@dataclass(frozen=True)
class ReferencePairAssessment:
    """Analysis-only suitability evidence for one explicitly named template.

    ``fit_score`` orders plausible pairs for a bounded human experiment.  It
    is not an audition score and makes no claim about perceptual quality.
    """

    archetype: ReferenceArchetype
    eligible: bool
    fit_score: float
    rejection_reasons: tuple[str, ...]
    cautions: tuple[str, ...]
    selection_reasons: tuple[str, ...]
    evidence: dict[str, Any]
    instance: ReferenceTemplateInstance | None = None

    def to_dict(self, *, include_instance: bool = True) -> dict[str, Any]:
        result = {
            "archetype": self.archetype.value,
            "eligible": self.eligible,
            "fit_score": self.fit_score,
            "rejection_reasons": list(self.rejection_reasons),
            "cautions": list(self.cautions),
            "selection_reasons": list(self.selection_reasons),
            "evidence": self.evidence,
        }
        if include_instance and self.instance is not None:
            result["instance"] = self.instance.to_dict()
        return result


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


def _curve_window_mean(curve: list[float], start: float, end: float, duration: float) -> float:
    """Return a duration-scaled mean for an analysis curve.

    Energy curves are normally one-Hz, but scaling by track duration keeps
    older caches with a different point count usable and deterministic.
    """
    values = np.asarray(curve, dtype=float)
    if not len(values) or duration <= 0 or end <= start:
        return 0.0
    left = max(0, min(len(values) - 1, int(start / duration * len(values))))
    right = max(left + 1, min(len(values), int(np.ceil(end / duration * len(values)))))
    window = np.nan_to_num(values[left:right], nan=0.0, posinf=0.0, neginf=0.0)
    return float(np.mean(window)) if len(window) else 0.0


def _curve_activity_onset(
    curve: list[float],
    start: float,
    end: float,
    duration: float,
) -> float | None:
    """Return a conservative relative onset from a duration-scaled curve.

    This is an analysis proxy, not a stem-transient detector.  It finds the
    first point reaching 60% of the strongest value inside the window.
    """
    values = np.asarray(curve, dtype=float)
    if not len(values) or duration <= 0 or end <= start:
        return None
    left = max(0, min(len(values) - 1, int(start / duration * len(values))))
    right = max(left + 1, min(len(values), int(np.ceil(end / duration * len(values)))))
    window = np.nan_to_num(values[left:right], nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(window)) if len(window) else 0.0
    if peak <= 1e-9:
        return None
    indexes = np.flatnonzero(window >= peak * .60)
    if not len(indexes):
        return None
    absolute_index = left + int(indexes[0])
    return max(0.0, absolute_index / len(values) * duration - start)


def _boundary_distance(values: list[float], time_sec: float) -> float | None:
    return min((abs(float(value) - time_sec) for value in values), default=None)


def _round_optional(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def _vocal_timing(analysis: TrackAnalysis, time_sec: float) -> dict[str, Any]:
    active = next(
        ((float(left), float(right)) for left, right in analysis.vocal_regions if float(left) <= time_sec < float(right)),
        None,
    )
    previous = [time_sec - float(right) for left, right in analysis.vocal_regions if float(right) <= time_sec]
    following = [float(left) - time_sec for left, right in analysis.vocal_regions if float(left) >= time_sec]
    boundaries = [float(value) for region in analysis.vocal_regions for value in region]
    return {
        "vocal_active": active is not None,
        "active_vocal_remaining_sec": max(0.0, active[1] - time_sec) if active else 0.0,
        "distance_since_previous_vocal_sec": min(previous) if previous else None,
        "distance_until_next_vocal_sec": min(following) if following else None,
        "nearest_vocal_boundary_sec": _boundary_distance(boundaries, time_sec),
    }


def _local_descriptor_mean(analysis: TrackAnalysis, field: str, start: float, end: float) -> np.ndarray:
    times = np.asarray(analysis.local_context_times, dtype=float)
    rows = np.asarray(getattr(analysis, field, []), dtype=float)
    if rows.ndim != 2 or not len(times) or len(rows) != len(times):
        return np.array([], dtype=float)
    indexes = (times >= start - 1.0) & (times <= end + 1.0)
    return np.mean(rows[indexes], axis=0) if np.any(indexes) else np.array([], dtype=float)


def _descriptor_similarity(left: np.ndarray, right: np.ndarray, scale: float) -> float:
    if not len(left) or len(left) != len(right):
        return .5
    return float(np.clip(1.0 - np.mean(np.abs(left - right)) / scale, 0.0, 1.0))


def _source_entry_context(
    analysis: TrackAnalysis,
    start_index: int,
    bars: int,
    archetype: ReferenceArchetype,
    duration_sec: float,
) -> dict[str, Any]:
    grid = _grid(analysis)
    effect_axis = {
        ReferenceArchetype.RESET_RELEASE: float(bars),
        ReferenceArchetype.STEM_ECHO_HANDOFF: 6.92,
        ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF: 3.7,
        ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND: 0.0,
    }[archetype]
    effect_time = float(np.interp(start_index + effect_axis, np.arange(len(grid)), grid))
    start_sec, end_sec = float(grid[start_index]), float(grid[start_index + bars])
    entry_bar_end = float(np.interp(start_index + min(effect_axis + 1.0, bars), np.arange(len(grid)), grid))
    timing = _vocal_timing(analysis, effect_time)
    section_start = _section_at(analysis, start_sec)
    section_end = _section_at(analysis, max(start_sec, end_sec - .001))
    section_boundaries = [
        float(value)
        for section in analysis.section_profiles
        for value in (section.get("start_sec", 0.0), section.get("end_sec", duration_sec))
    ]
    evidence: dict[str, Any] = {
        "source_start_bar_index": start_index,
        "source_end_bar_index": start_index + bars,
        "source_start_sec": round(start_sec, 6),
        "source_end_sec": round(end_sec, 6),
        "source_phrase_duration_sec": round(end_sec - start_sec, 6),
        "effect_onset_bar": round(effect_axis, 4),
        "effect_onset_sec": round(effect_time, 6),
        "effect_entry_vocal_coverage": round(_vocal_coverage(analysis, effect_time - .25, effect_time + .25), 4),
        "effect_entry_vocal_activity": round(
            _curve_window_mean(analysis.vocal_activity_curve, effect_time - .5, effect_time + .5, duration_sec), 4,
        ),
        "effect_entry_transient_density": round(
            _curve_window_mean(analysis.rhythmic_density_curve, effect_time - 1.0, entry_bar_end, duration_sec), 4,
        ),
        "effect_entry_energy": round(
            _curve_window_mean(analysis.energy_curve, effect_time - 1.0, entry_bar_end, duration_sec), 4,
        ),
        "effect_entry_bass_ratio": round(
            _curve_window_mean(analysis.low_energy_curve, effect_time - 1.0, entry_bar_end, duration_sec), 4,
        ),
        "source_section_at_start": section_start,
        "source_section_at_effect": _section_at(analysis, effect_time),
        "source_window_section_continuous": section_start == section_end,
        "nearest_section_boundary_sec": _round_optional(_boundary_distance(section_boundaries, effect_time)),
        "nearest_phrase_boundary_sec": _round_optional(_boundary_distance(analysis.phrase_boundaries, effect_time)),
        "source_window_vocal_density": round(_vocal_coverage(analysis, start_sec, end_sec), 4),
    }
    evidence.update({name: round(value, 4) if isinstance(value, float) else value for name, value in timing.items()})
    if archetype == ReferenceArchetype.RESET_RELEASE:
        last_bar_start = float(grid[start_index + bars - 1])
        previous_bar_start = float(grid[max(start_index, start_index + bars - 2)])
        regions = [
            (max(start_sec, float(left)), min(end_sec, float(right)))
            for left, right in analysis.vocal_regions
            if float(right) > start_sec and float(left) < end_sec
        ]
        evidence.update({
            "final_bar_vocal_coverage": round(_vocal_coverage(analysis, last_bar_start, end_sec), 4),
            "vocal_units_intersecting_window": len(regions),
            "largest_vocal_unit_window_coverage": round(
                max((right - left for left, right in regions), default=0.0) / max(end_sec - start_sec, 1e-9), 4,
            ),
            "repeatable_motif_evidence": {
                "ends_near_vocal_boundary": (
                    timing["nearest_vocal_boundary_sec"] is not None
                    and timing["nearest_vocal_boundary_sec"] <= 1.0
                ),
                "final_bar_vocal_coverage": round(
                    _vocal_coverage(analysis, last_bar_start, end_sec), 4,
                ),
                "previous_to_final_rhythm_similarity": round(
                    _descriptor_similarity(
                        _local_descriptor_mean(
                            analysis, "local_rhythm_curve", previous_bar_start, last_bar_start,
                        ),
                        _local_descriptor_mean(
                            analysis, "local_rhythm_curve", last_bar_start, end_sec,
                        ),
                        2.0,
                    ),
                    4,
                ),
                "previous_to_final_spectral_similarity": round(
                    _descriptor_similarity(
                        _local_descriptor_mean(
                            analysis, "local_spectral_curve", previous_bar_start, last_bar_start,
                        ),
                        _local_descriptor_mean(
                            analysis, "local_spectral_curve", last_bar_start, end_sec,
                        ),
                        .7,
                    ),
                    4,
                ),
                "scope": "boundary, vocal coverage, and local descriptor evidence; semantic lyric completeness requires human listening",
            },
        })
    elif archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        motif_start, motif_end = float(grid[start_index + 1]), float(grid[start_index + 2])
        loop_start = float(grid[start_index + 4])
        loop_timing = _vocal_timing(analysis, loop_start)
        entry_end = float(grid[start_index + 5])
        motif_rhythm = _local_descriptor_mean(analysis, "local_rhythm_curve", motif_start, motif_end)
        entry_rhythm = _local_descriptor_mean(analysis, "local_rhythm_curve", loop_start, entry_end)
        motif_spectral = _local_descriptor_mean(analysis, "local_spectral_curve", motif_start, motif_end)
        entry_spectral = _local_descriptor_mean(analysis, "local_spectral_curve", loop_start, entry_end)
        evidence.update({
            "loop_motif_start_sec": round(motif_start, 6),
            "loop_motif_end_sec": round(motif_end, 6),
            "loop_start_sec": round(loop_start, 6),
            "loop_start_vocal_active": loop_timing["vocal_active"],
            "loop_start_distance_until_next_vocal_sec": _round_optional(
                loop_timing["distance_until_next_vocal_sec"],
            ),
            "motif_entry_rhythm_similarity": round(_descriptor_similarity(motif_rhythm, entry_rhythm, 2.0), 4),
            "motif_entry_spectral_similarity": round(_descriptor_similarity(motif_spectral, entry_spectral, .7), 4),
        })
    return evidence


def _f_entry_is_safe(context: dict[str, Any]) -> bool:
    return (
        context["final_bar_vocal_coverage"] >= .25
        and context["active_vocal_remaining_sec"] <= .75
        and context["nearest_vocal_boundary_sec"] is not None
        and context["nearest_vocal_boundary_sec"] <= 1.0
    )


def _b8_entry_modes(context: dict[str, Any]) -> tuple[bool, bool, bool]:
    next_vocal = context["distance_until_next_vocal_sec"]
    clean_gap = not context["vocal_active"] and (next_vocal is None or next_vocal >= .75)
    phrase_end_release = (
        context["vocal_active"]
        and context["active_vocal_remaining_sec"] <= .5
        and not context["loop_start_vocal_active"]
        and (
            context["loop_start_distance_until_next_vocal_sec"] is None
            or context["loop_start_distance_until_next_vocal_sec"] >= .75
        )
    )
    predictable_hook = (
        context["vocal_active"]
        and context["motif_entry_rhythm_similarity"] >= .95
        and (
            context["motif_entry_spectral_similarity"] >= .98
            or (
                context["source_window_section_continuous"]
                and context["motif_entry_spectral_similarity"] >= .93
            )
        )
    )
    return clean_gap, phrase_end_release, predictable_hook


def _refine_source_window(
    analysis: TrackAnalysis,
    bars: int,
    archetype: ReferenceArchetype,
    duration_sec: float,
    requested_start_index: int | None = None,
) -> tuple[int, int, dict[str, Any]]:
    baseline_start, baseline_end = _source_window(
        analysis, bars, archetype == ReferenceArchetype.RESET_RELEASE,
    )
    baseline = _source_entry_context(analysis, baseline_start, bars, archetype, duration_sec)
    if requested_start_index is not None:
        grid = _grid(analysis)
        if requested_start_index < 0 or requested_start_index + bars >= len(grid):
            raise ReferenceTemplateEligibilityError("requested source cue cannot contain the template phrase")
        selected = _source_entry_context(
            analysis, requested_start_index, bars, archetype, duration_sec,
        )
        if archetype == ReferenceArchetype.RESET_RELEASE and not _f_entry_is_safe(selected):
            raise ReferenceTemplateEligibilityError(
                "requested F cue has no complete repeatable motif at its release boundary"
            )
        if (
            archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF
            and not any(_b8_entry_modes(selected))
        ):
            raise ReferenceTemplateEligibilityError(
                "requested B8 cue interrupts an unpredictable active vocal phrase"
            )
        return requested_start_index, requested_start_index + bars, {
            "adjusted": requested_start_index != baseline_start,
            "adjustment_beats": float((requested_start_index - baseline_start) * 4),
            "selection_rule": "selector_requested_musically_valid_downbeat_window",
            "source_phrase_duration_change_sec": round(
                selected["source_phrase_duration_sec"] - baseline["source_phrase_duration_sec"], 6,
            ),
            "baseline": baseline,
            "selected": selected,
        }
    if archetype not in {ReferenceArchetype.RESET_RELEASE, ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF}:
        return baseline_start, baseline_end, {
            "adjusted": False,
            "adjustment_beats": 0.0,
            "selection_rule": "existing analysis-derived phrase window",
            "selected": baseline,
        }
    if archetype == ReferenceArchetype.RESET_RELEASE and _f_entry_is_safe(baseline):
        return baseline_start, baseline_end, {
            "adjusted": False,
            "adjustment_beats": 0.0,
            "selection_rule": "final-bar motif ends within 0.75 s of its vocal-unit boundary",
            "selected": baseline,
        }
    if archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF and any(_b8_entry_modes(baseline)):
        return baseline_start, baseline_end, {
            "adjusted": False,
            "adjustment_beats": 0.0,
            "selection_rule": "clean vocal gap or stable section with predictable motif continuity",
            "selected": baseline,
        }

    candidates: list[tuple[tuple[Any, ...], int, dict[str, Any], str]] = []
    grid = _grid(analysis)
    for start_index in range(0, len(grid) - bars):
        context = _source_entry_context(analysis, start_index, bars, archetype, duration_sec)
        bar_energy = _bar_mean(analysis, start_index, start_index + bars)
        if archetype == ReferenceArchetype.RESET_RELEASE:
            if not _f_entry_is_safe(context):
                continue
            rank = (
                context["vocal_units_intersecting_window"] == 1,
                -abs(start_index - baseline_start),
                context["largest_vocal_unit_window_coverage"],
                context["final_bar_vocal_coverage"],
                -context["nearest_vocal_boundary_sec"],
                bar_energy,
            )
            mode = "self_contained_final_bar_motif"
        else:
            clean_gap, phrase_end_release, predictable_hook = _b8_entry_modes(context)
            if not (clean_gap or phrase_end_release or predictable_hook):
                continue
            previous = context["distance_since_previous_vocal_sec"]
            following = context["distance_until_next_vocal_sec"]
            rank = (
                clean_gap or phrase_end_release,
                phrase_end_release or ((previous is not None and previous <= .5) if clean_gap else False),
                min(following if following is not None else 2.0, 2.0),
                context["source_window_section_continuous"],
                context["motif_entry_spectral_similarity"],
                context["motif_entry_rhythm_similarity"],
                bar_energy,
                -abs(start_index - baseline_start),
            )
            mode = "instrumental_gap" if clean_gap else "phrase_end_release" if phrase_end_release else "predictable_hook"
        candidates.append((rank, start_index, context, mode))
    if not candidates:
        label = "self-contained repeatable motif" if archetype == ReferenceArchetype.RESET_RELEASE else "safe loop-build source entry"
        raise ReferenceTemplateEligibilityError(f"source has no {label}")
    if archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        baseline_duration = baseline["source_phrase_duration_sec"]
        clock_stable = [
            item for item in candidates
            if abs(item[2]["source_phrase_duration_sec"] - baseline_duration) <= .005
        ]
        if clock_stable:
            candidates = clock_stable
    rank, selected_start, selected, mode = max(candidates, key=lambda item: (item[0], -item[1]))
    return selected_start, selected_start + bars, {
        "adjusted": True,
        "adjustment_beats": float((selected_start - baseline_start) * 4),
        "selection_rule": mode,
        "selection_rank_evidence": {
            "ordered_rule": (
                "single vocal unit, nearest safe window, unit coverage, final-bar coverage, boundary distance, energy"
                if archetype == ReferenceArchetype.RESET_RELEASE
                else "instrumental gap, recent phrase end, next-vocal runway, section continuity, motif spectrum/rhythm, energy, proximity"
            ),
            "selected_rank_values": [round(float(value), 6) for value in rank],
        },
        "source_phrase_duration_change_sec": round(
            selected["source_phrase_duration_sec"] - baseline["source_phrase_duration_sec"], 6,
        ),
        "baseline": baseline,
        "selected": selected,
    }


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
    source_start_bar_index: int | None = None,
    target_landing_bar_index: int | None = None,
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
    source_start_index, source_end_index, source_entry = _refine_source_window(
        source,
        definition.transition_bars,
        archetype,
        source_duration_sec,
        source_start_bar_index,
    )
    landing_index = (
        _target_landing_index(target, archetype)
        if target_landing_bar_index is None
        else int(target_landing_bar_index)
    )
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
        provenance_version="reference-template-2",
        metadata={
            "phase": 11,
            "purpose": "reference_backed_reproduction",
            "reference_archetype": archetype.value,
            "reference_label": definition.reference_label,
            "template_schema_version": REFERENCE_TEMPLATE_SCHEMA_VERSION,
            "anchors": anchors.to_dict(),
            "choreography": choreography,
            "source_entry": source_entry,
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
            "source_entry": source_entry,
        },
        choreography=choreography,
        instance_id=instance_id,
    )


def archetype_catalog() -> dict[str, dict[str, Any]]:
    """Return the explicit template catalog without choosing from it."""
    return {key.value: value.to_dict() for key, value in ARCHETYPE_DEFINITIONS.items()}


def _bar_mean(analysis: TrackAnalysis, start: int, end: int) -> float:
    values = analysis.bar_energies[start:end]
    return float(np.mean(values)) if values else float(analysis.mean_energy)


def _section_profile(analysis: TrackAnalysis, time_sec: float) -> dict[str, Any]:
    for section in analysis.section_profiles:
        if float(section.get("start_sec", 0.0)) - .25 <= time_sec < float(section.get("end_sec", 0.0)):
            return section
    return {}


def _groove_distance(source: TrackAnalysis, target: TrackAnalysis) -> float:
    fields = ("onbeat_fraction", "syncopation_index", "percussion_density_mean")
    return float(sum(abs(float(source.groove_profile.get(name, .5)) - float(target.groove_profile.get(name, .5))) for name in fields))


def _key_score(source: TrackAnalysis, target: TrackAnalysis) -> float:
    if not source.camelot or not target.camelot:
        return .5
    return float(score_key_compatibility(source.camelot, target.camelot))


def _nearest_cue(analysis: TrackAnalysis, time_sec: float) -> dict[str, Any]:
    if not analysis.cue_candidates:
        return {}
    return min(analysis.cue_candidates, key=lambda cue: abs(float(cue.get("time_sec", 0.0)) - time_sec))


def _target_vocal_onset(analysis: TrackAnalysis, landing_sec: float) -> float | None:
    starts = [max(0.0, float(left) - landing_sec) for left, right in analysis.vocal_regions if float(right) > landing_sec]
    return min(starts) if starts else None


def assess_reference_template_pair(
    source: TrackAnalysis,
    target: TrackAnalysis,
    archetype: ReferenceArchetype | str,
    *,
    source_track_id: str,
    target_track_id: str,
    source_duration_sec: float,
    target_duration_sec: float,
    source_start_bar_index: int | None = None,
    target_landing_bar_index: int | None = None,
) -> ReferencePairAssessment:
    """Return deterministic analysis-only suitability evidence.

    This deliberately stops at feasibility/context screening.  It neither
    renders nor invokes Audition Lab, and its fit score is only a transparent
    ordering aid for the cross-pair human-listening experiment.
    """
    archetype = ReferenceArchetype(archetype)
    try:
        instance = instantiate_reference_template(
            source,
            target,
            archetype,
            source_track_id=source_track_id,
            target_track_id=target_track_id,
            source_duration_sec=source_duration_sec,
            target_duration_sec=target_duration_sec,
            source_start_bar_index=source_start_bar_index,
            target_landing_bar_index=target_landing_bar_index,
        )
    except ReferenceTemplateEligibilityError as exc:
        return ReferencePairAssessment(
            archetype=archetype,
            eligible=False,
            fit_score=0.0,
            rejection_reasons=tuple(str(exc).split("; ")),
            cautions=(),
            selection_reasons=(),
            evidence={
                "source_bpm": round(float(source.bpm), 4),
                "target_bpm": round(float(target.bpm), 4),
                "source_key": source.key,
                "target_key": target.key,
                "source_camelot": source.camelot,
                "target_camelot": target.camelot,
            },
        )

    anchors = instance.anchors
    sg, tg = _grid(source), _grid(target)
    source_last_start = float(sg[anchors.source_end_bar_index - 1])
    source_last_end = float(sg[anchors.source_end_bar_index])
    target_last_start = float(tg[anchors.target_landing_bar_index - 1])
    target_first_end = float(tg[anchors.target_landing_bar_index + 1])
    source_capture_start_index = max(
        anchors.source_start_bar_index,
        anchors.source_start_bar_index + instance.definition.transition_bars - 2,
    )
    source_capture_start = float(sg[source_capture_start_index])
    source_vocal_density = _vocal_coverage(source, anchors.source_start_sec, anchors.source_end_sec)
    source_last_vocal = _vocal_coverage(source, source_last_start, source_last_end)
    source_capture_vocal = _vocal_coverage(source, source_capture_start, source_last_end)
    target_runway_vocal = _vocal_coverage(target, anchors.target_runway_start_sec, anchors.target_landing_sec)
    target_last_vocal = _vocal_coverage(target, target_last_start, anchors.target_landing_sec)
    target_first_vocal = _vocal_coverage(target, anchors.target_landing_sec, target_first_end)
    vocal_onset = _target_vocal_onset(target, anchors.target_landing_sec)
    source_energy = _bar_mean(source, anchors.source_start_bar_index, anchors.source_end_bar_index)
    target_runway_energy = _bar_mean(target, anchors.target_runway_bar_index, anchors.target_landing_bar_index)
    target_landing_energy = _bar_mean(target, anchors.target_landing_bar_index, anchors.target_landing_bar_index + 2)
    target_two_bar = target.bar_energies[anchors.target_landing_bar_index:anchors.target_landing_bar_index + 2]
    target_two_bar_spread = float(max(target_two_bar) - min(target_two_bar)) if len(target_two_bar) == 2 else 1.0
    tempo_delta = abs(source.bpm - target.bpm) / max(min(source.bpm, target.bpm), 1e-9) * 100
    tempo_ratio = source.bpm / target.bpm
    harmonic = _key_score(source, target)
    groove = _groove_distance(source, target)
    target_profile = _section_profile(target, anchors.target_landing_sec)
    source_profile = _section_profile(source, anchors.source_start_sec)
    target_cue = _nearest_cue(target, anchors.target_landing_sec)
    source_stem_profiles = source.stem_activity_profiles
    target_stem_profiles = target.stem_activity_profiles
    target_drum_activity = float(target_stem_profiles.get("drums", {}).get("active_fraction", 0.0))
    source_other_activity = float(source_stem_profiles.get("other", {}).get("active_fraction", 0.0))
    source_drum_activity = float(source_stem_profiles.get("drums", {}).get("active_fraction", 0.0))
    target_bass_activity = float(target_stem_profiles.get("bass", {}).get("active_fraction", 0.0))
    source_vocal_stem_confidence = float(
        source_stem_profiles.get("vocals", {}).get("activity_confidence", 0.0)
    )
    target_vocal_stem_confidence = float(
        target_stem_profiles.get("vocals", {}).get("activity_confidence", 0.0)
    )
    target_arrangement_density = float(target_profile.get("drum_density", target_drum_activity))
    source_arrangement_density = float(source_profile.get("drum_density", source_drum_activity))
    shared_density_pressure = source_arrangement_density + target_arrangement_density
    raw_vocal_overlap_pressure = min(source_vocal_density, target_runway_vocal)
    source_bass_window = _curve_window_mean(
        source.low_energy_curve,
        anchors.source_start_sec,
        anchors.source_end_sec,
        source_duration_sec,
    )
    target_runway_bass = _curve_window_mean(
        target.low_energy_curve,
        anchors.target_runway_start_sec,
        anchors.target_landing_sec,
        target_duration_sec,
    )
    target_landing_bass = _curve_window_mean(
        target.low_energy_curve,
        anchors.target_landing_sec,
        target_first_end,
        target_duration_sec,
    )
    target_drum_onset = _curve_activity_onset(
        target.rhythmic_density_curve,
        anchors.target_runway_start_sec,
        anchors.target_landing_sec,
        target_duration_sec,
    )
    target_bass_onset = _curve_activity_onset(
        target.low_energy_curve,
        anchors.target_runway_start_sec,
        anchors.target_landing_sec,
        target_duration_sec,
    )

    evidence = {
        "source_bpm": round(float(source.bpm), 4),
        "target_bpm": round(float(target.bpm), 4),
        "tempo_delta_pct": round(tempo_delta, 4),
        "target_tempo_ratio": round(tempo_ratio, 6),
        "target_tempo_adjustment_pct": round((tempo_ratio - 1.0) * 100, 4),
        "source_key": source.key,
        "target_key": target.key,
        "source_camelot": source.camelot,
        "target_camelot": target.camelot,
        "harmonic_compatibility": round(harmonic, 4),
        "groove_distance": round(groove, 4),
        "source_section": anchors.source_section,
        "target_runway_section": anchors.target_runway_section,
        "target_landing_section": anchors.target_landing_section,
        "source_energy": round(source_energy, 4),
        "target_runway_energy": round(target_runway_energy, 4),
        "target_landing_energy": round(target_landing_energy, 4),
        "landing_energy_change": round(target_landing_energy - target_runway_energy, 4),
        "target_two_bar_energy_spread": round(target_two_bar_spread, 4),
        "source_vocal_density": round(source_vocal_density, 4),
        "source_final_bar_vocal_density": round(source_last_vocal, 4),
        "source_capture_region_vocal_density": round(source_capture_vocal, 4),
        "target_runway_vocal_density": round(target_runway_vocal, 4),
        "target_final_runway_bar_vocal_density": round(target_last_vocal, 4),
        "target_first_landing_bar_vocal_density": round(target_first_vocal, 4),
        "target_vocal_onset_sec_after_landing": round(vocal_onset, 4) if vocal_onset is not None else None,
        "source_arrangement_density": round(source_arrangement_density, 4),
        "target_arrangement_density": round(target_arrangement_density, 4),
        "shared_arrangement_density_pressure": round(shared_density_pressure, 4),
        "source_cue_bass_ratio": round(source_bass_window, 4),
        "target_runway_bass_ratio": round(target_runway_bass, 4),
        "target_landing_bass_ratio": round(target_landing_bass, 4),
        "target_bass_change_at_landing": round(target_landing_bass - target_runway_bass, 4),
        "source_other_stem_activity": round(source_other_activity, 4),
        "source_drum_stem_activity": round(source_drum_activity, 4),
        "target_drum_stem_activity": round(target_drum_activity, 4),
        "target_bass_stem_activity": round(target_bass_activity, 4),
        "source_vocal_stem_confidence": round(source_vocal_stem_confidence, 4),
        "target_vocal_stem_confidence": round(target_vocal_stem_confidence, 4),
        "source_stems": sorted((source.stems or {}).keys()),
        "target_stems": sorted((target.stems or {}).keys()),
        "stem_quality_scope": "activity/confidence only; bleed/artifact quality unavailable",
        "target_cue": {
            "time_sec": round(float(target_cue.get("time_sec", anchors.target_landing_sec)), 4),
            "confidence": round(float(target_cue.get("confidence", 0.0)), 4),
            "vocal_state": str(target_cue.get("vocal_state", "unknown")),
            "mix_in_score": round(float(target_cue.get("mix_in_score", 0.0)), 4),
            "use_cases": list(target_cue.get("use_cases", [])),
        },
        "phrase_compatibility": {
            "transition_bars": instance.definition.transition_bars,
            "source_phrase_duration_sec": round(anchors.source_end_sec - anchors.source_start_sec, 4),
            "target_runway_duration_sec": round(anchors.target_landing_sec - anchors.target_runway_start_sec, 4),
            "source_and_target_anchors_are_downbeats": True,
            "target_runway_and_body_are_adjacent": True,
        },
        "source_entry": instance.eligibility["source_entry"],
        "target_entry": {
            "landing_is_downbeat": True,
            "nearest_phrase_boundary_sec": _round_optional(
                _boundary_distance(target.phrase_boundaries, anchors.target_landing_sec),
            ),
            "nearest_section_boundary_sec": _round_optional(
                _boundary_distance(
                    [
                        float(value)
                        for section in target.section_profiles
                        for value in (section.get("start_sec", 0.0), section.get("end_sec", target_duration_sec))
                    ],
                    anchors.target_landing_sec,
                ),
            ),
            "runway_vocal_density": round(target_runway_vocal, 4),
            "landing_vocal_onset_sec": round(vocal_onset, 4) if vocal_onset is not None else None,
            "drum_activity_onset_sec_after_runway_start": _round_optional(target_drum_onset),
            "bass_activity_onset_sec_after_runway_start": _round_optional(target_bass_onset),
            "activity_onset_scope": "duration-scaled rhythmic/low-energy curve proxy; not a stem transient detector",
            "runway_bass_ratio": round(target_runway_bass, 4),
            "landing_bass_ratio": round(target_landing_bass, 4),
            "arrangement_density": round(target_arrangement_density, 4),
            "cue_confidence": round(float(target_cue.get("confidence", 0.0)), 4),
            "cue_cleanliness": {
                "mix_in_score": round(float(target_cue.get("mix_in_score", 0.0)), 4),
                "vocal_state": str(target_cue.get("vocal_state", "unknown")),
                "runway_vocal_density": round(target_runway_vocal, 4),
                "landing_section": anchors.target_landing_section,
            },
            "target_establishment_bars": instance.definition.postlanding_bars,
        },
        "pair_context": {
            "tempo_delta_pct": round(tempo_delta, 4),
            "groove_distance": round(groove, 4),
            "harmonic_compatibility": round(harmonic, 4),
            "source_to_target_energy_change": round(target_landing_energy - source_energy, 4),
            "stem_quality_scope": "presence/activity/confidence only; bleed/artifact quality requires audio",
            "expected_overlap_conflicts": {
                "raw_vocal_overlap_pressure": round(raw_vocal_overlap_pressure, 4),
                "shared_arrangement_density_pressure": round(shared_density_pressure, 4),
                "bass_ownership_is_choreography_controlled": True,
                "stem_bleed_conflict_deferred": True,
            },
        },
        "anchors": anchors.to_dict(),
    }
    rejected: list[str] = []
    cautions: list[str] = []
    reasons: list[str] = []

    if archetype == ReferenceArchetype.RESET_RELEASE:
        reset_need = min(1.0, tempo_delta / 35.0 + (1.0 - harmonic) * .35)
        landing_lift = target_landing_energy - target_runway_energy
        if source_last_vocal < .25:
            rejected.append("source final bar lacks a recognizable vocal/hook capture")
        if target_last_vocal > .65:
            rejected.append("target pickup is too vocally dense for reset space")
        if reset_need < .45:
            rejected.append("pair does not justify a tempo/harmonic reset")
        if landing_lift < .08:
            rejected.append("target continuation does not establish a clear landing lift")
        score = .30 * source_last_vocal + .22 * (1 - target_last_vocal) + .22 * reset_need + .16 * np.clip(landing_lift / .45, 0, 1) + .10 * target.analysis_confidence
        reasons.extend((
            "final source bar contains capturable recognizable material",
            "target pickup leaves space for the repeated release",
            "tempo/harmonic contrast makes a reset tell a coherent story",
            "target continuation supplies a measurable energy landing",
        ))
    elif archetype == ReferenceArchetype.STEM_ECHO_HANDOFF:
        if source_capture_vocal < .30:
            rejected.append("late source phrase lacks enough vocal material for the echo edit")
        if target_drum_activity < .60 or target_arrangement_density < .45:
            rejected.append("target lacks a sufficiently active drum phrase")
        if groove > .42:
            rejected.append("source and target groove descriptors are too far apart for a stem handoff")
        if harmonic < .30:
            rejected.append("harmonic overlap risk is too high for the staged stem edit")
        if source_capture_vocal > .85 and target_runway_vocal > .90:
            rejected.append(
                "source and target vocals remain active throughout the useful C3 shared window"
            )
        if source_vocal_stem_confidence < .75 or target_vocal_stem_confidence < .75:
            rejected.append("vocal-stem activity confidence is too weak for a controlled C3 handoff")
        score = .24 * (1 - min(groove / .42, 1)) + .22 * source_capture_vocal + .20 * target_drum_activity + .14 * target_landing_energy + .10 * harmonic + .10 * target.analysis_confidence
        reasons.extend((
            "late source vocal supports a captured echo continuation",
            "target drum activity can establish ownership before landing",
            "groove descriptors support a synchronized stem exchange",
            "target vocal remains renderer-withheld until the landing",
        ))
        if tempo_delta > 8.0 and groove > .18 and source_arrangement_density > .80:
            cautions.append("near-limit stretch and groove change meet a dense source arrangement; expect only borderline eligibility")
    elif archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        if source_other_activity < .55:
            rejected.append("source backing stem activity is too weak for a recognizable loop motif")
        if target_drum_activity < .60 or target_landing_energy < .68:
            rejected.append("target landing lacks the drum/energy strength required for build payoff")
        if groove > .42:
            rejected.append("source and target groove descriptors are too far apart for loop-build alignment")
        if vocal_onset is None or vocal_onset < .25:
            rejected.append("target vocal begins at landing, leaving no bounded post-release tail runway")
        if target_two_bar_spread > .28:
            rejected.append("target two-bar landing cadence is too unstable for the low-frequency preview")
        if harmonic < .30:
            rejected.append("harmonic overlap risk is too high during the progressive target reveal")
        onset_room = np.clip(((vocal_onset or 0.0) - .25) / 1.5, 0, 1)
        score = .22 * (1 - min(groove / .42, 1)) + .18 * source_other_activity + .18 * target_drum_activity + .16 * target_landing_energy + .14 * onset_room + .07 * harmonic + .05 * target.analysis_confidence
        reasons.extend((
            "source backing supports one phase-anchored 4/2/1-beat motif",
            "target drums and landing energy provide build payoff",
            "target vocal timing leaves a measurable stateful-tail window",
            "two-bar target cadence supports stable bass ownership before landing",
        ))
    else:
        energy_gap = abs(source_energy - target_landing_energy)
        if groove > .35:
            rejected.append("groove difference is too large for a restrained long blend")
        if harmonic < .50:
            rejected.append("global harmonic compatibility is too weak for prolonged shared territory")
        if shared_density_pressure > 1.65:
            rejected.append("combined source/target arrangement density is too high for a restrained long blend")
        if target_drum_activity < .60 or target_bass_activity < .55:
            rejected.append("target lacks active drum/bass material for the late ownership handoff")
        if energy_gap > .32:
            rejected.append("section energy gap is too large for a restrained ownership blend")
        score = .27 * (1 - min(groove / .35, 1)) + .20 * harmonic + .18 * (1 - min(energy_gap / .32, 1)) + .15 * target_drum_activity + .10 * target_bass_activity + .10 * target.analysis_confidence
        reasons.extend((
            "close tempo and groove support a long unobtrusive blend",
            "shared-territory harmonic risk remains bounded",
            "source/target energy permits gradual rather than dramatic transfer",
            "target drum and bass activity support the late ownership handoff",
        ))

    if harmonic < .7:
        cautions.append("global key relation is not an ideal Camelot move; exact local overlap remains an estimate")
    if target_runway_vocal > .75:
        cautions.append("analysis marks a vocally dense target runway; renderer stem withholding is essential")
    if source_vocal_density > .85 and archetype != ReferenceArchetype.RESET_RELEASE:
        cautions.append("source phrase is vocally dense; sequential vocal ownership must remain fixed")
    if abs(tempo_ratio - 1) > .08 and archetype != ReferenceArchetype.RESET_RELEASE:
        cautions.append("tempo adjustment is near the archetype limit")
    return ReferencePairAssessment(
        archetype=archetype,
        eligible=not rejected,
        fit_score=round(float(np.clip(score, 0, 1)), 6) if not rejected else 0.0,
        rejection_reasons=tuple(rejected),
        cautions=tuple(cautions),
        selection_reasons=tuple(reasons) if not rejected else (),
        evidence=evidence,
        instance=instance,
    )
