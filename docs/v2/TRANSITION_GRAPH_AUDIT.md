# Transition graph connectivity audit

2026-09-16. Planning-only audit of the bounded fourteen-track private library. Full
per-edge evidence, including private track descriptors, cues, all four archetype
decisions, cue-local context, set-flow phases, and rejection reasons, is in
`/tmp/djenius_reference_dj_transition/transition_graph_audit/`. No WAV was rendered;
no production gate, template, choreography, or renderer was changed.

## Result

**Conclusion E — a combination, not a single novelty-exclusion failure.** Pilot 3's
exclusions removed two currently usable edges relative to a realistic history
policy. But even ignoring *all* history, the graph has only nine static usable
edges and no simple four- or five-track path. The current performance gates also
reject approved reference performances at their approved cues. This is direct
evidence of over-conservatism for at least those cases, alongside a small,
disconnected test pool under the current rules. The audit does **not** establish
a recurring missing-archetype capability: unlistened rejected pairs cannot be
declared DJable, and the approved false negatives already use existing F/B8/C3.

The production selector found 23/182 mechanically transitionable directed pairs.
Nine of those survive a cue-local context and set-flow check in at least one
declared phase. This static union is optimistic: it tests each edge from its
source's initial state under HOLD, BUILD, PEAK, and RELEASE; a real path must
also respect cumulative set state and establishment timing.

| Scenario | Usable edges | Density | Longest simple path | Four-/five-track paths |
| --- | ---: | ---: | ---: | ---: |
| A: exact Pilot 3 exclusions | 6 | 3.30% | 2 tracks | 0 / 0 |
| B: exclude pair-level human negatives only | 8 | 4.40% | 3 tracks | 0 / 0 |
| C: current musical rules, no history | 9 | 4.95% | 3 tracks | 0 / 0 |

The offline **production** joint planner under B tried all four Pilot 3 role
trajectories with the full fourteen-track candidate pool. Each stopped at three
tracks; none produced five. `REALISTIC_5_TRACK_PLAN.json` records the actual
partial plan, dead-end, and candidate traces. No audio was rendered.
Under B, seven tracks are isolated even in the weak (direction-ignoring)
graph, nine have no outgoing usable edge, and nine have no incoming usable
edge. The only nontrivial strongly connected component has two tracks.

Pilot 3's code did **not** blanket-exclude every previously tested pair. It
excluded thirteen ordered pairs: ten pair-level human negatives, one known-good
Pilot 2 calibration adjacency, one D2-only human rejection, and one F-cue-only
human rejection. The latter two were broader exclusions than their human labels
justify. Of the thirteen, three are static-usable under current musical rules:
the known-good calibration pair, the previously rejected F cue's pair at a newly
selected cue/phase, and a human-bad context pair that the current context rules
would admit in another phase. B restores the first two; C additionally admits
the human-bad pair. History is therefore useful for explicit pair-level human
negatives, but novelty alone should not be mistaken for musical invalidity.

## Rejection topology and coverage

Among the 173 edges rejected by current musical rules, 86 have no technically
eligible template/cue; 73 have a technical option but none passes
`USABLE_FOR_PERFORMANCE`; 14 have a performance-usable option but fail context
or set-flow in every declared phase. These are precedence-based primary causes.
The detailed JSON also counts co-occurring check failures; those counts overlap
and include checks from templates that were not selected, so they are diagnostic,
not independent acoustic verdicts. The most common explicit pair-level reasons
are no approved template/cue combination (86), no sufficiently intentional
source launch (68), and no strong target establishment window (35).

On the nine static usable edges, frozen archetype coverage is F: 7, C3: 0,
B8: 1, D2: 2. Eight edges have exactly one mechanically usable archetype;
one has two. C3 has one performance-usable edge elsewhere, but context/set-flow
rejects it in all declared phases. This is sparse and F-heavy, but it does not
prove that a fifth template would solve the musical-context problem.

## Human-evidence calibration

The audit replayed fifteen accepted/acceptable *instances* (manual and automated
copies are intentionally separate instances) and twelve rejected instances at
their recorded pair, template, and relevant set phase. All fifteen positive
instances remain technically eligible, but only nine pass the current
performance floor. None of the twelve negative instances reaches a final
context-and-flow-usable decision at its recorded phase; six already fail the
performance floor. Local
transition acceptance is **not** treated as proof that the same pair belongs
in a whole set: `GEN_F_02_FIX` was locally good, while the later Pilot 2
same-pair context verdict was negative.
Four additional near-pass/borderline labels are recorded separately; they are
not silently promoted to either a firm success or a firm rejection.

The clearest gate conflicts are cue-exact, not merely density statistics:

- Approved manual/AUTO F: the selector reproduces source and target cues to
  within 0.00004 s, yet fails motif-completion, natural-effect-boundary, and
  target-pickup performance checks.
- Approved manual/AUTO B8: the selector reproduces the cues to within
  0.00004 s, yet fails `pair_groove_has_performance_margin`.
- Approved manual/AUTO C3: the source cue is reproduced, but the current search
  moves the target landing 12.933517 s later and rejects the resulting
  performance on arrangement/groove/ownership checks. This is a cue-selection
  plus acceptance discrepancy, not proof that the approved C3 performance is
  invalid.
- Approved manual/AUTO D2 passes the local performance floor but fails this
  audit's HOLD set-context test. Since its human label was local performance,
  that result alone does not demonstrate context-gate over-conservatism.

The three human-accepted set-context controls—Pilot 2 transition 1,
`CONTEXT_NATURAL`, and `CONTEXT_BRIDGE`—remain accepted at their recorded
phases. Thus the cue-local context gate should not be blamed from graph
density alone. One prior human-bad context pair is static-usable under RELEASE,
so the explicit human-negative exclusion remains necessary.

## What the graph can and cannot say

The known approved F/B8/C3 performances are proven cases where a DJ *can*
connect the pair with the existing vocabulary; the present gate/search does
not preserve those cases. For the many unlabelled rejected pairs, neither
"a good DJ should avoid it" nor "a fifth archetype is missing" is established
without listening evidence. The pool is disconnected **under current rules**;
its absolute suitability and a recurring vocabulary gap remain undetermined.
No threshold was loosened, and no extra tracks or family were introduced to
make the graph appear connected.

The next decision should be evidence-led calibration of the identified
approved-reference false negatives before interpreting graph sparsity as a
new-technique requirement. This audit does not authorize Pilot 4 or a new
render.
