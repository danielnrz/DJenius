"""Natural language parser for converting user text into SetIntent.

Two parsing strategies:
1. Deterministic keyword parser - regex-based, no external dependencies
2. Ollama LLM parser - uses a local LLM for more sophisticated parsing

The deterministic parser runs first. If the user wants more sophisticated
parsing and Ollama is available, the LLM parser can be used as a fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

from djenius.core.intent import (
    SetIntent, TransitionStyle, VocalPreference,
    EnergyPreference, make_intent, PRESETS,
)
from djenius.core.models import EnergyProfile
from djenius.core.semantic import ACTIVITIES, MOODS
from djenius.core.meaning import THEMES, LYRICAL_MOODS

logger = logging.getLogger(__name__)


# ---- Deterministic Keyword Parser ----

# Keywords that map to energy profiles
_ENERGY_KEYWORDS: dict[str, EnergyProfile] = {
    "chill": EnergyProfile.STEADY,
    "steady": EnergyProfile.STEADY,
    "relaxed": EnergyProfile.STEADY,
    "calm": EnergyProfile.STEADY,
    "build": EnergyProfile.SLOW_BUILD,
    "building": EnergyProfile.SLOW_BUILD,
    "rising": EnergyProfile.SLOW_BUILD,
    "crescendo": EnergyProfile.SLOW_BUILD,
    "warm up": EnergyProfile.WARMUP_TO_PEAK,
    "warmup": EnergyProfile.WARMUP_TO_PEAK,
    "peak": EnergyProfile.WARMUP_TO_PEAK,
    "climax": EnergyProfile.WARMUP_TO_PEAK,
    "wave": EnergyProfile.WAVE,
    "ups and downs": EnergyProfile.WAVE,
    "rollercoaster": EnergyProfile.WAVE,
    "drop": EnergyProfile.COOLDOWN,
    "cooldown": EnergyProfile.COOLDOWN,
    "wind down": EnergyProfile.COOLDOWN,
    "wind-down": EnergyProfile.COOLDOWN,
    "ending": EnergyProfile.COOLDOWN,
}

# Keywords that map to transition styles
_TRANSITION_KEYWORDS: dict[str, str] = {
    "smooth": TransitionStyle.SMOOTH,
    "blend": TransitionStyle.SMOOTH,
    "seamless": TransitionStyle.SMOOTH,
    "flow": TransitionStyle.SMOOTH,
    "energetic": TransitionStyle.ENERGETIC,
    "high energy": TransitionStyle.ENERGETIC,
    "intense": TransitionStyle.ENERGETIC,
    "bangers": TransitionStyle.ENERGETIC,
    "minimal": TransitionStyle.MINIMAL,
    "simple": TransitionStyle.MINIMAL,
    "clean": TransitionStyle.MINIMAL,
    "varied": TransitionStyle.VARIED,
    "diverse": TransitionStyle.VARIED,
    "mixed": TransitionStyle.VARIED,
    "experimental": TransitionStyle.VARIED,
    "safe": TransitionStyle.SAFE,
    "reliable": TransitionStyle.SAFE,
    "no risks": TransitionStyle.SAFE,
}

# Keywords for vocal preference
_VOCAL_KEYWORDS: dict[str, str] = {
    "vocal safe": VocalPreference.VOCAL_SAFE,
    "vocal-safe": VocalPreference.VOCAL_SAFE,
    "no vocal clash": VocalPreference.VOCAL_SAFE,
    "instrumental": VocalPreference.INSTRUMENTAL_ONLY,
    "no vocals": VocalPreference.INSTRUMENTAL_ONLY,
    "vocals": VocalPreference.VOCALS_PREFERRED,
    "sing": VocalPreference.VOCALS_PREFERRED,
    "singing": VocalPreference.VOCALS_PREFERRED,
    "stem": VocalPreference.STEM_FRIENDLY,
    "stems": VocalPreference.STEM_FRIENDLY,
    "separation": VocalPreference.STEM_FRIENDLY,
}

# Keywords for transition length
_LENGTH_KEYWORDS: dict[str, str] = {
    "short": "short",
    "quick": "short",
    "fast": "short",
    "long": "long",
    "extended": "long",
    "extended transitions": "long",
    "medium": "medium",
    "standard": "medium",
    "normal": "medium",
}

# Keywords for energy levels
_ENERGY_LEVEL_KEYWORDS: dict[str, str] = {
    "low energy": EnergyPreference.LOW,
    "low-key": EnergyPreference.LOW,
    "mellow": EnergyPreference.LOW,
    "chill vibes": EnergyPreference.LOW,
    "medium energy": EnergyPreference.MEDIUM,
    "moderate": EnergyPreference.MEDIUM,
    "high energy": EnergyPreference.HIGH,
    "high-energy": EnergyPreference.HIGH,
    "pumping": EnergyPreference.HIGH,
    "intense": EnergyPreference.HIGH,
}

_MOOD_KEYWORDS = {
    "happy": "happy", "sad": "sad", "melancholic": "melancholic",
    "emotional": "melancholic", "romantic": "romantic", "euphoric": "euphoric",
    "dark": "dark", "dreamy": "dreamy", "calm": "calm", "relaxed": "calm",
    "angry": "angry", "hopeful": "hopeful", "nostalgic": "nostalgic",
}
_ACTIVITY_KEYWORDS = {
    "dance": "dance", "danceable": "dance", "dancing": "dance",
    "party": "party", "workout": "workout", "driving": "driving",
    "late night": "late_night", "late-night": "late_night",
    "relaxing": "relaxing", "background": "background", "focused": "focused",
}

_THEME_KEYWORDS = {
    "heartbreak": "heartbreak", "broken heart": "heartbreak", "breakup": "breakup",
    "break up": "breakup", "love": "love", "romantic": "romance", "romance": "romance",
    "longing": "longing", "friendship": "friendship", "party": "party",
    "celebration": "celebration", "celebrate": "celebration", "confidence": "confidence",
    "success": "success", "struggle": "struggle", "anger": "anger", "hope": "hope",
    "hopeful": "hope", "healing": "healing", "freedom": "freedom", "lonely": "loneliness",
    "loneliness": "loneliness", "loss": "loss", "self-reflection": "self_reflection",
    "motivation": "motivation",
}

# Preset keywords (map to preset names)
_PRESET_KEYWORDS: dict[str, str] = {
    "chill mix": "chill",
    "chill set": "chill",
    "chill session": "chill",
    "smooth mix": "smooth",
    "smooth set": "smooth",
    "balanced mix": "balanced",
    "balanced set": "balanced",
    "energetic mix": "energetic",
    "energetic set": "energetic",
    "peak time": "peak",
    "peak set": "peak",
    "late night": "late_night",
    "late-night": "late_night",
    "vocal safe": "vocal_safe",
    "vocal-safe": "vocal_safe",
    "no vocal clash": "vocal_safe",
    "experimental mix": "experimental",
    "experimental set": "experimental",
}

# BPM range patterns
_BPM_PATTERN = re.compile(
    r'(\d{2,3})\s*'
    r'(?:(?:to|-|until)\s*(\d{2,3})\s*(?:bpm|beats?)?'
    r'|(?:bpm|beats?))',
    re.IGNORECASE,
)

# Duration patterns
_DURATION_PATTERN = re.compile(
    r'(\d+)\s*(?:min(?:ute)?s?|hours?|h)',
    re.IGNORECASE,
)


def parse_deterministic(text: str) -> SetIntent:
    """Parse natural language text into a SetIntent using keyword matching.

    This is the deterministic parser: no external dependencies, fast,
    and predictable. It extracts energy profile, transition style,
    vocal preference, BPM range, duration, and preset from keywords.

    Args:
        text: Natural language description of the desired set.

    Returns:
        A SetIntent with fields populated from matched keywords.
    """
    text_lower = text.lower().strip()
    intent = SetIntent(raw_text=text, source="nl_parser")

    # 0. Check for exact preset name match first
    from djenius.core.intent import PRESETS as _PRESETS
    if text_lower in _PRESETS:
        preset_intent = make_intent(text_lower)
        for field_name in [
            "energy_profile", "transition_style", "vocal_preference",
            "target_duration_sec", "bpm_min", "bpm_max",
            "energy_min", "energy_max", "transition_length",
        ]:
            val = getattr(preset_intent, field_name)
            setattr(intent, field_name, val)
        intent.preset = text_lower
        return intent

    # 1. Check for preset keywords (highest priority)
    for keyword, preset_name in _PRESET_KEYWORDS.items():
        if keyword in text_lower:
            preset_intent = make_intent(preset_name)
            # Copy preset values into intent
            for field_name in [
                "energy_profile", "transition_style", "vocal_preference",
                "target_duration_sec", "bpm_min", "bpm_max",
                "energy_min", "energy_max", "transition_length",
            ]:
                val = getattr(preset_intent, field_name)
                setattr(intent, field_name, val)
            intent.preset = preset_name
            break  # Use first matched preset

    # 2. Energy profile keywords
    for keyword, energy_profile in _ENERGY_KEYWORDS.items():
        if keyword in text_lower:
            intent.energy_profile = energy_profile
            break

    # 3. Transition style keywords
    for keyword, style in _TRANSITION_KEYWORDS.items():
        if keyword in text_lower:
            intent.transition_style = style
            break

    # 4. Vocal preference keywords
    for keyword, pref in _VOCAL_KEYWORDS.items():
        if keyword in text_lower:
            intent.vocal_preference = pref
            break

    # 5. Transition length keywords
    for keyword, length in _LENGTH_KEYWORDS.items():
        if keyword in text_lower:
            intent.transition_length = length
            break

    # 6. Energy level keywords (fine-grained)
    for keyword, energy_pref in _ENERGY_LEVEL_KEYWORDS.items():
        if keyword in text_lower:
            e_min, e_max = EnergyPreference.to_range(energy_pref)
            intent.energy_min = e_min
            intent.energy_max = e_max
            break

    # 7. BPM range
    bpm_match = _BPM_PATTERN.search(text_lower)
    if bpm_match:
        bpm_low = int(bpm_match.group(1))
        bpm_high_str = bpm_match.group(2)
        if bpm_high_str:
            bpm_high = int(bpm_high_str)
        else:
            # Single BPM value: create a range around it
            bpm_high = bpm_low + 10
            bpm_low = max(0, bpm_low - 5)
        intent.bpm_min = float(bpm_low)
        intent.bpm_max = float(bpm_high)

    # 8. Duration
    duration_match = _DURATION_PATTERN.search(text_lower)
    if duration_match:
        value = int(duration_match.group(1))
        matched_text = duration_match.group(0)
        if "hour" in matched_text or matched_text.rstrip().endswith("h"):
            intent.target_duration_sec = float(value * 3600)
        else:
            intent.target_duration_sec = float(value * 60)

    # 9. Special modifiers
    if "no" in text_lower and "key clash" in text_lower:
        intent.avoid_key_clash = True
    if "harmonic" in text_lower:
        intent.prefer_harmonic = True
    if "no" in text_lower and "clash" in text_lower:
        intent.avoid_key_clash = True

    # 10. Stem preference
    if "stem" in text_lower:
        intent.prefer_stems = True

    # 11. Semantic descriptors. These remain soft preferences unless the
    # request explicitly uses exclusion language.
    for keyword, mood in _MOOD_KEYWORDS.items():
        if keyword in text_lower and mood not in intent.desired_moods:
            intent.desired_moods.append(mood)
    for keyword, activity in _ACTIVITY_KEYWORDS.items():
        if keyword in text_lower and activity not in intent.desired_activity:
            intent.desired_activity.append(activity)
    lyrical_mood_keywords = {
        "happy": "happy", "sad": "sad", "melancholic": "melancholic", "emotional": "melancholic",
        "romantic": "romantic", "hopeful": "hopeful", "angry": "angry", "nostalgic": "nostalgic",
        "celebratory": "celebratory", "positive lyrics": "hopeful", "positive song": "hopeful",
        "dark lyrics": "dark",
    }
    for keyword, theme in _THEME_KEYWORDS.items():
        if keyword in text_lower and theme not in intent.desired_themes:
            intent.desired_themes.append(theme)
    for keyword, mood in lyrical_mood_keywords.items():
        if keyword in text_lower and mood not in intent.desired_lyrical_moods:
            intent.desired_lyrical_moods.append(mood)
    for keyword, mood in _MOOD_KEYWORDS.items():
        if re.search(rf"(?:no|avoid|without|never)\s+(?:\w+\s+){{0,2}}{re.escape(keyword)}", text_lower):
            if mood in intent.desired_moods:
                intent.desired_moods.remove(mood)
            if mood not in intent.avoid_moods:
                intent.avoid_moods.append(mood)
    for keyword, theme in _THEME_KEYWORDS.items():
        if re.search(rf"(?:no|avoid|without|never|exclude)\s+(?:\w+\s+){{0,2}}{re.escape(keyword)}", text_lower):
            if theme in intent.desired_themes:
                intent.desired_themes.remove(theme)
            if theme not in intent.avoid_themes:
                intent.avoid_themes.append(theme)
    for keyword, mood in lyrical_mood_keywords.items():
        if re.search(rf"(?:no|avoid|without|never|exclude)\s+(?:\w+\s+){{0,2}}{re.escape(keyword)}", text_lower):
            if mood in intent.desired_lyrical_moods:
                intent.desired_lyrical_moods.remove(mood)
            if mood not in intent.avoid_lyrical_moods:
                intent.avoid_lyrical_moods.append(mood)
    trajectory_patterns = (
        (r"(?:melancholic|sad|dark).*?(?:become|turn|get|grow|move).*?(?:hopeful|happy|euphoric)", ["melancholic", "hopeful"]),
        (r"(?:melancholic|sad|dark).*?(?:become|turn|get|grow|move).*?(?:energetic|dance)", ["melancholic", "energetic"]),
        (r"(?:calm|relaxed|chill).*?(?:become|turn|get|grow|move).*?(?:energetic|euphoric|dance)", ["calm", "energetic"]),
        (r"(?:dark).*?(?:become|turn|get|grow|move).*?(?:euphoric|happy)", ["dark", "euphoric"]),
    )
    for pattern, trajectory in trajectory_patterns:
        if re.search(pattern, text_lower):
            intent.mood_trajectory = trajectory
            intent.energy_profile = intent.energy_profile or EnergyProfile.SLOW_BUILD
            break
    for pattern, trajectory in (
        (r"(?:sad|melancholic|heartbreak).*?(?:become|turn|get|grow|move).*?(?:hopeful|positive|happy|celebrat)", ["sad", "hopeful"]),
        (r"(?:heartbreak|sad).*?(?:become|turn|get|grow|move).*?(?:hope|heal)", ["sad", "hopeful"]),
    ):
        if re.search(pattern, text_lower):
            intent.meaning_trajectory = trajectory
            break

    # V10 performance language is deliberately small and deterministic.  It
    # complements (rather than controls) the audio planner.
    if re.search(r"\b(?:lots? of different|many different|more variety|diverse|varied|showcase)\b", text_lower):
        intent.desired_variety = 0.85
    elif re.search(r"\b(?:smooth|story|long-form|long form)\b", text_lower):
        intent.desired_variety = 0.15
    if re.search(r"\b(?:avoid|fewer|no)\s+(?:repeats?|reprises?)\b", text_lower):
        intent.reprise_preference = "avoid"
    elif re.search(r"\b(?:callback|return to|reprise)\b", text_lower):
        intent.reprise_preference = "callback"
    if re.search(r"\b(?:do not|don't|no|without|never|avoid)\s+(?:use\s+)?(?:any\s+)?(?:mashups?|layered(?:\s+vocals?)?)\b", text_lower):
        intent.layering_preference = "off"
    elif re.search(r"\b(?:mashup|layered|creative mashup)\b", text_lower):
        intent.layering_preference = "prefer"
    if re.search(r"\b(?:experimental|mashup)\b", text_lower):
        intent.performance_style = "experimental"
        intent.performance_mode = "segment"
    elif re.search(r"\bclub(?:[- ]style)?\b", text_lower):
        intent.performance_style = "club"
        intent.performance_mode = "segment"
    elif re.search(r"\bstory(?:[- ]like)?\b", text_lower):
        intent.performance_style = "story"
        intent.performance_mode = "classic"

    return intent


# ---- Ollama LLM Parser ----

_OLLAMA_URL = "http://localhost:11434"
_OLLAMA_MODEL = os.environ.get("DJENIUS_OLLAMA_MODEL", "granite4:3b")


def ollama_model_name() -> str:
    """Return the configured local model name shown by the app."""
    return _OLLAMA_MODEL

_SYSTEM_PROMPT = """You are a DJ intent parser. Convert the user's natural language request into a JSON SetIntent object.

