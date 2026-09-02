"""Source-provenance checks for rendered DJ timelines."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable


LOOPING_TRANSITIONS = {"loop_blend"}


def audit_source_provenance(
    events: Iterable[dict],
    track_lengths: dict[str, int],
) -> dict:
    """Audit declared source intervals against output order and track bounds."""
    ordered_events = sorted(events, key=lambda event: event["output_start_sample"])
    intervals_by_track: dict[str, list[dict]] = defaultdict(list)
    violations: list[dict] = []
    intentional_loops: list[dict] = []
    previous_output_end = 0

    for event_index, event in enumerate(ordered_events):
        output_start = event["output_start_sample"]
        output_end = event["output_end_sample"]
        if output_start != previous_output_end:
            violations.append({
                "kind": "output_gap" if output_start > previous_output_end else "output_overlap",
                "event_index": event_index,
                "expected_output_start_sample": previous_output_end,
                "actual_output_start_sample": output_start,
            })
        previous_output_end = max(previous_output_end, output_end)

        if event["type"] == "track":
            _check_interval(
                event_index=event_index,
                role="body",
                track_id=event["track_id"],
                start=event["source_start_sample"],
                end=event["source_end_sample"],
                output_start=output_start,
                output_end=output_end,
                track_length=track_lengths[event["track_id"]],
                intervals_by_track=intervals_by_track,
                violations=violations,
            )
            planned_exit = event.get("planned_source_exit_sample")
            if planned_exit is not None and event["source_end_sample"] > planned_exit:
                violations.append({
                    "kind": "body_past_planned_exit",
                    "event_index": event_index,
                    "track_id": event["track_id"],
                    "body_end_sample": event["source_end_sample"],
                    "planned_exit_sample": planned_exit,
                })
            continue

        transition_type = event["transition_type"]
        _check_interval(
            event_index=event_index,
            role="transition_source",
            track_id=event["source_track_id"],
            start=event["source_start_sample"],
            end=event["source_end_sample"],
            output_start=output_start,
            output_end=output_end,
            track_length=track_lengths[event["source_track_id"]],
            intervals_by_track=intervals_by_track,
            violations=violations,
        )
        _check_interval(
            event_index=event_index,
            role="transition_target",
            track_id=event["target_track_id"],
            start=event["target_start_sample"],
            end=event["target_end_sample"],
            output_start=output_start,
            output_end=output_end,
            track_length=track_lengths[event["target_track_id"]],
            intervals_by_track=intervals_by_track,
            violations=violations,
        )
        if transition_type in LOOPING_TRANSITIONS:
            intentional_loops.append({
                "kind": "intentional_loop",
                "event_index": event_index,
                "track_id": event["source_track_id"],
                "source_start_sample": event["source_start_sample"],
                "source_end_sample": event["source_end_sample"],
                "output_start_sample": output_start,
                "output_end_sample": output_end,
            })

    kinds = {violation["kind"] for violation in violations}
    return {
        "violations": violations,
        "intentional_loops": intentional_loops,
        "duplicate_source_region_detected": "duplicate_source_interval" in kinds,
        "unexpected_backwards_jump": "unexpected_backwards_source_jump" in kinds,
        "body_past_planned_exit": "body_past_planned_exit" in kinds,
        "transition_after_eof": "transition_after_eof" in kinds,
        "unexpected_timeline_gap": "output_gap" in kinds,
        "clean": not violations,
    }


def _check_interval(
    *,
    event_index: int,
    role: str,
    track_id: str,
    start: int,
    end: int,
    output_start: int,
    output_end: int,
    track_length: int,
    intervals_by_track: dict[str, list[dict]],
    violations: list[dict],
) -> None:
    if start < 0 or end <= start:
        violations.append({
            "kind": "invalid_source_interval",
            "event_index": event_index,
            "track_id": track_id,
            "role": role,
            "source_start_sample": start,
            "source_end_sample": end,
        })
        return
    if end > track_length:
        violations.append({
            "kind": "transition_after_eof" if role.startswith("transition") else "body_after_eof",
            "event_index": event_index,
            "track_id": track_id,
            "role": role,
            "source_end_sample": end,
            "track_length_samples": track_length,
        })

    previous = intervals_by_track[track_id]
    if previous:
        latest_end = max(interval["end"] for interval in previous)
        if start < latest_end:
            violations.append({
                "kind": "unexpected_backwards_source_jump",
                "event_index": event_index,
                "track_id": track_id,
                "role": role,
                "source_start_sample": start,
                "previous_source_end_sample": latest_end,
            })
        for interval in previous:
            overlap_start = max(start, interval["start"])
            overlap_end = min(end, interval["end"])
            if overlap_end > overlap_start:
                violations.append({
                    "kind": "duplicate_source_interval",
                    "event_index": event_index,
                    "track_id": track_id,
                    "role": role,
                    "source_start_sample": overlap_start,
                    "source_end_sample": overlap_end,
                    "previous_event_index": interval["event_index"],
                })
                break

    previous.append({
        "start": start,
        "end": end,
        "event_index": event_index,
        "role": role,
        "output_start": output_start,
        "output_end": output_end,
    })


def audit_performance_provenance(events: Iterable[dict], track_lengths: dict[str, int]) -> dict:
    """Audit V9 appearance/transition mappings without track-cursor assumptions.

    A transition is allowed to overlap the tail/head it explicitly declares;
    ordinary appearances of a repeated track still must use disjoint source
    regions.  This is deliberately additive so V5.3's strict audit remains
    unchanged.
    """
    violations: list[dict] = []
    appearances = [event for event in events if event.get("type") == "appearance"]
    for index, event in enumerate(appearances):
        track_id = event.get("track_id", "")
        start = int(event.get("source_start_sample", -1))
        end = int(event.get("source_end_sample", -1))
        output_start = int(event.get("output_start_sample", -1))
        output_end = int(event.get("output_end_sample", -1))
        if track_id not in track_lengths or start < 0 or end <= start or end > track_lengths.get(track_id, 0):
            violations.append({"kind": "appearance_out_of_bounds", "event_index": index, "track_id": track_id})
        if output_start < 0 or output_end <= output_start:
            violations.append({"kind": "invalid_appearance_output", "event_index": index})
    by_track: dict[str, list[dict]] = defaultdict(list)
    for event in appearances:
        by_track[event.get("track_id", "")].append(event)
    for track_id, items in by_track.items():
        for index, left in enumerate(items):
            for right in items[index + 1:]:
                overlap = min(left["source_end_sample"], right["source_end_sample"]) - max(left["source_start_sample"], right["source_start_sample"])
                exact = left["source_start_sample"] == right["source_start_sample"] and left["source_end_sample"] == right["source_end_sample"]
                if exact or overlap > max(1, int(track_lengths.get(track_id, 1) * 0.01)):
                    if not left.get("reprise") or not right.get("reprise") or exact:
                        violations.append({"kind": "unplanned_duplicate_source_region", "track_id": track_id})
    for index, event in enumerate(event for event in events if event.get("type") == "performance_transition"):
        for key in ("source_track_id", "target_track_id"):
            track_id = event.get(key, "")
            start = int(event.get(f"{key.split('_')[0]}_start_sample", -1))
            end = int(event.get(f"{key.split('_')[0]}_end_sample", -1))
            if track_id not in track_lengths or start < 0 or end <= start or end > track_lengths[track_id]:
                violations.append({"kind": "transition_source_out_of_bounds", "event_index": index, "track_id": track_id})
    layered = [event for event in events if event.get("type") == "layered"]
    layered_regions: set[tuple[str, str, int, int]] = set()
    for index, event in enumerate(layered):
        output_start = int(event.get("output_start_sample", -1))
        output_end = int(event.get("output_end_sample", -1))
        if output_start < 0 or output_end <= output_start:
            violations.append({"kind": "invalid_layer_output", "event_index": index})
        sources = event.get("sources", [])
        if not sources:
            violations.append({"kind": "layer_has_no_declared_sources", "event_index": index})
        expected_length = output_end - output_start
        stretch_ratio = float(event.get("time_stretch_ratio", 1.0) or 1.0)
        for source_index, source in enumerate(sources):
            track_id = str(source.get("track_id", ""))
            stem = str(source.get("stem", ""))
            start = int(source.get("start_sample", -1))
            end = int(source.get("end_sample", -1))
            if track_id not in track_lengths or start < 0 or end <= start or end > track_lengths.get(track_id, 0):
                violations.append({
                    "kind": "layer_source_out_of_bounds",
                    "event_index": index,
                    "source_index": source_index,
                    "track_id": track_id,
                    "stem": stem,
                })
            expected_source_length = expected_length
            if stem == "vocals" and 0.85 <= stretch_ratio <= 1.18:
                expected_source_length = int(round(expected_length * stretch_ratio))
            # Audio backends may round a time-stretched interval by a few
            # samples.  Keep the declared ratio authoritative but allow a
            # small bounded conversion tolerance.
            tolerance = max(2, int(round(expected_source_length * 0.005)))
            if abs((end - start) - expected_source_length) > tolerance:
                violations.append({
                    "kind": "layer_source_duration_mismatch",
                    "event_index": index,
                    "source_index": source_index,
                })
            if stem not in {"vocals", "drums", "bass", "other"}:
                violations.append({"kind": "unknown_layer_stem", "event_index": index, "stem": stem})
            region = (track_id, stem, start, end)
            if region in layered_regions:
                violations.append({"kind": "duplicate_layer_source_region", "event_index": index, "track_id": track_id, "stem": stem})
            layered_regions.add(region)
        vocal_tracks = {str(item.get("track_id", "")) for item in sources if item.get("stem") == "vocals"}
        backing_tracks = {str(item.get("track_id", "")) for item in sources if item.get("stem") in {"drums", "bass", "other"}}
        if vocal_tracks & backing_tracks:
            violations.append({"kind": "same_track_layered_sources", "event_index": index})
        backing_stems = {
            str(item.get("stem", ""))
            for item in sources
            if item.get("stem") in {"drums", "bass", "other"}
        }
        if backing_tracks and backing_stems != {"drums", "bass", "other"}:
            violations.append({"kind": "incomplete_layer_backing", "event_index": index})
    return {
        "clean": not violations,
        "violations": violations,
        "appearance_count": len(appearances),
        "layered_event_count": len(layered),
    }
