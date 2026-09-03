"""V13.1 set-direction tests; audio DSP remains covered by V13 tests."""

from djenius.core.intent import SetIntent
from djenius.core.models import TransitionType
from djenius.core.performance import plan_performance_timeline, score_segment_pair
from djenius.core.performance_direction import (
    build_performance_arc,
    creative_budget,
    technique_tier,
    transition_direction,
)
from djenius.core.techniques import MusicalSituation, choose_technique, rank_techniques

from tests.test_v9_performance import profile


def _situation(**changes):
    values = dict(
        source_bpm=124.0, target_bpm=126.0, harmonic_fit=0.88,
        rhythm_fit=0.86, timbre_fit=0.78, source_energy=0.55,
        target_energy=0.72, source_vocal_state="light", target_vocal_state="light",
        source_bass=0.55, target_bass=0.58, phrase_alignment=0.92,
        downbeat_alignment=0.92, local_context_score=0.84, desired_style="club",
    )
    values.update(changes)
    return MusicalSituation(**values)


def test_arc_is_created_before_handoffs_and_has_roles():
    arc = build_performance_arc(7, "experimental")
    assert arc[0] == "INTRO" and arc[-1] == "OUTRO"
    decisions = [transition_direction(arc, i) for i in range(len(arc) - 1)]
    assert len(decisions) == 6
    assert {item.transition_role for item in decisions} >= {"BUILD", "REVEAL", "CLOSE"}


def test_creative_budget_is_style_aware():
    assert creative_budget(300, "smooth")["strong_max"] == 0
    assert creative_budget(300, "experimental")["strong_max"] >= 1


def test_strong_effects_get_landing_spacing_penalty():
    unconstrained = choose_technique(
        _situation(), TransitionType.BEATMATCHED_BLEND,
        style="experimental", intensity="strong", transition_role="BUILD",
        recent_strong_distance=5, strong_effects_remaining=2,
    )
    constrained = choose_technique(
        _situation(), TransitionType.BEATMATCHED_BLEND,
        style="experimental", intensity="strong", transition_role="CONTINUE",
        recent_strong_distance=0, strong_effects_remaining=2,
    )
    assert technique_tier(constrained.name) != "strong" or constrained.score < unconstrained.score


def test_smooth_and_story_do_not_prefer_strong_effects():
    ranked = rank_techniques(
        _situation(), TransitionType.BEATMATCHED_BLEND,
        style="story", intensity="moderate", transition_role="CONTINUE",
        recent_strong_distance=4, strong_effects_remaining=2,
    )
    assert technique_tier(ranked[0].name) != "strong"


def test_build_role_can_select_a_loop_or_drop_when_supported():
    ranked = rank_techniques(
        _situation(), TransitionType.BEATMATCHED_BLEND,
        style="experimental", intensity="strong", transition_role="BUILD",
        recent_strong_distance=4, strong_effects_remaining=2,
    )
    assert any(item.name in {"loop-roll drop", "drop switch", "bass transfer"} for item in ranked[:3])


def test_transition_metadata_contains_preparation_and_landing():
    tracks = [profile(str(i), bpm=120 + i) for i in range(5)]
    timeline, _ = plan_performance_timeline(
        tracks, 180, SetIntent(performance_mode="segment", performance_style="experimental"),
        seed=4, performance_style="experimental",
    )
    assert timeline.performance_states[0] == "INTRO"
    assert len(timeline.transition_roles) == len(timeline.transitions)
    assert all(item.preparation_duration_sec > 0 for item in timeline.transitions)
    assert all(item.landing_duration_sec > 0 for item in timeline.transitions)
    assert timeline.average_landing_duration_sec > 0


def test_transition_roles_survive_timeline_round_trip():
    tracks = [profile(str(i)) for i in range(4)]
    timeline, _ = plan_performance_timeline(tracks, 180, SetIntent(), seed=2, performance_style="quick_mix")
    restored = timeline.from_dict(timeline.to_dict())
    assert restored.performance_states == timeline.performance_states
    assert restored.transition_roles == timeline.transition_roles
    assert [item.transition_role for item in restored.transitions] == [item.transition_role for item in timeline.transitions]


def test_strong_techniques_are_budgeted_in_timeline():
    tracks = [profile(str(i), bpm=118 + i) for i in range(6)]
    timeline, _ = plan_performance_timeline(
        tracks, 300, SetIntent(performance_mode="segment", performance_style="experimental"),
        seed=7, performance_style="experimental",
    )
    assert timeline.strong_effect_count <= timeline.creative_budget["strong_max"]


def test_arc_state_is_attached_to_each_appearance():
    tracks = [profile(str(i)) for i in range(5)]
    timeline, _ = plan_performance_timeline(tracks, 180, SetIntent(), seed=1, performance_style="club")
    assert [item.performance_state for item in timeline.appearances] == timeline.performance_states


def test_v13_positive_control_large_tempo_reset_remains_available():
    item = choose_technique(
        _situation(source_bpm=76, target_bpm=123, source_vocal_state="light"),
        TransitionType.CROSSFADE, style="experimental", intensity="strong",
        transition_role="RESET", recent_strong_distance=4, strong_effects_remaining=2,
    )
    assert item.name == "tape-stop reset"


def test_v13_positive_control_loop_roll_remains_available():
    ranked = rank_techniques(
        _situation(), TransitionType.BEATMATCHED_BLEND, style="experimental",
        intensity="strong", transition_role="BUILD", recent_strong_distance=4,
        strong_effects_remaining=2,
    )
    assert any(item.name == "loop-roll drop" for item in ranked)


def test_direction_does_not_change_classic_plan_contract():
    tracks = [profile("a"), profile("b")]
    from djenius.core.planner import plan_set

    plan = plan_set(tracks, 180, intent=SetIntent(performance_mode="classic"), seed=1)
    assert plan.performance_timeline is None
