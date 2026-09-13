from __future__ import annotations

import numpy as np
import pytest

from djenius.core.analysis_v2 import build_tempo_hypotheses
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile
from djenius.core.set_director import (
    EdgeAuditionCache,
    SetArc,
    SetDirectorConfig,
    plan_set_v2,
)

SR = 6000
DURATION = 60.0


def _track(
    track_id: str,
    *,
    bpm: float = 120.0,
    camelot: str = "8A",
    mean_energy: float = 0.5,
    artist: str = "",
) -> TrackProfile:
    third = DURATION / 3.0
    sections = [
        {"start_sec": 0.0, "end_sec": third, "label": "intro", "boundary_confidence": 0.9,
         "mix_in_score": 0.9, "mix_out_score": 0.35, "landing_strength": 0.3, "bass_density": 0.55, "energy_mean": mean_energy},
        {"start_sec": third, "end_sec": 2 * third, "label": "drop", "boundary_confidence": 0.9,
         "mix_in_score": 0.88, "mix_out_score": 0.78, "landing_strength": 0.75, "bass_density": 0.65, "energy_mean": mean_energy},
        {"start_sec": 2 * third, "end_sec": DURATION, "label": "outro", "boundary_confidence": 0.9,
         "mix_in_score": 0.3, "mix_out_score": 0.96, "landing_strength": 0.25, "bass_density": 0.5, "energy_mean": mean_energy},
    ]
    cues = [
        {"time_sec": 0.0, "bar_index": 1, "beat_in_bar": 1, "confidence": 0.9, "section": "intro",
         "use_cases": ["mix_in"], "mix_in_score": 0.9, "mix_out_score": 0.2},
        {"time_sec": third, "bar_index": 17, "beat_in_bar": 1, "confidence": 0.9, "section": "drop",
         "use_cases": ["mix_in", "phrase_cut", "drop_landing"], "mix_in_score": 0.88, "mix_out_score": 0.78},
        {"time_sec": 2 * third, "bar_index": 33, "beat_in_bar": 1, "confidence": 0.9, "section": "outro",
         "use_cases": ["mix_out", "phrase_cut"], "mix_in_score": 0.3, "mix_out_score": 0.96},
    ]
    analysis = TrackAnalysis(
        bpm=bpm, bpm_confidence=0.97, camelot=camelot, analysis_confidence=0.95,
        tempo_hypotheses=build_tempo_hypotheses(bpm, 0.97),
        section_profiles=sections, cue_candidates=cues,
        vocal_activity_curve=[0.08] * int(DURATION), energy_curve=[mean_energy] * int(DURATION),
        mean_energy=mean_energy, low_energy=0.55,
        groove_profile={"confidence": 0.9, "syncopation_index": 0.25, "swing_ratio": 1.0, "percussion_density_mean": 0.55},
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(filepath=f"/synthetic/{track_id}.wav", duration_sec=DURATION, artist=artist),
        analysis=analysis,
    )


def _pulse_audio(*, bpm: float, gain: float = 0.30) -> np.ndarray:
    n = int(round(DURATION * SR))
    t = np.arange(n, dtype=np.float64) / SR
    mono = 0.035 * np.sin(2 * np.pi * 220.0 * t) + 0.02 * np.sin(2 * np.pi * 880.0 * t)
    beat = 60.0 / bpm
    pulse_len = max(6, int(round(0.012 * SR)))
    for beat_time in np.arange(0.0, DURATION, beat):
        start = int(round(beat_time * SR))
        if start >= n:
            continue
        end = min(n, start + pulse_len)
        envelope = np.linspace(1.0, 0.0, end - start, dtype=np.float64)
        mono[start:end] += gain * envelope
    return np.column_stack([mono, mono]).astype(np.float32)


def _provider(audio_by_id: dict[str, np.ndarray]):
    from djenius.core.set_director import TrackAudio

    def provide(track: TrackProfile) -> TrackAudio:
        return TrackAudio(audio=audio_by_id[track.id], sample_rate=SR)
    return provide


def _small_config(**overrides) -> SetDirectorConfig:
    base = dict(beam_width=3, shortlist_width=3, max_candidates_audited_per_edge=2)
    base.update(overrides)
    return SetDirectorConfig(**base)


def test_config_validate_requires_user_preference_weight():
    config = SetDirectorConfig()
    config.validate()
    assert "user_preference" in config.weights
    assert "user_preference" in SetDirectorConfig.EDGE_COMPONENTS

    incomplete = SetDirectorConfig(weights={k: v for k, v in config.weights.items() if k != "user_preference"})
    with pytest.raises(ValueError):
        incomplete.validate()


