"""FastAPI entry point for the local DJenius application."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from djenius.application import LocalAppService

STATIC_DIR = Path(__file__).parent / "static"


class LibraryRequest(BaseModel):
    path: str = Field(min_length=1)


class AnalyzeRequest(BaseModel):
    path: Optional[str] = None
    force: bool = False


class LyricsAnalyzeRequest(BaseModel):
    path: Optional[str] = None
    force: bool = False
    use_llm: bool = True
    use_transcription: bool = True
    use_vocal_stem: bool = False
    retry_unresolved: bool = False


class PlanRequest(BaseModel):
    path: Optional[str] = None
    request: Optional[str] = None
    preset: Optional[str] = None
    duration_minutes: Optional[float] = Field(default=None, gt=0, le=24 * 60)
    use_llm: bool = False


class EditPlanRequest(BaseModel):
    order: list[str] = Field(min_length=2)


class RenderRequest(BaseModel):
    target_lufs: float = Field(default=-14.0, ge=-30.0, le=-1.0)
    use_stems: bool = False


class MixFeedbackRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)


class TransitionFeedbackRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    position: int = Field(ge=1)
    rating: str | float


class TrackFeedbackRequest(BaseModel):
    track_id: str = Field(min_length=1)
    liked: bool


class TrackCorrectionRequest(BaseModel):
    themes: list[str] = Field(default_factory=list)
    lyrical_moods: list[str] = Field(default_factory=list)
    audio_tags: list[str] = Field(default_factory=list)


def create_app(service: LocalAppService | None = None) -> FastAPI:
    """Create the web app, optionally with isolated paths for tests."""
    service = service or LocalAppService()
    app = FastAPI(title="DJenius", version="0.1.0", docs_url=None, redoc_url=None)
    app.state.service = service
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def fail(exc: Exception) -> HTTPException:
        if isinstance(exc, FileNotFoundError):
            return HTTPException(status_code=404, detail=str(exc))
        return HTTPException(status_code=400, detail=str(exc))

    @app.get("/", response_class=HTMLResponse)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/favicon.ico")
    def favicon() -> FileResponse:
        return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "service": "djenius", "core": "ready"}

    @app.get("/api/state")
    def state() -> dict:
        return service.app_state()

    @app.get("/api/presets")
    def presets() -> dict:
        return {"presets": service.app_state()["presets"]}

    @app.post("/api/library/scan")
    def scan(request: LibraryRequest) -> dict:
        try:
            return service.scan_library(request.path)
        except (FileNotFoundError, ValueError) as exc:
            raise fail(exc) from exc

    @app.post("/api/library/analyze")
    def analyze(request: AnalyzeRequest) -> dict:
        try:
            return {"job_id": service.start_analysis(request.path, request.force)}
        except (FileNotFoundError, ValueError) as exc:
            raise fail(exc) from exc

    @app.post("/api/library/semantic")
    def semantic(request: AnalyzeRequest) -> dict:
        try:
            return {"job_id": service.start_semantic_analysis(request.path, request.force)}
        except (FileNotFoundError, ValueError) as exc:
            raise fail(exc) from exc

    @app.post("/api/library/lyrics")
    def lyrics(request: LyricsAnalyzeRequest) -> dict:
        try:
            return {"job_id": service.start_lyrics_analysis(
                request.path, request.force, request.use_llm,
                request.use_transcription, request.use_vocal_stem,
                request.retry_unresolved,
            )}
        except (FileNotFoundError, ValueError) as exc:
            raise fail(exc) from exc

    @app.post("/api/plans")
    def create_plan(request: PlanRequest) -> dict:
        try:
            return {
                "job_id": service.start_plan(
                    library_path=request.path,
                    request=request.request,
                    preset=request.preset,
                    duration_minutes=request.duration_minutes,
                    use_llm=request.use_llm,
                )
            }
        except (FileNotFoundError, ValueError) as exc:
            raise fail(exc) from exc

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict:
        try:
            return service.get_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Job not found") from exc

    @app.get("/api/plans/{plan_id}")
    def get_plan(plan_id: str) -> dict:
        try:
            return service.plan_view(plan_id, service.get_plan(plan_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/plans/{plan_id}/edit")
    def edit_plan(plan_id: str, request: EditPlanRequest) -> dict:
        try:
            return service.edit_plan(plan_id, request.order)
        except (KeyError, ValueError) as exc:
            raise fail(exc) from exc

    @app.post("/api/plans/{plan_id}/regenerate")
    def regenerate_plan(plan_id: str) -> dict:
        try:
            return service.regenerate_plan(plan_id)
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise fail(exc) from exc

    @app.post("/api/plans/{plan_id}/render")
    def render_plan(plan_id: str, request: RenderRequest) -> dict:
        try:
            return {"job_id": service.start_render(plan_id, request.target_lufs, request.use_stems)}
        except (KeyError, ValueError) as exc:
            raise fail(exc) from exc

    @app.get("/api/outputs")
    def outputs() -> dict:
        return {"outputs": service.list_outputs()}

    @app.get("/api/outputs/{filename}")
    def output(filename: str) -> FileResponse:
        try:
            path = service.safe_output(filename)
        except (FileNotFoundError, ValueError) as exc:
            raise fail(exc) from exc
        media_type = "audio/mpeg" if path.suffix.lower() == ".mp3" else "audio/wav"
        return FileResponse(path, media_type=media_type, filename=path.name)

    @app.post("/api/feedback/mix")
    def mix_feedback(request: MixFeedbackRequest) -> dict:
        try:
            return service.save_mix_feedback(request.plan_id, request.rating)
        except (KeyError, ValueError) as exc:
            raise fail(exc) from exc

    @app.post("/api/feedback/transition")
    def transition_feedback(request: TransitionFeedbackRequest) -> dict:
        try:
            return service.save_transition_feedback(request.plan_id, request.position, request.rating)
        except (KeyError, ValueError) as exc:
            raise fail(exc) from exc

    @app.post("/api/feedback/track")
    def track_feedback(request: TrackFeedbackRequest) -> dict:
        try:
            return service.save_track_feedback(request.track_id, request.liked)
        except ValueError as exc:
            raise fail(exc) from exc

    @app.post("/api/library/tracks/{track_id}/correction")
    def correction(track_id: str, request: TrackCorrectionRequest) -> dict:
        try:
            payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
            return service.save_track_correction(track_id, payload)
        except ValueError as exc:
            raise fail(exc) from exc

    @app.get("/api/preferences")
    def preferences() -> dict:
        return service.preferences()

    @app.get("/api/system")
    def system() -> dict:
        return service.system_status()

    return app


app = create_app()
