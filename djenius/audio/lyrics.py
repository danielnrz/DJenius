"""Optional local lyrics acquisition and transcription.

The source hierarchy is metadata, sidecar, optional local transcription, then
an explicit unavailable profile. No network lyrics lookup is performed.
"""

from __future__ import annotations

import gc
import logging
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

from djenius.core.meaning import MEANING_ANALYSIS_VERSION, parse_lyrics_meaning, deterministic_meaning
from djenius.core.models import LyricsProfile
from djenius.db.cache import compute_file_hash, LYRICS_ANALYSIS_VERSION

logger = logging.getLogger(__name__)

DEFAULT_TRANSCRIPTION_MODEL = os.environ.get("DJENIUS_TRANSCRIPTION_MODEL", "large-v3")
TRANSCRIPTION_BACKEND = "faster-whisper"


def lyrics_dependencies_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def lyrics_install_hint() -> str:
    return "Install optional local lyrics transcription with: pip install -e '.[lyrics]'"


def _tag_text(value) -> str:
    if isinstance(value, (list, tuple)):
        return "\n".join(_tag_text(item) for item in value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return str(value) if value is not None else ""


def _embedded_lyrics(filepath: str) -> str:
    try:
        import mutagen
        audio = mutagen.File(filepath)
        if audio is None:
            return ""
        tags = audio.tags or {}
        candidates = []
        for key, value in tags.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ("lyrics", "unsynced", "uslt", "sylt", "©lyr")):
                candidates.append(_tag_text(getattr(value, "text", value)))
        for key in ("lyrics", "unsyncedlyrics", "©lyr", "lyricist"):
            if key in audio:
                candidates.append(_tag_text(audio[key]))
        return max((item.strip() for item in candidates if item.strip()), key=len, default="")
    except Exception as exc:
        logger.debug("Embedded lyrics read failed for %s: %s", filepath, exc)
        return ""


def _sidecar_lyrics(filepath: str) -> tuple[str, str, list[dict]]:
    path = Path(filepath)
    for suffix in (".lrc", ".txt"):
        candidate = path.with_suffix(suffix)
        if not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        segments = []
        for line in text.splitlines():
            stamps = re.findall(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]", line)
            clean = re.sub(r"\[\d{1,2}:\d{2}(?:[.:]\d{1,3})?\]", "", line).strip()
            if clean:
                for minute, second, fraction in stamps or [("", "", "")]:
                    start = int(minute) * 60 + int(second) + (float(f"0.{fraction}") if fraction else 0.0) if minute else 0.0
                    segments.append({"start": round(start, 3), "text": clean})
        return text, suffix[1:], segments
    return "", "", []


def extract_lyrics(filepath: str) -> tuple[str, str, list[dict]]:
    """Return `(text, source, segments)` according to the local hierarchy."""
    embedded = _embedded_lyrics(filepath)
    if embedded:
        return embedded, "embedded", []
    sidecar, source, segments = _sidecar_lyrics(filepath)
    if sidecar:
        return sidecar, "sidecar", segments
    return "", "unavailable", []


