"""Behavioral coverage for V10 creative performance planning."""

from djenius.application import LocalAppService
from djenius.core.intent import SetIntent
from djenius.core.performance import plan_performance_timeline

from tests.test_v9_performance import profile


def test_two_track_quick_mix_limits_pathological_repetition():
    tracks = [profile("a", bpm=118), profile("b", bpm=120)]
    intent = SetIntent(
        target_duration_sec=300,
        performance_mode="segment",
        performance_style="quick_mix",
    )
    timeline, _ = plan_performance_timeline(
        tracks, 300, intent, seed=4, performance_style="quick_mix",
    )
    assert len(timeline.appearances) == 4
    assert len({item.segment.track_id for item in timeline.appearances}) == 2
    assert timeline.repeated_pair_count == 1


def test_requested_variety_adds_new_tracks_before_reprises():
    tracks = [profile(str(index), bpm=118 + index) for index in range(6)]
    intent = SetIntent(
        target_duration_sec=300,
        performance_mode="segment",
        performance_style="quick_mix",
        desired_variety=0.85,
    )
    timeline, _ = plan_performance_timeline(
        tracks, 300, intent, seed=7, performance_style="quick_mix",
    )
    first_seen = []
    for item in timeline.appearances:
        if item.segment.track_id not in first_seen:
            first_seen.append(item.segment.track_id)
    assert len(first_seen) >= 5
    assert len({item.segment.track_id for item in timeline.appearances[:5]}) == 5


def test_reprise_has_an_explicit_performance_reason():
    tracks = [profile("a"), profile("b"), profile("c")]
    intent = SetIntent(
        target_duration_sec=180,
        performance_mode="segment",
        performance_style="experimental",
        reprise_preference="callback",
    )
    timeline, _ = plan_performance_timeline(
        tracks, 180, intent, seed=3, performance_style="experimental",
    )
    reprises = [item for item in timeline.appearances if item.reprise]
    assert reprises
    assert all(item.performance_reason for item in reprises)
    assert timeline.repeated_pair_count >= 0


def test_performance_summary_round_trips():
    tracks = [profile("a"), profile("b"), profile("c"), profile("d")]
    timeline, _ = plan_performance_timeline(
        tracks, 180, SetIntent(), seed=2, performance_style="quick_mix",
    )
    restored = timeline.from_dict(timeline.to_dict())
    assert restored is not None
    assert restored.reuse_counts == timeline.reuse_counts
    assert restored.performance_arc == timeline.performance_arc
    assert restored.diversity_level == timeline.diversity_level


def test_v10_performance_language_is_structured_without_llm(tmp_path):
    service = LocalAppService(data_dir=tmp_path / "data", output_dir=tmp_path / "output")
    club, _ = service._intent("Make me an energetic club-style mix", None, 5, False)
    experimental, _ = service._intent(
        "Make an experimental mix with lots of different songs and a few mashup moments",
        None, 5, False,
    )
    story, _ = service._intent("Make a story-like heartbreak mix", None, 7, False)
    assert (club.performance_mode, club.performance_style) == ("segment", "club")
    assert experimental.performance_style == "experimental"
    assert experimental.desired_variety >= 0.8
    assert experimental.layering_preference == "prefer"
    assert (story.performance_mode, story.performance_style) == ("classic", "classic")
