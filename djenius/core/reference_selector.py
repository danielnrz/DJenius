"""Constrained autonomous selection among human-approved DJ templates.

This module does not call Candidate Composer, Audition Lab, or Set Director.
It searches analysis-derived cue windows for exactly the four frozen reference
archetypes, exposes every threshold and rejection, and may abstain.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from djenius.core.models import TrackAnalysis
from djenius.core.reference_templates import (
    ARCHETYPE_DEFINITIONS,
    ReferenceArchetype,
    ReferencePairAssessment,
    ReferenceTemplateInstance,
    _boundary_distance,
    _grid,
    _section_at,
    _source_window,
    _target_landing_index,
    assess_reference_template_pair,
)


REFERENCE_SELECTOR_SCHEMA_VERSION = "reference-selector-1"


@dataclass(frozen=True)
class ReferenceTemplateEvaluation:
    archetype: ReferenceArchetype
    eligible: bool
    rejection_reasons: tuple[str, ...]
    cautions: tuple[str, ...]
    selection_reasons: tuple[str, ...]
    evidence: dict[str, Any]
    cue_search: dict[str, Any]
    story_rule: dict[str, Any]
    instance: ReferenceTemplateInstance | None = None

    def to_dict(self, *, include_instance: bool = True) -> dict[str, Any]:
        result = {
            "archetype": self.archetype.value,
            "eligible": self.eligible,
            "rejection_reasons": list(self.rejection_reasons),
            "cautions": list(self.cautions),
            "selection_reasons": list(self.selection_reasons),
            "evidence": self.evidence,
            "cue_search": self.cue_search,
            "story_rule": self.story_rule,
        }
        if include_instance and self.instance is not None:
            result["instance"] = self.instance.to_dict()
        return result


@dataclass(frozen=True)
class ReferenceTransitionSelection:
    source_track_id: str
    target_track_id: str
    evaluations: tuple[ReferenceTemplateEvaluation, ...]
    selected_archetype: ReferenceArchetype | None
    decision: str
    decision_trace: tuple[dict[str, Any], ...]
    selector_id: str
    schema_version: str = REFERENCE_SELECTOR_SCHEMA_VERSION

    @property
    def selected_instance(self) -> ReferenceTemplateInstance | None:
        for evaluation in self.evaluations:
            if evaluation.archetype == self.selected_archetype:
                return evaluation.instance
        return None

    def to_dict(self, *, include_instances: bool = True) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "selector_id": self.selector_id,
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "selected_template": self.selected_archetype.value if self.selected_archetype else None,
            "decision": self.decision,
            "decision_trace": list(self.decision_trace),
            "evaluations": [
                item.to_dict(include_instance=include_instances) for item in self.evaluations
            ],
        }


def _source_candidate_indices(
    analysis: TrackAnalysis,
    archetype: ReferenceArchetype,
) -> tuple[int, ...]:
    grid = _grid(analysis)
    definition = ARCHETYPE_DEFINITIONS[archetype]
    baseline, _ = _source_window(
        analysis,
        definition.transition_bars,
        archetype == ReferenceArchetype.RESET_RELEASE,
    )
    boundaries = [
        float(value)
        for section in analysis.section_profiles
        for value in (section.get("start_sec", 0.0), section.get("end_sec", grid[-1]))
    ] + [float(value) for value in analysis.phrase_boundaries]
    candidates: list[tuple[tuple[float, ...], int]] = []
    for index in range(len(grid) - definition.transition_bars):
        end_index = index + definition.transition_bars
        start, end = float(grid[index]), float(grid[end_index])
        section = _section_at(analysis, start)
        if section not in definition.suitable_source_sections:
            continue
        if _section_at(analysis, max(start, end - .001)) not in definition.suitable_source_sections:
            continue
        bar_duration = max(1e-6, (end - start) / definition.transition_bars)
        boundary_distance = _boundary_distance(boundaries, start)
        near_musical_boundary = boundary_distance is not None and boundary_distance <= bar_duration * .55
        if index != baseline and abs(index - baseline) > 16:
            continue
        candidates.append(((0.0 if near_musical_boundary else 1.0, abs(index - baseline), index), index))
    candidates.sort(key=lambda item: item[0])
    return tuple(index for _, index in candidates[:32])


def _target_candidate_indices(
    analysis: TrackAnalysis,
    archetype: ReferenceArchetype,
) -> tuple[int, ...]:
    grid = _grid(analysis)
    definition = ARCHETYPE_DEFINITIONS[archetype]
    runway = 1 if archetype == ReferenceArchetype.RESET_RELEASE else definition.transition_bars
    allowed = {
        ReferenceArchetype.RESET_RELEASE: {"verse", "build", "drop", "bridge", "chorus"},
        ReferenceArchetype.STEM_ECHO_HANDOFF: {"drop", "chorus"},
        ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF: {"drop", "chorus"},
        ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND: {"build", "verse", "bridge", "drop"},
    }[archetype]
    try:
        baseline = _target_landing_index(analysis, archetype)
    except Exception:
        baseline = -1
    candidates: list[tuple[tuple[float, ...], int]] = []
    for index in range(runway, len(grid) - definition.postlanding_bars):
        landing = float(grid[index])
        section = _section_at(analysis, landing)
        if section not in allowed:
            continue
        containing = next(
            (
                item for item in analysis.section_profiles
                if float(item.get("start_sec", 0.0)) <= landing < float(item.get("end_sec", grid[-1]))
            ),
            {},
        )
        section_start = float(containing.get("start_sec", landing))
        bar_duration = max(1e-6, float(grid[index] - grid[index - 1]))
        bars_inside = (landing - section_start) / bar_duration
        if baseline >= 0 and index != baseline and abs(index - baseline) > 8:
            continue
        if index != baseline and bars_inside > 8.25:
            continue
        phrase_distance = _boundary_distance(analysis.phrase_boundaries, landing)
        phrase_boundary = phrase_distance is not None and phrase_distance <= bar_duration * .55
        section_boundary = abs(landing - section_start) <= bar_duration * .55
        candidates.append((
            (
                0.0 if phrase_boundary or section_boundary else 1.0,
                abs(index - baseline) if baseline >= 0 else index,
                index,
            ),
            index,
        ))
    candidates.sort(key=lambda item: item[0])
    return tuple(index for _, index in candidates[:16])


def _rank_evidence(
    assessment: ReferencePairAssessment,
    target_baseline_index: int,
) -> tuple[tuple[float, ...], list[dict[str, Any]]]:
    evidence = assessment.evidence
    source = evidence["source_entry"]["selected"]
    target = evidence["target_entry"]
    target_shift = abs(assessment.instance.anchors.target_landing_bar_index - target_baseline_index)
    common = [
        ("fewer_cautions", -len(assessment.cautions), "higher"),
        ("nearby_target_cue", -target_shift, "higher"),
    ]
    if assessment.archetype == ReferenceArchetype.RESET_RELEASE:
        ordered = common + [
            ("self_contained_vocal_unit", -source.get("vocal_units_intersecting_window", 99), "higher"),
            ("final_bar_motif_coverage", evidence["source_final_bar_vocal_density"], "higher"),
            ("target_pickup_space", 1.0 - evidence["target_final_runway_bar_vocal_density"], "higher"),
            ("landing_energy_lift", evidence["landing_energy_change"], "higher"),
        ]
    elif assessment.archetype == ReferenceArchetype.STEM_ECHO_HANDOFF:
        ordered = common + [
            ("tempo_closeness", -evidence["tempo_delta_pct"], "higher"),
            ("groove_closeness", -evidence["groove_distance"], "higher"),
            ("late_vocal_capture", evidence["source_capture_region_vocal_density"], "higher"),
            ("target_drum_activity", evidence["target_drum_stem_activity"], "higher"),
            ("lower_source_density", -evidence["source_arrangement_density"], "higher"),
        ]
    elif assessment.archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        mode = source.get("selection_rule", "")
        mode_value = {"phrase_end_release": 3.0, "instrumental_gap": 2.0, "predictable_hook": 1.0}.get(mode, 0.0)
        if not mode_value:
            if not source.get("vocal_active", False):
                mode_value = 2.0
            elif source.get("active_vocal_remaining_sec", 99.0) <= .5:
                mode_value = 3.0
            else:
                mode_value = 1.0
        ordered = common + [
            ("source_entry_mode", mode_value, "higher"),
            ("target_vocal_runway", target.get("landing_vocal_onset_sec") or 0.0, "higher"),
            ("target_landing_energy", evidence["target_landing_energy"], "higher"),
            ("stable_two_bar_cadence", -evidence["target_two_bar_energy_spread"], "higher"),
            ("groove_closeness", -evidence["groove_distance"], "higher"),
        ]
    else:
        ordered = common + [
            ("harmonic_compatibility", evidence["harmonic_compatibility"], "higher"),
            ("lower_shared_density", -evidence["shared_arrangement_density_pressure"], "higher"),
            ("energy_closeness", -abs(evidence["target_landing_energy"] - evidence["source_energy"]), "higher"),
            ("groove_closeness", -evidence["groove_distance"], "higher"),
        ]
    rank = tuple(float(value) for _, value, _ in ordered)
    return rank, [
        {"criterion": name, "value": round(float(value), 6), "preferred": direction}
        for name, value, direction in ordered
    ]


def _story_rule(assessment: ReferencePairAssessment) -> dict[str, Any]:
    e = assessment.evidence
    if assessment.archetype == ReferenceArchetype.RESET_RELEASE:
        checks = {
            "reset_contrast_is_material": e["tempo_delta_pct"] >= 12.0 or e["harmonic_compatibility"] < .50,
            "repeatable_motif_is_complete": e["source_final_bar_vocal_density"] >= .25,
            "target_reset_has_space": e["target_final_runway_bar_vocal_density"] <= .65,
            "target_continuation_lifts": e["landing_energy_change"] >= .08,
        }
        rule = "recognizable motif resolves a material tempo/harmonic contrast into target lift"
    elif assessment.archetype == ReferenceArchetype.STEM_ECHO_HANDOFF:
        checks = {
            "tempo_is_not_near_limit": e["tempo_delta_pct"] <= 8.0,
            "groove_is_close": e["groove_distance"] <= .18,
            "late_vocal_capture_is_present": e["source_capture_region_vocal_density"] >= .30,
            "source_arrangement_is_controllable": e["source_arrangement_density"] <= .80,
            "target_drums_can_take_ownership": e["target_drum_stem_activity"] >= .60,
        }
        rule = "controlled vocal/stem edit over close tempo and groove"
    elif assessment.archetype == ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF:
        entry = e["source_entry"]["selected"]
        checks = {
            "source_launch_is_vocal_safe_or_predictable": (
                not entry.get("vocal_active", False)
                or entry.get("active_vocal_remaining_sec", 99.0) <= .5
                or (
                    entry.get("motif_entry_rhythm_similarity", 0.0) >= .95
                    and entry.get("motif_entry_spectral_similarity", 0.0) >= .93
                )
            ),
            "target_has_build_payoff": e["target_landing_energy"] >= .72,
            "target_vocal_leaves_tail_room": (e["target_vocal_onset_sec_after_landing"] or 0.0) >= .40,
            "target_cadence_is_stable": e["target_two_bar_energy_spread"] <= .22,
        }
        rule = "safe source manipulation builds into a stable energetic target payoff"
    else:
        overlap = e["pair_context"]["expected_overlap_conflicts"]
        checks = {
            "tempo_is_close": e["tempo_delta_pct"] <= 6.0,
            "groove_is_close": e["groove_distance"] <= .20,
            "harmony_supports_long_overlap": e["harmonic_compatibility"] >= .70,
            "shared_arrangement_has_space": e["shared_arrangement_density_pressure"] <= 1.50,
            "energy_gap_is_restrained": abs(e["target_landing_energy"] - e["source_energy"]) <= .22,
            "raw_vocal_overlap_is_bounded": overlap["raw_vocal_overlap_pressure"] <= .75,
        }
        rule = "compatible, spacious material supports a restrained ownership transfer"
    return {
        "rule": rule,
        "checks": checks,
        "qualified": all(checks.values()),
    }


def _evaluate_template(
    source: TrackAnalysis,
    target: TrackAnalysis,
    archetype: ReferenceArchetype,
    *,
    source_track_id: str,
    target_track_id: str,
    source_duration_sec: float,
    target_duration_sec: float,
) -> ReferenceTemplateEvaluation:
    source_candidates = _source_candidate_indices(source, archetype)
    target_candidates = _target_candidate_indices(target, archetype)
    try:
        target_baseline = _target_landing_index(target, archetype)
    except Exception:
        target_baseline = -1
    accepted: list[tuple[tuple[float, ...], ReferencePairAssessment, list[dict[str, Any]]]] = []
    rejected = Counter()
    baseline_assessment: ReferencePairAssessment | None = None
    if not source_candidates or not target_candidates:
        baseline_assessment = assess_reference_template_pair(
            source,
            target,
            archetype,
            source_track_id=source_track_id,
            target_track_id=target_track_id,
            source_duration_sec=source_duration_sec,
            target_duration_sec=target_duration_sec,
        )
        rejected.update(baseline_assessment.rejection_reasons)
    for source_index in source_candidates:
        for target_index in target_candidates:
            assessment = assess_reference_template_pair(
                source,
                target,
                archetype,
                source_track_id=source_track_id,
                target_track_id=target_track_id,
                source_duration_sec=source_duration_sec,
                target_duration_sec=target_duration_sec,
                source_start_bar_index=source_index,
                target_landing_bar_index=target_index,
            )
            if assessment.eligible and assessment.instance is not None:
                rank, rank_evidence = _rank_evidence(assessment, target_baseline)
                accepted.append((rank, assessment, rank_evidence))
            else:
                rejected.update(assessment.rejection_reasons)
    if not accepted:
        if not source_candidates:
            rejected.update(["source has no nearby valid section/downbeat window for this template"])
        if not target_candidates:
            rejected.update(["target has no nearby valid entry section with the required runway and establishment"])
        reasons = tuple(
            reason for reason, _ in sorted(rejected.items(), key=lambda item: (-item[1], item[0]))
        ) or ("no musically valid source/target cue combination",)
        baseline_evidence = baseline_assessment.evidence if baseline_assessment is not None else {}
        return ReferenceTemplateEvaluation(
            archetype=archetype,
            eligible=False,
            rejection_reasons=reasons,
            cautions=(),
            selection_reasons=(),
            evidence={
                **baseline_evidence,
                "source_candidate_windows": len(source_candidates),
                "target_candidate_windows": len(target_candidates),
                "deferred": ["stem bleed/artifact quality requires rendered audio"],
            },
            cue_search={
                "combinations_considered": len(source_candidates) * len(target_candidates),
                "eligible_combinations": 0,
                "rejection_reason_counts": dict(sorted(rejected.items())),
            },
            story_rule={"qualified": False, "rule": "template has no eligible cue combination", "checks": {}},
        )
    accepted.sort(key=lambda item: (item[0], -item[1].instance.anchors.source_start_bar_index, -item[1].instance.anchors.target_landing_bar_index), reverse=True)
    _, selected, rank_evidence = accepted[0]
    anchors = selected.instance.anchors
    source_entry = selected.evidence["source_entry"]
    if target_baseline < 0:
        target_baseline = anchors.target_landing_bar_index
    source_shift = int(source_entry.get("adjustment_beats", 0.0))
    target_shift = int((anchors.target_landing_bar_index - target_baseline) * 4)
    rationale = []
    if source_shift:
        rationale.append(f"source launch shifted {source_shift:+d} beats for the selected entry context")
    else:
        rationale.append("source launch retains the analysis-derived baseline")
    if target_shift:
        rationale.append(f"target landing shifted {target_shift:+d} beats for cleaner phrase/ownership evidence")
    else:
        rationale.append("target landing retains the analysis-derived baseline")
    story = _story_rule(selected)
    return ReferenceTemplateEvaluation(
        archetype=archetype,
        eligible=True,
        rejection_reasons=(),
        cautions=selected.cautions,
        selection_reasons=selected.selection_reasons,
        evidence=selected.evidence,
        cue_search={
            "source_candidate_windows": len(source_candidates),
            "target_candidate_windows": len(target_candidates),
            "combinations_considered": len(source_candidates) * len(target_candidates),
            "eligible_combinations": len(accepted),
            "rejection_reason_counts": dict(sorted(rejected.items())),
            "selected_source_start_bar_index": anchors.source_start_bar_index,
            "selected_target_landing_bar_index": anchors.target_landing_bar_index,
            "source_cue_shift_beats": source_shift,
            "target_cue_shift_beats": target_shift,
            "cue_shift_rationale": rationale,
            "lexicographic_rank_evidence": rank_evidence,
            "no_aggregate_cue_score": True,
        },
        story_rule=story,
        instance=selected.instance,
    )


def select_reference_transition(
    source: TrackAnalysis,
    target: TrackAnalysis,
    *,
    source_track_id: str,
    target_track_id: str,
    source_duration_sec: float,
    target_duration_sec: float,
) -> ReferenceTransitionSelection:
    """Choose one approved archetype with cues, or explicitly abstain."""
    evaluations = tuple(
        _evaluate_template(
            source,
            target,
            archetype,
            source_track_id=source_track_id,
            target_track_id=target_track_id,
            source_duration_sec=source_duration_sec,
            target_duration_sec=target_duration_sec,
        )
        for archetype in ReferenceArchetype
    )
    by_type = {item.archetype: item for item in evaluations}
    qualified = {
        archetype: item
        for archetype, item in by_type.items()
        if item.eligible and item.story_rule["qualified"]
    }
    trace: list[dict[str, Any]] = []

    def matches(archetype: ReferenceArchetype, condition: bool, reason: str) -> bool:
        matched = archetype in qualified and condition
        trace.append({"template": archetype.value, "rule": reason, "matched": matched})
        return matched

    selected: ReferenceArchetype | None = None
    f = qualified.get(ReferenceArchetype.RESET_RELEASE)
    d2 = qualified.get(ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND)
    b8 = qualified.get(ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF)
    c3 = qualified.get(ReferenceArchetype.STEM_ECHO_HANDOFF)
    if matches(
        ReferenceArchetype.RESET_RELEASE,
        bool(f and f.evidence["tempo_delta_pct"] > 12.0),
        "material tempo contrast requires the only approved non-beatmatched reset",
    ):
        selected = ReferenceArchetype.RESET_RELEASE
    elif matches(
        ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND,
        bool(d2 and d2.evidence["landing_energy_change"] < .12),
        "close, spacious pair has no dramatic landing demand",
    ):
        selected = ReferenceArchetype.RESTRAINED_OWNERSHIP_BLEND
    elif matches(
        ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
        bool(b8 and (b8.evidence["landing_energy_change"] >= .12 or b8.evidence["target_landing_energy"] >= .80)),
        "safe source motif has a pronounced target payoff",
    ):
        selected = ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF
    elif matches(
        ReferenceArchetype.STEM_ECHO_HANDOFF,
        bool(c3),
        "close tempo/groove and controlled vocal stems support the edit",
    ):
        selected = ReferenceArchetype.STEM_ECHO_HANDOFF
    elif matches(
        ReferenceArchetype.RESET_RELEASE,
        bool(f),
        "harmonic contrast and complete motif support a reset even without a large tempo jump",
    ):
        selected = ReferenceArchetype.RESET_RELEASE
    else:
        trace.append({
            "template": None,
            "rule": "no eligible template also satisfies its explicit musical-story contract",
            "matched": True,
        })

    decision = (
        f"selected {selected.value}: {by_type[selected].story_rule['rule']}"
        if selected is not None
        else "NO_SUITABLE_TEMPLATE"
    )
    payload = {
        "schema": REFERENCE_SELECTOR_SCHEMA_VERSION,
        "source": source_track_id,
        "target": target_track_id,
        "selected": selected.value if selected else None,
        "evaluations": [item.to_dict(include_instance=False) for item in evaluations],
        "trace": trace,
    }
    selector_id = "rts_" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return ReferenceTransitionSelection(
        source_track_id=source_track_id,
        target_track_id=target_track_id,
        evaluations=evaluations,
        selected_archetype=selected,
        decision=decision,
        decision_trace=tuple(trace),
        selector_id=selector_id,
    )
