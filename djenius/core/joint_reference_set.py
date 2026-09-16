"""Thin joint track-and-transition planner for the reference-backed pilot.

This module is deliberately separate from the legacy Set Director, Candidate
Composer, and Audition Lab.  A next track is admissible only when the frozen
reference selector can also supply a usable F/C3/B8/D2 performance and cues.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from typing import Any, Iterable

import numpy as np

from djenius.core.models import TrackProfile
from djenius.core.musical_role import (
    MusicalContextCalibration,
    SetFlowState,
    SetRole,
    assess_musical_flow,
    calibrate_musical_context,
    derive_musical_role,
    initial_set_flow_state,
)
from djenius.core.reference_selector import (
    ReferenceTransitionSelection,
    select_reference_transition,
)
from djenius.core.reference_templates import ReferenceArchetype
from djenius.utils.camelot import score_key_compatibility


JOINT_REFERENCE_SET_SCHEMA_VERSION = "joint-reference-set-4"


@dataclass(frozen=True)
class JointSetConfig:
    track_count: int = 4
    candidate_limit: int = 8
    min_establishment_sec: float = 30.0
    opening_establishment_sec: float = 45.0
    closing_establishment_sec: float = 45.0
    max_energy_jump: float = 0.22
    preferred_max_consecutive_same_archetype: int = 2
    set_role_sequence: tuple[str, ...] = ("OPEN", "HOLD", "HOLD", "PEAK")
    max_contrast_events: int = 1
    excluded_ordered_pairs: tuple[tuple[str, str], ...] = ()
    excluded_track_sequences: tuple[tuple[str, ...], ...] = ()
    allow_partial_plan: bool = False
    minimum_partial_track_count: int = 2


@dataclass(frozen=True)
class SetFlowEvaluation:
    passes_hard_gates: bool
    hard_gates: dict[str, bool]
    evidence: dict[str, Any]
    ranking_evidence: tuple[dict[str, Any], ...]
    rejection_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passes_hard_gates": self.passes_hard_gates,
            "hard_gates": self.hard_gates,
            "evidence": self.evidence,
            "ranking_evidence": list(self.ranking_evidence),
            "rejection_reasons": list(self.rejection_reasons),
            "no_opaque_set_flow_score": True,
        }


@dataclass(frozen=True)
class JointCandidateDecision:
    current_track_id: str
    candidate_track_id: str
    set_flow: SetFlowEvaluation
    transition_selection: ReferenceTransitionSelection
    establishment: dict[str, Any]
    retained: bool
    rejection_reasons: tuple[str, ...]
    archetype_context_evaluations: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        instance = self.transition_selection.selected_instance
        return {
            "current_track_id": self.current_track_id,
            "candidate_track_id": self.candidate_track_id,
            "set_flow": self.set_flow.to_dict(),
            "pair_transitionable": self.transition_selection.pair_transitionable,
            "all_template_eligibility": self.transition_selection.to_dict(),
            "eligible_archetypes": [
                item.archetype.value
                for item in self.transition_selection.evaluations
                if item.eligible
            ],
            "usable_archetypes": [
                item.archetype.value
                for item in self.transition_selection.evaluations
                if item.eligible and item.usable_for_performance
            ],
            "best_valid_cues": (
                instance.anchors.to_dict() if instance is not None else None
            ),
            "establishment": self.establishment,
            "retained": self.retained,
            "rejection_reasons": list(self.rejection_reasons),
            "archetype_context_evaluations": list(self.archetype_context_evaluations),
        }


@dataclass(frozen=True)
class JointTransitionDecision:
    index: int
    source_track_id: str
    target_track_id: str
    selection: ReferenceTransitionSelection
    candidate_table: tuple[JointCandidateDecision, ...]
    why_this_won: tuple[str, ...]

    @property
    def instance(self):
        return self.selection.selected_instance

    def to_dict(self) -> dict[str, Any]:
        instance = self.instance
        return {
            "transition_index": self.index,
            "current_track": self.source_track_id,
            "next_track": self.target_track_id,
            "transition_archetype": (
                self.selection.selected_archetype.value
                if self.selection.selected_archetype is not None
                else None
            ),
            "source_cue_sec": instance.anchors.source_start_sec if instance else None,
            "target_cue_sec": instance.anchors.target_landing_sec if instance else None,
            "why_this_won": list(self.why_this_won),
            "selected_transition": self.selection.to_dict(),
            "candidate_decision_table": [
                item.to_dict() for item in self.candidate_table
            ],
        }


@dataclass(frozen=True)
class JointReferenceSetPlan:
    tracks: tuple[TrackProfile, ...]
    transitions: tuple[JointTransitionDecision, ...]
    opening_decision: dict[str, Any]
    config: JointSetConfig
    plan_id: str
    schema_version: str = JOINT_REFERENCE_SET_SCHEMA_VERSION
    completion: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "planning_mode": "thin_joint_reference_backed_planner",
            "legacy_set_director_used": False,
            "candidate_composer_used": False,
            "audition_lab_used": False,
            "track_ids": [track.id for track in self.tracks],
            "opening_decision": self.opening_decision,
            "config": {
                "track_count": self.config.track_count,
                "candidate_limit": self.config.candidate_limit,
                "min_establishment_sec": self.config.min_establishment_sec,
                "opening_establishment_sec": self.config.opening_establishment_sec,
                "closing_establishment_sec": self.config.closing_establishment_sec,
                "max_energy_jump": self.config.max_energy_jump,
                "preferred_max_consecutive_same_archetype": self.config.preferred_max_consecutive_same_archetype,
                "set_role_sequence": list(self.config.set_role_sequence),
                "max_contrast_events": self.config.max_contrast_events,
                "excluded_ordered_pairs": [
                    list(item) for item in self.config.excluded_ordered_pairs
                ],
                "excluded_track_sequences": [
                    list(item) for item in self.config.excluded_track_sequences
                ],
                "allow_partial_plan": self.config.allow_partial_plan,
                "minimum_partial_track_count": self.config.minimum_partial_track_count,
            },
            "completion": self.completion,
            "transitions": [item.to_dict() for item in self.transitions],
        }


class JointSetPlanningDeadEnd(RuntimeError):
    """Raised when no requested or permitted partial path clears every gate."""

    def __init__(self, message: str, diagnostics: dict[str, Any]):
        super().__init__(message)
        self.diagnostics = diagnostics


def _median_vocal_activity(track: TrackProfile) -> float:
    curve = np.asarray(track.analysis.vocal_activity_curve, dtype=float)
    if curve.size:
        return float(np.clip(np.median(curve), 0.0, 1.0))
    duration = max(track.duration_sec, 1e-6)
    covered = sum(
        max(0.0, min(duration, right) - max(0.0, left))
        for left, right in track.analysis.vocal_regions
    )
    return float(np.clip(covered / duration, 0.0, 1.0))


def _artist(track: TrackProfile) -> str:
    return " ".join((track.metadata.artist or "").lower().split())


def _tempo_delta_pct(source: TrackProfile, target: TrackProfile) -> float:
    if source.bpm <= 0 or target.bpm <= 0:
        return math.inf
    return abs(source.bpm - target.bpm) / max(source.bpm, target.bpm) * 100.0


def _set_flow(
    source: TrackProfile,
    target: TrackProfile,
    *,
    used_track_ids: set[str],
    state: SetFlowState,
    target_phase: SetRole,
    selected_archetype: ReferenceArchetype | None,
    selected_evidence: dict[str, Any],
    config: JointSetConfig,
    context_calibration: MusicalContextCalibration | None = None,
    source_context_sec: float | None = None,
    target_context_sec: float | None = None,
) -> SetFlowEvaluation:
    energy_change = float(target.mean_energy - source.mean_energy)
    tempo_delta = _tempo_delta_pct(source, target)
    harmonic = score_key_compatibility(source.camelot, target.camelot)
    same_artist = bool(_artist(source) and _artist(source) == _artist(target))
    identity_gates = {
        "target_not_already_used": target.id not in used_track_ids,
        "different_track": source.id != target.id,
        "artist_not_immediately_repeated": not same_artist,
        "analysis_confidence_usable": min(
            source.analysis.analysis_confidence,
            target.analysis.analysis_confidence,
        )
        >= 0.75,
    }
    tempo_for_performance = float(selected_evidence.get("tempo_delta_pct", tempo_delta))
    groove_distance = float(selected_evidence.get("groove_distance", 1.0))
    musical = assess_musical_flow(
        source,
        target,
        state=state,
        target_phase=target_phase,
        archetype=selected_archetype,
        tempo_delta_pct=tempo_for_performance,
        groove_distance=groove_distance,
        max_energy_jump=config.max_energy_jump,
        max_contrast_events=config.max_contrast_events,
        context_calibration=context_calibration,
        source_context_sec=source_context_sec,
        target_context_sec=target_context_sec,
    )
    hard_gates = {
        **identity_gates,
        **{f"set_story_{name}": passed for name, passed in musical.hard_gates.items()},
    }
    rejection = [name for name, passed in identity_gates.items() if not passed]
    rejection.extend(musical.rejection_reasons)
    source_vocal = _median_vocal_activity(source)
    target_vocal = _median_vocal_activity(target)
    evidence = {
        "source_bpm": round(source.bpm, 4),
        "target_bpm": round(target.bpm, 4),
        "tempo_delta_pct": round(tempo_delta, 4),
        "source_energy": round(source.mean_energy, 4),
        "target_energy": round(target.mean_energy, 4),
        "energy_change": round(energy_change, 4),
        "energy_trajectory": (
            "lift"
            if energy_change > 0.035
            else "release"
            if energy_change < -0.035
            else "steady"
        ),
        "source_camelot": source.camelot,
        "target_camelot": target.camelot,
        "harmonic_compatibility": round(harmonic, 4),
        "source_vocal_density": round(source_vocal, 4),
        "target_vocal_density": round(target_vocal, 4),
        "vocal_density_change": round(target_vocal - source_vocal, 4),
        "genre_or_style_evidence": {
            "source": musical.source_role.style,
            "target": musical.target_role.style,
        },
        "mood_or_affect_evidence": {
            "source": musical.source_role.mood,
            "target": musical.target_role.mood,
            "claim_deferred": musical.evidence["mood_claim_deferred"],
        },
        "musical_role_and_set_story": musical.to_dict(),
        "artist_continuity": "different_or_unknown"
        if not same_artist
        else "same_artist",
        "local_contrast_vs_continuity": {
            "tempo": "contrast" if tempo_delta > 12 else "continuity",
            "energy": "contrast" if abs(energy_change) > 0.12 else "continuity",
            "vocal_density": "contrast"
            if abs(target_vocal - source_vocal) > 0.25
            else "continuity",
        },
    }
    ranking = (
        {
            "criterion": "smaller_energy_discontinuity",
            "value": round(abs(energy_change), 6),
            "direction": "lower",
        },
        {
            "criterion": "smaller_tempo_discontinuity",
            "value": round(tempo_delta, 6),
            "direction": "lower",
        },
        {
            "criterion": "harmonic_compatibility",
            "value": round(harmonic, 6),
            "direction": "higher",
        },
        {
            "criterion": "vocal_density_contrast",
            "value": round(abs(target_vocal - source_vocal), 6),
            "direction": "lower",
        },
    )
    return SetFlowEvaluation(
        all(hard_gates.values()), hard_gates, evidence, ranking, tuple(rejection)
    )


def _opening_evidence(track: TrackProfile) -> dict[str, Any]:
    sections = track.analysis.section_profiles
    first_section = (
        str(sections[0].get("label", sections[0].get("type", "unknown")))
        if sections
        else "unknown"
    )
    early_vocal = 0.0
    window = min(30.0, track.duration_sec)
    if window > 0:
        early_vocal = (
            sum(
                max(0.0, min(window, right) - max(0.0, left))
                for left, right in track.analysis.vocal_regions
            )
            / window
        )
    role = derive_musical_role(track)
    return {
        "track_id": track.id,
        "opening_section": first_section,
        "first_30_sec_vocal_coverage": round(float(np.clip(early_vocal, 0, 1)), 4),
        "mean_energy": round(track.mean_energy, 4),
        "bpm": round(track.bpm, 4),
        "analysis_confidence": round(track.analysis.analysis_confidence, 4),
        "musical_role": role.to_dict(),
        "opening_role_supported": role.role_suitability[SetRole.OPEN.value],
        "opening_rank_vector": [
            0 if role.role_suitability[SetRole.OPEN.value] else 1,
            0 if first_section == "intro" else 1,
            round(abs(track.mean_energy - 0.72), 6),
            round(float(np.clip(early_vocal, 0, 1)), 6),
            track.id,
        ],
    }


def _candidate_key(
    candidate: JointCandidateDecision, recent_archetypes: tuple[str, ...]
) -> tuple:
    selected = candidate.transition_selection.selected_archetype
    archetype = selected.value if selected is not None else ""
    repeated = 1 if recent_archetypes and archetype == recent_archetypes[-1] else 0
    e = candidate.set_flow.evidence
    relationship = e.get("musical_role_and_set_story", {}).get(
        "relationship", "NATURAL_CONTINUATION"
    )
    # This is a disclosed lexicographic ordering, not a weighted compatibility score.
    return (
        0 if relationship == "NATURAL_CONTINUATION" else 1,
        abs(float(e["energy_change"])),
        float(e["tempo_delta_pct"]),
        -float(e["harmonic_compatibility"]),
        repeated,
        candidate.candidate_track_id,
    )


def _evaluate_candidate(
    source: TrackProfile,
    target: TrackProfile,
    *,
    used_track_ids: set[str],
    prior_target_landing_sec: float | None,
    set_flow_state: SetFlowState,
    target_phase: SetRole,
    config: JointSetConfig,
    context_calibration: MusicalContextCalibration | None = None,
) -> JointCandidateDecision:
    excluded = (source.id, target.id) in set(config.excluded_ordered_pairs)
    base_selection = select_reference_transition(
        source.analysis,
        target.analysis,
        source_track_id=source.id,
        target_track_id=target.id,
        source_duration_sec=source.duration_sec,
        target_duration_sec=target.duration_sec,
    )
    options: list[tuple[tuple[int, int, str], Any, Any, dict, tuple[str, ...]]] = []
    context_rows: list[dict[str, Any]] = []
    for evaluation in base_selection.evaluations:
        if not (
            evaluation.eligible
            and evaluation.usable_for_performance
            and evaluation.instance is not None
        ):
            continue
        archetype = evaluation.archetype
        instance = evaluation.instance
        selector_payload = {
            "base_selector_id": base_selection.selector_id,
            "joint_archetype": archetype.value,
        }
        selection = replace(
            base_selection,
            selected_archetype=archetype,
            decision=(
                f"joint planner retained {archetype.value}: "
                f"{evaluation.performance_acceptance['rule']}"
            ),
            decision_trace=(
                *base_selection.decision_trace,
                {
                    "template": archetype.value,
                    "rule": "joint cue-local musical-context evaluation",
                    "matched": True,
                    "base_mechanical_winner": (
                        base_selection.selected_archetype.value
                        if base_selection.selected_archetype
                        else None
                    ),
                },
            ),
            selector_id="rtsj_"
            + hashlib.sha256(
                json.dumps(
                    selector_payload, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()[:16],
        )
        flow = _set_flow(
            source,
            target,
            used_track_ids=used_track_ids,
            state=set_flow_state,
            target_phase=target_phase,
            selected_archetype=archetype,
            selected_evidence=evaluation.evidence,
            config=config,
            context_calibration=context_calibration,
            source_context_sec=instance.anchors.source_end_sec,
            target_context_sec=instance.anchors.target_landing_sec,
        )
        establishment_sec = (
            None
            if prior_target_landing_sec is None
            else instance.anchors.source_start_sec - prior_target_landing_sec
        )
        establishment_pass = prior_target_landing_sec is None or (
            establishment_sec is not None
            and establishment_sec >= config.min_establishment_sec
        )
        establishment = {
            "prior_target_landing_sec": prior_target_landing_sec,
            "outgoing_source_launch_sec": instance.anchors.source_start_sec,
            "available_establishment_sec": round(establishment_sec, 6)
            if establishment_sec is not None
            else None,
            "required_minimum_sec": config.min_establishment_sec,
            "passes": establishment_pass,
        }
        reasons = list(flow.rejection_reasons)
        if excluded:
            reasons.append("ordered_pair_excluded_by_prior_human_evidence")
        if not establishment_pass:
            reasons.append("insufficient_target_establishment_before_next_source_move")
        retained = flow.passes_hard_gates and not excluded and establishment_pass
        relationship = flow.evidence["musical_role_and_set_story"]["relationship"]
        context_rows.append(
            {
                "archetype": archetype.value,
                "base_mechanical_winner": archetype
                == base_selection.selected_archetype,
                "source_cue_sec": instance.anchors.source_start_sec,
                "target_cue_sec": instance.anchors.target_landing_sec,
                "context_relationship": relationship,
                "set_flow": flow.to_dict(),
                "establishment": establishment,
                "retained": retained,
                "rejection_reasons": list(dict.fromkeys(reasons)),
            }
        )
        if retained:
            options.append(
                (
                    (
                        0 if relationship == "NATURAL_CONTINUATION" else 1,
                        0 if archetype == base_selection.selected_archetype else 1,
                        archetype.value,
                    ),
                    selection,
                    flow,
                    establishment,
                    tuple(dict.fromkeys(reasons)),
                )
            )

    if options:
        _, selection, flow, establishment, reasons = min(
            options, key=lambda item: item[0]
        )
        retained = True
    else:
        selection = base_selection
        instance = selection.selected_instance
        selected_evaluation = next(
            (
                item
                for item in selection.evaluations
                if item.archetype == selection.selected_archetype
            ),
            None,
        )
        selected_evidence = (
            selected_evaluation.evidence if selected_evaluation is not None else {}
        )
        flow = _set_flow(
            source,
            target,
            used_track_ids=used_track_ids,
            state=set_flow_state,
            target_phase=target_phase,
            selected_archetype=selection.selected_archetype,
            selected_evidence=selected_evidence,
            config=config,
            context_calibration=context_calibration,
            source_context_sec=(instance.anchors.source_end_sec if instance else None),
            target_context_sec=(
                instance.anchors.target_landing_sec if instance else None
            ),
        )
        establishment_sec = (
            None
            if prior_target_landing_sec is None or instance is None
            else instance.anchors.source_start_sec - prior_target_landing_sec
        )
        establishment_pass = prior_target_landing_sec is None or (
            establishment_sec is not None
            and establishment_sec >= config.min_establishment_sec
        )
        establishment = {
            "prior_target_landing_sec": prior_target_landing_sec,
            "outgoing_source_launch_sec": (
                instance.anchors.source_start_sec if instance else None
            ),
            "available_establishment_sec": round(establishment_sec, 6)
            if establishment_sec is not None
            else None,
            "required_minimum_sec": config.min_establishment_sec,
            "passes": establishment_pass,
        }
        reasons = list(flow.rejection_reasons)
        if excluded:
            reasons.append("ordered_pair_excluded_by_prior_human_evidence")
        if not selection.pair_transitionable:
            reasons.extend(
                selection.pair_rejection_reasons or ("pair_not_transitionable",)
            )
        if not establishment_pass:
            reasons.append("insufficient_target_establishment_before_next_source_move")
        reasons = tuple(dict.fromkeys(reasons))
        retained = False
    return JointCandidateDecision(
        current_track_id=source.id,
        candidate_track_id=target.id,
        set_flow=flow,
        transition_selection=selection,
        establishment=establishment,
        retained=retained,
        rejection_reasons=tuple(reasons),
        archetype_context_evaluations=tuple(context_rows),
    )


def _path_repetition(archetypes: tuple[str, ...]) -> tuple[int, int]:
    consecutive = 1
    maximum = 1 if archetypes else 0
    for left, right in zip(archetypes[:-1], archetypes[1:]):
        consecutive = consecutive + 1 if left == right else 1
        maximum = max(maximum, consecutive)
    return maximum, len(archetypes) - len(set(archetypes))


def plan_joint_reference_set(
    tracks: Iterable[TrackProfile],
    *,
    config: JointSetConfig = JointSetConfig(),
) -> JointReferenceSetPlan:
    """Plan exactly one bounded set by jointly selecting tracks, templates, and cues."""
    pool = tuple(sorted(tracks, key=lambda item: item.id))
    if config.track_count < 2:
        raise ValueError("joint set must contain at least two tracks")
    if len(pool) < config.track_count and not config.allow_partial_plan:
        raise ValueError("track pool is smaller than requested set")
    if len(pool) < 2:
        raise ValueError("track pool must contain at least two tracks")
    if not 2 <= config.minimum_partial_track_count <= config.track_count:
        raise ValueError(
            "minimum_partial_track_count must be between two and track_count"
        )
    if config.candidate_limit < 1:
        raise ValueError("candidate_limit must be positive")
    if len(config.set_role_sequence) != config.track_count:
        raise ValueError("set_role_sequence must contain one role per track")
    try:
        role_sequence = tuple(SetRole(item) for item in config.set_role_sequence)
    except ValueError as exc:
        raise ValueError("set_role_sequence contains an unknown role") from exc
    if role_sequence[0] != SetRole.OPEN:
        raise ValueError("set_role_sequence must begin with OPEN")
    ids = [track.id for track in pool]
    if len(ids) != len(set(ids)):
        raise ValueError("track ids must be unique")

    opening_rows = tuple(
        sorted(
            (_opening_evidence(track) for track in pool),
            key=lambda item: tuple(item["opening_rank_vector"]),
        )
    )
    opening_rank_by_id = {
        row["track_id"]: index for index, row in enumerate(opening_rows)
    }
    by_id = {track.id: track for track in pool}
    context_calibration = calibrate_musical_context(pool)
    complete: list[
        tuple[tuple[TrackProfile, ...], tuple[JointCandidateDecision, ...], tuple]
    ] = []
    partial: list[
        tuple[tuple[TrackProfile, ...], tuple[JointCandidateDecision, ...], tuple]
    ] = []
    explored: dict[str, Any] = {"openers": [], "dead_ends": []}

    def path_rank(
        path: tuple[TrackProfile, ...],
        chosen: tuple[JointCandidateDecision, ...],
    ) -> tuple:
        archetypes = tuple(
            item.transition_selection.selected_archetype.value for item in chosen
        )
        max_run, repeats = _path_repetition(archetypes)
        energies = [item.mean_energy for item in path]
        energy_jump = max(
            (abs(b - a) for a, b in zip(energies[:-1], energies[1:])), default=0.0
        )
        tempo_jump = max(
            (_tempo_delta_pct(a, b) for a, b in zip(path[:-1], path[1:])),
            default=0.0,
        )
        intentional_contrasts = sum(
            item.set_flow.evidence["musical_role_and_set_story"]["relationship"]
            == "INTENTIONAL_BRIDGEABLE_CONTRAST"
            for item in chosen
        )
        diversity_excess = max(
            0, max_run - config.preferred_max_consecutive_same_archetype
        )
        return (
            intentional_contrasts,
            round(energy_jump, 8),
            round(tempo_jump, 8),
            diversity_excess,
            repeats,
            tuple(item.id for item in path),
        )

    def search(
        path: tuple[TrackProfile, ...],
        chosen: tuple[JointCandidateDecision, ...],
        prior_landing: float | None,
        flow_state: SetFlowState,
    ) -> None:
        if len(path) == config.track_count:
            if tuple(item.id for item in path) in set(config.excluded_track_sequences):
                explored["dead_ends"].append(
                    {
                        "path": [item.id for item in path],
                        "reason": "exact_track_sequence_excluded",
                    }
                )
                return
            complete.append((path, chosen, path_rank(path, chosen)))
            return
        source = path[-1]
        candidates = [
            _evaluate_candidate(
                source,
                target,
                used_track_ids={item.id for item in path},
                prior_target_landing_sec=prior_landing,
                set_flow_state=flow_state,
                target_phase=role_sequence[len(path)],
                config=config,
                context_calibration=context_calibration,
            )
            for target in pool
            if target.id != source.id
        ]
        recent = tuple(
            item.transition_selection.selected_archetype.value for item in chosen
        )
        retained = sorted(
            (item for item in candidates if item.retained),
            key=lambda item: _candidate_key(item, recent),
        )[: config.candidate_limit]
        if not retained:
            explored["dead_ends"].append(
                {
                    "path": [item.id for item in path],
                    "candidate_table": [item.to_dict() for item in candidates],
                }
            )
            if (
                config.allow_partial_plan
                and len(path) >= config.minimum_partial_track_count
            ):
                partial.append((path, chosen, path_rank(path, chosen)))
        for candidate in retained:
            target = by_id[candidate.candidate_track_id]
            landing = candidate.transition_selection.selected_instance.anchors.target_landing_sec
            state_after = candidate.set_flow.evidence["musical_role_and_set_story"][
                "state_after"
            ]
            next_state = SetFlowState(
                phase=SetRole(state_after["phase"]),
                recent_track_ids=tuple(state_after["recent_track_ids"]),
                recent_energy=tuple(state_after["recent_energy"]),
                recent_dance_functions=tuple(state_after["recent_dance_functions"]),
                recent_rhythmic_characters=tuple(
                    state_after["recent_rhythmic_characters"]
                ),
                reliable_moods=tuple(state_after["reliable_moods"]),
                contrast_events=int(state_after["contrast_events"]),
            )
            search(path + (target,), chosen + (candidate,), landing, next_state)

    # Opening rank remains the first criterion.  Path existence is a hard gate,
    # not a hidden optimization around a hand-picked first pair.
    for row in opening_rows:
        before = len(complete)
        partial_before = len(partial)
        opener = by_id[row["track_id"]]
        search((opener,), (), None, initial_set_flow_state(opener))
        found = len(complete) > before
        opener_partials = partial[partial_before:]
        explored["openers"].append(
            {
                **row,
                "complete_path_exists": found,
                "longest_partial_track_count": max(
                    (len(item[0]) for item in opener_partials), default=0
                ),
            }
        )
        if found:
            break

    is_complete = bool(complete)
    if complete:
        path, chosen_candidates, path_rank_vector = min(
            complete, key=lambda item: item[2]
        )
    elif partial:
        # Longest valid path wins before any musical ranking evidence. No gate is
        # relaxed to manufacture the requested track count.
        path, chosen_candidates, path_rank_vector = min(
            partial,
            key=lambda item: (
                -len(item[0]),
                opening_rank_by_id[item[0][0].id],
                item[2],
            ),
        )
    else:
        raise JointSetPlanningDeadEnd(
            "no candidate path satisfies set-flow, transitionability, cue, and establishment floors",
            explored,
        )
    decisions: list[JointTransitionDecision] = []
    prior_landing = None
    flow_state = initial_set_flow_state(path[0])
    for index, (source, winner) in enumerate(zip(path[:-1], chosen_candidates), 1):
        table = tuple(
            _evaluate_candidate(
                source,
                target,
                used_track_ids={item.id for item in path[:index]},
                prior_target_landing_sec=prior_landing,
                set_flow_state=flow_state,
                target_phase=role_sequence[index],
                config=config,
                context_calibration=context_calibration,
            )
            for target in pool
            if target.id != source.id
        )
        winner = next(
            item
            for item in table
            if item.candidate_track_id == winner.candidate_track_id
        )
        selected = winner.transition_selection.selected_archetype.value
        why = (
            "set-flow hard gates passed",
            "PAIR_TRANSITIONABLE is YES",
            f"{selected} satisfies its USABLE_FOR_PERFORMANCE contract",
            "source and target cues satisfy the establishment and continuity floor",
            "won disclosed path ordering after all hard gates; performance quality was not traded for variety",
        )
        decisions.append(
            JointTransitionDecision(
                index=index,
                source_track_id=source.id,
                target_track_id=winner.candidate_track_id,
                selection=winner.transition_selection,
                candidate_table=table,
                why_this_won=why,
            )
        )
        prior_landing = (
            winner.transition_selection.selected_instance.anchors.target_landing_sec
        )
        state_after = winner.set_flow.evidence["musical_role_and_set_story"][
            "state_after"
        ]
        flow_state = SetFlowState(
            phase=SetRole(state_after["phase"]),
            recent_track_ids=tuple(state_after["recent_track_ids"]),
            recent_energy=tuple(state_after["recent_energy"]),
            recent_dance_functions=tuple(state_after["recent_dance_functions"]),
            recent_rhythmic_characters=tuple(state_after["recent_rhythmic_characters"]),
            reliable_moods=tuple(state_after["reliable_moods"]),
            contrast_events=int(state_after["contrast_events"]),
        )

    opening = {
        "selected_track_id": path[0].id,
        "selection_rule": (
            "first deterministic opening-suitability candidate with a complete hard-gated path"
            if is_complete
            else "longest hard-gated partial path after the bounded pool exhausted all complete paths"
        ),
        "path_existence_is_hard_gate": True,
        "opening_candidates": explored["openers"],
        "selected_path_rank_vector": list(path_rank_vector[:-1])
        + [list(path_rank_vector[-1])],
        "path_rank_order": [
            "fewest_intentional_contrasts after all declared-role hard gates",
            "smallest_max_energy_jump",
            "smallest_max_tempo_jump",
            "least_excess_over_preferred_consecutive_archetype_limit_after_quality_evidence",
            "fewest_repeated_archetypes_after_quality_evidence",
            "stable_track_id_tiebreak",
        ],
        "partial_path_precedence": [
            "longest_hard_gated_path",
            "best_deterministic_opening_suitability",
            "declared_path_rank_order",
        ],
        "musical_context_calibration": context_calibration.to_dict(),
    }
    completion = {
        "requested_track_count": config.track_count,
        "actual_track_count": len(path),
        "complete": is_complete,
        "hard_gates_weakened": False,
        "planning_stopped_reason": (
            None
            if is_complete
            else "bounded_candidate_pool_exhausted_without_another_hard-gated_adjacency"
        ),
        "dead_end_count": len(explored["dead_ends"]),
        "selected_terminal_dead_end": next(
            (
                item
                for item in explored["dead_ends"]
                if item.get("path") == [track.id for track in path]
            ),
            None,
        )
        if not is_complete
        else None,
    }
    payload = {
        "schema": JOINT_REFERENCE_SET_SCHEMA_VERSION,
        "tracks": [item.id for item in path],
        "transitions": [
            item.transition_selection.selector_id for item in chosen_candidates
        ],
        "config": config.__dict__,
        "completion": completion,
        "musical_context_calibration": context_calibration.to_dict(),
    }
    plan_id = (
        "jrsp_"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
    )
    return JointReferenceSetPlan(
        path,
        tuple(decisions),
        opening,
        config,
        plan_id,
        completion=completion,
    )
