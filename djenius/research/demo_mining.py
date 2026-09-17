"""Conservative shadow mining of private DJ-reference change regions.

This module enriches coarse, *unverified* finished-audio changes with
repeat-like and original-alignment evidence. It emits private JSON only. No
inferred DJ action is promoted to the production archetype/selection stack.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from djenius.research.demo_alignment import _fingerprint


WAVE_RATE = 2000


def decode_reference_wave_for_ephemeral_checks(path: Path) -> np.ndarray:
    """Decode in memory only; never persist source waveform in metadata/cache."""
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn",
         "-ac", "1", "-ar", str(WAVE_RATE), "-f", "f32le", "pipe:1"],
        capture_output=True, check=True, timeout=900,
    )
    return np.frombuffer(result.stdout, dtype="<f4")


def waveform_repeat_evidence(wave: np.ndarray, center_sec: float) -> dict:
    """Exact-ish audio repeat, far stricter than harmonic similarity alone."""
    best = {"normalized_waveform_correlation": -1.0}
    center = int(round(center_sec))
    for period in (2, 4, 8):
        length = period * WAVE_RATE
        for start_sec in range(max(0, center - 24), center + 4):
            first = start_sec * WAVE_RATE
            middle = first + length
            stop = middle + length
            if stop > len(wave):
                continue
            a = wave[first:middle]
            b = wave[middle:stop]
            a_energy = float(np.dot(a, a))
            b_energy = float(np.dot(b, b))
            if min(a_energy, b_energy) / max(len(a), 1) < 1e-5:
                continue
            corr = float(np.dot(a, b) / np.sqrt(a_energy * b_energy))
            if corr > best["normalized_waveform_correlation"]:
                best = {
                    "period_sec": period,
                    "first_start_sec": start_sec,
                    "second_start_sec": start_sec + period,
                    "normalized_waveform_correlation": round(corr, 5),
                }
    best["status"] = ("EXACT_LIKE_AUDIO_REPEAT_NOT_PROOF_OF_DJ_LOOP"
                      if best["normalized_waveform_correlation"] >= .88
                      else "NO_EXACT_LIKE_AUDIO_REPEAT")
    return best


def cached_waveform_repeats(path: Path, content_sha256: str, candidates: list[dict],
                            cache_dir: Path) -> list[dict]:
    """Cache scalar evidence only, never waveform samples."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    centers = [candidate["center_sec"] for candidate in candidates]
    key = hashlib.sha256(json.dumps([content_sha256, "exact-repeat-v1", centers]).encode()).hexdigest()
    cache_path = cache_dir / f"{key}.json"
    if cache_path.exists():
        values = json.loads(cache_path.read_text())
        if len(values) != len(candidates):
            raise ValueError("Repeat-evidence cache length mismatch")
        return values
    wave = decode_reference_wave_for_ephemeral_checks(path)
    values = [waveform_repeat_evidence(wave, center) for center in centers]
    cache_path.write_text(json.dumps(values, sort_keys=True) + "\n")
    return values


def repeat_evidence(chroma: np.ndarray, center_sec: float) -> dict:
    """Adjacent repeated-harmony evidence; not a loop-intent classifier."""
    center = int(round(center_sec))
    best = None
    for period in (2, 4, 8, 16):
        for start in range(max(0, center - 32), min(center + 8, len(chroma) - 2 * period)):
            first = chroma[start:start + period]
            second = chroma[start + period:start + 2 * period]
            if len(first) != period or len(second) != period:
                continue
            values = np.sum(first * second, axis=1)
            mean = float(np.mean(values))
            if best is None or mean > best["mean_frame_cosine"]:
                best = {
                    "period_sec": period,
                    "first_start_sec": start,
                    "second_start_sec": start + period,
                    "mean_frame_cosine": round(mean, 5),
                    "minimum_frame_cosine": round(float(np.min(values)), 5),
                }
    if best is None:
        return {"status": "NO_TESTABLE_REPEAT"}
    if best["mean_frame_cosine"] >= .84 and best["minimum_frame_cosine"] >= .65:
        best["status"] = "STRONG_REPEAT_LIKE_AUDIO_NOT_DJ_INTENT"
    elif best["mean_frame_cosine"] >= .72:
        best["status"] = "POSSIBLE_REPEAT_LIKE_AUDIO"
    else:
        best["status"] = "NO_STRONG_REPEAT_EVIDENCE"
    return best


