"""Deterministic full-context scoring for musical DJ transitions."""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

import numpy as np

from djenius.core.intent import SetIntent, TransitionStyle, VocalPreference
from djenius.core.models import (
    EnergyProfile,
    TrackProfile,
    TransitionQualityScore,
    TransitionRecipe,
    TransitionType,
)
from djenius.core.scorer import score_compatibility


def playtime_bounds(track: TrackProfile) -> tuple[float, float, float]:
    """Return minimum, preferred, and maximum useful body playtime."""
    duration = max(1.0, track.duration_sec)
    minimum = min(90.0, max(55.0, duration * 0.28))
    preferred = min(180.0, max(70.0, duration * 0.48))
    maximum = min(300.0, max(120.0, duration * 0.78))
    return minimum, preferred, maximum


def target_entry_limit(track: TrackProfile) -> float:
    """Keep normal entries near the beginning of the target's musical story."""
    return min(max(45.0, track.duration_sec * 0.30), 180.0)


def score_transition_candidate(
    source: TrackProfile,
    target: TrackProfile,
    source_exit_time: float,
    target_entry_time: float,
    overlap_duration: float,
    transition_type: TransitionType,
    *,
    incoming_source_cursor: float = 0.0,
    intent: Optional[SetIntent] = None,
    energy_profile: EnergyProfile = EnergyProfile.STEADY,
) -> tuple[TransitionQualityScore, TransitionRecipe, dict]:
    """Score one exit/entry/type/length combination using full context."""
    compat = score_compatibility(source, target)
    style = intent.effective_transition_style() if intent else TransitionStyle.SAFE
    vocal_preference = (
        intent.effective_vocal_preference() if intent else VocalPreference.ANY
    )

    source_bar_score, source_bar_index, source_bar_error = _alignment_score(
        source_exit_time, source.analysis.bar_times, source.bpm,
    )
    target_bar_score, target_bar_index, target_bar_error = _alignment_score(
        target_entry_time, target.analysis.bar_times, target.bpm,
    )
    source_phrase_score, source_phrase_error = _phrase_score(source, source_exit_time)
    target_phrase_score, target_phrase_error = _phrase_score(target, target_entry_time)
    phrase_score = (source_phrase_score + target_phrase_score) / 2.0
    bar_score = (source_bar_score + target_bar_score) / 2.0

    target_consumed = _target_consumed_seconds(
        transition_type, overlap_duration, source.bpm, target.bpm,
    )
    target_resume = target_entry_time + target_consumed

    source_relative_energy = _curve_mean(
        source.analysis.energy_curve,
        source_exit_time - 8.0,
        source_exit_time,
        source.duration_sec,
        source.mean_energy,
    )
    target_entry_relative_energy = _curve_mean(
        target.analysis.energy_curve,
        target_entry_time,
        target_entry_time + min(8.0, target_consumed),
        target.duration_sec,
        target.mean_energy,
    )
    target_landing_relative_energy = _curve_mean(
        target.analysis.energy_curve,
        target_resume,
        target_resume + 10.0,
        target.duration_sec,
        target.mean_energy,
    )
    source_energy = _absolute_local_rms(source, source_relative_energy)
    target_entry_energy = _absolute_local_rms(target, target_entry_relative_energy)
    target_landing_energy = _absolute_local_rms(target, target_landing_relative_energy)
    source_normalization_db, target_normalization_db = _pair_normalization_gain_db(
        source, target,
    )
    source_energy *= 10.0 ** (source_normalization_db / 20.0)
    target_entry_energy *= 10.0 ** (target_normalization_db / 20.0)
    target_landing_energy *= 10.0 ** (target_normalization_db / 20.0)
    energy_delta_db = _ratio_db(target_landing_energy, source_energy)
    energy_score = _energy_continuity_score(energy_delta_db, energy_profile, style)
    landing_score = _landing_score(
        source_energy, target_entry_energy, target_landing_energy, energy_profile,
    )

    source_loudness = _normalized_local_loudness(
        source, source_exit_time - 8.0, source_exit_time,
    )
    target_loudness = _normalized_local_loudness(
        target, target_resume, target_resume + 10.0,
    )
    loudness_delta = target_loudness - source_loudness
    loudness_score = max(0.0, 1.0 - abs(loudness_delta) / 8.0)
    transition_floor_score, predicted_trough_db = _transition_floor_score(
        source,
        target,
        source_exit_time,
        target_entry_time,
        overlap_duration,
        target_consumed,
        source_loudness,
        target_loudness,
        transition_type,
    )

    source_bass = _curve_mean(
        source.analysis.low_energy_curve,
        source_exit_time,
        source_exit_time + overlap_duration,
        source.duration_sec,
        source.analysis.low_energy,
    )
    target_bass = _curve_mean(
        target.analysis.low_energy_curve,
        target_entry_time,
        target_entry_time + target_consumed,
        target.duration_sec,
        target.analysis.low_energy,
    )
    bass_score, bass_mode = _bass_handoff_score(
        source_bass, target_bass, transition_type,
    )

    source_vocal = _vocal_fraction(
        source.analysis.vocal_regions,
        source_exit_time,
        source_exit_time + overlap_duration,
    )
    target_vocal = _vocal_fraction(
        target.analysis.vocal_regions,
        target_entry_time,
        target_entry_time + target_consumed,
    )
    vocal_collision = source_vocal * target_vocal
    vocal_score = max(0.0, 1.0 - vocal_collision)
    if vocal_preference == VocalPreference.VOCAL_SAFE:
        vocal_score = max(0.0, 1.0 - vocal_collision * 2.5)

    source_section = section_at(source, source_exit_time)
    target_section = section_at(target, target_entry_time)
    structural_score = _structural_context_score(source_section, target_section)
    style_score = _transition_style_score(
        transition_type=transition_type,
        style=style,
        phrase_score=phrase_score,
        tempo_score=compat.tempo_score,
        energy_delta=energy_delta_db,
        landing_score=landing_score,
        source_bass=source_bass,
        target_bass=target_bass,
        source_vocal=source_vocal,
        target_vocal=target_vocal,
        source_section=source_section,
        source=source,
        target=target,
    )
    body_play = source_exit_time - incoming_source_cursor
    playtime_score = _playtime_score(source, body_play)

    weights = _weights_for_intent(style, vocal_preference, energy_profile)
    components = {
        "phrase": phrase_score,
        "bar": bar_score,
        "tempo": compat.tempo_score,
        "harmonic": compat.key_score,
        "energy": energy_score,
        "loudness": loudness_score,
        "bass": bass_score,
        "vocal": vocal_score,
        "structure": structural_score,
        "style": style_score,
        "playtime": playtime_score,
        "landing": landing_score,
        "floor": transition_floor_score,
    }
    overall = sum(components[name] * weight for name, weight in weights.items())
    overall /= sum(weights.values())

    analysis_confidence = (
        source.analysis.analysis_confidence
        + target.analysis.analysis_confidence
        + source.analysis.bpm_confidence
        + target.analysis.bpm_confidence
        + source.analysis.key_confidence
        + target.analysis.key_confidence
    ) / 6.0
    confidence = np.clip(
        0.55 * analysis_confidence + 0.25 * phrase_score + 0.20 * overall,
        0.0,
        1.0,
    )

    quality = TransitionQualityScore(
        phrase_alignment_score=round(phrase_score, 4),
        bar_alignment_score=round(bar_score, 4),
        tempo_compatibility_score=round(compat.tempo_score, 4),
        harmonic_compatibility_score=round(compat.key_score, 4),
        energy_continuity_score=round(energy_score, 4),
        loudness_continuity_score=round(loudness_score, 4),
        bass_handoff_score=round(bass_score, 4),
        vocal_clash_score=round(vocal_score, 4),
        structural_context_score=round(structural_score, 4),
        transition_style_fit_score=round(style_score, 4),
        track_playtime_score=round(playtime_score, 4),
        target_landing_score=round(landing_score, 4),
        transition_floor_score=round(transition_floor_score, 4),
        overall_score=round(float(overall), 4),
    )
    target_gain_db = float(np.clip(-loudness_delta, -3.0, 3.0))
    vocal_policy = (
        "strict_no_overlap"
        if vocal_preference == VocalPreference.VOCAL_SAFE
        else "avoid_overlap"
    )
    reasoning = (
        f"{source_section}->{target_section}; phrase={phrase_score:.2f}; "
        f"landing={landing_score:.2f}; energy_delta={energy_delta_db:+.1f}dB; "
        f"loudness_delta={loudness_delta:+.1f}dB; vocals={vocal_collision:.2f}"
    )
    recipe = TransitionRecipe(
        source_gain_db=0.0,
        target_gain_db=round(target_gain_db, 2),
        landing_gain_decay_sec=10.0,
        bass_handoff_mode=bass_mode,
        vocal_policy=vocal_policy,
        energy_delta=round(energy_delta_db, 4),
        confidence=round(float(confidence), 4),
        reasoning=reasoning,
    )
    details = {
        "source_section": source_section,
        "target_section": target_section,
        "source_phrase_alignment_error_ms": round(source_phrase_error, 1),
        "target_phrase_alignment_error_ms": round(target_phrase_error, 1),
        "source_bar_alignment_error_ms": round(source_bar_error, 1),
        "target_bar_alignment_error_ms": round(target_bar_error, 1),
        "source_bar_index": source_bar_index,
        "target_bar_index": target_bar_index,
        "phrase_length_bars": 8,
        "body_play_sec": round(body_play, 3),
        "source_context_energy": round(source_energy, 6),
        "target_entry_energy": round(target_entry_energy, 6),
        "target_landing_energy": round(target_landing_energy, 6),
        "source_relative_energy": round(source_relative_energy, 4),
        "target_entry_relative_energy": round(target_entry_relative_energy, 4),
        "target_landing_relative_energy": round(target_landing_relative_energy, 4),
        "energy_delta_db": round(energy_delta_db, 3),
        "predicted_transition_trough_db": round(predicted_trough_db, 3),
        "source_context_loudness": round(source_loudness, 3),
        "target_landing_loudness": round(target_loudness, 3),
        "loudness_delta_db": round(loudness_delta, 3),
        "source_bass": round(source_bass, 4),
        "target_bass": round(target_bass, 4),
        "source_vocal_fraction": round(source_vocal, 4),
        "target_vocal_fraction": round(target_vocal, 4),
        "vocal_collision": round(vocal_collision, 4),
        "components": {name: round(value, 4) for name, value in components.items()},
    }
    return quality, recipe, details


