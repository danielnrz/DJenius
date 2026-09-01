"""SetIntent: the user-facing description of what kind of DJ set to build.

SetIntent is a structured dataclass that captures everything a user might
want in a set: energy profile, transition style, vocal preferences, BPM
range, duration, and track constraints. It feeds into the planner as the
single source of truth for what the user asked for.

8 built-in presets cover common use cases. Users can also supply custom
values or combine a preset with overrides.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from djenius.core.models import EnergyProfile, TransitionType
from djenius.core.semantic import SEMANTIC_LABELS
from djenius.core.meaning import THEMES, LYRICAL_MOODS


# ---- Enums for intent-specific preferences ----

class TransitionStyle:
    """Presets for which transition types to prefer.

    Each style maps to a set of allowed TransitionType values and a
    weighting that biases the planner toward certain mixes.
    """
    SMOOTH = "smooth"
    ENERGETIC = "energetic"
    MINIMAL = "minimal"
    VARIED = "varied"
    SAFE = "safe"

    ALL = {SMOOTH, ENERGETIC, MINIMAL, VARIED, SAFE}

    @staticmethod
    def allowed_types(style: str) -> list[TransitionType]:
        """Return the transition types allowed for a given style."""
        mapping = {
            TransitionStyle.SMOOTH: [
                TransitionType.BEATMATCHED_BLEND,
                TransitionType.CROSSFADE,
                TransitionType.FILTER_SWEEP,
            ],
            TransitionStyle.ENERGETIC: [
                TransitionType.BASS_SWAP,
                TransitionType.BEATMATCHED_BLEND,
                TransitionType.MASHUP,
                TransitionType.PHRASE_CUT,
            ],
            TransitionStyle.MINIMAL: [
                TransitionType.CROSSFADE,
                TransitionType.PHRASE_CUT,
                TransitionType.ECHO_OUT,
            ],
            TransitionStyle.VARIED: [
                t for t in TransitionType
            ],
            TransitionStyle.SAFE: [
                TransitionType.CROSSFADE,
                TransitionType.PHRASE_CUT,
                TransitionType.BEATMATCHED_BLEND,
                TransitionType.FILTER_SWEEP,
            ],
        }
        return mapping.get(style, list(TransitionType))


class VocalPreference:
    """Vocal handling preference."""
    ANY = "any"
    VOCAL_SAFE = "vocal_safe"       # Avoid vocal-on-vocal clashes
    INSTRUMENTAL_ONLY = "instrumental"  # Prefer tracks without vocals
    VOCALS_PREFERRED = "vocals"     # Prefer tracks with vocals
    STEM_FRIENDLY = "stem_friendly"  # Prefer tracks where stems are available

    ALL = {ANY, VOCAL_SAFE, INSTRUMENTAL_ONLY, VOCALS_PREFERRED, STEM_FRIENDLY}


class EnergyPreference:
    """Shorthand energy descriptors that map to numerical bands."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ANY = "any"

    ALL = {LOW, MEDIUM, HIGH, ANY}

    @staticmethod
    def to_range(preference: str) -> tuple[float, float]:
        """Map a preference string to (min_energy, max_energy) bounds."""
        mapping = {
            EnergyPreference.LOW: (0.0, 0.35),
            EnergyPreference.MEDIUM: (0.3, 0.65),
            EnergyPreference.HIGH: (0.6, 1.0),
            EnergyPreference.ANY: (0.0, 1.0),
        }
        return mapping.get(preference, (0.0, 1.0))


# ---- SetIntent ----

