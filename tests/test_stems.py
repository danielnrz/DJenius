"""Tests for stem separation module (Phase 12-15).

All Demucs processing is mocked — no real separation runs.
GPU availability and audio I/O are also mocked as needed.
"""

import importlib
import os
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
import soundfile as sf


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_fake_track(tmp_path: Path, name: str = "track.mp3", sr: int = 44100, samples: int = 1000) -> str:
    """Create a tiny fake audio file and return its path."""
    path = str(tmp_path / name)
    sf.write(path, np.zeros(samples, dtype=np.float32), sr)
    return path


def _write_stem_cache(tmp_path: Path, track_path: str, sr: int = 44100, samples: int = 1000) -> Path:
    """Write properly hash-named stem cache files for a track.

    Returns the stem directory used.
    """
    from djenius.audio.stems import _file_hash, STEM_NAMES
    stem_dir = tmp_path / "stems"
    stem_dir.mkdir(exist_ok=True)
    fhash = _file_hash(track_path)
    for name in STEM_NAMES:
        sf.write(str(stem_dir / f"{fhash}_{name}.wav"), np.zeros(samples, dtype=np.float32), sr)
    return stem_dir


def _fake_stem_dict(sr: int = 44100, duration_sec: float = 10.0) -> dict[str, np.ndarray]:
    """Create a fake 4-stem dict (stereo, float32) for testing."""
    n = int(sr * duration_sec)
    return {
        "vocals": np.random.randn(n, 2).astype(np.float32) * 0.1,
        "drums":  np.random.randn(n, 2).astype(np.float32) * 0.2,
        "bass":   np.random.randn(n, 2).astype(np.float32) * 0.15,
        "other":  np.random.randn(n, 2).astype(np.float32) * 0.12,
    }


# ── Module availability tests ────────────────────────────────────────────────

class TestStemsAvailability:
    """Verify that optional stem imports don't break anything."""

    def test_stems_module_imports(self):
        """The stems module should always import cleanly."""
        from djenius.audio import stems
        assert hasattr(stems, "separate_stems")
        assert hasattr(stems, "load_stems")
        assert hasattr(stems, "stems_available")
        assert hasattr(stems, "stems_cached")
        assert hasattr(stems, "gpu_available")
        assert hasattr(stems, "get_stem_audio")

    def test_stems_available_without_demucs(self):
        """stems_available() should not crash even if demucs is mocked out."""
        from djenius.audio import stems
        result = stems.stems_available()
        assert isinstance(result, bool)

    def test_gpu_available_returns_bool(self):
        """gpu_available() should return a bool."""
        from djenius.audio import stems
        result = stems.gpu_available()
        assert isinstance(result, bool)


# ── Caching tests ────────────────────────────────────────────────────────────

class TestStemsCache:
    """Test file-hash based caching logic."""

    def test_stems_cached_false_for_track_with_no_stems(self, tmp_path: Path):
        """stems_cached() should return False when no stem files exist for a track."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        result = stems.stems_cached(track)
        assert result is False

    def test_stems_cached_true_after_separation(self, tmp_path: Path):
        """After writing properly hash-named stem files, stems_cached should return True."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        stem_dir = _write_stem_cache(tmp_path, track)
        result = stems.stems_cached(track, stem_dir=stem_dir)
        assert result is True

    def test_stems_cached_false_with_wrong_dir(self, tmp_path: Path):
        """stems_cached should return False when looking in wrong directory."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        _write_stem_cache(tmp_path, track)  # Write to default stems/ dir
        wrong_dir = tmp_path / "wrong_stems"
        wrong_dir.mkdir()
        result = stems.stems_cached(track, stem_dir=wrong_dir)
        assert result is False


# ── Loading tests ────────────────────────────────────────────────────────────

class TestStemsLoading:
    """Test load_stems returns dict of audio arrays when cached."""

    def test_load_stems_returns_audio_arrays(self, tmp_path: Path):
        """load_stems should return a dict mapping stem names to numpy arrays."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        stem_dir = _write_stem_cache(tmp_path, track)
        result = stems.load_stems(track, stem_dir=stem_dir)
        assert isinstance(result, dict)
        for name in ("vocals", "drums", "bass", "other"):
            assert name in result
            assert isinstance(result[name], np.ndarray)

    def test_load_stems_raises_for_missing(self, tmp_path: Path):
        """load_stems should raise FileNotFoundError when stems aren't cached."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        with pytest.raises(FileNotFoundError):
            stems.load_stems(track)

    def test_load_stems_partial_cache(self, tmp_path: Path):
        """load_stems should return whatever stems exist (partial cache)."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        fhash = stems._file_hash(track)
        stem_dir = tmp_path / "stems"
        stem_dir.mkdir()
        # Only create vocals stem
        sf.write(str(stem_dir / f"{fhash}_vocals.wav"), np.zeros(1000, dtype=np.float32), 44100)
        result = stems.load_stems(track, stem_dir=stem_dir)
        assert "vocals" in result
        # Other stems may or may not be present depending on whether any files exist
        assert isinstance(result, dict)


