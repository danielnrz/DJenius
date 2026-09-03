"""Small, explicit preparation/landing plans for performance transitions.

The V13.1 direction fields described a preparation phase, but the performance
renderer only changed samples inside the overlap.  This module keeps the
phase vocabulary deliberately small and produces data-only operations for the
performance renderer.  It does not perform DSP or alter the classic renderer.
"""

from __future__ import annotations


def build_preparation_operations(
    technique_name: str,
    transition_role: str,
    performance_style: str,
    *,
    stems_available: bool = False,
) -> list[dict]:
    """Return bounded source-side operations for a selected handoff.

    These are intentionally conservative.  A preparation is only useful when
    it is audible and has a musical reason; ordinary continuations remain
    untouched.  The renderer validates and executes the operations.
    """
    name = str(technique_name).lower()
    role = str(transition_role).upper()
    if name == "drop switch" and role in {"BUILD", "REVEAL", "RESET"}:
        operations = [
            {
                "type": "bass_automation",
                "start_db": 0.0,
                "end_db": -9.0,
                "cutoff_hz": 180.0,
                "reason": "clear outgoing low end before the target downbeat",
            },
            {
                "type": "generated_fx",
                "effect": "riser",
                "level": 0.012,
                "seed": 1701,
                "reason": "subtle anticipation before the prepared reveal",
            },
        ]
        if stems_available and performance_style in {"club", "experimental"}:
            operations.append({
                "type": "target_percussion_tease",
                "reason": "introduce the target groove before the prepared downbeat",
            })
        return operations
    if name == "loop-roll drop" and role in {"BUILD", "REVEAL"}:
        operations = [{
            "type": "bass_automation",
            "start_db": 0.0,
            "end_db": -6.0,
            "cutoff_hz": 180.0,
            "reason": "make room for the rhythmic loop and landing",
        }]
        if stems_available and performance_style == "club":
            operations.append({
                "type": "target_percussion_tease",
                "reason": "preview the incoming groove without target vocals",
            })
        return operations
    if name == "bass transfer":
        return [{
            "type": "bass_automation",
            "start_db": 0.0,
            "end_db": -7.0,
            "cutoff_hz": 180.0,
            "reason": "prepare a single-bass ownership handoff",
        }]
    if name == "clean filter sweep" or "filter" in name:
        return [{
            "type": "filter_automation",
            "mode": "highpass",
            "start_hz": 20.0,
            "end_hz": 150.0,
            "reason": "gradually thin the outgoing spectrum before entry",
        }]
    if name == "vocal echo tail" and performance_style in {"story", "smooth"}:
        return [{
            "type": "filter_automation",
            "mode": "highpass",
            "start_hz": 20.0,
            "end_hz": 90.0,
            "reason": "leave space for the incoming instrumental landing",
        }]
    return []


def landing_operations() -> list[dict]:
    """Landing is intentionally clean; gain stabilization remains bounded."""
    return []