@dataclass
class SetIntent:
    """Structured description of what the user wants in a DJ set.

    All fields are optional. When a field is None, the planner uses
    defaults (no constraint on that axis). Presets fill in a coherent
    set of values that can be selectively overridden.
    """
    # -- Core request --
    preset: Optional[str] = None       # Name of a built-in preset
    energy_profile: Optional[EnergyProfile] = None
    transition_style: Optional[str] = None
    vocal_preference: Optional[str] = None

    # -- Duration --
    target_duration_sec: float = 1800.0  # 30 minutes default

    # -- BPM constraints --
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None

    # -- Energy range (finer than energy_profile) --
    energy_min: Optional[float] = None
    energy_max: Optional[float] = None

    # -- Key constraints --
    avoid_key_clash: bool = True       # Penalize key clashes
    prefer_harmonic: bool = False      # Strongly prefer harmonically compatible

    # -- Track constraints --
    must_include: list[str] = field(default_factory=list)   # Track IDs or filepaths
    must_exclude: list[str] = field(default_factory=list)   # Track IDs or filepaths

    # -- Transition length preference --
    transition_length: Optional[str] = None  # "short", "medium", "long"

    # -- Source metadata --
    raw_text: Optional[str] = None     # Original NL text if parsed from language
    source: str = "manual"             # "manual", "nl_parser", "llm", "llm_fallback"
    parser_model: Optional[str] = None
    parser_latency_ms: Optional[float] = None
    parser_error: Optional[str] = None
    llm_attempted: bool = False

    # -- Semantic preferences --
    desired_moods: list[str] = field(default_factory=list)
    avoid_moods: list[str] = field(default_factory=list)
    desired_activity: list[str] = field(default_factory=list)
    mood_trajectory: list[str] = field(default_factory=list)
    semantic_strength: float = 0.5

    # Lyrical meaning preferences. These are soft unless the request uses
    # explicit exclusion language such as "avoid" or "only".
    desired_themes: list[str] = field(default_factory=list)
    avoid_themes: list[str] = field(default_factory=list)
    desired_lyrical_moods: list[str] = field(default_factory=list)
    avoid_lyrical_moods: list[str] = field(default_factory=list)
    meaning_trajectory: list[str] = field(default_factory=list)
    lyrics_strength: float = 0.5

    # -- Stems --
    prefer_stems: Optional[bool] = None  # None = no preference

    def validate(self) -> list[str]:
        """Validate the intent and return a list of error messages.

        Returns empty list if valid.
        """
        errors = []

        if self.preset and self.preset not in PRESETS:
            valid = ", ".join(sorted(PRESETS.keys()))
            errors.append(f"Unknown preset '{self.preset}'. Valid: {valid}")

        if self.transition_style and self.transition_style not in TransitionStyle.ALL:
            valid = ", ".join(sorted(TransitionStyle.ALL))
            errors.append(f"Unknown transition_style '{self.transition_style}'. Valid: {valid}")

        if self.vocal_preference and self.vocal_preference not in VocalPreference.ALL:
            valid = ", ".join(sorted(VocalPreference.ALL))
            errors.append(f"Unknown vocal_preference '{self.vocal_preference}'. Valid: {valid}")

        for field_name in ("desired_moods", "avoid_moods", "desired_activity", "mood_trajectory"):
            values = getattr(self, field_name)
            invalid = sorted(set(values) - SEMANTIC_LABELS)
            if invalid:
                errors.append(f"Unknown semantic labels in {field_name}: {', '.join(invalid)}")

        for field_name in ("desired_themes", "avoid_themes"):
            invalid = sorted(set(getattr(self, field_name)) - set(THEMES))
            if invalid:
                errors.append(f"Unknown lyric themes in {field_name}: {', '.join(invalid)}")
        for field_name in ("desired_lyrical_moods", "avoid_lyrical_moods", "meaning_trajectory"):
            invalid = sorted(set(getattr(self, field_name)) - set(LYRICAL_MOODS))
            if invalid:
                errors.append(f"Unknown lyrical moods in {field_name}: {', '.join(invalid)}")

        if not 0.0 <= self.semantic_strength <= 1.0:
            errors.append(f"semantic_strength must be between 0.0 and 1.0, got {self.semantic_strength}")
        if not 0.0 <= self.lyrics_strength <= 1.0:
            errors.append(f"lyrics_strength must be between 0.0 and 1.0, got {self.lyrics_strength}")

        if self.bpm_min is not None and self.bpm_max is not None:
            if self.bpm_min > self.bpm_max:
                errors.append(f"bpm_min ({self.bpm_min}) must be <= bpm_max ({self.bpm_max})")

        if self.energy_min is not None and self.energy_max is not None:
            if self.energy_min > self.energy_max:
                errors.append(f"energy_min ({self.energy_min}) must be <= energy_max ({self.energy_max})")
            if not (0.0 <= self.energy_min <= 1.0):
                errors.append(f"energy_min must be between 0.0 and 1.0, got {self.energy_min}")
            if not (0.0 <= self.energy_max <= 1.0):
                errors.append(f"energy_max must be between 0.0 and 1.0, got {self.energy_max}")

        if self.target_duration_sec <= 0:
            errors.append(f"target_duration_sec must be positive, got {self.target_duration_sec}")

        if self.transition_length is not None:
            valid_lengths = {"short", "medium", "long"}
            if self.transition_length not in valid_lengths:
                errors.append(f"transition_length must be one of {valid_lengths}, got '{self.transition_length}'")

        return errors

    def effective_energy_profile(self) -> EnergyProfile:
        """Return the energy profile to use, falling back to STEADY."""
        return self.energy_profile or EnergyProfile.STEADY

    def effective_transition_style(self) -> str:
        """Return the transition style to use, falling back to SAFE."""
        return self.transition_style or TransitionStyle.SAFE

    def effective_vocal_preference(self) -> str:
        """Return the vocal preference to use, falling back to ANY."""
        return self.vocal_preference or VocalPreference.ANY

    def allowed_transition_types(self) -> list[TransitionType]:
        """Return the list of transition types this intent permits."""
        return TransitionStyle.allowed_types(self.effective_transition_style())

    def effective_transition_length_bars(self) -> tuple[int, int]:
        """Return (min_bars, max_bars) for transitions based on preference."""
        mapping = {
            "short": (4, 8),
            "medium": (8, 16),
            "long": (16, 32),
        }
        return mapping.get(self.transition_length, (4, 16))


