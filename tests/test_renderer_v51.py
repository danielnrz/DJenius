"""Tests for the renderer V5.1 fixes: timeline assembly, audio loading, diagnostics."""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
import soundfile as sf

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

    def test_render_mix_aborts_on_unreadable_track(self, tmp_path):
        """render_mix must abort (DecodeError) when a track cannot be loaded,
        never produce a silent placeholder for that track."""
        good_path = str(tmp_path / "good.wav")
        bad_path = str(tmp_path / "bad.wav")
        _create_test_audio_file(good_path, 5.0, 44100, 440.0)
        with open(bad_path, "w") as f:
            f.write("not audio")

        good = _make_track("g", "Good", good_path, 5.0)
        bad = _make_track("b", "Bad", bad_path, 3.0)

        plan = SetPlan(
            tracks=[good, bad],
            transitions=[],
            total_duration_sec=8.0,
            target_duration_sec=8.0,
            energy_profile=EnergyProfile.STEADY,
        )

        with pytest.raises(DecodeError):
            render_mix(plan, str(tmp_path / "out.wav"), "wav", sample_rate=44100)

        # The output file must NOT exist — render aborted before writing
        assert not (tmp_path / "out.wav").exists()


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


# ============================================================================
# Sample-Exact Regression Tests (Tests A-J)
# SR=10000, constant-value arrays, mocked _load_audio.
# ============================================================================

SR = 10000  # 10 kHz for easy sample math


def _const_audio(duration_sec: float, value: float = 1.0) -> np.ndarray:
    """Return a mono float32 array of constant value."""
    n = int(duration_sec * SR)
    return np.full(n, value, dtype=np.float32)


def _make_mock_load(audio_map: dict[str, np.ndarray]):
    """Return a mock for djenius.audio.renderer._load_audio.

    audio_map: {filepath: mono_array}  — each array is returned as-is.
    """
    def _mock_load(filepath, target_sr=SR):
        if filepath not in audio_map:
            raise FileNotFoundError(f"No mock audio for {filepath}")
        return audio_map[filepath], SR
    return _mock_load


class TestSampleExactA:
    """Test A: First track solo ends exactly at source_exit_sample."""

    def test_first_track_solo_length(self, tmp_path):
        """Mix[0 : SET_0] must be exactly the first track's audio."""
        dur_a = 1.0  # 10000 samples
        dur_b = 1.0
        set_0 = 0.6  # source_exit_time -> 6000 samples
        tet_1 = 0.0
        od = 0.3

        a_audio = _const_audio(dur_a, 1.0)
        b_audio = _const_audio(dur_b, 2.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        trans = _make_transition("a", "b", set_0, tet_1, od)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans],
            total_duration_sec=dur_a + dur_b,
            target_duration_sec=dur_a + dur_b,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({"/mock/a.wav": a_audio, "/mock/b.wav": b_audio})

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        out, _ = sf.read(output_path)
        expected_set0 = int(set_0 * SR)  # 6000

        # First 6000 samples should be all Track A (value 1.0)
        # (post-mastering may scale, so check relative: all equal)
        solo_region = out[:expected_set0]
        if np.max(np.abs(solo_region)) > 1e-6:
            assert np.allclose(solo_region[:, 0], solo_region[0, 0], atol=1e-3), \
                "First track solo region should be constant-valued"
        # The diagnostics should confirm the boundary
        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)
        track_events = [e for e in diag["events"] if e["type"] == "track"]
        assert len(track_events) >= 1
        assert track_events[0]["source_start_sample"] == 0
        assert track_events[0]["source_end_sample"] == expected_set0


class TestSampleExactB:
    """Test B: Transition output length equals overlap_samples (clamped)."""

    def test_transition_length_matches_overlap(self, tmp_path):
        """Transition event in diagnostics should span overlap_samples."""
        dur_a = 1.0
        dur_b = 1.0
        set_0 = 0.7
        tet_1 = 0.0
        od = 0.2

        a_audio = _const_audio(dur_a, 1.0)
        b_audio = _const_audio(dur_b, 2.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        trans = _make_transition("a", "b", set_0, tet_1, od)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans],
            total_duration_sec=dur_a + dur_b,
            target_duration_sec=dur_a + dur_b,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({"/mock/a.wav": a_audio, "/mock/b.wav": b_audio})

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        trans_events = [e for e in diag["events"] if e["type"] == "transition"]
        assert len(trans_events) == 1
        t = trans_events[0]
        expected_overlap_samples = int(od * SR)
        actual_trans_samples = t["mix_end_sample"] - t["mix_start_sample"]
        assert actual_trans_samples == expected_overlap_samples, (
            f"Transition should be {expected_overlap_samples} samples, "
            f"got {actual_trans_samples}"
        )