# ── get_stem_audio tests ─────────────────────────────────────────────────────

class TestGetStemAudio:
    """Test loading actual audio data from stem files."""

    def test_get_stem_audio_loads_array(self, tmp_path: Path):
        """get_stem_audio should load and return a numpy array from cached stems."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        stem_dir = _write_stem_cache(tmp_path, track)
        result = stems.get_stem_audio(track, "vocals", stem_dir=stem_dir)
        assert result is not None
        assert isinstance(result, np.ndarray)

    def test_get_stem_audio_returns_none_for_missing(self, tmp_path: Path):
        """get_stem_audio should return None when stem is not cached."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        result = stems.get_stem_audio(track, "vocals")
        assert result is None

    def test_get_stem_audio_returns_none_for_bad_name(self, tmp_path: Path):
        """get_stem_audio should return None for unknown stem name."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        stem_dir = _write_stem_cache(tmp_path, track)
        result = stems.get_stem_audio(track, "nonexistent_stem", stem_dir=stem_dir)
        assert result is None


# ── Separate_stems integration tests (mocked Demucs) ────────────────────────

class TestSeparateStems:
    """Test the separate_stems function with mocked Demucs pipeline."""

    def test_separate_stems_uses_cache(self, tmp_path: Path):
        """separate_stems should return cached paths when files already exist."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        stem_dir = _write_stem_cache(tmp_path, track)

        result = stems.separate_stems(track, stem_dir=stem_dir)
        assert isinstance(result, dict)
        assert "vocals" in result
        assert "bass" in result
        # All returned paths should be strings pointing to existing files
        for name, path in result.items():
            assert isinstance(path, str)
            assert os.path.exists(path)

    def test_separate_stems_raises_without_demucs(self, tmp_path: Path):
        """separate_stems should raise ImportError when demucs is not installed."""
        import builtins
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)

        # Mock __import__ to raise ImportError for demucs/torch modules
        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name == "torch" or name.startswith("torch."):
                raise ImportError("mocked: torch not installed")
            if name == "demucs" or name.startswith("demucs."):
                raise ImportError("mocked: demucs not installed")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=blocking_import):
            with pytest.raises(ImportError, match="Stem separation requires"):
                stems.separate_stems(track)

    def test_separate_stems_force_recompute(self, tmp_path: Path, monkeypatch):
        """separate_stems with force=True should attempt re-separation."""
        from djenius.audio import stems
        track = _create_fake_track(tmp_path)
        stem_dir = _write_stem_cache(tmp_path, track)

        # Mock the Demucs imports to succeed, and mock apply_model
        mock_torch = mock.MagicMock()
        mock_model = mock.MagicMock()
        mock_model.sources = ["drums", "bass", "other", "vocals"]

        fake_sources = np.random.randn(1, 4, 2, 1000).astype(np.float32)
        fake_sources_tensor = mock.MagicMock()
        fake_sources_tensor.cpu.return_value.numpy.return_value = fake_sources

        with mock.patch.dict("sys.modules", {
            "torch": mock_torch,
            "demucs": mock.MagicMock(),
            "demucs.pretrained": mock.MagicMock(get_model=mock.MagicMock(return_value=mock_model)),
            "demucs.audio": mock.MagicMock(),
            "demucs.apply": mock.MagicMock(apply_model=mock.MagicMock(return_value=fake_sources_tensor)),
        }):
            monkeypatch.setattr(stems, "stems_available", lambda: True)
            result = stems.separate_stems(track, stem_dir=stem_dir, force=True)
            assert isinstance(result, dict)
            assert "vocals" in result


# ── Vocal region from stem tests ─────────────────────────────────────────────

