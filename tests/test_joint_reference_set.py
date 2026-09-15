from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from djenius.audio.joint_reference_set_renderer import (
    JointTrackRenderMaterial,
    render_joint_reference_set,
)
from djenius.audio.reference_template_renderer import RenderedReferenceTemplate
from djenius.core.joint_reference_set import (
    JointCandidateDecision,
    JointReferenceSetPlan,
    JointSetConfig,
    JointSetPlanningDeadEnd,
    JointTransitionDecision,
    SetFlowEvaluation,
    plan_joint_reference_set,
)
from djenius.core.models import TrackAnalysis, TrackMetadata, TrackProfile
from djenius.core.musical_role import SetRole, initial_set_flow_state
from djenius.core.reference_templates import ReferenceArchetype, TemplateAnchors


def _profile(track_id: str, *, energy: float = 0.72) -> TrackProfile:
    grid = [2.0 * index for index in range(61)]
    analysis = TrackAnalysis(
        bpm=120,
        bpm_confidence=0.98,
        analysis_confidence=0.96,
        mean_energy=energy,
        camelot="8A",
        downbeat_times=grid,
        bar_times=grid,
        section_profiles=[{"start_sec": 0.0, "end_sec": 120.0, "label": "intro"}],
        vocal_regions=[],
    )
    return TrackProfile(
        id=track_id,
        metadata=TrackMetadata(
            filepath=f"/{track_id}.wav", title=track_id, duration_sec=120
        ),
        analysis=analysis,
    )


def _anchors(
    source_start: float = 40.0, target_landing: float = 10.0
) -> TemplateAnchors:
    return TemplateAnchors(
        source_start_sec=source_start,
        source_end_sec=source_start + 16,
        target_runway_start_sec=2.0,
        target_landing_sec=target_landing,
        target_post_end_sec=target_landing + 20,
        source_start_bar_index=int(source_start / 2),
        source_end_bar_index=int((source_start + 16) / 2),
        target_runway_bar_index=1,
        target_landing_bar_index=int(target_landing / 2),
        target_post_end_bar_index=int((target_landing + 20) / 2),
        source_section="outro",
        target_runway_section="intro",
        target_landing_section="drop",
    )


@dataclass(frozen=True)
class _Selection:
    source_track_id: str
    target_track_id: str
    selected_archetype: ReferenceArchetype | None
    selected_instance: object | None
    pair_transitionable: bool
    selector_id: str
    evaluations: tuple = ()
    pair_rejection_reasons: tuple[str, ...] = ()

    def to_dict(self, **_kwargs):
        return {
            "source_track_id": self.source_track_id,
            "target_track_id": self.target_track_id,
            "selected_template": self.selected_archetype.value
            if self.selected_archetype
            else None,
            "pair_transitionable": self.pair_transitionable,
        }


def _candidate(
    source,
    target,
    archetype=None,
    *,
    retained=False,
    prior_landing=None,
    set_flow_state=None,
    target_phase=SetRole.HOLD,
):
    instance = SimpleNamespace(anchors=_anchors()) if archetype is not None else None
    selection = _Selection(
        source.id,
        target.id,
        archetype,
        instance,
        archetype is not None,
        f"{source.id}-{target.id}-{archetype}",
        pair_rejection_reasons=() if archetype else ("no usable template",),
    )
    state = set_flow_state or initial_set_flow_state(source)
    state_after = {
        **state.to_dict(),
        "phase": target_phase.value,
        "recent_track_ids": [*state.recent_track_ids[-2:], target.id],
        "recent_energy": [*state.recent_energy[-2:], target.mean_energy],
    }
    flow = SetFlowEvaluation(
        True,
        {"test_gate": True},
        {
            "energy_change": round(target.mean_energy - source.mean_energy, 4),
            "tempo_delta_pct": 0.0,
            "harmonic_compatibility": 1.0,
            "musical_role_and_set_story": {
                "relationship": "COHERENT_CONTINUATION",
                "state_after": state_after,
            },
        },
        (),
        (),
    )
    return JointCandidateDecision(
        source.id,
        target.id,
        flow,
        selection,
        {
            "prior_target_landing_sec": prior_landing,
            "outgoing_source_launch_sec": 40.0 if instance else None,
            "available_establishment_sec": None if prior_landing is None else 30.0,
            "required_minimum_sec": 30.0,
            "passes": True,
        },
        retained,
        () if retained else ("pair_not_transitionable",),
    )


