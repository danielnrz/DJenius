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
class TrackProfile:
    """Complete profile of a track - metadata + analysis combined."""
    id: str = ""               # unique identifier (file hash)
    metadata: TrackMetadata = field(default_factory=TrackMetadata)
    analysis: TrackAnalysis = field(default_factory=TrackAnalysis)

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

    # Weighted final score
    overall_score: float = 0.0

    # Explanation
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

    # V5: Intent and explanations
    intent_used: Optional[SetIntent] = None
    human_readable_reasons: list[str] = field(default_factory=list)

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
            "human_readable_reasons": self.human_readable_reasons,
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
            human_readable_reasons=d.get("human_readable_reasons", []),
        )

    @staticmethod
    def _track_to_dict(track: TrackProfile) -> dict:
        return {
            "id": track.id,
            "metadata": track.metadata.__dict__,
            "analysis": track.analysis.to_dict(),
        }

    @staticmethod
    def _track_from_dict(d: dict) -> TrackProfile:
        metadata = TrackMetadata(**d.get("metadata", {}))
        analysis = TrackAnalysis.from_dict(d.get("analysis", {}))
        return TrackProfile(
            id=d.get("id", ""),
            metadata=metadata,
            analysis=analysis,
        )