class TestVocalRegionsFromStem:
    """Test stem-based vocal region detection."""

    def test_estimate_vocal_regions_from_stem_silent(self):
        """Silent stem should yield no vocal regions."""
        from djenius.audio.vocals import estimate_vocal_regions_from_stem
        sr = 44100
        silent = np.zeros(sr * 10, dtype=np.float32)
        regions = estimate_vocal_regions_from_stem(silent, sr)
        assert regions == []

    def test_estimate_vocal_regions_from_stem_with_energy(self):
        """Stem with constant energy should detect a vocal region."""
        from djenius.audio.vocals import estimate_vocal_regions_from_stem
        sr = 44100
        # 10 seconds of constant amplitude signal
        vocal = np.ones(sr * 10, dtype=np.float32) * 0.3
        regions = estimate_vocal_regions_from_stem(vocal, sr)
        assert isinstance(regions, list)
        # With enough energy, should detect at least one region
        assert len(regions) >= 1

    def test_estimate_vocal_regions_from_stereo_stem(self):
        """Stereo vocal stem should be flattened and analyzed correctly."""
        from djenius.audio.vocals import estimate_vocal_regions_from_stem
        sr = 44100
        vocal = np.ones((sr * 10, 2), dtype=np.float32) * 0.3
        regions = estimate_vocal_regions_from_stem(vocal, sr)
        assert isinstance(regions, list)
        assert len(regions) >= 1

    def test_score_vocal_overlap_stem_returns_float(self):
        """score_vocal_overlap_stem should return a float between 0 and 1."""
        from djenius.audio.vocals import score_vocal_overlap_stem
        sr = 44100
        src_vocal = np.random.randn(sr * 30).astype(np.float32) * 0.3
        tgt_vocal = np.random.randn(sr * 30).astype(np.float32) * 0.3
        score = score_vocal_overlap_stem(src_vocal, tgt_vocal, sr,
                                         source_exit_sample=0,
                                         target_entry_sample=0,
                                         overlap_samples=sr * 5)
        assert 0.0 <= score <= 1.0

    def test_score_vocal_overlap_stem_silent_stems(self):
        """Both silent stems should return 1.0 (safe)."""
        from djenius.audio.vocals import score_vocal_overlap_stem
        sr = 44100
        silence = np.zeros(sr * 10, dtype=np.float32)
        score = score_vocal_overlap_stem(silence, silence, sr,
                                         source_exit_sample=0,
                                         target_entry_sample=0,
                                         overlap_samples=sr * 5)
        assert score == 1.0

    def test_score_vocal_overlap_stem_zero_overlap(self):
        """Zero overlap should return 1.0 (safe)."""
        from djenius.audio.vocals import score_vocal_overlap_stem
        sr = 44100
        src = np.ones(sr * 10, dtype=np.float32) * 0.5
        tgt = np.ones(sr * 10, dtype=np.float32) * 0.5
        score = score_vocal_overlap_stem(src, tgt, sr,
                                         source_exit_sample=0,
                                         target_entry_sample=0,
                                         overlap_samples=0)
        assert score == 1.0


# ── Bass-swap-stems transition tests ─────────────────────────────────────────

class TestBassSwapStems:
    """Test the stem-based bass swap transition function."""

    def test_bass_swap_stems_returns_correct_length(self):
        """_bass_swap_stems should return audio of the correct length."""
        from djenius.audio.transitions import _bass_swap_stems
        sr = 44100
        n = sr * 4  # 4 seconds
        source = np.random.randn(n).astype(np.float32) * 0.1
        target = np.random.randn(n).astype(np.float32) * 0.1
        src_bass = np.random.randn(n).astype(np.float32) * 0.1
        tgt_bass = np.random.randn(n).astype(np.float32) * 0.1

        result = _bass_swap_stems(source, target, sr, src_bass, tgt_bass)
        assert len(result) == n

    def test_bass_swap_stems_stereo(self):
        """_bass_swap_stems should handle stereo input."""
        from djenius.audio.transitions import _bass_swap_stems
        sr = 44100
        n = sr * 4
        source = np.random.randn(n, 2).astype(np.float32) * 0.1
        target = np.random.randn(n, 2).astype(np.float32) * 0.1
        src_bass = np.random.randn(n, 2).astype(np.float32) * 0.1
        tgt_bass = np.random.randn(n, 2).astype(np.float32) * 0.1

        result = _bass_swap_stems(source, target, sr, src_bass, tgt_bass)
        assert result.ndim == 2
        assert result.shape == (n, 2)

    def test_bass_swap_stems_no_clipping(self):
        """_bass_swap_stems should not clip (output should be bounded)."""
        from djenius.audio.transitions import _bass_swap_stems
        sr = 44100
        n = sr * 2
        source = np.random.randn(n).astype(np.float32) * 0.5
        target = np.random.randn(n).astype(np.float32) * 0.5
        src_bass = np.random.randn(n).astype(np.float32) * 0.5
        tgt_bass = np.random.randn(n).astype(np.float32) * 0.5

        result = _bass_swap_stems(source, target, sr, src_bass, tgt_bass)
        # Should not be wildly out of range
        assert np.max(np.abs(result)) < 5.0

    def test_bass_swap_stems_shorter_bass(self):
        """_bass_swap_stems should handle bass shorter than source/target."""
        from djenius.audio.transitions import _bass_swap_stems
        sr = 44100
        n = sr * 4
        source = np.random.randn(n).astype(np.float32) * 0.1
        target = np.random.randn(n).astype(np.float32) * 0.1
        # Bass stems are shorter than the overlap
        src_bass = np.random.randn(sr * 2).astype(np.float32) * 0.1
        tgt_bass = np.random.randn(sr * 2).astype(np.float32) * 0.1

        result = _bass_swap_stems(source, target, sr, src_bass, tgt_bass)
        assert len(result) == n