def quality_dict(quality: TransitionQualityScore) -> dict:
    return asdict(quality)


def section_at(track: TrackProfile, time_sec: float) -> str:
    for start, end, label in track.analysis.structural_sections:
        if start <= time_sec < end:
            return label
    if time_sec <= max(track.analysis.intro_end, track.duration_sec * 0.08):
        return "intro"
    if time_sec >= track.analysis.outro_start:
        return "outro"
    return "unknown"


def _alignment_score(
    time_sec: float,
    bar_times: list[float],
    bpm: float,
) -> tuple[float, int, float]:
    if not bar_times or bpm <= 0:
        return 0.35, -1, 1000.0
    index = min(range(len(bar_times)), key=lambda i: abs(bar_times[i] - time_sec))
    error = (time_sec - bar_times[index]) * 1000.0
    tolerance_ms = max(40.0, (60.0 / bpm) * 1000.0 * 0.20)
    score = max(0.0, 1.0 - abs(error) / (tolerance_ms * 4.0))
    return score, index, error


def _phrase_score(track: TrackProfile, time_sec: float) -> tuple[float, float]:
    bar_score, bar_index, bar_error_ms = _alignment_score(
        time_sec, track.analysis.bar_times, track.bpm,
    )
    if bar_index < 0:
        return 0.3, 1000.0
    group_distance = min(bar_index % 8, 8 - (bar_index % 8))
    grouped_score = max(0.0, 1.0 - group_distance / 4.0) * bar_score
    bar_duration = 4 * 60.0 / max(track.bpm, 60)
    grouped_error_ms = group_distance * bar_duration * 1000.0 + abs(bar_error_ms)
    if not track.analysis.phrase_boundaries:
        return grouped_score, grouped_error_ms
    nearest = min(track.analysis.phrase_boundaries, key=lambda t: abs(t - time_sec))
    error_ms = (time_sec - nearest) * 1000.0
    phrase_duration = 8 * 4 * 60.0 / max(track.bpm, 60)
    detected_score = max(0.0, 1.0 - abs(error_ms) / (phrase_duration * 500.0))
    if grouped_score >= detected_score:
        return grouped_score, grouped_error_ms
    return detected_score, error_ms