def test_technique_preference_reflected_in_user_preference_component():
    a = _track("a", bpm=120.0)
    b = _track("b", bpm=121.0)
    audio = _provider({"a": _pulse_audio(bpm=120.0), "b": _pulse_audio(bpm=121.0)})
    # beam_width=1 with only two tracks forces a single deterministic
    # opener/edge (A -> B); with a wider beam both A->B and B->A would be
    # explored as separate candidate paths, and since they can have
    # different audition winners, changing technique_preferences could
    # legitimately flip *which path* wins rather than only its score --
    # a real and correct behavior, just not what this narrower test targets.
    config = _small_config(beam_width=1)

    neutral_plan = plan_set_v2(
        [a, b], audio_provider=audio, target_duration_sec=90.0, arc=SetArc.SMOOTH,
        config=config, cache=EdgeAuditionCache(),
    )
    assert len(neutral_plan.edges) == 1
    family = neutral_plan.edges[0].handoff.selected_family
    assert family is not None
    assert neutral_plan.edges[0].component_scores["user_preference"] == pytest.approx(0.5)

    liked_config = _small_config(beam_width=1, technique_preferences={family: 0.95})
    liked_plan = plan_set_v2(
        [a, b], audio_provider=audio, target_duration_sec=90.0, arc=SetArc.SMOOTH,
        config=liked_config, cache=EdgeAuditionCache(),
    )
    assert liked_plan.edges[0].handoff.selected_family == family
    assert liked_plan.edges[0].component_scores["user_preference"] == pytest.approx(0.95)

    disliked_config = _small_config(beam_width=1, technique_preferences={family: 0.05})
    disliked_plan = plan_set_v2(
        [a, b], audio_provider=audio, target_duration_sec=90.0, arc=SetArc.SMOOTH,
        config=disliked_config, cache=EdgeAuditionCache(),
    )
    assert disliked_plan.edges[0].handoff.selected_family == family
    assert disliked_plan.edges[0].component_scores["user_preference"] == pytest.approx(0.05)
    assert liked_plan.total_score > neutral_plan.total_score > disliked_plan.total_score


def test_disliked_track_is_avoided_in_favor_of_an_equally_good_alternative():
    # SMOOTH's opening energy target is ~0.42; giving the intended opener an
    # exact match (while the other two stay at the 0.5 default) makes it win
    # the start-of-set slot deterministically, regardless of id ordering.
    opener = _track("opener", bpm=120.0, camelot="8A", mean_energy=0.42)
    # Identical bpm/key/energy so the only real difference is the preference.
    tempting_but_disliked = _track("disliked_next", bpm=121.0, camelot="8A")
    fine_alternative = _track("fine_next", bpm=121.0, camelot="8A")
    tracks = [opener, tempting_but_disliked, fine_alternative]
    audio = _provider({
        "opener": _pulse_audio(bpm=120.0),
        "disliked_next": _pulse_audio(bpm=121.0),
        "fine_next": _pulse_audio(bpm=121.0),
    })
    # Candidate IDs are content-hashed from (among other things) the track
    # ids themselves, so which small subset of the full candidate set a
    # bounded audition samples can differ between two otherwise-identical
    # fixtures that only differ by id. Auditioning the full candidate set
    # here removes that sampling noise so the preference signal is the only
    # real difference between the two paths.
    config = _small_config(
        beam_width=2, shortlist_width=3, max_candidates_audited_per_edge=8,
        disliked_track_ids=frozenset({"disliked_next"}),
    )
    # max_tracks=2 makes "which of the two equally-good options is chosen"
    # an actual choice; without a cap all three tracks fit comfortably
    # within the target duration and both get used regardless of order.
    plan = plan_set_v2(
        tracks, audio_provider=audio, target_duration_sec=100.0, arc=SetArc.SMOOTH,
        max_tracks=2, config=config,
    )
    assert plan.track_ids[0] == "opener"
    assert plan.track_ids[1] == "fine_next", f"expected the disliked track to be avoided, got {plan.track_ids}"


def test_liked_track_is_preferred_over_an_equally_good_alternative():
    opener = _track("opener2", bpm=120.0, camelot="8A", mean_energy=0.42)
    liked_next = _track("liked_next", bpm=121.0, camelot="8A")
    plain_next = _track("plain_next", bpm=121.0, camelot="8A")
    tracks = [opener, liked_next, plain_next]
    audio = _provider({
        "opener2": _pulse_audio(bpm=120.0),
        "liked_next": _pulse_audio(bpm=121.0),
        "plain_next": _pulse_audio(bpm=121.0),
    })
    config = _small_config(
        beam_width=2, shortlist_width=3, max_candidates_audited_per_edge=8,
        liked_track_ids=frozenset({"liked_next"}),
    )
    plan = plan_set_v2(
        tracks, audio_provider=audio, target_duration_sec=100.0, arc=SetArc.SMOOTH,
        max_tracks=2, config=config,
    )
    assert plan.track_ids[0] == "opener2"
    assert plan.track_ids[1] == "liked_next", f"expected the liked track to be preferred, got {plan.track_ids}"
