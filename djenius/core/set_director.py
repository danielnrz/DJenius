"""V2 Phase 7 Set Director: plans the whole-set journey above individual handoffs.

The Candidate Composer (Phase 5) asks "what transition performances are
feasible?" and the Audition Lab (Phase 6) asks "which rendered candidate is
strongest for one handoff?". The Set Director asks a different question:
"what sequence of tracks and handoffs creates the strongest whole-set
journey?" It is additive to, and does not replace, the classic beam-search
planner in :mod:`djenius.core.planner`.

Combinatorial cost is controlled with a fixed pipeline: a cheap per-track
compatibility/arc-fit shortlist narrows which next tracks are even considered
for a given beam state, only shortlisted edges reach Phase 5 candidate
generation, only a bounded number of the resulting candidates are actually
rendered and audited by Phase 6, and every (source, target, context) audition
outcome is cached so repeated planning or shuffled-baseline comparisons never
re-render an edge already evaluated under the same context.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import random
from typing import Any, Callable, Optional

import numpy as np

from djenius.core.audition_lab import (
    AuditionConfig,
    AuditionRanking,
    audition_candidate,
    rank_auditions,
)
from djenius.core.candidate_composer import (
    CandidateComposerConfig,
    CandidateSetContext,
    TransitionCandidate,
    compose_transition_candidates,
)
from djenius.core.models import TrackProfile
from djenius.core.scorer import score_compatibility

SET_DIRECTOR_SCHEMA_VERSION = "7.0"


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canonicalize(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_canonicalize(item) for item in value]
    return value


def _mean_curve(curve: list[float]) -> float:
    return float(sum(curve) / len(curve)) if curve else 0.0


def _artist_key(track: TrackProfile) -> str:
    return (track.metadata.artist or "").strip().lower()


class SetArc:
    """Explicit set-arc identifiers understood by the Set Director.

    Kept as plain string constants (not a stdlib ``Enum``) so callers can add
    a project-specific arc label without editing this module, while the
    built-in arcs below remain first-class and fully supported.
    """

    SMOOTH = "smooth"
    WARMUP_TO_PEAK = "warmup_to_peak"
    PEAK_TIME = "peak_time"
    WAVE = "wave"
    OPEN_FORMAT = "open_format"

    ALL = (SMOOTH, WARMUP_TO_PEAK, PEAK_TIME, WAVE, OPEN_FORMAT)


def arc_energy_target(arc: str, position_fraction: float) -> float:
    """Deterministic target mean-energy in [0,1] at a fractional set position."""
    p = _clip01(position_fraction)
    if arc == SetArc.WARMUP_TO_PEAK:
        if p <= 0.75:
            return 0.22 + 0.66 * (p / 0.75)
        return 0.88 - 0.22 * ((p - 0.75) / 0.25)
    if arc == SetArc.PEAK_TIME:
        return 0.70 + 0.16 * math.sin(math.pi * p)
    if arc == SetArc.WAVE:
        cycles = 2.5
        return _clip01(0.55 + 0.28 * math.sin(2 * math.pi * cycles * p - math.pi / 2))
    if arc == SetArc.OPEN_FORMAT:
        return 0.55
    # SMOOTH and any unrecognized arc: a gentle single hump, modest movement.
    return 0.42 + 0.12 * math.sin(math.pi * p)


def _arc_target_peak_fraction(arc: str) -> float:
    if arc == SetArc.WARMUP_TO_PEAK:
        return 0.85
    return 0.5


def bpm_relationship(
    source: TrackProfile,
    target: TrackProfile,
    *,
    reset_threshold_pct: float = 12.0,
    hypothesis_match_threshold_pct: float = 8.0,
) -> dict[str, Any]:
    """Independent tempo-relationship fact for a directed track pair.

    This intentionally does not import from ``candidate_composer`` so that
    Set Director validation metrics remain independent evidence rather than a
    re-expression of internal scoring policy. A half/double (or other
    non-primary) hypothesis is only accepted when it is genuinely close;
    otherwise a large gap is reported honestly as a primary-tempo jump rather
    than the "least bad" of three still-distant hypotheses.
    """
    if source.bpm <= 0 or target.bpm <= 0:
        return {"relation": "unknown", "delta_pct": 0.0, "confidence": 0.0, "is_reset": False}
    raw_delta = abs(source.bpm - target.bpm) / source.bpm * 100.0
    best_relation, best_delta, best_confidence = (
        "primary", raw_delta, min(source.analysis.bpm_confidence, target.analysis.bpm_confidence),
    )
    for hypothesis in target.analysis.tempo_hypotheses or []:
        relation = str(hypothesis.get("relation", "primary"))
        if relation == "primary":
            continue
        hyp_bpm = float(hypothesis.get("bpm", 0.0))
        hyp_confidence = float(hypothesis.get("confidence", 0.0))
        if hyp_bpm <= 0 or hyp_confidence < 0.5:
            continue
        delta = abs(source.bpm - hyp_bpm) / source.bpm * 100.0
        if delta < best_delta and delta <= hypothesis_match_threshold_pct:
            best_relation, best_delta, best_confidence = relation, delta, hyp_confidence
    is_reset = best_relation == "primary" and best_delta > reset_threshold_pct
    return {
        "relation": best_relation,
        "delta_pct": round(best_delta, 4),
        "confidence": round(best_confidence, 4),
        "is_reset": is_reset,
    }


def _groove_delta(source: TrackProfile, target: TrackProfile) -> float:
    source_groove = source.analysis.groove_profile or {}
    target_groove = target.analysis.groove_profile or {}
    syncopation_delta = abs(
        float(source_groove.get("syncopation_index", 0.0)) - float(target_groove.get("syncopation_index", 0.0))
    )
    swing_delta = abs(float(source_groove.get("swing_ratio", 1.0)) - float(target_groove.get("swing_ratio", 1.0)))
    return _clip01(0.6 * syncopation_delta + 0.4 * min(1.0, swing_delta))


def _set_phase_for(position_fraction: float) -> str:
    if position_fraction < 0.15:
        return "OPEN"
    if position_fraction < 0.7:
        return "DEVELOP"
    if position_fraction < 0.9:
        return "PEAK"
    return "CLOSE"


def _transition_role_for(energy_delta: float) -> str:
    if energy_delta > 0.08:
        return "BUILD"
    if energy_delta < -0.08:
        return "RELEASE"
    return "CONTINUE"


@dataclass(frozen=True)
class TrackAudio:
    """Decoded audio bundle handed to Set Director edge evaluation."""

    audio: np.ndarray
    sample_rate: int
    stems: dict[str, np.ndarray] | None = None


AudioProvider = Callable[[TrackProfile], TrackAudio]


@dataclass(frozen=True)
class SetDirectorConfig:
    beam_width: int = 4
    shortlist_width: int = 4
    max_candidates_audited_per_edge: int = 4
    max_edges_to_audition: int = 400
    max_reset_budget: int = 2
    reset_threshold_pct: float = 12.0
    artist_spacing_min_tracks: int = 3
    vocal_heavy_threshold: float = 0.55
    weights: dict[str, float] = field(default_factory=lambda: {
        "handoff_quality": 0.28,
        "energy_arc_fit": 0.16,
        "bpm_journey_fit": 0.12,
        "vocal_pacing": 0.10,
        "groove_continuity": 0.08,
        "technique_diversity": 0.10,
        "artist_spacing": 0.08,
        "duration_fit": 0.04,
        "reset_budget": 0.04,
    })
    composer_config: CandidateComposerConfig = field(default_factory=CandidateComposerConfig)
    audition_config: AuditionConfig = field(default_factory=AuditionConfig)
    seed: int = 0

    EDGE_COMPONENTS = (
        "handoff_quality", "energy_arc_fit", "bpm_journey_fit", "vocal_pacing",
        "groove_continuity", "technique_diversity", "artist_spacing",
    )
    PATH_COMPONENTS = ("duration_fit", "reset_budget")

    def validate(self) -> None:
        if self.beam_width < 1:
            raise ValueError("beam_width must be >= 1")
        if self.shortlist_width < 1:
            raise ValueError("shortlist_width must be >= 1")
        if self.max_candidates_audited_per_edge < 1:
            raise ValueError("max_candidates_audited_per_edge must be >= 1")
        if self.max_edges_to_audition < 1:
            raise ValueError("max_edges_to_audition must be >= 1")
        if self.artist_spacing_min_tracks < 1:
            raise ValueError("artist_spacing_min_tracks must be >= 1")
        needed = set(self.EDGE_COMPONENTS) | set(self.PATH_COMPONENTS)
        if not needed.issubset(self.weights):
            raise ValueError(f"weights must define: {sorted(needed)}")
        if any(float(v) < 0.0 for v in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if sum(self.weights.values()) <= 0:
            raise ValueError("weights must sum to a positive total")
        self.composer_config.validate()
        self.audition_config.validate()

    def effective_max_reset_budget(self, arc: str) -> int:
        if arc == SetArc.OPEN_FORMAT:
            return self.max_reset_budget + 2
        if arc == SetArc.SMOOTH:
            return max(0, self.max_reset_budget - 1)
        return self.max_reset_budget


@dataclass(frozen=True)
class HandoffSummary:
    """Cached bounded-audition outcome for one directed track pair."""

    source_track_id: str
    target_track_id: str
    context_key: str
    candidate_count: int
    rejected_count: int
    audited_count: int
    survivor_count: int
    hard_rejected_count: int
    selected_candidate_id: str | None
    selected_family: str | None
    selected_score: float
    ranking: AuditionRanking | None = None
    composition_diagnostics: dict[str, Any] = field(default_factory=dict)
    candidates: dict[str, TransitionCandidate] = field(default_factory=dict)
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "context_key": self.context_key,
            "candidate_count": self.candidate_count,
            "rejected_count": self.rejected_count,
            "audited_count": self.audited_count,
            "survivor_count": self.survivor_count,
            "hard_rejected_count": self.hard_rejected_count,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_family": self.selected_family,
            "selected_score": round(float(self.selected_score), 9),
            "cache_hit": self.cache_hit,
            "composition_diagnostics": _canonicalize(self.composition_diagnostics),
        }


class EdgeAuditionCache:
    """Deterministic (source, target, context) -> HandoffSummary cache."""

    def __init__(self) -> None:
        self._store: dict[str, HandoffSummary] = {}

    def get(self, key: str) -> HandoffSummary | None:
        return self._store.get(key)

    def put(self, key: str, value: HandoffSummary) -> None:
        self._store[key] = value

    def __len__(self) -> int:
        return len(self._store)


def edge_cache_key(
    source_id: str,
    target_id: str,
    *,
    transition_role: str,
    set_phase: str,
    energy_goal: float,
    recent_families: tuple[str, ...],
    composer_config: CandidateComposerConfig,
    audition_config: AuditionConfig,
    seed: int,
) -> str:
    from dataclasses import asdict

    payload = {
        "source": source_id,
        "target": target_id,
        "role": transition_role,
        "phase": set_phase,
        "energy_goal": round(float(energy_goal), 3),
        "recent_families": list(recent_families[-2:]),
        "composer_config": asdict(composer_config),
        "audition_config": asdict(audition_config),
        "seed": seed,
    }
    encoded = json.dumps(_canonicalize(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


@dataclass
class SetDirectorComputeStats:
    edges_considered: int = 0
    edges_shortlisted: int = 0
    candidates_generated: int = 0
    candidates_rendered: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    budget_exhausted_edges: int = 0

    def to_dict(self) -> dict[str, int]:
        return dict(self.__dict__)


def evaluate_edge(
    source: TrackProfile,
    target: TrackProfile,
    *,
    audio_provider: AudioProvider,
    set_context: CandidateSetContext,
    config: SetDirectorConfig,
    cache: EdgeAuditionCache,
    stats: SetDirectorComputeStats,
) -> HandoffSummary:
    """Return the cached or freshly bounded-audited handoff summary for an edge."""
    key = edge_cache_key(
        source.id, target.id,
        transition_role=set_context.transition_role, set_phase=set_context.set_phase,
        energy_goal=set_context.energy_goal, recent_families=set_context.previous_technique_families,
        composer_config=config.composer_config, audition_config=config.audition_config, seed=config.seed,
    )
    cached = cache.get(key)
    if cached is not None:
        stats.cache_hits += 1
        return replace(cached, cache_hit=True)
    stats.cache_misses += 1

    if stats.candidates_rendered >= config.max_edges_to_audition * config.max_candidates_audited_per_edge:
        stats.budget_exhausted_edges += 1
        summary = HandoffSummary(
            source_track_id=source.id, target_track_id=target.id, context_key=key,
            candidate_count=0, rejected_count=0, audited_count=0, survivor_count=0,
            hard_rejected_count=0, selected_candidate_id=None, selected_family=None,
            selected_score=float(score_compatibility(source, target).overall_score) * 0.5,
            ranking=None, composition_diagnostics={"budget_exhausted": True},
        )
        cache.put(key, summary)
        return summary

    composition = compose_transition_candidates(
        source, target, set_context=set_context, config=config.composer_config, seed=config.seed,
    )
    stats.candidates_generated += len(composition.candidates)
    if not composition.candidates:
        summary = HandoffSummary(
            source_track_id=source.id, target_track_id=target.id, context_key=key,
            candidate_count=0, rejected_count=len(composition.rejected), audited_count=0,
            survivor_count=0, hard_rejected_count=0, selected_candidate_id=None,
            selected_family=None, selected_score=0.0, ranking=None,
            composition_diagnostics=dict(composition.diagnostics),
        )
        cache.put(key, summary)
        return summary

    ordered_candidates = sorted(composition.candidates, key=lambda item: item.candidate_id)
    to_audit = ordered_candidates[: config.max_candidates_audited_per_edge]
    candidates_by_id = {item.candidate_id: item for item in to_audit}

    source_bundle = audio_provider(source)
    target_bundle = audio_provider(target)
    if source_bundle.sample_rate != target_bundle.sample_rate:
        raise ValueError("Set Director requires source/target audio at the same sample rate")

    auditions = [
        audition_candidate(
            candidate, source_bundle.audio, target_bundle.audio, source_bundle.sample_rate,
            config=config.audition_config, source_stems=source_bundle.stems, target_stems=target_bundle.stems,
        )
        for candidate in to_audit
    ]
    stats.candidates_rendered += len(auditions)
    ranking = rank_auditions(auditions, config=config.audition_config)
    selected = next((item for item in ranking.auditions if item.selected), None)
    summary = HandoffSummary(
        source_track_id=source.id, target_track_id=target.id, context_key=key,
        candidate_count=len(composition.candidates), rejected_count=len(composition.rejected),
        audited_count=len(auditions), survivor_count=ranking.survivor_count,
        hard_rejected_count=ranking.rejected_count,
        selected_candidate_id=selected.candidate_id if selected else None,
        selected_family=candidates_by_id[selected.candidate_id].technique_family if selected else None,
        selected_score=float(selected.final_score) if selected else 0.0,
        ranking=ranking,
        composition_diagnostics=dict(composition.diagnostics),
        candidates=candidates_by_id,
    )
    cache.put(key, summary)
    return summary


def _estimate_overlap_sec(source: TrackProfile, target: TrackProfile) -> float:
    avg_bpm = max((source.bpm + target.bpm) / 2.0, 60.0)
    bar_duration = 4 * 60.0 / avg_bpm
    return min(bar_duration * 16, target.duration_sec * 0.5, source.duration_sec * 0.5)


def _shortlist_next_tracks(
    source: TrackProfile,
    remaining: list[TrackProfile],
    *,
    arc: str,
    position_fraction: float,
    next_position_fraction: float,
    artist_history: tuple[str, ...],
    config: SetDirectorConfig,
) -> list[TrackProfile]:
    """Cheap, audio-free pre-filter bounding how many edges reach real audition."""
    desired_delta = arc_energy_target(arc, next_position_fraction) - arc_energy_target(arc, position_fraction)
    window = artist_history[-(max(config.artist_spacing_min_tracks - 1, 0)):]
    scored = []
    for track in remaining:
        compat = score_compatibility(source, track).overall_score
        actual_delta = track.mean_energy - source.mean_energy
        energy_fit = 1.0 - min(1.0, abs(desired_delta - actual_delta))
        artist = _artist_key(track)
        artist_penalty = 0.35 if artist and artist in window else 0.0
        score = 0.55 * compat + 0.35 * energy_fit + 0.10 - artist_penalty
        scored.append((score, track))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [track for _, track in scored[: max(1, config.shortlist_width)]]


@dataclass(frozen=True)
class SetDirectorEdgeChoice:
    source_track_id: str
    target_track_id: str
    handoff: HandoffSummary
    component_scores: dict[str, float]
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "handoff": self.handoff.to_dict(),
            "component_scores": {k: round(float(v), 6) for k, v in self.component_scores.items()},
            "explanation": self.explanation,
        }


def _score_edge_components(
    *,
    source: TrackProfile,
    target: TrackProfile,
    handoff: HandoffSummary,
    arc: str,
    next_position_fraction: float,
    artist_history: tuple[str, ...],
    technique_history: tuple[str, ...],
    config: SetDirectorConfig,
) -> dict[str, float]:
    components: dict[str, float] = {
        "handoff_quality": float(handoff.selected_score) if handoff.selected_candidate_id else 0.0,
    }

    target_energy_goal = arc_energy_target(arc, next_position_fraction)
    components["energy_arc_fit"] = 1.0 - min(1.0, abs(target.mean_energy - target_energy_goal))

    relation = bpm_relationship(source, target, reset_threshold_pct=config.reset_threshold_pct)
    components["bpm_journey_fit"] = 1.0 - min(1.0, relation["delta_pct"] / 25.0)

    source_vocal = _mean_curve(source.analysis.vocal_activity_curve)
    target_vocal = _mean_curve(target.analysis.vocal_activity_curve)
    both_vocal_heavy = source_vocal >= config.vocal_heavy_threshold and target_vocal >= config.vocal_heavy_threshold
    components["vocal_pacing"] = 0.3 if both_vocal_heavy else 1.0

    groove_delta_value = _groove_delta(source, target)
    if arc == SetArc.OPEN_FORMAT:
        components["groove_continuity"] = min(1.0, 0.4 + groove_delta_value)
    else:
        components["groove_continuity"] = 1.0 - groove_delta_value

    family = handoff.selected_family
    recent = technique_history[-3:]
    repeats = recent.count(family) if family else 0
    components["technique_diversity"] = 1.0 if not family else max(0.0, 1.0 - 0.4 * repeats)

    artist = _artist_key(target)
    window = artist_history[-(max(config.artist_spacing_min_tracks - 1, 0)):]
    components["artist_spacing"] = 0.2 if artist and artist in window else 1.0

    return components


def _explain_edge(source: TrackProfile, target: TrackProfile, handoff: HandoffSummary, components: dict[str, float]) -> str:
    family = handoff.selected_family or "no_survivor"
    return (
        f"{source.id} -> {target.id}: selected {family} "
        f"(score={handoff.selected_score:.3f}, {handoff.survivor_count}/{handoff.audited_count} survived); "
        f"energy_arc_fit={components.get('energy_arc_fit', 0.0):.2f} "
        f"bpm_journey_fit={components.get('bpm_journey_fit', 0.0):.2f} "
        f"artist_spacing={components.get('artist_spacing', 0.0):.2f}"
    )


@dataclass
class _BeamState:
    track_ids: tuple[str, ...]
    duration_sec: float
    technique_history: tuple[str, ...]
    artist_history: tuple[str, ...]
    reset_count: int
    edge_total: float
    edges: tuple[SetDirectorEdgeChoice, ...]


def _avg_edge_score(state: _BeamState) -> float:
    return state.edge_total / len(state.edges) if state.edges else 0.0


def _beam_sort_key(state: _BeamState):
    return (-_avg_edge_score(state), state.track_ids)


@dataclass(frozen=True)
class SetDirectorPlan:
    arc: str = SetArc.SMOOTH
    track_ids: tuple[str, ...] = ()
    edges: tuple[SetDirectorEdgeChoice, ...] = ()
    total_score: float = 0.0
    component_totals: dict[str, float] = field(default_factory=dict)
    total_duration_sec: float = 0.0
    compute_stats: dict[str, int] = field(default_factory=dict)
    human_readable_reasons: tuple[str, ...] = ()
    schema_version: str = SET_DIRECTOR_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "arc": self.arc,
            "track_ids": list(self.track_ids),
            "edges": [item.to_dict() for item in self.edges],
            "total_score": round(float(self.total_score), 9),
            "component_totals": {k: round(float(v), 6) for k, v in self.component_totals.items()},
            "total_duration_sec": round(float(self.total_duration_sec), 3),
            "compute_stats": dict(self.compute_stats),
            "human_readable_reasons": list(self.human_readable_reasons),
        }


def plan_set_v2(
    tracks: list[TrackProfile],
    *,
    audio_provider: AudioProvider,
    target_duration_sec: float = 1800.0,
    arc: str = SetArc.SMOOTH,
    config: Optional[SetDirectorConfig] = None,
    cache: Optional[EdgeAuditionCache] = None,
    max_tracks: Optional[int] = None,
) -> SetDirectorPlan:
    """Plan a whole-set track order and per-handoff technique using bounded audition.

    Deterministic: identical tracks, arc, config, and cache contents always
    produce an identical plan. No randomness is used for ordering decisions;
    ``config.seed`` only salts Phase 5 candidate-ID generation.
    """
    config = config or SetDirectorConfig()
    config.validate()
    cache = cache if cache is not None else EdgeAuditionCache()
    stats = SetDirectorComputeStats()

    if len(tracks) < 2:
        return SetDirectorPlan(
            arc=arc,
            track_ids=tuple(track.id for track in tracks),
            total_duration_sec=sum(track.duration_sec for track in tracks),
            compute_stats=stats.to_dict(),
            human_readable_reasons=("Fewer than two tracks are available; there are no transitions to plan.",),
        )

    by_id = {track.id: track for track in tracks}
    effective_max_tracks = max_tracks or len(tracks)
    if effective_max_tracks < 2:
        effective_max_tracks = 2

    start_target_energy = arc_energy_target(arc, 0.0)

    def start_key(track: TrackProfile) -> tuple[float, str]:
        return (-(1.0 - abs(track.mean_energy - start_target_energy)), track.id)

    opener_pool = sorted(tracks, key=start_key)[: max(1, config.beam_width)]
    beams: list[_BeamState] = [
        _BeamState(
            track_ids=(track.id,),
            duration_sec=track.duration_sec,
            technique_history=(),
            artist_history=((_artist_key(track),) if _artist_key(track) else ()),
            reset_count=0,
            edge_total=0.0,
            edges=(),
        )
        for track in opener_pool
    ]
    finished: list[_BeamState] = []

    for _ in range(effective_max_tracks - 1):
        expanded: list[_BeamState] = []
        for state in beams:
            if len(state.track_ids) >= effective_max_tracks or state.duration_sec >= target_duration_sec:
                finished.append(state)
                continue
            source = by_id[state.track_ids[-1]]
            remaining = [track for track in tracks if track.id not in state.track_ids]
            if not remaining:
                finished.append(state)
                continue

            position_fraction = (len(state.track_ids) - 1) / max(effective_max_tracks - 1, 1)
            next_position_fraction = len(state.track_ids) / max(effective_max_tracks - 1, 1)
            shortlisted = _shortlist_next_tracks(
                source, remaining, arc=arc, position_fraction=position_fraction,
                next_position_fraction=next_position_fraction, artist_history=state.artist_history, config=config,
            )
            stats.edges_considered += len(remaining)
            stats.edges_shortlisted += len(shortlisted)

            for target in shortlisted:
                energy_goal = arc_energy_target(arc, next_position_fraction) - arc_energy_target(arc, position_fraction)
                set_context = CandidateSetContext(
                    set_phase=_set_phase_for(next_position_fraction),
                    transition_role=_transition_role_for(energy_goal),
                    energy_goal=round(energy_goal, 3),
                    previous_technique_families=state.technique_history,
                    avoid_recent_repeats=True,
                    allow_tempo_reset=state.reset_count < config.effective_max_reset_budget(arc),
                )
                handoff = evaluate_edge(
                    source, target, audio_provider=audio_provider, set_context=set_context,
                    config=config, cache=cache, stats=stats,
                )
                components = _score_edge_components(
                    source=source, target=target, handoff=handoff, arc=arc,
                    next_position_fraction=next_position_fraction, artist_history=state.artist_history,
                    technique_history=state.technique_history, config=config,
                )
                edge_score = sum(components[name] * config.weights.get(name, 0.0) for name in components)
                relation = bpm_relationship(source, target, reset_threshold_pct=config.reset_threshold_pct)
                new_technique_history = state.technique_history
                if handoff.selected_family:
                    new_technique_history = (state.technique_history + (handoff.selected_family,))[-4:]
                new_artist = _artist_key(target)
                new_artist_history = state.artist_history + ((new_artist,) if new_artist else ())
                overlap = _estimate_overlap_sec(source, target)
                expanded.append(_BeamState(
                    track_ids=state.track_ids + (target.id,),
                    duration_sec=state.duration_sec + target.duration_sec - overlap,
                    technique_history=new_technique_history,
                    artist_history=new_artist_history,
                    reset_count=state.reset_count + (1 if relation["is_reset"] else 0),
                    edge_total=state.edge_total + edge_score,
                    edges=state.edges + (SetDirectorEdgeChoice(
                        source.id, target.id, handoff, components,
                        _explain_edge(source, target, handoff, components),
                    ),),
                ))
        if not expanded:
            break
        expanded.sort(key=_beam_sort_key)
        beams = expanded[: config.beam_width]

    finished.extend(beams)
    if not finished:
        # Every remaining track was already used by every beam (small library).
        finished = beams or [_BeamState(
            track_ids=(opener_pool[0].id,), duration_sec=opener_pool[0].duration_sec,
            technique_history=(), artist_history=(), reset_count=0, edge_total=0.0, edges=(),
        )]

    def final_key(state: _BeamState):
        n_edges = max(len(state.edges), 1)
        avg_edge = state.edge_total / n_edges
        duration_fit = 1.0 - min(1.0, abs(state.duration_sec - target_duration_sec) / max(target_duration_sec, 1.0))
        effective_budget = config.effective_max_reset_budget(arc)
        excess = max(0, state.reset_count - effective_budget)
        reset_budget_component = max(0.0, 1.0 - 0.3 * excess)
        final_score = (
            avg_edge
            + duration_fit * config.weights["duration_fit"]
            + reset_budget_component * config.weights["reset_budget"]
        )
        return (-final_score, state.track_ids)

    finished.sort(key=final_key)
    best = finished[0]

    component_totals: dict[str, float] = {}
    if best.edges:
        for name in SetDirectorConfig.EDGE_COMPONENTS:
            values = [edge.component_scores.get(name, 0.0) for edge in best.edges]
            component_totals[name] = sum(values) / len(values)
    else:
        for name in SetDirectorConfig.EDGE_COMPONENTS:
            component_totals[name] = 0.0
    duration_fit_final = 1.0 - min(1.0, abs(best.duration_sec - target_duration_sec) / max(target_duration_sec, 1.0))
    effective_budget = config.effective_max_reset_budget(arc)
    reset_excess = max(0, best.reset_count - effective_budget)
    component_totals["duration_fit"] = duration_fit_final
    component_totals["reset_budget"] = max(0.0, 1.0 - 0.3 * reset_excess)

    total_score = (
        _avg_edge_score(best)
        + component_totals["duration_fit"] * config.weights["duration_fit"]
        + component_totals["reset_budget"] * config.weights["reset_budget"]
    )

    reasons = [
        f"Arc '{arc}' produced a {len(best.track_ids)}-track set "
        f"({best.duration_sec:.0f}s vs {target_duration_sec:.0f}s target) with {len(best.edges)} handoffs.",
    ]
    if reset_excess > 0:
        reasons.append(
            f"Used {best.reset_count} deliberate tempo resets, {reset_excess} over the "
            f"configured budget of {effective_budget} for this arc, because no lower-cost option remained."
        )

    return SetDirectorPlan(
        arc=arc,
        track_ids=best.track_ids,
        edges=best.edges,
        total_score=total_score,
        component_totals=component_totals,
        total_duration_sec=best.duration_sec,
        compute_stats=stats.to_dict(),
        human_readable_reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class SetQualityMetrics:
    """Independently observable set-quality facts, not the internal weighted score.

    Used both to describe a Set Director plan and to describe a shuffled
    baseline ordering of the same track pool, so the two can be compared
    without evaluating the shuffled order against Set Director's own
    objective (which would be circular validation).
    """

    energy_arc_error: float
    peak_position_fraction: float
    peak_placement_error: float
    mean_bpm_jump_pct: float
    max_bpm_jump_pct: float
    reset_edge_count: int
    consecutive_vocal_heavy_count: int
    dominant_technique_share: float
    max_technique_run: int
    artist_spacing_violations: int
    viable_audition_edge_rate: float
    mean_selected_audition_score: float
    hard_rejection_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            key: (round(value, 6) if isinstance(value, float) else value)
            for key, value in self.__dict__.items()
        }


def measure_set_quality(
    tracks: list[TrackProfile],
    edges: tuple[SetDirectorEdgeChoice, ...],
    arc: str,
    *,
    vocal_heavy_threshold: float = 0.55,
    artist_spacing_min_tracks: int = 3,
) -> SetQualityMetrics:
    n = len(tracks)
    if n == 0:
        return SetQualityMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0, 0, 0, 0.0, 0.0, 0.0)

    energies = [track.mean_energy for track in tracks]
    targets = [arc_energy_target(arc, i / max(n - 1, 1)) for i in range(n)]
    energy_arc_error = math.sqrt(sum((e - g) ** 2 for e, g in zip(energies, targets)) / n)
    peak_index = max(range(n), key=lambda i: energies[i])
    peak_position_fraction = peak_index / max(n - 1, 1)
    peak_placement_error = abs(peak_position_fraction - _arc_target_peak_fraction(arc))

    jumps: list[float] = []
    reset_count = 0
    for a, b in zip(tracks, tracks[1:]):
        relation = bpm_relationship(a, b)
        jumps.append(relation["delta_pct"])
        if relation["is_reset"]:
            reset_count += 1
    mean_jump = sum(jumps) / len(jumps) if jumps else 0.0
    max_jump = max(jumps) if jumps else 0.0

    vocal_means = [_mean_curve(track.analysis.vocal_activity_curve) for track in tracks]
    consecutive_vocal_heavy = sum(
        1 for a, b in zip(vocal_means, vocal_means[1:])
        if a >= vocal_heavy_threshold and b >= vocal_heavy_threshold
    )

    families = [edge.handoff.selected_family for edge in edges if edge.handoff.selected_family]
    dominant_share = 0.0
    max_run = 0
    if families:
        counts = Counter(families)
        dominant_share = max(counts.values()) / len(families)
        run = best_run = 1
        for prev, cur in zip(families, families[1:]):
            run = run + 1 if cur == prev else 1
            best_run = max(best_run, run)
        max_run = best_run

    artist_violations = 0
    history: list[str] = []
    for track in tracks:
        artist = _artist_key(track)
        if artist:
            window = history[-(artist_spacing_min_tracks - 1):] if artist_spacing_min_tracks > 1 else []
            if artist in window:
                artist_violations += 1
        history.append(artist)

    if edges:
        viable_rate = sum(1 for edge in edges if edge.handoff.survivor_count > 0) / len(edges)
        selected_scores = [edge.handoff.selected_score for edge in edges if edge.handoff.selected_candidate_id]
        mean_selected = sum(selected_scores) / len(selected_scores) if selected_scores else 0.0
        hard_rejection_rates = [
            edge.handoff.hard_rejected_count / edge.handoff.audited_count
            for edge in edges if edge.handoff.audited_count > 0
        ]
        hard_rejection_rate = sum(hard_rejection_rates) / len(hard_rejection_rates) if hard_rejection_rates else 0.0
    else:
        viable_rate = 0.0
        mean_selected = 0.0
        hard_rejection_rate = 0.0

    return SetQualityMetrics(
        energy_arc_error=energy_arc_error,
        peak_position_fraction=peak_position_fraction,
        peak_placement_error=peak_placement_error,
        mean_bpm_jump_pct=mean_jump,
        max_bpm_jump_pct=max_jump,
        reset_edge_count=reset_count,
        consecutive_vocal_heavy_count=consecutive_vocal_heavy,
        dominant_technique_share=dominant_share,
        max_technique_run=max_run,
        artist_spacing_violations=artist_violations,
        viable_audition_edge_rate=viable_rate,
        mean_selected_audition_score=mean_selected,
        hard_rejection_rate=hard_rejection_rate,
    )


def compare_to_shuffled_baselines(
    tracks: list[TrackProfile],
    edges: tuple[SetDirectorEdgeChoice, ...],
    arc: str,
    *,
    audio_provider: AudioProvider,
    config: Optional[SetDirectorConfig] = None,
    cache: Optional[EdgeAuditionCache] = None,
    shuffle_count: int = 20,
    seed: int = 0,
) -> dict[str, Any]:
    """Compare a planned set against many seeded shuffled orderings of the same pool.

    Shuffled orderings are audited with a neutral (no technique-memory-chain)
    context so their edge cache keys collapse to plain (source, target) pairs;
    this keeps the baseline gate's compute bounded even for many shuffles,
    since repeated pairs across shuffles are cache hits.
    """
    config = config or SetDirectorConfig()
    cache = cache if cache is not None else EdgeAuditionCache()
    stats = SetDirectorComputeStats()
    planned_metrics = measure_set_quality(
        tracks, edges, arc,
        vocal_heavy_threshold=config.vocal_heavy_threshold,
        artist_spacing_min_tracks=config.artist_spacing_min_tracks,
    )

    neutral_context = CandidateSetContext(
        set_phase="DEVELOP", transition_role="CONTINUE", energy_goal=0.0,
        previous_technique_families=(), avoid_recent_repeats=False, allow_tempo_reset=True,
    )

    shuffled_metrics: list[SetQualityMetrics] = []
    for i in range(shuffle_count):
        order = list(tracks)
        random.Random(seed * 1_000_003 + i).shuffle(order)
        shuffled_edges = []
        for a, b in zip(order, order[1:]):
            handoff = evaluate_edge(
                a, b, audio_provider=audio_provider, set_context=neutral_context,
                config=config, cache=cache, stats=stats,
            )
            shuffled_edges.append(SetDirectorEdgeChoice(a.id, b.id, handoff, {}))
        shuffled_metrics.append(measure_set_quality(
            order, tuple(shuffled_edges), arc,
            vocal_heavy_threshold=config.vocal_heavy_threshold,
            artist_spacing_min_tracks=config.artist_spacing_min_tracks,
        ))

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    baseline = {
        "shuffle_count": shuffle_count,
        "mean_energy_arc_error": mean([m.energy_arc_error for m in shuffled_metrics]),
        "mean_peak_placement_error": mean([m.peak_placement_error for m in shuffled_metrics]),
        "mean_bpm_jump_pct": mean([m.mean_bpm_jump_pct for m in shuffled_metrics]),
        "mean_reset_edge_count": mean([m.reset_edge_count for m in shuffled_metrics]),
        "mean_consecutive_vocal_heavy_count": mean([m.consecutive_vocal_heavy_count for m in shuffled_metrics]),
        "mean_dominant_technique_share": mean([m.dominant_technique_share for m in shuffled_metrics]),
        "mean_artist_spacing_violations": mean([m.artist_spacing_violations for m in shuffled_metrics]),
        "mean_viable_audition_edge_rate": mean([m.viable_audition_edge_rate for m in shuffled_metrics]),
        "mean_selected_audition_score": mean([m.mean_selected_audition_score for m in shuffled_metrics]),
        "mean_hard_rejection_rate": mean([m.hard_rejection_rate for m in shuffled_metrics]),
    }
    return {
        "planned": planned_metrics.to_dict(),
        "shuffled_baseline": baseline,
        "compute_stats": stats.to_dict(),
        "planned_beats_baseline": {
            "energy_arc_error": planned_metrics.energy_arc_error <= baseline["mean_energy_arc_error"],
            "peak_placement_error": planned_metrics.peak_placement_error <= baseline["mean_peak_placement_error"],
            "artist_spacing_violations": planned_metrics.artist_spacing_violations <= baseline["mean_artist_spacing_violations"],
            "viable_audition_edge_rate": planned_metrics.viable_audition_edge_rate >= baseline["mean_viable_audition_edge_rate"],
            "mean_selected_audition_score": planned_metrics.mean_selected_audition_score >= baseline["mean_selected_audition_score"],
        },
    }
