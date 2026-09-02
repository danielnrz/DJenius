"""Intent-first track relevance scoring.

This module deliberately sits before the technical DJ planner.  It answers
"does this track belong in the requested set?" without changing the
renderer-facing transition search.  Missing semantic evidence is represented
as unknown, rather than being treated as a match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from djenius.core.intent import SetIntent
from djenius.core.models import TrackProfile


STRONG_MATCH = "strong"
PARTIAL_MATCH = "partial"
UNKNOWN = "unknown"
CONTRADICTION = "contradiction"

_STATUS_RANK = {
    STRONG_MATCH: 3,
    PARTIAL_MATCH: 2,
    UNKNOWN: 1,
    CONTRADICTION: 0,
}

# Broad oppositions help distinguish reliable evidence even when a model did
# not return an explicit ``avoid`` label.  They are only used as a soft
# relevance signal; technical compatibility remains responsible for ordering.
_OPPOSITES = {
    "heartbreak": {"celebration", "party", "confidence", "success", "happy", "celebratory", "hopeful"},
    "breakup": {"celebration", "party", "happy", "celebratory", "hopeful"},
    "sad": {"happy", "euphoric", "celebratory", "celebration", "party"},
    "melancholic": {"happy", "euphoric", "celebratory", "celebration", "party"},
    "happy": {"sad", "melancholic", "dark", "heartbreak", "breakup", "loss", "loneliness"},
    "celebratory": {"sad", "melancholic", "heartbreak", "breakup", "loss"},
    "party": {"sad", "melancholic", "heartbreak", "breakup", "loneliness"},
    "romantic": {"angry", "anger", "aggressive"},
    "hopeful": {"sad", "melancholic", "heartbreak", "loss", "loneliness"},
    "relaxing": {"aggressive", "angry", "party"},
}

_RELATED_MEANING_LABELS = {
    "breakup": {"breakup", "heartbreak"},
    "heartbreak": {"heartbreak", "breakup"},
    "love": {"love", "romance"},
    "romance": {"romance", "love"},
}


@dataclass
class TrackIntentScore:
    """Evidence-aware relevance of one track to one SetIntent."""

    track_id: str
    title: str
    lyrics_theme_match: float = 0.5
    lyrics_mood_match: float = 0.5
    audio_mood_match: float = 0.5
    activity_match: float = 0.5
    energy_match: float = 0.5
    trajectory_suitability: float = 0.5
    explicit_exclusion_penalty: float = 0.0
    evidence_reliability: float = 0.0
    overall_intent_score: float = 0.5
    status: str = UNKNOWN
    explanation: str = ""
    evidence: list[str] = field(default_factory=list)

    @property
    def status_rank(self) -> int:
        return _STATUS_RANK.get(self.status, 0)

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "title": self.title,
            "lyrics_theme_match": round(self.lyrics_theme_match, 4),
            "lyrics_mood_match": round(self.lyrics_mood_match, 4),
            "audio_mood_match": round(self.audio_mood_match, 4),
            "activity_match": round(self.activity_match, 4),
            "energy_match": round(self.energy_match, 4),
            "trajectory_suitability": round(self.trajectory_suitability, 4),
            "explicit_exclusion_penalty": round(self.explicit_exclusion_penalty, 4),
            "evidence_reliability": round(self.evidence_reliability, 4),
            "overall_intent_score": round(self.overall_intent_score, 4),
            "status": self.status,
            "explanation": self.explanation,
            "evidence": list(self.evidence),
        }


@dataclass
class IntentCandidatePool:
    """The result of Stage A, including visible relaxation diagnostics."""

    tracks: list[TrackProfile]
    scores: dict[str, TrackIntentScore]
    excluded_track_ids: list[str] = field(default_factory=list)
    fallback_track_ids: list[str] = field(default_factory=list)
    relaxation_steps: list[str] = field(default_factory=list)
    target_duration_met: bool = True

    @property
    def candidate_track_ids(self) -> list[str]:
        return [track.id for track in self.tracks]


def intent_requests_semantics(intent: SetIntent | None) -> bool:
    if intent is None:
        return False
    return bool(
        intent.desired_themes
        or intent.avoid_themes
        or intent.desired_lyrical_moods
        or intent.avoid_lyrical_moods
        or intent.desired_moods
        or intent.avoid_moods
        or intent.desired_activity
        or intent.mood_trajectory
        or intent.meaning_trajectory
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _label_match(
    available: Iterable[str],
    desired: Iterable[str],
    *,
    primary: Iterable[str] = (),
) -> float:
    wanted = set(desired)
    if not wanted:
        return 0.5
    available_set = set(available)
    primary_set = set(primary)
    if not available_set:
        return 0.0
    hits = wanted & available_set
    if not hits:
        return 0.0
    primary_hits = hits & primary_set
    # Labels emitted by the parser are usually alternatives ("heartbreak",
    # "breakup", "nostalgia"), not an AND requirement.  One reliable hit is
    # therefore already strong evidence; extra hits increase the score.
    hit_score = 0.85 + 0.15 * min(1.0, (len(hits) - 1) / max(len(wanted) - 1, 1))
    if primary_hits:
        hit_score = 1.0
    return _clamp(hit_score)


def _score_map_match(
    scores: dict[str, float],
    desired: Iterable[str],
    avoided: Iterable[str] = (),
) -> float:
    wanted = list(desired)
    avoid = list(avoided)
    if not wanted and not avoid:
        return 0.5
    positive = max((float(scores.get(label, 0.0)) for label in wanted), default=0.0)
    negative = max((float(scores.get(label, 0.0)) for label in avoid), default=0.0)
    return _clamp(positive - 0.45 * negative)


def _energy_match(track: TrackProfile, intent: SetIntent) -> float:
    if intent.energy_min is None and intent.energy_max is None:
        # Audio words still imply a useful but deliberately weak energy cue.
        high = set(intent.desired_moods) | set(intent.desired_activity)
        if high & {"happy", "euphoric", "dance", "party", "workout"}:
            return _clamp(track.mean_energy / 0.75)
        if set(intent.desired_moods) & {"sad", "melancholic", "calm", "dark"} or "relaxing" in intent.desired_activity:
            return _clamp(1.0 - track.mean_energy)
        return 0.5
    minimum = intent.energy_min if intent.energy_min is not None else 0.0
    maximum = intent.energy_max if intent.energy_max is not None else 1.0
    if minimum <= track.mean_energy <= maximum:
        return 1.0
    distance = minimum - track.mean_energy if track.mean_energy < minimum else track.mean_energy - maximum
    return _clamp(1.0 - distance / 0.5)


def _reliable_meaning(track: TrackProfile):
    meaning = track.lyrics.meaning if track.lyrics else None
    if meaning is None:
        return None, 0.0
    reliability = _clamp(float(meaning.meaning_confidence))
    if track.lyrics and track.lyrics.transcription_confidence:
        reliability *= _clamp(float(track.lyrics.transcription_confidence) / 0.65)
    return meaning, reliability


def score_track_intent(track: TrackProfile, intent: SetIntent) -> TrackIntentScore:
    """Score one track for request satisfaction, preserving unknown evidence."""
    meaning, lyric_reliability = _reliable_meaning(track)
    semantic = track.semantic
    audio_reliability = _clamp(float(semantic.semantic_confidence)) if semantic else 0.0

    meaning_requested = bool(
        intent.desired_themes or intent.avoid_themes
        or intent.desired_lyrical_moods or intent.avoid_lyrical_moods
        or intent.meaning_trajectory
    )
    audio_requested = bool(
        intent.desired_moods or intent.avoid_moods or intent.desired_activity
        or intent.mood_trajectory or intent.energy_min is not None
        or intent.energy_max is not None
    )

    lyrics_theme_match = 0.5
    lyrics_mood_match = 0.5
    audio_mood_match = 0.5
    activity_match = 0.5
    trajectory = 0.5
    evidence: list[str] = []

    themes: set[str] = set()
    lyrical_moods: set[str] = set()
    if meaning is not None:
        themes = set(meaning.primary_themes + meaning.secondary_themes)
        lyrical_moods = set(meaning.lyrical_moods)
        # Structured meaning also carries scalar context.  Turning those
        # fields into conservative evidence keeps "party" and "hopeful"
        # requests useful even when the local model chose a nearby label such
        # as "celebration" or "confidence".
        if meaning.party_context >= 0.55 or meaning.celebration >= 0.55:
            themes.update({"party", "celebration"})
            lyrical_moods.update({"happy", "celebratory"})
        if meaning.hopefulness >= 0.55:
            themes.add("hope")
            lyrical_moods.add("hopeful")
        if meaning.sadness >= 0.55:
            themes.update({"loss", "heartbreak"})
            lyrical_moods.update({"sad", "melancholic"})
        if meaning.romance >= 0.55:
            themes.update({"love", "romance"})
            lyrical_moods.add("romantic")
        lyrics_theme_match = _label_match(
            themes, intent.desired_themes, primary=meaning.primary_themes,
        )
        lyrics_mood_match = _label_match(lyrical_moods, intent.desired_lyrical_moods)
        trajectory_labels = set(intent.meaning_trajectory)
        trajectory = _label_match(lyrical_moods | themes, trajectory_labels)
        if themes:
            evidence.append("lyrics themes: " + ", ".join(sorted(themes)))
        if lyrical_moods:
            evidence.append("lyrical moods: " + ", ".join(sorted(lyrical_moods)))
    elif meaning_requested:
        evidence.append("lyrics meaning unavailable")

    if semantic is not None:
        audio_mood_match = _score_map_match(
            semantic.mood_scores, intent.desired_moods, intent.avoid_moods,
        )
        activity_match = _score_map_match(
            semantic.activity_scores, intent.desired_activity,
        )
        if semantic.semantic_tags:
            evidence.append("audio cues: " + ", ".join(semantic.semantic_tags[:4]))
    elif audio_requested:
        evidence.append("audio semantic profile unavailable")

    energy_match = _energy_match(track, intent)
    avoided_labels = set(intent.avoid_themes) | set(intent.avoid_lyrical_moods)
    avoided_labels |= set(intent.avoid_moods)
    explicit_penalty = 0.0
    if meaning is not None and lyric_reliability >= 0.6:
        explicit_penalty = max(
            [1.0 for label in avoided_labels if (
                themes | lyrical_moods
            ).intersection(_RELATED_MEANING_LABELS.get(label, {label}))]
            or [0.0]
        )
        if explicit_penalty:
            evidence.append("reliable excluded meaning")
    if semantic is not None:
        explicit_penalty = max(
            explicit_penalty,
            0.85 if any(float(semantic.mood_scores.get(label, 0.0)) >= 0.35 for label in intent.avoid_moods) else 0.0,
        )

    requested_labels = set(intent.desired_themes) | set(intent.desired_lyrical_moods)
    requested_labels |= set(intent.desired_moods) | set(intent.desired_activity)
    observed_labels = themes | lyrical_moods
    if semantic:
        observed_labels |= {
            label for label, value in semantic.mood_scores.items() if value >= 0.35
        }
        observed_labels |= {
            label for label, value in semantic.activity_scores.items() if value >= 0.35
        }
    opposite = any(
        observed_labels & _OPPOSITES.get(label, set())
        for label in requested_labels
    )

    if meaning_requested and meaning is not None and lyric_reliability >= 0.6:
        lyric_match = (
            max(lyrics_theme_match, lyrics_mood_match)
            if intent.meaning_trajectory
            else 0.75 * lyrics_theme_match + 0.25 * lyrics_mood_match
        )
        if lyric_match >= 0.55:
            evidence_reliability = lyric_reliability
            status = STRONG_MATCH if lyric_match >= 0.72 else PARTIAL_MATCH
        else:
            evidence_reliability = lyric_reliability
            status = CONTRADICTION if opposite or lyric_match < 0.25 else PARTIAL_MATCH
        if explicit_penalty >= 0.8:
            status = CONTRADICTION
    elif meaning_requested:
        evidence_reliability = max(audio_reliability * 0.55, lyric_reliability)
        status = UNKNOWN
    elif audio_requested and semantic is not None and audio_reliability >= 0.35:
        audio_match = 0.65 * audio_mood_match + 0.25 * activity_match + 0.10 * energy_match
        status = STRONG_MATCH if audio_match >= 0.62 else PARTIAL_MATCH if audio_match >= 0.35 else CONTRADICTION if opposite else UNKNOWN
        evidence_reliability = audio_reliability
    elif intent_requests_semantics(intent):
        status = UNKNOWN
        evidence_reliability = 0.0
    else:
        status = STRONG_MATCH
        evidence_reliability = 1.0

    if meaning_requested:
        lyric_match = (
            max(lyrics_theme_match, lyrics_mood_match)
            if intent.meaning_trajectory
            else 0.75 * lyrics_theme_match + 0.25 * lyrics_mood_match
        )
        if meaning is not None and lyric_reliability >= 0.6:
            overall = 0.62 * lyric_match
            if audio_requested:
                overall += 0.16 * audio_mood_match + 0.10 * activity_match
            overall += 0.07 * energy_match + 0.05 * trajectory
        else:
            # Unknown lyrics remain usable as fallback, but can never look
            # like a reliable theme match merely because BPM/key are good.
            overall = 0.24 + 0.10 * audio_mood_match + 0.08 * activity_match + 0.08 * energy_match
            overall *= max(0.65, 1.0 - 0.35 * (1.0 - evidence_reliability))
    elif audio_requested:
        overall = 0.62 * audio_mood_match + 0.20 * activity_match + 0.13 * energy_match + 0.05 * trajectory
    else:
        overall = 0.5

    overall -= 0.62 * explicit_penalty
    if status == CONTRADICTION and meaning is not None and lyric_reliability >= 0.6:
        overall = min(overall, 0.18)
    elif status == UNKNOWN:
        overall = min(overall, 0.48)
    overall = _clamp(overall)

    if status == STRONG_MATCH:
        prefix = "Strong match"
    elif status == PARTIAL_MATCH:
        prefix = "Partial match"
    elif status == CONTRADICTION:
        prefix = "Reliable contradiction"
    else:
        prefix = "Fallback"
    explanation = prefix
    if evidence:
        explanation += " — " + "; ".join(evidence[:2])
    return TrackIntentScore(
        track_id=track.id,
        title=track.title,
        lyrics_theme_match=lyrics_theme_match,
        lyrics_mood_match=lyrics_mood_match,
        audio_mood_match=audio_mood_match,
        activity_match=activity_match,
        energy_match=energy_match,
        trajectory_suitability=trajectory,
        explicit_exclusion_penalty=explicit_penalty,
        evidence_reliability=evidence_reliability,
        overall_intent_score=overall,
        status=status,
        explanation=explanation,
        evidence=evidence,
    )


def trajectory_label_score(track: TrackProfile, label: str) -> float:
    """Return evidence that a track can occupy a semantic trajectory point."""
    meaning, lyric_reliability = _reliable_meaning(track)
    if meaning is not None and lyric_reliability >= 0.6:
        labels = set(meaning.primary_themes + meaning.secondary_themes + meaning.lyrical_moods)
        if label in labels:
            return 1.0
        if label in {"hope", "hopeful"} and meaning.hopefulness >= 0.55:
            return 1.0
        if label in {"happy", "celebratory", "party"} and (
            meaning.celebration >= 0.55 or meaning.party_context >= 0.55
        ):
            return 1.0
        if label in {"sad", "melancholic"} and meaning.sadness >= 0.55:
            return 1.0
        if labels & _OPPOSITES.get(label, set()):
            return 0.0
        return 0.15
    if track.semantic:
        return _clamp(float(track.semantic.mood_scores.get(label, 0.5)))
    return 0.5


def rank_tracks_by_intent(
    tracks: list[TrackProfile], intent: SetIntent,
) -> list[TrackIntentScore]:
    scores = [score_track_intent(track, intent) for track in tracks]
    return sorted(
        scores,
        key=lambda score: (score.status_rank, score.overall_intent_score),
        reverse=True,
    )


def select_intent_candidate_pool(
    tracks: list[TrackProfile],
    intent: SetIntent,
    target_duration_sec: float,
) -> IntentCandidatePool:
    """Select a relevance-first pool and relax only as duration requires."""
    scores = {score.track_id: score for score in (score_track_intent(t, intent) for t in tracks)}
    ranked = sorted(
        tracks,
        key=lambda track: (
            scores[track.id].status_rank,
            scores[track.id].overall_intent_score,
        ),
        reverse=True,
    )
    explicit_exclusions = bool(
        intent.raw_text
        and re.search(r"\b(?:avoid|exclude|never|without|only)\b", intent.raw_text.lower())
    )
    explicit_structured_exclusions = not intent.raw_text and bool(
        intent.avoid_themes or intent.avoid_lyrical_moods or intent.avoid_moods
    )
    excluded = [
        track.id for track in ranked
        if scores[track.id].status == CONTRADICTION
        and (explicit_exclusions or explicit_structured_exclusions)
    ]
    usable = [track for track in ranked if track.id not in excluded]
    strong_partial = [track for track in usable if scores[track.id].status in {STRONG_MATCH, PARTIAL_MATCH}]
    unknown = [track for track in usable if scores[track.id].status == UNKNOWN]
    contradictions = [track for track in usable if scores[track.id].status == CONTRADICTION]

    # A two-track minimum is required by the technical planner.  Otherwise,
    # first satisfy the request with relevant material and only then relax for
    # duration.  A simple 90% effective-duration estimate avoids padding a
    # coherent short set with an unrelated full track.
    chosen: list[TrackProfile] = []
    relaxation_steps: list[str] = []
    fallback_ids: list[str] = []

    def effective_duration(items: list[TrackProfile]) -> float:
        return sum(max(0.0, item.duration_sec * 0.9) for item in items)

    for track in strong_partial:
        chosen.append(track)
    if not chosen and unknown:
        relaxation_steps.append("No strong or partial intent matches; using unknown semantic evidence.")

    if len(chosen) < 2:
        for track in unknown:
            if track not in chosen:
                chosen.append(track)
                fallback_ids.append(track.id)
            if len(chosen) >= 2:
                break
        if unknown and strong_partial:
            relaxation_steps.append("Added tracks with unknown meaning only to reach the technical two-track minimum.")

    if effective_duration(chosen) < target_duration_sec and unknown:
        for track in unknown:
            if track in chosen:
                continue
            chosen.append(track)
            fallback_ids.append(track.id)
            if effective_duration(chosen) >= target_duration_sec:
                relaxation_steps.append("Relaxed to unknown meaning evidence to approach the requested duration.")
                break

    # A user who explicitly asks for variety is asking for more than a
    # duration-sufficient two-track pool.  Add unknown tracks only up to a
    # small soft diversity target, and only after all strong/partial evidence
    # has been admitted.  This keeps intent relevance ahead of novelty.
    if (
        intent.performance_mode == "segment"
        and intent.desired_variety >= 0.65
        and unknown
    ):
        desired_unique = min(
            len(tracks),
            max(3, min(8, int(round(target_duration_sec / 75.0)))),
        )
        if len(chosen) < desired_unique:
            for track in unknown:
                if track in chosen:
                    continue
                chosen.append(track)
                fallback_ids.append(track.id)
                if len(chosen) >= desired_unique:
                    relaxation_steps.append(
                        "Added unknown-evidence tracks to support the requested variety while keeping known matches first."
                    )
                    break

    if len(chosen) < 2 and contradictions:
        for track in contradictions:
            if track in chosen:
                continue
            chosen.append(track)
            fallback_ids.append(track.id)
            if len(chosen) >= 2 and effective_duration(chosen) >= target_duration_sec:
                relaxation_steps.append("Used the least contradictory remaining track as a last-resort duration fallback.")
                break

    # If there are no semantic fields, preserve the old planner's full pool.
    if not intent_requests_semantics(intent):
        chosen = list(tracks)
        excluded = []
        fallback_ids = []
        relaxation_steps = []

    unique: dict[str, TrackProfile] = {}
    for track in chosen:
        unique.setdefault(track.id, track)
    chosen = list(unique.values())
    target_met = effective_duration(chosen) >= target_duration_sec
    if not target_met and chosen:
        relaxation_steps.append("The library cannot provide the requested duration without weaker intent matches; preserving coherence.")
    return IntentCandidatePool(
        tracks=chosen,
        scores=scores,
        excluded_track_ids=excluded,
        fallback_track_ids=fallback_ids,
        relaxation_steps=relaxation_steps,
        target_duration_met=target_met,
    )


def summarize_intent_coverage(
    selected: list[TrackProfile],
    scores: dict[str, TrackIntentScore],
    target_duration_sec: float,
) -> dict:
    counts = {status: 0 for status in (STRONG_MATCH, PARTIAL_MATCH, UNKNOWN, CONTRADICTION)}
    for track in selected:
        status = scores.get(track.id, TrackIntentScore(track.id, track.title)).status
        counts[status] += 1
    total = len(selected)
    weighted = counts[STRONG_MATCH] + 0.6 * counts[PARTIAL_MATCH]
    coverage = weighted / total if total else 0.0
    if counts[CONTRADICTION]:
        label = "Limited"
    elif counts[STRONG_MATCH] == total and total:
        label = "Strong"
    elif coverage >= 0.6:
        label = "Good"
    else:
        label = "Limited"
    return {
        "label": label,
        "coverage": round(coverage, 3),
        "selected_count": total,
        "strong_match_count": counts[STRONG_MATCH],
        "partial_match_count": counts[PARTIAL_MATCH],
        "unknown_count": counts[UNKNOWN],
        "contradiction_count": counts[CONTRADICTION],
        "target_duration_sec": round(target_duration_sec, 1),
        "selected_duration_sec": round(sum(track.duration_sec for track in selected), 1),
    }
