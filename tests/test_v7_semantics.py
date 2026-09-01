"""Focused V7 tests for local intent provenance and semantic cache/scoring."""

from __future__ import annotations

from pathlib import Path

from djenius.core.intent import SetIntent
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile, SemanticProfile
from djenius.core.nl_parser import parse_request
from djenius.core.planner import plan_set
from djenius.core.scorer import score_compatibility
from djenius.db.cache import AnalysisCache


def _profile(path: Path, track_id: str, semantic: SemanticProfile | None = None) -> TrackProfile:
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=str(path), title=track_id, duration_sec=60.0),
        analysis=TrackAnalysis(bpm=120.0, camelot="8B", mean_energy=0.4),
        semantic=semantic,
    )


def test_llm_disabled_never_calls_ollama(monkeypatch):
    called = False

    def fail(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("Ollama should not be called")

    monkeypatch.setattr("djenius.core.nl_parser.parse_with_ollama", fail)
    intent = parse_request("make a chill 20 minute mix", use_llm=False)
    assert intent.source == "nl_parser"
    assert called is False


def test_llm_enabled_calls_ollama_even_when_deterministic_is_useful(monkeypatch):
    calls = []

    def fake(text, model, url):
        calls.append((text, model, url))
        return SetIntent(
            raw_text=text,
            source="llm",
            parser_model=model,
            parser_latency_ms=12.5,
            llm_attempted=True,
            desired_moods=["melancholic"],
            desired_activity=["late_night"],
        )

    monkeypatch.setattr("djenius.core.nl_parser.parse_with_ollama", fake)
    intent = parse_request("make a chill late night mix", use_llm=True)
    assert calls and calls[0][0].startswith("make a chill")
    assert calls[0][2].startswith("http://localhost:")
    assert intent.source == "llm"
    assert intent.parser_model == "granite4:3b"
    assert intent.desired_moods == ["melancholic"]
    assert intent.desired_activity == ["late_night"]


def test_ollama_failure_is_visible_fallback(monkeypatch):
    monkeypatch.setattr("djenius.core.nl_parser.parse_with_ollama", lambda *args, **kwargs: None)
    intent = parse_request("make a happy dance mix", use_llm=True)
    assert intent.source == "llm_fallback"
    assert intent.llm_attempted is True
    assert intent.parser_error
    assert "happy" in intent.desired_moods
    assert "dance" in intent.desired_activity


def test_semantic_cache_round_trip_and_file_change_invalidation(tmp_path):
    path = tmp_path / "track.wav"
    path.write_bytes(b"audio-one")
    cache = AnalysisCache(str(tmp_path / "cache.db"))
    try:
        from djenius.db.cache import compute_file_hash
        cache.put(_profile(path, compute_file_hash(str(path))))
        semantic = SemanticProfile(
            model_name="test-model",
            model_version="1",
            embedding=[1.0, 0.0],
            mood_scores={"sad": 0.8, "happy": 0.1},
            activity_scores={"late_night": 0.7},
            semantic_tags=["sad", "late_night"],
            source_file_hash="",
        )
        cache.put_semantic(str(path), semantic)
        result = cache.get_semantic(str(path), "test-model", "1")
        assert result is not None
        assert result.semantic_tags == ["sad", "late_night"]
        assert cache.get(str(path)).semantic is not None
        path.write_bytes(b"audio-two")
        assert cache.get_semantic(str(path), "test-model", "1") is None
    finally:
        cache.close()


def test_semantic_compatibility_is_secondary_and_explained(tmp_path):
    first = _profile(tmp_path / "one.wav", "one", SemanticProfile(
        embedding=[1.0, 0.0], mood_scores={"sad": 0.9, "happy": 0.1},
        activity_scores={"late_night": 0.9},
    ))
    second = _profile(tmp_path / "two.wav", "two", SemanticProfile(
        embedding=[1.0, 0.0], mood_scores={"sad": 0.8, "happy": 0.2},
        activity_scores={"late_night": 0.8},
    ))
    score = score_compatibility(first, second)
    assert score.semantic_similarity_score > 0.9
    assert score.mood_continuity_score >= 0.9
    assert "mood" in score.reasoning


def test_seeded_plans_are_reproducible_but_can_choose_an_alternative(tmp_path):
    tracks = []
    for index in range(5):
        profile = _profile(tmp_path / f"{index}.wav", str(index))
        profile.metadata.duration_sec = 180.0
        profile.analysis.possible_exit_points = [120.0]
        profile.analysis.possible_entry_points = [10.0]
        profile.analysis.phrase_boundaries = [0.0, 60.0, 120.0]
        profile.analysis.bar_times = [0.0, 60.0, 120.0]
        tracks.append(profile)

    first = plan_set(tracks, target_duration_sec=300.0, seed=1)
    repeat = plan_set(tracks, target_duration_sec=300.0, seed=1)
    alternative = plan_set(tracks, target_duration_sec=300.0, seed=2)
    assert [track.id for track in first.tracks] == [track.id for track in repeat.tracks]
    assert [track.id for track in first.tracks] != [track.id for track in alternative.tracks]
