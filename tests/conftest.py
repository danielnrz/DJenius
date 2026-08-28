"""Shared test fixtures for DJenius test suite.

Generates synthetic audio files (sine waves, click tracks) using numpy/soundfile.
No real audio files are used.
"""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf
from pathlib import Path

from djenius.core.models import TrackMetadata, TrackAnalysis, TrackProfile


SR = 44100


@pytest.fixture
def sr():
    """Standard sample rate."""
    return SR


@pytest.fixture
def tmp_wav(tmp_path):
    """Factory fixture: write a numpy array to a temporary WAV file."""
    def _write(audio: np.ndarray, name: str = "test.wav", sr: int = SR) -> Path:
        path = tmp_path / name
        sf.write(str(path), audio, sr, subtype="PCM_16")
        return path
    return _write


@pytest.fixture
def sine_wave(sr):
    """Generate a mono sine wave at a given frequency and duration."""
    def _gen(freq: float = 440.0, duration: float = 2.0, amplitude: float = 0.5) -> np.ndarray:
        t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
        return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return _gen


@pytest.fixture
def stereo_sine(sr):
    """Generate a stereo sine wave (slight detune for L/R)."""
    def _gen(freq: float = 440.0, duration: float = 2.0, amplitude: float = 0.5) -> np.ndarray:
        t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
        left = amplitude * np.sin(2 * np.pi * freq * t)
        right = amplitude * np.sin(2 * np.pi * (freq * 1.005) * t)
        return np.column_stack([left, right]).astype(np.float32)
    return _gen


@pytest.fixture
def click_track(sr):
    """Generate a click track at a given BPM with short impulses."""
    def _gen(bpm: float = 120.0, duration: float = 4.0, amplitude: float = 0.8) -> np.ndarray:
        n_samples = int(sr * duration)
        audio = np.zeros(n_samples, dtype=np.float32)
        samples_per_beat = int(sr * 60.0 / bpm)
        click_len = min(256, samples_per_beat // 4)
        for i in range(0, n_samples, samples_per_beat):
            end = min(i + click_len, n_samples)
            # Short burst of high-frequency sine to simulate a transient
            t = np.linspace(0, click_len / sr, click_len, endpoint=False, dtype=np.float32)
            click = amplitude * np.sin(2 * np.pi * 1000 * t)
            # Apply decay envelope
            click *= np.exp(-np.linspace(0, 4, click_len)).astype(np.float32)
            audio[i:end] = click[:end - i]
        return audio
    return _gen


@pytest.fixture
def synthetic_track_profile(tmp_wav, sine_wave):
    """Create a full TrackProfile with a synthetic WAV file."""
    audio = sine_wave(freq=440.0, duration=3.0)
    path = tmp_wav(audio, name="synthetic_a.wav")

    metadata = TrackMetadata(
        filepath=str(path),
        title="Synthetic A",
        artist="Test Artist",
        album="Test Album",
        duration_sec=3.0,
        sample_rate=SR,
        channels=1,
        format="WAV",
    )

    beat_times = [float(i * 0.5) for i in range(1, 12)]  # 120 BPM -> 0.5s per beat

    analysis = TrackAnalysis(
        bpm=120.0,
        bpm_confidence=0.95,
        beat_times=beat_times,
        downbeat_times=[0.0, 2.0],
        bar_times=[0.0, 2.0],
        estimated_bars=1,
        key="C Major",
        camelot="8B",
        key_confidence=0.9,
        integrated_lufs=-14.0,
        peak_level=-1.0,
        rms_energy=0.3,
        energy_curve=[0.3, 0.5, 0.7, 0.6, 0.4],
        mean_energy=0.5,
        spectral_centroid_mean=2000.0,
        low_energy=0.2,
        mid_energy=0.5,
        high_energy=0.3,
        phrase_boundaries=[0.0, 1.0, 2.0],
        intro_end=0.5,
        outro_start=2.5,
        possible_exit_points=[1.0, 2.0],
        possible_entry_points=[0.0, 0.5],
        analysis_confidence=0.85,
    )

    return TrackProfile(
        id="synthetic_a_hash",
        metadata=metadata,
        analysis=analysis,
    )


@pytest.fixture
def synthetic_track_profile_b(tmp_wav, sine_wave):
    """A second profile with different characteristics for pairwise tests."""
    audio = sine_wave(freq=330.0, duration=4.0)
    path = tmp_wav(audio, name="synthetic_b.wav")

    metadata = TrackMetadata(
        filepath=str(path),
        title="Synthetic B",
        artist="Test Artist B",
        album="Test Album B",
        duration_sec=4.0,
        sample_rate=SR,
        channels=1,
        format="WAV",
    )

    beat_times = [float(i * 0.55) for i in range(1, 15)]  # ~109 BPM

    analysis = TrackAnalysis(
        bpm=109.0,
        bpm_confidence=0.88,
        beat_times=beat_times,
        downbeat_times=[0.0, 2.2],
        bar_times=[0.0, 2.2],
        estimated_bars=1,
        key="A Minor",
        camelot="8A",
        key_confidence=0.85,
        integrated_lufs=-16.0,
        peak_level=-3.0,
        rms_energy=0.25,
        energy_curve=[0.2, 0.4, 0.6, 0.5, 0.3],
        mean_energy=0.4,
        spectral_centroid_mean=1800.0,
        low_energy=0.3,
        mid_energy=0.4,
        high_energy=0.3,
        phrase_boundaries=[0.0, 1.1, 2.2],
        intro_end=0.55,
        outro_start=3.3,
        possible_exit_points=[1.1, 2.2],
        possible_entry_points=[0.0, 0.55],
        analysis_confidence=0.82,
    )

    return TrackProfile(
        id="synthetic_b_hash",
        metadata=metadata,
        analysis=analysis,
    )


@pytest.fixture
def stereo_audio_block(sr):
    """A short stereo audio block for transition testing."""
    duration = 2.0
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False, dtype=np.float32)
    left = 0.3 * np.sin(2 * np.pi * 200 * t)
    right = 0.3 * np.sin(2 * np.pi * 210 * t)
    return np.column_stack([left, right]).astype(np.float32)
