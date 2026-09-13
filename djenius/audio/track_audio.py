"""Robust stereo audio decoding shared by application-layer audio consumers.

Uses the same tiered fallback strategy as :mod:`djenius.audio.analyzer`
(soundfile -> librosa -> ffmpeg) so formats that need the ffmpeg tier for
analysis also decode here.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np
import soundfile as sf


def load_track_audio(filepath: str, target_sr: int | None = None) -> tuple[np.ndarray, int]:
    """Decode a track to stereo float32 audio, resampling if `target_sr` is given.

    Returns (audio, sample_rate) with audio shaped (n_samples, 2).
    """
    audio, sr = _decode_stereo(filepath)
    if target_sr and sr != target_sr:
        audio = _resample_stereo(audio, sr, target_sr)
        sr = target_sr
    return audio, sr


def _decode_stereo(filepath: str) -> tuple[np.ndarray, int]:
    try:
        audio, sr = sf.read(filepath, dtype="float32", always_2d=True)
        return _to_stereo(audio), sr
    except Exception:
        pass
    try:
        import librosa
        audio, sr = librosa.load(filepath, sr=None, mono=False)
        audio = audio.T if audio.ndim == 2 else audio.reshape(-1, 1)
        return _to_stereo(audio.astype(np.float32)), sr
    except Exception:
        pass
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        tmp_path = handle.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", filepath, "-ar", "44100", "-ac", "2", "-f", "wav", tmp_path],
            capture_output=True, timeout=120, check=True,
        )
        audio, sr = sf.read(tmp_path, dtype="float32", always_2d=True)
        return _to_stereo(audio), sr
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _to_stereo(audio: np.ndarray) -> np.ndarray:
    if audio.shape[1] == 1:
        return np.repeat(audio, 2, axis=1).astype(np.float32)
    if audio.shape[1] > 2:
        return audio[:, :2].astype(np.float32)
    return audio.astype(np.float32)


def _resample_stereo(audio: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    import librosa
    left = librosa.resample(np.asarray(audio[:, 0], dtype=np.float32), orig_sr=source_sr, target_sr=target_sr)
    right = librosa.resample(np.asarray(audio[:, 1], dtype=np.float32), orig_sr=source_sr, target_sr=target_sr)
    n = min(len(left), len(right))
    return np.column_stack([left[:n], right[:n]]).astype(np.float32)