def _curve_mean(
    curve: list[float],
    start: float,
    end: float,
    duration: float,
    fallback: float,
) -> float:
    if not curve or duration <= 0 or end <= start:
        return float(fallback)
    count = len(curve)
    first = max(0, min(count - 1, int(start / duration * count)))
    last = max(first + 1, min(count, int(np.ceil(end / duration * count))))
    return float(np.mean(curve[first:last]))


def _normalized_local_loudness(track: TrackProfile, start: float, end: float) -> float:
    local = _curve_mean(
        track.analysis.loudness_curve,
        start,
        end,
        track.duration_sec,
        track.analysis.integrated_lufs,
    )
    return local - track.analysis.integrated_lufs


def _vocal_fraction(regions: list[tuple[float, float]], start: float, end: float) -> float:
    if end <= start:
        return 0.0
    overlap = sum(
        max(0.0, min(end, region_end) - max(start, region_start))
        for region_start, region_end in regions
    )
    return min(1.0, overlap / (end - start))


def _absolute_local_rms(track: TrackProfile, relative_energy: float) -> float:
    """Combine within-track energy shape with a cross-track RMS anchor."""
    base_rms = track.analysis.rms_energy
    if base_rms <= 1e-6:
        base_rms = 10.0 ** (track.analysis.integrated_lufs / 20.0)
    relative_scale = relative_energy / max(track.mean_energy, 0.05)
    return max(1e-6, float(base_rms * relative_scale))