class TestSampleExactC:
    """Test C: Source transition interval is source[SET_0 : SET_0+OD]."""

    def test_source_interval_in_transition(self, tmp_path):
        """Transition must consume source audio from SET_0 for OD samples."""
        # Integer-first arithmetic to avoid float rounding
        set_0_s = 6000    # SET_0 in samples
        od_s = 2000       # OD in samples
        set_0 = set_0_s / SR
        od = od_s / SR
        dur_a = 1.0
        dur_b = 1.0
        tet_1 = 0.0

        # Source audio: 0.5 before SET_0, 1.0 from SET_0 onward.
        # This lets us verify the transition uses the right part of source.
        a_n = int(dur_a * SR)
        a_audio = np.full((a_n, 2), 0.5, dtype=np.float32)
        a_audio[set_0_s:] = 1.0
        b_audio = _const_audio(dur_b, 2.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        trans = _make_transition("a", "b", set_0, tet_1, od)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans],
            total_duration_sec=dur_a + dur_b,
            target_duration_sec=dur_a + dur_b,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({"/mock/a.wav": a_audio, "/mock/b.wav": b_audio})

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        # The transition event must start at SET_0 in mix space
        trans_events = [e for e in diag["events"] if e["type"] == "transition"]
        assert len(trans_events) == 1
        assert trans_events[0]["mix_start_sample"] == set_0_s, (
            f"Transition should start at mix sample {set_0_s}, "
            f"got {trans_events[0]['mix_start_sample']}"
        )
        assert trans_events[0]["mix_end_sample"] == set_0_s + od_s, (
            f"Transition should end at mix sample {set_0_s + od_s}, "
            f"got {trans_events[0]['mix_end_sample']}"
        )

        out, _ = sf.read(output_path)

        # The transition region is a crossfade of source[SET_0:SET_0+OD]
        # and target[0:OD]. Source has value 1.0 in that range, target has
        # value 2.0. So the crossfade should monotonically increase from
        # ~1.0 toward ~2.0.
        trans_region = out[set_0_s:set_0_s + od_s]
        assert len(trans_region) > 2, (
            f"Transition region should have >2 samples, got {len(trans_region)}"
        )
        assert np.max(np.abs(trans_region)) > 1e-6, (
            "Transition region is silent — crossfade produced no audio"
        )
        left_ch = trans_region[:, 0]
        diffs = np.diff(left_ch)
        assert np.sum(diffs > 0) > np.sum(diffs < 0), (
            "Transition from source(1.0) to target(2.0) "
            "should show overall increasing trend"
        )


