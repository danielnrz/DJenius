"""V2 Phase 6 Audition Lab: measure, reject, rank, and select rendered candidates.

The score here is an explainable deterministic heuristic over currently
measurable evidence.  It is not a claim of human-perceived professional DJ
quality; the later blind listening gate remains authoritative for that claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
from typing import Any, Iterable

import numpy as np

from djenius.audio.audition_renderer import RenderedCandidatePreview
from djenius.core.candidate_composer import TransitionCandidate

AUDITION_SCHEMA_VERSION = "6.0"


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _db(value: float) -> float:
    return float(20.0 * np.log10(max(float(value), 1e-8)))


def _mono(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    if values.ndim == 1:
        return values
    if values.ndim == 2 and values.shape[1] in {1, 2}:
        return np.mean(values, axis=1, dtype=np.float32)
    raise ValueError("audition audio must be mono or stereo")


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_value(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


@dataclass(frozen=True)
class AuditionFailure:
    code: str
    message: str
    observed: float | str | None = None
    threshold: float | str | None = None
    hard: bool = True

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditionFailure":
        return cls(
            code=str(data.get("code", "")),
            message=str(data.get("message", "")),
            observed=data.get("observed"),
            threshold=data.get("threshold"),
            hard=bool(data.get("hard", True)),
        )


@dataclass(frozen=True)
class AuditionMetrics:
    technical: dict[str, Any] = field(default_factory=dict)
    beat: dict[str, Any] = field(default_factory=dict)
    spectral: dict[str, Any] = field(default_factory=dict)
    vocal: dict[str, Any] = field(default_factory=dict)
    harmonic: dict[str, Any] = field(default_factory=dict)
    energy: dict[str, Any] = field(default_factory=dict)
    fx: dict[str, Any] = field(default_factory=dict)
    normalized_components: dict[str, float] = field(default_factory=dict)
    deferred: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "technical": _json_value(self.technical),
            "beat": _json_value(self.beat),
            "spectral": _json_value(self.spectral),
            "vocal": _json_value(self.vocal),
            "harmonic": _json_value(self.harmonic),
            "energy": _json_value(self.energy),
            "fx": _json_value(self.fx),
            "normalized_components": _json_value(self.normalized_components),
            "deferred": list(self.deferred),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditionMetrics":
        return cls(
            technical=dict(data.get("technical", {})),
            beat=dict(data.get("beat", {})),
            spectral=dict(data.get("spectral", {})),
            vocal=dict(data.get("vocal", {})),
            harmonic=dict(data.get("harmonic", {})),
            energy=dict(data.get("energy", {})),
            fx=dict(data.get("fx", {})),
            normalized_components={str(k): float(v) for k, v in data.get("normalized_components", {}).items()},
            deferred=tuple(str(x) for x in data.get("deferred", [])),
        )


@dataclass(frozen=True)
class CandidateAudition:
    candidate_id: str
    recipe_id: str
    render_status: str
    hard_rejected: bool
    failures: tuple[AuditionFailure, ...]
    metrics: AuditionMetrics
    final_score: float
    rank: int | None = None
    selected: bool = False
    selection_reason: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = AUDITION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "recipe_id": self.recipe_id,
            "render_status": self.render_status,
            "hard_rejected": self.hard_rejected,
            "failures": [item.to_dict() for item in self.failures],
            "metrics": self.metrics.to_dict(),
            "final_score": round(float(self.final_score), 9),
            "rank": self.rank,
            "selected": self.selected,
            "selection_reason": self.selection_reason,
            "provenance": _json_value(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateAudition":
        return cls(
            schema_version=str(data.get("schema_version", AUDITION_SCHEMA_VERSION)),
            candidate_id=str(data.get("candidate_id", "")),
            recipe_id=str(data.get("recipe_id", "")),
            render_status=str(data.get("render_status", "")),
            hard_rejected=bool(data.get("hard_rejected", False)),
            failures=tuple(AuditionFailure.from_dict(x) for x in data.get("failures", [])),
            metrics=AuditionMetrics.from_dict(data.get("metrics", {})),
            final_score=float(data.get("final_score", 0.0)),
            rank=int(data["rank"]) if data.get("rank") is not None else None,
            selected=bool(data.get("selected", False)),
            selection_reason=str(data.get("selection_reason", "")),
            provenance=dict(data.get("provenance", {})),
        )


@dataclass(frozen=True)
class AuditionConfig:
    sample_clip_threshold: float = 1.0
    oversampled_peak_threshold: float = 1.0
    maximum_clipping_fraction: float = 0.0
    catastrophic_silence_dbfs: float = -58.0
    maximum_silent_fraction: float = 0.80
    hard_discontinuity_amplitude: float = 0.90
    bpm_confidence_threshold: float = 0.55
    beat_good_error_ms: float = 35.0
    beat_poor_error_ms: float = 140.0
    weights: dict[str, float] = field(default_factory=lambda: {
        "technical_margin": 0.16,
        "beat_stability": 0.22,
        "spectral_cleanliness": 0.18,
        "vocal_safety": 0.14,
        "energy_goal_fit": 0.20,
        "fx_safety": 0.10,
    })

    def validate(self) -> None:
        if not 0.5 <= self.sample_clip_threshold <= 2.0:
            raise ValueError("sample_clip_threshold must be in [0.5, 2.0]")
        if not 0.5 <= self.oversampled_peak_threshold <= 2.0:
            raise ValueError("oversampled_peak_threshold must be in [0.5, 2.0]")
        if not 0.0 <= self.maximum_clipping_fraction <= 1.0:
            raise ValueError("maximum_clipping_fraction must be in [0, 1]")
        if not 0.0 <= self.maximum_silent_fraction <= 1.0:
            raise ValueError("maximum_silent_fraction must be in [0, 1]")
        if self.hard_discontinuity_amplitude <= 0.0:
            raise ValueError("hard_discontinuity_amplitude must be positive")
        if not self.weights or any(float(v) < 0.0 for v in self.weights.values()) or sum(self.weights.values()) <= 0:
            raise ValueError("audition weights must contain positive total weight")

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self.__dict__)


@dataclass(frozen=True)
class AuditionRanking:
    auditions: tuple[CandidateAudition, ...]
    selected_candidate_id: str | None
    survivor_count: int
    rejected_count: int
    ranking_order: tuple[str, ...]
    config: dict[str, Any]
    schema_version: str = AUDITION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "auditions": [item.to_dict() for item in self.auditions],
            "selected_candidate_id": self.selected_candidate_id,
            "survivor_count": self.survivor_count,
            "rejected_count": self.rejected_count,
            "ranking_order": list(self.ranking_order),
            "config": _json_value(self.config),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditionRanking":
        return cls(
            schema_version=str(data.get("schema_version", AUDITION_SCHEMA_VERSION)),
            auditions=tuple(CandidateAudition.from_dict(x) for x in data.get("auditions", [])),
            selected_candidate_id=(str(data["selected_candidate_id"]) if data.get("selected_candidate_id") else None),
            survivor_count=int(data.get("survivor_count", 0)),
            rejected_count=int(data.get("rejected_count", 0)),
            ranking_order=tuple(str(x) for x in data.get("ranking_order", [])),
            config=dict(data.get("config", {})),
        )


def _region(preview: RenderedCandidatePreview, which: str) -> np.ndarray:
    start = preview.transition_start_sample
    end = preview.transition_end_sample
    if which == "before":
        return preview.audio[:start]
    if which == "transition":
        return preview.audio[start:end]
    if which == "after":
        return preview.audio[end:]
    raise ValueError(which)


def _rms_db(audio: np.ndarray) -> float:
    if not np.asarray(audio).size:
        return -120.0
    mono = _mono(audio).astype(np.float64)
    return _db(float(np.sqrt(np.mean(mono * mono))))


def _peak(audio: np.ndarray) -> float:
    values = np.asarray(audio)
    return float(np.max(np.abs(values))) if values.size else 0.0


def _silent_fraction(audio: np.ndarray, sample_rate: int, threshold_dbfs: float = -55.0) -> float:
    mono = _mono(audio)
    frame = max(1, int(round(sample_rate * 0.10)))
    if not len(mono):
        return 1.0
    silent = total = 0
    for start in range(0, len(mono), frame):
        region = mono[start:start + frame]
        if not len(region):
            continue
        total += 1
        rms = float(np.sqrt(np.mean(region.astype(np.float64) ** 2)))
        silent += _db(rms) <= threshold_dbfs
    return float(silent / max(total, 1))


def _boundary_jump(preview: RenderedCandidatePreview) -> float:
    audio = np.asarray(preview.audio, dtype=np.float32)
    if len(audio) < 2:
        return float("inf")
    jumps: list[float] = []
    for boundary in (preview.transition_start_sample, preview.transition_end_sample):
        if 0 < boundary < len(audio):
            jumps.append(float(np.max(np.abs(audio[boundary] - audio[boundary - 1]))))
    return max(jumps, default=0.0)


def _band_profile(audio: np.ndarray, sample_rate: int) -> dict[str, float]:
    mono = _mono(audio)
    if not len(mono):
        return {"low_ratio": 0.0, "mud_ratio": 0.0, "mid_ratio": 0.0, "high_ratio": 0.0, "centroid_hz": 0.0}
    limit = min(len(mono), max(2048, sample_rate * 4))
    start = max(0, (len(mono) - limit) // 2)
    values = mono[start:start + limit].astype(np.float64)
    if len(values) < 64:
        return {"low_ratio": 0.0, "mud_ratio": 0.0, "mid_ratio": 0.0, "high_ratio": 0.0, "centroid_hz": 0.0}
    window = np.hanning(len(values))
    spectrum = np.abs(np.fft.rfft(values * window))
    power = spectrum * spectrum
    frequencies = np.fft.rfftfreq(len(values), 1.0 / sample_rate)
    total = max(float(np.sum(power)), 1e-12)
    low = float(np.sum(power[frequencies < 180.0]) / total)
    mud = float(np.sum(power[(frequencies >= 180.0) & (frequencies < 500.0)]) / total)
    mid = float(np.sum(power[(frequencies >= 500.0) & (frequencies < 8000.0)]) / total)
    high = float(np.sum(power[frequencies >= 8000.0]) / total) if sample_rate / 2 > 8000 else 0.0
    centroid = float(np.sum(frequencies * spectrum) / max(float(np.sum(spectrum)), 1e-12))
    return {
        "low_ratio": low,
        "mud_ratio": mud,
        "mid_ratio": mid,
        "high_ratio": high,
        "centroid_hz": centroid,
    }


def _beat_metrics(preview: RenderedCandidatePreview, candidate: TransitionCandidate, config: AuditionConfig) -> dict[str, Any]:
    evidence = candidate.diagnostics.evidence
    confidence = min(
        float(evidence.get("source_bpm_confidence", 0.0)),
        float(evidence.get("target_bpm_confidence", 0.0)),
    )
    if confidence < config.bpm_confidence_threshold or candidate.source_bpm <= 0:
        return {
            "applicable": False,
            "reason": "beat evidence below confidence threshold",
            "analysis_confidence": round(confidence, 4),
        }
    audio = _mono(_region(preview, "transition"))
    sr = preview.sample_rate
    frame = max(8, int(round(sr * 0.010)))
    count = len(audio) // frame
    if count < 4:
        return {"applicable": False, "reason": "transition too short for beat measurement"}
    trimmed = audio[:count * frame].reshape(count, frame).astype(np.float64)
    energy = np.sqrt(np.mean(trimmed * trimmed, axis=1))
    onset = np.maximum(np.diff(np.r_[energy[0], energy]), 0.0)
    if float(np.max(onset)) <= 1e-7:
        return {"applicable": False, "reason": "no measurable onset evidence"}
    beat_sec = 60.0 / candidate.source_bpm
    duration = len(audio) / sr
    expected = np.arange(0.0, duration, beat_sec)
    # Exclude boundary beats: a frame-energy onset detector cannot observe the
    # pre-boundary derivative for beat zero, which would bias an otherwise
    # perfectly aligned fixture. Interior beats provide the stable evidence.
    search = beat_sec * 0.45
    interior = expected[(expected >= search) & (expected <= duration - search)]
    if len(interior) >= 2:
        expected = interior
    else:
        expected = expected[(expected >= 0.0) & (expected < duration)]
    if len(expected) < 2:
        return {"applicable": False, "reason": "fewer than two expected beats"}
    frame_times = (np.arange(count) + 0.5) * frame / sr
    errors: list[float] = []
    signed: list[float] = []
    coincidences = 0
    for beat_time in expected:
        mask = np.where(np.abs(frame_times - beat_time) <= search)[0]
        if not len(mask):
            continue
        local = mask[int(np.argmax(onset[mask]))]
        error_ms = (float(frame_times[local]) - float(beat_time)) * 1000.0
        errors.append(abs(error_ms))
        signed.append(error_ms)
        coincidences += abs(error_ms) <= 50.0
    if len(errors) < 2:
        return {"applicable": False, "reason": "insufficient detected beat evidence"}
    mean_error = float(np.mean(errors))
    drift = float(abs(signed[-1] - signed[0]))
    coincidence = float(coincidences / len(errors))
    # Continuous decay preserves useful monotonicity even inside the nominal
    # "good" tolerance instead of flattening all small offsets to 1.0.
    phase_scale = max(config.beat_good_error_ms * 2.0, 1.0)
    phase_score = _clip01(math.exp(-mean_error / phase_scale))
    drift_score = _clip01(1.0 - drift / 180.0)
    score = _clip01(0.65 * phase_score + 0.20 * coincidence + 0.15 * drift_score)
    return {
        "applicable": True,
        "analysis_confidence": round(confidence, 4),
        "beat_grid_phase_error_ms": round(mean_error, 3),
        "onset_grid_coincidence_fraction": round(coincidence, 4),
        "sync_drift_proxy_ms": round(drift, 3),
        "local_tempo_mismatch_pct": round(abs(candidate.source_bpm - candidate.target_bpm) / candidate.source_bpm * 100.0, 4),
        "detected_expected_beats": len(errors),
        "score": round(score, 6),
        "precision_note": "frame-energy onset proxy; not isolated kick detection",
    }


def _spectral_metrics(preview: RenderedCandidatePreview) -> dict[str, Any]:
    before = _band_profile(_region(preview, "before"), preview.sample_rate)
    transition = _band_profile(_region(preview, "transition"), preview.sample_rate)
    after = _band_profile(_region(preview, "after"), preview.sample_rate)
    context = {name: (before[name] + after[name]) / 2.0 for name in ("low_ratio", "mud_ratio", "mid_ratio", "high_ratio")}
    lf_excess = max(0.0, transition["low_ratio"] - max(before["low_ratio"], after["low_ratio"]))
    mud_excess = max(0.0, transition["mud_ratio"] - max(before["mud_ratio"], after["mud_ratio"]))
    hf_excess = max(0.0, transition["high_ratio"] - max(before["high_ratio"], after["high_ratio"]))
    continuity_distance = sum(abs(transition[name] - context[name]) for name in context)
    continuity = _clip01(1.0 - continuity_distance / 1.5)
    before_db = _rms_db(_region(preview, "before"))
    transition_db = _rms_db(_region(preview, "transition"))
    after_db = _rms_db(_region(preview, "after"))
    spectral_hole_db = max(0.0, (before_db + after_db) / 2.0 - transition_db)
    hole_score = _clip01(1.0 - max(0.0, spectral_hole_db - 3.0) / 10.0)
    bass_masking_proxy = _clip01(lf_excess / 0.45)
    lf_score = _clip01(1.0 - lf_excess / 0.45)
    mud_score = _clip01(1.0 - mud_excess / 0.30)
    hf_score = _clip01(1.0 - hf_excess / 0.28)
    score = _clip01(0.30 * lf_score + 0.20 * mud_score + 0.12 * hf_score + 0.23 * continuity + 0.15 * hole_score)
    return {
        "applicable": True,
        "low_frequency_collision_excess_ratio": round(lf_excess, 6),
        "bass_masking_proxy": round(bass_masking_proxy, 6),
        "low_mid_mud_excess_ratio": round(mud_excess, 6),
        "spectral_hole_depth_db": round(spectral_hole_db, 3),
        "high_frequency_buildup_excess_ratio": round(hf_excess, 6),
        "spectral_continuity_proxy": round(continuity, 6),
        "before_profile": {k: round(v, 6) for k, v in before.items()},
        "transition_profile": {k: round(v, 6) for k, v in transition.items()},
        "after_profile": {k: round(v, 6) for k, v in after.items()},
        "score": round(score, 6),
        "precision_note": "band-energy ratios and centroid; not a perceptual-quality model",
    }


def _vocal_metrics(candidate: TransitionCandidate) -> dict[str, Any]:
    source = float(candidate.vocal_overlap_assumptions.get("source_density", candidate.source_segment.vocal_density))
    target = float(candidate.vocal_overlap_assumptions.get("target_density", candidate.target_segment.vocal_density))
    collision = _clip01(source * target)
    intentional = candidate.technique_family == "stem_handoff"
    penalty = collision * (0.25 if intentional else 1.0)
    score = _clip01(1.0 - penalty)
    return {
        "applicable": True,
        "source_vocal_density": round(source, 4),
        "target_vocal_density": round(target, 4),
        "vocal_on_vocal_collision_proxy": round(collision, 6),
        "intentional_vocal_interaction": intentional,
        "accidental_vocal_chopping_proxy": None,
        "stem_bleed_metric": None,
        "score": round(score, 6),
        "precision_note": "uses Phase 1 vocal-density evidence; chopping/bleed deferred without reliable stem-local evidence",
    }


def _energy_metrics(preview: RenderedCandidatePreview, candidate: TransitionCandidate) -> dict[str, Any]:
    before_db = _rms_db(_region(preview, "before"))
    transition_db = _rms_db(_region(preview, "transition"))
    after_db = _rms_db(_region(preview, "after"))
    reference = (before_db + after_db) / 2.0
    dip_db = max(0.0, reference - transition_db)
    spike_db = max(0.0, transition_db - max(before_db, after_db))
    landing_delta = after_db - before_db
    goal = float(candidate.intent.energy_goal)
    if goal > 0.10:
        goal_score = _clip01(1.0 - abs(landing_delta - 2.0) / 8.0)
    elif goal < -0.10:
        goal_score = _clip01(1.0 - abs(landing_delta + 2.0) / 8.0)
    else:
        goal_score = _clip01(1.0 - abs(landing_delta) / 8.0)
    deliberate_release = candidate.technique_family in {"echo_out", "tempo_reset", "phrase_cut"}
    allowed_dip = 9.0 if deliberate_release else 4.5
    dip_score = _clip01(1.0 - max(0.0, dip_db - allowed_dip) / 10.0)
    spike_score = _clip01(1.0 - max(0.0, spike_db - 3.0) / 9.0)
    if candidate.technique_family in {"riser_impact", "loop_shortening"}:
        landing_score = _clip01(1.0 - max(0.0, before_db - after_db - 2.0) / 8.0)
    else:
        landing_score = _clip01(1.0 - abs(landing_delta) / 10.0)
    score = _clip01(0.45 * goal_score + 0.25 * dip_score + 0.15 * spike_score + 0.15 * landing_score)
    return {
        "applicable": True,
        "before_rms_dbfs": round(before_db, 3),
        "transition_rms_dbfs": round(transition_db, 3),
        "after_rms_dbfs": round(after_db, 3),
        "energy_dip_db": round(dip_db, 3),
        "energy_spike_db": round(spike_db, 3),
        "landing_delta_db": round(landing_delta, 3),
        "energy_goal": round(goal, 4),
        "deliberate_release_dip_allowance": deliberate_release,
        "score": round(score, 6),
    }


def _fx_metrics(preview: RenderedCandidatePreview, candidate: TransitionCandidate) -> dict[str, Any]:
    relevant = candidate.technique_family in {"echo_out", "riser_impact", "loop_shortening", "drum_bridge"}
    if not relevant:
        return {"applicable": False, "reason": "candidate family has no Phase 6 FX-specific metric"}
    transition = _region(preview, "transition")
    before = _region(preview, "before")
    after = _region(preview, "after")
    transition_peak_db = _db(_peak(transition))
    context_peak_db = max(_db(_peak(before)), _db(_peak(after)))
    excess_peak_db = max(0.0, transition_peak_db - context_peak_db)
    score_peak = _clip01(1.0 - max(0.0, excess_peak_db - 4.0) / 10.0)
    masking = 0.0
    runaway = 0.0
    if len(transition):
        mono = _mono(transition)
        tail = mono[int(len(mono) * 0.80):]
        tail_db = _rms_db(tail)
        after_head = _mono(after)[: max(1, min(len(after), preview.sample_rate * 2))]
        after_db = _rms_db(after_head)
        masking = max(0.0, tail_db - after_db)
        if candidate.technique_family == "echo_out":
            runaway = max(0.0, masking - 4.0)
    masking_score = _clip01(1.0 - max(0.0, masking - 3.0) / 10.0)
    runaway_score = _clip01(1.0 - runaway / 10.0)
    score = _clip01(0.50 * score_peak + 0.30 * masking_score + 0.20 * runaway_score)
    return {
        "applicable": True,
        "transition_peak_excess_db": round(excess_peak_db, 3),
        "target_landing_masking_proxy_db": round(masking, 3),
        "echo_runaway_proxy_db": round(runaway, 3) if candidate.technique_family == "echo_out" else None,
        "reverb_length_metric": None,
        "modulation_extremity_metric": None,
        "score": round(score, 6),
        "precision_note": "family-conditioned level/tail proxies; unsupported effect internals remain deferred",
    }


def _oversampled_peak_proxy(audio: np.ndarray, sample_rate: int, sample_peak: float) -> tuple[float, str]:
    """Return a bounded-memory 4x polyphase inter-sample peak proxy.

    Very low sample peaks cannot plausibly cross the hard 0 dBFS gate under
    ordinary reconstruction overshoot, so expensive oversampling is reserved
    for previews already near the ceiling. This is deliberately labelled a
    proxy rather than an ITU-R BS.1770 certified true-peak meter.
    """
    if sample_peak < 0.75 or not np.asarray(audio).size:
        return float(sample_peak), "sample_peak_below_oversampling_trigger"
    try:
        from scipy.signal import resample_poly
    except Exception:
        return float(sample_peak), "scipy_unavailable_sample_peak_only"
    values = np.asarray(audio, dtype=np.float32)
    if values.ndim == 1:
        values = values[:, None]
    chunk = max(256, int(sample_rate * 2))
    overlap = min(128, max(16, sample_rate // 100))
    peak = float(sample_peak)
    for start in range(0, len(values), chunk):
        left = max(0, start - overlap)
        right = min(len(values), start + chunk + overlap)
        region = values[left:right]
        for channel in range(region.shape[1]):
            upsampled = resample_poly(region[:, channel].astype(np.float64), 4, 1)
            if upsampled.size:
                peak = max(peak, float(np.max(np.abs(upsampled))))
    return peak, "4x_polyphase_inter_sample_peak_proxy"


def _technical_metrics(preview: RenderedCandidatePreview, config: AuditionConfig) -> tuple[dict[str, Any], list[AuditionFailure]]:
    failures: list[AuditionFailure] = []
    audio = np.asarray(preview.audio)
    finite = bool(audio.size and np.isfinite(audio).all())
    if not finite:
        failures.append(AuditionFailure("non_finite_audio", "preview contains NaN or Inf"))

    # Candidate safety is judged on the rendered transition itself.  The
    # surrounding before/after context is copied source material and may
    # legitimately contain pre-existing mastered peaks at or slightly above
    # 0 dBFS; those peaks must not disqualify every candidate for a handoff.
    # Whole-preview values are still reported for auditability.
    transition = np.asarray(_region(preview, "transition"))
    finite_transition = transition[np.isfinite(transition)] if transition.size else np.asarray([], dtype=np.float32)
    finite_preview = audio[np.isfinite(audio)] if audio.size else np.asarray([], dtype=np.float32)
    peak = float(np.max(np.abs(finite_transition))) if finite_transition.size else 0.0
    clipping_fraction = float(np.mean(np.abs(finite_transition) >= config.sample_clip_threshold)) if finite_transition.size else 0.0
    preview_peak = float(np.max(np.abs(finite_preview))) if finite_preview.size else 0.0
    preview_clipping_fraction = float(np.mean(np.abs(finite_preview) >= config.sample_clip_threshold)) if finite_preview.size else 0.0
    safe_transition = np.nan_to_num(transition, nan=0.0, posinf=0.0, neginf=0.0)
    oversampled_peak, oversampled_peak_status = _oversampled_peak_proxy(safe_transition, preview.sample_rate, peak) if finite else (float("inf"), "non_finite_audio")
    rms_db = _rms_db(safe_transition) if transition.size else -120.0
    silent_fraction = _silent_fraction(safe_transition, preview.sample_rate) if transition.size else 1.0
    jump = _boundary_jump(preview) if finite else float("inf")
    if peak > config.sample_clip_threshold + 1e-7 or clipping_fraction > config.maximum_clipping_fraction:
        failures.append(AuditionFailure(
            "unsafe_sample_peak", "preview exceeds configured sample-peak/clipping safety",
            round(peak, 6), config.sample_clip_threshold,
        ))
    elif oversampled_peak > config.oversampled_peak_threshold + 1e-7:
        failures.append(AuditionFailure(
            "unsafe_oversampled_peak_proxy",
            "4x polyphase inter-sample peak proxy exceeds configured safety ceiling",
            round(oversampled_peak, 6), config.oversampled_peak_threshold,
        ))
    if rms_db <= config.catastrophic_silence_dbfs or silent_fraction > config.maximum_silent_fraction:
        failures.append(AuditionFailure(
            "catastrophic_silence", "preview contains catastrophic/unintended silence",
            round(max(silent_fraction, 0.0), 6), config.maximum_silent_fraction,
        ))
    if jump > config.hard_discontinuity_amplitude:
        failures.append(AuditionFailure(
            "severe_boundary_discontinuity", "preview has a severe sample discontinuity at a handoff boundary",
            round(jump, 6), config.hard_discontinuity_amplitude,
        ))
    if preview.sample_rate <= 0 or preview.channels not in {1, 2} or len(audio) <= 0:
        failures.append(AuditionFailure("invalid_preview_duration", "preview metadata/duration is invalid"))
    if not (0 <= preview.transition_start_sample < preview.transition_end_sample <= len(audio)):
        failures.append(AuditionFailure("broken_preview_bounds", "transition output bounds are outside preview audio"))
    peak_score = _clip01((1.0 - peak) / 0.20) if peak <= 1.0 else 0.0
    silence_score = _clip01(1.0 - silent_fraction / max(config.maximum_silent_fraction, 1e-9))
    discontinuity_score = _clip01(1.0 - jump / max(config.hard_discontinuity_amplitude, 1e-9)) if math.isfinite(jump) else 0.0
    score = _clip01(0.45 * peak_score + 0.30 * silence_score + 0.25 * discontinuity_score)
    return {
        "finite_samples": finite,
        "sample_peak": round(peak, 7),
        "sample_peak_dbfs": round(_db(peak), 3),
        "sample_peak_scope": "transition_only",
        "preview_sample_peak": round(preview_peak, 7),
        "preview_clipping_fraction": round(preview_clipping_fraction, 9),
        "oversampled_peak_proxy": round(oversampled_peak, 7) if math.isfinite(oversampled_peak) else None,
        "oversampled_peak_proxy_dbfs": round(_db(oversampled_peak), 3) if math.isfinite(oversampled_peak) else None,
        "oversampled_peak_status": oversampled_peak_status,
        "clipping_fraction": round(clipping_fraction, 9),
        "rms_dbfs": round(rms_db, 3),
        "near_silent_frame_fraction": round(silent_fraction, 6),
        "boundary_discontinuity_amplitude": round(jump, 7) if math.isfinite(jump) else None,
        "true_peak_metric": None,
        "true_peak_status": "not_itu_certified_use_oversampled_peak_proxy",
        "score": round(score, 6),
    }, failures


def evaluate_candidate_preview(
    candidate: TransitionCandidate,
    preview: RenderedCandidatePreview,
    *,
    config: AuditionConfig | None = None,
) -> CandidateAudition:
    """Measure one rendered candidate and hard-reject invalid previews before scoring."""
    config = config or AuditionConfig()
    config.validate()
    failures: list[AuditionFailure] = []
    expected_binding = {
        "candidate_id": candidate.candidate_id,
        "recipe_id": candidate.recipe.recipe_id,
        "source_track_id": candidate.source_track_id,
        "target_track_id": candidate.target_track_id,
    }
    observed_binding = {
        "candidate_id": preview.candidate_id,
        "recipe_id": preview.recipe_id,
        "source_track_id": preview.source_track_id,
        "target_track_id": preview.target_track_id,
    }
    if expected_binding != observed_binding:
        failures.append(AuditionFailure("identity_binding_mismatch", "preview identity does not match candidate/recipe binding"))
    if preview.renderer_provenance.get("candidate_id") != candidate.candidate_id or preview.renderer_provenance.get("recipe_id") != candidate.recipe.recipe_id:
        failures.append(AuditionFailure("renderer_provenance_mismatch", "renderer provenance is inconsistent with candidate identity"))
    if candidate.stem_requirements and not bool(preview.renderer_provenance.get("required_stems_rendered", False)):
        failures.append(AuditionFailure("invalid_required_stem_use", "candidate requires stems that were not actually rendered"))
    if any(str(item.get("recipe_id", "")) != candidate.recipe.recipe_id for item in preview.sample_layer_provenance):
        failures.append(AuditionFailure("sample_layer_provenance_mismatch", "sample-layer provenance is not bound to the candidate recipe"))
    if bool(preview.renderer_provenance.get("requires_stretch", False)):
        ratio = float(preview.renderer_provenance.get("time_stretch_ratio", 0.0))
        if not 0.75 <= ratio <= 1.333333:
            failures.append(AuditionFailure("unstable_time_stretch_ratio", "declared time-stretch ratio is outside the Phase 6 stable audit range", ratio, "[0.75, 1.333333]"))

    technical, technical_failures = _technical_metrics(preview, config)
    failures.extend(technical_failures)
    beat = _beat_metrics(preview, candidate, config)
    spectral = _spectral_metrics(preview)
    vocal = _vocal_metrics(candidate)
    energy = _energy_metrics(preview, candidate)
    fx = _fx_metrics(preview, candidate)
    harmonic = {
        "applicable": False,
        "status": "deferred",
        "reason": "current Phase 6 core does not claim reliable overlap-local chroma/dissonance from the available preview evidence",
    }
    deferred = [
        "itu_certified_true_peak_measurement",
        "isolated_kick_alignment",
        "stem_bleed_and_vocal_intelligibility",
        "overlap_local_harmonic_quality",
    ]
    if not fx.get("applicable", False):
        deferred.append("family_specific_fx_metric_not_applicable")

    components: dict[str, float] = {
        "technical_margin": float(technical.get("score", 0.0)),
        "spectral_cleanliness": float(spectral.get("score", 0.0)),
        "vocal_safety": float(vocal.get("score", 0.0)),
        "energy_goal_fit": float(energy.get("score", 0.0)),
    }
    if beat.get("applicable"):
        components["beat_stability"] = float(beat.get("score", 0.0))
    if fx.get("applicable"):
        components["fx_safety"] = float(fx.get("score", 0.0))

    hard_rejected = any(item.hard for item in failures)
    active_weight = sum(config.weights.get(name, 0.0) for name in components)
    score = (
        sum(components[name] * config.weights.get(name, 0.0) for name in components) / active_weight
        if active_weight > 0 else 0.0
    )
    if hard_rejected:
        score = 0.0
    metrics = AuditionMetrics(
        technical=technical,
        beat=beat,
        spectral=spectral,
        vocal=vocal,
        harmonic=harmonic,
        energy=energy,
        fx=fx,
        normalized_components={k: round(_clip01(v), 6) for k, v in components.items()},
        deferred=tuple(deferred),
    )
    return CandidateAudition(
        candidate_id=candidate.candidate_id,
        recipe_id=candidate.recipe.recipe_id,
        render_status="hard_rejected" if hard_rejected else "measured",
        hard_rejected=hard_rejected,
        failures=tuple(failures),
        metrics=metrics,
        final_score=round(_clip01(score), 9),
        provenance={
            "audition": "v2_phase6_audition_lab",
            "candidate_id": candidate.candidate_id,
            "recipe_id": candidate.recipe.recipe_id,
            "preview_audio_sha256": preview.audio_sha256,
            "preview_duration_sec": round(preview.exact_duration_sec, 9),
            "sample_rate": preview.sample_rate,
            "channels": preview.channels,
            "score_semantics": "transparent_automated_metrics_not_human_quality_truth",
            "hard_rejection_precedes_soft_score": True,
        },
    )


def audition_candidate(
    candidate: TransitionCandidate,
    source_audio: np.ndarray,
    target_audio: np.ndarray,
    sample_rate: int,
    *,
    preview_config=None,
    config: AuditionConfig | None = None,
    source_stems: dict[str, np.ndarray] | None = None,
    target_stems: dict[str, np.ndarray] | None = None,
) -> CandidateAudition:
    """Render and evaluate one candidate, converting render failures to typed hard rejects."""
    from djenius.audio.audition_renderer import render_candidate_preview

    config = config or AuditionConfig()
    try:
        preview = render_candidate_preview(
            candidate, source_audio, target_audio, sample_rate,
            config=preview_config, source_stems=source_stems, target_stems=target_stems,
        )
    except Exception as exc:
        failure = AuditionFailure(
            code="render_failure",
            message=f"candidate preview render failed: {type(exc).__name__}: {exc}",
        )
        return CandidateAudition(
            candidate_id=candidate.candidate_id,
            recipe_id=candidate.recipe.recipe_id,
            render_status="render_failed",
            hard_rejected=True,
            failures=(failure,),
            metrics=AuditionMetrics(deferred=("metrics_unavailable_due_to_render_failure",)),
            final_score=0.0,
            selection_reason="hard_rejected_before_ranking",
            provenance={
                "audition": "v2_phase6_audition_lab",
                "candidate_id": candidate.candidate_id,
                "recipe_id": candidate.recipe.recipe_id,
                "render_failure_type": type(exc).__name__,
                "hard_rejection_precedes_soft_score": True,
            },
        )
    return evaluate_candidate_preview(candidate, preview, config=config)


def rank_auditions(
    auditions: Iterable[CandidateAudition],
    *,
    config: AuditionConfig | None = None,
) -> AuditionRanking:
    """Rank valid auditions deterministically; hard rejects never receive a rank."""
    config = config or AuditionConfig()
    config.validate()
    items = list(auditions)
    ids = [item.candidate_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("audition ranking requires unique candidate IDs")
    survivors = sorted(
        (item for item in items if not item.hard_rejected),
        key=lambda item: (-item.final_score, item.candidate_id),
    )
    ranked: dict[str, CandidateAudition] = {}
    for index, item in enumerate(survivors, 1):
        ranked[item.candidate_id] = replace(
            item,
            rank=index,
            selected=index == 1,
            selection_reason=(
                "selected_best_current_transparent_automated_score"
                if index == 1 else "survived_but_ranked_below_selected_candidate"
            ),
        )
    for item in items:
        if item.hard_rejected:
            ranked[item.candidate_id] = replace(
                item,
                rank=None,
                selected=False,
                selection_reason="hard_rejected_before_ranking",
            )
    ordered = tuple(
        [ranked[item.candidate_id] for item in survivors]
        + [ranked[item.candidate_id] for item in sorted((x for x in items if x.hard_rejected), key=lambda x: x.candidate_id)]
    )
    ranking_order = tuple(item.candidate_id for item in ordered if item.rank is not None)
    return AuditionRanking(
        auditions=ordered,
        selected_candidate_id=survivors[0].candidate_id if survivors else None,
        survivor_count=len(survivors),
        rejected_count=len(items) - len(survivors),
        ranking_order=ranking_order,
        config=config.to_dict(),
    )