def transcript_quality(segments: list[dict], language_probability: float = 0.0, track_duration_sec: float | None = None) -> tuple[float, bool]:
    """Estimate reliability and flag obvious music-ASR repetition hallucinations."""
    texts = [re.sub(r"\s+", " ", str(item.get("text", "")).strip().lower()) for item in segments]
    texts = [item for item in texts if item]
    if not texts:
        return 0.0, False
    normalized = [re.sub(r"[^a-z0-9\u0080-\uffff]+", " ", item).strip() for item in texts]
    repeated = len(normalized) >= 3 and len(set(normalized)) <= max(1, len(normalized) // 3)
    total_chars = sum(len(item) for item in normalized)
    duration = max(float(segments[-1].get("end", 0.0)) - float(segments[0].get("start", 0.0)), 1.0)
    density = min(1.0, total_chars / (duration * 7.0))
    logprobs = [float(item.get("avg_logprob", -1.0)) for item in segments if item.get("avg_logprob") is not None]
    acoustic = sum(math.exp(max(-10.0, min(0.0, value))) for value in logprobs) / max(len(logprobs), 1)
    coverage = 1.0
    if track_duration_sec and track_duration_sec > 0:
        coverage = min(1.0, duration / (track_duration_sec * 0.35))
    confidence = max(0.0, min(1.0, 0.30 * language_probability + 0.30 * acoustic + 0.20 * density + 0.20 * coverage))
    if repeated:
        confidence *= 0.15
    # A one-second fragment from a four-minute song is not enough evidence
    # for song-level meaning, even when its language detector is confident.
    if track_duration_sec and track_duration_sec > 0:
        observed_fraction = duration / track_duration_sec
        if observed_fraction < 0.10:
            confidence *= max(0.05, observed_fraction / 0.10)
    return round(confidence, 4), repeated


class FasterWhisperTranscriber:
    """Lazy Whisper-family transcription with CPU fallback and release()."""

    def __init__(self, model_name: str = DEFAULT_TRANSCRIPTION_MODEL, device: str | None = None):
        self.model_name = model_name
        self.device_name = device
        self._model = None

    @property
    def device(self) -> str:
        if self.device_name:
            return self.device_name
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def load(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        device = self.device
        compute = "float16" if device == "cuda" else "int8"
        try:
            self._model = WhisperModel(self.model_name, device=device, compute_type=compute)
        except Exception as exc:
            if device != "cuda":
                raise
            logger.warning("Whisper CUDA load failed; retrying on CPU: %s", exc)
            self.device_name = "cpu"
            self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")

    def transcribe(self, filepath: str) -> tuple[str, str, float, float, list[dict], bool]:
        self.load()
        def collect():
            segments, info = self._model.transcribe(
                filepath, beam_size=5, vad_filter=True, condition_on_previous_text=False,
            )
            rows = []
            for segment in segments:
                rows.append({
                    "start": round(float(segment.start), 3), "end": round(float(segment.end), 3),
                    "text": str(segment.text).strip(),
                    "avg_logprob": float(getattr(segment, "avg_logprob", -1.0)),
                    "no_speech_prob": float(getattr(segment, "no_speech_prob", 0.0)),
                })
            return rows, info
        try:
            rows, info = collect()
        except RuntimeError as exc:
            if self.device != "cuda" or not any(token in str(exc).lower() for token in ("cuda", "out of memory", "invalid device")):
                raise
            logger.warning("Whisper CUDA transcription failed; retrying on CPU: %s", exc)
            self.release()
            self.device_name = "cpu"
            self.load()
            rows, info = collect()
        language_probability = float(getattr(info, "language_probability", 0.0))
        try:
            import soundfile as sf
            track_duration = float(sf.info(filepath).duration)
        except Exception:
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", filepath],
                    capture_output=True, text=True, timeout=20, check=True,
                )
                track_duration = float(probe.stdout.strip())
            except Exception:
                track_duration = None
        confidence, repeated = transcript_quality(rows, language_probability, track_duration)
        text = " ".join(row["text"] for row in rows).strip()
        return text, str(getattr(info, "language", "")), confidence, language_probability, rows, repeated

    def release(self):
        self._model = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def analyze_track_lyrics(
    filepath: str,
    *,
    use_llm: bool = True,
    transcriber: FasterWhisperTranscriber | None = None,
    use_transcription: bool = True,
    use_vocal_stem: bool = False,
    audio_path: str | None = None,
    progress: Optional[Callable[[str], None]] = None,
) -> LyricsProfile:
    """Acquire and optionally interpret one track, never requiring lyrics."""
    started = time.time()
    text, source, segments = extract_lyrics(filepath)
    language = ""
    backend = ""
    transcription_model = ""
    confidence = 1.0 if text and source in {"embedded", "sidecar"} else 0.0
    language_confidence = 0.0
    hallucinated = False
    error = ""
    if not text and use_transcription and lyrics_dependencies_available():
        if progress: progress("Transcribing locally")
        owned = transcriber is None
        transcriber = transcriber or FasterWhisperTranscriber()
        try:
            text, language, confidence, language_confidence, segments, hallucinated = transcriber.transcribe(audio_path or filepath)
            source = "transcribed_vocal_stem" if use_vocal_stem else "transcribed_full_audio"
            backend = TRANSCRIPTION_BACKEND
            transcription_model = transcriber.model_name
            if hallucinated or confidence < 0.35:
                error = "Transcription was too uncertain for song-meaning analysis"
                text = ""
                source = "unavailable"
        except Exception as exc:
            error = str(exc)
            source = "unavailable"
        finally:
            if owned:
                transcriber.release()
            elif use_llm:
                # Keep Ollama and Whisper from competing for the 8 GB GPU.
                # transcribe() lazily reloads the model for the next track.
                transcriber.release()
    elif not text:
        error = lyrics_install_hint() if use_transcription else "No embedded or sidecar lyrics found"
    meaning = None
    meaning_error = ""
    if text:
        if progress: progress("Understanding lyrics locally")
        try:
            if use_llm:
                meaning, _latency = parse_lyrics_meaning(text, language=language)
            else:
                meaning = deterministic_meaning(text, language)
        except Exception as exc:
            meaning_error = str(exc)
            logger.warning("Local lyrics meaning interpretation failed for %s: %s", filepath, exc)
            meaning = deterministic_meaning(text, language)
            meaning.meaning_confidence = min(meaning.meaning_confidence, 0.25)
    return LyricsProfile(
        source=source, language=language, text=text, segments=segments,
        transcription_backend=backend, transcription_model=transcription_model,
            transcription_model_version="faster-whisper-1.2.1", transcription_confidence=confidence,
        language_confidence=language_confidence, hallucination_detected=hallucinated, meaning=meaning,
        source_file_hash=compute_file_hash(filepath), analysis_version=LYRICS_ANALYSIS_VERSION,
        analyzed_at=time.time(), error=meaning_error or error,
    )
