"""V8 lyrics and song-meaning contract tests; heavy models are mocked/omitted."""

from pathlib import Path

import pytest

from djenius.audio.lyrics import extract_lyrics, transcript_quality
from djenius.core.intent import SetIntent
from djenius.core.meaning import meaning_from_json, parse_lyrics_meaning
from djenius.core.models import (
    LyricsMeaningProfile, LyricsProfile, TrackAnalysis, TrackMetadata, TrackProfile,
)
from djenius.core.nl_parser import parse_deterministic, parse_request
from djenius.core.scorer import score_compatibility
from djenius.db.cache import AnalysisCache, LYRICS_ANALYSIS_VERSION, compute_file_hash


def _track(path: Path, track_id: str, meaning: LyricsMeaningProfile | None = None) -> TrackProfile:
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=str(path), title=track_id, duration_sec=60),
        analysis=TrackAnalysis(bpm=120, camelot="8B", mean_energy=.45),
        lyrics=LyricsProfile(source="sidecar", text="local", meaning=meaning, analysis_version=LYRICS_ANALYSIS_VERSION),
    )


def test_sidecar_priority_and_lrc_segments(tmp_path):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"audio")
    (tmp_path / "song.txt").write_text("plain text", encoding="utf-8")
    (tmp_path / "song.lrc").write_text("[00:12.50] line one", encoding="utf-8")
    text, source, segments = extract_lyrics(str(audio))
    assert source == "sidecar"
    assert text.startswith("[00:12.50]")
    assert segments[0]["start"] == 12.5


def test_embedded_lyrics_win_over_sidecar(tmp_path, monkeypatch):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"audio")
    (tmp_path / "song.txt").write_text("sidecar", encoding="utf-8")
    monkeypatch.setattr("djenius.audio.lyrics._embedded_lyrics", lambda _: "embedded")
    assert extract_lyrics(str(audio)) == ("embedded", "embedded", [])


def test_no_lyrics_is_explicitly_unavailable(tmp_path, monkeypatch):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"audio")
    monkeypatch.setattr("djenius.audio.lyrics.lyrics_dependencies_available", lambda: False)
    from djenius.audio.lyrics import analyze_track_lyrics
    profile = analyze_track_lyrics(str(audio))
    assert profile.source == "unavailable"
    assert profile.meaning is None
    assert "Install optional" in profile.error


def test_lyrics_cache_round_trip_and_version_invalidation(tmp_path):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    cache = AnalysisCache(str(tmp_path / "cache.db"))
    try:
        profile = _track(audio, "x").lyrics
        cache.put_lyrics(str(audio), profile)
        assert cache.get_lyrics(str(audio), LYRICS_ANALYSIS_VERSION).source == "sidecar"
        assert cache.get_lyrics(str(audio), "old-version") is None
        audio.write_bytes(b"changed")
        assert cache.get_lyrics(str(audio), LYRICS_ANALYSIS_VERSION) is None
    finally:
        cache.close()


def test_meaning_json_rejects_unknown_labels_and_clamps_values():
    with pytest.raises(ValueError, match="Unknown labels"):
        meaning_from_json({"primary_themes": ["made_up"]}, model="test")
    result = meaning_from_json({"primary_themes": ["heartbreak"], "emotional_valence": 9, "meaning_confidence": 2}, model="test")
    assert result.emotional_valence == 1
    assert result.meaning_confidence == 1


def test_transcription_repetition_is_low_confidence():
    segments = [{"start": i, "end": i + 1, "text": "la la la", "avg_logprob": -.2} for i in range(5)]
    confidence, repeated = transcript_quality(segments, .95)
    assert repeated is True
    assert confidence < .35


def test_intent_parses_lyrical_themes_and_exclusions():
    intent = parse_deterministic("Make a romantic party mix but avoid breakup songs")
    assert "romance" in intent.desired_themes
    assert "party" in intent.desired_themes
    assert "breakup" in intent.avoid_themes
    assert intent.validate() == []


def test_meaning_trajectory_is_parsed():
    intent = parse_deterministic("Start sad and emotional and slowly become hopeful")
    assert intent.meaning_trajectory == ["sad", "hopeful"]


def test_low_confidence_meaning_has_small_pair_influence(tmp_path):
    weak = LyricsMeaningProfile(primary_themes=["heartbreak"], meaning_confidence=.05)
    strong = LyricsMeaningProfile(primary_themes=["party"], meaning_confidence=1.0)
    first = _track(tmp_path / "a", "a", weak)
    second = _track(tmp_path / "b", "b", strong)
    score = score_compatibility(first, second)
    assert score.lyrical_theme_similarity == 0.0
    assert score.overall_score > .7


def test_meaning_profile_serializes_without_transcript_requirement():
    profile = LyricsProfile(source="embedded", language="it", meaning=LyricsMeaningProfile(primary_themes=["love"]))
    restored = LyricsProfile.from_dict(profile.to_dict())
    assert restored.meaning.primary_themes == ["love"]
    assert restored.language == "it"


def test_llm_lyrics_meaning_is_local_and_structured(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"message": {"content": '{"primary_themes":["hope"],"lyrical_moods":["hopeful"],"meaning_confidence":0.8}'}}
    calls = []
    import httpx
    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: (calls.append(url) or Response()))
    result, latency = parse_lyrics_meaning("tomorrow will be better", model="granite4:3b")
    assert result.primary_themes == ["hope"]
    assert calls == ["http://localhost:11434/api/chat"]
    assert latency >= 0