def signal_patterns(candidate: dict) -> list[str]:
    axes = candidate["axis_evidence"]
    rms = axes["log_rms"]["delta"]
    low = axes["low_fraction"]["delta"]
    transient = axes["transient_activity"]["delta"]
    high = axes["high_fraction"]["delta"]
    patterns = []
    if rms > 1.4 and low > .04 and transient > 0:
        patterns.append("ENERGY_AND_LOW_END_ARRIVAL_SIGNAL")
    if rms < -1.4 and low < -.04 and transient < 0:
        patterns.append("ENERGY_AND_LOW_END_REDUCTION_SIGNAL")
    if low < -.04 and rms > -.6:
        patterns.append("LOW_END_REDUCTION_WITH_LEVEL_HELD_SIGNAL")
    if low > .04 and transient > 0:
        patterns.append("LOW_END_AND_TRANSIENT_ARRIVAL_SIGNAL")
    if abs(high) > .03:
        patterns.append("HIGH_BAND_REDISTRIBUTION_SIGNAL")
    if abs(axes["centroid_hz"]["delta"]) > 180:
        patterns.append("SPECTRAL_CENTER_MOVEMENT_SIGNAL")
    if not patterns:
        patterns.append("MULTI_AXIS_STRUCTURE_CHANGE_UNATTRIBUTED")
    return patterns


def alignment_intervals(alignment: dict) -> dict[int, list[dict]]:
    by_reference: dict[int, list[dict]] = defaultdict(list)
    for song in alignment["rows"]:
        for match in song["matches"]:
            if match["status"] not in {"HIGH_CONFIDENCE_AUDIO_ALIGNMENT", "HIGH_CONFIDENCE_EXCERPT_ONLY"}:
                continue
            for hit in match.get("verified_hits") or match.get("supporting_hits", []):
                by_reference[match["reference_index"]].append({
                    "source_index": song["source_index"],
                    "reference_start_sec": hit["reference_start_sec"],
                    "reference_end_sec": hit["reference_start_sec"] + 24 * hit["tempo_ratio"],
                    "original_start_sec": hit["source_start_sec"],
                    "mean_frame_cosine": hit["mean_frame_cosine"],
                    "alignment_scope": match["status"],
                })
    return by_reference


def evidence_near_region(intervals: list[dict], center_sec: float) -> dict:
    before = [row for row in intervals if row["reference_end_sec"] <= center_sec + 8
              and row["reference_end_sec"] >= center_sec - 50]
    after = [row for row in intervals if row["reference_start_sec"] >= center_sec - 8
             and row["reference_start_sec"] <= center_sec + 50]
    before.sort(key=lambda row: abs(row["reference_end_sec"] - center_sec))
    after.sort(key=lambda row: abs(row["reference_start_sec"] - center_sec))
    different_source_pairs = [
        (a, b) for a in before[:5] for b in after[:5]
        if a["source_index"] != b["source_index"]
        and b["reference_start_sec"] >= a["reference_start_sec"]
    ]
    return {
        "before_aligned_originals": before[:3],
        "after_aligned_originals": after[:3],
        "distinct_original_change_candidate": bool(different_source_pairs),
        "meaning": "Suggests source-material turnover near this region; does not prove DJ handoff or its exact boundary",
    }


