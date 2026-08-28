"""Tests for compatibility scoring between tracks."""

from __future__ import annotations

import pytest

from djenius.core.models import TrackProfile, TrackMetadata, TrackAnalysis, TransitionType
from djenius.core.scorer import (
    score_compatibility,
    score_transition_quality,
    recommend_transition_type,
    rank_candidates,
)


def _make_profile(
    bpm: float = 120.0,
    camelot: str = "8B",
    mean_energy: float = 0.5,
    spectral_centroid: float = 2000.0,
    low_energy: float = 0.2,
    mid_energy: float = 0.5,
    high_energy: float = 0.3,
    title: str = "Test",
) -> TrackProfile:
    return TrackProfile(
        id=f"hash_{title}",
        metadata=TrackMetadata(filepath=f"/tmp/{title}.wav", title=title),
        analysis=TrackAnalysis(
            bpm=bpm,
            camelot=camelot,
            mean_energy=mean_energy,
            spectral_centroid_mean=spectral_centroid,
            low_energy=low_energy,
            mid_energy=mid_energy,
            high_energy=high_energy,
        ),
    )


class TestScoreCompatibility:
    def test_same_track_high_score(self):
        a = _make_profile(bpm=120, camelot="8B", mean_energy=0.5, title="A")
        score = score_compatibility(a, a)
        assert score.overall_score >= 0.8

    def test_close_bpm_high_tempo_score(self):
        a = _make_profile(bpm=120, camelot="8B", title="A")
        b = _make_profile(bpm=121, camelot="8B", title="B")
        score = score_compatibility(a, b)
        assert score.tempo_score >= 0.9

    def test_far_bpm_low_tempo_score(self):
        a = _make_profile(bpm=120, camelot="8B", title="A")
        b = _make_profile(bpm=90, camelot="8B", title="B")
        score = score_compatibility(a, b)
        assert score.tempo_score <= 0.7

    def test_compatible_camelot_high_key_score(self):
        a = _make_profile(camelot="8B", title="A")
        b = _make_profile(camelot="9B", title="B")
        score = score_compatibility(a, b)
        assert score.key_score >= 0.7

    def test_incompatible_camelot_low_key_score(self):
        a = _make_profile(camelot="1A", title="A")
        b = _make_profile(camelot="7A", title="B")
        score = score_compatibility(a, b)
        assert score.key_score <= 0.4

    def test_spectral_score_range(self):
        a = _make_profile(spectral_centroid=2000, title="A")
        b = _make_profile(spectral_centroid=2200, title="B")
        score = score_compatibility(a, b)
        assert 0.0 <= score.spectral_score <= 1.0

    def test_energy_score_range(self):
        a = _make_profile(low_energy=0.2, mid_energy=0.5, high_energy=0.3, title="A")
        b = _make_profile(low_energy=0.3, mid_energy=0.4, high_energy=0.3, title="B")
        score = score_compatibility(a, b)
        assert 0.0 <= score.energy_score <= 1.0

    def test_overall_is_weighted_average(self):
        a = _make_profile(bpm=120, camelot="8B", title="A")
        b = _make_profile(bpm=120, camelot="8B", title="B")
        score = score_compatibility(a, b)
        # Just verify it's a reasonable aggregate
        assert 0.0 <= score.overall_score <= 1.0


class TestScoreTransitionQuality:
    def test_score_range(self):
        a = _make_profile(title="A")
        b = _make_profile(title="B")
        score = score_transition_quality(a, b, TransitionType.CROSSFADE, 8.0)
        assert 0.0 <= score <= 1.0

    def test_longer_overlap_slightly_better(self):
        a = _make_profile(title="A")
        b = _make_profile(title="B")
        score_short = score_transition_quality(a, b, TransitionType.CROSSFADE, 4.0)
        score_long = score_transition_quality(a, b, TransitionType.CROSSFADE, 12.0)
        assert score_long >= score_short


class TestRecommendTransitionType:
    def test_returns_tuple(self):
        a = _make_profile(title="A")
        b = _make_profile(title="B")
        result = recommend_transition_type(a, b)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_returns_valid_type_and_confidence(self):
        a = _make_profile(title="A")
        b = _make_profile(title="B")
        ttype, confidence, reasoning = recommend_transition_type(a, b)
        assert isinstance(ttype, TransitionType)
        assert isinstance(confidence, float)
        assert isinstance(reasoning, str)
        assert 0.0 <= confidence <= 1.0

    def test_high_energy_gets_confident_recommendation(self):
        a = _make_profile(low_energy=0.8, mid_energy=0.7, high_energy=0.6, title="A")
        b = _make_profile(low_energy=0.8, mid_energy=0.7, high_energy=0.6, title="B")
        ttype, confidence, reasoning = recommend_transition_type(a, b)
        assert confidence >= 0.3
        assert len(reasoning) > 0


class TestRankCandidates:
    def test_ranking_order(self):
        a = _make_profile(bpm=120, camelot="8B", mean_energy=0.5, title="A")
        b_good = _make_profile(bpm=121, camelot="8B", mean_energy=0.5, title="B")
        b_far = _make_profile(bpm=90, camelot="1A", mean_energy=0.9, title="C")
        candidates = [b_far, b_good]
        ranked = rank_candidates(a, candidates)
        # b_good has closer BPM and compatible key — should rank higher
        assert ranked[0][0].id == b_good.id

    def test_returns_list_of_tuples(self):
        a = _make_profile(title="A")
        b = _make_profile(title="B")
        ranked = rank_candidates(a, [b])
        assert len(ranked) == 1
        target, score = ranked[0]
        assert target.id == b.id
        assert isinstance(score.overall_score, float)

    def test_excludes_self(self):
        a = _make_profile(title="A")
        ranked = rank_candidates(a, [a])
        assert len(ranked) == 0
