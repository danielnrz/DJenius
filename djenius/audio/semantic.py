"""Optional local audio/text semantic analysis.

The acoustic analyzer remains the source of timing and transition truth.  This
module only adds cached, model-estimated descriptors used as a soft planning
signal.  The model is loaded lazily by the explicit semantic-analysis job.
"""

from __future__ import annotations

import gc
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from djenius.core.models import SemanticProfile
from djenius.core.semantic import (
    score_separation,
)
from djenius.db.cache import compute_file_hash

logger = logging.getLogger(__name__)

SEMANTIC_ANALYSIS_VERSION = "2"
DEFAULT_SEMANTIC_MODEL = "laion/clap-htsat-unfused"
SEMANTIC_SAMPLE_RATE = 48_000

_PROMPT_GROUPS = {
    "mood_scores": {
        "happy": ["a happy upbeat song", "joyful cheerful music", "music with a positive happy mood"],
        "sad": ["a sad emotional song", "melancholic sorrowful music", "music with a sad emotional mood"],
        "melancholic": ["a melancholic reflective song", "wistful introspective music", "music with a melancholy feeling"],
        "romantic": ["romantic emotional music", "a love song with a romantic feeling", "warm intimate romantic music"],
        "euphoric": ["an euphoric uplifting song", "ecstatic triumphant dance music", "music that feels euphoric and celebratory"],
        "dark": ["a dark moody song", "brooding shadowy music", "music with a dark ominous feeling"],
        "dreamy": ["a dreamy atmospheric song", "hazy floating music", "music with a dreamlike feeling"],
        "calm": ["a calm peaceful song", "serene gentle music", "music with a relaxed tranquil mood"],
        "angry": ["an angry intense song", "furious confrontational music", "music with an aggressive angry mood"],
        "hopeful": ["a hopeful uplifting song", "optimistic encouraging music", "music that feels hopeful and forward-looking"],
        "nostalgic": ["a nostalgic sentimental song", "music that evokes memories", "warm wistful nostalgic music"],
    },
    "activity_scores": {
        "dance": ["danceable rhythmic music", "music for dancing", "upbeat club or dance music"],
        "party": ["music for a lively party", "celebratory social dance music", "an upbeat party song"],
        "workout": ["high-energy workout music", "driving music for exercise", "motivating music for training"],
        "driving": ["music for a road trip", "steady energetic driving music", "music that suits a long drive"],
        "late_night": ["calm late-night music", "music for a nocturnal atmosphere", "intimate music for late at night"],
        "relaxing": ["relaxing peaceful music", "music for unwinding", "gentle background music for relaxation"],
        "background": ["subtle background music", "unobtrusive music for a room", "music that stays in the background"],
        "focused": ["music for concentration", "focused productive background music", "music suitable for deep work"],
    },
    "intensity_scores": {
        "soft": ["soft gentle music", "quiet delicate music", "music with low intensity"],
        "moderate": ["moderately energetic music", "balanced medium-intensity music", "music with a steady moderate energy"],
        "energetic": ["energetic driving music", "high-energy upbeat music", "music with strong momentum"],
        "aggressive": ["aggressive intense music", "forceful hard-hitting music", "music with a confrontational intensity"],
    },
    "style_scores": {
        "electronic": ["electronic music", "synth-driven electronic production", "a song made with electronic textures"],
        "pop": ["a pop song", "mainstream melodic pop music", "catchy contemporary pop production"],
        "rock": ["a rock song", "guitar-driven rock music", "music with a rock band sound"],
        "hip_hop": ["a hip-hop song", "rhythmic rap and hip-hop music", "music with a hip-hop production style"],
        "acoustic": ["an acoustic song", "organic unplugged music", "music centered on acoustic instruments"],
        "orchestral": ["orchestral music", "cinematic symphonic music", "music with an orchestra"],
        "ambient": ["ambient atmospheric music", "spacious soundscape music", "music focused on texture and atmosphere"],
    },
}


def representative_windows(duration_sec: float, window_sec: float = 10.0) -> list[dict[str, float]]:
    """Return short windows distributed over the entire source track."""
    duration = max(0.0, float(duration_sec))
    if duration <= window_sec:
        return [{"start_sec": 0.0, "end_sec": round(duration, 3)}]
    starts = []
    for fraction in (0.10, 0.35, 0.60, 0.85):
        start = min(max(0.0, fraction * duration - window_sec / 2), duration - window_sec)
        starts.append(start)
    unique = []
    for start in starts:
        if not unique or abs(start - unique[-1]) > 0.01:
            unique.append(start)
    return [{"start_sec": round(start, 3), "end_sec": round(start + window_sec, 3)} for start in unique]


