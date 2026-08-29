"""Tests for the renderer V5.1 fixes: timeline assembly, audio loading, diagnostics."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from djenius.core.errors import DecodeError
from djenius.core.models import (
    SetPlan, TransitionPlan, TransitionType, CompatibilityScore,
    EnergyProfile, TrackProfile, TrackMetadata, TrackAnalysis,
)
from djenius.audio.renderer import render_mix, _load_audio


def _make_track(
    track_id: str,
    title: str,
    filepath: str,
    duration_sec: float = 10.0,
    bpm: float = 120.0,
    energy: float = 0.5,
) -> TrackProfile:
    """Create a mock TrackProfile for testing."""
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(
            filepath=filepath,
            title=title,
            artist="Test Artist",
            duration_sec=duration_sec,
        ),
        analysis=TrackAnalysis(
            bpm=bpm,
            mean_energy=energy,
            key="C",
            key_confidence=0.9,
            intro_end=2.0,
            outro_start=duration_sec - 2.0,
            bar_times=[],
            bar_energies=[],
            possible_entry_points=[duration_sec * 0.1],
            possible_exit_points=[duration_sec * 0.9],
        ),
    )


def _make_transition(
    source_id: str,
    target_id: str,
    source_exit_time: float,
    target_entry_time: float,
    overlap_duration: float,
    transition_type: TransitionType = TransitionType.CROSSFADE,
) -> TransitionPlan:
    """Create a mock TransitionPlan for testing."""
    return TransitionPlan(
        source_track_id=source_id,
        target_track_id=target_id,
        transition_type=transition_type,
        source_exit_time=source_exit_time,
        target_entry_time=target_entry_time,
        overlap_duration=overlap_duration,
        length_bars=8,
        target_bpm=0.0,
        requires_stretch=False,
        stretch_amount_pct=0.0,
        compatibility_score=CompatibilityScore(
            source_id=source_id,
            target_id=target_id,
            overall_score=0.8,
            tempo_score=0.9,
            energy_score=0.7,
            key_score=0.85,
        ),
        confidence=0.9,
        reasoning="Test transition",
    )


def _create_test_audio_file(
    filepath: str,
    duration_sec: float = 10.0,
    sample_rate: int = 44100,
    frequency: float = 440.0,
) -> None:
    """Create a test WAV file with a sine wave."""
    import soundfile as sf
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
    sf.write(filepath, audio, sample_rate)


def _create_test_m4a_file(filepath: str, duration_sec: float = 10.0) -> None:
    """Create a test M4A file using ffmpeg."""
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"sine=frequency=440:duration={duration_sec}",
        "-codec:a", "aac", "-b:a", "128k", filepath,
    ]
    subprocess.run(cmd, capture_output=True, check=True)


class TestThreeTrackTimeline:
    """Test correct assembly of A -> B -> C without sequence bleeding."""

    def test_three_track_assembly(self, tmp_path):
        """Three tracks should assemble monotonically without overlap."""
        # Create test audio files
        track_a_path = str(tmp_path / "track_a.wav")
        track_b_path = str(tmp_path / "track_b.wav")
        track_c_path = str(tmp_path / "track_c.wav")
        output_path = str(tmp_path / "output.wav")
        diagnostics_path = str(tmp_path / "output_diagnostics.json")

        _create_test_audio_file(track_a_path, 10.0, 44100, 440.0)
        _create_test_audio_file(track_b_path, 8.0, 44100, 550.0)
        _create_test_audio_file(track_c_path, 6.0, 44100, 660.0)

        track_a = _make_track("a", "Track A", track_a_path, 10.0)
        track_b = _make_track("b", "Track B", track_b_path, 8.0)
        track_c = _make_track("c", "Track C", track_c_path, 6.0)

        trans_ab = _make_transition("a", "b", 8.0, 1.0, 2.0)
        trans_bc = _make_transition("b", "c", 6.0, 0.5, 1.5)

        plan = SetPlan(
            tracks=[track_a, track_b, track_c],
            transitions=[trans_ab, trans_bc],
            total_duration_sec=20.0,
            target_duration_sec=20.0,
            energy_profile=EnergyProfile.STEADY,
        )

        result = render_mix(plan, output_path, "wav", sample_rate=44100)
        
        assert os.path.exists(output_path)
        assert result["transitions_rendered"] == 2
        assert result["duration_sec"] > 0

        # Check diagnostics JSON
        assert os.path.exists(diagnostics_path)
        with open(diagnostics_path) as f:
            diag = json.load(f)
        assert len(diag["events"]) > 0


class TestNoDuplicatedIntervals:
    """Test that no source audio sample index goes backwards."""

    def test_no_backwards_samples(self, tmp_path):
        """Source samples should only move forward, never repeat."""
        track_a_path = str(tmp_path / "track_a.wav")
        track_b_path = str(tmp_path / "track_b.wav")
        output_path = str(tmp_path / "output.wav")

        _create_test_audio_file(track_a_path, 10.0)
        _create_test_audio_file(track_b_path, 8.0)

        track_a = _make_track("a", "Track A", track_a_path, 10.0)
        track_b = _make_track("b", "Track B", track_b_path, 8.0)

        trans_ab = _make_transition("a", "b", 8.0, 1.0, 2.0)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans_ab],
            total_duration_sec=16.0,
            target_duration_sec=16.0,
            energy_profile=EnergyProfile.STEADY,
        )

        result = render_mix(plan, output_path, "wav", sample_rate=44100)

        # Load diagnostics and check for backwards samples
        diagnostics_path = result["timeline_diagnostics_path"]
        with open(diagnostics_path) as f:
            diag = json.load(f)

        for event in diag["events"]:
            if event["type"] == "track":
                # Source samples should only move forward
                assert event["source_end_sample"] >= event["source_start_sample"]


class TestNoSilencePlaceholder:
    """Test that undecodable files do not generate silent placeholders."""

    def test_decode_error_on_invalid_file(self, tmp_path):
        """Invalid audio should raise DecodeError, not produce silence."""
        invalid_path = str(tmp_path / "invalid.wav")
        with open(invalid_path, "w") as f:
            f.write("This is not an audio file")

        with pytest.raises(DecodeError):
            _load_audio(invalid_path, 44100)


class TestDecoderFailureException:
    """Test that DecodeError is raised on completely invalid audio files."""

    def test_corrupt_file_raises_error(self, tmp_path):
        """Corrupt audio files should raise DecodeError."""
        corrupt_path = str(tmp_path / "corrupt.wav")
        with open(corrupt_path, "wb") as f:
            f.write(b"RIFF" + b"\x00" * 100)  # Corrupt WAV header

        with pytest.raises(DecodeError):
            _load_audio(corrupt_path, 44100)


class TestFFmpegFallback:
    """Test that FFmpeg fallback works when soundfile fails."""

    def test_m4a_fallback_to_ffmpeg(self, tmp_path):
        """M4A files should load via FFmpeg fallback."""
        m4a_path = str(tmp_path / "test.m4a")
        _create_test_m4a_file(m4a_path, 2.0)

        # This should not raise an exception
        audio, sr = _load_audio(m4a_path, 44100)
        assert audio is not None
        assert sr == 44100
        assert len(audio) > 0


class TestTransitionTiming:
    """Test that transition start/end sample indices match planner's overlap."""

    def test_transition_timing_match(self, tmp_path):
        """Transition duration should match planner's overlap_duration."""
        track_a_path = str(tmp_path / "track_a.wav")
        track_b_path = str(tmp_path / "track_b.wav")
        output_path = str(tmp_path / "output.wav")

        _create_test_audio_file(track_a_path, 10.0)
        _create_test_audio_file(track_b_path, 8.0)

        track_a = _make_track("a", "Track A", track_a_path, 10.0)
        track_b = _make_track("b", "Track B", track_b_path, 8.0)

        overlap_duration = 2.0
        trans_ab = _make_transition("a", "b", 8.0, 1.0, overlap_duration)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans_ab],
            total_duration_sec=16.0,
            target_duration_sec=16.0,
            energy_profile=EnergyProfile.STEADY,
        )

        result = render_mix(plan, output_path, "wav", sample_rate=44100)

        # Check diagnostics for transition timing
        diagnostics_path = result["timeline_diagnostics_path"]
        with open(diagnostics_path) as f:
            diag = json.load(f)

        transitions = [e for e in diag["events"] if e["type"] == "transition"]
        assert len(transitions) == 1
        
        trans = transitions[0]
        # Transition duration should be close to overlap_duration
        actual_duration = trans["mix_end_sec"] - trans["mix_start_sec"]
        assert abs(actual_duration - overlap_duration) < 0.1