def _patch_graph(monkeypatch, graph):
    def evaluate(
        source,
        target,
        *,
        prior_target_landing_sec,
        set_flow_state,
        target_phase,
        **_kwargs,
    ):
        archetype = graph.get((source.id, target.id))
        return _candidate(
            source,
            target,
            archetype,
            retained=archetype is not None,
            prior_landing=prior_target_landing_sec,
            set_flow_state=set_flow_state,
            target_phase=target_phase,
        )

    monkeypatch.setattr(
        "djenius.core.joint_reference_set._evaluate_candidate", evaluate
    )


def test_joint_choice_rejects_attractive_but_untransitionable_track(monkeypatch):
    tracks = [
        _profile("A"),
        _profile("B", energy=0.73),
        _profile("C", energy=0.74),
        _profile("D", energy=0.75),
        _profile("X", energy=0.7201),
    ]
    graph = {
        ("A", "B"): ReferenceArchetype.RESET_RELEASE,
        ("B", "C"): ReferenceArchetype.STEM_ECHO_HANDOFF,
        ("C", "D"): ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
    }
    _patch_graph(monkeypatch, graph)
    plan = plan_joint_reference_set(tracks, config=JointSetConfig(candidate_limit=5))
    assert [item.id for item in plan.tracks] == ["A", "B", "C", "D"]
    first_table = {
        item.candidate_track_id: item for item in plan.transitions[0].candidate_table
    }
    assert first_table["X"].retained is False
    assert first_table["X"].transition_selection.pair_transitionable is False


def test_joint_planning_is_deterministic_and_preserves_template_contracts(monkeypatch):
    tracks = [_profile(letter) for letter in "ABCD"]
    graph = {
        ("A", "B"): ReferenceArchetype.RESET_RELEASE,
        ("B", "C"): ReferenceArchetype.STEM_ECHO_HANDOFF,
        ("C", "D"): ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
    }
    _patch_graph(monkeypatch, graph)
    first = plan_joint_reference_set(tracks)
    second = plan_joint_reference_set(reversed(tracks))
    assert first.plan_id == second.plan_id
    assert first.to_dict() == second.to_dict()
    assert [item.selection.selected_archetype for item in first.transitions] == list(
        graph.values()
    )


def test_joint_planner_never_forces_a_transition(monkeypatch):
    tracks = [_profile(letter) for letter in "ABCD"]
    _patch_graph(monkeypatch, {})
    with pytest.raises(JointSetPlanningDeadEnd) as raised:
        plan_joint_reference_set(tracks)
    assert raised.value.diagnostics["dead_ends"]
    assert all(
        not row["retained"]
        for dead_end in raised.value.diagnostics["dead_ends"]
        for row in dead_end["candidate_table"]
    )


def test_establishment_floor_rejects_an_early_outgoing_cue(monkeypatch):
    import djenius.core.joint_reference_set as joint

    source, target = _profile("A"), _profile("B")
    instance = SimpleNamespace(anchors=_anchors(source_start=35.0))
    selection = _Selection(
        source.id,
        target.id,
        ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
        instance,
        True,
        "early-cue",
    )
    monkeypatch.setattr(
        joint, "select_reference_transition", lambda *_args, **_kwargs: selection
    )
    candidate = joint._evaluate_candidate(
        source,
        target,
        used_track_ids={source.id},
        prior_target_landing_sec=10.0,
        set_flow_state=initial_set_flow_state(source),
        target_phase=SetRole.HOLD,
        config=JointSetConfig(min_establishment_sec=30),
    )
    assert candidate.establishment["available_establishment_sec"] == 25.0
    assert candidate.retained is False
    assert (
        "insufficient_target_establishment_before_next_source_move"
        in candidate.rejection_reasons
    )