def _pair_normalization_gain_db(
    source: TrackProfile,
    target: TrackProfile,
) -> tuple[float, float]:
    """Estimate the renderer's bounded global normalization for one pair."""
    reference = (source.analysis.integrated_lufs + target.analysis.integrated_lufs) / 2.0
    source_gain = float(np.clip(reference - source.analysis.integrated_lufs, -4.0, 4.0))
    target_gain = float(np.clip(reference - target.analysis.integrated_lufs, -4.0, 4.0))
    return source_gain, target_gain


def _ratio_db(value: float, reference: float) -> float:
    return float(20.0 * np.log10(max(value, 1e-6) / max(reference, 1e-6)))


def _transition_floor_score(
    source: TrackProfile,
    target: TrackProfile,
    source_exit: float,
    target_entry: float,
    overlap: float,
    target_consumed: float,
    source_anchor_db: float,
    target_anchor_db: float,
    transition_type: TransitionType,
) -> tuple[float, float]:
    """Predict short troughs from the audio context consumed by the blend."""
    window_count = max(4, int(np.ceil(overlap / 2.0)))
    worst_trough_db = 0.0
    for index in range(window_count):
        progress = (index + 0.5) / window_count
        source_time = source_exit + progress * overlap
        target_time = target_entry + progress * target_consumed
        source_db = _normalized_local_loudness(source, source_time - 1.0, source_time + 1.0)
        target_db = _normalized_local_loudness(target, target_time - 1.0, target_time + 1.0)
        if transition_type == TransitionType.PHRASE_CUT:
            source_gain = 0.0
            target_gain = 1.0
        else:
            source_gain = np.cos(progress * np.pi / 2.0)
            target_gain = np.sin(progress * np.pi / 2.0)
        combined_power = (
            (source_gain * 10.0 ** (source_db / 20.0)) ** 2
            + (target_gain * 10.0 ** (target_db / 20.0)) ** 2
        )
        combined_db = 10.0 * np.log10(max(combined_power, 1e-12))
        expected_db = (
            source_anchor_db * (1.0 - progress)
            + target_anchor_db * progress
        )
        worst_trough_db = max(worst_trough_db, expected_db - combined_db)
    score = 1.0 - max(0.0, worst_trough_db - 1.5) / 7.5
    return float(np.clip(score, 0.0, 1.0)), float(worst_trough_db)


