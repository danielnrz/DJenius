"""Small, validated helpers for local lyrics/song-meaning interpretation."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

from djenius.core.models import LyricsMeaningProfile

logger = logging.getLogger(__name__)

THEMES = (
    "love", "romance", "heartbreak", "breakup", "longing", "nostalgia",
    "friendship", "celebration", "party", "confidence", "success",
    "struggle", "anger", "hope", "healing", "freedom", "loneliness",
    "loss", "self_reflection", "motivation",
)
LYRICAL_MOODS = (
    "happy", "sad", "melancholic", "romantic", "hopeful", "angry",
    "nostalgic", "celebratory", "confident", "dark",
)
RELATIONSHIP_CONTEXTS = {"", "romantic", "friendship", "family", "self", "general"}
MEANING_ANALYSIS_VERSION = "2"
MEANING_MODEL_VERSION = "validated-json-v2"
_DEFAULT_MODEL = os.environ.get("DJENIUS_OLLAMA_MODEL", "granite4:3b")


def meaning_model_name() -> str:
    """Return the currently configured local meaning interpreter."""
    return _DEFAULT_MODEL


def meaning_state(profile, *, use_llm: bool = True) -> str:
    """Classify lyrics and meaning independently for UI/retry decisions."""
    if profile is None:
        return "NOT_ANALYZED"
    from djenius.db.cache import LYRICS_ANALYSIS_VERSION
    if getattr(profile, "analysis_version", "") != LYRICS_ANALYSIS_VERSION:
        return "STALE_VERSION"
    if profile.source == "unavailable" and not profile.text:
        return "TRANSCRIPTION_FAILED" if profile.transcription_error else "NO_LYRICS_AVAILABLE"
    if not profile.text:
        return "TRANSCRIPTION_FAILED"
    expected_model = meaning_model_name() if use_llm else "deterministic-keyword-fallback"
    meaning = profile.meaning
    if meaning is None:
        return "TRANSCRIPT_READY_MEANING_MISSING"
    if (
        profile.meaning_error
        or profile.meaning_analysis_version != MEANING_ANALYSIS_VERSION
        or meaning.model_version != MEANING_MODEL_VERSION
        or meaning.model_name != expected_model
    ):
        return "MEANING_INVALID"
    if meaning.meaning_confidence < 0.35 or profile.transcription_confidence < 0.35:
        return "MEANING_LOW_CONFIDENCE"
    return "MEANING_READY"


def meaning_is_current(profile, *, use_llm: bool = True) -> bool:
    return meaning_state(profile, use_llm=use_llm) in {"MEANING_READY", "MEANING_LOW_CONFIDENCE"}


def _bounded(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def validate_meaning_data(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the small LLM contract and reject unknown labels."""
    if not isinstance(data, dict):
        raise ValueError("Meaning response must be a JSON object")
    for field in ("primary_themes", "secondary_themes", "lyrical_moods"):
        values = data.get(field, [])
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValueError(f"{field} must be a list of strings")
        allowed = THEMES if "theme" in field else LYRICAL_MOODS
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            raise ValueError(f"Unknown labels in {field}: {', '.join(unknown)}")
        data[field] = list(dict.fromkeys(values))[:6]
    relationship = data.get("relationship_context", "")
    if relationship not in RELATIONSHIP_CONTEXTS:
        raise ValueError(f"Unknown relationship_context: {relationship}")
    data["relationship_context"] = relationship
    data["emotional_valence"] = _bounded(data.get("emotional_valence", 0.0), -1.0, 1.0)
    for field in ("emotional_intensity", "party_context", "hopefulness", "sadness", "romance", "anger", "celebration", "meaning_confidence"):
        data[field] = _bounded(data.get(field, 0.0))
    return data


def meaning_from_json(data: dict[str, Any], *, model: str, source: str = "ollama") -> LyricsMeaningProfile:
    values = validate_meaning_data(dict(data))
    return LyricsMeaningProfile(
        model_name=model,
        model_version=MEANING_MODEL_VERSION,
        primary_themes=values["primary_themes"],
        secondary_themes=values["secondary_themes"],
        lyrical_moods=values["lyrical_moods"],
        emotional_valence=values["emotional_valence"],
        emotional_intensity=values["emotional_intensity"],
        relationship_context=values["relationship_context"],
        party_context=values["party_context"],
        hopefulness=values["hopefulness"],
        sadness=values["sadness"],
        romance=values["romance"],
        anger=values["anger"],
        celebration=values["celebration"],
        meaning_confidence=values["meaning_confidence"],
        meaning_source=source,
        analyzed_at=time.time(),
    )


