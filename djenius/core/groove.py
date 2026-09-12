"""Typed Groove / Sampler structures for DJenius V2 Phase 4."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum
import hashlib
import json
from typing import Any


class MusicalSubdivision(IntEnum):
    QUARTER = 1
    EIGHTH = 2
    SIXTEENTH = 4


PERCUSSION_GENERATORS = frozenset({
    "kick_v1", "snare_v1", "clap_v1", "closed_hat_v1", "open_hat_v1",
})
FX_GENERATORS = frozenset({
    "noise_riser_v1", "downlifter_v1", "impact_v1", "reverse_cymbal_v1",
})
SUPPORTED_PROCEDURAL_GENERATORS = PERCUSSION_GENERATORS | FX_GENERATORS

_DEFAULT_DURATION_BEATS = {
    "kick_v1": 0.75,
    "snare_v1": 0.50,
    "clap_v1": 0.50,
    "closed_hat_v1": 0.25,
    "open_hat_v1": 1.00,
    "noise_riser_v1": 4.00,
    "downlifter_v1": 4.00,
    "impact_v1": 1.00,
    "reverse_cymbal_v1": 2.00,
}


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, IntEnum):
        return int(value)
    return value


def _strict_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        parsed = int(value)
        if float(value) != parsed:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    return parsed


def _stable_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(
        _canonicalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:16]}"


def source_type_for_generator(generator: str) -> str:
    if generator in PERCUSSION_GENERATORS:
        return "procedural_percussion"
    if generator in FX_GENERATORS:
        return "generated_fx"
    raise ValueError(f"unsupported procedural generator: {generator}")


def default_duration_beats(generator: str) -> float:
    try:
        return _DEFAULT_DURATION_BEATS[generator]
    except KeyError as exc:
        raise ValueError(f"unsupported procedural generator: {generator}") from exc


@dataclass(frozen=True)
class PatternStep:
    """One event on a pattern-local rhythmic grid."""

    step: int
    generator: str
    velocity: float = 1.0
    gain_db: float = 0.0
    seed_offset: int = 0
    duration_beats: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "generator": self.generator,
            "velocity": self.velocity,
            "gain_db": self.gain_db,
            "seed_offset": self.seed_offset,
            "duration_beats": self.duration_beats,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternStep":
        return cls(
            step=_strict_int(data.get("step", -1), "pattern step"),
            generator=str(data.get("generator", "")),
            velocity=float(data.get("velocity", 1.0)),
            gain_db=float(data.get("gain_db", 0.0)),
            seed_offset=_strict_int(data.get("seed_offset", 0), "seed_offset"),
            duration_beats=float(data.get("duration_beats", 0.0)),
        )


@dataclass(frozen=True)
class GroovePattern:
    """Deterministic rhythmic pattern expressed in beat subdivisions."""

    name: str
    length_beats: float
    subdivision: MusicalSubdivision
    steps: tuple[PatternStep, ...]
    pattern_id: str = ""

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "length_beats": self.length_beats,
            "subdivision": int(self.subdivision),
            "steps": [item.to_dict() for item in self.steps],
        }

    def with_deterministic_id(self) -> "GroovePattern":
        return replace(self, pattern_id=_stable_id("gp4", self._identity_payload()))

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.name:
            errors.append("pattern requires a name")
        if not 0.25 <= self.length_beats <= 32.0:
            errors.append("pattern length_beats must be in [0.25, 32]")
        if int(self.subdivision) not in {1, 2, 4}:
            errors.append("pattern subdivision must be quarter, eighth, or sixteenth")
        grid_length = self.length_beats * int(self.subdivision)
        if abs(grid_length - round(grid_length)) > 1e-9:
            errors.append("pattern length does not align to its subdivision grid")
        max_steps = max(0, int(round(grid_length)))
        if not self.steps:
            errors.append("pattern has no steps")
        seen: set[tuple[int, str]] = set()
        for index, step in enumerate(self.steps):
            if step.step < 0 or step.step >= max_steps:
                errors.append(f"step {index + 1} is outside pattern bounds")
            if step.generator not in SUPPORTED_PROCEDURAL_GENERATORS:
                errors.append(f"step {index + 1} has unsupported generator")
            if not 0.0 < step.velocity <= 1.0:
                errors.append(f"step {index + 1} velocity must be in (0, 1]")
            if not -24.0 <= step.gain_db <= 0.0:
                errors.append(f"step {index + 1} gain_db must be in [-24, 0]")
            if (
                isinstance(step.seed_offset, bool)
                or not isinstance(step.seed_offset, int)
                or not -(2**31) <= step.seed_offset <= 2**31 - 1
            ):
                errors.append(f"step {index + 1} seed_offset must be a signed 32-bit integer")
            duration = step.duration_beats or default_duration_beats(step.generator) if step.generator in SUPPORTED_PROCEDURAL_GENERATORS else 0.0
            if duration <= 0.0 or step.step / max(int(self.subdivision), 1) + duration > self.length_beats + 1e-9:
                errors.append(f"step {index + 1} duration exceeds pattern")
            key = (step.step, step.generator)
            if key in seen:
                errors.append(f"step {index + 1} duplicates the same generator on the same grid point")
            seen.add(key)
        if list(self.steps) != sorted(self.steps, key=lambda item: (item.step, item.generator, item.seed_offset)):
            errors.append("pattern steps are not in deterministic order")
        expected = self.with_deterministic_id().pattern_id
        if self.pattern_id and self.pattern_id != expected:
            errors.append("pattern_id does not match deterministic pattern content")
        return errors

    def to_dict(self) -> dict[str, Any]:
        result = self._identity_payload()
        result["pattern_id"] = self.pattern_id
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GroovePattern":
        # Invalid grid values fail closed instead of silently changing musical time.
        subdivision = MusicalSubdivision(
            _strict_int(data.get("subdivision", 1), "pattern subdivision")
        )
        return cls(
            name=str(data.get("name", "")),
            length_beats=float(data.get("length_beats", 0.0)),
            subdivision=subdivision,
            steps=tuple(PatternStep.from_dict(item) for item in data.get("steps", [])),
            pattern_id=str(data.get("pattern_id", "")),
        )


@dataclass(frozen=True)
class PerformanceSampleEvent:
    """One compiled audible extra-layer event with reproducible provenance."""

    event_id: str
    source_type: str
    generator: str
    time_sec: float
    duration_sec: float
    level: float
    gain_db: float
    velocity: float
    seed: int
    recipe_id: str
    action_id: str
    musical_position: dict[str, Any]
    envelope: dict[str, float] = field(default_factory=dict)
    pattern_id: str = ""
    subdivision: int = 1
    provenance: dict[str, Any] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "generator": self.generator,
            "time_sec": round(self.time_sec, 9),
            "duration_sec": round(self.duration_sec, 9),
            "level": self.level,
            "gain_db": self.gain_db,
            "velocity": self.velocity,
            "seed": self.seed,
            "recipe_id": self.recipe_id,
            "action_id": self.action_id,
            "musical_position": _canonicalize(self.musical_position),
            "envelope": _canonicalize(self.envelope),
            "pattern_id": self.pattern_id,
            "subdivision": self.subdivision,
        }

    def with_deterministic_id(self) -> "PerformanceSampleEvent":
        event_id = sample_event_id(self._identity_payload())
        provenance = {
            **self.provenance,
            "type": self.source_type,
            "generator": self.generator,
            "seed": self.seed,
            "event_id": event_id,
            "recipe_id": self.recipe_id,
            "action_id": self.action_id,
        }
        return replace(self, event_id=event_id, provenance=provenance)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.generator not in SUPPORTED_PROCEDURAL_GENERATORS:
            errors.append("unsupported procedural generator")
        else:
            expected_source = source_type_for_generator(self.generator)
            if self.source_type != expected_source:
                errors.append("source_type does not match generator")
        if self.time_sec < 0.0:
            errors.append("time_sec must be non-negative")
        if not 0.005 <= self.duration_sec <= 16.0:
            errors.append("duration_sec must be in [0.005, 16]")
        if not 0.0 < self.level <= 0.05:
            errors.append("level must be in (0, 0.05]")
        if not -24.0 <= self.gain_db <= 0.0:
            errors.append("gain_db must be in [-24, 0]")
        if not 0.0 < self.velocity <= 1.0:
            errors.append("velocity must be in (0, 1]")
        if (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
            or not 0 <= self.seed <= 2**31 - 1
        ):
            errors.append("seed must be an integer in [0, 2147483647]")
        if self.subdivision not in {1, 2, 4}:
            errors.append("subdivision must be quarter, eighth, or sixteenth")
        if not self.recipe_id or not self.action_id:
            errors.append("event requires recipe_id and action_id ownership")
        if not isinstance(self.musical_position, dict):
            errors.append("musical_position must be an object")
        else:
            try:
                bar = _strict_int(self.musical_position.get("bar", 0), "musical_position.bar")
                beat = _strict_int(self.musical_position.get("beat", 0), "musical_position.beat")
                position_grid = _strict_int(
                    self.musical_position.get("subdivisions_per_beat", self.subdivision),
                    "musical_position.subdivisions_per_beat",
                )
                position_step = _strict_int(
                    self.musical_position.get("subdivision", 0),
                    "musical_position.subdivision",
                )
                if (
                    bar < 1 or beat < 1 or beat > 4
                    or position_grid != self.subdivision
                    or position_step < 0 or position_step >= position_grid
                ):
                    errors.append("musical_position is outside the declared subdivision grid")
            except ValueError:
                errors.append("musical_position is invalid")
        attack = float(self.envelope.get("attack_sec", 0.0))
        release = float(self.envelope.get("release_sec", 0.0))
        if attack < 0.0 or release < 0.0 or attack + release > self.duration_sec + 1e-9:
            errors.append("event envelope is outside duration")
        if self.event_id and self.event_id != sample_event_id(self._identity_payload()):
            errors.append("event_id does not match deterministic event content")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            **self._identity_payload(),
            "provenance": _canonicalize(self.provenance),
            "safety": _canonicalize(self.safety),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PerformanceSampleEvent":
        return cls(
            event_id=str(data.get("event_id", "")),
            source_type=str(data.get("source_type", "")),
            generator=str(data.get("generator", "")),
            time_sec=float(data.get("time_sec", 0.0)),
            duration_sec=float(data.get("duration_sec", 0.0)),
            level=float(data.get("level", 0.0)),
            gain_db=float(data.get("gain_db", 0.0)),
            velocity=float(data.get("velocity", 1.0)),
            seed=_strict_int(data.get("seed", 0), "seed"),
            recipe_id=str(data.get("recipe_id", "")),
            action_id=str(data.get("action_id", "")),
            musical_position=dict(data.get("musical_position", {}) or {}),
            envelope={str(k): float(v) for k, v in dict(data.get("envelope", {}) or {}).items()},
            pattern_id=str(data.get("pattern_id", "")),
            subdivision=_strict_int(data.get("subdivision", 1), "subdivision"),
            provenance=dict(data.get("provenance", {}) or {}),
            safety=dict(data.get("safety", {}) or {}),
        )


def sample_event_id(payload: dict[str, Any]) -> str:
    return _stable_id("se4", payload)


def percussion_bridge_pattern() -> GroovePattern:
    pattern = GroovePattern(
        name="percussion_bridge_v1",
        length_beats=4.0,
        subdivision=MusicalSubdivision.EIGHTH,
        steps=(
            PatternStep(0, "kick_v1", 0.82, -4.0),
            PatternStep(1, "closed_hat_v1", 0.55, -8.0),
            PatternStep(2, "clap_v1", 0.62, -7.0),
            PatternStep(3, "closed_hat_v1", 0.50, -9.0),
            PatternStep(4, "kick_v1", 0.76, -5.0),
            PatternStep(5, "closed_hat_v1", 0.55, -8.0),
            PatternStep(6, "clap_v1", 0.68, -6.5),
            PatternStep(7, "open_hat_v1", 0.42, -10.0, duration_beats=0.5),
        ),
    )
    return pattern.with_deterministic_id()


def short_drum_fill_pattern() -> GroovePattern:
    pattern = GroovePattern(
        name="short_drum_fill_v1",
        length_beats=2.0,
        subdivision=MusicalSubdivision.SIXTEENTH,
        steps=(
            PatternStep(0, "snare_v1", 0.48, -9.0, duration_beats=0.25),
            PatternStep(2, "snare_v1", 0.55, -8.0, duration_beats=0.25),
            PatternStep(4, "clap_v1", 0.60, -7.0, duration_beats=0.25),
            PatternStep(5, "snare_v1", 0.62, -7.0, duration_beats=0.25),
            PatternStep(6, "clap_v1", 0.68, -6.0, duration_beats=0.25),
            PatternStep(7, "open_hat_v1", 0.42, -10.0, duration_beats=0.25),
        ),
    )
    return pattern.with_deterministic_id()

def four_on_floor_pattern() -> GroovePattern:
    return GroovePattern(
        name="four_on_floor_v1", length_beats=4.0,
        subdivision=MusicalSubdivision.QUARTER,
        steps=tuple(PatternStep(step, "kick_v1", 0.78, -5.0) for step in range(4)),
    ).with_deterministic_id()


def backbeat_pattern() -> GroovePattern:
    return GroovePattern(
        name="backbeat_v1", length_beats=4.0,
        subdivision=MusicalSubdivision.QUARTER,
        steps=(
            PatternStep(1, "snare_v1", 0.62, -7.0),
            PatternStep(3, "clap_v1", 0.64, -7.0),
        ),
    ).with_deterministic_id()


def offbeat_hats_pattern() -> GroovePattern:
    return GroovePattern(
        name="offbeat_hats_v1", length_beats=4.0,
        subdivision=MusicalSubdivision.EIGHTH,
        steps=tuple(
            PatternStep(step, "closed_hat_v1", 0.46, -10.0)
            for step in (1, 3, 5, 7)
        ),
    ).with_deterministic_id()


def builtin_groove_pattern(name: str) -> GroovePattern:
    factories = {
        "percussion_bridge": percussion_bridge_pattern,
        "short_drum_fill": short_drum_fill_pattern,
        "four_on_floor": four_on_floor_pattern,
        "backbeat": backbeat_pattern,
        "offbeat_hats": offbeat_hats_pattern,
    }
    try:
        return factories[name]()
    except KeyError as exc:
        raise ValueError(f"unknown built-in groove pattern: {name}") from exc