def _energy_continuity_score(
    delta_db: float,
    profile: EnergyProfile,
    style: str,
) -> float:
    if profile in (EnergyProfile.SLOW_BUILD, EnergyProfile.WARMUP_TO_PEAK):
        if -0.75 <= delta_db <= 2.5:
            return 1.0
        if delta_db < -0.75:
            return max(0.0, 1.0 - abs(delta_db + 0.75) / 5.0)
        return max(0.0, 1.0 - (delta_db - 2.5) / 5.0)
    tolerance_db = 5.0 if style == TransitionStyle.ENERGETIC else 3.5
    return max(0.0, 1.0 - abs(delta_db) / tolerance_db)


def _landing_score(
    source_energy: float,
    entry_energy: float,
    landing_energy: float,
    profile: EnergyProfile,
) -> float:
    score = 1.0
    source_to_landing_db = _ratio_db(landing_energy, source_energy)
    entry_to_landing_db = _ratio_db(landing_energy, entry_energy)
    if source_to_landing_db < -2.0 and profile != EnergyProfile.COOLDOWN:
        score *= max(0.0, 1.0 - abs(source_to_landing_db + 2.0) / 6.0)
    if entry_to_landing_db < -2.5:
        score *= max(0.35, 1.0 - abs(entry_to_landing_db + 2.5) / 8.0)
    return float(np.clip(score, 0.0, 1.0))


def _bass_handoff_score(
    source_bass: float,
    target_bass: float,
    transition_type: TransitionType,
) -> tuple[float, str]:
    source_active = source_bass >= 0.25
    target_active = target_bass >= 0.25
    if source_active and target_active:
        if transition_type in (
            TransitionType.BASS_SWAP,
            TransitionType.FILTER_SWEEP,
            TransitionType.CROSSFADE,
        ):
            return 0.9, "source_to_target"
        return 0.55, "source_to_target"
    if source_active:
        return 0.85, "source_dominant"
    if target_active:
        return 0.85, "target_dominant"
    return 0.45, "low_bass_transition"


def _structural_context_score(source_section: str, target_section: str) -> float:
    preferred = {
        ("outro", "intro"): 1.0,
        ("outro", "verse"): 0.95,
        ("chorus", "intro"): 0.9,
        ("chorus", "verse"): 0.85,
        ("verse", "intro"): 0.85,
        ("verse", "verse"): 0.8,
        ("bridge", "intro"): 0.75,
        ("bridge", "verse"): 0.7,
    }
    if (source_section, target_section) in preferred:
        return preferred[(source_section, target_section)]
    if target_section == "chorus":
        return 0.35
    if source_section == "intro":
        return 0.3
    return 0.55