def _extract_json(content: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("Meaning response contained no JSON object")
    return json.loads(match.group())


def parse_lyrics_meaning(
    text: str,
    language: str = "",
    model: str = _DEFAULT_MODEL,
    url: str = "http://localhost:11434",
    timeout: float = 45.0,
) -> tuple[LyricsMeaningProfile, float]:
    """Ask only the local Ollama endpoint to classify supplied lyrics."""
    if not text.strip():
        raise ValueError("Cannot interpret empty lyrics")
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("Local meaning interpretation requires httpx") from exc
    system = f"""You classify the overall meaning of song lyrics. Return ONLY valid JSON.
Language hint: {language or 'unknown'}.
Allowed primary_themes/secondary_themes: {', '.join(THEMES)}.
Allowed lyrical_moods: {', '.join(LYRICAL_MOODS)}.
relationship_context must be one of: {', '.join(sorted(RELATIONSHIP_CONTEXTS - {''}))}, or empty string.
Use numeric emotional_valence in [-1,1], all other numeric fields in [0,1].
Required fields: primary_themes, secondary_themes, lyrical_moods, emotional_valence,
emotional_intensity, relationship_context, party_context, hopefulness, sadness,
romance, anger, celebration, meaning_confidence.
Scores are estimates; lower meaning_confidence when lyrics are incomplete or ambiguous."""
    started = time.perf_counter()
    response = httpx.post(
        f"{url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text[:24000]},
            ],
            "stream": False,
            "format": "json",
            # Meaning analysis is short-lived; do not keep Ollama resident
            # beside Whisper, CLAP, or Demucs on an 8 GB GPU.
            "keep_alive": 0,
            "options": {"temperature": 0.0, "num_predict": 384},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    return meaning_from_json(_extract_json(content), model=model), round((time.perf_counter() - started) * 1000.0, 1)


def deterministic_meaning(text: str, language: str = "") -> LyricsMeaningProfile:
    """Conservative offline fallback used when Ollama is unavailable."""
    lowered = text.lower()
    groups = {
        "heartbreak": ("heartbreak", "broken heart", "break up", "breakup", "goodbye"),
        "love": ("love", "lover", "darling", "kiss"),
        "romance": ("romance", "romantic", "together", "forever"),
        "longing": ("miss you", "missing you", "alone", "without you"),
        "party": ("party", "dance", "tonight", "celebrate"),
        "hope": ("hope", "heal", "better", "tomorrow", "rise"),
        "anger": ("hate", "angry", "fight", "rage"),
        "loss": ("lost", "loss", "gone", "dead"),
        "freedom": ("free", "freedom", "escape"),
    }
    counts = {label: sum(lowered.count(term) for term in terms) for label, terms in groups.items()}
    themes = [label for label, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count][:6]
    sad = min(1.0, (counts.get("heartbreak", 0) + counts.get("longing", 0) + counts.get("loss", 0)) / 5.0)
    hope = min(1.0, counts.get("hope", 0) / 4.0)
    party = min(1.0, counts.get("party", 0) / 4.0)
    romance = min(1.0, (counts.get("love", 0) + counts.get("romance", 0)) / 6.0)
    moods = []
    if sad > 0.25: moods.extend(["sad", "melancholic"])
    if hope > 0.25: moods.append("hopeful")
    if party > 0.25: moods.extend(["happy", "celebratory"])
    if romance > 0.25: moods.append("romantic")
    if counts.get("anger", 0): moods.append("angry")
    return LyricsMeaningProfile(
        model_name="deterministic-keyword-fallback", model_version=MEANING_MODEL_VERSION,
        primary_themes=themes[:3], secondary_themes=themes[3:6], lyrical_moods=list(dict.fromkeys(moods))[:4],
        emotional_valence=max(-1.0, min(1.0, hope + party - sad - counts.get("anger", 0) / 5.0)),
        emotional_intensity=min(1.0, (sum(counts.values()) / 12.0)),
        party_context=party, hopefulness=hope, sadness=sad, romance=romance,
        anger=min(1.0, counts.get("anger", 0) / 4.0), celebration=party,
        meaning_confidence=0.25 if themes else 0.0, meaning_source="deterministic_fallback", analyzed_at=time.time(),
    )


def meaning_similarity(first: LyricsMeaningProfile | None, second: LyricsMeaningProfile | None) -> tuple[float, float, float]:
    """Return theme, mood, and contextual continuity scores."""
    if not first or not second:
        return 0.5, 0.5, 0.5
    themes_a = set(first.primary_themes + first.secondary_themes)
    themes_b = set(second.primary_themes + second.secondary_themes)
    theme = len(themes_a & themes_b) / max(len(themes_a | themes_b), 1)
    mood_a, mood_b = set(first.lyrical_moods), set(second.lyrical_moods)
    mood = len(mood_a & mood_b) / max(len(mood_a | mood_b), 1)
    context = 1.0 - min(1.0, abs(first.party_context - second.party_context) * 0.7 + abs(first.sadness - second.sadness) * 0.3)
    return theme, mood, context
