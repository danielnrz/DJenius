"""Core data models for DJenius.

These dataclasses define the boundary between the DJ Brain and the Audio Engine.
The Brain produces instances of these models. The Engine consumes them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from djenius.core.intent import SetIntent


class TransitionType(Enum):
    """Types of transitions the engine can execute."""
    PHRASE_CUT = "phrase_cut"
    CROSSFADE = "crossfade"
    BEATMATCHED_BLEND = "beatmatched_blend"
    BASS_SWAP = "bass_swap"
    FILTER_SWEEP = "filter_sweep"
    ECHO_OUT = "echo_out"
    LOOP_BLEND = "loop_blend"
    MASHUP = "mashup"


class EnergyProfile(Enum):
    """Set energy profiles for overall journey planning."""
    STEADY = "steady"
    SLOW_BUILD = "slow_build"
    WARMUP_TO_PEAK = "warmup_to_peak"
    WAVE = "wave"
    PEAK_EARLY = "peak_early"
    PEAK_LATE = "peak_late"
    COOLDOWN = "cooldown"


@dataclass
class TrackMetadata:
    """Basic file and metadata information."""
    filepath: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_sec: float = 0.0
    sample_rate: int = 44100
    channels: int = 2
    format: str = ""
    file_hash: str = ""


@dataclass
class TrackAnalysis:
    """Results from audio analysis. This is the detailed musical profile."""
    # Tempo
    bpm: float = 0.0
    bpm_confidence: float = 0.0

    # Beats and structure
    beat_times: list[float] = field(default_factory=list)
    downbeat_times: list[float] = field(default_factory=list)
    bar_times: list[float] = field(default_factory=list)
    estimated_bars: int = 0

    # Key
    key: str = ""           # e.g., "C Minor"
    camelot: str = ""       # e.g., "5A"
    key_confidence: float = 0.0

    # Loudness
    integrated_lufs: float = 0.0
    peak_level: float = 0.0
    rms_energy: float = 0.0

    # Energy
    energy_curve: list[float] = field(default_factory=list)  # 1Hz resolution, 0-1
    loudness_curve: list[float] = field(default_factory=list)  # short-term RMS dBFS
    low_energy_curve: list[float] = field(default_factory=list)  # low-band ratio
    spectral_centroid_curve: list[float] = field(default_factory=list)
    mean_energy: float = 0.0

    # Spectral features
    spectral_centroid_mean: float = 0.0
    low_energy: float = 0.0     # avg energy < 300Hz
    mid_energy: float = 0.0     # avg energy 300-4000Hz
    high_energy: float = 0.0    # avg energy > 4000Hz

    # Phrase and structure
    phrase_boundaries: list[float] = field(default_factory=list)  # timestamps in sec
    structural_sections: list[tuple[float, float, str]] = field(default_factory=list)
    intro_end: float = 0.0
    outro_start: float = 0.0
    bar_energies: list[float] = field(default_factory=list)  # mean energy per bar

    # Vocal regions
    vocal_regions: list[tuple[float, float]] = field(default_factory=list)  # (start, end) in sec

    # Stem file paths (optional — None when stems not extracted)
    stems: dict[str, str] | None = None  # e.g. {"vocals": "/path/to/vocals.wav", ...}

    # Transition regions
    possible_exit_points: list[float] = field(default_factory=list)
    possible_entry_points: list[float] = field(default_factory=list)

    # Analysis quality
    analysis_confidence: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, list) and len(v) > 200:
                # Downsample large arrays for storage
                step = max(1, len(v) // 200)
                d[k] = v[::step]
            else:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TrackAnalysis":
        """Deserialize from dict."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class SemanticProfile:
    """Local model estimates of a track's mood, activity, and style.

    Scores are model estimates, not ground truth.  The embedding is retained
    so future intent vocabularies can be scored without decoding audio again.
    """

    model_name: str = ""
    model_version: str = ""
    embedding: list[float] = field(default_factory=list)
    mood_scores: dict[str, float] = field(default_factory=dict)
    activity_scores: dict[str, float] = field(default_factory=dict)
    intensity_scores: dict[str, float] = field(default_factory=dict)
    style_scores: dict[str, float] = field(default_factory=dict)
    semantic_tags: list[str] = field(default_factory=list)
    semantic_confidence: float = 0.0
    # V7.1 keeps the track summary for the existing planner, but also retains
    # the evidence used to make it.  Scores are relative model matches, not
    # calibrated probabilities.
    sample_windows: list[dict] = field(default_factory=list)
    whole_track_summary: dict[str, dict[str, float]] = field(default_factory=dict)
    raw_score_summary: dict[str, dict[str, float]] = field(default_factory=dict)
    group_metrics: dict[str, dict[str, float | str]] = field(default_factory=dict)
    reliability_by_group: dict[str, float] = field(default_factory=dict)
    semantic_variability: float = 0.0
    score_calibration: str = "relative_match"
    source_file_hash: str = ""
    analyzed_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "embedding": self.embedding,
            "mood_scores": self.mood_scores,
            "activity_scores": self.activity_scores,
            "intensity_scores": self.intensity_scores,
            "style_scores": self.style_scores,
            "semantic_tags": self.semantic_tags,
            "semantic_confidence": self.semantic_confidence,
            "sample_windows": self.sample_windows,
            "whole_track_summary": self.whole_track_summary,
            "raw_score_summary": self.raw_score_summary,
            "group_metrics": self.group_metrics,
            "reliability_by_group": self.reliability_by_group,
            "semantic_variability": self.semantic_variability,
            "score_calibration": self.score_calibration,
            "source_file_hash": self.source_file_hash,
            "analyzed_at": self.analyzed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticProfile":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in data.items() if key in known})