class TestSampleExactD:
    """Test D: Target interval is target[TET_1 : TET_1+OD]."""

    def test_target_interval_in_transition(self, tmp_path):
        """Transition must consume target audio starting at TET_1."""
        # Integer-first arithmetic
        set_0_s = 5000    # SET_0
        tet_1_s = 3000    # TET_1 (3000 samples into target)
        od_s = 2000       # OD
        set_0 = set_0_s / SR
        tet_1 = tet_1_s / SR
        od = od_s / SR
        dur_a = 1.0
        dur_b = 1.0

        a_audio = _const_audio(dur_a, 1.0)
        # Target: zeros for first tet_1_s samples, then 2.0
        b_n = int(dur_b * SR)
        b_audio = np.zeros(b_n, dtype=np.float32)
        b_audio[tet_1_s:] = 2.0

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        trans = _make_transition("a", "b", set_0, tet_1, od)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans],
            total_duration_sec=dur_a + dur_b,
            target_duration_sec=dur_a + dur_b,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({"/mock/a.wav": a_audio, "/mock/b.wav": b_audio})

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        # Verify transition event position
        trans_events = [e for e in diag["events"] if e["type"] == "transition"]
        assert len(trans_events) == 1
        assert trans_events[0]["mix_start_sample"] == set_0_s

        # The transition crossfades source[SET_0:SET_0+OD] with target[TET_1:TET_1+OD].
        # Target is 0.0 for first 3000 samples, then 2.0. So the transition
        # region starts with target=0.0 and ends with target=2.0.
        # The mix audio at the transition start should be dominated by
        # source (1.0, fade_out~1) + target (0.0, fade_in~0) ≈ 1.0.
        # At transition end: source (1.0, fade_out~0) + target (2.0, fade_in~1) ≈ 2.0.
        out, _ = sf.read(output_path)
        trans_region = out[set_0_s:set_0_s + od_s]
        assert len(trans_region) > 2, (
            f"Transition region should have >2 samples, got {len(trans_region)}"
        )
        assert np.max(np.abs(trans_region)) > 1e-6, (
            "Transition region is silent — crossfade produced no audio"
        )
        left_ch = trans_region[:, 0]
        diffs = np.diff(left_ch)
        assert np.sum(diffs > 0) > np.sum(diffs < 0), (
            "Crossfade from source(1.0) to target(0.0→2.0) "
            "should show overall increasing trend"
        )

        # Also verify: the remaining target solo starts at TET_1 + OD
        # in source space (integer-first: tet_1_s + od_s)
        track_events = [e for e in diag["events"] if e["type"] == "track"]
        b_events = [e for e in track_events if e["track_id"] == "b"]
        assert len(b_events) >= 1, "Track B should have at least one track event"
        b_event = b_events[-1]  # remaining solo
        expected_source_start = tet_1_s + od_s
        assert b_event["source_start_sample"] == expected_source_start, (
            f"Track B solo should start at source sample {expected_source_start}, "
            f"got {b_event['source_start_sample']}"
        )


class TestSampleExactE:
    """Test E: After transition, target solo resumes at TET_1 + OD."""

    def test_target_solo_resume_position(self, tmp_path):
        """Track B solo must begin at TET_1 + overlap_duration in source space."""
        # Integer-first arithmetic
        set_0_s = 5000    # SET_0
        tet_1_s = 2000    # TET_1 (2000 samples)
        od_s = 3000       # OD (3000 samples)
        set_0 = set_0_s / SR
        tet_1 = tet_1_s / SR
        od = od_s / SR
        dur_a = 1.0
        dur_b = 1.0

        a_audio = _const_audio(dur_a, 1.0)
        # Distinct value ramp to verify exact sample position
        b_n = int(dur_b * SR)
        b_audio = np.linspace(0.0, 10.0, b_n, dtype=np.float32)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        trans = _make_transition("a", "b", set_0, tet_1, od)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans],
            total_duration_sec=dur_a + dur_b,
            target_duration_sec=dur_a + dur_b,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({"/mock/a.wav": a_audio, "/mock/b.wav": b_audio})

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        track_events = [e for e in diag["events"] if e["type"] == "track"]
        b_events = [e for e in track_events if e["track_id"] == "b"]
        assert len(b_events) >= 1
        b_event = b_events[-1]

        # Source start should be at TET_1 + OD = tet_1_s + od_s
        expected_src_start = tet_1_s + od_s
        assert b_event["source_start_sample"] == expected_src_start

        # Verify mix position: after first track solo + transition
        # SET_0 + OD in mix space = set_0_s + od_s
        expected_mix_start = set_0_s + od_s
        assert b_event["mix_start_sample"] == expected_mix_start


class TestSampleExactF:
    """Test F: Final track plays to its physical end."""

    def test_final_track_full_length(self, tmp_path):
        """Last track must consume all remaining source audio to the end."""
        dur_a = 0.8
        dur_b = 1.0  # 10000 samples
        set_0 = 0.5
        tet_1 = 0.0
        od = 0.3

        a_audio = _const_audio(dur_a, 1.0)
        b_audio = _const_audio(dur_b, 2.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        trans = _make_transition("a", "b", set_0, tet_1, od)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans],
            total_duration_sec=dur_a + dur_b,
            target_duration_sec=dur_a + dur_b,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({"/mock/a.wav": a_audio, "/mock/b.wav": b_audio})

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        track_events = [e for e in diag["events"] if e["type"] == "track"]
        last_event = track_events[-1]

        # Final track's source_end should equal full track duration
        expected_end = int(dur_b * SR)
        assert last_event["source_end_sample"] == expected_end, (
            f"Final track should end at sample {expected_end}, "
            f"got {last_event['source_end_sample']}"
        )


