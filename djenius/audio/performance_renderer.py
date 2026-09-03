"""Safe renderer adapter for V9 performance timelines.

It decodes through the same fallback loader and applies the existing V5.3
transition DSP to explicit segment arrays.  The classic ``render_mix`` path
is not modified or used for performance timelines.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
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
    stem_audio: dict[str, dict[str, np.ndarray]] | None = None,
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
            body_start = 0
        else:
            transition = timeline.transitions[index - 1]
            overlap = min(
                len(previous_segment), len(current_stereo),
                max(1, int(round(transition.overlap_duration_sec * sample_rate))),
            )
            source_tail = previous_segment
            target_head = current_stereo
            output_start = len(output) - overlap
            body_start = len(output)
            target_consumed = min(
                len(current_stereo),
                max(
                    overlap,
                    int(round(
                        (transition.target_consumed_duration_sec or transition.overlap_duration_sec)
                        * sample_rate
                    )),
                ),
            )
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
                # V9.1 passes the selected transition-window evidence rather
                # than whole-track averages.  The classic renderer still
                # receives its original track-level contract.
                source_low_energy=transition.source_bass_activity,
                source_mid_energy=transition.source_local_energy,
                target_low_energy=transition.target_bass_activity,
                target_mid_energy=transition.target_local_energy,
                use_time_stretch=transition.requires_stretch,
                technique_operations=transition.technique_operations,
            )
            if len(transition_audio) != overlap:
                raise ValueError("Performance transition produced an unexpected duration")
            generated_fx = [
                {
                    "source_type": "generated_fx",
                    "effect_type": operation.get("effect", "riser"),
                    "seed": operation.get("seed", 0),
                    "output_start_sample": output_start,
                    "output_end_sample": output_start + overlap,
                }
                for operation in (transition.technique_operations or [])
                if operation.get("type") == "generated_fx"
            ]
            # A stretched beatmatched target may consume more source than
            # the rendered overlap.  Start the solo target body after the
            # declared consumed interval; using ``overlap`` here would replay
            # the target's opening source region.
            output = np.concatenate([output[:-overlap], _to_stereo(transition_audio), current_stereo[target_consumed:]], axis=0)
            out_start = output_start
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
                "transition_bars": transition.length_bars,
                "phase_error_ms": transition.phase_error_ms,
                "pair_quality": transition.pair_quality,
                "technical_score": transition.technical_score,
                "source_track_title": tracks[timeline.appearances[index - 1].segment.track_id].title,
                "target_track_title": tracks[segment.track_id].title,
                "source_segment_id": timeline.appearances[index - 1].segment.id,
                "target_segment_id": segment.id,
                "source_section": transition.source_section,
                "target_section": transition.target_section,
                "source_local_energy": transition.source_local_energy,
                "target_local_energy": transition.target_local_energy,
                "source_local_loudness": transition.source_local_loudness,
                "target_local_loudness": transition.target_local_loudness,
                "local_loudness_delta": round(transition.target_local_loudness - transition.source_local_loudness, 4),
                "source_bass_activity": transition.source_bass_activity,
                "target_bass_activity": transition.target_bass_activity,
                "source_vocal_density": transition.source_vocal_density,
                "target_vocal_density": transition.target_vocal_density,
                "requires_time_stretch": transition.requires_stretch,
                "target_consumed_duration_sec": transition.target_consumed_duration_sec,
                "local_context_score": transition.local_context_score,
                "local_harmonic_score": transition.local_harmonic_score,
                "local_rhythm_score": transition.local_rhythm_score,
                "local_energy_score": transition.local_energy_score,
                "local_energy_slope_score": transition.local_energy_slope_score,
                "local_timbre_score": transition.local_timbre_score,
                "local_bass_score": transition.local_bass_score,
                "local_vocal_score": transition.local_vocal_score,
                "local_confidence": transition.local_confidence,
                "transition_explanation": transition.explanation,
                "technique_intent": transition.technique_intent,
                "technique_name": transition.technique_name,
                "technique_confidence": transition.technique_confidence,
                "technique_reason": transition.technique_reason,
                "technique_operations": transition.technique_operations,
                "generated_fx_provenance": generated_fx,
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
            # The body starts after the preceding overlap.  This is the
            # renderer's authoritative output coordinate for optional layers.
            "body_start_sample": int(body_start),
        })
        previous_segment = current_stereo
        if progress_callback:
            progress_callback(30 + (index + 1) / max(len(timeline.appearances), 1) * 55, f"Rendering appearance {index + 1}/{len(timeline.appearances)}")

    if len(output) == 0:
        raise ValueError("Performance timeline produced no audio")
    layered_count = 0
    if timeline.layered_events and stem_audio:
        if progress_callback:
            progress_callback(87, "Applying safe layered performance moments...")
        for raw_event in timeline.layered_events:
            event = raw_event if isinstance(raw_event, dict) else raw_event.to_dict()
            try:
                rendered_event = _apply_layered_event(
                    output,
                    event,
                    events,
                    stem_audio,
                    sample_rate,
                )
                events.append(rendered_event)
                layered_count += 1
            except (KeyError, ValueError, IndexError) as exc:
                # A layer is an optional creative enhancement.  A bad cache,
                # stale plan, or missing stem must never make a normal V10
                # performance unsafe or unrenderable.
                logger.warning("Layered event %s declined; using normal performance: %s", event.get("id", ""), exc)
                events.append({
                    "type": "layer_fallback",
                    "layer_id": event.get("id", ""),
                    "reason": str(exc),
                })
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
        "layered_events": layered_count,
        "file_size_mb": round(os.path.getsize(output_path) / (1024 * 1024), 1),
    }


def _stereo_region(stem: np.ndarray, start_sample: int, end_sample: int) -> np.ndarray:
    """Extract a stereo stem region without changing channel semantics."""
    if stem.ndim == 1:
        stem = np.column_stack([stem, stem])
    elif stem.ndim != 2:
        raise ValueError("stem audio must be one- or two-dimensional")
    if start_sample < 0 or end_sample <= start_sample or end_sample > len(stem):
        raise ValueError("layer stem source interval is outside the cached stem")
    region = np.asarray(stem[start_sample:end_sample], dtype=np.float32)
    if region.shape[1] == 1:
        region = np.repeat(region, 2, axis=1)
    if region.shape[1] != 2:
        raise ValueError("layer stem must be mono or stereo")
    return region


def _fit_stereo_length(audio: np.ndarray, length: int, sample_rate: int, rate: float) -> np.ndarray:
    """Fit a layer to the backing phrase, preserving pitch when possible."""
    if len(audio) == length:
        return audio
    if not 0.85 <= rate <= 1.18:
        raise ValueError("layer time-stretch ratio is outside the safe range")
    stretched = None
    try:
        import pyrubberband as pyrb

        channels = [pyrb.time_stretch(audio[:, index], sample_rate, rate) for index in range(audio.shape[1])]
        stretched = np.column_stack(channels).astype(np.float32)
    except Exception as exc:
        logger.warning("Pitch-preserving layer stretch unavailable; declining layer: %s", exc)
    if stretched is None:
        # FFmpeg's atempo filter is already the renderer's supported local
        # fallback and preserves pitch for the small ratios admitted above.
        try:
            with tempfile.TemporaryDirectory(prefix="djenius-layer-") as temp_dir:
                input_path = Path(temp_dir) / "in.wav"
                output_path = Path(temp_dir) / "out.wav"
                sf.write(str(input_path), audio, sample_rate)
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(input_path),
                     "-filter:a", f"atempo={rate:.6f}", str(output_path)],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                stretched, _ = sf.read(str(output_path), dtype="float32")
                stretched = _to_stereo(stretched).astype(np.float32)
        except Exception as exc:
            logger.warning("FFmpeg layer stretch unavailable; declining layer: %s", exc)
    if stretched is None:
        raise ValueError("pitch-preserving layer time-stretch is unavailable")
    if len(stretched) < length:
        stretched = np.pad(stretched, ((0, length - len(stretched)), (0, 0)))
    return stretched[:length]


def _apply_layered_event(
    output: np.ndarray,
    event: dict,
    appearance_events: list[dict],
    stem_audio: dict[str, dict[str, np.ndarray]],
    sample_rate: int,
) -> dict:
    """Render one explicit vocals-A + drums/bass/other-B region in place."""
    vocal_track = str(event.get("vocal_track_id", ""))
    instrumental_track = str(event.get("instrumental_track_id", ""))
    if not vocal_track or not instrumental_track or vocal_track == instrumental_track:
        raise ValueError("layer needs two different source tracks")
    source_stems = stem_audio.get(vocal_track, {})
    target_stems = stem_audio.get(instrumental_track, {})
    if any(name not in source_stems for name in ("vocals",)) or any(name not in target_stems for name in ("drums", "bass", "other")):
        raise ValueError("layer is missing a required cached stem")
    target_appearance_id = event.get("target_appearance_id", "")
    target_event = next((item for item in appearance_events if item.get("appearance_id") == target_appearance_id), None)
    if target_event is None:
        raise ValueError("layer target appearance is not in the rendered timeline")
    start = int(target_event.get("body_start_sample", -1))
    # The planner's logical appearance start includes the preceding overlap;
    # the renderer's body_start is the authoritative coordinate for the first
    # post-handoff layer.  An optional explicit body offset supports future
    # in-body creative events without guessing from logical coordinates.
    start += max(0, int(round(float(event.get("body_offset_sec", 0.0)) * sample_rate)))
    end = start + int(round(float(event.get("output_end_sec", 0.0) - event.get("output_start_sec", 0.0)) * sample_rate))
    if end <= start or start < 0 or end > len(output):
        raise ValueError("layer output interval is outside the rendered body")
    vocal_start = int(round(float(event.get("vocal_source_start_sec", 0.0)) * sample_rate))
    vocal_end = int(round(float(event.get("vocal_source_end_sec", 0.0)) * sample_rate))
    inst_start = int(round(float(event.get("instrumental_source_start_sec", 0.0)) * sample_rate))
    inst_end = int(round(float(event.get("instrumental_source_end_sec", 0.0)) * sample_rate))
    length = end - start
    vocal_source = _stereo_region(source_stems["vocals"], vocal_start, vocal_end)
    vocals = _fit_stereo_length(
        vocal_source,
        length,
        sample_rate,
        float(event.get("time_stretch_ratio", 1.0)),
    )
    instrumental = np.zeros((length, 2), dtype=np.float32)
    for name in event.get("instrumental_stems", ["drums", "bass", "other"]):
        backing = _stereo_region(target_stems[name], inst_start, inst_end)
        if len(backing) < length:
            backing = np.pad(backing, ((0, length - len(backing)), (0, 0)))
        instrumental += backing[:length]
    vocal_gain = db_to_linear(float(event.get("vocal_gain_db", -1.5)))
    instrumental_gain = db_to_linear(float(event.get("instrumental_gain_db", -5.0)))
    layer = vocals * vocal_gain + instrumental * instrumental_gain
    fade_in = min(length // 2, max(1, int(float(event.get("entry_fade_sec", 1.5)) * sample_rate)))
    fade_out = min(length // 2, max(1, int(float(event.get("exit_fade_sec", 1.5)) * sample_rate)))
    envelope = np.ones(length, dtype=np.float32)
    envelope[:fade_in] = np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    envelope[-fade_out:] = np.minimum(envelope[-fade_out:], np.linspace(1.0, 0.0, fade_out, dtype=np.float32))
    base = output[start:end].copy()
    base_rms = float(np.sqrt(np.mean(np.square(base))) + 1e-9)
    layer_rms = float(np.sqrt(np.mean(np.square(layer))) + 1e-9)
    match_db = float(np.clip(20.0 * np.log10(base_rms / layer_rms), -3.0, 6.0))
    layer *= db_to_linear(match_db)
    output[start:end] = base * (1.0 - envelope[:, None]) + layer * envelope[:, None]
    return {
        "type": "layered",
        "layer_id": event.get("id", ""),
        "output_start_sample": start,
        "output_end_sample": end,
        "vocal_track_id": vocal_track,
        "instrumental_track_id": instrumental_track,
        "vocal_source_start_sample": vocal_start,
        "vocal_source_end_sample": vocal_end,
        "instrumental_source_start_sample": inst_start,
        "instrumental_source_end_sample": inst_end,
        "instrumental_stems": list(event.get("instrumental_stems", ["drums", "bass", "other"])),
        "vocal_gain_db": float(event.get("vocal_gain_db", -1.5)),
        "instrumental_gain_db": float(event.get("instrumental_gain_db", -5.0)),
        "rms_match_gain_db": round(match_db, 3),
        "time_stretch_ratio": float(event.get("time_stretch_ratio", 1.0)),
        "confidence": float(event.get("confidence", 0.0)),
        "reason": event.get("reason", ""),
        "sources": [
            {"track_id": vocal_track, "stem": "vocals", "start_sample": vocal_start, "end_sample": vocal_end},
            *[
                {"track_id": instrumental_track, "stem": name, "start_sample": inst_start, "end_sample": inst_end}
                for name in event.get("instrumental_stems", ["drums", "bass", "other"])
            ],
        ],
    }
