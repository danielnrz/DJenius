"""Thin joint track-and-transition planner for the reference-backed pilot.

This module is deliberately separate from the legacy Set Director, Candidate
Composer, and Audition Lab.  A next track is admissible only when the frozen
reference selector can also supply a usable F/C3/B8/D2 performance and cues.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable

import numpy as np

from djenius.core.models import TrackProfile
from djenius.core.reference_selector import (
    ReferenceTransitionSelection,
    select_reference_transition,
)
from djenius.utils.camelot import score_key_compatibility


JOINT_REFERENCE_SET_SCHEMA_VERSION = "joint-reference-set-1"


@dataclass(frozen=True)
class JointSetConfig:
    track_count: int = 4
    candidate_limit: int = 8
    min_establishment_sec: float = 30.0
    opening_establishment_sec: float = 45.0
    closing_establishment_sec: float = 45.0
    max_energy_jump: float = 0.22
    preferred_max_consecutive_same_archetype: int = 2
    excluded_ordered_pairs: tuple[tuple[str, str], ...] = ()


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
                "excluded_ordered_pairs": [
                    list(item) for item in self.config.excluded_ordered_pairs
                ],
            },
            "transitions": [item.to_dict() for item in self.transitions],
        }


class JointSetPlanningDeadEnd(RuntimeError):
    """Raised when no four-track path clears every performance hard gate."""

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
    max_energy_jump: float,
) -> SetFlowEvaluation:
    energy_change = float(target.mean_energy - source.mean_energy)
    tempo_delta = _tempo_delta_pct(source, target)
    harmonic = score_key_compatibility(source.camelot, target.camelot)
    same_artist = bool(_artist(source) and _artist(source) == _artist(target))
    hard_gates = {
        "target_not_already_used": target.id not in used_track_ids,
        "different_track": source.id != target.id,
        "energy_jump_within_pilot_bound": abs(energy_change) <= max_energy_jump,
        "artist_not_immediately_repeated": not same_artist,
        "analysis_confidence_usable": min(
            source.analysis.analysis_confidence,
            target.analysis.analysis_confidence,
        )
        >= 0.75,
    }
    rejection = tuple(name for name, passed in hard_gates.items() if not passed)
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
        "genre_or_style_evidence": "not available in deterministic TrackAnalysis",
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
        all(hard_gates.values()), hard_gates, evidence, ranking, rejection
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
    return {
        "track_id": track.id,
        "opening_section": first_section,
        "first_30_sec_vocal_coverage": round(float(np.clip(early_vocal, 0, 1)), 4),
        "mean_energy": round(track.mean_energy, 4),
        "bpm": round(track.bpm, 4),
        "analysis_confidence": round(track.analysis.analysis_confidence, 4),
        "opening_rank_vector": [
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
    # This is a disclosed lexicographic ordering, not a weighted compatibility score.
    return (
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
    config: JointSetConfig,
) -> JointCandidateDecision:
    flow = _set_flow(
        source,
        target,
        used_track_ids=used_track_ids,
        max_energy_jump=config.max_energy_jump,
    )
    excluded = (source.id, target.id) in set(config.excluded_ordered_pairs)
    selection = select_reference_transition(
        source.analysis,
        target.analysis,
        source_track_id=source.id,
        target_track_id=target.id,
        source_duration_sec=source.duration_sec,
        target_duration_sec=target.duration_sec,
    )
    instance = selection.selected_instance
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
        "outgoing_source_launch_sec": instance.anchors.source_start_sec
        if instance
        else None,
        "available_establishment_sec": round(establishment_sec, 6)
        if establishment_sec is not None
        else None,
        "required_minimum_sec": config.min_establishment_sec,
        "passes": establishment_pass,
    }
    reasons = list(flow.rejection_reasons)
    if excluded:
        reasons.append("ordered_pair_reserved_by_prior_listening_gate")
    if not selection.pair_transitionable:
        reasons.extend(selection.pair_rejection_reasons or ("pair_not_transitionable",))
    if not establishment_pass:
        reasons.append("insufficient_target_establishment_before_next_source_move")
    retained = (
        flow.passes_hard_gates
        and not excluded
        and selection.pair_transitionable
        and establishment_pass
    )
    return JointCandidateDecision(
        current_track_id=source.id,
        candidate_track_id=target.id,
        set_flow=flow,
        transition_selection=selection,
        establishment=establishment,
        retained=retained,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
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
    if len(pool) < config.track_count:
        raise ValueError("track pool is smaller than requested set")
    if config.candidate_limit < 1:
        raise ValueError("candidate_limit must be positive")
    ids = [track.id for track in pool]
    if len(ids) != len(set(ids)):
        raise ValueError("track ids must be unique")

    opening_rows = tuple(
        sorted(
            (_opening_evidence(track) for track in pool),
            key=lambda item: tuple(item["opening_rank_vector"]),
        )
    )
    by_id = {track.id: track for track in pool}
    complete: list[
        tuple[tuple[TrackProfile, ...], tuple[JointCandidateDecision, ...], tuple]
    ] = []
    explored: dict[str, Any] = {"openers": [], "dead_ends": []}

    def search(
        path: tuple[TrackProfile, ...],
        chosen: tuple[JointCandidateDecision, ...],
        prior_landing: float | None,
    ) -> None:
        if len(path) == config.track_count:
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
            diversity_excess = max(
                0, max_run - config.preferred_max_consecutive_same_archetype
            )
            key = (
                round(energy_jump, 8),
                round(tempo_jump, 8),
                diversity_excess,
                repeats,
                tuple(item.id for item in path),
            )
            complete.append((path, chosen, key))
            return
        source = path[-1]
        candidates = [
            _evaluate_candidate(
                source,
                target,
                used_track_ids={item.id for item in path},
                prior_target_landing_sec=prior_landing,
                config=config,
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
        for candidate in retained:
            target = by_id[candidate.candidate_track_id]
            landing = candidate.transition_selection.selected_instance.anchors.target_landing_sec
            search(path + (target,), chosen + (candidate,), landing)

    # Opening rank remains the first criterion.  Path existence is a hard gate,
    # not a hidden optimization around a hand-picked first pair.
    for row in opening_rows:
        before = len(complete)
        opener = by_id[row["track_id"]]
        search((opener,), (), None)
        found = len(complete) > before
        explored["openers"].append({**row, "complete_path_exists": found})
        if found:
            break

    if not complete:
        raise JointSetPlanningDeadEnd(
            "no candidate path satisfies set-flow, transitionability, cue, and establishment floors",
            explored,
        )
    path, chosen_candidates, path_rank = min(complete, key=lambda item: item[2])
    decisions: list[JointTransitionDecision] = []
    prior_landing = None
    for index, (source, winner) in enumerate(zip(path[:-1], chosen_candidates), 1):
        table = tuple(
            _evaluate_candidate(
                source,
                target,
                used_track_ids={item.id for item in path[:index]},
                prior_target_landing_sec=prior_landing,
                config=config,
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

    opening = {
        "selected_track_id": path[0].id,
        "selection_rule": "first deterministic opening-suitability candidate with a complete hard-gated path",
        "path_existence_is_hard_gate": True,
        "opening_candidates": explored["openers"],
        "selected_path_rank_vector": list(path_rank[:-1]) + [list(path_rank[-1])],
        "path_rank_order": [
            "smallest_max_energy_jump",
            "smallest_max_tempo_jump",
            "least_excess_over_preferred_consecutive_archetype_limit_after_quality_evidence",
            "fewest_repeated_archetypes_after_quality_evidence",
            "stable_track_id_tiebreak",
        ],
    }
    payload = {
        "schema": JOINT_REFERENCE_SET_SCHEMA_VERSION,
        "tracks": [item.id for item in path],
        "transitions": [
            item.transition_selection.selector_id for item in chosen_candidates
        ],
        "config": config.__dict__,
    }
    plan_id = (
        "jrsp_"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
    )
    return JointReferenceSetPlan(path, tuple(decisions), opening, config, plan_id)