@dataclass
class LyricsMeaningProfile:
    """Validated, local estimates of what a song's lyrics express.

    Numeric values are bounded model estimates, never claims about objective
    meaning.  The taxonomy is deliberately small so planner behavior remains
    inspectable.
    """

    model_name: str = ""
    model_version: str = ""
    primary_themes: list[str] = field(default_factory=list)
    secondary_themes: list[str] = field(default_factory=list)
    lyrical_moods: list[str] = field(default_factory=list)
    emotional_valence: float = 0.0  # -1 = negative, +1 = positive
    emotional_intensity: float = 0.0
    relationship_context: str = ""
    party_context: float = 0.0
    hopefulness: float = 0.0
    sadness: float = 0.0
    romance: float = 0.0
    anger: float = 0.0
    celebration: float = 0.0
    meaning_confidence: float = 0.0
    meaning_source: str = ""
    analyzed_at: float = 0.0

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict | None) -> "LyricsMeaningProfile | None":
        if not data:
            return None
        known = {f.name for f in cls.__dataclass_fields__.values()}
        values = {key: value for key, value in data.items() if key in known}
        for key in ("emotional_valence", "emotional_intensity", "party_context", "hopefulness", "sadness", "romance", "anger", "celebration", "meaning_confidence"):
            if key in values:
                values[key] = float(values[key])
        return cls(**values)


@dataclass
class LyricsProfile:
    """Lyrics acquisition plus optional song-level meaning interpretation."""

    source: str = "unavailable"
    language: str = ""
    text: str = ""
    segments: list[dict] = field(default_factory=list)
    transcription_backend: str = ""
    transcription_model: str = ""
    transcription_model_version: str = ""
    transcription_confidence: float = 0.0
    language_confidence: float = 0.0
    hallucination_detected: bool = False
    meaning: Optional[LyricsMeaningProfile] = None
    source_file_hash: str = ""
    analysis_version: str = ""
    analyzed_at: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        result = self.__dict__.copy()
        result["meaning"] = self.meaning.to_dict() if self.meaning else None
        return result

    @classmethod
    def from_dict(cls, data: dict | None) -> "LyricsProfile | None":
        if not data:
            return None
        known = {f.name for f in cls.__dataclass_fields__.values()}
        values = {key: value for key, value in data.items() if key in known}
        values["meaning"] = LyricsMeaningProfile.from_dict(values.get("meaning"))
        return cls(**values)


@dataclass
class TrackProfile:
    """Complete profile of a track - metadata + analysis combined."""
    id: str = ""               # unique identifier (file hash)
    metadata: TrackMetadata = field(default_factory=TrackMetadata)
    analysis: TrackAnalysis = field(default_factory=TrackAnalysis)
    semantic: Optional[SemanticProfile] = None
    lyrics: Optional[LyricsProfile] = None

    @property
    def filepath(self) -> str:
        return self.metadata.filepath

    @property
    def bpm(self) -> float:
        return self.analysis.bpm

    @property
    def camelot(self) -> str:
        return self.analysis.camelot

    @property
    def duration_sec(self) -> float:
        return self.metadata.duration_sec

    @property
    def mean_energy(self) -> float:
        return self.analysis.mean_energy

    @property
    def title(self) -> str:
        return self.metadata.title or Path(self.metadata.filepath).stem


