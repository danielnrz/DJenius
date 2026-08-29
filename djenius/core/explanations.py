"""Human-readable explanations for DJ set plans.

Generates natural language explanations of why the planner made the
choices it did, based on the SetIntent, track analysis, and transition
decisions.
"""

from __future__ import annotations

from typing import Optional

from djenius.core.models import SetPlan, TransitionPlan, TransitionType
from djenius.core.intent import SetIntent


def explain_set_plan(plan: SetPlan) -> list[str]:
    """Generate human-readable explanations for a set plan.

    Returns a list of explanation strings, each covering one aspect
    of the plan: overall strategy, track selection, transitions,
    energy journey, and intent alignment.
    """
    reasons = []

    # 1. Overall strategy
    reasons.append(_explain_strategy(plan))

    # 2. Energy journey
    energy_reason = _explain_energy_journey(plan)
    if energy_reason:
        reasons.append(energy_reason)

    # 3. Transition style
    trans_reason = _explain_transition_style(plan)
    if trans_reason:
        reasons.append(trans_reason)

    # 4. Track selection highlights
    track_reasons = _explain_track_selection(plan)
    reasons.extend(track_reasons)

    # 5. Intent alignment (if intent was used)
    if plan.intent_used:
        intent_reasons = _explain_intent_alignment(plan)
        reasons.extend(intent_reasons)

    return reasons


def explain_transition(transition: TransitionPlan) -> str:
    """Generate a brief explanation for a single transition."""
    parts = []

    parts.append(f"{transition.transition_type.value}")

    if transition.compatibility_score:
        score = transition.compatibility_score
        if score.overall_score > 0.8:
            parts.append("excellent match")
        elif score.overall_score > 0.6:
            parts.append("good match")
        elif score.overall_score > 0.4:
            parts.append("decent match")
        else:
            parts.append("challenging pair")

    if transition.confidence > 0.8:
        parts.append("high confidence")
    elif transition.confidence < 0.4:
        parts.append("low confidence - fallback")

    return " | ".join(parts)


# ---- Internal explanation helpers ----

def _explain_strategy(plan: SetPlan) -> str:
    """Explain the overall set strategy."""
    n = len(plan.tracks)
    dur_min = plan.total_duration_sec / 60.0

    avg_bpm = 0.0
    if plan.tracks:
        avg_bpm = sum(t.bpm for t in plan.tracks) / len(plan.tracks)

    avg_energy = 0.0
    if plan.tracks:
        avg_energy = sum(t.mean_energy for t in plan.tracks) / len(plan.tracks)

    strategy_parts = [f"Set: {n} tracks, {dur_min:.0f} minutes"]

    if avg_bpm > 0:
        strategy_parts.append(f"avg {avg_bpm:.0f} BPM")

    if avg_energy < 0.35:
        strategy_parts.append("low energy overall")
    elif avg_energy < 0.55:
        strategy_parts.append("medium energy overall")
    elif avg_energy < 0.75:
        strategy_parts.append("high energy overall")
    else:
        strategy_parts.append("very high energy")

    return ", ".join(strategy_parts)


