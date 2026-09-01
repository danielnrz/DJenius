"""Behavioral tests for intent-first V8.1 planning."""

from djenius.core.intent import SetIntent
from djenius.core.intent_scoring import (
    CONTRADICTION,
    PARTIAL_MATCH,
    STRONG_MATCH,
    UNKNOWN,
    score_track_intent,
    select_intent_candidate_pool,
)
from djenius.core.models import (
    EnergyProfile,
    LyricsMeaningProfile,
    LyricsProfile,
    SemanticProfile,
    TrackAnalysis,
    TrackMetadata,
    TrackProfile,
)
from djenius.core.planner import plan_set


def track(name, *, themes=(), moods=(), confidence=0.0, audio_moods=None,
          activity=None, energy=0.45, duration=180.0, bpm=120.0):
    meaning = None
    lyrics = None
    if themes or moods or confidence:
        meaning = LyricsMeaningProfile(
            primary_themes=list(themes),
            lyrical_moods=list(moods),
            meaning_confidence=confidence,
        )
        lyrics = LyricsProfile(
            source="sidecar",
            text="lyrics",
            transcription_confidence=0.95,
            meaning=meaning,
        )
    semantic = None
    if audio_moods is not None or activity is not None:
        semantic = SemanticProfile(
            mood_scores=dict(audio_moods or {}),
            activity_scores=dict(activity or {}),
            semantic_confidence=0.8,
            semantic_tags=list((audio_moods or {}).keys()),
        )
    return TrackProfile(
        id=name,
        metadata=TrackMetadata(filepath=f"/music/{name}.mp3", title=name, duration_sec=duration),
        analysis=TrackAnalysis(bpm=bpm, camelot="8A", mean_energy=energy),
        semantic=semantic,
        lyrics=lyrics,
    )


def test_reliable_theme_match_ranks_above_unknown():
    intent = SetIntent(desired_themes=["heartbreak"], lyrics_strength=1.0)
    match = score_track_intent(track("match", themes=("heartbreak",), confidence=0.95), intent)
    unknown = score_track_intent(track("unknown"), intent)
    assert match.status == STRONG_MATCH
    assert unknown.status == UNKNOWN
    assert match.overall_intent_score > unknown.overall_intent_score


def test_unknown_ranks_above_reliable_contradiction_as_fallback():
    intent = SetIntent(desired_themes=["heartbreak"], lyrics_strength=1.0)
    unknown = score_track_intent(track("unknown"), intent)
    contradiction = score_track_intent(track("party", themes=("celebration",), confidence=0.95), intent)
    assert unknown.overall_intent_score > contradiction.overall_intent_score
    assert contradiction.status == CONTRADICTION


def test_reliable_avoid_breakup_excludes_heartbreak_alias():
    intent = SetIntent(
        raw_text="romantic songs but avoid breakup songs",
        desired_themes=["romance"],
        avoid_themes=["breakup"],
    )
    pool = select_intent_candidate_pool(
        [
            track("safe", themes=("romance",), confidence=0.9),
            track("excluded", themes=("romance", "heartbreak"), confidence=0.9),
            track("unknown"),
        ],
        intent,
        240.0,
    )
    assert "excluded" in pool.excluded_track_ids
    assert "excluded" not in pool.candidate_track_ids


def test_technical_compatibility_cannot_overpower_candidate_selection():
    intent = SetIntent(desired_themes=["heartbreak"], lyrics_strength=1.0)
    relevant = track("relevant", themes=("heartbreak",), confidence=0.95, bpm=110.0)
    unrelated = track("unrelated", themes=("celebration",), confidence=0.95, bpm=110.0)
    unknown = track("unknown", bpm=110.0)
    pool = select_intent_candidate_pool([relevant, unrelated, unknown], intent, 300.0)
    assert pool.candidate_track_ids[0] == "relevant"
    assert "unrelated" not in pool.candidate_track_ids


def test_technical_planner_still_orders_relevant_candidates():
    intent = SetIntent(desired_themes=["heartbreak"], lyrics_strength=1.0)
    tracks = [
        track("one", themes=("heartbreak",), confidence=0.9, bpm=120.0),
        track("two", themes=("heartbreak",), confidence=0.85, bpm=121.0),
        track("three", themes=("heartbreak",), confidence=0.8, bpm=122.0),
    ]
    plan = plan_set(tracks, target_duration_sec=500.0, intent=intent)
    assert {item.id for item in plan.tracks} == {"one", "two", "three"}
    assert len(plan.transitions) == 2
    assert all(plan.intent_track_scores[item.id]["status"] == STRONG_MATCH for item in plan.tracks)


def test_duration_can_be_shortened_to_preserve_coherence():
    intent = SetIntent(desired_themes=["heartbreak"], lyrics_strength=1.0)
    strong = [track("one", themes=("heartbreak",), confidence=0.9, duration=170)]
    strong.append(track("two", themes=("heartbreak",), confidence=0.9, duration=170))
    strong.append(track("party", themes=("celebration",), confidence=0.95, duration=900))
    pool = select_intent_candidate_pool(strong, intent, 900.0)
    assert [item.id for item in pool.tracks] == ["one", "two"]
    assert pool.target_duration_met is False
    assert pool.relaxation_steps


def test_coverage_and_progressive_relaxation_are_reported():
    intent = SetIntent(desired_themes=["heartbreak"], lyrics_strength=1.0)
    pool = select_intent_candidate_pool(
        [track("strong", themes=("heartbreak",), confidence=0.9, duration=180), track("unknown", duration=180)],
        intent,
        600.0,
    )
    plan = plan_set([track("strong", themes=("heartbreak",), confidence=0.9, duration=180), track("unknown", duration=180)], target_duration_sec=600.0, intent=intent)
    assert pool.fallback_track_ids == ["unknown"]
    assert plan.intent_coverage["strong_match_count"] == 1
    assert plan.intent_coverage["unknown_count"] == 1
    assert any("unknown" in note for note in plan.intent_relaxation_steps)


def test_missing_hopeful_endpoint_is_honest():
    intent = SetIntent(
        desired_lyrical_moods=["sad", "hopeful"],
        meaning_trajectory=["sad", "hopeful"],
    )
    tracks = [
        track("sad", moods=("sad",), confidence=0.9),
        track("sad2", moods=("sad",), confidence=0.9),
    ]
    plan = plan_set(tracks, target_duration_sec=240.0, intent=intent)
    assert plan.intent_coverage
    assert any("no reliable 'hopeful' endpoint" in note for note in plan.intent_relaxation_steps)
