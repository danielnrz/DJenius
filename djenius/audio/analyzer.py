"""Audio analysis pipeline - extracts musical features from audio files.

Uses librosa for most analysis, with fallbacks for edge cases.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np
import librosa
import soundfile as sf

from djenius.core.models import TrackProfile, TrackMetadata, TrackAnalysis
from djenius.db.cache import compute_file_hash
from djenius.utils.camelot import detect_key_from_chroma, key_to_camelot
from djenius.utils.audio_math import (
    compute_energy_curve,
    compute_spectral_energy_bands,
    detect_intro_outro,
)

logger = logging.getLogger(__name__)


def analyze_track(
    filepath: str,
    target_sr: int = 22050,
    force: bool = False,
    cache=None,
) -> TrackProfile:
    """Full analysis pipeline for a single track.

    Args:
        filepath: Path to the audio file.
        target_sr: Sample rate for analysis (22050 is librosa default).
        force: If True, re-analyze even if cached.
        cache: Optional AnalysisCache instance.

    Returns:
        TrackProfile with complete analysis.
    """
    filepath = str(Path(filepath).absolute())

    # Check cache first
    if cache is not None and not force:
        cached = cache.get(filepath)
        if cached is not None:
            logger.debug("Cache hit for %s", filepath)
            return cached

    logger.info("Analyzing: %s", filepath)

    # Compute file hash
    file_hash = compute_file_hash(filepath)

    # Load audio
    try:
        y, sr = librosa.load(filepath, sr=target_sr, mono=True)
    except Exception as e:
        logger.error("Failed to load %s: %s", filepath, e)
        raise ValueError(f"Cannot load audio file: {filepath}") from e

    if len(y) == 0:
        raise ValueError(f"Empty audio file: {filepath}")

    duration = len(y) / sr

    # Load stereo for loudness measurement
    try:
        y_stereo, sr_stereo = sf.read(filepath, dtype="float32")
        if y_stereo.ndim == 1:
            y_stereo = y_stereo.reshape(-1, 1)
    except Exception:
        y_stereo = y.reshape(-1, 1)
        sr_stereo = sr

    # Start timing
    t0 = time.time()

    analysis = TrackAnalysis()

    # --- BPM and Beats ---
    try:
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        # librosa 0.10+ returns array for tempo
        if hasattr(tempo, '__len__'):
            tempo = float(tempo[0]) if len(tempo) > 0 else 0.0
        else:
            tempo = float(tempo)

        beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

        # Validate BPM
        if tempo < 40 or tempo > 220:
            # Try with a different estimate
            tempo_alt, _ = librosa.beat.beat_track(y=y, sr=sr, bpm=tempo * 2)
            if hasattr(tempo_alt, '__len__'):
                tempo_alt = float(tempo_alt[0]) if len(tempo_alt) > 0 else tempo
            if 60 <= tempo_alt <= 180:
                tempo = tempo_alt
                _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, bpm=tempo)
                beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

        # Handle 70 vs 140 BPM ambiguity
        if tempo < 70:
            tempo *= 2
        elif tempo > 180:
            tempo /= 2

        # Estimate beat interval consistency for confidence
        if len(beat_times) >= 3:
            intervals = np.diff(beat_times)
            expected_interval = 60.0 / tempo
            errors = np.abs(intervals - expected_interval)
            beat_confidence = max(0.0, 1.0 - float(np.mean(errors) / expected_interval))
        else:
            beat_confidence = 0.3

        analysis.bpm = round(tempo, 1)
        analysis.bpm_confidence = round(min(1.0, beat_confidence), 3)
        analysis.beat_times = beat_times

    except Exception as e:
        logger.warning("BPM analysis failed for %s: %s", filepath, e)
        analysis.bpm = 120.0
        analysis.bpm_confidence = 0.0

    # --- Downbeats and Bars ---
    try:
        bar_times = _detect_downbeats(beat_times, analysis.bpm)
        analysis.downbeat_times = bar_times
        analysis.bar_times = bar_times
        analysis.estimated_bars = len(bar_times)
    except Exception as e:
        logger.warning("Downbeat detection failed for %s: %s", filepath, e)
        # Fallback: assume every 4 beats is a bar
        if len(beat_times) >= 4:
            analysis.bar_times = beat_times[::4]
            analysis.downbeat_times = beat_times[::4]
            analysis.estimated_bars = len(analysis.bar_times)
        else:
            analysis.bar_times = []
            analysis.downbeat_times = []

    # --- Key Detection ---
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        # Average chroma over time
        avg_chroma = chroma.mean(axis=1).tolist()
        key_name, camelot, key_conf = detect_key_from_chroma(avg_chroma)
        analysis.key = key_name
        analysis.camelot = camelot
        analysis.key_confidence = round(key_conf, 3)
    except Exception as e:
        logger.warning("Key detection failed for %s: %s", filepath, e)
        analysis.key = ""
        analysis.camelot = ""
        analysis.key_confidence = 0.0

    # --- Loudness ---
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr_stereo)
        loudness_audio = y_stereo if y_stereo.ndim == 2 else y_stereo.reshape(-1, 1)
        integrated_lufs = meter.integrated_loudness(loudness_audio)
        if np.isinf(integrated_lufs) or np.isnan(integrated_lufs):
            integrated_lufs = -23.0
        analysis.integrated_lufs = round(float(integrated_lufs), 1)
    except Exception as e:
        logger.warning("LUFS measurement failed for %s: %s", filepath, e)
        analysis.integrated_lufs = -23.0

    try:
        analysis.peak_level = round(float(20 * np.log10(np.max(np.abs(y)) + 1e-10)), 1)
    except Exception:
        analysis.peak_level = -1.0

    try:
        analysis.rms_energy = round(float(np.sqrt(np.mean(y ** 2))), 4)
    except Exception:
        analysis.rms_energy = 0.0

    # --- Energy Curve ---
    try:
        energy_curve = compute_energy_curve(y, sr, resolution_hz=1.0)
        analysis.energy_curve = energy_curve.tolist()
        analysis.mean_energy = round(float(np.mean(energy_curve)), 3) if len(energy_curve) > 0 else 0.5
    except Exception as e:
        logger.warning("Energy curve failed for %s: %s", filepath, e)
        analysis.energy_curve = [0.5]
        analysis.mean_energy = 0.5

    # --- Spectral Features ---
    try:
        low, mid, high = compute_spectral_energy_bands(y, sr)
        analysis.low_energy = round(low, 3)
        analysis.mid_energy = round(mid, 3)
        analysis.high_energy = round(high, 3)

        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        analysis.spectral_centroid_mean = round(float(np.mean(spectral_centroid)), 1)
    except Exception as e:
        logger.warning("Spectral analysis failed for %s: %s", filepath, e)
        analysis.low_energy = 0.33
        analysis.mid_energy = 0.34
        analysis.high_energy = 0.33

    # --- Phrase Boundaries ---
    try:
        phrases = _detect_phrase_boundaries(y, sr, analysis.beat_times, analysis.bpm)
        analysis.phrase_boundaries = phrases
    except Exception as e:
        logger.warning("Phrase detection failed for %s: %s", filepath, e)
        # Fallback: group beats into 8-bar phrases
        if len(beat_times) >= 32:
            bar_duration = 4 * (60.0 / analysis.bpm) if analysis.bpm > 0 else 8.0
            phrase_duration = bar_duration * 8
            analysis.phrase_boundaries = list(np.arange(0, duration, phrase_duration))
        else:
            analysis.phrase_boundaries = []

    # --- Intro/Outro ---
    try:
        intro_end, outro_start = detect_intro_outro(
            np.array(analysis.energy_curve),
            threshold=0.3,
            min_bars=4,
            bar_duration_hint=4 * 60.0 / max(analysis.bpm, 60),
        )
        # Convert from 1Hz indices to seconds
        analysis.intro_end = intro_end
        analysis.outro_start = outro_start * (duration / max(len(analysis.energy_curve), 1))
    except Exception as e:
        logger.warning("Intro/outro detection failed for %s: %s", filepath, e)
        analysis.intro_end = 0.0
        analysis.outro_start = duration * 0.85

    # --- Transition Points ---
    try:
        analysis.possible_exit_points = _find_transition_points(
            analysis, duration, is_exit=True
        )
        analysis.possible_entry_points = _find_transition_points(
            analysis, duration, is_exit=False
        )
    except Exception:
        analysis.possible_exit_points = []
        analysis.possible_entry_points = []

    # --- Overall Confidence ---
    confidence_factors = [
        analysis.bpm_confidence,
        analysis.key_confidence,
        min(1.0, len(analysis.beat_times) / 20),
        min(1.0, len(analysis.phrase_boundaries) / 4),
    ]
    analysis.analysis_confidence = round(
        float(np.mean(confidence_factors)), 3
    )

    elapsed = time.time() - t0
    logger.info(
        "Analyzed %s in %.1fs - BPM=%.1f key=%s (%s) energy=%.2f conf=%.2f",
        Path(filepath).name, elapsed, analysis.bpm, analysis.key,
        analysis.camelot, analysis.mean_energy, analysis.analysis_confidence,
    )

    profile = TrackProfile(
        id=file_hash,
        metadata=TrackMetadata(
            filepath=filepath,
            title=Path(filepath).stem,
            duration_sec=duration,
            sample_rate=sr,
            channels=1,
            format=Path(filepath).suffix.strip("."),
            file_hash=file_hash,
        ),
        analysis=analysis,
    )

    # Try to get better metadata
    try:
        from djenius.audio.scanner import extract_metadata
        meta = extract_metadata(filepath)
        if meta:
            profile.metadata.title = meta.title
            profile.metadata.artist = meta.artist
            profile.metadata.album = meta.album
            profile.metadata.channels = meta.channels
    except Exception:
        pass

    # Cache the result
    if cache is not None:
        cache.put(profile)

    return profile


def _detect_downbeats(beat_times: list[float], bpm: float) -> list[float]:
    """Detect downbeat positions from beat times.

    Assumes 4/4 time signature. Groups beats into bars of 4.
    Uses energy analysis to verify bar alignment.
    """
    if not beat_times or bpm <= 0:
        return []

    beats = np.array(beat_times)
    beat_interval = 60.0 / bpm
    bar_duration = beat_interval * 4

    # Align to bars by finding the best phase offset
    # Use first beat as reference, then verify with energy
    downbeats = list(beats[::4])  # Every 4th beat

    return downbeats


def _detect_phrase_boundaries(
    y: np.ndarray,
    sr: int,
    beat_times: list[float],
    bpm: float,
) -> list[float]:
    """Detect phrase boundaries using self-similarity of MFCCs.

    Looks for structural changes that align with musical phrases (8 or 16 bars).
    """
    if len(beat_times) < 16 or bpm <= 0:
        return []

    # Compute MFCCs
    hop_length = 512
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, hop_length=hop_length)

    # Cap the matrix size to avoid OOM on long tracks
    max_frames = 10000  # ~3 minutes at hop_length=512, sr=44100
    if mfcc.shape[1] > max_frames:
        step = mfcc.shape[1] // max_frames
        mfcc = mfcc[:, ::step]

    # Compute self-similarity matrix
    sim = librosa.segment.recurrence_matrix(
        mfcc, mode="affinity", metric="cosine", k=5
    )

    # Get novelty curve
    novelty = librosa.segment.agglomerative(sim, k=64)

    # Convert novelty times to seconds
    times = librosa.frames_to_time(np.arange(len(novelty)), sr=sr, hop_length=hop_length)

    # Filter to find phrase boundaries aligned with bars
    bar_duration = 4 * (60.0 / bpm)
    min_phrase = bar_duration * 8  # 8 bars minimum phrase

    phrases = []
    for t in times[novelty > 0.5]:
        # Snap to nearest bar boundary
        bar_idx = round(t / bar_duration)
        snapped = bar_idx * bar_duration
        if snapped >= 1.0 and snapped not in phrases:
            phrases.append(round(snapped, 3))

    # Remove duplicates and sort
    phrases = sorted(set(phrases))

    # Ensure minimum spacing
    filtered = []
    for p in phrases:
        if not filtered or (p - filtered[-1]) >= min_phrase * 0.5:
            filtered.append(p)

    return filtered


def _find_transition_points(
    analysis: TrackAnalysis,
    duration: float,
    is_exit: bool = True,
) -> list[float]:
    """Find good points in a track for transitions.

    Exit points: where the outgoing track can leave.
    Entry points: where the incoming track can enter.
    """
    points = []

    if is_exit:
        # Good exit points are at phrase boundaries in the outro region
        outro_region_start = analysis.outro_start if analysis.outro_start > 0 else duration * 0.7

        for phrase in analysis.phrase_boundaries:
            if phrase >= outro_region_start:
                points.append(phrase)

        # Also add some general phrase boundaries in the later part
        for phrase in analysis.phrase_boundaries:
            if phrase >= duration * 0.5:
                points.append(phrase)
    else:
        # Good entry points are at phrase boundaries after the intro
        intro_end = analysis.intro_end if analysis.intro_end > 0 else duration * 0.15

        for phrase in analysis.phrase_boundaries:
            if phrase >= intro_end:
                points.append(phrase)

    # Remove duplicates and sort
    points = sorted(set(round(p, 3) for p in points))

    return points