@dataclass
class CompatibilityScore:
    """Detailed compatibility between two tracks."""
    source_id: str = ""
    target_id: str = ""

    # Individual component scores (0.0 to 1.0)
    tempo_score: float = 0.0
    key_score: float = 0.0
    energy_score: float = 0.0
    spectral_score: float = 0.0
    vocal_safety: float = 1.0  # 1.0 = safe, 0.0 = likely vocal clash
    semantic_similarity_score: float = 0.5
    mood_continuity_score: float = 0.5
    activity_compatibility_score: float = 0.5
    lyrical_theme_similarity: float = 0.5
    lyrical_mood_continuity: float = 0.5
    lyrical_context_compatibility: float = 0.5

    # Weighted final score
    overall_score: float = 0.0

    # Explanation
    reasoning: str = ""


@dataclass
class TransitionQualityScore:
    """Deterministic musical-context assessment for one transition plan."""
    phrase_alignment_score: float = 0.0
    bar_alignment_score: float = 0.0
    tempo_compatibility_score: float = 0.0
    harmonic_compatibility_score: float = 0.0
    energy_continuity_score: float = 0.0
    loudness_continuity_score: float = 0.0
    bass_handoff_score: float = 0.0
    vocal_clash_score: float = 0.0
    structural_context_score: float = 0.0
    transition_style_fit_score: float = 0.0
    track_playtime_score: float = 0.0
    target_landing_score: float = 0.0
    transition_floor_score: float = 0.0
    overall_score: float = 0.0


@dataclass
class TransitionRecipe:
    """Renderer-facing musical instructions selected by the DJ planner."""
    source_gain_db: float = 0.0
    target_gain_db: float = 0.0
    landing_gain_decay_sec: float = 10.0
    transition_floor_db: float = 4.5
    max_transition_boost_db: float = 6.0
    bass_handoff_mode: str = "source_to_target"
    vocal_policy: str = "avoid_overlap"
    energy_delta: float = 0.0
    confidence: float = 0.0
    reasoning: str = ""


@dataclass
class TransitionPlan:
    """A plan for transitioning between two tracks. DJ Brain output."""
    source_track_id: str = ""
    target_track_id: str = ""
    transition_type: TransitionType = TransitionType.PHRASE_CUT

    # Timing
    source_exit_time: float = 0.0      # seconds into source track
    target_entry_time: float = 0.0     # seconds into target track
    overlap_duration: float = 0.0      # how long both tracks play together
    length_bars: int = 8               # musical length of transition

    # Beatmatching
    target_bpm: float = 0.0            # BPM to stretch target to (0 = don't stretch)
    requires_stretch: bool = False
    stretch_amount_pct: float = 0.0    # how much stretching needed

    # Quality
    compatibility_score: Optional[CompatibilityScore] = None
    confidence: float = 0.0
    reasoning: str = ""
    quality_score: Optional[TransitionQualityScore] = None
    recipe: Optional[TransitionRecipe] = None
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["transition_type"] = self.transition_type.value
        if self.compatibility_score:
            d["compatibility_score"] = asdict(self.compatibility_score)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TransitionPlan":
        """Deserialize from dict."""
        tt_str = d.get("transition_type", "phrase_cut")
        try:
            tt = TransitionType(tt_str)
        except ValueError:
            tt = TransitionType.PHRASE_CUT

        compat = None
        if d.get("compatibility_score"):
            compat = CompatibilityScore(**d["compatibility_score"])

        quality = None
        if d.get("quality_score"):
            quality = TransitionQualityScore(**d["quality_score"])

        recipe = None
        if d.get("recipe"):
            recipe = TransitionRecipe(**d["recipe"])

        return cls(
            source_track_id=d.get("source_track_id", ""),
            target_track_id=d.get("target_track_id", ""),
            transition_type=tt,
            source_exit_time=d.get("source_exit_time", 0.0),
            target_entry_time=d.get("target_entry_time", 0.0),
            overlap_duration=d.get("overlap_duration", 0.0),
            length_bars=d.get("length_bars", 8),
            target_bpm=d.get("target_bpm", 0.0),
            requires_stretch=d.get("requires_stretch", False),
            stretch_amount_pct=d.get("stretch_amount_pct", 0.0),
            compatibility_score=compat,
            confidence=d.get("confidence", 0.0),
            reasoning=d.get("reasoning", ""),
            quality_score=quality,
            recipe=recipe,
            context=d.get("context", {}),
        )


