"""Nominate structured change regions in private DJ references.

This is a conservative *shadow* diagnostic, not a DJ-transition classifier.
Only derived acoustic metadata is emitted. It is intentionally disconnected
from candidate-song discovery, the selector, and the set planner.

Run with::

    python -m djenius.research.reference_regions \
        --reference-root testMusic/fromDJ \
        --output /tmp/dj_reference_regions.json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess

import numpy as np


SAMPLE_RATE = 11_025
STEP_SEC = 2
FRAME_SAMPLES = SAMPLE_RATE * STEP_SEC
FIELDS = (
    "log_rms", "low_fraction", "high_fraction", "centroid_hz",
    "transient_activity", "spectral_flatness",
)
BANDS_HZ = ((0, 80), (80, 180), (180, 500), (500, 1500),
            (1500, 3500), (3500, SAMPLE_RATE / 2))
EXTENSIONS = frozenset({".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".aiff"})


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    duration = float(result.stdout.strip())
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Invalid reference duration: {path}")
    return duration


def decode_coarse_features(path: Path) -> tuple[list[dict], np.ndarray]:
    """Stream finished audio; retain descriptors, never sample waveforms."""
    process = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    rows: list[dict] = []
    envelope: list[float] = []
    assert process.stdout is not None
    try:
        while True:
            raw = process.stdout.read(FRAME_SAMPLES * 4)
            if not raw:
                break
            samples = np.frombuffer(raw, dtype="<f4")
            if samples.size < FRAME_SAMPLES // 2:
                break
            if samples.size < FRAME_SAMPLES:
                samples = np.pad(samples, (0, FRAME_SAMPLES - samples.size))
            values = samples.astype(np.float64)
            rms = float(np.sqrt(np.mean(values ** 2)) + 1e-9)
            spectrum = np.abs(np.fft.rfft(values * np.hanning(len(values)))) ** 2
            frequencies = np.fft.rfftfreq(len(values), 1 / SAMPLE_RATE)
            total = float(spectrum.sum() + 1e-12)
            fractions = [
                float(spectrum[(frequencies >= low) & (frequencies < high)].sum() / total)
                for low, high in BANDS_HZ
            ]
            subframes = values[:(len(values) // 551) * 551].reshape(-1, 551)
            sub_rms = np.sqrt(np.mean(subframes ** 2, axis=1) + 1e-12)
            flux = np.maximum(0, np.diff(np.log(sub_rms + 1e-7)))
            envelope.extend(flux.tolist())
            flatness = float(
                np.exp(np.mean(np.log(spectrum + 1e-12))) /
                (np.mean(spectrum) + 1e-12)
            )
            rows.append({
                "at_sec": round((len(rows) + .5) * STEP_SEC, 3),
                "log_rms": round(20 * math.log10(rms), 5),
                "low_fraction": round(fractions[0] + fractions[1], 6),
                "high_fraction": round(fractions[-2] + fractions[-1], 6),
                "centroid_hz": round(float(np.dot(frequencies, spectrum) / total), 3),
                "transient_activity": round(float(np.mean(flux)), 6),
                "spectral_flatness": round(flatness, 6),
            })
    finally:
        process.stdout.close()
    if process.wait(timeout=30):
        raise RuntimeError(f"ffmpeg could not decode reference: {path}")
    return rows, np.asarray(envelope, dtype=float)


def tempo_hypothesis(flux: np.ndarray) -> dict | None:
    if len(flux) < 200:
        return None
    centered = flux - np.mean(flux)
    correlation = np.correlate(centered, centered, mode="full")[len(centered) - 1:]
    low_lag = max(1, int(round((60 / 200) * SAMPLE_RATE / 551)))
    high_lag = min(len(correlation) - 1, int(round(SAMPLE_RATE / 551)))
    lag = low_lag + int(np.argmax(correlation[low_lag:high_lag + 1]))
    return {
        "bpm_hypothesis": round(60 * SAMPLE_RATE / (551 * lag), 2),
        "autocorr_confidence": round(float(correlation[lag] / max(correlation[0], 1e-9)), 3),
        "half_double_ambiguity": "unresolved",
    }


def nominate_regions(
    rows: list[dict], envelope: np.ndarray, duration_sec: float,
    *, max_regions: int = 20,
) -> list[dict]:
    """Find multi-axis changes, not automatically identifiable DJ actions."""
    if len(rows) < 25:
        return []
    matrix = np.asarray([[row[field] for field in FIELDS] for row in rows], dtype=float)
    differences = np.asarray([
        np.mean(matrix[index:index + 5], axis=0) - np.mean(matrix[index - 5:index], axis=0)
        for index in range(5, len(rows) - 5)
    ])
    scale = np.maximum(np.median(np.abs(differences), axis=0),
                       [.25, .01, .01, 25, .003, .002])
    candidates = []
    for index in range(8, len(rows) - 8):
        before = np.mean(matrix[index - 5:index], axis=0)
        after = np.mean(matrix[index:index + 5], axis=0)
        delta = after - before
        strengths = np.abs(delta) / scale
        axes = [FIELDS[position] for position, value in enumerate(strengths) if value >= 2.8]
        if len(axes) < 2:
            continue
        flags = []
        if delta[0] > 1.4 and delta[4] > 0:
            flags.append("possible_build_or_drop_energy_arrival")
        if delta[0] < -1.4 and delta[4] < 0:
            flags.append("possible_arrangement_reduction")
        if abs(delta[1]) > .04:
            flags.append("low_frequency_spectral_balance_change")
        if abs(delta[2]) > .03 or abs(delta[3]) > 180:
            flags.append("possible_spectral_or_timbre_change")
        if abs(delta[4]) > .01:
            flags.append("transient_activity_change")
        center_sec = index * STEP_SEC
        candidates.append({
            "center_sec": round(center_sec, 3),
            "review_range_sec": [round(max(0, center_sec - 20), 3),
                                 round(min(duration_sec, center_sec + 20), 3)],
            "rank_value": round(float(sum(min(value, 8) for value in strengths)), 3),
            "independent_changed_axes": axes,
            "axis_evidence": {
                field: {
                    "before": round(float(before[position]), 5),
                    "after": round(float(after[position]), 5),
                    "delta": round(float(delta[position]), 5),
                    "robust_relative_change": round(float(strengths[position]), 3),
                }
                for position, field in enumerate(FIELDS)
            },
            "nomination_flags_not_confirmed_actions": flags,
            "classification": "CANDIDATE_REGION_NOT_CONFIRMED_DJ_TRANSITION",
        })
    selected = []
    for candidate in sorted(candidates, key=lambda row: -row["rank_value"]):
        if all(abs(candidate["center_sec"] - prior["center_sec"]) >= 30 for prior in selected):
            selected.append(candidate)
        if len(selected) >= max_regions:
            break
    hop = 551 / SAMPLE_RATE
    for candidate in selected:
        center = candidate["center_sec"]
        start = max(0, int((center - 25) / hop))
        middle = int(center / hop)
        stop = min(len(envelope), int((center + 25) / hop))
        before = tempo_hypothesis(envelope[start:middle])
        after = tempo_hypothesis(envelope[middle:stop])
        candidate["tempo_before_hypothesis"] = before
        candidate["tempo_after_hypothesis"] = after
        if before and after and min(before["autocorr_confidence"], after["autocorr_confidence"]) >= .18:
            if abs(after["bpm_hypothesis"] - before["bpm_hypothesis"]) >= 8:
                candidate["nomination_flags_not_confirmed_actions"].append(
                    "possible_tempo_hypothesis_change_unverified"
                )
    return sorted(selected, key=lambda row: row["center_sec"])


def discover_directory(reference_root: Path, output: Path) -> dict:
    """Write private derived metadata outside the repository, never audio."""
    root = reference_root.resolve()
    if root.name.casefold() != "fromdj" or not root.is_dir():
        raise ValueError("Explicit --reference-root must be an existing fromDJ directory")
    repository = Path(__file__).resolve().parents[2]
    destination = output.resolve()
    if destination.is_relative_to(repository):
        raise ValueError("Private reference metadata must be written outside the repository")
    files = sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in EXTENSIONS),
        key=lambda path: str(path.relative_to(root)).casefold(),
    )
    result = {
        "schema_version": "shadow-dj-reference-regions-1",
        "shadow_only": True,
        "all_regions_unverified": True,
        "reference_count": len(files),
        "complete": False,
        "rows": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    for path in files:
        duration = probe_duration(path)
        features, envelope = decode_coarse_features(path)
        result["rows"].append({
            "private_filepath": str(path),
            "duration_sec": round(duration, 6),
            "coarse_feature_count": len(features),
            "candidate_regions": nominate_regions(features, envelope, duration),
            "method_limits": [
                "nominations are not confirmed DJ edits or track-to-track handoffs",
                "finished audio cannot identify source/target or bass ownership",
                "tempo half/double ambiguity is unresolved",
            ],
        })
        output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                          encoding="utf-8")
    result["complete"] = True
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                      encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = discover_directory(args.reference_root, args.output)
    print(f"Nominated regions in {result['reference_count']} reference files; all unverified")


if __name__ == "__main__":
    main()
