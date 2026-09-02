"""Safe renderer adapter for V9 performance timelines.

It decodes through the same fallback loader and applies the existing V5.3
transition DSP to explicit segment arrays.  The classic ``render_mix`` path
is not modified or used for performance timelines.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from djenius.audio.provenance import audit_performance_provenance
from djenius.audio.renderer import _compute_track_gain_db, _load_audio, _to_stereo
from djenius.audio.transitions import apply_transition
from djenius.core.models import SetPlan
from djenius.core.performance import require_valid_performance_timeline
from djenius.utils.audio_math import db_to_linear, normalize_lufs, soft_clip

logger = logging.getLogger(__name__)


def render_performance_mix(
    plan: SetPlan,
    output_path: str,
    *,
    target_lufs: float = -14.0,
    sample_rate: int = 44100,
    progress_callback=None,
) -> dict:
    """Render explicit source appearances with declared provenance."""
    timeline = plan.performance_timeline
    if timeline is None:
        raise ValueError("Performance render requires a performance timeline")
    tracks = {track.id: track for track in plan.tracks}
    require_valid_performance_timeline(timeline, {key: item.duration_sec for key, item in tracks.items()})
    t0 = time.time()
    if progress_callback:
        progress_callback(0, "Loading performance sources...")
    audio: dict[str, np.ndarray] = {}
    gains = _compute_track_gain_db(plan)
    for index, track in enumerate(tracks.values()):
        y, _source_sr = _load_audio(track.filepath, sample_rate)
        audio[track.id] = y * db_to_linear(gains.get(track.id, 0.0))
        if progress_callback:
            progress_callback(10 + (index + 1) / max(len(tracks), 1) * 20, f"Loading source {index + 1}/{len(tracks)}: {track.title}")

    output = np.zeros((0, 2), dtype=np.float32)
    previous_segment: np.ndarray | None = None
    events: list[dict] = []
    transition_count = 0
    for index, appearance in enumerate(timeline.appearances):
        segment = appearance.segment
        source = audio[segment.track_id]
        left = max(0, int(round(segment.source_start_sec * sample_rate)))
        right = min(len(source), int(round(segment.source_end_sec * sample_rate)))
        current = source[left:right]
        if len(current) == 0:
            raise ValueError(f"Performance segment {appearance.id} decoded to no audio")
        current_stereo = _to_stereo(current).astype(np.float32)
        if previous_segment is None:
            output = current_stereo
            out_start = 0
        else:
            transition = timeline.transitions[index - 1]
            overlap = min(
                len(previous_segment), len(current_stereo),
                max(1, int(round(transition.overlap_duration_sec * sample_rate))),
            )
            source_tail = previous_segment
            target_head = current_stereo
            output_start = len(output) - overlap
            transition_audio = apply_transition(
                source_audio=source_tail,
                target_audio=target_head,
                sr=sample_rate,
                transition_type=transition.transition_type.value,
                overlap_samples=overlap,
                source_exit_sample=len(source_tail) - overlap,
                target_entry_sample=0,
                source_bpm=tracks[timeline.appearances[index - 1].segment.track_id].bpm,
                target_bpm=tracks[segment.track_id].bpm,
                source_low_energy=tracks[timeline.appearances[index - 1].segment.track_id].analysis.low_energy,
                source_mid_energy=tracks[timeline.appearances[index - 1].segment.track_id].analysis.mid_energy,
                target_low_energy=tracks[segment.track_id].analysis.low_energy,
                target_mid_energy=tracks[segment.track_id].analysis.mid_energy,
                use_time_stretch=False,
            )
            if len(transition_audio) != overlap:
                raise ValueError("Performance transition produced an unexpected duration")
            output = np.concatenate([output[:-overlap], _to_stereo(transition_audio), current_stereo[overlap:]], axis=0)
            out_start = len(output) - len(current_stereo)
            events.append({
                "type": "performance_transition",
                "source_appearance_id": timeline.appearances[index - 1].id,
                "target_appearance_id": appearance.id,
                "source_track_id": timeline.appearances[index - 1].segment.track_id,
                "target_track_id": segment.track_id,
                "source_start_sample": int(round(transition.source_start_sec * sample_rate)),
                "source_end_sample": int(round(transition.source_end_sec * sample_rate)),
                "target_start_sample": int(round(transition.target_start_sec * sample_rate)),
                "target_end_sample": int(round(transition.target_end_sec * sample_rate)),
                "output_start_sample": output_start,
                "output_end_sample": output_start + overlap,
                "mix_start_sample": output_start,
                "mix_end_sample": output_start + overlap,
                "transition_type": transition.transition_type.value,
                "confidence": transition.confidence,
            })
            transition_count += 1
        out_end = out_start + len(current_stereo)
        events.append({
            "type": "appearance",
            "appearance_id": appearance.id,
            "track_id": segment.track_id,
            "track_title": tracks[segment.track_id].title,
            "source_start_sample": left,
            "source_end_sample": right,
            "output_start_sample": out_start,
            "output_end_sample": out_end,
            "reprise": appearance.reprise,
            "section_type": segment.section_type,
            "semantic_role": segment.semantic_role,
            "intent_score": appearance.intent_score,
            "intent_status": appearance.intent_status,
        })
        previous_segment = current_stereo
        if progress_callback:
            progress_callback(30 + (index + 1) / max(len(timeline.appearances), 1) * 55, f"Rendering appearance {index + 1}/{len(timeline.appearances)}")

    if len(output) == 0:
        raise ValueError("Performance timeline produced no audio")
    audit = audit_performance_provenance(events, {key: len(value) for key, value in audio.items()})
    if not audit["clean"]:
        raise RuntimeError(f"Performance provenance audit failed: {audit['violations']}")
    if progress_callback:
        progress_callback(90, "Mastering performance...")
    try:
        output = normalize_lufs(output, sample_rate, target_lufs)
        output = _to_stereo(output) if output.ndim == 1 else output
    except Exception as exc:
        logger.warning("Performance LUFS normalization failed: %s", exc)
        peak = float(np.max(np.abs(output)))
        if peak > 0:
            output *= db_to_linear(-1.0) / peak
    output = soft_clip(output, threshold_db=-1.0)
    output_path = str(Path(output_path).absolute())
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, output, sample_rate, subtype="PCM_24")
    elapsed = time.time() - t0
    diagnostics_path = Path(output_path).with_name(Path(output_path).stem + "_diagnostics.json")
    events_for_file = []
    for event in events:
        item = dict(event)
        for key in list(item):
            if key.endswith("_sample"):
                item[key.replace("_sample", "_sec")] = round(item[key] / sample_rate, 3)
        if event["type"] == "appearance":
            item["source_region"] = [item["source_start_sec"], item["source_end_sec"]]
        events_for_file.append(item)
    diagnostics = {
        "mode": "segment",
        "performance_style": timeline.performance_style,
        "output_path": output_path,
        "sample_rate": sample_rate,
        "total_duration_sec": round(len(output) / sample_rate, 3),
        "events": events_for_file,
        "provenance_audit": audit,
        "target_duration_sec": timeline.target_duration_sec,
    }
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")
    if progress_callback:
        progress_callback(100, f"Done in {elapsed:.1f}s")
    return {
        "output_path": output_path,
        "duration_sec": round(len(output) / sample_rate, 1),
        "sample_rate": sample_rate,
        "channels": 2,
        "format": "wav",
        "peak_db": round(float(20 * np.log10(np.max(np.abs(output)) + 1e-10)), 1),
        "transitions_rendered": transition_count,
        "render_time_sec": round(elapsed, 1),
        "diagnostics": [],
        "timeline_diagnostics_path": str(diagnostics_path),
        "provenance_audit": audit,
        "performance_mode": "segment",
        "performance_style": timeline.performance_style,
        "appearance_count": len(timeline.appearances),
        "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 1),
    }
