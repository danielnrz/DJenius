"""Focused tests for the local application surface."""

from __future__ import annotations

import time
import asyncio
from pathlib import Path

import httpx
import pytest
import soundfile as sf

from djenius.application import LocalAppService
from djenius.core.intent import SetIntent
from djenius.core.models import SetPlan, TrackAnalysis, TrackMetadata, TrackProfile
from djenius.web.app import create_app


class ApiClient:
    """Small sync wrapper around HTTPX ASGI transport.

    This avoids depending on Starlette's optional test-client transport, which
    is changing independently of FastAPI across supported Python versions.
    """

    def __init__(self, app):
        self.app = app

    def _request(self, method: str, path: str, **kwargs):
        async def request():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(request())

    def get(self, path: str, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self._request("POST", path, **kwargs)


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


def _wait(client: ApiClient, job_id: str) -> dict:
    for _ in range(100):
        result = client.get(f"/api/jobs/{job_id}").json()
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_health_and_static_startup(tmp_path):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    client = ApiClient(create_app(service))
    assert client.get("/api/health").json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200
    assert "Create a mix" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/favicon.ico").status_code == 200


def test_scan_and_empty_library_are_graceful(tmp_path):
    library = tmp_path / "music"
    library.mkdir()
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    client = ApiClient(create_app(service))
    result = client.post("/api/library/scan", json={"path": str(library)})
    assert result.status_code == 200
    assert result.json()["track_count"] == 0
    assert result.json()["tracks"] == []

    result = client.post("/api/library/scan", json={"path": str(tmp_path / "missing")})
    assert result.status_code == 404
    assert "exists" in result.json()["detail"]


def test_system_reports_optional_semantic_and_ollama_state(tmp_path, monkeypatch):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    monkeypatch.setattr(service, "system_status", lambda: {
        "core": "ready", "ollama": False, "ollama_model": "granite4:3b",
        "semantic": False, "semantic_model": "laion/clap-htsat-unfused",
    })
    client = ApiClient(create_app(service))
    status = client.get("/api/system").json()
    assert status["semantic"] is False
    assert status["ollama_model"] == "granite4:3b"


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
    client = ApiClient(create_app(service))
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
    client = ApiClient(create_app(service))
    job = client.post("/api/plans", json={"path": str(library), "request": "chill 2 min"}).json()
    result = _wait(client, job["job_id"])
    assert result["status"] == "completed"
    assert called["intent"].raw_text == "chill 2 min"
    plan_id = result["result"]["id"]
    unsafe = client.post(f"/api/plans/{plan_id}/edit", json={"order": ["one", "one"]})
    assert unsafe.status_code == 400
    assert "duplicate" in unsafe.json()["detail"]


def test_free_form_request_is_not_mislabeled_as_selected_preset(tmp_path, monkeypatch):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    monkeypatch.setattr(
        "djenius.application.parse_request",
        lambda request, use_llm: SetIntent(preset="balanced"),
    )
    intent, _duration = service._intent(
        "make it heartbreak", "balanced", 10, False,
    )
    assert intent.preset is None


def test_output_path_traversal_and_feedback_persistence(tmp_path):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    service.paths.output_dir.mkdir(parents=True, exist_ok=True)
    (service.paths.output_dir / "mix.wav").write_bytes(b"not audio")
    client = ApiClient(create_app(service))
    assert client.get("/api/outputs/../data/app_state.json").status_code in {400, 404}
    assert client.get("/api/outputs/mix.wav").status_code == 200
    service.save_mix_feedback("mix-one", 5)
    assert service.preferences()["mix_ratings"][0]["rating"] == 5


def test_stems_option_fails_gracefully_when_optional_dependency_is_absent(tmp_path, monkeypatch):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    service._plans["plan"] = SetPlan()
    monkeypatch.setattr("djenius.audio.stems.stems_available", lambda: False)
    client = ApiClient(create_app(service))
    started = client.post("/api/plans/plan/render", json={"use_stems": True})
    assert started.status_code == 200
    result = _wait(client, started.json()["job_id"])
    assert result["status"] == "failed"
    assert "not installed" in result["error"]


def _set_director_track(path: Path, track_id: str, *, bpm: float = 120.0, artist: str = "", duration: float = 24.0) -> TrackProfile:
    from djenius.core.analysis_v2 import build_tempo_hypotheses

    sr = 6000
    n = int(round(duration * sr))
    t = [i / sr for i in range(n)]
    beat = 60.0 / bpm
    mono = [0.03 * ((-1) ** int(x / beat)) for x in t]
    sf.write(path, [[v, v] for v in mono], sr)
    third = duration / 3.0
    sections = [
        {"start_sec": 0.0, "end_sec": third, "label": "intro", "boundary_confidence": 0.9,
         "mix_in_score": 0.9, "mix_out_score": 0.35, "landing_strength": 0.3, "bass_density": 0.55, "energy_mean": 0.5},
        {"start_sec": third, "end_sec": 2 * third, "label": "drop", "boundary_confidence": 0.9,
         "mix_in_score": 0.88, "mix_out_score": 0.78, "landing_strength": 0.8, "bass_density": 0.65, "energy_mean": 0.75},
        {"start_sec": 2 * third, "end_sec": duration, "label": "outro", "boundary_confidence": 0.9,
         "mix_in_score": 0.3, "mix_out_score": 0.96, "landing_strength": 0.25, "bass_density": 0.5, "energy_mean": 0.5},
    ]
    cues = [
        {"time_sec": 0.0, "bar_index": 1, "beat_in_bar": 1, "confidence": 0.9, "section": "intro",
         "use_cases": ["mix_in"], "mix_in_score": 0.9, "mix_out_score": 0.2},
        {"time_sec": third, "bar_index": 17, "beat_in_bar": 1, "confidence": 0.9, "section": "drop",
         "use_cases": ["mix_in", "phrase_cut", "drop_landing"], "mix_in_score": 0.88, "mix_out_score": 0.78},
        {"time_sec": 2 * third, "bar_index": 33, "beat_in_bar": 1, "confidence": 0.9, "section": "outro",
         "use_cases": ["mix_out", "phrase_cut"], "mix_in_score": 0.3, "mix_out_score": 0.96},
    ]
    analysis = TrackAnalysis(
        bpm=bpm, bpm_confidence=0.97, camelot="8A", analysis_confidence=0.95,
        tempo_hypotheses=build_tempo_hypotheses(bpm, 0.97),
        section_profiles=sections, cue_candidates=cues,
        vocal_activity_curve=[0.08] * int(duration), energy_curve=[0.6] * int(duration),
        mean_energy=0.6, low_energy=0.55,
        groove_profile={"confidence": 0.9, "syncopation_index": 0.25, "swing_ratio": 1.0, "percussion_density_mean": 0.55},
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=str(path), title=track_id, artist=artist, duration_sec=duration, sample_rate=sr, channels=2),
        analysis=analysis,
    )