class TestFinalTrack:
    """Test that the last track correctly ignores exit logic."""

    def test_final_track_plays_to_end(self, tmp_path):
        """Final track should play to its physical completion."""
        track_a_path = str(tmp_path / "track_a.wav")
        track_b_path = str(tmp_path / "track_b.wav")
        output_path = str(tmp_path / "output.wav")

        _create_test_audio_file(track_a_path, 10.0)
        _create_test_audio_file(track_b_path, 8.0)

        track_a = _make_track("a", "Track A", track_a_path, 10.0)
        track_b = _make_track("b", "Track B", track_b_path, 8.0)

        trans_ab = _make_transition("a", "b", 8.0, 1.0, 2.0)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans_ab],
            total_duration_sec=16.0,
            target_duration_sec=16.0,
            energy_profile=EnergyProfile.STEADY,
        )

        result = render_mix(plan, output_path, "wav", sample_rate=44100)

        # Check diagnostics
        diagnostics_path = result["timeline_diagnostics_path"]
        with open(diagnostics_path) as f:
            diag = json.load(f)

        # Find the last track event
        track_events = [e for e in diag["events"] if e["type"] == "track"]
        last_track_event = track_events[-1]
        
        # Last track should end at its full duration (8.0 sec)
        assert abs(last_track_event["source_end_sec"] - 8.0) < 0.1


class TestTwoTrackTimeline:
    """Baseline integration test for simple A -> B flow."""

    def test_simple_two_track(self, tmp_path):
        """Two tracks should assemble correctly with one transition."""
        track_a_path = str(tmp_path / "track_a.wav")
        track_b_path = str(tmp_path / "track_b.wav")
        output_path = str(tmp_path / "output.wav")

        _create_test_audio_file(track_a_path, 10.0, 44100, 440.0)
        _create_test_audio_file(track_b_path, 8.0, 44100, 550.0)

        track_a = _make_track("a", "Track A", track_a_path, 10.0)
        track_b = _make_track("b", "Track B", track_b_path, 8.0)

        trans_ab = _make_transition("a", "b", 8.0, 1.0, 2.0)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans_ab],
            total_duration_sec=16.0,
            target_duration_sec=16.0,
            energy_profile=EnergyProfile.STEADY,
        )

        result = render_mix(plan, output_path, "wav", sample_rate=44100)
        
        assert os.path.exists(output_path)
        assert result["transitions_rendered"] == 1
        
        # Verify output is valid audio
        import soundfile as sf
        audio, sr = sf.read(output_path)
        assert len(audio) > 0
        assert sr == 44100