def _transition_style_score(
    *,
    transition_type: TransitionType,
    style: str,
    phrase_score: float,
    tempo_score: float,
    energy_delta: float,
    landing_score: float,
    source_bass: float,
    target_bass: float,
    source_vocal: float,
    target_vocal: float,
    source_section: str,
    source: TrackProfile,
    target: TrackProfile,
) -> float:
    if transition_type == TransitionType.CROSSFADE:
        score = 0.75 + 0.20 * min(tempo_score, landing_score)
        if style == TransitionStyle.SMOOTH:
            score += 0.05
    elif transition_type == TransitionType.BEATMATCHED_BLEND:
        score = 0.55 * tempo_score + 0.25 * phrase_score + 0.20 * landing_score
        if min(source.analysis.bpm_confidence, target.analysis.bpm_confidence) < 0.6:
            score *= 0.65
    elif transition_type == TransitionType.BASS_SWAP:
        score = 0.45 * tempo_score + 0.25 * phrase_score + 0.30 * landing_score
        if source_bass >= 0.25 and target_bass >= 0.25:
            score += 0.12
        if style != TransitionStyle.ENERGETIC:
            score *= 0.75
    elif transition_type == TransitionType.FILTER_SWEEP:
        score = 0.35 * phrase_score + 0.30 * landing_score + 0.20 * tempo_score + 0.15
        if style == TransitionStyle.SMOOTH:
            score += 0.05
    elif transition_type == TransitionType.PHRASE_CUT:
        score = 0.55 * phrase_score + 0.35 * landing_score + 0.10 * tempo_score
        if style == TransitionStyle.SMOOTH:
            score *= 0.55
        elif style == TransitionStyle.ENERGETIC and energy_delta >= -1.0:
            score += 0.08
    elif transition_type == TransitionType.ECHO_OUT:
        score = 0.55 * phrase_score + 0.25 * landing_score + 0.20
        if source_section != "outro" or source_vocal > 0.35:
            score *= 0.55
    elif transition_type == TransitionType.LOOP_BLEND:
        score = 0.40 * phrase_score + 0.30 * tempo_score + 0.30 * landing_score
        if source_vocal > 0.2 or style != TransitionStyle.VARIED:
            score *= 0.4
    elif transition_type == TransitionType.MASHUP:
        score = 0.8 if source.analysis.stems and target.analysis.stems else 0.1
    else:
        score = 0.5
    if source_vocal > 0.5 and target_vocal > 0.5 and transition_type not in (
        TransitionType.PHRASE_CUT,
        TransitionType.MASHUP,
    ):
        score *= 0.7
    return float(np.clip(score, 0.0, 1.0))


def _playtime_score(track: TrackProfile, body_play: float) -> float:
    minimum, preferred, maximum = playtime_bounds(track)
    if body_play < minimum:
        return max(0.0, body_play / max(minimum, 1.0)) * 0.5
    if body_play <= preferred:
        return 0.5 + 0.5 * (body_play - minimum) / max(preferred - minimum, 1.0)
    if body_play <= maximum:
        return 1.0 - 0.25 * (body_play - preferred) / max(maximum - preferred, 1.0)
    return max(0.2, 0.75 - (body_play - maximum) / max(maximum, 1.0))


def _weights_for_intent(
    style: str,
    vocal_preference: str,
    energy_profile: EnergyProfile,
) -> dict[str, float]:
    weights = {
        "phrase": 1.4,
        "bar": 0.7,
        "tempo": 1.0,
        "harmonic": 0.8,
        "energy": 1.3,
        "loudness": 1.2,
        "bass": 0.9,
        "vocal": 1.0,
        "structure": 1.1,
        "style": 1.0,
        "playtime": 1.0,
        "landing": 1.4,
        "floor": 1.4,
    }
    if style == TransitionStyle.SMOOTH:
        weights["energy"] = 1.7
        weights["loudness"] = 1.6
        weights["harmonic"] = 1.1
        weights["bass"] = 1.2
        weights["vocal"] = 2.0
        weights["floor"] = 2.0
    if style == TransitionStyle.ENERGETIC:
        weights["phrase"] = 1.7
        weights["landing"] = 1.7
        weights["style"] = 1.4
        weights["floor"] = 1.6
    if energy_profile == EnergyProfile.WARMUP_TO_PEAK:
        weights["energy"] = 2.0
        weights["landing"] = 1.8
    if vocal_preference == VocalPreference.VOCAL_SAFE:
        weights["vocal"] = 3.0
    return weights


def _target_consumed_seconds(
    transition_type: TransitionType,
    overlap_duration: float,
    source_bpm: float,
    target_bpm: float,
) -> float:
    if (
        transition_type == TransitionType.BEATMATCHED_BLEND
        and source_bpm > 0
        and target_bpm > 0
        and abs(source_bpm - target_bpm) > 0.5
    ):
        return overlap_duration * source_bpm / target_bpm
    return overlap_duration