def _wait_long(client: ApiClient, job_id: str) -> dict:
    for _ in range(3000):
        result = client.get(f"/api/jobs/{job_id}").json()
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_set_director_plan_inspect_lock_and_preview(tmp_path, monkeypatch):
    library = tmp_path / "music"
    library.mkdir()
    tracks = [
        _set_director_track(library / "a.wav", "a", bpm=120.0, artist="Artist A"),
        _set_director_track(library / "b.wav", "b", bpm=121.0, artist="Artist B"),
        _set_director_track(library / "c.wav", "c", bpm=119.0, artist="Artist C"),
    ]
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    monkeypatch.setattr(service, "_profiles_for_library", lambda path: tracks)
    client = ApiClient(create_app(service))

    job = client.post("/api/set-director/plans", json={
        "path": str(library), "arc": "smooth", "duration_minutes": 1.0, "max_tracks": 3,
    }).json()
    result = _wait_long(client, job["job_id"])
    assert result["status"] == "completed", result.get("error")
    plan = result["result"]
    plan_id = plan["id"]
    assert plan["arc"] == "smooth"
    assert len(plan["tracks"]) >= 2
    assert len(plan["handoffs"]) == len(plan["tracks"]) - 1

    fetched = client.get(f"/api/set-director/plans/{plan_id}").json()
    assert fetched["id"] == plan_id
    assert fetched["tracks"] == plan["tracks"]

    handoff = client.get(f"/api/set-director/plans/{plan_id}/handoffs/0").json()
    assert handoff["index"] == 0
    assert isinstance(handoff["candidates"], list)

    alternate = next(
        (item for item in handoff["candidates"] if not item["selected"] and not item["hard_rejected"]), None,
    )
    if alternate is not None:
        locked = client.post(
            f"/api/set-director/plans/{plan_id}/handoffs/0/lock",
            json={"candidate_id": alternate["candidate_id"]},
        ).json()
        assert locked["user_locked"] is True
        assert locked["selected_candidate_id"] == alternate["candidate_id"]
        updated_plan = client.get(f"/api/set-director/plans/{plan_id}").json()
        assert updated_plan["handoffs"][0]["user_locked"] is True
        assert updated_plan["handoffs"][0]["candidate_id"] == alternate["candidate_id"]

    bad_index = client.get(f"/api/set-director/plans/{plan_id}/handoffs/99")
    assert bad_index.status_code == 400

    preview = client.post(f"/api/set-director/plans/{plan_id}/handoffs/0/preview", json={})
    if handoff["candidates"] and any(not item["hard_rejected"] for item in handoff["candidates"]):
        assert preview.status_code == 200
        filename = preview.json()["filename"]
        played = client.get(f"/api/outputs/{filename}")
        assert played.status_code == 200
        assert played.headers["content-type"] in {"audio/wav", "audio/x-wav"}

    assert client.get("/api/set-director/plans/does-not-exist").status_code == 404

    # Phase 9: rating a handoff feeds the same preference store V1 uses.
    refreshed_handoff = client.get(f"/api/set-director/plans/{plan_id}/handoffs/0").json()
    rated_family = next(item["technique_family"] for item in refreshed_handoff["candidates"] if item["selected"])
    feedback = client.post(f"/api/set-director/plans/{plan_id}/handoffs/0/feedback", json={"rating": "great"})
    assert feedback.status_code == 200
    assert feedback.json() == {"index": 0, "technique_family": rated_family, "rating": 1.0}
    learned = client.get("/api/preferences").json()
    assert learned["preferred_transition_styles"].get(rated_family) == pytest.approx(1.0)

    bad_rating = client.post(f"/api/set-director/plans/{plan_id}/handoffs/0/feedback", json={"rating": "nonsense"})
    assert bad_rating.status_code == 400