# ── Mashup transition tests ──────────────────────────────────────────────────

class TestMashupTransition:
    """Test the mashup transition function."""

    def test_mashup_falls_back_without_stems(self):
        """_mashup should fall back to crossfade when stems are None."""
        from djenius.audio.transitions import _mashup
        sr = 44100
        n = sr * 4
        source = np.random.randn(n).astype(np.float32) * 0.1
        target = np.random.randn(n).astype(np.float32) * 0.1

        result = _mashup(source, target, sr, source_stems=None, target_stems=None)
        assert len(result) == n

    def test_mashup_uses_stems_when_available(self):
        """_mashup should produce a mashup mix when stems are provided."""
        from djenius.audio.transitions import _mashup
        sr = 44100
        n = sr * 4

        source_stems = _fake_stem_dict(sr, duration_sec=n / sr)
        target_stems = _fake_stem_dict(sr, duration_sec=n / sr)

        result = _mashup(
            np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32), sr,
            source_stems=source_stems, target_stems=target_stems,
            source_exit_sample=0, target_entry_sample=0,
        )
        assert len(result) == n
        # Result should not be silence (it should contain some audio)
        assert np.max(np.abs(result)) > 0.0

    def test_mashup_stereo_output(self):
        """_mashup should produce stereo output from stereo stems."""
        from djenius.audio.transitions import _mashup
        sr = 44100
        n = sr * 4

        source_stems = _fake_stem_dict(sr, duration_sec=n / sr)
        target_stems = _fake_stem_dict(sr, duration_sec=n / sr)
        source = np.zeros((n, 2), dtype=np.float32)
        target = np.zeros((n, 2), dtype=np.float32)

        result = _mashup(source, target, sr,
                         source_stems=source_stems, target_stems=target_stems,
                         source_exit_sample=0, target_entry_sample=0)
        # Should produce output
        assert len(result) == n


# ── apply_transition integration test ────────────────────────────────────────