def _average_prompt_embeddings(features: np.ndarray, prompts_per_label: int) -> np.ndarray:
    """Average each label's prompt ensemble, then normalize the result."""
    if prompts_per_label <= 0 or len(features) % prompts_per_label:
        raise ValueError("Prompt features do not match the ensemble size")
    groups = features.reshape(-1, prompts_per_label, features.shape[-1]).mean(axis=1)
    norms = np.linalg.norm(groups, axis=1, keepdims=True)
    return groups / np.maximum(norms, 1e-12)


def _audio_duration(filepath: str) -> float:
    try:
        import soundfile as sf
        return float(sf.info(filepath).duration)
    except Exception:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            check=True, capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())


def semantic_dependencies_available() -> bool:
    """Return whether local CLAP inference can be imported."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


def semantic_install_hint() -> str:
    return "Install local semantic support with: pip install -e '.[semantic]'"


def semantic_model_name() -> str:
    return os.environ.get("DJENIUS_SEMANTIC_MODEL", DEFAULT_SEMANTIC_MODEL)


def _softmax(values: np.ndarray) -> np.ndarray:
    """Turn label logits into a relative vocabulary match distribution.

    The output is only comparable within this prompt group; it is not a
    calibrated probability that the track has a label.
    """
    shifted = values - np.max(values)
    weights = np.exp(shifted * 3.0)
    return weights / max(float(weights.sum()), 1e-12)


class SemanticAnalyzer:
    """Lazy CLAP audio/text scorer with a small deterministic vocabulary."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or semantic_model_name()
        self.device_name = device
        self._model = None
        self._processor = None
        self._text_features: dict[str, np.ndarray] | None = None

    @property
    def device(self) -> str:
        if self.device_name:
            return self.device_name
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

    def load(self) -> None:
        if self._model is not None:
            return
        if not semantic_dependencies_available():
            raise RuntimeError(semantic_install_hint())
        from transformers import ClapModel, ClapProcessor

        logger.info("Loading semantic model %s on %s", self.model_name, self.device)
        self._processor = ClapProcessor.from_pretrained(self.model_name)
        self._model = ClapModel.from_pretrained(self.model_name)
        self._model.to(self.device)
        self._model.eval()
        self._text_features = self._encode_text_prompts()

    def _encode_text_prompts(self) -> dict[str, np.ndarray]:
        import torch

        labels: list[str] = []
        for group in _PROMPT_GROUPS.values():
            for prompts in group.values():
                labels.extend(prompts)
        inputs = self._processor(text=labels, return_tensors="pt", padding=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items() if hasattr(value, "to")}
        with torch.inference_mode():
            features = self._model.get_text_features(**inputs)
        features = features.detach().float().cpu().numpy()
        cursor = 0
        result: dict[str, np.ndarray] = {}
        for group_name, group in _PROMPT_GROUPS.items():
            count = len(group) * len(next(iter(group.values())))
            result[group_name] = _average_prompt_embeddings(features[cursor:cursor + count], len(next(iter(group.values()))))
            cursor += count
        return result

    def _audio_windows(self, filepath: str) -> tuple[list[dict[str, float]], list[np.ndarray]]:
        import librosa
        import soundfile as sf

        duration = _audio_duration(filepath)
        windows = representative_windows(duration)
        clips = []
        for window in windows:
            start = window["start_sec"]
            length = window["end_sec"] - start
            try:
                audio, _sr = librosa.load(
                    filepath, sr=SEMANTIC_SAMPLE_RATE, mono=True,
                    offset=start, duration=length,
                )
            except Exception:
                # Keep semantic analysis aligned with the acoustic decoder
                # fallback for AAC/M4A files with misleading extensions.
                temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                temporary.close()
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-i", filepath,
                         "-t", str(length), "-ar", str(SEMANTIC_SAMPLE_RATE), "-ac", "1",
                         "-f", "wav", temporary.name],
                        check=True, capture_output=True, timeout=120,
                    )
                    audio, _sr = sf.read(temporary.name, dtype="float32")
                finally:
                    Path(temporary.name).unlink(missing_ok=True)
            if audio.size == 0:
                raise ValueError(f"Empty semantic window in audio file: {filepath}")
            clips.append(np.asarray(audio, dtype=np.float32))
        return windows, clips

    def _audio_embeddings(self, filepath: str) -> tuple[list[dict[str, float]], np.ndarray]:
        import torch

        windows, clips = self._audio_windows(filepath)
        inputs = self._processor(audio=clips, sampling_rate=SEMANTIC_SAMPLE_RATE, return_tensors="pt", padding=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items() if hasattr(value, "to")}
        with torch.inference_mode():
            features = self._model.get_audio_features(**inputs)
        features = features.detach().float().cpu().numpy()
        norms = np.linalg.norm(features, axis=1, keepdims=True)
        return windows, (features / np.maximum(norms, 1e-12)).astype(np.float32)

    @staticmethod
    def _score_windows(
        windows: list[dict[str, float]],
        audio_features: np.ndarray,
        text_features: dict[str, np.ndarray],
    ) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, dict[str, float]]]]:
        summary_raw: dict[str, dict[str, float]] = {}
        summary_relative: dict[str, dict[str, float]] = {}
        window_scores: dict[str, dict[str, dict[str, float]]] = {}
        for group_name, group_features in text_features.items():
            normalized_text = group_features / np.maximum(np.linalg.norm(group_features, axis=1, keepdims=True), 1e-12)
            labels = list(_PROMPT_GROUPS[group_name])
            raw_rows = [normalized_text @ embedding for embedding in audio_features]
            relative_rows = [_softmax(row) for row in raw_rows]
            raw_mean = np.mean(raw_rows, axis=0)
            relative_mean = np.mean(relative_rows, axis=0)
            summary_raw[group_name] = {label: round(float(value), 6) for label, value in zip(labels, raw_mean)}
            summary_relative[group_name] = {label: round(float(value), 6) for label, value in zip(labels, relative_mean)}
            window_scores[group_name] = {
                str(index): {label: round(float(value), 6) for label, value in zip(labels, row)}
                for index, row in enumerate(relative_rows)
            }
        return summary_relative, summary_raw, window_scores

    def analyze(self, filepath: str) -> SemanticProfile:
        self.load()
        try:
            windows, audio_features = self._audio_embeddings(filepath)
        except RuntimeError as exc:
            # A broken/mismatched CUDA install should not block local use.
            # Keep the model and request local, but retry on CPU once.
            if self.device != "cuda" or not any(token in str(exc).lower() for token in ("cuda", "cudnn", "cublas")):
                raise
            logger.warning("Semantic CUDA inference failed; retrying on CPU: %s", exc)
            self.device_name = "cpu"
            self._model.to("cpu")
            self._text_features = self._encode_text_prompts()
            windows, audio_features = self._audio_embeddings(filepath)
        scores, raw_scores, window_scores = self._score_windows(windows, audio_features, self._text_features or {})
        metrics: dict[str, dict[str, float | str]] = {}
        reliability_by_group: dict[str, float] = {}
        tags: list[str] = []
        for group_name, values in scores.items():
            relative_windows = list(window_scores.get(group_name, {}).values())
            metric = score_separation(values, raw_scores.get(group_name), relative_windows)
            metrics[group_name] = metric
            reliability = float(metric["reliability"])
            reliability_by_group[group_name] = round(reliability, 6)
            # A label is a displayable estimate only when the evidence is
            # concentrated, separated, and reasonably reliable across clips.
            if reliability >= 0.55 and float(metric["margin"]) >= 0.025:
                tags.append(str(metric["top_label"]))
        flat_variability = []
        for group_name, values in scores.items():
            for row in window_scores.get(group_name, {}).values():
                flat_variability.append(sum(abs(float(row.get(label, 0.0)) - float(value)) for label, value in values.items()) / max(len(values), 1))
        variability = sum(flat_variability) / len(flat_variability) if flat_variability else 0.0
        confidence = sum(reliability_by_group.values()) / max(len(reliability_by_group), 1)
        embedding = np.mean(audio_features, axis=0)
        embedding /= max(float(np.linalg.norm(embedding)), 1e-12)
        serialized_windows = []
        for index, window in enumerate(windows):
            serialized_windows.append({
                **window,
                "scores": {group: window_scores[group].get(str(index), {}) for group in window_scores},
            })
        return SemanticProfile(
            model_name=self.model_name,
            model_version=SEMANTIC_ANALYSIS_VERSION,
            embedding=embedding.tolist(),
            mood_scores=scores.get("mood_scores", {}),
            activity_scores=scores.get("activity_scores", {}),
            intensity_scores=scores.get("intensity_scores", {}),
            style_scores=scores.get("style_scores", {}),
            semantic_tags=tags[:6],
            semantic_confidence=round(float(confidence), 6),
            sample_windows=serialized_windows,
            whole_track_summary=scores,
            raw_score_summary=raw_scores,
            group_metrics=metrics,
            reliability_by_group=reliability_by_group,
            semantic_variability=round(float(variability), 6),
            score_calibration="relative_match",
            source_file_hash=compute_file_hash(filepath),
            analyzed_at=time.time(),
        )

    def release(self) -> None:
        self._text_features = None
        self._processor = None
        self._model = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


def analyze_library_semantics(
    profiles: Iterable,
    analyzer: SemanticAnalyzer,
    progress: Callable[[int, str], None] | None = None,
) -> list[tuple[str, SemanticProfile]]:
    """Analyze profiles and return `(filepath, semantic_profile)` pairs."""
    profiles = list(profiles)
    results = []
    analyzer.load()
    for index, profile in enumerate(profiles):
        result = analyzer.analyze(profile.filepath)
        results.append((profile.filepath, result))
        if progress:
            progress(index + 1, f"Semantic tags: {profile.title}")
    return results