def test_transitionable_but_set_inappropriate_candidate_is_rejected(monkeypatch):
    import djenius.core.joint_reference_set as joint

    source, target = _profile("A"), _profile("B", energy=0.76)
    source.analysis.groove_profile = {
        "percussion_density_mean": 0.68,
        "onset_density_hz": 4.0,
        "syncopation_index": 0.3,
        "onbeat_fraction": 0.6,
        "swing_ratio": 1.0,
    }
    target.analysis.bpm = 86.0
    target.analysis.tempo_hypotheses = [{"relation": "double", "confidence": 0.7}]
    target.analysis.groove_profile = {
        "percussion_density_mean": 0.68,
        "onset_density_hz": 4.0,
        "syncopation_index": 0.3,
        "onbeat_fraction": 0.4,
        "swing_ratio": 1.0,
    }
    selection = _Selection(
        source.id,
        target.id,
        ReferenceArchetype.STEM_ECHO_HANDOFF,
        SimpleNamespace(anchors=_anchors()),
        True,
        "technically-transitionable",
    )
    monkeypatch.setattr(
        joint, "select_reference_transition", lambda *_args, **_kwargs: selection
    )
    candidate = joint._evaluate_candidate(
        source,
        target,
        used_track_ids={source.id},
        prior_target_landing_sec=None,
        set_flow_state=initial_set_flow_state(source),
        target_phase=SetRole.HOLD,
        config=JointSetConfig(),
    )
    assert candidate.transition_selection.pair_transitionable is True
    assert candidate.set_flow.passes_hard_gates is False
    assert candidate.retained is False
    assert (
        "incompatible rhythmic role lacks a supported bridge"
        in candidate.rejection_reasons
    )


def test_continuous_renderer_preserves_tail_and_context_excerpts(monkeypatch):
    sample_rate = 1000
    tracks = tuple(_profile(letter) for letter in "ABCD")
    transitions = []
    for index, (source, target, archetype) in enumerate(
        zip(
            tracks[:-1],
            tracks[1:],
            (
                ReferenceArchetype.RESET_RELEASE,
                ReferenceArchetype.STEM_ECHO_HANDOFF,
                ReferenceArchetype.LOOP_BUILD_COHERENT_HANDOFF,
            ),
        ),
        1,
    ):
        instance = SimpleNamespace(anchors=_anchors(), archetype=archetype)
        selection = _Selection(
            source.id, target.id, archetype, instance, True, f"s{index}"
        )
        transitions.append(
            JointTransitionDecision(
                index, source.id, target.id, selection, (), ("test",)
            )
        )
    plan = JointReferenceSetPlan(
        tracks,
        tuple(transitions),
        {"selected_track_id": "A"},
        JointSetConfig(opening_establishment_sec=10, closing_establishment_sec=10),
        "test-plan",
    )
    axis = np.arange(120 * sample_rate, dtype=np.float32) / sample_rate
    materials = {
        track.id: JointTrackRenderMaterial(
            np.column_stack(
                (
                    0.08 * np.sin(2 * np.pi * (2 + i) * axis),
                    0.08 * np.sin(2 * np.pi * (2 + i) * axis),
                )
            ),
            {},
            track.analysis,
            sample_rate,
        )
        for i, track in enumerate(tracks)
    }

    def fake_render(instance, inputs, **_kwargs):
        audio = np.column_stack(
            (
                0.1 * np.sin(2 * np.pi * 3 * np.arange(20 * sample_rate) / sample_rate),
                0.1 * np.sin(2 * np.pi * 3 * np.arange(20 * sample_rate) / sample_rate),
            )
        ).astype(np.float32)
        return RenderedReferenceTemplate(
            audio,
            sample_rate,
            10 * sample_rate,
            {"fx_tail": {"fx_tail_end_sec_relative_landing": 0.5}},
        )

    monkeypatch.setattr(
        "djenius.audio.joint_reference_set_renderer.render_reference_template",
        fake_render,
    )
    rendered = render_joint_reference_set(plan, materials, time_fit_backend="scipy")
    assert rendered.audio.ndim == 2 and rendered.audio.shape[1] == 2
    assert np.isfinite(rendered.audio).all()
    assert len(rendered.transition_landings) == 3
    assert rendered.transition_landings == tuple(sorted(rendered.transition_landings))
    assert all(len(rendered.transition_excerpt(i)) > 0 for i in range(3))
    assert all(
        join.get("incoming_template_tail_preserved_before_join", True)
        for join in rendered.provenance["joins"]
    )
    assert rendered.provenance["continuous_render"] is True
    assert rendered.provenance["legacy_set_renderer_used"] is False
    assert len(rendered.provenance["seam_diagnostics"]) == 6
