"""Application service for the local DJenius product.

The service is intentionally small: it owns local app state and background
jobs, while scanning, analysis, intent parsing, planning, rendering, and
preference learning remain in their existing engine modules.
"""

from __future__ import annotations

import json
import copy
import logging
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from djenius.audio.scanner import extract_metadata, scan_directory
from djenius.core.explanations import explain_transition
from djenius.core.intent import ALL_PRESETS, SetIntent, make_intent
from djenius.core.models import SetPlan, TrackAnalysis, TrackMetadata, TrackProfile
from djenius.core.nl_parser import ollama_model_name, parse_request
from djenius.core.meaning import MEANING_ANALYSIS_VERSION, MEANING_MODEL_VERSION, THEMES, LYRICAL_MOODS, meaning_model_name, meaning_state
from djenius.core.semantic import ACTIVITIES, INTENSITIES, MOODS, SEMANTIC_LABELS, STYLES
from djenius.core.planner import plan_ordered_set, plan_set
from djenius.core.performance import reorder_performance_timeline
from djenius.db.cache import AnalysisCache, compute_file_hash
from djenius.db.preferences import PreferenceProfile

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Convert engine scalar values into ordinary JSON-compatible values."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return [_json_safe(item) for item in sorted(value, key=str)]
    if isinstance(value, Path):
        return str(value)
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass
    return value


@dataclass
class AppPaths:
    """Local directories used by the application."""

    data_dir: Path
    output_dir: Path

    @classmethod
    def default(cls) -> "AppPaths":
        data_dir = Path.cwd() / "data"
        return cls(data_dir=data_dir, output_dir=Path.cwd() / "output")

    @property
    def cache_path(self) -> Path:
        return self.data_dir / "analysis_cache.db"

    @property
    def preferences_path(self) -> Path:
        return self.data_dir / "djenius_preferences.db"

    @property
    def state_path(self) -> Path:
        return self.data_dir / "app_state.json"

    @property
    def outputs_index_path(self) -> Path:
        return self.data_dir / "outputs.json"