class TestSampleExactG:
    """Test G: Forward cursor never backtracks."""

    def test_monotonic_mix_positions(self, tmp_path):
        """Every event's mix_start >= previous event's mix_end."""
        dur_a = 0.5
        dur_b = 0.5
        dur_c = 0.5
        set_0 = 0.3
        tet_1 = 0.0
        od_0 = 0.1
        set_1 = 0.35
        tet_2 = 0.0
        od_1 = 0.1

        a_audio = _const_audio(dur_a, 1.0)
        b_audio = _const_audio(dur_b, 2.0)
        c_audio = _const_audio(dur_c, 3.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        track_c = _make_track("c", "C", "/mock/c.wav", dur_c)
        trans_0 = _make_transition("a", "b", set_0, tet_1, od_0)
        trans_1 = _make_transition("b", "c", set_1, tet_2, od_1)

        plan = SetPlan(
            tracks=[track_a, track_b, track_c],
            transitions=[trans_0, trans_1],
            total_duration_sec=dur_a + dur_b + dur_c,
            target_duration_sec=dur_a + dur_b + dur_c,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({
            "/mock/a.wav": a_audio,
            "/mock/b.wav": b_audio,
            "/mock/c.wav": c_audio,
        })

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        events = diag["events"]
        assert len(events) >= 3
        for i in range(1, len(events)):
            assert events[i]["mix_start_sample"] >= events[i - 1]["mix_end_sample"], (
                f"Event {i} mix_start ({events[i]['mix_start_sample']}) < "
                f"Event {i-1} mix_end ({events[i-1]['mix_end_sample']}): "
                "cursor went backwards or events overlap"
            )


class TestSampleExactH:
    """Test H: Bounds clamping when transition extends past track end."""

    def test_clamp_when_overlap_exceeds_remaining(self, tmp_path):
        """If OD pushes past track end, renderer must clamp, not crash."""
        dur_a = 0.5
        dur_b = 0.4  # Short track
        set_0 = 0.4  # Exit at 0.4s
        tet_1 = 0.0
        od = 0.3  # But target is only 0.4s, transition wants 0.3s from start

        a_audio = _const_audio(dur_a, 1.0)
        b_audio = _const_audio(dur_b, 2.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        trans = _make_transition("a", "b", set_0, tet_1, od)

        plan = SetPlan(
            tracks=[track_a, track_b],
            transitions=[trans],
            total_duration_sec=dur_a + dur_b,
            target_duration_sec=dur_a + dur_b,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({"/mock/a.wav": a_audio, "/mock/b.wav": b_audio})

        # Should not raise
        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        assert os.path.exists(output_path)
        out, _ = sf.read(output_path)
        assert len(out) > 0

        # Diagnostics should show bounded values
        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)
        for event in diag["events"]:
            if "source_end_sample" in event:
                track_id = event["track_id"]
                dur = dur_a if track_id == "a" else dur_b
                assert event["source_end_sample"] <= int(dur * SR) + 1


class TestSampleExactI:
    """Test I: Full three-track pipeline with correct interleaving."""

    def test_three_track_interleaving(self, tmp_path):
        """T0 solo, trans(T0,T1), T1 solo, trans(T1,T2), T2 to end."""
        dur_a = 1.0
        dur_b = 1.0
        dur_c = 1.0
        set_0 = 0.6
        tet_1 = 0.0
        od_0 = 0.2
        set_1 = 0.7
        tet_2 = 0.0
        od_1 = 0.15

        a_audio = _const_audio(dur_a, 1.0)
        b_audio = _const_audio(dur_b, 2.0)
        c_audio = _const_audio(dur_c, 3.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        track_c = _make_track("c", "C", "/mock/c.wav", dur_c)
        trans_0 = _make_transition("a", "b", set_0, tet_1, od_0)
        trans_1 = _make_transition("b", "c", set_1, tet_2, od_1)

        plan = SetPlan(
            tracks=[track_a, track_b, track_c],
            transitions=[trans_0, trans_1],
            total_duration_sec=dur_a + dur_b + dur_c,
            target_duration_sec=dur_a + dur_b + dur_c,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({
            "/mock/a.wav": a_audio,
            "/mock/b.wav": b_audio,
            "/mock/c.wav": c_audio,
        })

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        events = diag["events"]
        # Expected event types in order:
        # track(A), transition(A->B), track(B), transition(B->C), track(C)
        types = [e["type"] for e in events]
        assert types == ["track", "transition", "track", "transition", "track"], (
            f"Expected [track, transition, track, transition, track], got {types}"
        )

        # Verify track IDs
        assert events[0]["track_id"] == "a"
        assert events[1]["from_track_id"] == "a"
        assert events[1]["to_track_id"] == "b"
        assert events[2]["track_id"] == "b"
        assert events[3]["from_track_id"] == "b"
        assert events[3]["to_track_id"] == "c"
        assert events[4]["track_id"] == "c"


class TestSampleExactJ:
    """Test J: Mix total length matches expected timeline duration."""

    def test_mix_length_matches_expectation(self, tmp_path):
        """Total mix = SET_0 + OD_0 + T1_solo + OD_1 + T2_remaining (sample-exact)."""
        # Define everything as integer sample counts first, derive seconds.
        set0_s = 6000    # SET_0 in samples
        od0_s = 2000     # OD_0
        set1_s = 7000    # SET_1
        tet1_s = 0       # TET_1
        tet2_s = 0       # TET_2
        od1_s = 1500     # OD_1
        dur_c_s = 10000  # track C duration in samples

        # Derive seconds for model construction
        set_0 = set0_s / SR
        od_0 = od0_s / SR
        set_1 = set1_s / SR
        tet_1 = tet1_s / SR
        od_1 = od1_s / SR
        tet_2 = tet2_s / SR
        dur_c = dur_c_s / SR
        dur_a = 1.0
        dur_b = 1.0

        a_audio = _const_audio(dur_a, 1.0)
        b_audio = _const_audio(dur_b, 2.0)
        c_audio = _const_audio(dur_c, 3.0)

        track_a = _make_track("a", "A", "/mock/a.wav", dur_a)
        track_b = _make_track("b", "B", "/mock/b.wav", dur_b)
        track_c = _make_track("c", "C", "/mock/c.wav", dur_c)
        trans_0 = _make_transition("a", "b", set_0, tet_1, od_0)
        trans_1 = _make_transition("b", "c", set_1, tet_2, od_1)

        plan = SetPlan(
            tracks=[track_a, track_b, track_c],
            transitions=[trans_0, trans_1],
            total_duration_sec=dur_a + dur_b + dur_c,
            target_duration_sec=dur_a + dur_b + dur_c,
            energy_profile=EnergyProfile.STEADY,
        )

        output_path = str(tmp_path / "out.wav")
        mock_load = _make_mock_load({
            "/mock/a.wav": a_audio,
            "/mock/b.wav": b_audio,
            "/mock/c.wav": c_audio,
        })

        with mock.patch("djenius.audio.renderer._load_audio", side_effect=mock_load):
            result = render_mix(plan, output_path, "wav", sample_rate=SR)

        with open(result["timeline_diagnostics_path"]) as f:
            diag = json.load(f)

        events = diag["events"]
        last_event = events[-1]
        mix_end = last_event["mix_end_sample"]

        # Compute expected total from independent integer boundaries
        t1_solo = set1_s - (tet1_s + od0_s)
        t2_remaining = dur_c_s - (tet2_s + od1_s)
        expected_total = set0_s + od0_s + t1_solo + od1_s + t2_remaining

        assert mix_end == expected_total, (
            f"Mix should end at {expected_total} samples, got {mix_end}. "
            f"Breakdown: SET_0={set0_s} + OD_0={od0_s} + "
            f"T1_solo={t1_solo} + OD_1={od1_s} + T2_rem={t2_remaining}"
        )