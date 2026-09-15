"""Continuous renderer for a :mod:`joint_reference_set` pilot plan.

Each frozen reference performance is rendered intact.  Natural playback fills
the establishment regions between performances, with sample-aligned seam
crossfades and a slow gain bridge between independently level-matched template
renders.  No loop/effect tail is touched: joins occur only after the template's
declared postlanding establishment window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from djenius.audio.reference_template_renderer import (
    ReferenceRenderInputs,
    RenderedReferenceTemplate,
    render_reference_template,
)
from djenius.core.joint_reference_set import JointReferenceSetPlan
from djenius.core.models import TrackAnalysis
from djenius.utils.audio_math import normalize_lufs, soft_clip


JOINT_SET_RENDERER_VERSION = "joint-reference-set-renderer-1"
JOIN_SEAM_SEC = 0.040


@dataclass(frozen=True)
class JointTrackRenderMaterial:
    audio: np.ndarray
    stems: dict[str, np.ndarray]
    analysis: TrackAnalysis
    sample_rate: int = 44100


@dataclass(frozen=True)
class RenderedJointReferenceSet:
    audio: np.ndarray
    sample_rate: int
    transition_landings: tuple[int, ...]
    transition_excerpt_ranges: tuple[tuple[int, int], ...]
    provenance: dict[str, Any]

    def transition_excerpt(self, index: int) -> np.ndarray:
        start, end = self.transition_excerpt_ranges[index]
        return self.audio[start:end].copy()


def _stereo(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    if values.ndim == 1:
        return np.column_stack((values, values)).astype(np.float32)
    if values.ndim != 2 or values.shape[1] not in {1, 2}:
        raise ValueError("joint-set audio must be mono or stereo")
    return (
        np.repeat(values, 2, axis=1).astype(np.float32)
        if values.shape[1] == 1
        else values
    )


def _slice(
    audio: np.ndarray, start_sec: float, end_sec: float, sample_rate: int
) -> np.ndarray:
    values = _stereo(audio)
    start = max(0, min(len(values), int(round(start_sec * sample_rate))))
    end = max(start, min(len(values), int(round(end_sec * sample_rate))))
    return values[start:end].copy()


def _rms(audio: np.ndarray) -> float:
    values = np.asarray(audio, dtype=np.float64)
    return float(np.sqrt(np.mean(values * values) + 1e-20))


def _match_gain(reference: np.ndarray, material: np.ndarray, sample_rate: int) -> float:
    window = max(1, min(len(reference), len(material), int(round(0.5 * sample_rate))))
    if not window:
        return 1.0
    return float(
        np.clip(_rms(reference[-window:]) / _rms(material[:window]), 0.25, 4.0)
    )


def _gain_bridge(audio: np.ndarray, start_gain: float, end_gain: float) -> np.ndarray:
    values = _stereo(audio).copy()
    if not len(values):
        return values
    start_db = 20 * np.log10(max(start_gain, 1e-8))
    end_db = 20 * np.log10(max(end_gain, 1e-8))
    phase = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, len(values), dtype=np.float64))
    gain = 10 ** ((start_db + (end_db - start_db) * phase) / 20)
    return (values * gain[:, None]).astype(np.float32)


def _append_aligned(
    left: np.ndarray, right: np.ndarray, seam: int
) -> tuple[np.ndarray, int]:
    """Append aligned material and return its output start sample.

    The last ``seam`` samples of ``left`` and first ``seam`` samples of
    ``right`` represent the same source-time interval.
    """
    left, right = _stereo(left), _stereo(right)
    seam = min(seam, len(left), len(right))
    if seam <= 0:
        return np.concatenate((left, right)).astype(np.float32), len(left)
    angle = np.linspace(0, np.pi / 2, seam, dtype=np.float32)
    mixed = (
        left[-seam:] * np.cos(angle)[:, None] + right[:seam] * np.sin(angle)[:, None]
    )
    start = len(left) - seam
    return np.concatenate((left[:-seam], mixed, right[seam:])).astype(np.float32), start


def _bar_duration(analysis: TrackAnalysis, index: int) -> float:
    grid = np.asarray(analysis.downbeat_times or analysis.bar_times, dtype=float)
    if len(grid) > 1:
        index = max(0, min(index, len(grid) - 2))
        return float(grid[index + 1] - grid[index])
    return 240.0 / max(analysis.bpm, 1.0)


def _source_pre_start(instance, analysis: TrackAnalysis) -> float:
    grid = np.asarray(analysis.downbeat_times or analysis.bar_times, dtype=float)
    return float(grid[max(0, instance.anchors.source_start_bar_index - 4)])


def _global_master(
    audio: np.ndarray, sample_rate: int, target_lufs: float
) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32)
    try:
        values = normalize_lufs(values, sample_rate, target_lufs)
    except Exception:
        pass
    values = soft_clip(values, threshold_db=-1.0).astype(np.float32)
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    if peak > 0.95:
        values *= 0.95 / peak
    return values.astype(np.float32)


def render_joint_reference_set(
    plan: JointReferenceSetPlan,
    materials: Mapping[str, JointTrackRenderMaterial],
    *,
    target_lufs: float = -14.0,
    time_fit_backend: str = "auto",
) -> RenderedJointReferenceSet:
    """Render one continuous plan without invoking any legacy transition path."""
    if len(plan.transitions) != len(plan.tracks) - 1:
        raise ValueError(
            "joint plan must contain one transition per adjacent track pair"
        )
    missing = {track.id for track in plan.tracks} - set(materials)
    if missing:
        raise ValueError(
            f"joint-set render material missing: {','.join(sorted(missing))}"
        )
    rates = {materials[track.id].sample_rate for track in plan.tracks}
    if len(rates) != 1:
        raise ValueError("all joint-set materials must share one sample rate")
    sample_rate = rates.pop()
    seam = max(1, int(round(JOIN_SEAM_SEC * sample_rate)))

    edges: list[RenderedReferenceTemplate] = []
    edge_metadata: list[dict[str, Any]] = []
    for transition, source, target in zip(
        plan.transitions, plan.tracks[:-1], plan.tracks[1:]
    ):
        if transition.instance is None:
            raise ValueError("joint-set transition has no selected template instance")
        source_material, target_material = materials[source.id], materials[target.id]
        rendered = render_reference_template(
            transition.instance,
            ReferenceRenderInputs(
                source_audio=source_material.audio,
                target_audio=target_material.audio,
                source_stems=source_material.stems,
                target_stems=target_material.stems,
                source_analysis=source_material.analysis,
                target_analysis=target_material.analysis,
                sample_rate=sample_rate,
            ),
            target_lufs=target_lufs,
            time_fit_backend=time_fit_backend,
        )
        tail_end = float(
            rendered.provenance["fx_tail"].get("fx_tail_end_sec_relative_landing", 0.0)
        )
        if tail_end * sample_rate + rendered.landing_sample >= len(rendered.audio):
            raise RuntimeError(
                "template tail exceeds the protected postlanding render window"
            )
        edges.append(rendered)
        edge_metadata.append(
            {
                "transition_index": transition.index,
                "source_track_id": source.id,
                "target_track_id": target.id,
                "template_render": rendered.provenance,
            }
        )

    first_transition = plan.transitions[0]
    first_source = plan.tracks[0]
    first_material = materials[first_source.id]
    first_pre = _source_pre_start(first_transition.instance, first_material.analysis)
    opening_start = max(0.0, first_pre - plan.config.opening_establishment_sec)
    opening = _slice(
        first_material.audio, opening_start, first_pre + JOIN_SEAM_SEC, sample_rate
    )
    opening_gain = _match_gain(
        edges[0].audio[: max(1, int(0.5 * sample_rate))],
        opening[-max(1, int(0.5 * sample_rate)) :],
        sample_rate,
    )
    opening *= opening_gain
    output, edge_start = _append_aligned(opening, edges[0].audio, seam)
    landings = [edge_start + edges[0].landing_sample]
    transition_starts = [
        edge_start
        + int(
            round(
                (first_transition.instance.anchors.source_start_sec - first_pre)
                * sample_rate
            )
        )
    ]
    joins: list[dict[str, Any]] = [
        {
            "kind": "opening_to_transition",
            "track_id": first_source.id,
            "source_time_sec": first_pre,
            "output_sample": edge_start,
            "seam_samples": seam,
            "opening_gain": round(opening_gain, 6),
            "sample_aligned": True,
        }
    ]

    for edge_index in range(1, len(edges)):
        previous_transition = plan.transitions[edge_index - 1]
        transition = plan.transitions[edge_index]
        current_track = plan.tracks[edge_index]
        current_material = materials[current_track.id]
        previous_target_end = previous_transition.instance.anchors.target_post_end_sec
        next_pre = _source_pre_start(transition.instance, current_material.analysis)
        bridge_start = previous_target_end - JOIN_SEAM_SEC
        bridge_end = next_pre + JOIN_SEAM_SEC
        if bridge_end <= bridge_start:
            raise RuntimeError(
                "outgoing source cue overlaps protected incoming establishment window"
            )
        bridge = _slice(current_material.audio, bridge_start, bridge_end, sample_rate)
        start_gain = _match_gain(
            output[-max(1, int(0.5 * sample_rate)) :], bridge, sample_rate
        )
        end_reference = edges[edge_index].audio[: max(1, int(0.5 * sample_rate))]
        end_material = bridge[-max(1, int(0.5 * sample_rate)) :]
        end_gain = float(np.clip(_rms(end_reference) / _rms(end_material), 0.25, 4.0))
        bridge = _gain_bridge(bridge, start_gain, end_gain)
        output, bridge_output_start = _append_aligned(output, bridge, seam)
        output, next_edge_start = _append_aligned(output, edges[edge_index].audio, seam)
        landings.append(next_edge_start + edges[edge_index].landing_sample)
        transition_starts.append(
            next_edge_start
            + int(
                round(
                    (transition.instance.anchors.source_start_sec - next_pre)
                    * sample_rate
                )
            )
        )
        joins.append(
            {
                "kind": "target_establishment_bridge",
                "track_id": current_track.id,
                "source_start_sec": round(bridge_start, 6),
                "source_end_sec": round(bridge_end, 6),
                "output_start_sample": bridge_output_start,
                "incoming_join_output_sample": bridge_output_start,
                "outgoing_join_output_sample": next_edge_start,
                "seam_samples": seam,
                "start_gain": round(start_gain, 6),
                "end_gain": round(end_gain, 6),
                "sample_aligned_at_outgoing_source_cue": True,
                "incoming_template_tail_preserved_before_join": True,
            }
        )

    last_transition = plan.transitions[-1]
    last_track = plan.tracks[-1]
    last_material = materials[last_track.id]
    target_end = last_transition.instance.anchors.target_post_end_sec
    closing_end = min(
        last_track.duration_sec, target_end + plan.config.closing_establishment_sec
    )
    closing = _slice(
        last_material.audio, target_end - JOIN_SEAM_SEC, closing_end, sample_rate
    )
    closing_gain = _match_gain(
        output[-max(1, int(0.5 * sample_rate)) :], closing, sample_rate
    )
    closing *= closing_gain
    output, closing_start = _append_aligned(output, closing, seam)
    joins.append(
        {
            "kind": "transition_to_closing_establishment",
            "track_id": last_track.id,
            "source_time_sec": target_end,
            "output_start_sample": closing_start,
            "output_sample": closing_start,
            "seam_samples": seam,
            "closing_gain": round(closing_gain, 6),
            "incoming_template_tail_preserved_before_join": True,
        }
    )

    mastered = _global_master(output, sample_rate, target_lufs)
    excerpt_ranges: list[tuple[int, int]] = []
    for transition, start, landing in zip(
        plan.transitions, transition_starts, landings
    ):
        source_bar = _bar_duration(
            materials[transition.source_track_id].analysis,
            transition.instance.anchors.source_start_bar_index,
        )
        excerpt_start = max(0, start - int(round(2 * source_bar * sample_rate)))
        excerpt_end = min(
            len(mastered), landing + int(round(4 * source_bar * sample_rate))
        )
        excerpt_ranges.append((excerpt_start, excerpt_end))

    delta = (
        np.max(np.abs(np.diff(mastered, axis=0)), axis=1)
        if len(mastered) > 1
        else np.zeros(1)
    )
    join_samples: list[tuple[str, int]] = []
    for join in joins:
        for field in (
            "output_sample",
            "incoming_join_output_sample",
            "outgoing_join_output_sample",
        ):
            if field in join:
                join_samples.append((f"{join['kind']}:{field}", int(join[field])))
    seam_diagnostics = []
    for label, position in join_samples:
        local = delta[max(0, position - 128) : min(len(delta), position + 128)]
        exact = delta[max(0, position - 4) : min(len(delta), position + 4)]
        one_second = delta[
            max(0, position - sample_rate) : min(len(delta), position + sample_rate)
        ]
        seam_diagnostics.append(
            {
                "join": label,
                "output_sample": position,
                "exact_boundary_max_sample_delta": round(
                    float(np.max(exact)) if len(exact) else 0.0,
                    6,
                ),
                "max_sample_delta_near_join": round(
                    float(np.max(local)) if len(local) else 0.0, 6
                ),
                "local_one_second_sample_delta_p99_9": round(
                    float(np.quantile(one_second, 0.999)) if len(one_second) else 0.0,
                    6,
                ),
            }
        )
    provenance = {
        "renderer_version": JOINT_SET_RENDERER_VERSION,
        "plan_id": plan.plan_id,
        "continuous_render": True,
        "legacy_set_renderer_used": False,
        "sample_rate": sample_rate,
        "duration_sec": round(len(mastered) / sample_rate, 6),
        "transition_landings": list(landings),
        "transition_excerpt_ranges": [list(item) for item in excerpt_ranges],
        "joins": joins,
        "seam_diagnostics": seam_diagnostics,
        "transitions": edge_metadata,
        "target_stream_continuity": "template target clock retained through postlanding window, then sample-aligned natural playback",
        "tail_policy": "all inter-track joins occur after each frozen template's bounded tail and establishment window",
        "global_sample_delta_p99_9": round(float(np.quantile(delta, 0.999)), 6),
        "sample_peak": round(float(np.max(np.abs(mastered))), 6),
        "clipping_fraction": round(float(np.mean(np.abs(mastered) >= 0.999)), 9),
    }
    return RenderedJointReferenceSet(
        mastered,
        sample_rate,
        tuple(landings),
        tuple(excerpt_ranges),
        provenance,
    )
