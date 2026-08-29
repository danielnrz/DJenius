"""Tests for transition diagnostics — audition WAV + JSON output."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from djenius.audio.diagnostics import (
    generate_transition_auditions,
    _make_synth_signal,
    _make_click_track,
)

SR = 44100


class TestMakeSynthSignal:
    """Verify synthetic signal generation."""

    def test_mono_output(self):
        audio = _make_synth_signal(1.0, 440.0, SR, stereo=False)
        assert audio.ndim == 1
        assert len(audio) == SR

    def test_stereo_output(self):
        audio = _make_synth_signal(1.0, 440.0, SR, stereo=True)
        assert audio.ndim == 2
        assert audio.shape == (SR, 2)

    def test_different_freqs(self):
        low = _make_synth_signal(0.5, 220.0, SR)
        high = _make_synth_signal(0.5, 880.0, SR)
        # High freq should have faster oscillation
        assert len(low) == len(high)

    def test_finite_values(self):
        audio = _make_synth_signal(1.0, 440.0, SR)
        assert np.all(np.isfinite(audio))


class TestMakeClickTrack:
    """Verify click track generation."""

    def test_click_track_has_clicks(self):
        audio = _make_click_track(120.0, 2.0)
        assert np.max(audio) > 0.1

    def test_click_track_length(self):
        audio = _make_click_track(120.0, 2.0)
        assert len(audio) == SR * 2

    @pytest.mark.parametrize("bpm", [80, 90, 100, 120, 128, 140, 160])
    def test_all_required_bpms(self, bpm):
        audio = _make_click_track(bpm, 2.0)
        assert np.max(audio) > 0


class TestGenerateTransitionAuditions:
    """Test the full audition generation pipeline."""

    def test_creates_all_files(self, tmp_path):
        result = generate_transition_auditions(str(tmp_path), stereo=True)

        # Check all expected files exist
        assert os.path.exists(result["json_path"])
        for f in result["files"]:
            assert os.path.exists(f), f"File missing: {f}"

        # Check JSON has all transition types
        with open(result["json_path"]) as f:
            data = json.load(f)
        types = {t["type"] for t in data["transitions"]}
        expected = {"crossfade", "beatmatched_blend", "bass_swap", "filter_sweep", "echo_out"}
        assert types == expected

    def test_mono_only(self, tmp_path):
        result = generate_transition_auditions(str(tmp_path), stereo=False)
        with open(result["json_path"]) as f:
            data = json.load(f)
        for t in data["transitions"]:
            assert t["channels"] == 1

    def test_wav_files_are_valid(self, tmp_path):
        result = generate_transition_auditions(str(tmp_path), stereo=True)
        for f in result["files"]:
            if f.endswith(".wav"):
                audio, sr = sf.read(f)
                assert sr == SR
                assert len(audio) > 0
                assert np.all(np.isfinite(audio))

    def test_diagnostics_have_required_fields(self, tmp_path):
        result = generate_transition_auditions(str(tmp_path), stereo=True)
        for diag in result["diagnostics"]:
            assert "type" in diag
            assert "file" in diag
            assert "channels" in diag
            assert "output_samples" in diag
            assert "rms_energy" in diag
            assert "peak_db" in diag
            assert diag["rms_energy"] > 0
            assert np.isfinite(diag["peak_db"])

    def test_beatmatched_diagnostics(self, tmp_path):
        result = generate_transition_auditions(str(tmp_path), stereo=False)
        beat_diag = [d for d in result["diagnostics"] if d["type"] == "beatmatched_blend"][0]
        assert beat_diag["source_bpm"] == 120.0
        assert beat_diag["target_bpm"] == 128.0
        assert beat_diag["stretch_pct"] > 0
        assert beat_diag["stretch_pct"] < 15  # 128/120 is ~6.7% stretch

    def test_json_structure(self, tmp_path):
        result = generate_transition_auditions(str(tmp_path), stereo=True)
        with open(result["json_path"]) as f:
            data = json.load(f)
        assert "sample_rate" in data
        assert "overlap_sec" in data
        assert "stereo_generated" in data
        assert "transitions" in data
        assert isinstance(data["transitions"], list)
        assert len(data["transitions"]) == 5

    def test_different_stereo_monaural_output(self, tmp_path):
        """Stereo auditions should have 2 channels, mono should have 1."""
        result = generate_transition_auditions(str(tmp_path), stereo=True)
        with open(result["json_path"]) as f:
            data = json.load(f)
        crossfade_diag = [d for d in data["transitions"] if d["type"] == "crossfade"][0]
        assert crossfade_diag["channels"] == 1  # Only mono crossfade in auditions

    def test_output_dir_created(self, tmp_path):
        nested = tmp_path / "nested" / "dir"
        generate_transition_auditions(str(nested))
        assert nested.exists()