def _explain_energy_journey(plan: SetPlan) -> Optional[str]:
    """Explain the energy trajectory of the set."""
    if len(plan.tracks) < 3:
        return None

    energies = [t.mean_energy for t in plan.tracks]
    start_energy = energies[0]
    mid_energy = energies[len(energies) // 2]
    end_energy = energies[-1]
    peak_energy = max(energies)

    profile = plan.energy_profile.value

    parts = [f"Energy journey ({profile}):"]

    if profile == "steady":
        variance = max(energies) - min(energies)
        if variance < 0.2:
            parts.append("consistent energy throughout")
        else:
            parts.append(f"energy varies from {start_energy:.2f} to {peak_energy:.2f}")

    elif profile == "slow_build":
        if end_energy > start_energy + 0.1:
            parts.append(f"builds from {start_energy:.2f} to {end_energy:.2f}")
        else:
            parts.append("intended build but energy stayed flat")

    elif profile == "warmup_to_peak":
        peak_idx = energies.index(peak_energy)
        peak_pct = peak_idx / len(energies) * 100
        parts.append(f"peaks at {peak_pct:.0f}% through the set (energy {peak_energy:.2f})")

    elif profile == "wave":
        ups = sum(1 for i in range(1, len(energies)) if energies[i] > energies[i-1])
        downs = len(energies) - 1 - ups
        parts.append(f"{ups} rises and {downs} drops create the wave pattern")

    elif profile == "cooldown":
        if start_energy > end_energy + 0.1:
            parts.append(f"winds down from {start_energy:.2f} to {end_energy:.2f}")
        else:
            parts.append("cooldown profile but energy stayed elevated")

    return " ".join(parts)


def _explain_transition_style(plan: SetPlan) -> Optional[str]:
    """Explain the transition style used in the set."""
    if not plan.transitions:
        return None

    type_counts: dict[str, int] = {}
    for t in plan.transitions:
        tt = t.transition_type.value
        type_counts[tt] = type_counts.get(tt, 0) + 1

    total = len(plan.transitions)
    dominant_type = max(type_counts, key=type_counts.get)
    dominant_count = type_counts[dominant_type]

    parts = [f"Transitions: {dominant_type} ({dominant_count}/{total})"]

    if len(type_counts) > 1:
        other_types = [t for t in type_counts if t != dominant_type]
        parts.append(f"also uses {', '.join(other_types[:2])}")

    avg_conf = plan.avg_transition_confidence
    if avg_conf > 0.8:
        parts.append("high confidence throughout")
    elif avg_conf < 0.5:
        parts.append("some challenging pairs")

    return " ".join(parts)


def _explain_track_selection(plan: SetPlan) -> list[str]:
    """Explain notable track selection choices."""
    reasons = []
    if not plan.tracks:
        return reasons

    # Find the highest and lowest energy tracks
    energies = [(t.mean_energy, t) for t in plan.tracks]
    energies.sort(key=lambda x: x[0])

    low_track = energies[0][1]
    high_track = energies[-1][1]

    if len(plan.tracks) > 3:
        reasons.append(
            f"Energy range: {low_track.title} ({low_track.mean_energy:.2f}) "
            f"to {high_track.title} ({high_track.mean_energy:.2f})"
        )

    # Check for BPM consistency
    bpms = [t.bpm for t in plan.tracks if t.bpm > 0]
    if bpms:
        bpm_range = max(bpms) - min(bpms)
        if bpm_range < 5:
            reasons.append("Very consistent BPM throughout")
        elif bpm_range > 20:
            reasons.append(f"Varied BPM range ({min(bpms):.0f} to {max(bpms):.0f})")

    return reasons


def _explain_intent_alignment(plan: SetPlan) -> list[str]:
    """Explain how the plan aligns with the original intent."""
    reasons = []
    intent = plan.intent_used
    if intent is None:
        return reasons

    # Preset alignment
    if intent.preset:
        reasons.append(f"Using '{intent.preset}' preset")

    # BPM range
    if intent.bpm_min is not None or intent.bpm_max is not None:
        bpm_min = intent.bpm_min or 0
        bpm_max = intent.bpm_max or 999
        track_bpms = [t.bpm for t in plan.tracks if t.bpm > 0]
        if track_bpms:
            in_range = sum(1 for b in track_bpms if bpm_min <= b <= bpm_max)
            pct = in_range / len(track_bpms) * 100
            reasons.append(
                f"BPM preference {bpm_min:.0f}-{bpm_max:.0f}: "
                f"{in_range}/{len(track_bpms)} tracks match ({pct:.0f}%)"
            )

    # Energy range
    if intent.energy_min is not None or intent.energy_max is not None:
        e_min = intent.energy_min or 0.0
        e_max = intent.energy_max or 1.0
        track_energies = [t.mean_energy for t in plan.tracks]
        in_range = sum(1 for e in track_energies if e_min <= e <= e_max)
        pct = in_range / len(track_energies) * 100
        reasons.append(
            f"Energy preference {e_min:.2f}-{e_max:.2f}: "
            f"{in_range}/{len(track_energies)} tracks match ({pct:.0f}%)"
        )

    # Transition style
    if intent.transition_style:
        from djenius.core.intent import TransitionStyle
        allowed = TransitionStyle.allowed_types(intent.transition_style)
        used_types = {t.transition_type for t in plan.transitions}
        matched = used_types & set(allowed)
        total = len(plan.transitions) or 1
        reasons.append(
            f"Transition style '{intent.transition_style}': "
            f"{len(matched)}/{total} transitions use preferred types"
        )

    return reasons


def format_plan_explanation(plan: SetPlan) -> str:
    """Format all explanations into a single readable string."""
    reasons = explain_set_plan(plan)
    if not reasons:
        return "No explanation available."
    return "\n".join(f"- {r}" for r in reasons)
