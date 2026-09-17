"""Shadow-only original-to-DJ-reference alignment.

No audio or fingerprint is committed or sent to a service.  The command needs
an explicit ``fromDJ`` directory and writes only to a path outside the repo.
Matches are *candidates* unless two nonoverlapping, temporally coherent
queries agree at a high frame-correlation margin.  A genre/chroma resemblance
alone is never reported as an aligned original.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.signal import correlate, stft


RATE = 8000
HOP = RATE
WINDOW = 8192
QUERY_SEC = 24
SKETCH_BLOCK_SEC = 4
REF_STRIDE_SEC = 4
SONG_STRIDE_SEC = 12
AUDIO_SUFFIXES = frozenset({".mp3", ".m4a", ".flac", ".wav", ".aac", ".ogg", ".aiff"})


def chroma24_from_samples(samples: np.ndarray) -> np.ndarray:
    """One-second, 24-pitch-class normalized energy snapshots."""
    if samples.ndim != 1 or not np.isfinite(samples).all():
        raise ValueError("Expected finite mono audio")
    _, _, spectrum = stft(
        samples.astype(np.float32), fs=RATE, window="hann", nperseg=WINDOW,
        noverlap=WINDOW - HOP, boundary=None, padded=False,
    )
    frequencies = np.fft.rfftfreq(WINDOW, 1 / RATE)
    bins = np.flatnonzero((frequencies >= 80) & (frequencies <= 2400))
    pitch = np.rint(24 * np.log2(frequencies[bins] / 440.0)).astype(int) % 24
    projection = np.zeros((24, len(frequencies)), dtype=np.float32)
    projection[pitch, bins] = 1.0
    energy = projection @ (np.abs(spectrum) ** 1.25)
    energy = np.log1p(energy * 100)
    energy -= np.mean(energy, axis=0, keepdims=True)
    norms = np.linalg.norm(energy, axis=0, keepdims=True)
    energy /= np.maximum(norms, 1e-8)
    return energy.T.astype(np.float32)


def decode_chroma(path: Path) -> np.ndarray:
    process = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn",
         "-ac", "1", "-ar", str(RATE), "-f", "f32le", "pipe:1"],
        capture_output=True, check=True, timeout=900,
    )
    samples = np.frombuffer(process.stdout, dtype="<f4")
    return chroma24_from_samples(samples)


def _spectral_excerpt(path: Path, start_sec: int) -> np.ndarray:
    """Short timbre-sensitive corroboration for one otherwise ambiguous hit."""
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start_sec),
         "-i", str(path), "-t", str(QUERY_SEC + 2), "-vn", "-ac", "1",
         "-ar", str(RATE), "-f", "f32le", "pipe:1"],
        capture_output=True, check=True, timeout=60,
    )
    samples = np.frombuffer(result.stdout, dtype="<f4")
    if len(samples) < QUERY_SEC * RATE:
        return np.empty((0, 32), dtype=np.float32)
    _, _, spectrum = stft(samples, fs=RATE, window="hann", nperseg=WINDOW,
                          noverlap=WINDOW - HOP, boundary=None, padded=False)
    frequencies = np.fft.rfftfreq(WINDOW, 1 / RATE)
    boundaries = np.geomspace(80, 3500, 33)
    bands = np.asarray([
        np.mean(np.abs(spectrum[(frequencies >= low) & (frequencies < high)]) ** 1.25, axis=0)
        for low, high in zip(boundaries[:-1], boundaries[1:])
    ], dtype=np.float32).T
    bands = np.log1p(bands * 100)
    bands -= np.mean(bands, axis=1, keepdims=True)
    bands /= np.maximum(np.linalg.norm(bands, axis=1, keepdims=True), 1e-8)
    return bands


def _short_wave(path: Path, start_sec: int) -> np.ndarray:
    result = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(max(0, start_sec - 1)),
         "-i", str(path), "-t", str(QUERY_SEC + 2), "-vn", "-ac", "1",
         "-ar", str(RATE), "-f", "f32le", "pipe:1"],
        capture_output=True, check=True, timeout=60,
    )
    return np.frombuffer(result.stdout, dtype="<f4")


def compare_original_excerpt(source_path: Path, reference_path: Path, hit: dict) -> dict:
    """Measure source/reference waveform resemblance, never reconstruct audio."""
    if abs(hit["tempo_ratio"] - 1.0) > .015:
        return {"status": "DEFERRED_TEMPO_WARP"}
    source = _short_wave(source_path, hit["source_start_sec"])
    reference = _short_wave(reference_path, hit["reference_start_sec"])
    length = min(len(source), len(reference), (QUERY_SEC + 2) * RATE)
    if length < QUERY_SEC * RATE:
        return {"status": "TOO_SHORT"}
    source = source[:length].astype(np.float64)
    reference = reference[:length].astype(np.float64)
    correlation = correlate(reference, source, mode="full", method="fft")
    center = len(source) - 1
    search = correlation[center - RATE:center + RATE + 1]
    offset_samples = int(np.argmax(np.abs(search))) - RATE
    if offset_samples >= 0:
        left = source[:length - offset_samples]
        right = reference[offset_samples:]
    else:
        left = source[-offset_samples:]
        right = reference[:length + offset_samples]
    normalized = float(np.dot(left, right) / np.sqrt(max(np.dot(left, left) * np.dot(right, right), 1e-12)))
    gain = float(np.dot(left, right) / max(np.dot(left, left), 1e-12))
    residual = right - gain * left
    residual_relative = float(np.sqrt(np.mean(residual ** 2)) / max(np.sqrt(np.mean(right ** 2)), 1e-9))
    return {
        "status": "WAVEFORM_COMPARISON_COMPLETE",
        "best_offset_sec": round(offset_samples / RATE, 5),
        "normalized_waveform_correlation": round(normalized, 5),
        "best_fit_constant_gain": round(gain, 5),
        "post_gain_residual_rms_fraction": round(residual_relative, 5),
        "interpretation_limit": "Residual may reflect encoding, mastering, layering, EQ or DJ action; no control attribution from this measure alone.",
    }


def corroborate_excerpt(source_path: Path, reference_path: Path, hit: dict) -> dict:
    """Require timbre as well as ordered harmony before accepting one excerpt."""
    source = _spectral_excerpt(source_path, hit["source_start_sec"])
    reference = _spectral_excerpt(reference_path, hit["reference_start_sec"])
    if len(source) < QUERY_SEC or len(reference) < QUERY_SEC:
        return {"status": "NOT_TESTABLE"}
    best = -1.0
    for shift in (-1, 0, 1):
        positions = np.rint(np.arange(QUERY_SEC) * hit["tempo_ratio"]).astype(int) + max(shift, 0)
        src_start = max(-shift, 0)
        if positions[-1] >= len(reference) or src_start + QUERY_SEC > len(source):
            continue
        value = float(np.mean(np.sum(source[src_start:src_start + QUERY_SEC] * reference[positions], axis=1)))
        best = max(best, value)
    return {
        "status": "TIMBRE_CORROBORATED_EXCERPT" if best >= .78 else "NOT_CORROBORATED",
        "mean_log_spectral_cosine": round(best, 5),
        "limit": "A single corroborated excerpt does not establish a complete source-to-reference timeline.",
    }


def sketches(chroma: np.ndarray, stride_sec: int) -> tuple[np.ndarray, np.ndarray]:
    """Six ordered block means retain sequential rather than genre-only evidence."""
    starts = np.arange(0, len(chroma) - QUERY_SEC + 1, stride_sec, dtype=np.int32)
    if not len(starts):
        return starts, np.empty((0, 24 * (QUERY_SEC // SKETCH_BLOCK_SEC)), dtype=np.float32)
    cumulative = np.vstack((np.zeros((1, 24), dtype=np.float32), np.cumsum(chroma, axis=0)))
    blocks = []
    for offset in range(0, QUERY_SEC, SKETCH_BLOCK_SEC):
        block = (cumulative[starts + offset + SKETCH_BLOCK_SEC] - cumulative[starts + offset]) / SKETCH_BLOCK_SEC
        block /= np.maximum(np.linalg.norm(block, axis=1, keepdims=True), 1e-8)
        blocks.append(block)
    vectors = np.concatenate(blocks, axis=1)
    vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-8)
    return starts, vectors.astype(np.float32)


def verify_segment(song: np.ndarray, ref: np.ndarray, song_start: int, ref_start: int) -> dict:
    """Check 24 seconds of ordered 1-second chroma at plausible tempo ratios."""
    query = song[song_start: song_start + QUERY_SEC]
    best = None
    for ratio in (0.90, 0.94, 0.97, 1.0, 1.03, 1.06, 1.10):
        for shift in (-2, -1, 0, 1, 2):
            positions = ref_start + shift + np.rint(np.arange(QUERY_SEC) * ratio).astype(int)
            if positions[0] < 0 or positions[-1] >= len(ref):
                continue
            similarity = np.sum(query * ref[positions], axis=1)
            block_means = [float(np.mean(block)) for block in np.array_split(similarity, 4)]
            evidence = {
                "mean_frame_cosine": round(float(np.mean(similarity)), 5),
                "minimum_six_second_block_cosine": round(min(block_means), 5),
                "tempo_ratio": ratio,
                "reference_start_sec": int(ref_start + shift),
                "source_start_sec": int(song_start),
            }
            if best is None or (evidence["mean_frame_cosine"], evidence["minimum_six_second_block_cosine"]) > (best["mean_frame_cosine"], best["minimum_six_second_block_cosine"]):
                best = evidence
    return best or {"mean_frame_cosine": -1.0, "minimum_six_second_block_cosine": -1.0}


def classify_alignment(hits: list[dict]) -> dict:
    """Require independent, coherent hits; never certify from a single resemblance."""
    strong = [hit for hit in hits if hit["mean_frame_cosine"] >= 0.78 and hit["minimum_six_second_block_cosine"] >= 0.68]
    strong.sort(key=lambda hit: hit["source_start_sec"])
    for first in strong:
        for second in strong:
            source_gap = second["source_start_sec"] - first["source_start_sec"]
            ref_gap = second["reference_start_sec"] - first["reference_start_sec"]
            if source_gap < QUERY_SEC or ref_gap <= 0:
                continue
            if abs(ref_gap / source_gap - first["tempo_ratio"]) > 0.15:
                continue
            if abs(second["tempo_ratio"] - first["tempo_ratio"]) > 0.08:
                continue
            return {"status": "HIGH_CONFIDENCE_AUDIO_ALIGNMENT", "supporting_hits": [first, second]}
    if strong:
        return {"status": "SINGLE_STRONG_REGION_UNCONFIRMED", "supporting_hits": strong[:3]}
    return {"status": "NO_CONFIDENT_ALIGNMENT", "supporting_hits": []}


def nearest_ordered_sketches(queries: np.ndarray, references: np.ndarray,
                            k: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """Chunked cosine retrieval using only the existing NumPy dependency."""
    if queries.ndim != 2 or references.ndim != 2 or queries.shape[1] != references.shape[1]:
        raise ValueError("Sketch dimensions must match")
    count = min(k, len(references))
    if len(queries) == 0:
        return (np.empty((0, count), dtype=np.float32),
                np.empty((0, count), dtype=np.int32))
    if count == 0:
        return (np.empty((len(queries), 0), dtype=np.float32),
                np.empty((len(queries), 0), dtype=np.int32))
    all_distances = []
    all_indices = []
    for start in range(0, len(queries), 32):
        cosine = queries[start:start + 32] @ references.T
        nearest = np.argpartition(-cosine, count - 1, axis=1)[:, :count]
        scores = np.take_along_axis(cosine, nearest, axis=1)
        order = np.argsort(-scores, axis=1, kind="stable")
        nearest = np.take_along_axis(nearest, order, axis=1)
        scores = np.take_along_axis(scores, order, axis=1)
        all_distances.append(1 - scores)
        all_indices.append(nearest.astype(np.int32))
    return np.vstack(all_distances), np.vstack(all_indices)


def _fingerprint(path: Path, cache_dir: Path) -> np.ndarray:
    source_stat = path.stat()
    key = hashlib.sha256(f"{path.resolve()}|{source_stat.st_size}|{source_stat.st_mtime_ns}|chroma24-v1".encode()).hexdigest()
    cache_path = cache_dir / f"{key}.npz"
    if cache_path.exists():
        with np.load(cache_path) as cached:
            return cached["chroma"]
    chroma = decode_chroma(path)
    np.savez_compressed(cache_path, chroma=chroma)
    return chroma


def align_library(normal_paths: list[Path], reference_paths: list[Path], cache_dir: Path) -> dict:
    """Nearest-neighbor retrieval followed by ordered, tempo-tolerant verification."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    ref_chroma = [_fingerprint(path, cache_dir) for path in reference_paths]
    ref_vectors = []
    ref_positions = []
    for ref_index, chroma in enumerate(ref_chroma):
        starts, vectors = sketches(chroma, REF_STRIDE_SEC)
        ref_vectors.append(vectors)
        ref_positions.extend((ref_index, int(start)) for start in starts)
    vectors = np.vstack(ref_vectors)
    output = []
    for source_index, path in enumerate(normal_paths):
        song = _fingerprint(path, cache_dir)
        starts, queries = sketches(song, SONG_STRIDE_SEC)
        if not len(starts):
            output.append({"source_index": source_index, "status": "TOO_SHORT", "matches": []})
            continue
        distances, nearest = nearest_ordered_sketches(queries, vectors)
        by_ref: dict[int, list[dict]] = {}
        for query_index, song_start in enumerate(starts):
            for rank in range(nearest.shape[1]):
                ref_index, ref_start = ref_positions[int(nearest[query_index, rank])]
                if distances[query_index, rank] > 0.38:
                    continue
                hit = verify_segment(song, ref_chroma[ref_index], int(song_start), ref_start)
                hit["sketch_cosine"] = round(float(1 - distances[query_index, rank]), 5)
                if hit["mean_frame_cosine"] >= 0.68:
                    by_ref.setdefault(ref_index, []).append(hit)
        matches = []
        for ref_index, hits in by_ref.items():
            deduped = {}
            for hit in hits:
                key = (hit["source_start_sec"], hit["reference_start_sec"] // 8)
                if key not in deduped or hit["mean_frame_cosine"] > deduped[key]["mean_frame_cosine"]:
                    deduped[key] = hit
            classified = classify_alignment(list(deduped.values()))
            if classified["status"] != "NO_CONFIDENT_ALIGNMENT":
                verified_hits = sorted(
                    (hit for hit in deduped.values()
                     if hit["mean_frame_cosine"] >= .78
                     and hit["minimum_six_second_block_cosine"] >= .68),
                    key=lambda hit: (hit["reference_start_sec"], hit["source_start_sec"]),
                )
                best_hit = max(deduped.values(), key=lambda h: h["mean_frame_cosine"])
                timbre = (corroborate_excerpt(path, reference_paths[ref_index], best_hit)
                          if classified["status"] == "SINGLE_STRONG_REGION_UNCONFIRMED"
                          else None)
                status = classified["status"]
                multi_timbre = None
                if status == "HIGH_CONFIDENCE_AUDIO_ALIGNMENT":
                    multi_timbre = [corroborate_excerpt(path, reference_paths[ref_index], hit)
                                    for hit in classified["supporting_hits"]]
                    if not all(item["status"] == "TIMBRE_CORROBORATED_EXCERPT"
                               for item in multi_timbre):
                        status = "MULTI_REGION_CHROMA_UNCONFIRMED"
                if (status == "SINGLE_STRONG_REGION_UNCONFIRMED" and
                        best_hit["mean_frame_cosine"] >= .85 and timbre and
                        timbre["status"] == "TIMBRE_CORROBORATED_EXCERPT"):
                    status = "HIGH_CONFIDENCE_EXCERPT_ONLY"
                comparison = (compare_original_excerpt(path, reference_paths[ref_index], best_hit)
                              if status == "HIGH_CONFIDENCE_EXCERPT_ONLY" else None)
                if (status == "HIGH_CONFIDENCE_EXCERPT_ONLY" and comparison and
                        (comparison["status"] != "WAVEFORM_COMPARISON_COMPLETE" or
                         abs(comparison["normalized_waveform_correlation"]) < .65)):
                    status = "FEATURE_MATCH_UNCONFIRMED_ORIGINAL_IDENTITY"
                matches.append({
                    "reference_index": ref_index,
                    **classified,
                    "status": status,
                    "best_hit": best_hit,
                    "verified_hits": verified_hits,
                    "timbre_corroboration": timbre,
                    "multi_region_timbre_corroboration": multi_timbre,
                    "original_vs_reference_waveform": comparison,
                })
        output.append({"source_index": source_index, "matches": sorted(matches, key=lambda m: -m["best_hit"]["mean_frame_cosine"]), "query_count": len(starts)})
    return {
        "schema_version": "shadow-original-alignment-1",
        "method": "24-bin chroma; ordered 24-second six-block ANN retrieval; 1-second ordered tempo-tolerant verification; two nonoverlapping coherent hits for high-confidence alignment",
        "limitations": ["May miss strongly transformed material, pitch shifts, short excerpts or a source omitted from the normal library", "Chroma resemblance is not proof of source identity", "No lyric, stem or DJ-intent inference"],
        "source_paths_private": [str(path.resolve()) for path in normal_paths],
        "reference_paths_private": [str(path.resolve()) for path in reference_paths],
        "rows": output,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normal-root", type=Path, required=True)
    parser.add_argument("--normal-inventory", type=Path,
                        help="Optional private library inventory: limit originals to ordinary-length real song candidates")
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.reference_root.resolve().name.casefold() != "fromdj":
        raise ValueError("reference root must be an explicit fromDJ directory")
    repo = Path(__file__).resolve().parents[2]
    destination = args.output.resolve()
    if destination.is_relative_to(repo):
        raise ValueError("Private alignments must be written outside the repository")
    if args.normal_inventory:
        inventory = json.loads(args.normal_inventory.read_text())
        normal = sorted((Path(row["private_filepath"]) for row in inventory["rows"]
                         if row["supported_extension"] and not row["synthetic_fixture_not_song"]
                         and row["probe"]["decodable"] and row["probe"]["duration_sec"] <= 600),
                        key=lambda path: path.name.casefold())
        if any(path.parent.resolve() != args.normal_root.resolve() for path in normal):
            raise ValueError("Normal-song inventory contains a path outside its root")
    else:
        normal = sorted((path for path in args.normal_root.iterdir() if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES), key=lambda path: path.name.casefold())
    refs = sorted((path for path in args.reference_root.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES), key=lambda path: str(path.relative_to(args.reference_root)).casefold())
    cache_dir = destination.parent / "private_fingerprint_cache"
    result = align_library(normal, refs, cache_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(f"Analyzed {len(normal)} normal recordings against {len(refs)} references")


if __name__ == "__main__":
    main()
