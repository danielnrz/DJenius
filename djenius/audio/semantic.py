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
from djenius.core.semantic import ACTIVITIES, INTENSITIES, MOODS, STYLES, clamp
from djenius.db.cache import compute_file_hash

logger = logging.getLogger(__name__)

SEMANTIC_ANALYSIS_VERSION = "1"
DEFAULT_SEMANTIC_MODEL = "laion/clap-htsat-unfused"
SEMANTIC_SAMPLE_RATE = 48_000

_PROMPT_GROUPS = {
    "mood_scores": {
        label: f"a {label.replace('_', ' ')} song" for label in MOODS
    },
    "activity_scores": {
        label: f"music for {label.replace('_', ' ')}" for label in ACTIVITIES
    },
    "intensity_scores": {
        label: f"{label.replace('_', ' ')} music" for label in INTENSITIES
    },
    "style_scores": {
        label: f"a {label.replace('_', ' ')} song" for label in STYLES
    },
}


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
        import torch
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
            labels.extend(group.values())
        inputs = self._processor(text=labels, return_tensors="pt", padding=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items() if hasattr(value, "to")}
        with torch.inference_mode():
            features = self._model.get_text_features(**inputs)
        features = features.detach().float().cpu().numpy()
        cursor = 0
        result: dict[str, np.ndarray] = {}
        for group_name, group in _PROMPT_GROUPS.items():
            result[group_name] = features[cursor:cursor + len(group)]
            cursor += len(group)
        return result

    def _audio_embedding(self, filepath: str) -> np.ndarray:
        import librosa
        import torch

        try:
            audio, _sr = librosa.load(filepath, sr=SEMANTIC_SAMPLE_RATE, mono=True, duration=30.0)
        except Exception:
            # Keep semantic analysis aligned with the acoustic analyzer's
            # decoder fallback for AAC/M4A files with misleading extensions.
            import soundfile as sf
            temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temporary.close()
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-i", filepath,
                     "-t", "30", "-ar", str(SEMANTIC_SAMPLE_RATE), "-ac", "1",
                     "-f", "wav", temporary.name],
                    check=True, capture_output=True, timeout=120,
                )
                audio, _sr = sf.read(temporary.name, dtype="float32")
            finally:
                Path(temporary.name).unlink(missing_ok=True)
        if audio.size == 0:
            raise ValueError(f"Empty audio file: {filepath}")
        # CLAP is trained on short windows. Average a few evenly-spaced clips
        # so a long intro or outro does not define the whole song.
        clip_size = SEMANTIC_SAMPLE_RATE * 10
        if audio.size <= clip_size:
            clips = [audio]
        else:
            starts = np.linspace(0, audio.size - clip_size, num=min(3, max(1, audio.size // clip_size)), dtype=int)
            clips = [audio[start:start + clip_size] for start in starts]
        inputs = self._processor(audio=clips, sampling_rate=SEMANTIC_SAMPLE_RATE, return_tensors="pt", padding=True)
        inputs = {key: value.to(self.device) for key, value in inputs.items() if hasattr(value, "to")}
        with torch.inference_mode():
            features = self._model.get_audio_features(**inputs)
        features = features.detach().float().cpu().numpy()
        embedding = features.mean(axis=0)
        norm = np.linalg.norm(embedding)
        return (embedding / norm if norm else embedding).astype(np.float32)

    def analyze(self, filepath: str) -> SemanticProfile:
        self.load()
        try:
            embedding = self._audio_embedding(filepath)
        except RuntimeError as exc:
            # A broken/mismatched CUDA install should not block local use.
            # Keep the model and request local, but retry on CPU once.
            if self.device != "cuda" or not any(token in str(exc).lower() for token in ("cuda", "cudnn", "cublas")):
                raise
            logger.warning("Semantic CUDA inference failed; retrying on CPU: %s", exc)
            self.device_name = "cpu"
            self._model.to("cpu")
            self._text_features = self._encode_text_prompts()
            embedding = self._audio_embedding(filepath)
        scores: dict[str, dict[str, float]] = {}
        for group_name, text_features in (self._text_features or {}).items():
            normalized_text = text_features / np.maximum(np.linalg.norm(text_features, axis=1, keepdims=True), 1e-12)
            logits = normalized_text @ embedding
            probabilities = _softmax(logits)
            labels = list(_PROMPT_GROUPS[group_name])
            scores[group_name] = {label: round(float(value), 4) for label, value in zip(labels, probabilities)}
        all_scores = [value for group in scores.values() for value in group.values()]
        # Keep the UI readable: one best estimate from each semantic family,
        # rather than presenting a long list of weak zero-shot labels.
        tags = [max(values, key=values.get) for values in scores.values() if values]
        return SemanticProfile(
            model_name=self.model_name,
            model_version=SEMANTIC_ANALYSIS_VERSION,
            embedding=embedding.tolist(),
            mood_scores=scores.get("mood_scores", {}),
            activity_scores=scores.get("activity_scores", {}),
            intensity_scores=scores.get("intensity_scores", {}),
            style_scores=scores.get("style_scores", {}),
            semantic_tags=tags[:6],
            semantic_confidence=round(float(max(all_scores) if all_scores else 0.0), 3),
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
