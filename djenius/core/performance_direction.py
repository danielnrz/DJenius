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


@dataclass(frozen=True)
class PerformanceDirective:
    """Executable, data-only translation of two blueprint acts.

    The directive is deliberately smaller than a blueprint.  It tells the
    existing V13 technique selector what the boundary is trying to achieve;
    it never contains waveform instructions or arbitrary source timestamps.
    """

    source_role: str = ""
    target_role: str = ""
    blueprint_decision: str = "SWITCH"
    musical_goal: str = "smooth continuation"
    intensity: str = "moderate"
    preserve_groove: bool = False
    require_payoff: bool = False
    prefer_vocal_clearance: bool = False
    allow_strong_technique: bool = True
    preparation_goal: str = ""
    landing_goal: str = ""
    transition_role: str = "CONTINUE"
    performance_state: str = "DEVELOP"
    next_performance_state: str = "DEVELOP"

    def to_dict(self) -> dict:
        return {
            "source_role": self.source_role,
            "target_role": self.target_role,
            "blueprint_decision": self.blueprint_decision,
            "musical_goal": self.musical_goal,
            "intensity": self.intensity,
            "preserve_groove": self.preserve_groove,
            "require_payoff": self.require_payoff,
            "prefer_vocal_clearance": self.prefer_vocal_clearance,
            "allow_strong_technique": self.allow_strong_technique,
            "preparation_goal": self.preparation_goal,
            "landing_goal": self.landing_goal,
            "transition_role": self.transition_role,
            "performance_state": self.performance_state,
            "next_performance_state": self.next_performance_state,
        }


def build_performance_directive(
    source_act: dict | None,
    target_act: dict | None,
    performance_style: str,
) -> PerformanceDirective:
    """Compile blueprint role/decision metadata into execution guidance."""
    source_act = source_act or {}
    target_act = target_act or {}
    source_role = str(source_act.get("role", ""))
    target_role = str(target_act.get("role", ""))
    decision = str(target_act.get("decision", "SWITCH") or "SWITCH").upper()
    source_out = str(source_act.get("transition_role_out", "CONTINUE") or "CONTINUE").upper()
    target_in = str(target_act.get("transition_role_in", "CONTINUE") or "CONTINUE").upper()

    # The target's incoming role describes what the listener should hear at
    # this boundary.  The source's outgoing role is the fallback for older
    # blueprints that did not populate incoming roles.
    role = target_in if target_in != "CONTINUE" else source_out
    role_goals = {
        "BUILD": ("build anticipation", "raise energy into the next idea", True, False),
        "REVEAL": ("deliver a prepared payoff", "make the target landing feel earned", True, False),
        "RELEASE": ("release tension", "give the next section room to breathe", False, True),
        "RESET": ("reset tempo or musical identity", "land cleanly after the reset", False, False),
        "CALLBACK": ("reveal a recognizable callback", "let the returned idea land clearly", False, True),
        "CLOSE": ("close the performance cleanly", "leave a stable final landing", False, True),
        "LIFT": ("lift the musical energy", "keep the groove stable while it rises", True, False),
        "CONTINUE": ("continue the musical idea", "preserve a stable groove", False, False),
    }
    goal, landing, payoff, vocal_clearance = role_goals.get(role, role_goals["CONTINUE"])
    preserve_groove = role in {"CONTINUE", "LIFT"} or source_role == target_role == "GROOVE"
    if target_role in {"BREATHING_ROOM", "RELEASE"}:
        vocal_clearance = True
    intensity = "strong" if role in {"REVEAL", "RESET"} else "moderate"
    if performance_style in {"smooth", "story"} and role not in {"RESET", "REVEAL"}:
        intensity = "subtle"
    if decision == "STAY":
        goal = "continue the current musical idea"
        landing = "preserve continuity without a conventional handoff"
        preserve_groove = True
        payoff = False
    elif decision == "VARIATE":
        goal = "develop the current track with an intentional section edit"
        landing = "make the new section land without a fade-out/fade-in reset"
    elif decision == "LAYER":
        goal = "introduce the new role as a controlled layer"
        landing = "return to one clear dominant musical source"
    allow_strong = performance_style not in {"smooth", "story"} or role in {"RESET", "REVEAL"}
    return PerformanceDirective(
        source_role=source_role,
        target_role=target_role,
        blueprint_decision=decision,
        musical_goal=goal,
        intensity=intensity,
        preserve_groove=preserve_groove,
        require_payoff=payoff,
        prefer_vocal_clearance=vocal_clearance,
        allow_strong_technique=allow_strong,
        preparation_goal=goal,
        landing_goal=landing,
        transition_role=role,
        performance_state=str(source_act.get("state", "DEVELOP")),
        next_performance_state=str(target_act.get("state", "DEVELOP")),
    )


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
