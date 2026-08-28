"""Tests for core data models: serialization and deserialization."""

from __future__ import annotations

import json
import pytest

from djenius.core.models import (
    TrackMetadata,
    TrackAnalysis,
    TrackProfile,
    CompatibilityScore,
    TransitionPlan,
    SetPlan,
    TransitionType,
    EnergyProfile,
)


class TestTrackMetadata:
    def test_defaults(self):
        m = TrackMetadata(filepath="/tmp/test.mp3")
        assert m.filepath == "/tmp/test.mp3"
        assert m.title == ""
        assert m.sample_rate == 44100
        assert m.channels == 2

    def test_roundtrip_via_dict(self):
        m = TrackMetadata(
            filepath="/tmp/test.wav",
            title="My Track",
            artist="Artist",
            duration_sec=180.5,
            format="WAV",
        )
        d = m.__dict__
        m2 = TrackMetadata(**d)
        assert m2.title == "My Track"
        assert m2.duration_sec == 180.5


class TestTrackAnalysis:
    def test_defaults(self):
        a = TrackAnalysis()
        assert a.bpm == 0.0
        assert a.beat_times == []
        assert a.phrase_boundaries == []

    def test_to_dict(self):
        a = TrackAnalysis(bpm=128.0, key="C Major", camelot="8B")
        d = a.to_dict()
        assert d["bpm"] == 128.0
        assert d["key"] == "C Major"
        assert d["camelot"] == "8B"

    def test_from_dict(self):
        d = {"bpm": 128.0, "key": "C Minor", "camelot": "5A", "beat_times": [0.5, 1.0]}
        a = TrackAnalysis.from_dict(d)
        assert a.bpm == 128.0
        assert a.camelot == "5A"
        assert a.beat_times == [0.5, 1.0]

    def test_from_dict_ignores_unknown_keys(self):
        d = {"bpm": 100.0, "unknown_field": "xyz", "another": 42}
        a = TrackAnalysis.from_dict(d)
        assert a.bpm == 100.0
        assert not hasattr(a, "unknown_field")

    def test_large_array_downsampled(self):
        a = TrackAnalysis(beat_times=[float(i) for i in range(2000)])
        d = a.to_dict()
        # Should be downsampled to ~200 entries (step = len // 200)
        assert len(d["beat_times"]) <= 201

    def test_small_array_not_downsampled(self):
        a = TrackAnalysis(beat_times=[0.0, 0.5, 1.0])
        d = a.to_dict()
        assert len(d["beat_times"]) == 3


class TestTrackProfile:
    def test_properties(self, synthetic_track_profile):
        p = synthetic_track_profile
        assert p.bpm == 120.0
        assert p.camelot == "8B"
        assert p.title == "Synthetic A"
        assert p.mean_energy == 0.5
        assert p.duration_sec == 3.0

    def test_title_fallback_to_stem(self, tmp_wav, sine_wave):
        audio = sine_wave(freq=440.0, duration=1.0)
        path = tmp_wav(audio, name="my_song.wav")
        m = TrackMetadata(filepath=str(path))
        a = TrackAnalysis()
        p = TrackProfile(metadata=m, analysis=a)
        assert p.title == "my_song"


class TestTransitionPlan:
    def test_to_dict_and_back(self):
        cs = CompatibilityScore(
            source_id="a", target_id="b",
            tempo_score=0.9, key_score=0.8,
            overall_score=0.85,
        )
        tp = TransitionPlan(
            source_track_id="a",
            target_track_id="b",
            transition_type=TransitionType.CROSSFADE,
            source_exit_time=120.0,
            target_entry_time=0.0,
            overlap_duration=8.0,
            compatibility_score=cs,
            confidence=0.9,
        )
        d = tp.to_dict()
        assert d["transition_type"] == "crossfade"
        assert d["compatibility_score"]["overall_score"] == 0.85

        tp2 = TransitionPlan.from_dict(d)
        assert tp2.transition_type == TransitionType.CROSSFADE
        assert tp2.overlap_duration == 8.0
        assert tp2.compatibility_score is not None
        assert tp2.compatibility_score.overall_score == 0.85

    def test_from_dict_invalid_type_falls_back(self):
        d = {"transition_type": "invalid_type"}
        tp = TransitionPlan.from_dict(d)
        assert tp.transition_type == TransitionType.PHRASE_CUT

    def test_from_dict_no_compatibility(self):
        d = {"transition_type": "bass_swap", "overlap_duration": 12.0}
        tp = TransitionPlan.from_dict(d)
        assert tp.compatibility_score is None


class TestSetPlan:
    def test_to_dict_and_back(self, synthetic_track_profile, synthetic_track_profile_b):
        tp = TransitionPlan(
            source_track_id="a",
            target_track_id="b",
            transition_type=TransitionType.PHRASE_CUT,
            overlap_duration=6.0,
        )
        sp = SetPlan(
            tracks=[synthetic_track_profile, synthetic_track_profile_b],
            transitions=[tp],
            total_duration_sec=300.0,
            target_duration_sec=600.0,
            energy_profile=EnergyProfile.STEADY,
            score=0.8,
        )
        d = sp.to_dict()
        assert d["energy_profile"] == "steady"
        assert len(d["tracks"]) == 2
        assert len(d["transitions"]) == 1

        sp2 = SetPlan.from_dict(d)
        assert len(sp2.tracks) == 2
        assert sp2.tracks[0].title == "Synthetic A"
        assert sp2.transitions[0].transition_type == TransitionType.PHRASE_CUT
        assert sp2.score == 0.8

    def test_get_track_by_id(self, synthetic_track_profile):
        sp = SetPlan(tracks=[synthetic_track_profile])
        assert sp.get_track_by_id("synthetic_a_hash") is synthetic_track_profile
        assert sp.get_track_by_id("nonexistent") is None

    def test_summary(self, synthetic_track_profile):
        sp = SetPlan(tracks=[synthetic_track_profile])
        s = sp.summary()
        assert "Synthetic A" in s
        assert "120" in s

    def test_invalid_energy_profile_falls_back(self):
        sp = SetPlan.from_dict({"energy_profile": "invalid"})
        assert sp.energy_profile == EnergyProfile.STEADY
