"""Deterministic DJ technique direction for segment performances.

This is a small situation-to-grammar layer. It selects among existing
transition DSP paths and may add bounded, auditable creative operations. It
does not choose timestamps or perform waveform work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from djenius.core.models import TransitionType


@dataclass
class MusicalSituation:
    source_section: str = "unknown"
    target_section: str = "unknown"
    source_bpm: float = 0.0
    target_bpm: float = 0.0
    bpm_ratio: float = 1.0
    harmonic_fit: float = 0.5
    rhythm_fit: float = 0.5
    timbre_fit: float = 0.5
    source_energy: float = 0.5
    target_energy: float = 0.5
    energy_direction: str = "steady"
    source_vocal_state: str = "unknown"
    target_vocal_state: str = "unknown"
    source_bass: float = 0.5
    target_bass: float = 0.5
    phrase_alignment: float = 0.5
    downbeat_alignment: float = 0.5
    semantic_relationship: str = "unknown"
    desired_style: str = "quick_mix"
    local_context_score: float = 0.5


@dataclass
class TechniqueCandidate:
    name: str
    transition_intent: str
    transition_type: TransitionType
    operations: list[dict] = field(default_factory=list)
    score: float = 0.0
    confidence: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict:
        result = asdict(self)
        result["transition_type"] = self.transition_type.value
        return result


def build_musical_situation(source, target, pair, *, style: str) -> MusicalSituation:
    source_energy = float(getattr(pair, "source_energy", 0.5))
    target_energy = float(getattr(pair, "target_energy", 0.5))
    delta = target_energy - source_energy
    direction = "build" if delta > 0.10 else "release" if delta < -0.10 else "steady"
    source_vocal = float(getattr(pair, "source_vocal", 0.0))
    target_vocal = float(getattr(pair, "target_vocal", 0.0))
    source_bpm = float(getattr(source, "bpm", 0.0) or 0.0)
    target_bpm = float(getattr(target, "bpm", 0.0) or 0.0)
    return MusicalSituation(
        source_section=str(getattr(pair, "source_section", "unknown")),
        target_section=str(getattr(pair, "target_section", "unknown")),
        source_bpm=source_bpm,
        target_bpm=target_bpm,
        bpm_ratio=source_bpm / max(target_bpm, 1.0),
        harmonic_fit=float(getattr(pair, "local_harmonic_score", 0.5)),
        rhythm_fit=float(getattr(pair, "local_rhythm_score", 0.5)),
        timbre_fit=float(getattr(pair, "local_timbre_score", 0.5)),
        source_energy=source_energy,
        target_energy=target_energy,
        energy_direction=direction,
        source_vocal_state="dense" if source_vocal >= 0.55 else "light",
        target_vocal_state="dense" if target_vocal >= 0.55 else "light",
        source_bass=float(getattr(pair, "source_bass", 0.5)),
        target_bass=float(getattr(pair, "target_bass", 0.5)),
        phrase_alignment=float(getattr(pair, "phrase_score", 0.5)),
        downbeat_alignment=max(0.0, 1.0 - min(1.0, abs(float(getattr(pair, "phase_error_ms", 1000.0))) / 250.0)),
        desired_style=style,
        local_context_score=float(getattr(pair, "local_context_score", 0.5)),
    )


def _candidate(name, intent, transition_type, score, confidence, reason, operations=None):
    return TechniqueCandidate(
        name=name,
        transition_intent=intent,
        transition_type=transition_type,
        operations=list(operations or []),
        score=max(0.0, min(1.0, score)),
        confidence=max(0.0, min(1.0, confidence)),
        reason=reason,
    )


def rank_techniques(
    situation: MusicalSituation,
    base_transition_type: TransitionType,
    *,
    style: str,
    allow_creative_fx: bool = True,
    intensity: str = "moderate",
    stems_available: bool = False,
    recent_techniques: tuple[str, ...] = (),
) -> list[TechniqueCandidate]:
    """Rank a small technique vocabulary for one concrete handoff."""
    if not allow_creative_fx:
        return [_candidate(
            "clean " + base_transition_type.value.replace("_", " "),
            "SMOOTH_CONTINUATION",
            base_transition_type,
            0.82,
            0.95,
            "Special effects disabled; retained the validated clean transition.",
        )]

    bpm_delta = abs(situation.source_bpm - situation.target_bpm) / max(situation.source_bpm, 1.0)
    close_groove = min(situation.rhythm_fit, situation.harmonic_fit, situation.downbeat_alignment)
    energy_lift = situation.energy_direction == "build"
    candidates = [_candidate(
        "clean continuation", "SMOOTH_CONTINUATION", base_transition_type,
        0.50 + 0.30 * situation.local_context_score
        - 0.20 * min(1.0, bpm_delta / 0.12), 0.72,
        "Local context supports a restrained handoff.",
    )]
    if base_transition_type == TransitionType.BEATMATCHED_BLEND and bpm_delta <= 0.14:
        candidates.append(_candidate(
            "tempo-locked blend", "SMOOTH_CONTINUATION", TransitionType.BEATMATCHED_BLEND,
            0.60 + 0.25 * close_groove, 0.80,
            "Beat and harmonic evidence support a tempo-locked phrase blend.",
            [{"type": "tempo_ramp", "mode": "beatmatched", "amount": round(min(0.14, bpm_delta), 4)}],
        ))
    if (base_transition_type in {TransitionType.BASS_SWAP, TransitionType.BEATMATCHED_BLEND}
            and close_groove >= 0.68 and max(situation.source_bass, situation.target_bass) >= 0.25):
        candidates.append(_candidate(
            "bass transfer", "ENERGY_BUILD" if energy_lift else "SMOOTH_CONTINUATION",
            TransitionType.BASS_SWAP, 0.58 + 0.30 * close_groove, 0.78,
            "Compatible groove and low-end structure support a controlled bass handoff.",
            [{"type": "bass_transfer", "bounded": True}],
        ))
    if (style in {"club", "experimental", "quick_mix"}
            and bpm_delta <= 0.10
            and situation.rhythm_fit >= 0.76
            and situation.phrase_alignment >= 0.70
            and situation.downbeat_alignment >= 0.68
            and situation.local_context_score >= 0.62
            and intensity != "subtle"):
        candidates.append(_candidate(
            "loop-roll drop", "DROP_REVEAL", TransitionType.CROSSFADE,
            0.54 + 0.30 * min(situation.rhythm_fit, situation.local_context_score), 0.70,
            "A short phrase-aligned loop can build the outgoing groove into the target landing.",
            [{"type": "loop_roll", "beats": 1, "repeats": 2},
             {"type": "generated_fx", "effect": "riser", "level": 0.025, "seed": 13}],
        ))
    if (style in {"club", "experimental"} and energy_lift
            and situation.harmonic_fit >= 0.72
            and situation.downbeat_alignment >= 0.78
            and situation.phrase_alignment >= 0.74):
        candidates.append(_candidate(
            "drop switch", "DROP_REVEAL", TransitionType.PHRASE_CUT,
            0.56 + 0.28 * close_groove, 0.74,
            "A supported downbeat and energy lift make a short drop switch appropriate.",
            [{"type": "generated_fx", "effect": "impact", "level": 0.018, "seed": 17}],
        ))
    if (style in {"club", "experimental"} and bpm_delta >= 0.12
            and situation.source_vocal_state == "light"
            and situation.downbeat_alignment >= 0.70):
        candidates.append(_candidate(
            "tape-stop reset", "DRAMATIC_RESET", TransitionType.ECHO_OUT,
            0.56 + 0.18 * situation.phrase_alignment, 0.66,
            "The tempo gap is too wide for a natural blend; a bounded speed reset makes the change explicit.",
            [{"type": "tape_stop", "strength": 0.72}],
        ))
    if (situation.source_vocal_state == "dense" and situation.target_vocal_state == "light"
            and situation.phrase_alignment >= 0.65 and style in {"story", "experimental", "club"}):
        candidates.append(_candidate(
            "vocal echo tail", "VOCAL_HANDOFF", TransitionType.ECHO_OUT,
            0.56 + 0.25 * situation.phrase_alignment, 0.73,
            "The outgoing vocal window is dense while the target leaves room for a tail.",
            [{"type": "echo_tail", "beats": 2}],
        ))
    if stems_available and style in {"club", "experimental"} and close_groove >= 0.82:
        candidates.append(_candidate(
            "vocal bridge", "VOCAL_TO_INSTRUMENTAL", TransitionType.MASHUP,
            0.58 + 0.22 * close_groove, 0.76,
            "Stems and local harmonic/rhythm evidence permit a conservative vocal bridge.",
            [{"type": "stem_bridge", "stems": ["vocals", "drums", "bass", "other"]}],
        ))

    for item in candidates:
        item.score -= min(0.12, 0.045 * recent_techniques[-3:].count(item.name))
    candidates.sort(key=lambda item: (item.score, item.confidence, item.name), reverse=True)
    return candidates


def choose_technique(
    situation: MusicalSituation,
    base_transition_type: TransitionType,
    *,
    style: str,
    allow_creative_fx: bool = True,
    intensity: str = "moderate",
    stems_available: bool = False,
    recent_techniques: tuple[str, ...] = (),
) -> TechniqueCandidate:
    """Choose the highest-ranked safe technique for one concrete handoff."""
    return rank_techniques(
        situation,
        base_transition_type,
        style=style,
        allow_creative_fx=allow_creative_fx,
        intensity=intensity,
        stems_available=stems_available,
        recent_techniques=recent_techniques,
    )[0]


def technique_research_summary() -> list[dict]:
    """Compact local audit table used by reports and tests."""
    return [
        {"name": "beatmatched blend", "purpose": "groove continuity", "priority": "core", "risk": "phase/time-stretch artifacts"},
        {"name": "bass transfer", "purpose": "avoid double bass", "priority": "core", "risk": "low-end hole if unsupported"},
        {"name": "filter sweep", "purpose": "frequency handoff", "priority": "core", "risk": "thin outgoing sound"},
        {"name": "echo/reverb tail", "purpose": "complete phrase exit", "priority": "core", "risk": "washout"},
        {"name": "loop roll", "purpose": "rhythmic build into landing", "priority": "V13", "risk": "repetition"},
        {"name": "tape-stop reset", "purpose": "explicit tempo/style reset", "priority": "V13", "risk": "pitch/speed artifact"},
        {"name": "tempo ramp", "purpose": "gradual BPM bridge", "priority": "V13", "risk": "stretch artifacts"},
        {"name": "drop switch", "purpose": "energy reveal", "priority": "V13", "risk": "hard contrast"},
        {"name": "procedural riser/impact", "purpose": "mark a transition", "priority": "V13", "risk": "distracting FX"},
        {"name": "vocal-over-instrumental", "purpose": "two-record bridge", "priority": "V11/V13", "risk": "stem bleed and harmonic clash"},
    ]