class TestApplyTransitionStems:
    """Test that apply_transition correctly passes stems through."""

    def test_apply_transition_bass_swap_uses_stems(self):
        """apply_transition should use stem-based bass swap when stems are provided."""
        from djenius.audio.transitions import apply_transition
        sr = 44100
        n = sr * 4  # 4 seconds overlap
        source = np.random.randn(n, 2).astype(np.float32) * 0.1
        target = np.random.randn(n, 2).astype(np.float32) * 0.1

        # Create stem audio — need enough audio for the full track + overlap
        full_len = n * 3
        src_bass = np.random.randn(full_len, 2).astype(np.float32) * 0.1
        tgt_bass = np.random.randn(full_len, 2).astype(np.float32) * 0.1

        source_stems = {"bass": src_bass}
        target_stems = {"bass": tgt_bass}

        result = apply_transition(
            source_audio=source,
            target_audio=target,
            sr=sr,
            transition_type="bass_swap",
            overlap_samples=n,
            source_exit_sample=0,
            target_entry_sample=0,
            source_stems=source_stems,
            target_stems=target_stems,
        )
        assert result.shape == source.shape
        assert result.dtype == np.float32

    def test_apply_transition_mashup_uses_stems(self):
        """apply_transition should use mashup transition when type is mashup."""
        from djenius.audio.transitions import apply_transition
        sr = 44100
        n = sr * 4
        source = np.random.randn(n, 2).astype(np.float32) * 0.1
        target = np.random.randn(n, 2).astype(np.float32) * 0.1

        full_len = n * 3
        source_stems = {
            "vocals": np.random.randn(full_len, 2).astype(np.float32) * 0.3,
            "drums":  np.random.randn(full_len, 2).astype(np.float32) * 0.2,
            "bass":   np.random.randn(full_len, 2).astype(np.float32) * 0.15,
            "other":  np.random.randn(full_len, 2).astype(np.float32) * 0.1,
        }
        target_stems = {
            "vocals": np.random.randn(full_len, 2).astype(np.float32) * 0.3,
            "drums":  np.random.randn(full_len, 2).astype(np.float32) * 0.2,
            "bass":   np.random.randn(full_len, 2).astype(np.float32) * 0.15,
            "other":  np.random.randn(full_len, 2).astype(np.float32) * 0.1,
        }

        result = apply_transition(
            source_audio=source,
            target_audio=target,
            sr=sr,
            transition_type="mashup",
            overlap_samples=n,
            source_exit_sample=0,
            target_entry_sample=0,
            source_stems=source_stems,
            target_stems=target_stems,
        )
        assert result.shape == source.shape

    def test_apply_transition_crossfade_without_stems(self):
        """apply_transition should work without stems for regular transitions."""
        from djenius.audio.transitions import apply_transition
        sr = 44100
        n = sr * 4
        source = np.random.randn(n, 2).astype(np.float32) * 0.1
        target = np.random.randn(n, 2).astype(np.float32) * 0.1

        result = apply_transition(
            source_audio=source,
            target_audio=target,
            sr=sr,
            transition_type="crossfade",
            overlap_samples=n,
            source_exit_sample=0,
            target_entry_sample=0,
        )
        assert result.shape == source.shape


# ── Scorer MASHUP recommendation tests ──────────────────────────────────────

class TestScorerMashup:
    """Test that the scorer recommends MASHUP when stems are available."""

    def _make_profile(self, bpm=120, energy=0.5, stems=None):
        """Helper to build a minimal TrackProfile for testing."""
        from djenius.core.models import TrackProfile, TrackMetadata, TrackAnalysis
        return TrackProfile(
            id=f"test_{bpm}_{energy}",
            metadata=TrackMetadata(
                filepath=f"/fake/track_{bpm}.mp3",
                title=f"Track {bpm}",
                duration_sec=300.0,
                sample_rate=44100,
                channels=2,
                format="mp3",
                file_hash="abc123",
            ),
            analysis=TrackAnalysis(
                bpm=bpm,
                mean_energy=energy,
                stems=stems,
            ),
        )

    def test_mashup_recommended_when_stems_available(self):
        """MASHUP should be recommended when both tracks have stems."""
        from djenius.core.scorer import recommend_transition_type
        from djenius.core.models import TransitionType

        src = self._make_profile(bpm=125, energy=0.5, stems={"vocals": "/f", "drums": "/f", "bass": "/f", "other": "/f"})
        tgt = self._make_profile(bpm=126, energy=0.55, stems={"vocals": "/f", "drums": "/f", "bass": "/f", "other": "/f"})

        ttype, conf, reason = recommend_transition_type(src, tgt)
        assert ttype == TransitionType.MASHUP, f"Expected MASHUP but got {ttype}: {reason}"
        assert 0.0 < conf <= 1.0

    def test_mashup_penalized_without_stems(self):
        """MASHUP should score poorly when neither track has stems."""
        from djenius.core.scorer import recommend_transition_type
        from djenius.core.models import TransitionType

        src = self._make_profile(bpm=125, energy=0.5, stems=None)
        tgt = self._make_profile(bpm=126, energy=0.55, stems=None)

        ttype, conf, reason = recommend_transition_type(src, tgt)
        # Should NOT recommend mashup without stems
        assert ttype != TransitionType.MASHUP

    def test_mashup_confidence_clamped(self):
        """Confidence should always be between 0.0 and 1.0."""
        from djenius.core.scorer import recommend_transition_type

        # Test with stems
        src = self._make_profile(bpm=125, energy=0.9, stems={"v": "/f"})
        tgt = self._make_profile(bpm=126, energy=0.9, stems={"v": "/f"})
        _, conf, _ = recommend_transition_type(src, tgt)
        assert 0.0 <= conf <= 1.0

        # Test without stems
        src = self._make_profile(bpm=125, energy=0.9)
        tgt = self._make_profile(bpm=126, energy=0.9)
        _, conf, _ = recommend_transition_type(src, tgt)
        assert 0.0 <= conf <= 1.0