# ---- Presets ----

# Each preset is a dict of SetIntent keyword arguments.
# Users can apply a preset and override individual fields.
PRESETS: dict[str, dict] = {
    "chill": {
        "energy_profile": EnergyProfile.STEADY,
        "transition_style": TransitionStyle.SMOOTH,
        "vocal_preference": VocalPreference.ANY,
        "target_duration_sec": 2400.0,  # 40 min
        "bpm_min": 80,
        "bpm_max": 115,
        "energy_min": 0.1,
        "energy_max": 0.45,
        "transition_length": "long",
        "avoid_key_clash": True,
    },
    "smooth": {
        "energy_profile": EnergyProfile.SLOW_BUILD,
        "transition_style": TransitionStyle.SMOOTH,
        "vocal_preference": VocalPreference.VOCAL_SAFE,
        "target_duration_sec": 2700.0,  # 45 min
        "bpm_min": 100,
        "bpm_max": 128,
        "energy_min": 0.2,
        "energy_max": 0.6,
        "transition_length": "medium",
        "avoid_key_clash": True,
    },
    "balanced": {
        "energy_profile": EnergyProfile.WARMUP_TO_PEAK,
        "transition_style": TransitionStyle.SAFE,
        "vocal_preference": VocalPreference.ANY,
        "target_duration_sec": 3600.0,  # 60 min
        "bpm_min": 110,
        "bpm_max": 135,
        "energy_min": 0.15,
        "energy_max": 0.85,
        "transition_length": "medium",
        "avoid_key_clash": True,
    },
    "energetic": {
        "energy_profile": EnergyProfile.SLOW_BUILD,
        "transition_style": TransitionStyle.ENERGETIC,
        "vocal_preference": VocalPreference.ANY,
        "target_duration_sec": 3600.0,
        "bpm_min": 120,
        "bpm_max": 140,
        "energy_min": 0.35,
        "energy_max": 0.95,
        "transition_length": "medium",
        "avoid_key_clash": True,
    },
    "peak": {
        "energy_profile": EnergyProfile.WARMUP_TO_PEAK,
        "transition_style": TransitionStyle.ENERGETIC,
        "vocal_preference": VocalPreference.ANY,
        "target_duration_sec": 5400.0,  # 90 min
        "bpm_min": 125,
        "bpm_max": 150,
        "energy_min": 0.5,
        "energy_max": 1.0,
        "transition_length": "short",
        "avoid_key_clash": True,
    },
    "late_night": {
        "energy_profile": EnergyProfile.WAVE,
        "transition_style": TransitionStyle.VARIED,
        "vocal_preference": VocalPreference.VOCAL_SAFE,
        "target_duration_sec": 5400.0,
        "bpm_min": 115,
        "bpm_max": 132,
        "energy_min": 0.25,
        "energy_max": 0.75,
        "transition_length": "medium",
        "avoid_key_clash": True,
    },
    "vocal_safe": {
        "energy_profile": EnergyProfile.STEADY,
        "transition_style": TransitionStyle.SAFE,
        "vocal_preference": VocalPreference.VOCAL_SAFE,
        "target_duration_sec": 3000.0,  # 50 min
        "bpm_min": 105,
        "bpm_max": 130,
        "energy_min": 0.2,
        "energy_max": 0.7,
        "transition_length": "medium",
        "avoid_key_clash": True,
    },
    "experimental": {
        "energy_profile": EnergyProfile.WAVE,
        "transition_style": TransitionStyle.VARIED,
        "vocal_preference": VocalPreference.ANY,
        "target_duration_sec": 3600.0,
        "bpm_min": None,
        "bpm_max": None,
        "energy_min": None,
        "energy_max": None,
        "transition_length": None,
        "avoid_key_clash": False,
        "prefer_harmonic": False,
    },
}

