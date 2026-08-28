"""Music library scanner - discovers audio files and extracts basic metadata."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import soundfile as sf

from djenius.core.models import TrackMetadata

SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma", ".aiff"}


def scan_directory(
    directory: str,
    recursive: bool = True,
    exclude_patterns: Optional[list[str]] = None,
) -> list[TrackMetadata]:
    """Recursively scan a directory for audio files.

    Args:
        directory: Root directory to scan.
        recursive: Whether to recurse into subdirectories.
        exclude_patterns: Path substrings to exclude.

    Returns:
        List of TrackMetadata for each discovered file.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    exclude = exclude_patterns or []
    tracks = []

    if recursive:
        walker = dir_path.rglob("*")
    else:
        walker = dir_path.glob("*")

    for fpath in walker:
        if not fpath.is_file():
            continue

        if fpath.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        # Check exclusions
        fpath_str = str(fpath)
        if any(excl in fpath_str for excl in exclude):
            continue

        meta = extract_metadata(fpath_str)
        if meta is not None:
            tracks.append(meta)

    return tracks


def extract_metadata(filepath: str) -> Optional[TrackMetadata]:
    """Extract basic metadata from an audio file.

    Returns None if the file cannot be read.
    """
    path = Path(filepath)
    if not path.exists():
        return None

    try:
        info = sf.info(filepath)
        duration = info.duration
        sample_rate = info.samplerate
        channels = info.channels
        fmt = info.format
    except Exception:
        # Try librosa as fallback for formats soundfile can't handle
        try:
            import librosa
            import numpy as np
            # Just get info, don't load full file
            y, sr = librosa.load(filepath, sr=None, duration=0.1)
            duration = float(len(y)) / sr  # Very rough estimate
            sample_rate = sr
            channels = 1 if y.ndim == 1 else y.shape[0]
            fmt = path.suffix.upper().strip(".")
        except Exception:
            return None

    # Extract metadata from file info
    title = path.stem
    artist = ""
    album = ""

    # Try mutagen for better metadata
    try:
        import mutagen
        tag_file = mutagen.File(filepath, easy=True)
        if tag_file is not None:
            if tag_file.get("title"):
                title = tag_file["title"][0]
            if tag_file.get("artist"):
                artist = tag_file["artist"][0]
            if tag_file.get("album"):
                album = tag_file["album"][0]
    except Exception:
        pass

    return TrackMetadata(
        filepath=str(path.absolute()),
        title=title,
        artist=artist,
        album=album,
        duration_sec=duration,
        sample_rate=sample_rate,
        channels=channels,
        format=fmt,
    )