@dataclass
class SetPlan:
    """A complete set plan - ordered tracks with transitions."""
    tracks: list[TrackProfile] = field(default_factory=list)
    transitions: list[TransitionPlan] = field(default_factory=list)
    total_duration_sec: float = 0.0
    target_duration_sec: float = 0.0
    energy_profile: EnergyProfile = EnergyProfile.STEADY

    # Summary
    avg_transition_confidence: float = 0.0
    score: float = 0.0
    final_track_end_time: Optional[float] = None

    # V5: Intent and explanations
    intent_used: Optional[SetIntent] = None
    human_readable_reasons: list[str] = field(default_factory=list)

    # V8.1: relevance-first planning diagnostics.  These fields are
    # additive and optional so plans written by earlier versions remain
    # readable.
    intent_coverage: dict = field(default_factory=dict)
    intent_track_scores: dict[str, dict] = field(default_factory=dict)
    intent_candidate_pool_ids: list[str] = field(default_factory=list)
    intent_excluded_track_ids: list[str] = field(default_factory=list)
    intent_relaxation_steps: list[str] = field(default_factory=list)

    def get_track_by_id(self, track_id: str) -> Optional[TrackProfile]:
        for t in self.tracks:
            if t.id == track_id:
                return t
        return None

    def summary(self) -> str:
        lines = [f"Set Plan ({len(self.tracks)} tracks, {self.total_duration_sec:.0f}s)"]
        if self.human_readable_reasons:
            lines.append("Reasons:")
            for reason in self.human_readable_reasons:
                lines.append(f"  - {reason}")
        for i, track in enumerate(self.tracks):
            trans = ""
            if i < len(self.transitions):
                t = self.transitions[i]
                trans = f" -> [{t.transition_type.value}]"
            lines.append(
                f"  {i+1}. {track.title} "
                f"({track.bpm:.0f} BPM, {track.camelot}, "
                f"energy={track.mean_energy:.2f}){trans}"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        return {
            "tracks": [self._track_to_dict(t) for t in self.tracks],
            "transitions": [t.to_dict() for t in self.transitions],
            "total_duration_sec": self.total_duration_sec,
            "target_duration_sec": self.target_duration_sec,
            "energy_profile": self.energy_profile.value,
            "avg_transition_confidence": self.avg_transition_confidence,
            "score": self.score,
            "final_track_end_time": self.final_track_end_time,
            "human_readable_reasons": self.human_readable_reasons,
            "intent_coverage": self.intent_coverage,
            "intent_track_scores": self.intent_track_scores,
            "intent_candidate_pool_ids": self.intent_candidate_pool_ids,
            "intent_excluded_track_ids": self.intent_excluded_track_ids,
            "intent_relaxation_steps": self.intent_relaxation_steps,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SetPlan":
        """Deserialize from dict."""
        tracks = [cls._track_from_dict(t) for t in d.get("tracks", [])]
        transitions = [TransitionPlan.from_dict(t) for t in d.get("transitions", [])]

        ep_str = d.get("energy_profile", "steady")
        try:
            ep = EnergyProfile(ep_str)
        except ValueError:
            ep = EnergyProfile.STEADY

        return cls(
            tracks=tracks,
            transitions=transitions,
            total_duration_sec=d.get("total_duration_sec", 0.0),
            target_duration_sec=d.get("target_duration_sec", 0.0),
            energy_profile=ep,
            avg_transition_confidence=d.get("avg_transition_confidence", 0.0),
            score=d.get("score", 0.0),
            final_track_end_time=d.get("final_track_end_time"),
            human_readable_reasons=d.get("human_readable_reasons", []),
            intent_coverage=d.get("intent_coverage", {}),
            intent_track_scores=d.get("intent_track_scores", {}),
            intent_candidate_pool_ids=d.get("intent_candidate_pool_ids", []),
            intent_excluded_track_ids=d.get("intent_excluded_track_ids", []),
            intent_relaxation_steps=d.get("intent_relaxation_steps", []),
        )

    @staticmethod
    def _track_to_dict(track: TrackProfile) -> dict:
        return {
            "id": track.id,
            "metadata": track.metadata.__dict__,
            "analysis": track.analysis.to_dict(),
            "semantic": track.semantic.to_dict() if track.semantic else None,
            "lyrics": track.lyrics.to_dict() if track.lyrics else None,
        }

    @staticmethod
    def _track_from_dict(d: dict) -> TrackProfile:
        metadata = TrackMetadata(**d.get("metadata", {}))
        analysis = TrackAnalysis.from_dict(d.get("analysis", {}))
        semantic_data = d.get("semantic")
        lyrics_data = d.get("lyrics")
        return TrackProfile(
            id=d.get("id", ""),
            metadata=metadata,
            analysis=analysis,
            semantic=SemanticProfile.from_dict(semantic_data) if semantic_data else None,
            lyrics=LyricsProfile.from_dict(lyrics_data) if lyrics_data else None,
        )