ALL_PRESETS: list[str] = sorted(PRESETS.keys())


def make_intent(preset: Optional[str] = None, **overrides) -> SetIntent:
    """Create a SetIntent from a preset name plus optional overrides.

    Fields in overrides take precedence over preset values.
    Fields not in overrides and not in the preset keep their
    SetIntent defaults (None).

    Args:
        preset: Name of a built-in preset (e.g. "chill", "peak").
        **overrides: Any SetIntent field name as a keyword argument.

    Returns:
        A SetIntent instance.

    Raises:
        ValueError: If the preset name is unknown.
    """
    if preset is not None and preset not in PRESETS:
        valid = ", ".join(sorted(PRESETS.keys()))
        raise ValueError(f"Unknown preset '{preset}'. Valid: {valid}")

    # Start with preset values, then apply overrides
    kwargs = {}
    if preset:
        kwargs.update(PRESETS[preset])

    # Overrides always win
    kwargs.update(overrides)

    return SetIntent(preset=preset, **kwargs)


def apply_preset(intent: SetIntent, preset_name: str) -> SetIntent:
    """Apply a preset to an existing intent, keeping any overrides.

    Creates a new SetIntent. Fields that are already set on the
    original intent (non-None) are preserved. Fields that are None
    get filled from the preset.
    """
    if preset_name not in PRESETS:
        valid = ", ".join(sorted(PRESETS.keys()))
        raise ValueError(f"Unknown preset '{preset_name}'. Valid: {valid}")

    result = copy.deepcopy(intent)
    result.preset = preset_name

    preset_values = PRESETS[preset_name]
    for key, value in preset_values.items():
        current = getattr(result, key, None)
        if current is None:
            setattr(result, key, value)

    return result