def test_set_director_learns_technique_preference_across_plans(tmp_path, monkeypatch):
    library = tmp_path / "music"
    library.mkdir()
    tracks = [
        _set_director_track(library / "a.wav", "a", bpm=120.0, artist="Artist A"),
        _set_director_track(library / "b.wav", "b", bpm=121.0, artist="Artist B"),
    ]
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    monkeypatch.setattr(service, "_profiles_for_library", lambda path: tracks)
    client = ApiClient(create_app(service))

    job = client.post("/api/set-director/plans", json={"path": str(library), "duration_minutes": 1.0}).json()
    first = _wait_long(client, job["job_id"])
    assert first["status"] == "completed", first.get("error")
    first_plan_id = first["result"]["id"]
    family = first["result"]["handoffs"][0]["technique_family"]
    assert family

    for _ in range(3):
        response = client.post(f"/api/set-director/plans/{first_plan_id}/handoffs/0/feedback", json={"rating": "bad"})
        assert response.status_code == 200

    learned = service._set_director_learned_preferences()
    assert learned["technique_preferences"][family] == pytest.approx(0.0)

    config = service._set_director_config("balanced")
    assert config.technique_preferences[family] == pytest.approx(0.0)


def test_set_director_full_mix_render_endpoint(tmp_path, monkeypatch):
    library = tmp_path / "music"
    library.mkdir()
    # Longer, more widely spread-out tracks than the other Set Director
    # fixtures in this file: a full-mix render needs a target-entry anchor
    # (near a track's start) and a later source-exit anchor (near its end)
    # to land in non-conflicting order on any shared middle track, which a
    # very short/sparse fixture cannot reliably guarantee.
    tracks = [
        _set_director_track(library / "a.wav", "a", bpm=120.0, artist="Artist A", duration=180.0),
        _set_director_track(library / "b.wav", "b", bpm=121.0, artist="Artist B", duration=180.0),
        _set_director_track(library / "c.wav", "c", bpm=119.0, artist="Artist C", duration=180.0),
    ]
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    monkeypatch.setattr(service, "_profiles_for_library", lambda path: tracks)
    client = ApiClient(create_app(service))

    job = client.post("/api/set-director/plans", json={
        "path": str(library), "arc": "smooth", "duration_minutes": 8.0, "max_tracks": 3,
    }).json()
    planned = _wait_long(client, job["job_id"])
    assert planned["status"] == "completed", planned.get("error")
    plan_id = planned["result"]["id"]
    handoff_count = len(planned["result"]["handoffs"])
    assert handoff_count >= 1

    render_job = client.post(f"/api/set-director/plans/{plan_id}/render", json={}).json()
    rendered = _wait_long(client, render_job["job_id"])
    assert rendered["status"] == "completed", rendered.get("error")
    filename = rendered["result"]["filename"]
    assert rendered["result"]["duration_sec"] > 0

    played = client.get(f"/api/outputs/{filename}")
    assert played.status_code == 200
    assert played.headers["content-type"] in {"audio/wav", "audio/x-wav"}

    outputs = client.get("/api/outputs").json()["outputs"]
    matching = next(item for item in outputs if item["filename"] == filename)
    assert matching["set_director"] is True
    assert matching["arc"] == "smooth"
    assert len(matching["technique_sequence"]) == handoff_count

    assert client.post("/api/set-director/plans/does-not-exist/render", json={}).status_code == 404
