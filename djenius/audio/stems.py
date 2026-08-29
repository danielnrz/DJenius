"""Stem separation module using Demucs (optional dependency).

Provides source separation into vocal/drum/bass/other stems.
All heavy dependencies (torch, demucs) are imported lazily so the
core DJenius workflow works without them.

Stem files are cached on disk keyed by file hash. Repeated calls for
the same track skip separation entirely.

Typical usage::

    from djenius.audio.stems import separate_stems, stems_available

    if stems_available():
        stems = separate_stems("track.mp3", output_dir="stems/")
        # stems = {"vocals": "path/to/vocals.wav", ...}
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

# Stem labels produced by Demucs (htdemucs model)
STEM_NAMES = ("vocals", "drums", "bass", "other")

# Default subdirectory for stem cache
DEFAULT_STEM_DIR = "stems"


def stems_available() -> bool:
    """Check whether Demucs + PyTorch are installed and importable.

    Returns True only if both ``demucs`` and ``torch`` can be imported
    without error.  This is a fast check — no GPU probing.
    """
    try:
        import demucs  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def gpu_available() -> bool:
    """Return True if a CUDA-capable GPU is reachable by PyTorch."""
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def _file_hash(filepath: str) -> str:
    """Fast xxhash-based file fingerprint (matches db/cache pattern)."""
    try:
        import xxhash
        h = xxhash.xxh128()
    except ImportError:
        h = hashlib.blake2b(digest_size=16)

    with open(filepath, "rb") as f:
        while chunk := f.read(1 << 20):  # 1 MB chunks
            h.update(chunk)
    return h.hexdigest()


def _stem_cache_path(stem_dir: Path, fhash: str) -> dict[str, Path]:
    """Return expected paths for cached stem WAV files."""
    return {name: stem_dir / f"{fhash}_{name}.wav" for name in STEM_NAMES}


def stems_cached(filepath: str, stem_dir: str | Path = DEFAULT_STEM_DIR) -> bool:
    """Check whether stems are already cached on disk for this file."""
    fhash = _file_hash(filepath)
    cache = _stem_cache_path(Path(stem_dir), fhash)
    return all(p.exists() for p in cache.values())


def load_stems(
    filepath: str,
    sr: int = 44100,
    stem_dir: str | Path = DEFAULT_STEM_DIR,
) -> dict[str, np.ndarray]:
    """Load pre-computed stems from disk cache.

    Args:
        filepath: Original audio file path (used to derive hash).
        sr: Expected sample rate of cached stems.
        stem_dir: Directory where stem WAVs are stored.

    Returns:
        Dict mapping stem name to audio array (stereo float32).
        Missing stems are silently skipped.

    Raises:
        FileNotFoundError: If no cached stems exist for this file.
    """
    fhash = _file_hash(filepath)
    cache = _stem_cache_path(Path(stem_dir), fhash)

    if not any(p.exists() for p in cache.values()):
        raise FileNotFoundError(f"No cached stems for {filepath} (hash={fhash})")

    stems: dict[str, np.ndarray] = {}
    for name in STEM_NAMES:
        path = cache[name]
        if path.exists():
            audio, file_sr = sf.read(str(path), dtype="float32")
            if file_sr != sr:
                import librosa
                # SoundFile returns (samples, channels) — resample along time axis (0)
                audio = librosa.resample(audio, orig_sr=file_sr, target_sr=sr, axis=0)
            stems[name] = audio

    return stems


def separate_stems(
    filepath: str,
    stem_dir: str | Path = DEFAULT_STEM_DIR,
    model_name: str = "htdemucs",
    device: Optional[str] = None,
    force: bool = False,
    sr: int = 44100,
) -> dict[str, str]:
    """Separate an audio file into stems using Demucs.

    Results are cached on disk. Repeated calls return cached paths
    instantly unless ``force=True``.

    Args:
        filepath: Path to the audio file to separate.
        stem_dir: Directory to write stem WAVs.
        model_name: Demucs model name (default: htdemucs).
        device: PyTorch device string (None = auto-detect).
        force: If True, re-separate even if cached.
        sr: Sample rate for output stems.

    Returns:
        Dict mapping stem name to file path (str).
        Keys: "vocals", "drums", "bass", "other".

    Raises:
        ImportError: If demucs/torch are not installed.
        RuntimeError: If separation fails.
    """
    filepath = str(Path(filepath).absolute())
    stem_dir = Path(stem_dir)
    stem_dir.mkdir(parents=True, exist_ok=True)

    fhash = _file_hash(filepath)
    cache = _stem_cache_path(stem_dir, fhash)

    # Return cached stems if available
    if not force and all(p.exists() for p in cache.values()):
        logger.info("Stems cached for %s", Path(filepath).name)
        return {name: str(cache[name]) for name in STEM_NAMES}

    # Lazy import — only fails if stems are actually requested
    try:
        import torch
        from demucs.pretrained import get_model
        from demucs.audio import save_audio
        from demucs.apply import apply_model
    except ImportError as exc:
        raise ImportError(
            "Stem separation requires demucs and torch. "
            "Install with: pip install djenius[stems]"
        ) from exc

    # Resolve device
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info(
        "Separating stems for %s (model=%s, device=%s)...",
        Path(filepath).name, model_name, device,
    )

    t0 = time.time()

    # Load audio — Demucs expects (channels, samples) float64
    try:
        audio, file_sr = sf.read(filepath, dtype="float32")
    except Exception:
        # Fallback via ffmpeg for exotic formats (M4A, AAC, etc.)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", filepath, "-ar", str(sr),
                 "-ac", "2", "-f", "wav", tmp_path],
                capture_output=True, timeout=300, check=True,
            )
            audio, file_sr = sf.read(tmp_path, dtype="float32")
        finally:
            import os
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # Convert to (channels, samples) for Demucs
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]  # mono -> (1, samples)
    else:
        audio = audio.T  # (samples, channels) -> (channels, samples)

    # Resample if needed
    if file_sr != sr:
        import librosa
        audio = librosa.resample(audio, orig_sr=file_sr, target_sr=sr, axis=-1)

    # Add batch dimension: (1, channels, samples)
    audio_tensor = torch.from_numpy(audio).float().unsqueeze(0)

    # Load model and run separation
    model = get_model(model_name)
    model.to(device)

    with torch.no_grad():
        sources = apply_model(model, audio_tensor, device=device)

    # sources shape: (1, n_sources, channels, samples)
    sources = sources[0].cpu().numpy()  # (n_sources, channels, samples)

    # Map model output channels to (samples, channels) and save
    model_sources = model.sources  # e.g. ["drums", "bass", "other", "vocals"]
    result: dict[str, str] = {}

    for i, source_name in enumerate(model_sources):
        if source_name not in STEM_NAMES:
            continue
        # (channels, samples) -> (samples, channels)
        stem_audio = sources[i].T.astype(np.float32)
        out_path = cache[source_name]
        sf.write(str(out_path), stem_audio, sr)
        result[source_name] = str(out_path)
        logger.debug("Saved stem %s -> %s", source_name, out_path.name)

    elapsed = time.time() - t0
    logger.info(
        "Stem separation complete for %s in %.1fs",
        Path(filepath).name, elapsed,
    )

    return result


def get_stem_audio(
    filepath: str,
    stem_name: str,
    sr: int = 44100,
    stem_dir: str | Path = DEFAULT_STEM_DIR,
) -> Optional[np.ndarray]:
    """Load a single stem as audio array.

    Returns None if the stem is not available (not cached and
    stems not installed).  Never raises for missing stems.
    """
    if stem_name not in STEM_NAMES:
        return None

    try:
        stems = load_stems(filepath, sr=sr, stem_dir=stem_dir)
        return stems.get(stem_name)
    except FileNotFoundError:
        return None
    except ImportError:
        return None
