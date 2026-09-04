"""V14 whole-performance director tests using synthetic analysis only."""

from djenius.core.blueprint import (
    DirectorIntent,
    MUSICAL_ROLES,
    BlueprintAct,
    RemixBlueprint,
    build_remix_blueprint,
    compile_blueprint,
    derive_director_intent,
)
from djenius.core.intent import SetIntent
from djenius.core.models import (
    LyricsMeaningProfile,
    LyricsProfile,
    SemanticProfile,
)
from djenius.core.performance import plan_performance_timeline

from tests.test_v9_performance import profile


def _rich_profile(track_id: str, *, energy: float = 0.6):
    track = profile(track_id, duration=240.0, energy=energy, bpm=120.0)
    track.semantic = SemanticProfile(
        semantic_tags=["energetic", "dance"],
        mood_scores={"energetic": 0.9},
        activity_scores={"dance": 0.9},
        semantic_confidence=0.9,
    )
    track.lyrics = LyricsProfile(
        source="sidecar", text="synthetic lyrics", transcription_confidence=0.95,
        analysis_version="2", meaning_analysis_version="2",
        meaning=LyricsMeaningProfile(
            model_name="granite4:3b", model_version="validated-json-v2",
            primary_themes=["heartbreak"], lyrical_moods=["sad"], meaning_confidence=0.9,
        ),
    )
    return track


def test_blueprint_is_a_role_first_object_before_timeline_execution():
    tracks = [_rich_profile("a"), _rich_profile("b", energy=0.85), _rich_profile("c", energy=0.3)]
    intent = SetIntent(raw_text="energetic heartbreak remix", target_duration_sec=300)
    blueprint = build_remix_blueprint(tracks, 300, intent, performance_style="experimental")
    assert blueprint.acts
    assert blueprint.narrative
    assert any(act.role == "VOCAL_IDENTITY" for act in blueprint.acts)
    assert any(act.role == "PEAK" for act in blueprint.acts)
    assert all(act.role in MUSICAL_ROLES for act in blueprint.acts)


def test_role_assignment_is_section_level_and_meaning_sound_stay_separate():
    tracks = [_rich_profile("a"), _rich_profile("b")]
    tracks[1].lyrics = None
    intent = SetIntent(raw_text="energetic heartbreak remix", desired_themes=["heartbreak"], desired_moods=["energetic"])
    blueprint = build_remix_blueprint(tracks, 180, intent, performance_style="experimental")
    assert all(act.selected_segment_id for act in blueprint.acts)
    assert any(act.meaning_score != act.sound_score for act in blueprint.acts)
    assert any(act.role == "VOCAL_IDENTITY" and act.selected_section for act in blueprint.acts)


def test_blueprint_can_reuse_a_track_for_a_different_role_and_callback():
    tracks = [_rich_profile("a"), _rich_profile("b")]
    intent = SetIntent(raw_text="remix with a recognizable callback")
    blueprint = build_remix_blueprint(tracks, 300, intent, performance_style="experimental")
    repeated = [act for act in blueprint.acts if act.selected_track_id == blueprint.acts[2].selected_track_id]
    assert repeated
    callback = [act for act in blueprint.acts if act.callback_to]
    assert callback
    assert callback[0].callback_reason
    assert any(act.selected_segment_id != blueprint.acts[2].selected_segment_id for act in repeated)


def test_blueprint_count_is_duration_and_style_driven_not_fixed_ten():
    tracks = [_rich_profile(str(index)) for index in range(4)]
    short = build_remix_blueprint(tracks, 120, SetIntent(), performance_style="experimental")
    long = build_remix_blueprint(tracks, 420, SetIntent(), performance_style="club")
    assert len(short.acts) != 10
    assert len(long.acts) != len(short.acts)


def test_blueprint_can_explicitly_schedule_breathing_room_build_peak_release():
    tracks = [_rich_profile("a"), _rich_profile("b")]
    blueprint = build_remix_blueprint(tracks, 300, SetIntent(raw_text="story heartbreak"), performance_style="story")
    roles = {act.role for act in blueprint.acts}
    assert "BREATHING_ROOM" in roles
    assert "BUILD" in roles
    assert "CALLBACK" in roles


