"""Small deterministic director for full-set performance shape.

The V13 technique library chooses how to execute one handoff.  This module
chooses the set-level state and role that handoff is serving.  It deliberately
contains no audio processing and keeps the rules inspectable.
"""

from __future__ import annotations

from dataclasses import dataclass


PERFORMANCE_STATES = (
    "INTRO", "ESTABLISH", "DEVELOP", "BUILD", "PEAK", "RELEASE",
    "RESET", "CALLBACK", "OUTRO",
)

TRANSITION_ROLES = (
    "CONTINUE", "LIFT", "BUILD", "RELEASE", "RESET", "REVEAL",
    "CALLBACK", "CLOSE",
)

TECHNIQUE_TIERS = {
    "clean continuation": "subtle",
    "clean crossfade": "subtle",
    "clean beatmatched blend": "subtle",
    "clean filter sweep": "subtle",
    "tempo-locked blend": "subtle",
    "bass transfer": "moderate",
    "clean bass swap": "moderate",
    "vocal echo tail": "moderate",
    "vocal bridge": "moderate",
    "tape-stop reset": "strong",
    "loop-roll drop": "strong",
    "drop switch": "strong",
}


@dataclass(frozen=True)
class DirectionDecision:
    state: str
    next_state: str
    transition_role: str
    preparation_bars: int
    landing_bars: int


def build_performance_arc(count: int, style: str) -> list[str]:
    """Return a compact state path before individual transitions are scored."""
    if count <= 0:
        return []
    if count == 1:
        return ["INTRO"]
    if style == "experimental":
        template = ["INTRO", "ESTABLISH", "BUILD", "PEAK", "RELEASE", "CALLBACK", "PEAK", "OUTRO"]
    elif style == "club":
        template = ["INTRO", "ESTABLISH", "DEVELOP", "BUILD", "PEAK", "RELEASE", "PEAK", "OUTRO"]
    elif style == "story":
        template = ["INTRO", "DEVELOP", "RELEASE", "CALLBACK", "BUILD", "OUTRO"]
    elif style in {"smooth", "classic"}:
        template = ["INTRO", "ESTABLISH", "DEVELOP", "BUILD", "RELEASE", "OUTRO"]
    else:
        template = ["INTRO", "ESTABLISH", "BUILD", "PEAK", "RELEASE", "CALLBACK", "OUTRO"]
    if count <= len(template):
        indexes = [round(i * (len(template) - 1) / max(count - 1, 1)) for i in range(count)]
        return [template[index] for index in indexes]
    result = []
    for index in range(count):
        if index == 0:
            result.append("INTRO")
        elif index == count - 1:
            result.append("OUTRO")
        elif index < count * 0.25:
            result.append("ESTABLISH" if index == 1 else "DEVELOP")
        elif index < count * 0.55:
            result.append("BUILD")
        elif index < count * 0.72:
            result.append("PEAK")
        elif index < count * 0.86:
            result.append("RELEASE")
        else:
            result.append("CALLBACK")
    return result


def transition_direction(arc: list[str], index: int) -> DirectionDecision:
    """Describe the boundary before appearance ``index + 1``."""
    state = arc[index] if 0 <= index < len(arc) else "DEVELOP"
    next_state = arc[index + 1] if index + 1 < len(arc) else "OUTRO"
    if next_state in {"BUILD", "PEAK"}:
        role = "BUILD" if next_state == "BUILD" else "REVEAL"
    elif next_state == "RELEASE":
        role = "RELEASE"
    elif next_state == "RESET":
        role = "RESET"
    elif next_state == "CALLBACK":
        role = "CALLBACK"
    elif next_state == "OUTRO":
        role = "CLOSE"
    elif state in {"INTRO", "ESTABLISH"}:
        role = "CONTINUE"
    else:
        role = "LIFT" if next_state in {"DEVELOP", "ESTABLISH"} else "CONTINUE"
    preparation = 2 if role in {"BUILD", "REVEAL", "RESET"} else 1
    landing = 4 if role in {"REVEAL", "RESET", "CALLBACK"} else 2
    return DirectionDecision(state, next_state, role, preparation, landing)


def technique_tier(name: str) -> str:
    return TECHNIQUE_TIERS.get(str(name), "subtle")


def creative_budget(target_duration_sec: float, style: str) -> dict:
    """Return a small budget; values are guidance, not forced effects."""
    if style in {"smooth", "classic"}:
        strong = 0
        moderate = max(1, round(target_duration_sec / 180.0))
    elif style == "story":
        strong = 0 if target_duration_sec < 360 else 1
        moderate = max(1, round(target_duration_sec / 150.0))
    elif style == "club":
        strong = max(1, min(3, round(target_duration_sec / 180.0)))
        moderate = max(1, round(target_duration_sec / 100.0))
    else:  # quick_mix and experimental
        strong = max(1, min(3, round(target_duration_sec / 150.0)))
        moderate = max(1, round(target_duration_sec / 90.0))
    return {"strong_max": strong, "moderate_max": moderate, "strong_remaining": strong, "moderate_remaining": moderate}


def state_energy_target(state: str) -> float:
    return {
        "INTRO": 0.35, "ESTABLISH": 0.45, "DEVELOP": 0.52,
        "BUILD": 0.68, "PEAK": 0.82, "RELEASE": 0.55,
        "RESET": 0.42, "CALLBACK": 0.70, "OUTRO": 0.38,
    }.get(state, 0.5)


def role_fit(technique_name: str, role: str, style: str) -> float:
    """Small role prior; pair safety still determines the final recipe."""
    name = technique_name.lower()
    if role in {"BUILD", "REVEAL"}:
        if "loop" in name or "drop" in name or "bass" in name:
            return 0.16
        if "tempo" in name or "filter" in name:
            return 0.08
    if role == "RESET" and ("tape" in name or "echo" in name):
        return 0.18
    if role in {"CALLBACK", "CLOSE"} and ("echo" in name or "crossfade" in name):
        return 0.08
    if role == "CONTINUE" and technique_tier(name) == "subtle":
        return 0.07
    if style in {"smooth", "story"} and technique_tier(name) == "strong":
        return -0.22
    return 0.0