Valid fields:
- preset: one of "chill", "smooth", "balanced", "energetic", "peak", "late_night", "vocal_safe", "experimental"
- energy_profile: one of "steady", "slow_build", "warmup_to_peak", "wave", "peak_early", "peak_late", "cooldown"
- transition_style: one of "smooth", "energetic", "minimal", "varied", "safe"
- vocal_preference: one of "any", "vocal_safe", "instrumental", "vocals", "stem_friendly"
- target_duration_sec: number in seconds (e.g. 1800 for 30 minutes)
- bpm_min: minimum BPM (number)
- bpm_max: maximum BPM (number)
- energy_min: minimum energy 0.0-1.0
- energy_max: maximum energy 0.0-1.0
- transition_length: one of "short", "medium", "long"
- prefer_stems: boolean
- desired_moods: list of labels from happy, sad, melancholic, romantic, euphoric, dark, dreamy, calm, angry, hopeful, nostalgic
- avoid_moods: list of mood labels to avoid
- desired_activity: list of labels from dance, party, workout, driving, late_night, relaxing, background, focused
- mood_trajectory: ordered mood labels, for example ["melancholic", "hopeful"]
- semantic_strength: number from 0.0 to 1.0
- desired_themes: list from love, romance, heartbreak, breakup, longing, nostalgia, friendship, celebration, party, confidence, success, struggle, anger, hope, healing, freedom, loneliness, loss, self_reflection, motivation
- avoid_themes: lyric themes to avoid
- desired_lyrical_moods: list from happy, sad, melancholic, romantic, hopeful, angry, nostalgic, celebratory, confident, dark
- avoid_lyrical_moods: lyric moods to avoid
- meaning_trajectory: ordered lyrical moods, for example ["sad", "hopeful"]
- lyrics_strength: number from 0.0 to 1.0
- performance_style: one of "classic", "smooth", "club", "story", "quick_mix", "experimental"
- desired_variety: number from 0.0 to 1.0
- reprise_preference: one of "avoid", "balanced", "callback"
- layering_preference: one of "off", "prefer", "required"