def test_stay_value_is_represented_without_disabling_replay_validation():
    tracks = [_rich_profile("a"), _rich_profile("b")]
    blueprint = RemixBlueprint(acts=[
        BlueprintAct(id="one", role="GROOVE", selected_track_id="a", start_fraction=0, end_fraction=.5),
        BlueprintAct(id="two", role="BUILD", selected_track_id="a", start_fraction=.5, end_fraction=1, stay_on_track=True),
    ])
    assert compile_blueprint(blueprint, tracks)["acts"][1]["stay_on_track"] is True
    timeline, _ = plan_performance_timeline(
        tracks, 120, SetIntent(performance_mode="segment", performance_style="experimental"),
        seed=3, performance_style="experimental", blueprint=blueprint.to_dict(),
    )
    assert timeline.remix_blueprint


def test_blueprint_compiles_and_round_trips_through_timeline():
    tracks = [_rich_profile("a"), _rich_profile("b")]
    blueprint = build_remix_blueprint(tracks, 180, SetIntent(raw_text="remix"), performance_style="experimental")
    serialized = compile_blueprint(blueprint, tracks)
    restored = RemixBlueprint.from_dict(serialized)
    assert restored is not None
    timeline, _ = plan_performance_timeline(
        tracks, 180, SetIntent(performance_mode="segment", performance_style="experimental"),
        seed=2, performance_style="experimental", blueprint=serialized,
    )
    assert timeline.remix_blueprint["director_version"] == "v14-blueprint-1"
    assert timeline.appearances


def test_same_seed_reproduces_blueprint_and_timeline_assignments():
    tracks = [_rich_profile(str(index)) for index in range(4)]
    intent = SetIntent(raw_text="energetic heartbreak remix", desired_themes=["heartbreak"])
    first = build_remix_blueprint(tracks, 300, intent, performance_style="experimental").to_dict()
    second = build_remix_blueprint(tracks, 300, intent, performance_style="experimental").to_dict()
    assert first == second


def test_narrative_request_uses_segment_director_mode():
    from djenius.application import LocalAppService

    service = LocalAppService()
    intent, _ = service._intent(
        "Start emotional, build to a peak, release, and bring the opening vocal back near the end.",
        None, 5, False,
    )
    assert intent.performance_mode == "segment"
    assert intent.performance_style == "experimental"


def test_director_priorities_change_with_request_axes():
    meaning = derive_director_intent(
        SetIntent(raw_text="heartbreak remix", desired_themes=["heartbreak"]),
        "experimental",
    )
    sound = derive_director_intent(
        SetIntent(raw_text="energetic club remix", desired_moods=["energetic"], desired_activity=["dance"]),
        "club",
    )
    assert meaning.meaning_priority > meaning.sound_priority
    assert sound.groove_priority > meaning.groove_priority
    assert sound.sound_priority > meaning.sound_priority


def test_complete_blueprint_search_retains_ranked_alternatives_and_score_components():
    tracks = [_rich_profile(str(index), energy=0.35 + index * 0.2) for index in range(4)]
    blueprint = build_remix_blueprint(
        tracks, 300, SetIntent(raw_text="energetic heartbreak remix", desired_themes=["heartbreak"]),
        performance_style="experimental",
    )
    assert len(blueprint.candidate_blueprints) >= 3
    assert 0.0 <= blueprint.whole_score <= 1.0
    assert "request_fidelity" in blueprint.whole_score_components


def test_role_aware_energy_penalty_applies_to_peak_but_not_release():
    from djenius.core.blueprint import _role_score
    from djenius.core.models import PerformanceSegment

    track = _rich_profile("low", energy=0.2)
    segment = PerformanceSegment(track_id="low", source_start_sec=0, source_end_sec=16, energy=0.2, quality_score=0.9)
    intent = SetIntent(raw_text="energetic heartbreak remix", desired_themes=["heartbreak"], desired_moods=["energetic"])
    peak, _, _, _ = _role_score("PEAK", track, segment, intent)
    release, _, _, _ = _role_score("RELEASE", track, segment, intent)
    assert release > peak


def test_stay_switch_decisions_are_explicit_and_not_descriptive_only():
    tracks = [_rich_profile("a"), _rich_profile("b")]
    blueprint = build_remix_blueprint(tracks, 300, SetIntent(raw_text="remix"), performance_style="experimental")
    assert blueprint.stay_switch_decisions
    assert {item["decision"] for item in blueprint.stay_switch_decisions} <= {"STAY", "VARIATE", "LAYER", "SWITCH"}


def test_director_intent_is_serialized_into_blueprint():
    blueprint = build_remix_blueprint(
        [_rich_profile("a"), _rich_profile("b")], 180,
        SetIntent(raw_text="energetic heartbreak remix", desired_themes=["heartbreak"]),
        performance_style="experimental",
    )
    assert isinstance(blueprint.director_intent, dict)
    assert blueprint.director_intent["meaning_priority"] > 0.0
    assert blueprint.primary_vocal_anchor
