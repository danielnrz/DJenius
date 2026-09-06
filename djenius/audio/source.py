"""Audio source abstraction for provenance tracking and section editing.

Provides a clean interface for loading audio with path metadata,
supporting both direct file paths and pre-loaded audio buffers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
import soundfile as sf

from djenius.core.errors import DecodeError


@dataclass(frozen=True)
class AudioSource:
    """Represents an audio source with path metadata and lazy loading.
    
    This abstraction is used for provenance tracking where exact
    source slices need to be documented. Loading is deferred until
    needed to avoid redundant I/O operations.
    """
    
    path: str
    _audio_data: Optional[Tuple[np.ndarray, int]] = None
    _sample_rate: Optional[int] = None
    
    def __post_init__(self):
        """Validate path on initialization."""
        if not self.path:
            raise ValueError("AudioSource requires a non-empty path")
        path_obj = Path(self.path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Audio file not found: {self.path}")
    
    def load(self, target_sr: Optional[int] = None) -> Tuple[np.ndarray, int]:
        """Load the audio file, returning (audio_array, sample_rate).
        
        Args:
            target_sr: Optional sample rate for resampling. If None,
                      uses the file's native sample rate.
        
        Returns:
            Tuple of (audio_array, sample_rate) where audio_array is
            a numpy array with shape (samples,) for mono or (samples, channels)
            for multi-channel audio.
        """
        if self._audio_data is not None:
            return self._audio_data
        
        try:
            y, sr = sf.read(self.path, dtype="float32")
            if y.ndim == 1:
                y = y.reshape(-1, 1)
            
            # Resample if target_sr specified and differs
            if target_sr is not None and sr != target_sr:
                import librosa
                if y.ndim == 2:
                    channels = []
                    for ch in range(y.shape[1]):
                        channels.append(librosa.resample(y[:, ch], orig_sr=sr, target_sr=target_sr))
                    y = np.column_stack(channels)
                else:
                    y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
                sr = target_sr
            
            # Store loaded data
            object.__setattr__(self, '_audio_data', (y, sr))
            object.__setattr__(self, '_sample_rate', sr)
            
            return y, sr
            
        except Exception as e:
            raise DecodeError(f"Failed to load audio from {self.path}: {e}") from e
    
    @property
    def sample_rate(self) -> int:
        """Get the sample rate of the audio file."""
        if self._sample_rate is not None:
            return self._sample_rate
        # Read just the metadata
        with sf.SoundFile(self.path) as f:
            return f.samplerate
    
    def duration_sec(self) -> float:
        """Get the duration of the audio file in seconds."""
        sr = self.sample_rate
        if self._audio_data is not None:
            return len(self._audio_data[0]) / sr
        
        with sf.SoundFile(self.path) as f:
            return f.frames / f.samplerate
