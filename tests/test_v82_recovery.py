"""V8.2 meaning-cache recovery and human-correction tests."""

from pathlib import Path
import time

import djenius.application as application
from djenius.application import LocalAppService
from djenius.audio.lyrics import DEFAULT_TRANSCRIPTION_MODEL
from djenius.core.meaning import MEANING_ANALYSIS_VERSION, MEANING_MODEL_VERSION, meaning_model_name
from djenius.core.models import (
    LyricsMeaningProfile, LyricsProfile, TrackAnalysis, TrackMetadata, TrackProfile,
)
from djenius.db.cache import AnalysisCache, LYRICS_ANALYSIS_VERSION


def _metadata(path: Path) -> TrackMetadata:
    return TrackMetadata(filepath=str(path), title="Recovery", duration_sec=120.0)


def _meaning(themes=("heartbreak",), confidence=.9):
    return LyricsMeaningProfile(
        model_name=meaning_model_name(), model_version=MEANING_MODEL_VERSION,
        primary_themes=list(themes), meaning_confidence=confidence,
    )


def _lyrics(*, text="cached transcript", meaning=None, version=LYRICS_ANALYSIS_VERSION, error=""):
    return LyricsProfile(
        source="transcribed_full_audio", text=text,
        transcription_model=DEFAULT_TRANSCRIPTION_MODEL,
        transcription_confidence=.92, language="en", language_confidence=.96,
        meaning=meaning, meaning_analysis_version=MEANING_ANALYSIS_VERSION if meaning else "",
        meaning_error=error, analysis_version=version,
    )


def _run(service, job_id):
    for _ in range(100):
        result = service.get_job(job_id)
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(.01)
    raise AssertionError("job did not finish")


def test_transcript_without_meaning_retries_meaning_without_transcription(tmp_path, monkeypatch):
    music = tmp_path / "music"
    music.mkdir()
    audio = music / "song.mp3"
    audio.write_bytes(b"stable-audio")
    item = _metadata(audio)
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "out")
    cache = AnalysisCache(str(service.paths.cache_path))
    cache.put_lyrics(str(audio), _lyrics())
    cache.close()
    monkeypatch.setattr(application, "scan_directory", lambda _: [item])
    calls = []

    def fake_analyze(filepath, **kwargs):
        calls.append(kwargs.get("existing_profile"))
        assert kwargs["existing_profile"].text == "cached transcript"
        return _lyrics(meaning=_meaning())

    monkeypatch.setattr("djenius.audio.lyrics.analyze_track_lyrics", fake_analyze)
    result = _run(service, service.start_lyrics_analysis(str(music), use_llm=True))
    assert result["status"] == "completed"
    assert result["result"]["lyrics_analyzed"] == 1
    assert result["result"]["lyrics_skipped"] == 0
    assert len(calls) == 1
    assert calls[0] is not None


def test_valid_meaning_skips_and_stale_meaning_reuses_transcript(tmp_path, monkeypatch):
    music = tmp_path / "music"
    music.mkdir()
    audio = music / "song.mp3"
    audio.write_bytes(b"stable-audio")
    item = _metadata(audio)
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "out")
    monkeypatch.setattr(application, "scan_directory", lambda _: [item])
    cache = AnalysisCache(str(service.paths.cache_path))
    cache.put_lyrics(str(audio), _lyrics(meaning=_meaning()))
    cache.close()
    calls = []
    monkeypatch.setattr("djenius.audio.lyrics.analyze_track_lyrics", lambda *args, **kwargs: calls.append(kwargs) or _lyrics(meaning=_meaning()))
    skipped = _run(service, service.start_lyrics_analysis(str(music), use_llm=True))
    assert skipped["result"]["lyrics_skipped"] == 1
    assert not calls

    cache = AnalysisCache(str(service.paths.cache_path))
    stale = _lyrics(meaning=_meaning())
    stale.meaning_analysis_version = "old-meaning-version"
    cache.put_lyrics(str(audio), stale)
    cache.close()
    retried = _run(service, service.start_lyrics_analysis(str(music), use_llm=True))
    assert retried["result"]["lyrics_analyzed"] == 1
    assert calls[0]["existing_profile"].text == "cached transcript"


def test_scan_reports_distinct_meaning_states(tmp_path, monkeypatch):
    music = tmp_path / "music"
    music.mkdir()
    files = [music / f"{name}.mp3" for name in ("none", "missing", "ready", "failed")]
    for path in files:
        path.write_bytes(path.name.encode())
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "out")
    cache = AnalysisCache(str(service.paths.cache_path))
    cache.put(TrackProfile(id="none", metadata=_metadata(files[0]), analysis=TrackAnalysis()))
    cache.put_lyrics(str(files[1]), _lyrics())
    cache.put_lyrics(str(files[2]), _lyrics(meaning=_meaning()))
    cache.put_lyrics(str(files[3]), _lyrics(meaning=_meaning(), error="bad response"))
    cache.close()
    monkeypatch.setattr(application, "scan_directory", lambda _: [_metadata(path) for path in files])
    result = service.scan_library(str(music))
    states = {row["filename"]: row["meaning_status"] for row in result["tracks"]}
    assert states["none.mp3"] == "NOT_ANALYZED"
    assert states["missing.mp3"] == "TRANSCRIPT_READY_MEANING_MISSING"
    assert states["ready.mp3"] == "MEANING_READY"
    assert states["failed.mp3"] == "MEANING_INVALID"
    assert result["meaning_summary"]["ready"] == 1
    assert result["meaning_summary"]["missing"] == 1
    assert result["meaning_summary"]["failed"] == 1


def test_user_correction_overlay_wins_without_overwriting_raw_cache(tmp_path):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"stable-audio")
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "out")
    from djenius.db.cache import compute_file_hash
    raw = TrackProfile(
        id=compute_file_hash(str(audio)), metadata=_metadata(audio), analysis=TrackAnalysis(),
        lyrics=_lyrics(meaning=_meaning(("party",))),
    )
    cache = AnalysisCache(str(service.paths.cache_path))
    cache.put(raw)
    cache.put_lyrics(str(audio), raw.lyrics)
    cache.close()
    service.save_track_correction(raw.id, {"themes": ["heartbreak"], "lyrical_moods": ["sad"], "audio_tags": ["energetic", "dance"]})
    effective = service._effective_profile(raw)
    assert effective.lyrics.meaning.primary_themes == ["heartbreak"]
    assert effective.lyrics.meaning.meaning_source == "manual_correction"
    assert effective.semantic.semantic_tags == ["energetic", "dance"]
    cache = AnalysisCache(str(service.paths.cache_path))
    restored = cache.get(str(audio))
    cache.close()
    assert restored.lyrics.meaning.primary_themes == ["party"]
