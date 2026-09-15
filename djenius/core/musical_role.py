"""Interpretable track-role and short-set-flow evidence.

The profile combines existing acoustic analysis with optional local semantic
and lyric estimates.  Unreliable semantic groups remain explicitly unknown;
they are never promoted into mood facts merely to make a planning decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any

import numpy as np

from djenius.core.models import TrackProfile
from djenius.core.reference_templates import ReferenceArchetype
from djenius.core.semantic import distribution_similarity
from djenius.utils.camelot import score_key_compatibility


MUSICAL_ROLE_SCHEMA_VERSION = "musical-role-2"
SEMANTIC_RELIABILITY_FLOOR = 0.55


@dataclass(frozen=True)
class MusicalContextCalibration:
    """Unlabelled, pool-relative bands for the existing local descriptors.

    These are distribution bands, not human-label-fitted success thresholds.
    They keep CLAP's model-specific cosine scale and the descriptor scales
    inspectable while avoiding claims that a cosine value denotes a mood.
    """

    track_count: int
    embedding_pair_count: int
    embedding_outlier_floor: float
    embedding_same_territory_floor: float
    rhythm_anchor_ceiling: float
    rhythm_outlier_floor: float
    spectral_anchor_ceiling: float
    spectral_outlier_floor: float
    cue_style_anchor_ceiling: float
    cue_style_shift_floor: float
    cue_style_outlier_floor: float
    cue_intensity_anchor_ceiling: float
    cue_intensity_shift_floor: float
    cue_intensity_outlier_floor: float
    source: str = "unlabelled_candidate_pool_quantiles"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SetRole(str, Enum):
    OPEN = "OPEN"
    BUILD = "BUILD"
    HOLD = "HOLD"
    PEAK = "PEAK"
    RELEASE = "RELEASE"
    COOLDOWN = "COOLDOWN"


@dataclass(frozen=True)
class MusicalRoleProfile:
    track_id: str
    energy: dict[str, Any]
    groove: dict[str, Any]
    vocals: dict[str, Any]
    mood: dict[str, Any]
    activity: dict[str, Any]
    intensity: dict[str, Any]
    style: dict[str, Any]
    role_suitability: dict[str, bool]
    evidence_limits: tuple[str, ...]
    schema_version: str = MUSICAL_ROLE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SetFlowState:
    phase: SetRole
    recent_track_ids: tuple[str, ...]
    recent_energy: tuple[float, ...]
    recent_dance_functions: tuple[str, ...]
    recent_rhythmic_characters: tuple[str, ...]
    reliable_moods: tuple[str, ...]
    contrast_events: int

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["phase"] = self.phase.value
        return result


@dataclass(frozen=True)
class MusicalFlowAssessment:
    accepted: bool
    relationship: str
    hard_gates: dict[str, bool]
    rejection_reasons: tuple[str, ...]
    intentional_shift_evidence: dict[str, Any]
    source_role: MusicalRoleProfile
    target_role: MusicalRoleProfile
    state_before: SetFlowState
    state_after: SetFlowState
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "relationship": self.relationship,
            "hard_gates": self.hard_gates,
            "rejection_reasons": list(self.rejection_reasons),
            "intentional_shift_evidence": self.intentional_shift_evidence,
            "source_role": self.source_role.to_dict(),
            "target_role": self.target_role.to_dict(),
            "state_before": self.state_before.to_dict(),
            "state_after": self.state_after.to_dict(),
            "evidence": self.evidence,
            "no_opaque_flow_score": True,
        }


def _band(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "moderate"


def _curve_summary(
    values: list[float], fallback: float
) -> tuple[float, float, float, float]:
    curve = np.asarray(values, dtype=float)
    if not curve.size:
        return fallback, fallback, fallback, 0.0
    span = max(1, int(round(len(curve) * 0.2)))
    opening = float(np.mean(curve[:span]))
    closing = float(np.mean(curve[-span:]))
    peak = float(np.max(curve))
    return opening, closing, peak, closing - opening


def _section_weighted(track: TrackProfile, name: str, fallback: float = 0.0) -> float:
    rows = track.analysis.section_profiles
    weighted = [
        (
            max(0.0, float(row.get("end_sec", 0.0)) - float(row.get("start_sec", 0.0))),
            float(row.get(name, fallback)),
        )
        for row in rows
    ]
    duration = sum(weight for weight, _ in weighted)
    return (
        sum(weight * value for weight, value in weighted) / duration
        if duration
        else fallback
    )


def _semantic_group(track: TrackProfile, group: str) -> dict[str, Any]:
    semantic = track.semantic
    if semantic is None:
        return {
            "label": None,
            "reliability": 0.0,
            "scores": {},
            "status": "unavailable",
            "source": "none",
        }
    scores = dict(getattr(semantic, group, {}) or {})
    reliability = float(semantic.reliability_by_group.get(group, 0.0))
    top = max(scores, key=scores.get) if scores else None
    reliable = reliability >= SEMANTIC_RELIABILITY_FLOOR
    return {
        "label": top if reliable else None,
        "top_estimate": top,
        "reliability": round(reliability, 6),
        "scores": scores,
        "status": "reliable_relative_estimate"
        if reliable
        else "deferred_low_reliability",
        "source": f"local_{semantic.model_name}",
        "calibration": semantic.score_calibration,
    }


def _mood(track: TrackProfile) -> dict[str, Any]:
    result = _semantic_group(track, "mood_scores")
    meaning = track.lyrics.meaning if track.lyrics and track.lyrics.meaning else None
    if meaning and meaning.meaning_confidence >= SEMANTIC_RELIABILITY_FLOOR:
        result = {
            **result,
            "lyrical_moods": list(meaning.lyrical_moods),
            "valence": round(float(meaning.emotional_valence), 6),
            "lyric_reliability": round(float(meaning.meaning_confidence), 6),
            "lyric_source": meaning.meaning_source,
        }
    else:
        result = {
            **result,
            "lyrical_moods": [],
            "valence": None,
            "lyric_reliability": 0.0,
            "lyric_source": "unavailable_or_below_reliability_floor",
        }
    return result


def _tempo_hypothesis(track: TrackProfile, relation: str) -> float:
    return max(
        (
            float(row.get("confidence", 0.0))
            for row in track.analysis.tempo_hypotheses
            if row.get("relation") == relation
        ),
        default=0.0,
    )


def derive_musical_role(track: TrackProfile) -> MusicalRoleProfile:
    """Derive a deterministic, explainable role profile from existing evidence."""
    analysis = track.analysis
    opening, closing, peak, direction = _curve_summary(
        analysis.bar_energies, track.mean_energy
    )
    groove = analysis.groove_profile or {}
    percussion = float(groove.get("percussion_density_mean", 0.0))
    onset = float(groove.get("onset_density_hz", 0.0))
    syncopation = float(groove.get("syncopation_index", 0.0))
    onbeat = float(groove.get("onbeat_fraction", 0.0))
    swing = float(groove.get("swing_ratio", 1.0))
    double_confidence = _tempo_hypothesis(track, "double")
    half_confidence = _tempo_hypothesis(track, "half")
    if track.bpm < 100 and double_confidence >= 0.55:
        rhythmic_character = "compound_or_halftime_candidate"
    elif track.bpm > 145 and half_confidence >= 0.55:
        rhythmic_character = "fast_or_doubletime_candidate"
    elif abs(swing - 1.0) >= 0.28:
        rhythmic_character = "swung"
    elif syncopation >= 0.50:
        rhythmic_character = "syncopated"
    elif onbeat >= 0.45:
        rhythmic_character = "straight_driving"
    else:
        rhythmic_character = "mixed"

    if track.mean_energy >= 0.70 and percussion >= 0.62 and onset >= 3.2:
        dance_function = "driving_dance"
    elif percussion >= 0.55 and onset >= 2.6:
        dance_function = "rhythmic_song"
    else:
        dance_function = "atmospheric_or_sparse"
    energy_direction = (
        "rising" if direction > 0.08 else "falling" if direction < -0.08 else "stable"
    )
    vocal_density = _section_weighted(track, "vocal_density")
    drum_density = _section_weighted(track, "drum_density", percussion)
    bass_density = _section_weighted(track, "bass_density")
    mood = _mood(track)
    activity = _semantic_group(track, "activity_scores")
    intensity = _semantic_group(track, "intensity_scores")
    style = _semantic_group(track, "style_scores")
    role_suitability = {
        SetRole.OPEN.value: opening <= track.mean_energy + 0.02
        and track.mean_energy <= 0.82,
        SetRole.BUILD.value: energy_direction == "rising"
        or track.mean_energy >= opening + 0.06,
        SetRole.HOLD.value: 0.62 <= track.mean_energy <= 0.86
        and dance_function != "atmospheric_or_sparse",
        SetRole.PEAK.value: track.mean_energy >= 0.74
        and dance_function == "driving_dance",
        SetRole.RELEASE.value: closing <= peak - 0.08 or energy_direction == "falling",
        SetRole.COOLDOWN.value: track.mean_energy <= 0.73
        or closing <= track.mean_energy - 0.08,
    }
    limits = []
    if mood["label"] is None:
        limits.append(
            "audio mood below reliability floor; no mood label or valence claim"
        )
    if activity["label"] is None:
        limits.append(
            "semantic activity below reliability floor; dance function uses acoustic evidence"
        )
    if style["label"] is None:
        limits.append("style family below reliability floor")
    if not mood["lyrical_moods"]:
        limits.append("lyric meaning unavailable or below reliability floor")
    return MusicalRoleProfile(
        track_id=track.id,
        energy={
            "mean": round(track.mean_energy, 6),
            "opening": round(opening, 6),
            "closing": round(closing, 6),
            "peak": round(peak, 6),
            "direction_delta": round(direction, 6),
            "direction": energy_direction,
            "level": _band(track.mean_energy, 0.68, 0.80),
        },
        groove={
            "dance_function": dance_function,
            "rhythmic_character": rhythmic_character,
            "bpm": round(track.bpm, 6),
            "double_time_hypothesis_confidence": round(double_confidence, 6),
            "half_time_hypothesis_confidence": round(half_confidence, 6),
            "percussion_density": round(percussion, 6),
            "section_drum_density": round(drum_density, 6),
            "section_bass_density": round(bass_density, 6),
            "onset_density_hz": round(onset, 6),
            "onbeat_fraction": round(onbeat, 6),
            "syncopation_index": round(syncopation, 6),
            "swing_ratio": round(swing, 6),
            "groove_confidence": round(float(groove.get("confidence", 0.0)), 6),
        },
        vocals={
            "section_weighted_prominence": round(vocal_density, 6),
            "prominence_band": _band(vocal_density, 0.30, 0.68),
        },
        mood=mood,
        activity=activity,
        intensity=intensity,
        style=style,
        role_suitability=role_suitability,
        evidence_limits=tuple(limits),
    )


def initial_set_flow_state(
    track: TrackProfile, phase: SetRole = SetRole.OPEN
) -> SetFlowState:
    profile = derive_musical_role(track)
    reliable_moods = tuple(
        item
        for item in (
            profile.mood.get("label"),
            *profile.mood.get("lyrical_moods", []),
        )
        if item
    )
    return SetFlowState(
        phase=phase,
        recent_track_ids=(track.id,),
        recent_energy=(float(profile.energy["mean"]),),
        recent_dance_functions=(str(profile.groove["dance_function"]),),
        recent_rhythmic_characters=(str(profile.groove["rhythmic_character"]),),
        reliable_moods=reliable_moods,
        contrast_events=0,
    )


def _phase_energy_gate(
    source_energy: float, target_energy: float, target_phase: SetRole
) -> bool:
    change = target_energy - source_energy
    if target_phase == SetRole.BUILD:
        return change >= -0.06
    if target_phase == SetRole.HOLD:
        return abs(change) <= 0.12
    if target_phase == SetRole.PEAK:
        return change >= -0.03
    if target_phase == SetRole.RELEASE:
        return change <= 0.06
    if target_phase == SetRole.COOLDOWN:
        return change <= 0.03
    return abs(change) <= 0.12


def _raw_cosine(first: list[float], second: list[float]) -> float | None:
    left = np.asarray(first, dtype=float).reshape(-1)
    right = np.asarray(second, dtype=float).reshape(-1)
    if not len(left) or len(left) != len(right):
        return None
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-12:
        return None
    return float(np.clip(np.dot(left, right) / denominator, -1.0, 1.0))


def _descriptor_distance(
    source: TrackProfile,
    target: TrackProfile,
    attribute: str,
) -> float | None:
    left = np.asarray(getattr(source.analysis, attribute, []), dtype=float)
    right = np.asarray(getattr(target.analysis, attribute, []), dtype=float)
    if left.ndim != 2 or right.ndim != 2 or not len(left) or not len(right):
        return None
    if left.shape[1] != right.shape[1]:
        return None
    return float(np.mean(np.abs(np.mean(left, axis=0) - np.mean(right, axis=0))))


def _pair_context_values(
    source: TrackProfile,
    target: TrackProfile,
) -> tuple[float | None, float | None, float | None]:
    embedding = (
        _raw_cosine(source.semantic.embedding, target.semantic.embedding)
        if source.semantic is not None and target.semantic is not None
        else None
    )
    return (
        embedding,
        _descriptor_distance(source, target, "local_rhythm_curve"),
        _descriptor_distance(source, target, "local_spectral_curve"),
    )


def _window_group_distance(
    source_window: dict[str, Any],
    target_window: dict[str, Any],
    group: str,
) -> float | None:
    left = source_window.get("scores", {}).get(group, {})
    right = target_window.get("scores", {}).get(group, {})
    labels = set(left) | set(right)
    if not labels:
        return None
    return float(
        sum(abs(float(left.get(label, 0.0)) - float(right.get(label, 0.0))) for label in labels)
        / len(labels)
    )


def _nearest_semantic_window(
    track: TrackProfile,
    context_sec: float | None,
) -> dict[str, Any] | None:
    if track.semantic is None or not track.semantic.sample_windows:
        return None
    if context_sec is None:
        return None
    return min(
        track.semantic.sample_windows,
        key=lambda item: abs(
            (float(item.get("start_sec", 0.0)) + float(item.get("end_sec", 0.0)))
            / 2.0
            - context_sec
        ),
    )


def _cue_semantic_distances(
    source: TrackProfile,
    target: TrackProfile,
    source_context_sec: float | None,
    target_context_sec: float | None,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    source_window = _nearest_semantic_window(source, source_context_sec)
    target_window = _nearest_semantic_window(target, target_context_sec)
    groups = ("mood_scores", "activity_scores", "intensity_scores", "style_scores")
    distances = {
        group: (
            _window_group_distance(source_window, target_window, group)
            if source_window is not None and target_window is not None
            else None
        )
        for group in groups
    }
    provenance = {
        "source_window": (
            {
                "start_sec": source_window.get("start_sec"),
                "end_sec": source_window.get("end_sec"),
            }
            if source_window is not None
            else None
        ),
        "target_window": (
            {
                "start_sec": target_window.get("start_sec"),
                "end_sec": target_window.get("end_sec"),
            }
            if target_window is not None
            else None
        ),
        "selection": "nearest cached representative semantic window to the actual transition context",
    }
    return distances, provenance


def calibrate_musical_context(
    tracks: list[TrackProfile] | tuple[TrackProfile, ...],
) -> MusicalContextCalibration:
    """Calibrate descriptor bands from the unlabelled candidate pool."""
    embeddings: list[float] = []
    rhythm: list[float] = []
    spectral: list[float] = []
    cue_style: list[float] = []
    cue_intensity: list[float] = []
    ordered = tuple(sorted(tracks, key=lambda item: item.id))
    for index, source in enumerate(ordered):
        for target in ordered[index + 1:]:
            semantic_value, rhythm_value, spectral_value = _pair_context_values(
                source, target
            )
            if semantic_value is not None:
                embeddings.append(semantic_value)
            if rhythm_value is not None:
                rhythm.append(rhythm_value)
            if spectral_value is not None:
                spectral.append(spectral_value)
            if source.semantic is not None and target.semantic is not None:
                for source_window in source.semantic.sample_windows:
                    for target_window in target.semantic.sample_windows:
                        style_value = _window_group_distance(
                            source_window, target_window, "style_scores"
                        )
                        intensity_value = _window_group_distance(
                            source_window, target_window, "intensity_scores"
                        )
                        if style_value is not None:
                            cue_style.append(style_value)
                        if intensity_value is not None:
                            cue_intensity.append(intensity_value)

    def quantile(values: list[float], q: float, fallback: float) -> float:
        return float(np.quantile(values, q)) if values else fallback

    return MusicalContextCalibration(
        track_count=len(ordered),
        embedding_pair_count=len(embeddings),
        embedding_outlier_floor=round(quantile(embeddings, .10, .86), 6),
        embedding_same_territory_floor=round(quantile(embeddings, .25, .885), 6),
        rhythm_anchor_ceiling=round(quantile(rhythm, .50, .055), 6),
        rhythm_outlier_floor=round(quantile(rhythm, .90, .10), 6),
        spectral_anchor_ceiling=round(quantile(spectral, .50, .065), 6),
        spectral_outlier_floor=round(quantile(spectral, .90, .14), 6),
        cue_style_anchor_ceiling=round(quantile(cue_style, .50, .02), 6),
        cue_style_shift_floor=round(quantile(cue_style, .75, .025), 6),
        cue_style_outlier_floor=round(quantile(cue_style, .90, .03), 6),
        cue_intensity_anchor_ceiling=round(quantile(cue_intensity, .50, .02), 6),
        cue_intensity_shift_floor=round(quantile(cue_intensity, .75, .03), 6),
        cue_intensity_outlier_floor=round(quantile(cue_intensity, .90, .04), 6),
    )


def _default_context_calibration() -> MusicalContextCalibration:
    return MusicalContextCalibration(
        track_count=0,
        embedding_pair_count=0,
        embedding_outlier_floor=.72,
        embedding_same_territory_floor=.77,
        rhythm_anchor_ceiling=.055,
        rhythm_outlier_floor=.10,
        spectral_anchor_ceiling=.065,
        spectral_outlier_floor=.14,
        cue_style_anchor_ceiling=.02,
        cue_style_shift_floor=.025,
        cue_style_outlier_floor=.03,
        cue_intensity_anchor_ceiling=.02,
        cue_intensity_shift_floor=.03,
        cue_intensity_outlier_floor=.04,
        source="documented_model_scale_fallback",
    )


def assess_musical_flow(
    source: TrackProfile,
    target: TrackProfile,
    *,
    state: SetFlowState,
    target_phase: SetRole,
    archetype: ReferenceArchetype | None,
    tempo_delta_pct: float,
    groove_distance: float,
    max_energy_jump: float,
    max_contrast_events: int,
    context_calibration: MusicalContextCalibration | None = None,
    source_context_sec: float | None = None,
    target_context_sec: float | None = None,
) -> MusicalFlowAssessment:
    """Require an explainable continuation or a phase-supported intentional shift."""
    source_role = derive_musical_role(source)
    target_role = derive_musical_role(target)
    source_energy = float(source_role.energy["mean"])
    target_energy = float(target_role.energy["mean"])
    energy_change = target_energy - source_energy
    source_character = str(source_role.groove["rhythmic_character"])
    target_character = str(target_role.groove["rhythmic_character"])
    source_function = str(source_role.groove["dance_function"])
    target_function = str(target_role.groove["dance_function"])
    rhythmic_jump = (
        tempo_delta_pct > 18.0
        and groove_distance > 0.14
        and source_character != target_character
    )
    dance_jump = {
        source_function,
        target_function,
    } == {"driving_dance", "atmospheric_or_sparse"}
    source_style = source_role.style.get("label")
    target_style = target_role.style.get("label")
    style_similarity = distribution_similarity(
        source_role.style.get("scores", {}),
        target_role.style.get("scores", {}),
    )
    style_jump = bool(
        source_style
        and target_style
        and source_style != target_style
        and style_similarity < 0.90
    )
    source_mood = source_role.mood.get("label")
    target_mood = target_role.mood.get("label")
    mood_similarity = distribution_similarity(
        source_role.mood.get("scores", {}),
        target_role.mood.get("scores", {}),
    )
    source_valence = source_role.mood.get("valence")
    target_valence = target_role.mood.get("valence")
    valence_jump = (
        source_valence is not None
        and target_valence is not None
        and abs(float(target_valence) - float(source_valence)) > 0.45
    )
    semantic_mood_jump = bool(
        source_mood
        and target_mood
        and source_mood != target_mood
        and mood_similarity < 0.90
    )
    calibration = context_calibration or _default_context_calibration()
    embedding_similarity, rhythm_descriptor_distance, spectral_descriptor_distance = (
        _pair_context_values(source, target)
    )
    cue_semantic_distances, cue_semantic_provenance = _cue_semantic_distances(
        source,
        target,
        source_context_sec,
        target_context_sec,
    )
    cue_style_distance = cue_semantic_distances["style_scores"]
    cue_intensity_distance = cue_semantic_distances["intensity_scores"]
    harmonic_compatibility = score_key_compatibility(source.camelot, target.camelot)
    source_centroid = max(float(source.analysis.spectral_centroid_mean), 1.0)
    target_centroid = max(float(target.analysis.spectral_centroid_mean), 1.0)
    centroid_distance_octaves = abs(math.log2(target_centroid / source_centroid))
    embedding_is_outlier = (
        embedding_similarity is not None
        and embedding_similarity < calibration.embedding_outlier_floor
    )
    embedding_supports_same_territory = (
        embedding_similarity is not None
        and embedding_similarity >= calibration.embedding_same_territory_floor
    )
    rhythm_anchor = (
        rhythm_descriptor_distance is not None
        and rhythm_descriptor_distance <= calibration.rhythm_anchor_ceiling
    )
    spectral_anchor = (
        spectral_descriptor_distance is not None
        and spectral_descriptor_distance <= calibration.spectral_anchor_ceiling
    )
    harmonic_anchor = harmonic_compatibility >= .70
    cue_style_anchor = (
        cue_style_distance is not None
        and cue_style_distance <= calibration.cue_style_anchor_ceiling
    )
    cue_intensity_anchor = (
        cue_intensity_distance is not None
        and cue_intensity_distance <= calibration.cue_intensity_anchor_ceiling
    )
    continuity_anchors = {
        "audio_embedding_same_territory": embedding_supports_same_territory,
        "whole_track_rhythm_descriptor": rhythm_anchor,
        "whole_track_spectral_descriptor": spectral_anchor,
        "harmonic_relation": harmonic_anchor,
        "cue_style_distribution": cue_style_anchor,
        "cue_intensity_distribution": cue_intensity_anchor,
    }
    continuity_anchor_count = sum(continuity_anchors.values())
    rhythm_descriptor_outlier = (
        rhythm_descriptor_distance is not None
        and rhythm_descriptor_distance > calibration.rhythm_outlier_floor
    )
    spectral_descriptor_outlier = (
        spectral_descriptor_distance is not None
        and spectral_descriptor_distance > calibration.spectral_outlier_floor
    )
    material_tempo_transform = tempo_delta_pct > 18.0
    cue_style_outlier = (
        cue_style_distance is not None
        and cue_style_distance > calibration.cue_style_outlier_floor
    )
    cue_intensity_outlier = (
        cue_intensity_distance is not None
        and cue_intensity_distance > calibration.cue_intensity_outlier_floor
    )
    cue_multi_axis_shift = (
        cue_style_distance is not None
        and cue_intensity_distance is not None
        and cue_style_distance > calibration.cue_style_shift_floor
        and cue_intensity_distance > calibration.cue_intensity_shift_floor
    )
    context_contrast_axes = {
        "pool_relative_audio_embedding_outlier": embedding_is_outlier,
        "material_tempo_or_meter_change": material_tempo_transform,
        "whole_track_rhythm_outlier": rhythm_descriptor_outlier,
        "whole_track_spectral_outlier": spectral_descriptor_outlier,
        "rhythmic_role_change": rhythmic_jump,
        "dance_function_change": dance_jump,
        "reliable_style_change": style_jump,
        "reliable_mood_or_valence_change": valence_jump or semantic_mood_jump,
        "cue_style_distribution_outlier": cue_style_outlier,
        "cue_intensity_distribution_outlier": cue_intensity_outlier,
        "cue_style_and_intensity_shift_together": cue_multi_axis_shift,
    }
    contrast_detected = any(context_contrast_axes.values())
    phase_direction_supports_shift = (
        (
            target_phase == SetRole.PEAK
            and energy_change >= -0.03
            and target_function == "driving_dance"
        )
        or (target_phase == SetRole.RELEASE and energy_change <= 0.03)
        or (target_phase == SetRole.COOLDOWN and energy_change <= -0.02)
        or (
            target_phase == SetRole.BUILD
            and energy_change >= 0.03
            and target_function == "driving_dance"
        )
    )
    reset_communicates_shift = archetype == ReferenceArchetype.RESET_RELEASE
    contrast_budget_available = state.contrast_events < max_contrast_events
    unresolved_cue_context_split = (
        cue_style_outlier or cue_intensity_outlier or cue_multi_axis_shift
    )
    cue_context_available = (
        cue_style_distance is not None and cue_intensity_distance is not None
    )
    context_has_bridge_anchors = (
        not embedding_is_outlier
        and not unresolved_cue_context_split
        and cue_context_available
        and continuity_anchor_count >= 2
    )
    intentional_shift = (
        contrast_detected
        and phase_direction_supports_shift
        and reset_communicates_shift
        and contrast_budget_available
        and context_has_bridge_anchors
    )
    role_supported = bool(target_role.role_suitability.get(target_phase.value, False))
    hard_gates = {
        "energy_jump_within_set_bound": abs(energy_change) <= max_energy_jump,
        "target_supports_declared_set_role": role_supported,
        "energy_direction_matches_declared_phase": _phase_energy_gate(
            source_energy,
            target_energy,
            target_phase,
        ),
        "dance_function_is_coherent_or_intentional": not dance_jump
        or intentional_shift,
        "rhythmic_role_is_coherent_or_intentional": not rhythmic_jump
        or intentional_shift,
        "style_change_is_coherent_or_intentional": not style_jump or intentional_shift,
        "reliable_mood_change_is_coherent_or_intentional": not (
            valence_jump or semantic_mood_jump
        )
        or intentional_shift,
        "musical_context_is_natural_or_bridgeable": not contrast_detected
        or intentional_shift,
        "contrast_has_declared_bridge": not contrast_detected or intentional_shift,
        "contrast_budget_not_exceeded": not contrast_detected or contrast_budget_available,
    }
    reason_map = {
        "energy_jump_within_set_bound": "excessive unexplained energy jump",
        "target_supports_declared_set_role": f"target does not support the declared {target_phase.value} set role",
        "energy_direction_matches_declared_phase": f"energy direction breaks the declared {target_phase.value} trajectory",
        "dance_function_is_coherent_or_intentional": "danceability/functional-role discontinuity lacks a supported bridge",
        "rhythmic_role_is_coherent_or_intentional": "incompatible rhythmic role lacks a supported bridge",
        "style_change_is_coherent_or_intentional": "genre/style change lacks reliable bridging evidence",
        "reliable_mood_change_is_coherent_or_intentional": "reliable mood/valence discontinuity lacks a supported arc",
        "musical_context_is_natural_or_bridgeable": "musical-territory contrast lacks enough continuity anchors for a proven bridge",
        "contrast_has_declared_bridge": "detected contrast lacks a phase-supported reset/release bridge",
        "contrast_budget_not_exceeded": "set has already spent its allowed intentional contrast",
    }
    rejection = tuple(
        reason_map[name] for name, passed in hard_gates.items() if not passed
    )
    accepted = all(hard_gates.values())
    if contrast_detected:
        relationship = (
            "INTENTIONAL_BRIDGEABLE_CONTRAST"
            if intentional_shift
            else "UNJUSTIFIED_DISCONTINUITY"
        )
    else:
        relationship = "NATURAL_CONTINUATION"
    reliable_moods = tuple(
        item
        for item in (
            *state.reliable_moods,
            target_mood,
            *target_role.mood.get("lyrical_moods", []),
        )
        if item
    )
    state_after = SetFlowState(
        phase=target_phase,
        recent_track_ids=(*state.recent_track_ids[-2:], target.id),
        recent_energy=(*state.recent_energy[-2:], target_energy),
        recent_dance_functions=(*state.recent_dance_functions[-2:], target_function),
        recent_rhythmic_characters=(
            *state.recent_rhythmic_characters[-2:],
            target_character,
        ),
        reliable_moods=reliable_moods[-3:],
        contrast_events=state.contrast_events + (1 if intentional_shift else 0),
    )
    return MusicalFlowAssessment(
        accepted=accepted,
        relationship=relationship,
        hard_gates=hard_gates,
        rejection_reasons=rejection,
        intentional_shift_evidence={
            "contrast_detected": contrast_detected,
            "phase_direction_supports_shift": phase_direction_supports_shift,
            "reset_release_archetype_communicates_shift": reset_communicates_shift,
            "context_has_at_least_two_continuity_anchors": context_has_bridge_anchors,
            "continuity_anchor_count": continuity_anchor_count,
            "continuity_anchors": continuity_anchors,
            "contrast_budget_before": state.contrast_events,
            "contrast_budget_limit": max_contrast_events,
            "contrast_budget_available": contrast_budget_available,
            "qualified_intentional_shift": intentional_shift,
        },
        source_role=source_role,
        target_role=target_role,
        state_before=state,
        state_after=state_after,
        evidence={
            "target_phase": target_phase.value,
            "energy_change": round(energy_change, 6),
            "tempo_delta_pct": round(tempo_delta_pct, 6),
            "groove_distance": round(groove_distance, 6),
            "rhythmic_character_change": [source_character, target_character],
            "dance_function_change": [source_function, target_function],
            "rhythmic_jump": rhythmic_jump,
            "dance_function_jump": dance_jump,
            "style_labels": [source_style, target_style],
            "style_distribution_similarity": round(style_similarity, 6),
            "mood_labels": [source_mood, target_mood],
            "mood_distribution_similarity": round(mood_similarity, 6),
            "valence_values": [source_valence, target_valence],
            "mood_claim_deferred": source_mood is None or target_mood is None,
            "musical_context": {
                "classification": relationship,
                "audio_embedding_cosine": (
                    round(embedding_similarity, 6)
                    if embedding_similarity is not None
                    else None
                ),
                "audio_embedding_interpretation": (
                    "pool_relative_musical_territory_only; not a mood or genre label"
                    if embedding_similarity is not None
                    else "unavailable"
                ),
                "rhythm_descriptor_mean_absolute_distance": (
                    round(rhythm_descriptor_distance, 6)
                    if rhythm_descriptor_distance is not None
                    else None
                ),
                "spectral_descriptor_mean_absolute_distance": (
                    round(spectral_descriptor_distance, 6)
                    if spectral_descriptor_distance is not None
                    else None
                ),
                "spectral_centroid_distance_octaves": round(
                    centroid_distance_octaves, 6
                ),
                "harmonic_compatibility": round(harmonic_compatibility, 6),
                "cue_semantic_distribution_distances": {
                    name: round(value, 6) if value is not None else None
                    for name, value in cue_semantic_distances.items()
                },
                "cue_semantic_window_provenance": cue_semantic_provenance,
                "cue_context_split_unresolved": unresolved_cue_context_split,
                "cue_context_available_for_contrast_decision": cue_context_available,
                "contrast_axes": context_contrast_axes,
                "continuity_anchors": continuity_anchors,
                "continuity_anchor_count": continuity_anchor_count,
                "calibration": calibration.to_dict(),
                "semantic_label_claims_deferred": (
                    source_mood is None or target_mood is None
                ),
                "no_opaque_context_score": True,
            },
            "section_role_evidence": {
                "source_energy_direction": source_role.energy["direction"],
                "target_energy_direction": target_role.energy["direction"],
                "source_role_suitability": source_role.role_suitability,
                "target_role_suitability": target_role.role_suitability,
            },
        },
    )