Return ONLY the JSON object, no explanation. If a field is not mentioned, omit it.
Example: {"preset": "chill", "energy_profile": "steady", "transition_style": "smooth"}
"""


def parse_with_ollama(
    text: str,
    model: str = _OLLAMA_MODEL,
    url: str = _OLLAMA_URL,
    timeout: float = 15.0,
) -> Optional[SetIntent]:
    """Parse natural language text into a SetIntent using Ollama LLM.

    Calls a local Ollama instance to parse the user's request.
    Returns None if Ollama is unavailable or parsing fails.

    Args:
        text: Natural language description.
        model: Ollama model name.
        url: Ollama API base URL.
        timeout: Request timeout in seconds.

    Returns:
        A SetIntent if parsing succeeds, None otherwise.
    """
    started = time.perf_counter()
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed. LLM parser unavailable. Install with: pip install httpx")
        return None

    try:
        response = httpx.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 256,
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()

        result = response.json()
        content = result.get("message", {}).get("content", "")

        # Extract JSON from response (may be wrapped in markdown code block)
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if not json_match:
            logger.warning("LLM response contained no JSON: %s", content[:200])
            return None

        data = json.loads(json_match.group())

        for field_name, allowed in (
            ("desired_themes", THEMES), ("avoid_themes", THEMES),
            ("desired_lyrical_moods", LYRICAL_MOODS),
            ("avoid_lyrical_moods", LYRICAL_MOODS),
        ):
            values = data.get(field_name, [])
            if not isinstance(values, list) or any(value not in allowed for value in values):
                logger.warning("Ollama returned invalid %s", field_name)
                return None

        # Convert duration if specified
        if "target_duration_sec" in data:
            data["target_duration_sec"] = float(data["target_duration_sec"])

        # Build SetIntent from parsed data
        intent = SetIntent(
            raw_text=text,
            source="llm",
            parser_model=model,
            parser_latency_ms=round((time.perf_counter() - started) * 1000.0, 1),
            llm_attempted=True,
            preset=data.get("preset"),
            target_duration_sec=data.get("target_duration_sec", 1800.0),
            bpm_min=data.get("bpm_min"),
            bpm_max=data.get("bpm_max"),
            energy_min=data.get("energy_min"),
            energy_max=data.get("energy_max"),
            transition_length=data.get("transition_length"),
            prefer_stems=data.get("prefer_stems"),
            desired_moods=[value for value in data.get("desired_moods", []) if value in MOODS],
            avoid_moods=[value for value in data.get("avoid_moods", []) if value in MOODS],
            desired_activity=[value for value in data.get("desired_activity", []) if value in ACTIVITIES],
            mood_trajectory=[value for value in data.get("mood_trajectory", []) if value in set(MOODS) | {"energetic"}],
            semantic_strength=float(data.get("semantic_strength", 0.7)),
            desired_themes=[value for value in data.get("desired_themes", []) if value in THEMES],
            avoid_themes=[value for value in data.get("avoid_themes", []) if value in THEMES],
            desired_lyrical_moods=[value for value in data.get("desired_lyrical_moods", []) if value in LYRICAL_MOODS],
            avoid_lyrical_moods=[value for value in data.get("avoid_lyrical_moods", []) if value in LYRICAL_MOODS],
            meaning_trajectory=[value for value in data.get("meaning_trajectory", []) if value in LYRICAL_MOODS],
            lyrics_strength=float(data.get("lyrics_strength", 0.7)),
            desired_variety=float(data.get("desired_variety", 0.35)),
            reprise_preference=data.get("reprise_preference", "balanced"),
            layering_preference=data.get("layering_preference", "off"),
            segment_density=data.get("segment_density"),
            performance_style=data.get("performance_style", "classic"),
            performance_mode=data.get("performance_mode", "classic"),
        )

        # Set enum fields
        if "energy_profile" in data:
            try:
                intent.energy_profile = EnergyProfile(data["energy_profile"])
            except ValueError:
                pass

        if "transition_style" in data:
            if data["transition_style"] in TransitionStyle.ALL:
                intent.transition_style = data["transition_style"]

        if "vocal_preference" in data:
            if data["vocal_preference"] in VocalPreference.ALL:
                intent.vocal_preference = data["vocal_preference"]

        errors = intent.validate()
        if errors:
            logger.warning("Ollama returned invalid intent: %s", "; ".join(errors))
            return None
        return intent

    except Exception as e:
        logger.warning("Ollama LLM parsing failed: %s", e)
        return None


# ---- Unified Parser ----

def parse_request(
    text: str,
    use_llm: bool = False,
    llm_model: str = _OLLAMA_MODEL,
    llm_url: str = _OLLAMA_URL,
) -> SetIntent:
    """Parse a natural language request into a SetIntent.

    Tries the deterministic parser first. If use_llm is True and
    the deterministic parser yields few results, tries the LLM parser
    as a fallback.

    Args:
        text: Natural language description.
        use_llm: Whether to try LLM parser as fallback.
        llm_model: Ollama model name.
        llm_url: Ollama API URL.

    Returns:
        A SetIntent (always non-None, may have default values).
    """
    intent = parse_deterministic(text)
    if use_llm and text.strip():
        # Explicit LLM selection means a free-form request is actually sent
        # to Ollama. Deterministic parsing then supplements omitted fields.
        llm_intent = parse_with_ollama(text, model=llm_model, url=llm_url)
        if llm_intent is not None:
            return _merge_intents(llm_intent, intent)
        intent.source = "llm_fallback"
        intent.parser_model = llm_model
        intent.llm_attempted = True
        intent.parser_error = "Ollama was unavailable or returned invalid structured intent"

    return intent


def _merge_intents(primary: SetIntent, supplement: SetIntent) -> SetIntent:
    """Keep the LLM's interpretation and fill only missing fields locally."""
    for name in (
        "preset", "energy_profile", "transition_style", "vocal_preference",
        "bpm_min", "bpm_max", "energy_min", "energy_max", "transition_length",
        "prefer_stems", "target_duration_sec",
        "desired_variety", "reprise_preference", "layering_preference", "segment_density",
    ):
        if getattr(primary, name) in (None, 1800.0) and getattr(supplement, name) not in (None, 1800.0):
            setattr(primary, name, getattr(supplement, name))
    for name in ("desired_moods", "avoid_moods", "desired_activity", "mood_trajectory", "desired_themes", "avoid_themes", "desired_lyrical_moods", "avoid_lyrical_moods", "meaning_trajectory"):
        values = list(dict.fromkeys(getattr(primary, name) + getattr(supplement, name)))
        setattr(primary, name, values)
    primary.raw_text = supplement.raw_text or primary.raw_text
    return primary


def _intent_has_substantial_info(intent: SetIntent) -> bool:
    """Check if an intent has enough information to be useful."""
    indicators = [
        intent.preset is not None,
        intent.energy_profile is not None,
        intent.transition_style is not None,
        intent.vocal_preference is not None,
        intent.bpm_min is not None,
        intent.bpm_max is not None,
        intent.energy_min is not None,
        intent.energy_max is not None,
        intent.transition_length is not None,
        len(intent.must_include) > 0,
        bool(intent.desired_moods),
        bool(intent.avoid_moods),
        bool(intent.desired_activity),
        bool(intent.mood_trajectory),
        bool(intent.desired_themes),
        bool(intent.avoid_themes),
        bool(intent.desired_lyrical_moods),
        bool(intent.avoid_lyrical_moods),
    ]
    return sum(indicators) >= 2  # At least 2 meaningful fields