def _write_json(output: Path, value: dict) -> None:
    output.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def mine(inventory: dict, coarse: dict, alignment: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "private_fingerprint_cache"
    inventory_rows = inventory["rows"]
    refs = [str(Path(path).resolve()) for path in alignment["reference_paths_private"]]
    if len(refs) != len(inventory_rows):
        raise ValueError("Reference inventory/alignment size mismatch")
    inventory_by_path = {str(Path(row["private_filepath"]).resolve()): row for row in inventory_rows}
    intervals = alignment_intervals(alignment)
    typed_rows = []
    for index, path in enumerate(refs):
        old = inventory_by_path[path]
        tags = old["probe"].get("metadata_tags_as_recorded") or {}
        title = str(tags.get("title", ""))
        title_hint = f"{title} {old['private_filename']}".casefold()
        if any(token in title_hint for token in ("mix", "podcast", "episode", "weekend live")):
            type_class = "LONG_FORM_MIX_OR_SET_CANDIDATE"
            confidence = "MEDIUM_METADATA_DURATION_ONLY"
        else:
            type_class = "LONG_FORM_REFERENCE_UNKNOWN_STRUCTURE"
            confidence = "LOW"
        typed_rows.append({
            "reference_index": index,
            "reference_path_private": path,
            "duration_sec": old["probe"]["duration_sec"],
            "type_class": type_class,
            "type_confidence": confidence,
            "metadata_as_recorded_private": tags,
            "high_confidence_original_or_excerpt_links": len({row["source_index"] for row in intervals.get(index, [])}),
            "full_song_alignment_links": len({row["source_index"] for row in intervals.get(index, []) if row["alignment_scope"] == "HIGH_CONFIDENCE_AUDIO_ALIGNMENT"}),
            "warning": "Filename, title and length alone do not confirm an actual transition, mashup, edit or DJ set.",
        })
    _write_json(output_dir / "REFERENCE_TYPE_INVENTORY.json", {
        "schema_version": "shadow-reference-type-1", "file_count": len(typed_rows),
        "normal_library_eligible": False, "rows": typed_rows,
    })

    all_regions = []
    repeat_cache_dir = output_dir / "private_repeat_evidence_cache"
    for ref_index, row in enumerate(coarse["rows"]):
        path = refs[ref_index]
        if row["reference_index"] != ref_index:
            raise ValueError("Reference order mismatch")
        chroma = _fingerprint(Path(path), cache_dir)
        exact_repeats = cached_waveform_repeats(
            Path(path), inventory_by_path[path]["sha256"],
            row["candidate_regions"], repeat_cache_dir,
        )
        for candidate_index, candidate in enumerate(row["candidate_regions"]):
            center = candidate["center_sec"]
            nearby = evidence_near_region(intervals.get(ref_index, []), center)
            repetition = repeat_evidence(chroma, center)
            exact_repetition = exact_repeats[candidate_index]
            patterns = signal_patterns(candidate)
            all_regions.append({
                "region_id": f"REF_{ref_index:02d}_REG_{candidate_index:02d}",
                "reference_index": ref_index,
                "reference_path_private": path,
                "center_sec": center,
                "review_range_sec": candidate["review_range_sec"],
                "candidate_rank_value": candidate["interesting_region_rank_value"],
                "independent_changed_axes": candidate["independent_changed_axes"],
                "axis_evidence": candidate["axis_evidence"],
                "tempo_before_hypothesis": candidate["tempo_before_hypothesis"],
                "tempo_after_hypothesis": candidate["tempo_after_hypothesis"],
                "repeat_evidence": repetition,
                "waveform_repeat_evidence": exact_repetition,
                "signal_patterns_not_confirmed_actions": patterns,
                "original_alignment_evidence": nearby,
                "action_confidence": "UNVERIFIED" if not nearby["distinct_original_change_candidate"] else "POSSIBLE_MULTI_ORIGINAL_CHANGE_REQUIRES_LISTENING",
                "dj_action_confirmed": False,
                "scope_warning": "Finished-audio features cannot distinguish DJ control from native arrangement without source alignment or listening.",
            })
    _write_json(output_dir / "DJ_ACTION_REGIONS.json", {
        "schema_version": "shadow-action-regions-1", "region_count": len(all_regions),
        "confirmed_dj_action_count": 0, "rows": all_regions,
    })

    # Timelines are limited to observations, not fabricated effect controls.
    ranked = sorted(all_regions, key=lambda r: (
        bool(r["original_alignment_evidence"]["distinct_original_change_candidate"]),
        r["candidate_rank_value"], len(r["independent_changed_axes"])), reverse=True)
    timelines = []
    for region in ranked[:30]:
        axes = region["axis_evidence"]
        before_tempo = region["tempo_before_hypothesis"]
        tempo = before_tempo if before_tempo and before_tempo["autocorr_confidence"] >= .4 else None
        bar_seconds = 240 / tempo["bpm_hypothesis"] if tempo else None
        raw = coarse["rows"][region["reference_index"]]["raw_coarse_features_private"]
        snapshots = []
        for relative in (-16, -12, -8, -4, 0, 4, 8, 12, 16):
            at_sec = region["center_sec"] + relative
            nearby = min(raw, key=lambda item: abs(item["at_sec"] - at_sec))
            snapshots.append({
                "relative_sec": relative,
                "relative_bars_approx_if_usable": round(relative / bar_seconds, 2) if bar_seconds else None,
                "observation": "finished-audio descriptor; not a named DJ control",
                "log_rms": nearby["log_rms"],
                "low_fraction": nearby["low_fraction"],
                "high_fraction": nearby["high_fraction"],
                "transient_activity": nearby["transient_activity"],
                "centroid_hz": nearby["centroid_hz"],
            })
        timelines.append({
            "region_id": region["region_id"],
            "reference_index": region["reference_index"],
            "center_sec": region["center_sec"],
            "timing_basis": "approximate four-beat bars from local autocorrelation" if tempo else "seconds_only; beat/bar phase unverified",
            "seconds_per_bar_if_usable": round(bar_seconds, 4) if bar_seconds else None,
            "events": snapshots,
            "coarse_change_summary": {"log_rms_delta": axes["log_rms"]["delta"],
                                      "low_fraction_delta": axes["low_fraction"]["delta"],
                                      "transient_activity_delta": axes["transient_activity"]["delta"]},
            "repeat_evidence": region["repeat_evidence"],
            "waveform_repeat_evidence": region["waveform_repeat_evidence"],
            "original_alignment_evidence": region["original_alignment_evidence"],
            "cannot_infer": ["vocal phrase completion", "effect wet/dry", "bass ownership", "source/target stems", "DJ intent"],
        })
    _write_json(output_dir / "DJ_CHOREOGRAPHY_TIMELINES.json", {
        "schema_version": "shadow-timelines-1", "confirmed_choreographies": [],
        "observational_timelines_not_choreography": timelines,
    })

    pattern_rows = defaultdict(list)
    for region in all_regions:
        for pattern in region["signal_patterns_not_confirmed_actions"]:
            pattern_rows[pattern].append(region)
    pattern_summary = [
        {"signal_pattern": name, "region_count": len(rows),
         "reference_file_count": len({r["reference_index"] for r in rows}),
         "region_ids_first_ten": [r["region_id"] for r in rows[:10]],
         "inference_limit": "Recurrence of a finished-audio signal pattern, not of a confirmed DJ action."}
        for name, rows in sorted(pattern_rows.items())
    ]
    exact_repeat_regions = [
        region for region in all_regions
        if region["waveform_repeat_evidence"]["status"] ==
        "EXACT_LIKE_AUDIO_REPEAT_NOT_PROOF_OF_DJ_LOOP"
    ]
    preceding_repeat_regions = [
        region for region in exact_repeat_regions
        if (region["waveform_repeat_evidence"]["second_start_sec"]
            + region["waveform_repeat_evidence"]["period_sec"]
            <= region["center_sec"])
    ]
    preceding_repeat_reductions = [
        region for region in preceding_repeat_regions
        if "ENERGY_AND_LOW_END_REDUCTION_SIGNAL" in region["signal_patterns_not_confirmed_actions"]
    ]
    _write_json(output_dir / "RECURRENT_DJ_PATTERNS.json", {
        "schema_version": "shadow-recurrence-1", "confirmed_dj_choreography_patterns": [],
        "recurrent_signal_patterns_not_proven_actions": pattern_summary,
        "exact_like_waveform_repeat_observation": {
            "region_count": len(exact_repeat_regions),
            "reference_file_count": len({r["reference_index"] for r in exact_repeat_regions}),
            "repeat_precedes_nominated_change_count": len(preceding_repeat_regions),
            "repeat_precedes_nominated_change_file_count": len({r["reference_index"] for r in preceding_repeat_regions}),
            "repeat_precedes_energy_and_low_end_reduction_count": len(preceding_repeat_reductions),
            "repeat_precedes_energy_and_low_end_reduction_file_count": len({r["reference_index"] for r in preceding_repeat_reductions}),
            "meaning": "Strong short waveform repetition is observed, but may be native arrangement or a DJ loop; causal/control attribution and exact bar phase require listening/originals.",
        },
    })

    context_rows = []
    for region in all_regions:
        if region["candidate_rank_value"] < 12:
            continue
        axes = region["axis_evidence"]
        context_rows.append({
            "region_id": region["region_id"],
            "pre_action_observable_state": {
                "log_rms": axes["log_rms"]["before"],
                "low_fraction": axes["low_fraction"]["before"],
                "transient_activity": axes["transient_activity"]["before"],
                "spectral_centroid_hz": axes["centroid_hz"]["before"],
            },
            "following_signal_patterns": region["signal_patterns_not_confirmed_actions"],
            "phrase_vocal_style_context": "UNKNOWN_IN_THIS_PASS",
        })
    _write_json(output_dir / "CONTEXT_TO_ACTION_EVIDENCE.json", {
        "schema_version": "shadow-context-action-1", "action_conditional_rule_claims": [],
        "observational_rows": context_rows,
        "limit": "No inference that a DJ chose an action because of these pre-change measurements.",
    })

    _write_json(output_dir / "CURRENT_ARCHETYPE_COMPARISON.json", {
        "schema_version": "shadow-archetype-comparison-1",
        "confirmed_class_A_well_represented": [],
        "confirmed_class_B_simpler_execution": [],
        "confirmed_class_C_missing": [],
        "confirmed_class_D_out_of_scope": [],
        "hypothesis_mapping_only": {
            "repeat_like_audio": ["F", "C3", "B8"],
            "energy_and_low_end_arrival": ["B8", "D2"],
            "energy_and_low_end_reduction": ["F", "C3", "B8", "D2"],
        },
        "conclusion": "Finished-audio changes alone do not establish choreography or a missing fifth archetype.",
    })

    per_ref = defaultdict(list)
    for region in all_regions:
        per_ref[region["reference_index"]].append(region)
    set_rows = []
    for ref_index, row in enumerate(typed_rows):
        centers = sorted(region["center_sec"] for region in per_ref[ref_index])
        gaps = np.diff(centers) if len(centers) > 1 else np.asarray([])
        set_rows.append({
            "reference_index": ref_index,
            "reference_type_provisional": row["type_class"],
            "structured_change_candidate_count": len(centers),
            "candidate_spacing_sec_median": round(float(np.median(gaps)), 3) if len(gaps) else None,
            "aligned_distinct_original_or_excerpt_count": row["high_confidence_original_or_excerpt_links"],
            "track_establishment_duration": "UNKNOWN_UNTIL_HANDOFF_BOUNDARIES_CONFIRMED",
            "energy_arc": "DEFERRED_NO_CONFIRMED_TRACK_BOUNDARIES",
            "contrast_preparation": "DEFERRED_NO_CONFIRMED_TRACK_IDENTITIES_OR_LISTENING",
        })
    _write_json(output_dir / "SET_LEVEL_REFERENCE_BEHAVIOR.json", {
        "schema_version": "shadow-set-level-1", "rows": set_rows,
        "sampling_censoring": "Prior discovery retained at most 20 spaced structured-change nominations per file; counts and gaps are not unbiased transition frequency or DJ pacing.",
    })

    selected = []
    used_refs = set()

    def add_region(region: dict, purpose: str) -> bool:
        if (region["reference_index"] in used_refs or region["center_sec"] < 30
                or region["review_range_sec"][1] - region["center_sec"] < 18):
            return False
        selected.append({
            "shortlist_id": f"LISTEN_{len(selected) + 1:02d}",
            "region_id": region["region_id"],
            "reference_index": region["reference_index"],
            "reference_path_private": region["reference_path_private"],
            "start_sec": region["review_range_sec"][0],
            "end_sec": region["review_range_sec"][1],
            "center_sec": region["center_sec"],
            "selection_purpose": purpose,
            "why_interesting": {
                "signal_patterns_unverified": region["signal_patterns_not_confirmed_actions"],
                "repeat_evidence": region["repeat_evidence"],
                "waveform_repeat_evidence": region["waveform_repeat_evidence"],
                "original_change_candidate": region["original_alignment_evidence"]["distinct_original_change_candidate"],
                "changed_axes": region["independent_changed_axes"],
            },
            "requested_human_feedback": ["LIKE", "NEUTRAL", "DISLIKE", "Is this an actual DJ action or native song arrangement?"],
        })
        used_refs.add(region["reference_index"])
        return True

    exact = sorted(
        (r for r in all_regions if r["waveform_repeat_evidence"]["status"] ==
         "EXACT_LIKE_AUDIO_REPEAT_NOT_PROOF_OF_DJ_LOOP"),
        key=lambda r: (-r["waveform_repeat_evidence"]["normalized_waveform_correlation"],
                       -r["candidate_rank_value"], r["reference_index"]),
    )
    strata = [
        ("repeat_before_or_near_low_end_reduction",
         lambda r: "ENERGY_AND_LOW_END_REDUCTION_SIGNAL" in r["signal_patterns_not_confirmed_actions"]),
        ("repeat_before_or_near_low_end_arrival",
         lambda r: "ENERGY_AND_LOW_END_ARRIVAL_SIGNAL" in r["signal_patterns_not_confirmed_actions"]),
        ("other_exact_like_repeat_with_structure_change", lambda r: True),
    ]
    for purpose, predicate in strata:
        for region in exact:
            if predicate(region) and add_region(region, purpose):
                break
    for purpose, predicate in [
        ("strong_arrival_without_exact_repeat", lambda r: "ENERGY_AND_LOW_END_ARRIVAL_SIGNAL" in r["signal_patterns_not_confirmed_actions"]),
        ("strong_reduction_without_exact_repeat", lambda r: "ENERGY_AND_LOW_END_REDUCTION_SIGNAL" in r["signal_patterns_not_confirmed_actions"]),
        ("spectral_change_without_exact_repeat", lambda r: "SPECTRAL_CENTER_MOVEMENT_SIGNAL" in r["signal_patterns_not_confirmed_actions"]),
    ]:
        for region in ranked:
            if (region["waveform_repeat_evidence"]["status"] == "NO_EXACT_LIKE_AUDIO_REPEAT"
                    and predicate(region) and add_region(region, purpose)):
                break
    # A high-confidence matched excerpt is an alignment control, not an action.
    for song in alignment["rows"]:
        for match in song["matches"]:
            if match["status"] not in {"HIGH_CONFIDENCE_EXCERPT_ONLY", "FEATURE_MATCH_UNCONFIRMED_ORIGINAL_IDENTITY"}:
                continue
            ref_index = match["reference_index"]
            if ref_index in used_refs:
                continue
            hit = match["best_hit"]
            center = hit["reference_start_sec"] + 12
            selected.append({
                "shortlist_id": f"LISTEN_{len(selected) + 1:02d}",
                "region_id": f"REF_{ref_index:02d}_ALIGNED_EXCERPT",
                "reference_index": ref_index,
                "reference_path_private": refs[ref_index],
                "start_sec": max(0, center - 20),
                "end_sec": min(typed_rows[ref_index]["duration_sec"], center + 20),
                "center_sec": center,
                "selection_purpose": "ambiguous_feature_match_identity_control_not_assumed_dj_action",
                "why_interesting": {"original_source_index_private": song["source_index"],
                                    "alignment": match},
                "requested_human_feedback": ["Does this region contain a DJ action?", "LIKE", "NEUTRAL", "DISLIKE"],
            })
            used_refs.add(ref_index)
            break
        if len(selected) >= 7:
            break
    for region in ranked:
        if len(selected) >= 8:
            break
        add_region(region, "high_rank_diverse_fallback")
    _write_json(output_dir / "DJ_REFERENCE_LISTENING_SHORTLIST.json", {
        "schema_version": "shadow-listening-shortlist-1", "regions": selected,
        "privacy": "Private source paths and timestamps; no audio extracted or copied.",
    })
    conclusion = {
        "schema_version": "shadow-demo-mining-conclusion-1",
        "reference_file_count": len(typed_rows),
        "candidate_region_count": len(all_regions),
        "high_confidence_full_song_alignment_links": sum(row["full_song_alignment_links"] for row in typed_rows),
        "high_confidence_original_excerpt_links": sum(row["high_confidence_original_or_excerpt_links"] for row in typed_rows),
        "feature_level_original_match_candidates_unconfirmed": sum(
            1 for song in alignment["rows"] for match in song["matches"]
            if match["status"] == "FEATURE_MATCH_UNCONFIRMED_ORIGINAL_IDENTITY"),
        "confirmed_dj_action_regions": 0,
        "confirmed_recurrent_choreographies": 0,
        "strongest_missing_behavior": "NONE_DEMONSTRATED_YET",
        "why": "The current pass finds finished-audio change/repetition candidates, but no full original alignment and no waveform-confirmed ordinary-song excerpt. Feature-level resemblances cannot safely establish song identity or DJ control.",
        "next_experiment": "Human listens to the eight private shortlist regions and labels action type/preference; then compare confirmed examples against original-aligned material before proposing any fifth archetype.",
    }
    _write_json(output_dir / "DJ_DEMONSTRATION_MINING_CONCLUSION.json", conclusion)
    return conclusion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--regions", type=Path, required=True)
    parser.add_argument("--alignment", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if args.output_dir.resolve().is_relative_to(repo):
        raise ValueError("Private DJ research outputs must be outside repository")
    inventory = json.loads(args.inventory.read_text())
    coarse = json.loads(args.regions.read_text())
    alignment = json.loads(args.alignment.read_text())
    result = mine(inventory, coarse, alignment, args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