class LocalAppService:
    """Orchestrate local application actions and in-process jobs."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        output_dir: str | Path | None = None,
        max_workers: int = 2,
    ):
        default = AppPaths.default()
        self.paths = AppPaths(
            data_dir=Path(data_dir).expanduser().resolve() if data_dir else default.data_dir,
            output_dir=Path(output_dir).expanduser().resolve() if output_dir else default.output_dir,
        )
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.paths.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="djenius")
        self._jobs: dict[str, dict[str, Any]] = {}
        self._plans: dict[str, SetPlan] = {}
        self._plan_libraries: dict[str, str] = {}
        self._analysis_failures: dict[str, str] = {}
        self._state = self._load_json(self.paths.state_path, {})
        self._output_records = self._load_json(self.paths.outputs_index_path, [])

    # ---- local state and safe paths ----

    @staticmethod
    def _load_json(path: Path, fallback: Any) -> Any:
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return fallback

    def _save_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
        temporary.replace(path)

    def resolve_library(self, library_path: str | None = None) -> Path:
        candidate = library_path or self._state.get("library_path")
        if not candidate:
            raise ValueError("Choose a music folder first")
        path = Path(candidate).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Selected music folder no longer exists: {path}")
        if not path.is_dir():
            raise ValueError("The selected music path is not a folder")
        return path

    def safe_output(self, filename: str) -> Path:
        """Resolve a generated output by basename only."""
        candidate_name = Path(filename).name
        if candidate_name != filename or Path(filename).suffix.lower() not in {".wav", ".mp3"}:
            raise ValueError("Only generated WAV and MP3 outputs can be served")
        candidate = (self.paths.output_dir / candidate_name).resolve()
        if candidate.parent != self.paths.output_dir or not candidate.is_file():
            raise FileNotFoundError("Rendered output not found")
        return candidate

    def _remember_state(self, **values: Any) -> None:
        self._state.update(values)
        self._save_json(self.paths.state_path, self._state)

    # ---- jobs ----

    def _new_job(self, kind: str) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "type": kind,
                "status": "queued",
                "progress": 0.0,
                "message": "Queued",
                "result": None,
                "error": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._prune_jobs()
        return job_id

    def _prune_jobs(self) -> None:
        completed = [
            job for job in self._jobs.values()
            if job["status"] in {"completed", "failed"}
        ]
        if len(completed) <= 100:
            return
        completed.sort(key=lambda job: job["updated_at"])
        for job in completed[:-100]:
            self._jobs.pop(job["id"], None)

    def _update_job(self, job_id: str, **values: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(values, updated_at=time.time())

    def _run_job(self, job_id: str, action: Callable[[Callable[[float, str], None]], Any]) -> None:
        self._update_job(job_id, status="running", message="Starting")

        def progress(value: float, message: str) -> None:
            self._update_job(job_id, progress=max(0.0, min(100.0, float(value))), message=message)

        try:
            result = action(progress)
        except Exception as exc:
            logger.exception("DJenius job %s failed", job_id)
            self._update_job(job_id, status="failed", message=str(exc), error=str(exc))
            return
        self._update_job(
            job_id,
            status="completed",
            progress=100.0,
            message="Complete",
            result=_json_safe(result),
        )

    def submit_job(self, kind: str, action: Callable[[Callable[[float, str], None]], Any]) -> str:
        job_id = self._new_job(kind)
        self._executor.submit(self._run_job, job_id, action)
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return dict(job)

    # ---- library ----

    @staticmethod
    def _normalize_correction(correction: dict[str, Any]) -> dict[str, list[str]]:
        """Validate a small user overlay; automatic evidence stays cached."""
        if not isinstance(correction, dict):
            raise ValueError("Correction must be an object")
        fields = {
            "themes": set(THEMES),
            "lyrical_moods": set(LYRICAL_MOODS),
            "audio_tags": set(SEMANTIC_LABELS),
        }
        normalized: dict[str, list[str]] = {}
        for field, allowed in fields.items():
            value = correction.get(field, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError(f"{field} must be a list of labels")
            unknown = sorted(set(value) - allowed)
            if unknown:
                raise ValueError(f"Unknown correction labels in {field}: {', '.join(unknown)}")
            normalized[field] = list(dict.fromkeys(value))[:8]
        if not any(normalized.values()):
            raise ValueError("Enter at least one correction label")
        return normalized

    def _corrections(self) -> dict[str, dict]:
        prefs = PreferenceProfile(str(self.paths.preferences_path))
        try:
            return prefs.get_track_corrections()
        finally:
            prefs.close()

    @staticmethod
    def _apply_correction(profile: TrackProfile, correction: dict | None) -> TrackProfile:
        if not correction:
            return profile
        result = copy.deepcopy(profile)
        result.manual_correction = copy.deepcopy(correction)
        themes = correction.get("themes", [])
        moods = correction.get("lyrical_moods", [])
        if themes or moods:
            from djenius.core.models import LyricsMeaningProfile, LyricsProfile
            if result.lyrics is None:
                result.lyrics = LyricsProfile(source="manual", transcription_confidence=1.0)
            if result.lyrics.meaning is None:
                result.lyrics.meaning = LyricsMeaningProfile()
            meaning = result.lyrics.meaning
            if themes:
                meaning.primary_themes = list(themes)
                meaning.secondary_themes = []
            if moods:
                meaning.lyrical_moods = list(moods)
            meaning.meaning_confidence = 1.0
            meaning.model_name = meaning_model_name()
            meaning.model_version = MEANING_MODEL_VERSION
            meaning.meaning_source = "manual_correction"
            result.lyrics.meaning_analysis_version = MEANING_ANALYSIS_VERSION
            result.lyrics.meaning_error = ""
        audio_tags = correction.get("audio_tags", [])
        if audio_tags:
            from djenius.core.models import SemanticProfile
            if result.semantic is None:
                result.semantic = SemanticProfile()
            result.semantic.semantic_tags = list(audio_tags)
            for label in audio_tags:
                if label in MOODS:
                    result.semantic.mood_scores[label] = 1.0
                elif label in ACTIVITIES:
                    result.semantic.activity_scores[label] = 1.0
                elif label in INTENSITIES:
                    result.semantic.intensity_scores[label] = 1.0
                elif label in STYLES:
                    result.semantic.style_scores[label] = 1.0
            result.semantic.semantic_confidence = 1.0
        return result

    def _effective_profile(self, profile: TrackProfile | None, corrections: dict[str, dict] | None = None) -> TrackProfile | None:
        if profile is None:
            return None
        corrections = corrections if corrections is not None else self._corrections()
        return self._apply_correction(profile, corrections.get(profile.id))

    @staticmethod
    def _meaning_view(lyrics, correction: dict | None = None) -> dict[str, Any]:
        state = meaning_state(lyrics, use_llm=True)
        return {
            "meaning_status": state,
            "meaning_error": lyrics.meaning_error if lyrics else "",
            "transcription_error": lyrics.transcription_error if lyrics else "",
            "lyrics_status": {
                "MEANING_READY": "ready",
                "MEANING_LOW_CONFIDENCE": "low_confidence",
                "MEANING_INVALID": "failed",
                "TRANSCRIPT_READY_MEANING_MISSING": "meaning_missing",
                "TRANSCRIPTION_FAILED": "failed",
                "NO_LYRICS_AVAILABLE": "unavailable",
                "NOT_ANALYZED": "not_analyzed",
                "STALE_VERSION": "stale",
            }.get(state, "uncertain"),
            "meaning_origin": "manual_correction" if correction and (correction.get("themes") or correction.get("lyrical_moods")) else (
                lyrics.meaning.meaning_source if lyrics and lyrics.meaning else None
            ),
        }

    @staticmethod
    def _metadata_view(metadata: TrackMetadata, status: str, profile: TrackProfile | None = None) -> dict[str, Any]:
        semantic = profile.semantic if profile else None
        lyrics = profile.lyrics if profile else None
        meaning = lyrics.meaning if lyrics else None
        meaning_view = LocalAppService._meaning_view(lyrics, profile.manual_correction if profile else None)
        return {
            "filepath": metadata.filepath,
            "filename": Path(metadata.filepath).name,
            "title": metadata.title or Path(metadata.filepath).stem,
            "artist": metadata.artist,
            "album": metadata.album,
            "duration_sec": round(metadata.duration_sec, 2),
            "sample_rate": metadata.sample_rate,
            "channels": metadata.channels,
            "format": metadata.format,
            "status": status,
            "bpm": round(profile.bpm, 1) if profile else None,
            "key": profile.camelot if profile else None,
            "energy": round(profile.mean_energy, 3) if profile else None,
            "semantic_status": (
                "ready" if semantic and semantic.semantic_tags
                else "uncertain" if semantic else "not_analyzed"
            ),
            "semantic_tags": list(semantic.semantic_tags[:4]) if semantic else [],
            "semantic_confidence": round(semantic.semantic_confidence, 3) if semantic else None,
            "semantic_reliability": semantic.reliability_by_group if semantic else {},
            "semantic_variability": round(semantic.semantic_variability, 4) if semantic else None,
            "semantic_windows": semantic.sample_windows if semantic else [],
            **meaning_view,
            "lyrics_source": lyrics.source if lyrics else None,
            "lyrics_language": lyrics.language if lyrics else None,
            "transcription_confidence": round(lyrics.transcription_confidence, 3) if lyrics else None,
            "meaning_themes": (meaning.primary_themes + meaning.secondary_themes)[:5] if meaning else [],
            "lyrical_moods": meaning.lyrical_moods[:4] if meaning else [],
            "meaning_confidence": round(meaning.meaning_confidence, 3) if meaning else None,
            "manual_correction": profile.manual_correction if profile else {},
        }

    def scan_library(self, library_path: str | None = None) -> dict[str, Any]:
        path = self.resolve_library(library_path)
        from djenius.audio.semantic import SEMANTIC_ANALYSIS_VERSION, semantic_model_name
        cache = AnalysisCache(str(self.paths.cache_path))
        corrections = self._corrections()
        try:
            metadata = scan_directory(str(path))
            tracks = []
            ready = 0
            for item in metadata:
                profile = cache.get(item.filepath)
                audio_profile = profile is not None
                if profile is None:
                    # Lyrics analysis is intentionally usable before acoustic
                    # analysis finishes, so recovery state is not hidden from
                    # the library view.
                    lyrics = cache.get_lyrics_raw(item.filepath)
                    if lyrics is not None:
                        profile = TrackProfile(
                            id=compute_file_hash(item.filepath), metadata=item,
                            analysis=TrackAnalysis(), lyrics=lyrics,
                        )
                if profile and profile.semantic and (
                    profile.semantic.model_name != semantic_model_name()
                    or profile.semantic.model_version != SEMANTIC_ANALYSIS_VERSION
                ):
                    profile.semantic = None
                profile = self._effective_profile(profile, corrections)
                status = "ready" if audio_profile else "lyrics_only" if profile else (
                    "failed" if item.filepath in self._analysis_failures else "not_analyzed"
                )
                ready += audio_profile
                tracks.append(self._metadata_view(item, status, profile))
        finally:
            cache.close()
        self._remember_state(library_path=str(path))
        summary = {state: sum(track.get("meaning_status") == state for track in tracks) for state in (
            "NOT_ANALYZED", "TRANSCRIPT_READY_MEANING_MISSING", "MEANING_INVALID",
            "MEANING_LOW_CONFIDENCE", "MEANING_READY", "TRANSCRIPTION_FAILED",
            "NO_LYRICS_AVAILABLE", "STALE_VERSION",
        )}
        return {
            "library_path": str(path),
            "tracks": tracks,
            "track_count": len(tracks),
            "ready_count": ready,
            "meaning_summary": {
                "total": len(tracks),
                "counts": summary,
                "ready": summary["MEANING_READY"],
                "low_confidence": summary["MEANING_LOW_CONFIDENCE"],
                "failed": summary["MEANING_INVALID"] + summary["TRANSCRIPTION_FAILED"],
                "unavailable": summary["NO_LYRICS_AVAILABLE"],
                "missing": summary["TRANSCRIPT_READY_MEANING_MISSING"],
            },
        }

    def start_analysis(self, library_path: str | None = None, force: bool = False) -> str:
        path = self.resolve_library(library_path)
        self._remember_state(library_path=str(path))

        def action(progress: Callable[[float, str], None]) -> dict[str, Any]:
            metadata = scan_directory(str(path))
            cache = AnalysisCache(str(self.paths.cache_path))
            analyzed = skipped = failed = 0
            failures: list[dict[str, str]] = []
            try:
                for index, item in enumerate(metadata):
                    if not force and cache.has(item.filepath):
                        skipped += 1
                        progress((index + 1) / max(len(metadata), 1) * 100, f"Cached: {item.title}")
                        continue
                    try:
                        from djenius.audio.analyzer import analyze_track

                        analyze_track(item.filepath, force=force, cache=cache)
                        self._analysis_failures.pop(item.filepath, None)
                        analyzed += 1
                        progress((index + 1) / max(len(metadata), 1) * 100, f"Analyzed: {item.title}")
                    except Exception as exc:
                        self._analysis_failures[item.filepath] = str(exc)
                        failed += 1
                        failures.append({"track": item.title, "error": str(exc)})
                        progress((index + 1) / max(len(metadata), 1) * 100, f"Failed: {item.title}")
            finally:
                cache.close()
            result = self.scan_library(str(path))
            result.update({"analyzed": analyzed, "skipped": skipped, "failed": failed, "failures": failures})
            return result

        return self.submit_job("analysis", action)

    def start_semantic_analysis(self, library_path: str | None = None, force: bool = False) -> str:
        """Run the optional local CLAP layer as an explicit background job."""
        path = self.resolve_library(library_path)
        self._remember_state(library_path=str(path))

        def action(progress: Callable[[float, str], None]) -> dict[str, Any]:
            from djenius.audio.semantic import (
                SEMANTIC_ANALYSIS_VERSION, SemanticAnalyzer, semantic_model_name,
            )
            profiles = self._profiles_for_library(path)
            cache = AnalysisCache(str(self.paths.cache_path))
            analyzer = SemanticAnalyzer(model_name=semantic_model_name())
            analyzed = skipped = failed = 0
            failures: list[dict[str, str]] = []
            try:
                pending = []
                for profile in profiles:
                    if not force and cache.get_semantic(
                        profile.filepath, analyzer.model_name, SEMANTIC_ANALYSIS_VERSION,
                    ):
                        skipped += 1
                    else:
                        pending.append(profile)
                analyzer.load()
                total = max(len(pending), 1)
                for index, profile in enumerate(pending):
                    try:
                        semantic = analyzer.analyze(profile.filepath)
                        cache.put_semantic(profile.filepath, semantic)
                        analyzed += 1
                        progress((index + 1) / total * 100.0, f"Semantic tags: {profile.title}")
                    except Exception as exc:
                        failed += 1
                        failures.append({"track": profile.title, "error": str(exc)})
                        self._analysis_failures[profile.filepath] = str(exc)
                        logger.exception("Semantic analysis failed for %s", profile.filepath)
                        progress((index + 1) / total * 100.0, f"Semantic failed: {profile.title}")
            finally:
                analyzer.release()
                cache.close()
            result = self.scan_library(str(path))
            result.update({"semantic_analyzed": analyzed, "semantic_skipped": skipped, "semantic_failed": failed, "semantic_failures": failures})
            return result

        return self.submit_job("semantic", action)

    def start_lyrics_analysis(
        self,
        library_path: str | None = None,
        force: bool = False,
        use_llm: bool = True,
        use_transcription: bool = True,
        use_vocal_stem: bool = False,
        retry_unresolved: bool = False,
    ) -> str:
        """Run explicit, optional local lyrics and meaning analysis."""
        path = self.resolve_library(library_path)
        self._remember_state(library_path=str(path))

        def action(progress: Callable[[float, str], None]) -> dict[str, Any]:
            from djenius.audio.lyrics import analyze_track_lyrics
            from djenius.core.meaning import meaning_is_current, meaning_state

            metadata = scan_directory(str(path))
            cache = AnalysisCache(str(self.paths.cache_path))
            analyzed = skipped = 0
            try:
                for index, item in enumerate(metadata):
                    cached_lyrics = cache.get_lyrics_raw(item.filepath)
                    cached_state = meaning_state(cached_lyrics, use_llm=use_llm)
                    reusable_transcript = bool(cached_lyrics and cached_lyrics.text)
                    valid_meaning = meaning_is_current(cached_lyrics, use_llm=use_llm)
                    safe_no_lyrics = cached_state == "NO_LYRICS_AVAILABLE" and not use_transcription
                    safe_low_confidence = cached_state == "MEANING_LOW_CONFIDENCE" and not retry_unresolved
                    if not force and cached_lyrics is not None and (valid_meaning or safe_no_lyrics or safe_low_confidence):
                        skipped += 1
                        progress((index + 1) / max(len(metadata), 1) * 100.0, f"Meaning cached: {item.title}")
                        continue
                    if reusable_transcript and not force and cached_state in {
                        "TRANSCRIPT_READY_MEANING_MISSING", "MEANING_INVALID", "MEANING_LOW_CONFIDENCE",
                    }:
                        progress(index / max(len(metadata), 1) * 100.0, f"Reusing transcript; retrying meaning: {item.title}")
                    else:
                        progress(index / max(len(metadata), 1) * 100.0, f"Reading lyrics: {item.title}")
                    vocal_path = None
                    if use_vocal_stem:
                        from djenius.audio.stems import separate_stems, stems_available
                        if not stems_available():
                            raise ValueError("Optional stem separation is not installed. Standard lyrics analysis is still available.")
                        progress(index / max(len(metadata), 1) * 100.0, f"Separating vocals: {item.title}")
                        stem_paths = separate_stems(item.filepath, stem_dir=self.paths.data_dir / "stems")
                        vocal_path = stem_paths.get("vocals")
                    profile = analyze_track_lyrics(
                        item.filepath, use_llm=use_llm, use_transcription=use_transcription,
                        use_vocal_stem=use_vocal_stem,
                        audio_path=vocal_path,
                        existing_profile=cached_lyrics if reusable_transcript and not force else None,
                        progress=lambda message: progress(index / max(len(metadata), 1) * 100.0, f"{message}: {item.title}"),
                    )
                    cache.put_lyrics(item.filepath, profile)
                    analyzed += 1
                    progress((index + 1) / max(len(metadata), 1) * 100.0, f"Meaning saved: {item.title}")
            finally:
                cache.close()
            result = self.scan_library(str(path))
            result.update({"lyrics_analyzed": analyzed, "lyrics_skipped": skipped, "lyrics_retry_unresolved": retry_unresolved})
            return result

        return self.submit_job("lyrics", action)

    def save_track_correction(self, track_id: str, correction: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_correction(correction)
        prefs = PreferenceProfile(str(self.paths.preferences_path))
        try:
            prefs.save_track_correction(track_id, normalized)
        finally:
            prefs.close()
        return {"track_id": track_id, "correction": normalized}

    def _profiles_for_library(self, path: Path) -> list[TrackProfile]:
        metadata = scan_directory(str(path))
        from djenius.audio.semantic import SEMANTIC_ANALYSIS_VERSION, semantic_model_name
        cache = AnalysisCache(str(self.paths.cache_path))
        corrections = self._corrections()
        try:
            profiles = [cache.get(item.filepath) for item in metadata]
            for profile in profiles:
                if profile and profile.semantic and (
                    profile.semantic.model_name != semantic_model_name()
                    or profile.semantic.model_version != SEMANTIC_ANALYSIS_VERSION
                ):
                    profile.semantic = None
        finally:
            cache.close()
        profiles = [self._effective_profile(profile, corrections) for profile in profiles]
        ready = [profile for profile in profiles if profile is not None]
        if len(ready) < 2:
            missing = len(profiles) - len(ready)
            if not ready:
                raise ValueError("Analyze the library before creating a mix")
            raise ValueError(f"At least two analyzed tracks are required ({missing} not analyzed)")
        return ready

    # ---- intent and planning ----

    def _intent(
        self,
        request: str | None,
        preset: str | None,
        duration_minutes: float | None,
        use_llm: bool,
        performance_style: str | None = None,
    ) -> tuple[SetIntent, float]:
        if request and request.strip():
            intent = parse_request(request.strip(), use_llm=use_llm)
            # A free-form request is the source of truth.  An LLM may emit a
            # convenient preset-like interpretation, but that is not a user
            # selected preset and must not be presented as one in the UI.
            intent.preset = None
        elif preset and preset != "auto":
            intent = make_intent(preset)
        else:
            intent = SetIntent(target_duration_sec=(duration_minutes or 30.0) * 60.0)
        if duration_minutes is not None and duration_minutes > 0:
            intent.target_duration_sec = duration_minutes * 60.0
        requested_style = (performance_style or "auto").strip().lower()
        if requested_style not in {"auto", "classic", "smooth", "club", "quick_mix", "mashup", "story", "radio", "experimental"}:
            raise ValueError("Unknown performance style")
        if requested_style != "auto":
            intent.performance_style = requested_style
            intent.performance_mode = "segment" if requested_style in {"quick_mix", "club", "mashup", "experimental"} else "classic"
        elif request and re.search(r"\b(?:quick|short|rapid|showcase)\b", request.lower()) and "mix" in request.lower():
            intent.performance_style = "quick_mix"
            intent.performance_mode = "segment"
        elif request and re.search(r"\bclub(?:[- ]style)?(?:\s+performance)?\b", request.lower()):
            intent.performance_style = "club"
            intent.performance_mode = "segment"
        elif request and re.search(r"\b(?:experimental|mashup|remix(?:-style|er)?)\b", request.lower()):
            intent.performance_style = "experimental" if "experimental" in request.lower() or "remix" in request.lower() else "mashup"
            intent.performance_mode = "segment"
        elif request and re.search(r"\bstory(?:[- ]like)?\s+(?:set|performance|mix)\b", request.lower()):
            intent.performance_style = "story"
            intent.performance_mode = "classic"
        else:
            intent.performance_style = "classic"
            intent.performance_mode = "classic"
        # Apply V10 performance modifiers after parsing so an explicit
        # request remains visible even when Ollama omits optional fields.
        if request:
            lowered = request.lower()
            if re.search(r"\b(?:lots? of different|many different|more variety|diverse|varied|showcase)\b", lowered):
                intent.desired_variety = 0.85
            if re.search(r"\b(?:avoid|fewer|no)\s+(?:repeats?|reprises?)\b", lowered):
                intent.reprise_preference = "avoid"
            if re.search(r"\b(?:callback|return to|reprise)\b", lowered):
                intent.reprise_preference = "callback"
            if re.search(r"\b(?:do not|don't|no|without|never|avoid)\s+(?:use\s+)?(?:any\s+)?(?:mashups?|layered(?:\s+vocals?)?)\b", lowered):
                intent.layering_preference = "off"
            elif re.search(r"\b(?:mashup|layered|creative mashup)\b", lowered):
                intent.layering_preference = "prefer"
        errors = intent.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return intent, intent.target_duration_sec

    @staticmethod
    def plan_view(plan_id: str, plan: SetPlan) -> dict[str, Any]:
        tracks = []
        for index, track in enumerate(plan.tracks):
            meaning_view = LocalAppService._meaning_view(
                track.lyrics, track.manual_correction,
            )
            tracks.append({
                "position": index + 1,
                "id": track.id,
                "title": track.title,
                "artist": track.metadata.artist,
                "filename": Path(track.filepath).name,
                "duration_sec": round(track.duration_sec, 2),
                "bpm": round(track.bpm, 1),
                "key": track.analysis.key,
                "camelot": track.camelot,
                "energy": round(track.mean_energy, 3),
                "semantic_tags": list(track.semantic.semantic_tags[:5]) if track.semantic else [],
                "semantic_status": (
                    "ready" if track.semantic and track.semantic.semantic_tags
                    else "uncertain" if track.semantic else "not_analyzed"
                ),
                "semantic_confidence": round(track.semantic.semantic_confidence, 3) if track.semantic else None,
                "moods": sorted(track.semantic.mood_scores, key=track.semantic.mood_scores.get, reverse=True)[:3] if track.semantic else [],
                "activity": sorted(track.semantic.activity_scores, key=track.semantic.activity_scores.get, reverse=True)[:2] if track.semantic else [],
                "meaning_themes": (track.lyrics.meaning.primary_themes + track.lyrics.meaning.secondary_themes)[:5] if track.lyrics and track.lyrics.meaning else [],
                "lyrical_moods": track.lyrics.meaning.lyrical_moods[:4] if track.lyrics and track.lyrics.meaning else [],
                **meaning_view,
                "lyrics_source": track.lyrics.source if track.lyrics else None,
                "lyrics_language": track.lyrics.language if track.lyrics else None,
                "meaning_confidence": round(track.lyrics.meaning.meaning_confidence, 3) if track.lyrics and track.lyrics.meaning else None,
                "manual_correction": track.manual_correction,
                "intent_fit": plan.intent_track_scores.get(track.id),
            })
        transitions = []
        for index, transition in enumerate(plan.transitions):
            source = plan.tracks[index]
            target = plan.tracks[index + 1]
            transitions.append({
                "position": index + 1,
                "source_track_id": source.id,
                "target_track_id": target.id,
                "source_title": source.title,
                "target_title": target.title,
                "type": transition.transition_type.value,
                "duration_sec": round(transition.overlap_duration, 2),
                "source_exit_sec": round(transition.source_exit_time, 2),
                "target_entry_sec": round(transition.target_entry_time, 2),
                "confidence": round(transition.confidence, 3),
                "explanation": transition.reasoning or explain_transition(transition),
            })
        return {
            "id": plan_id,
            "tracks": tracks,
            "transitions": transitions,
            "total_duration_sec": round(plan.total_duration_sec, 1),
            "target_duration_sec": round(plan.target_duration_sec, 1),
            "energy_profile": plan.energy_profile.value,
            "avg_transition_confidence": round(plan.avg_transition_confidence, 3),
            "score": round(plan.score, 3),
            "reasons": list(plan.human_readable_reasons),
            "intent_coverage": _json_safe(plan.intent_coverage),
            "intent_candidate_pool_ids": list(plan.intent_candidate_pool_ids),
            "intent_excluded_track_ids": list(plan.intent_excluded_track_ids),
            "intent_relaxation_steps": list(plan.intent_relaxation_steps),
            "intent": LocalAppService._intent_view(plan.intent_used),
            "performance_mode": plan.performance_mode,
            "performance_style": plan.performance_style,
            "timeline": plan.performance_timeline.to_dict() if plan.performance_timeline else None,
            "markers": [],
        }

    @staticmethod
    def _intent_view(intent: SetIntent | None) -> dict[str, Any] | None:
        if intent is None:
            return None
        source_labels = {
            "manual": "Manual",
            "nl_parser": "Deterministic",
            "llm": "Ollama",
            "llm_fallback": "Ollama failed -> deterministic fallback",
        }
        return {
            "source": source_labels.get(intent.source, intent.source),
            "source_code": intent.source,
            "model": intent.parser_model,
            "latency_ms": intent.parser_latency_ms,
            "error": intent.parser_error,
            "moods": list(intent.desired_moods),
            "avoid_moods": list(intent.avoid_moods),
            "activity": list(intent.desired_activity),
            "trajectory": list(intent.mood_trajectory),
            "themes": list(intent.desired_themes),
            "avoid_themes": list(intent.avoid_themes),
            "lyrical_moods": list(intent.desired_lyrical_moods),
            "avoid_lyrical_moods": list(intent.avoid_lyrical_moods),
            "meaning_trajectory": list(intent.meaning_trajectory),
            "preset": intent.preset,
            "energy_profile": intent.effective_energy_profile().value,
            "transition_style": intent.effective_transition_style(),
            "vocal_preference": intent.effective_vocal_preference(),
            "duration_sec": round(intent.target_duration_sec, 1),
            "performance_mode": intent.performance_mode,
            "performance_style": intent.performance_style,
            "allow_creative_fx": intent.allow_creative_fx,
            "technique_intensity": intent.technique_intensity,
        }

    def start_plan(
        self,
        library_path: str | None = None,
        request: str | None = None,
        preset: str | None = None,
        duration_minutes: float | None = None,
        use_llm: bool = False,
        seed: int | None = None,
        performance_style: str | None = None,
    ) -> str:
        path = self.resolve_library(library_path)
        self._remember_state(
            library_path=str(path),
            preset=preset or self._state.get("preset", "balanced"),
            duration_minutes=duration_minutes,
            use_llm=use_llm,
            performance_style=performance_style,
        )

        def action(progress: Callable[[float, str], None]) -> dict[str, Any]:
            progress(5, "Loading analyzed tracks")
            profiles = self._profiles_for_library(path)
            progress(30, "Parsing set request")
            intent, duration = self._intent(request, preset, duration_minutes, use_llm, performance_style)
            self._remember_state(
                ollama_last_request={
                    "source": intent.source,
                    "model": intent.parser_model,
                    "latency_ms": intent.parser_latency_ms,
                    "error": intent.parser_error,
                    "at": time.time(),
                }
            )
            progress(45, "Planning musical order and performance timeline")
            prefs = PreferenceProfile(str(self.paths.preferences_path))
            try:
                preference_bonuses = prefs.get_scoring_bonuses()
            finally:
                prefs.close()
            plan = plan_set(
                tracks=profiles,
                target_duration_sec=duration,
                intent=intent,
                preference_bonuses=preference_bonuses,
                seed=seed,
            )
            from djenius.core.explanations import explain_set_plan

            plan.human_readable_reasons = explain_set_plan(plan)
            plan_id = uuid.uuid4().hex
            with self._lock:
                self._plans[plan_id] = plan
                self._plan_libraries[plan_id] = str(path)
            progress(100, f"Proposed {len(plan.tracks)} tracks")
            return self.plan_view(plan_id, plan)

        return self.submit_job("planning", action)

    def get_plan(self, plan_id: str) -> SetPlan:
        with self._lock:
            try:
                return self._plans[plan_id]
            except KeyError as exc:
                raise KeyError("Plan has expired; create it again") from exc

    def edit_plan(self, plan_id: str, ordered_ids: list[str]) -> dict[str, Any]:
        current = self.get_plan(plan_id)
        if not ordered_ids:
            raise ValueError("An edited plan must contain tracks")
        if current.performance_timeline and set(ordered_ids).issubset({
            appearance.id for appearance in current.performance_timeline.appearances
        }):
            updated_timeline = reorder_performance_timeline(
                copy.deepcopy(current.performance_timeline),
                ordered_ids,
                {track.id: track.duration_sec for track in current.tracks},
            )
            updated = copy.deepcopy(current)
            updated.performance_timeline = updated_timeline
            updated.total_duration_sec = updated_timeline.total_duration_sec
            updated.tracks = []
            for appearance in updated_timeline.appearances:
                track = next(track for track in current.tracks if track.id == appearance.segment.track_id)
                if track not in updated.tracks:
                    updated.tracks.append(track)
            updated.human_readable_reasons = list(current.human_readable_reasons) + [
                "Performance appearances reordered and revalidated."
            ]
            with self._lock:
                self._plans[plan_id] = updated
            return self.plan_view(plan_id, updated)
        updated = plan_ordered_set(
            tracks=current.tracks,
            ordered_ids=ordered_ids,
            target_duration_sec=current.target_duration_sec,
            intent=current.intent_used,
        )
        from djenius.core.explanations import explain_set_plan

        updated.human_readable_reasons = explain_set_plan(updated)
        with self._lock:
            self._plans[plan_id] = updated
        return self.plan_view(plan_id, updated)

    def regenerate_plan(self, plan_id: str) -> dict[str, Any]:
        current = self.get_plan(plan_id)
        path = Path(self._plan_libraries[plan_id])
        profiles = self._profiles_for_library(path)
        prefs = PreferenceProfile(str(self.paths.preferences_path))
        try:
            bonuses = prefs.get_scoring_bonuses()
        finally:
            prefs.close()
        previous_ids = {track.id for track in current.tracks}
        previous_edges = {
            (current.tracks[index].id, current.tracks[index + 1].id)
            for index in range(len(current.tracks) - 1)
        }
        attempt = int(self._state.get("regeneration_attempt", 0)) + 1
        self._remember_state(regeneration_attempt=attempt)
        updated = plan_set(
            tracks=profiles,
            target_duration_sec=current.target_duration_sec,
            intent=current.intent_used,
            preference_bonuses=bonuses,
            seed=attempt,
            avoid_track_ids=previous_ids,
            avoid_edges=previous_edges,
        )
        from djenius.core.explanations import explain_set_plan

        updated.human_readable_reasons = explain_set_plan(updated)
        with self._lock:
            self._plans[plan_id] = updated
        return self.plan_view(plan_id, updated)

    # ---- rendering and outputs ----

    def _render_markers(self, diagnostics_path: str | None) -> list[dict[str, Any]]:
        if not diagnostics_path:
            return []
        try:
            diagnostics = self._load_json(Path(diagnostics_path), {})
            return [
                {
                    "time_sec": event.get("mix_start_sec", 0.0),
                    "source_title": event.get("source_track_title", event.get("track_title", event.get("vocal_track_id", ""))),
                    "target_title": event.get("target_track_title", event.get("track_title", event.get("instrumental_track_id", ""))),
                    "type": event.get("section_type", event.get("transition_type", "")),
                }
                for event in diagnostics.get("events", [])
                if event.get("type") in {"transition", "performance_transition", "appearance", "layered"}
            ]
        except Exception:
            return []

    def start_render(self, plan_id: str, target_lufs: float = -14.0, use_stems: bool = False) -> str:
        plan = self.get_plan(plan_id)
        output_name = f"mix-{plan_id[:10]}-{int(time.time())}.wav"
        output_path = self.paths.output_dir / output_name

        def action(progress: Callable[[float, str], None]) -> dict[str, Any]:
            if use_stems:
                from djenius.audio.stems import separate_stems, stems_available

                if not stems_available():
                    raise ValueError("Optional stem separation is not installed. Standard DJ mixing is still available.")
                stem_dir = self.paths.data_dir / "stems"
                candidates = {
                    track.id
                    for transition in plan.transitions
                    if transition.transition_type.value in {"bass_swap", "mashup"}
                    for track in plan.tracks
                    if track.id in {transition.source_track_id, transition.target_track_id}
                }
                if plan.performance_timeline:
                    appearance_by_id = {
                        item.id: item for item in plan.performance_timeline.appearances
                    }
                    for transition in plan.performance_timeline.transitions:
                        if any(item.get("type") == "target_percussion_tease" for item in transition.preparation_operations):
                            for appearance_id in (transition.source_appearance_id, transition.target_appearance_id):
                                appearance = appearance_by_id.get(appearance_id)
                                if appearance:
                                    candidates.add(appearance.segment.track_id)
                if plan.performance_timeline and plan.intent_used and plan.intent_used.layering_preference != "off":
                    from djenius.core.layering import layer_candidate_track_ids

                    candidates.update(layer_candidate_track_ids(plan))
                for index, track in enumerate(plan.tracks):
                    if track.id not in candidates:
                        continue
                    progress(2 + index / max(len(plan.tracks), 1) * 18, f"Preparing stems: {track.title}")
                    track.analysis.stems = separate_stems(track.filepath, stem_dir=stem_dir)

            if plan.performance_timeline:
                from djenius.audio.performance_renderer import render_performance_mix
                stem_audio = None
                if use_stems:
                    from djenius.audio.stems import load_stems
                    layer_ids: set[str] = set()
                    if plan.intent_used and plan.intent_used.layering_preference != "off":
                        from djenius.core.layering import prepare_layered_events

                        # The stem selector is intentionally run after preparation:
                        # a cached transcript/analysis is not enough evidence for
                        # a layered event until all required stem files exist.
                        prepare_layered_events(plan)
                        layer_ids = {
                            item.get("vocal_track_id")
                            for item in plan.performance_timeline.layered_events
                        } | {
                            item.get("instrumental_track_id")
                            for item in plan.performance_timeline.layered_events
                        }
                    # V13.2 preparation may preview target drums before the
                    # boundary.  Those stems are independent of the V11
                    # vocal-layer preference and are loaded only on request.
                    appearance_by_id = {
                        item.id: item for item in plan.performance_timeline.appearances
                    }
                    for transition in plan.performance_timeline.transitions:
                        if any(item.get("type") == "target_percussion_tease" for item in transition.preparation_operations):
                            source_appearance = appearance_by_id.get(transition.source_appearance_id)
                            target_appearance = appearance_by_id.get(transition.target_appearance_id)
                            if source_appearance:
                                layer_ids.add(source_appearance.segment.track_id)
                            if target_appearance:
                                layer_ids.add(target_appearance.segment.track_id)
                    stem_audio = {}
                    for track_id in layer_ids:
                        if not track_id:
                            continue
                        try:
                            stem_audio[track_id] = load_stems(
                                next(track.filepath for track in plan.tracks if track.id == track_id),
                                stem_dir=self.paths.data_dir / "stems",
                            )
                        except (FileNotFoundError, OSError) as exc:
                            logger.warning("Could not load stems for optional layer %s: %s", track_id, exc)
                    if not stem_audio:
                        plan.performance_timeline.layered_events = []

                result = render_performance_mix(
                    plan=plan,
                    output_path=str(output_path),
                    target_lufs=target_lufs,
                    progress_callback=progress,
                    stem_audio=stem_audio,
                )
            else:
                from djenius.audio.renderer import render_mix

                result = render_mix(
                    plan=plan,
                    output_path=str(output_path),
                    output_format="wav",
                    target_lufs=target_lufs,
                    progress_callback=progress,
                )
            record = {
                "filename": output_name,
                "created_at": time.time(),
                "duration_sec": result.get("duration_sec", 0.0),
                "plan_id": plan_id,
                "preset": plan.intent_used.preset if plan.intent_used else None,
                "request": plan.intent_used.raw_text if plan.intent_used else None,
                "performance_mode": plan.performance_mode,
                "performance_style": plan.performance_style,
                "markers": self._render_markers(result.get("timeline_diagnostics_path")),
            }
            with self._lock:
                self._output_records = [record] + [
                    item for item in self._output_records if item.get("filename") != output_name
                ]
                self._save_json(self.paths.outputs_index_path, self._output_records[:50])
            result["filename"] = output_name
            result["markers"] = record["markers"]
            return result

        return self.submit_job("render", action)

    def list_outputs(self) -> list[dict[str, Any]]:
        records = []
        known = {item.get("filename"): item for item in self._output_records}
        for path in sorted(self.paths.output_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file() or path.suffix.lower() not in {".wav", ".mp3"}:
                continue
            metadata = extract_metadata(str(path))
            record = dict(known.get(path.name, {}))
            record.update({
                "filename": path.name,
                "created_at": record.get("created_at", path.stat().st_mtime),
                "duration_sec": round(metadata.duration_sec if metadata else 0.0, 2),
                "url": f"/api/outputs/{path.name}",
            })
            records.append(record)
        return records

    # ---- feedback and system status ----

    def save_mix_feedback(self, plan_id: str, rating: int) -> dict[str, Any]:
        if not 1 <= rating <= 5:
            raise ValueError("Mix rating must be between 1 and 5")
        prefs = PreferenceProfile(str(self.paths.preferences_path))
        try:
            prefs.rate_mix(plan_id, rating)
        finally:
            prefs.close()
        return self.preferences()

    def save_transition_feedback(self, plan_id: str, position: int, rating: str | float) -> dict[str, Any]:
        plan = self.get_plan(plan_id)
        index = position - 1
        if index < 0 or index >= len(plan.transitions):
            raise ValueError("Transition position is out of range")
        transition = plan.transitions[index]
        if isinstance(rating, str):
            labels = {"great": 1.0, "good": 0.7, "bad": -1.0, "too abrupt": -0.6, "too long": -0.4, "too weak": -0.3}
            if rating not in labels:
                raise ValueError("Unknown transition rating")
            score = labels[rating]
        else:
            score = float(rating)
        prefs = PreferenceProfile(str(self.paths.preferences_path))
        try:
            prefs.rate_transition(
                transition.source_track_id,
                transition.target_track_id,
                transition.transition_type.value,
                score,
            )
        finally:
            prefs.close()
        return self.preferences()

    def save_track_feedback(self, track_id: str, liked: bool) -> dict[str, Any]:
        prefs = PreferenceProfile(str(self.paths.preferences_path))
        try:
            (prefs.like_track if liked else prefs.dislike_track)(track_id)
        finally:
            prefs.close()
        return self.preferences()

    def preferences(self) -> dict[str, Any]:
        prefs = PreferenceProfile(str(self.paths.preferences_path))
        try:
            transition_types = prefs.get_preferred_transition_types(min_samples=1)
            return {
                "liked_tracks": prefs.get_liked_tracks(),
                "disliked_tracks": prefs.get_disliked_tracks(),
                "preferred_transition_styles": transition_types,
                "bpm_range": prefs.get_bpm_preference(),
                "energy_range": prefs.get_energy_preference(),
                "mix_ratings": prefs.get_mix_ratings(),
            }
        finally:
            prefs.close()

    def system_status(self) -> dict[str, Any]:
        from djenius.audio.stems import gpu_available, stems_available
        from djenius.audio.semantic import semantic_dependencies_available, semantic_model_name
        from djenius.audio.lyrics import lyrics_dependencies_available, DEFAULT_TRANSCRIPTION_MODEL

        ollama = False
        try:
            import urllib.request

            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.5) as response:
                ollama = response.status == 200
        except Exception:
            pass
        preference_db = True
        try:
            prefs = PreferenceProfile(str(self.paths.preferences_path))
            prefs.close()
        except Exception:
            preference_db = False
        stem_cache_dir = self.paths.data_dir / "stems"
        stem_cache_count = len(list(stem_cache_dir.glob("*_vocals.wav"))) if stem_cache_dir.is_dir() else 0
        return {
            "core": "ready",
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None,
            "demucs": stems_available(),
            "layered_performance": stems_available(),
            "stem_cache_count": stem_cache_count,
            "gpu": gpu_available(),
            "ollama": ollama,
            "ollama_model": self._state.get("ollama_last_request", {}).get("model") or ollama_model_name(),
            "ollama_last_request": self._state.get("ollama_last_request"),
            "semantic": semantic_dependencies_available(),
            "semantic_model": semantic_model_name(),
            "lyrics": lyrics_dependencies_available(),
            "lyrics_backend": "faster-whisper" if lyrics_dependencies_available() else None,
            "lyrics_model": DEFAULT_TRANSCRIPTION_MODEL,
            "preference_db": preference_db,
        }

    def app_state(self) -> dict[str, Any]:
        return {
            "library_path": self._state.get("library_path"),
            "preset": self._state.get("preset", "balanced"),
            "duration_minutes": self._state.get("duration_minutes", 30),
            "use_llm": self._state.get("use_llm", False),
            "ollama_last_request": self._state.get("ollama_last_request"),
            "presets": ALL_PRESETS,
            "outputs": self.list_outputs(),
        }
