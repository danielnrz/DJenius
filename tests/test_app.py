"""Focused tests for the local application surface."""

from __future__ import annotations

import time
from pathlib import Path

import soundfile as sf
from fastapi.testclient import TestClient

from djenius.application import LocalAppService
from djenius.core.models import SetPlan, TrackAnalysis, TrackMetadata, TrackProfile
from djenius.web.app import create_app


def _profile(path: Path, title: str, track_id: str) -> TrackProfile:
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(
            filepath=str(path), title=title, duration_sec=4.0,
            sample_rate=44100, channels=1, format="WAV",
        ),
        analysis=TrackAnalysis(
            bpm=120.0, camelot="8B", mean_energy=0.4,
            analysis_confidence=0.9, bpm_confidence=0.9,
            phrase_boundaries=[0.0, 2.0], bar_times=[0.0, 2.0],
            possible_exit_points=[2.0], possible_entry_points=[0.0],
        ),
    )


def _wait(client: TestClient, job_id: str) -> dict:
    for _ in range(100):
        result = client.get(f"/api/jobs/{job_id}").json()
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_health_and_static_startup(tmp_path):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    client = TestClient(create_app(service))
    assert client.get("/api/health").json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200
    assert "Create a mix" in page.text
    assert client.get("/static/app.js").status_code == 200


def test_scan_and_empty_library_are_graceful(tmp_path):
    library = tmp_path / "music"
    library.mkdir()
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    client = TestClient(create_app(service))
    result = client.post("/api/library/scan", json={"path": str(library)})
    assert result.status_code == 200
    assert result.json()["track_count"] == 0
    assert result.json()["tracks"] == []

    result = client.post("/api/library/scan", json={"path": str(tmp_path / "missing")})
    assert result.status_code == 404
    assert "exists" in result.json()["detail"]


def test_analysis_job_lifecycle_and_cached_track_status(tmp_path, monkeypatch):
    library = tmp_path / "music"
    library.mkdir()
    for name, freq in (("one.wav", 220), ("two.wav", 330)):
        sf.write(library / name, [0.2, -0.2, 0.1 if freq == 220 else -0.1] * 29400, 44100)
    profiles = {
        str(library / "one.wav"): _profile(library / "one.wav", "One", "one"),
        str(library / "two.wav"): _profile(library / "two.wav", "Two", "two"),
    }

    def fake_analyze(filepath, force=False, cache=None):
        profile = profiles[str(Path(filepath))]
        from djenius.db.cache import compute_file_hash
        profile.id = compute_file_hash(filepath)
        cache.put(profile)
        return profile

    monkeypatch.setattr("djenius.audio.analyzer.analyze_track", fake_analyze)
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    client = TestClient(create_app(service))
    job = client.post("/api/library/analyze", json={"path": str(library)}).json()
    result = _wait(client, job["job_id"])
    assert result["status"] == "completed"
    assert result["result"]["analyzed"] == 2
    assert result["result"]["ready_count"] == 2


def test_plan_job_uses_engine_and_rejects_unsafe_edits(tmp_path, monkeypatch):
    library = tmp_path / "music"
    library.mkdir()
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    first = _profile(library / "one.wav", "One", "one")
    second = _profile(library / "two.wav", "Two", "two")
    monkeypatch.setattr(service, "_profiles_for_library", lambda path: [first, second])
    called = {}

    def fake_plan(**kwargs):
        called.update(kwargs)
        return SetPlan(tracks=[first, second], total_duration_sec=8.0, target_duration_sec=120.0)

    monkeypatch.setattr("djenius.application.plan_set", fake_plan)
    client = TestClient(create_app(service))
    job = client.post("/api/plans", json={"path": str(library), "request": "chill 2 min"}).json()
    result = _wait(client, job["job_id"])
    assert result["status"] == "completed"
    assert called["intent"].raw_text == "chill 2 min"
    plan_id = result["result"]["id"]
    unsafe = client.post(f"/api/plans/{plan_id}/edit", json={"order": ["one", "one"]})
    assert unsafe.status_code == 400
    assert "duplicate" in unsafe.json()["detail"]


def test_output_path_traversal_and_feedback_persistence(tmp_path):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    service.paths.output_dir.mkdir(parents=True, exist_ok=True)
    (service.paths.output_dir / "mix.wav").write_bytes(b"not audio")
    client = TestClient(create_app(service))
    assert client.get("/api/outputs/../data/app_state.json").status_code in {400, 404}
    assert client.get("/api/outputs/mix.wav").status_code == 200
    service.save_mix_feedback("mix-one", 5)
    assert service.preferences()["mix_ratings"][0]["rating"] == 5


def test_stems_option_fails_gracefully_when_optional_dependency_is_absent(tmp_path, monkeypatch):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    service._plans["plan"] = SetPlan()
    monkeypatch.setattr("djenius.audio.stems.stems_available", lambda: False)
    client = TestClient(create_app(service))
    started = client.post("/api/plans/plan/render", json={"use_stems": True})
    assert started.status_code == 200
    result = _wait(client, started.json()["job_id"])
    assert result["status"] == "failed"
    assert "not installed" in result["error"]
