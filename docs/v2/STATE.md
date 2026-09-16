# DJenius V2 State

## CURRENT PHASE
All roadmap phases (0-10) remain frozen. **There is no new roadmap phase.**
The user passed manual reference quality, same-pair automated reproduction,
new-pair generalization, and the two targeted source-entry fixes. The first
blind autonomous selector gate failed; its postmortem produced a calibrated,
conservative `PAIR_TRANSITIONABLE`/`USABLE_FOR_PERFORMANCE` selector. One
isolated joint-planning pilot then failed on set story. The second flow-aware
pilot passed its first transition but exposed two musical-context failures.
The explicit bridgeability gate passed human listening. Pilot 3 then correctly
hit a bounded-pool planning dead end: only a two-track/one-transition path
cleared every performance, context, cue, and prior-human-evidence gate. That
longest valid fallback is now awaiting human listening, but the requested
five-track continuous-set milestone was not achieved. The legacy Set
Director, Candidate Composer, Audition Lab, UI, personalization, generic
families, and unrestricted/full-set automation remain disconnected.

## JOINT SET PILOT 3 (PARTIAL FALLBACK; HUMAN LISTENING PENDING)

- The planner now makes context-aware archetype choice across all mechanically
  usable frozen F/C3/B8/D2 options. A technically first-ranked archetype cannot
  hide another frozen option that is the one satisfying cue-local context.
- Exact completion and longest-valid partial completion are distinct results.
  Partial fallback is opt-in, ranks path length before other disclosed
  evidence, and records `hard_gates_weakened = false` plus the terminal
  candidate table.
- All explicit human-negative ordered pairs and the exact Pilot 2 transition-1
  calibration pair were excluded. Across four plausible five-role stories,
  the bounded fourteen-track pool supplied only two-track paths.
- The rendered fallback is one natural-continuation F handoff, 122.783673 s,
  stereo 44.1 kHz PCM24, sample peak `.682467`, clipping fraction `0`. Only
  `TRANSITION_01.wav` exists because later transitions were rejected.
- Private artifacts are under
  `/tmp/djenius_reference_dj_transition/joint_set_pilot_3/`. Focused tests:
  **61 passed**. Complete regression: **1164 passed in 87.93s**.
- This checkpoint validates conservative replanning/abstention and continuous
  partial rendering. It does not pass the five-track Pilot 3 product gate.

## MUSICAL CONTEXT / BRIDGEABILITY GATE (HUMAN PASSED)

- Existing cached analysis was sufficient only after using cue-local evidence:
  whole-track embedding alone could not separate the Pilot 2 failures. The
  planner now compares the nearest cached representative-window style and
  intensity distributions, plus whole-track embedding, rhythm, spectral,
  harmony, tempo, role, and set intent. No model/dependency was added.
- The evidence remains epistemically bounded: distances mean relative musical
  territory, never asserted mood/genre/lyrical facts. Quantile bands come from
  the unlabelled candidate pool, not human pass/fail labels.
- Adjacencies are explicitly `NATURAL_CONTINUATION`,
  `INTENTIONAL_BRIDGEABLE_CONTRAST`, or `UNJUSTIFIED_DISCONTINUITY`.
  Intentional contrast requires frozen F, phase/budget support, cue evidence,
  at least two named continuity anchors, and no unresolved local
  style/intensity split. Other frozen archetypes do not authorize a large
  contextual jump.
- Pilot 2 transition 1 remains a frozen natural-continuation PASS. Transitions
  2 and 3 are now rejected as unjustified discontinuities. The prior
  `GEN_F_02_FIX` PASS is retained as local-performance evidence; it is the same
  pair/cues as transition 2 and is therefore not a set-context positive.
- A selector defect was fixed without changing choreography: every technically
  eligible cue now receives `USABLE_FOR_PERFORMANCE` evaluation before cue
  ranking, preventing a weak first cue from hiding a valid nearby cue.
- Private output contains exactly two WAVs and one abstention under
  `/tmp/djenius_reference_dj_transition/musical_context_bridgeability/`.
  `CONTEXT_NATURAL.wav` and `CONTEXT_BRIDGE.wav` are finite/unclipped;
  `CONTEXT_REJECT` has no WAV. Full diagnosis is private in
  `MUSICAL_CONTEXT_DIAGNOSIS.json`.
- Focused regression: **82 passed**. Complete regression: **1159 passed in
  84.26s**. Human listening is the quality gate; Pilot 3 is prohibited.

## FLOW-AWARE JOINT SET PILOT 2 (POSTMORTEM INPUT)

- The first pilot's three old choices now all fail an independent hard gate:
  D2 performance launch/groove margin; HOLD rhythmic-role continuity; and PEAK
  target-role/energy direction, respectively.
- `musical_role.py` uses existing acoustic, groove, section, optional semantic,
  and optional lyric evidence. Semantic mood/style below `.55` reliability is
  explicitly unknown. The human-described affect mismatch remains human
  evidence; no unsupported classifier claim is substituted for it.
- `PERFORMANCE_FEASIBILITY` and `SET_FLOW_SUITABILITY` are independent. The
  planner carries a short OPEN/BUILD/HOLD/PEAK/RELEASE/COOLDOWN state, recent
  energy/dance/rhythm/reliable-mood context, and an intentional-contrast budget.
- The one second pilot follows `OPEN -> HOLD -> PEAK -> RELEASE`, anonymous
  energy `.750 -> .747 -> .770 -> .702`, and frozen D2/F/F choreography. It is
  264.977052 seconds, peak `.95`, with no clipped samples.
- Private artifacts and the complete old-vs-new postmortem are under
  `/tmp/djenius_reference_dj_transition/joint_set_pilot_2/`.
- Focused gate: **66 passed**. Full regression: **1154 passed in 88.07s** with
  two existing dependency warnings. Human listening remains the only quality
  gate; no third pilot is authorized.
- Validated implementation checkpoint: `1313c7f` (`Add flow-aware joint set
  planning`), pushed with its docs-only handoff finalization immediately after.

## CONSTRAINED JOINT SET-DIRECTOR PILOT (HUMAN GATE PENDING)

- `joint_reference_set.py` makes track, frozen archetype, source cue, and target
  cue one decision. Set-flow and performance evidence stay explicit; a pair
  failing the transition floor cannot enter a path.
- Opening choice is deterministic and requires a complete hard-gated path.
  Bounded path search records each candidate table and uses diversity only
  after transition and set-flow evidence.
- `joint_reference_set_renderer.py` renders frozen reference choreography
  intact, preserves target/tail state through the full template window, and
  continues each middle track by sample-aligned natural playback before its
  outgoing move. The three review excerpts come from the continuous set.
- The anonymous four-track path uses D2, F, F across three previously unused
  ordered edges. All prior listening-test ordered pairs were excluded.
- Private output: 391.595283 s stereo 44.1 kHz PCM24, sample peak `.935026`,
  zero clipping. Focused tests: **45 passed**; full regression: **1147 passed
  in 83.79s** with two existing dependency warnings.
- These are technical gates only. Human listening decides whether the order
  and all three transitions pass; no second pilot is authorized.

## REFERENCE-BACKED AUTONOMOUS SELECTION POSTMORTEM

- Human labels are `PAIR_02 = FAIL_NOT_GOOD`,
  `PAIR_03 = FAIL_BETTER_THAN_02`, `PAIR_04 = NEAR_PASS_BUT_NOT_GOOD`, and
  `PAIR_05 = BEST_OF_ROUND_BUT_NOT_PASS`. None is a pass.
- Blind calibration at the pre-postmortem selector checkpoint recovered the
  correct template for three accepted cases but missed two accepted source
  cues and abstained on accepted F_02_FIX because the proven intro pickup was
  excluded. The revised selector recovers all four templates and exact
  accepted bar anchors.
- `select_reference_transition` now separates technical `eligible` from
  explicit archetype-specific `USABLE_FOR_PERFORMANCE`, and exposes separate
  `PAIR_TRANSITIONABLE` state and reasons. No aggregate winner score is used.
- Re-evaluation of every frozen archetype at its best nearby cues finds no
  credible alternative for PAIR_02-05. All four are now
  `SHOULD_HAVE_ABSTAINED`; zero counterfactual WAVs were fabricated.
- PAIR_01/06/07/08 remain abstentions under the stronger floor, so their
  conservative behavior was appropriate relative to the four false positives.
- Human labels and anonymous hashes are durable in
  `REFERENCE_SELECTOR_LABELS.json`; the detailed private report is under
  `/tmp/djenius_reference_dj_transition/autonomous_selection/postmortem/`.
- Renderer and frozen template choreography are unchanged. This is selection
  and cue-discovery work only.
- Focused selector/template tests: **40 passed**; focused structural regression:
  **136 passed**; complete repository regression: **1142 passed in 84.58s**
  with the two existing dependency warnings.

## FIRST AUTONOMOUS SELECTION GATE (FAILED; HISTORICAL INPUT)
- Each evaluation exposes source phrase/vocal/gap/motif/energy/transient
  context, target cue/phrase/vocal/drum/bass/density/establishment context,
  pair tempo/groove/harmony/energy/stem/overlap context, and a named
  template-specific musical-story contract. No aggregate winner score is
  used or exposed.
- The selector is isolated from Candidate Composer, Audition Lab, and Set
  Director. The legacy generalization `fit_score` is deliberately ignored.
- Exactly eight unseen ordered pairs were fixed by an analysis-only stratified
  sampling policy before render. Decisions: F for PAIR_02, B8 for PAIR_03/04,
  C3 for PAIR_05, and abstain for PAIR_01/06/07/08. No D2 was forced.
- Four WAVs and the complete private manifest are under
  `/tmp/djenius_reference_dj_transition/autonomous_selection/`. The WAVs are
  finite, unclipped stereo 44.1 kHz PCM24 and byte-identical on rerender.
- The twelve accepted manual/AUTO/generalization references are frozen by
  hash in `REFERENCE_GENERALIZATION_LABELS.json` and were verified unchanged
  before and after rendering.
- Focused tests: **34 passed**. Complete regression: **1136 passed in 81.99s**
  with two existing dependency warnings.
- Human listening decides whether the chosen behaviors, cue placements, and
  abstentions were appropriate.

## GENERALIZATION ROUND 2 CHECKPOINT (PASSED)

- The four manual and four automated references are immutable and reverified
  by SHA-256. Their choreography and hashes are recorded in
  `REFERENCE_BACKED_ARCHETYPES.md`.
- Human labels are durable in `REFERENCE_GENERALIZATION_LABELS.json`; they are
  engineering evidence, not machine-learning targets.
- Source-entry evidence now exposes vocal activity, coverage, phrase-boundary
  distance, instrumental runway, section stability, transient/density context,
  and motif repeatability. Cue refinement is deterministic and lexicographic,
  with its evidence exposed rather than collapsed into an opaque score.
- F requires a self-contained final-bar capture close to a vocal boundary and
  searches other four-bar downbeat windows before returning `NOT SUITABLE`.
  B8 prefers instrumental space or a phrase-end release into a vocal gap;
  active-vocal entry is allowed only for stable, predictably repeating motif
  context while preserving source phrase duration.
- C3 marks the observed combination of >8% stretch, groove distance >0.18,
  and source density >0.80 as borderline. D2 now hard-rejects global harmonic
  compatibility <0.50 or shared arrangement-density pressure >1.65.
- Exactly `GEN_B8_02_FIX.wav` and `GEN_F_02_FIX.wav` were rendered. No C3 or
  D2 replacement was made. Target-side B8 content is sample-identical to the
  prior B8_02 contribution; F target timing/choreography is unchanged.
- Focused reference-template tests pass (**24 passed**). Complete regression
  passes (**1126 passed in 82.45s**, 2 pre-existing dependency warnings).
- Human listening passed both fixes: their source placement restored coherent,
  clearly audible DJ behavior without changing the proven target handoffs.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## LATEST REFERENCE-AUTOMATION COMMIT
`cce15d2` - "Tighten reference selector abstention gate". It contains the
selector calibration corrections, explicit `USABLE_FOR_PERFORMANCE` and
`PAIR_TRANSITIONABLE` contracts, stricter conservative abstention, focused
regression coverage, and durable human labels. It was pushed to
`origin/v2-professional-autonomous-dj`; a docs-only handoff finalization follows,
so resolve the current tip from Git.

## PHASE COMPLETION HISTORY (unchanged, factual record)
- Phases 0-9: frozen. Phase 9 pushed at `4f71818e2f2613d14db184c23901f43474ce04fd`
  (handoff-doc-only follow-up at `191dd40`).
- Phase 10: autonomous portion complete, pushed at
  `844d4162c164d244edf8aca2c28ffa501bd388c3` ("Add V2 full mix rendering").
  Added `render_set_director_mix` (first capability to render a whole
  Set-Director plan into one continuous mix), the anchor-shift correction
  (D044), the render endpoint/UI button, and the difficult-pair transition
  benchmark. This work is real and correct as far as it goes -- it is what
  made the human listening comparison possible in the first place.
- Base V1 commit: `efcfcca6d21aeaa595b236306b025b70668106fd`. V1 remains
  unchanged throughout.

## POST-PHASE-10 INVESTIGATION (unplanned, mandated by the first failed listen)
Triggered by listening result #1 above. Found and fixed **four real,
independent, verified production defects**, all with regression coverage,
full 1095-test suite green, pushed at `89bfda5`:

1. `SetDirectorConfig.max_candidates_audited_per_edge` was 4 while
   Candidate Composer generates up to 8 candidates ordered by content-hash
   id -- silently excluded whole technique families from ever being
   auditioned for some real handoffs. Fixed: raised to 8 + added
   `_family_diverse_order`.
2. The beam search could select an edge where every candidate hard-rejected
   on real audition (`survivor_count == 0`) -- unrenderable, crashes
   `render_set_director_mix`. Fixed: such edges are now excluded from beam
   expansion.
3. `_choose_anchor`'s position preference was a tuple tie-breaker that
   real, continuously-varying scores essentially never tie on, so it never
   actually influenced anchor choice -- anchors landed deep inside tracks
   regardless of position. Fixed: folded into the primary score as a
   bounded (0.35) weighted term.
4. `_estimate_overlap_sec` assumed every track contributes close to its
   full length; real anchors land far from track boundaries, overstating a
   real plan's duration by ~236s. Fixed: duration bookkeeping now uses each
   edge's real selected-candidate anchors.

Measured effect of the fix: V2's rendered duration on the same 12-track
comparison went from **427.8s to 589.2s** against a 600s target (4 tracks
to 5), with 100% of generated candidates now actually audited (was
partial). Full detail, including the controlled (same-track-order)
comparison and per-handoff review package, is in `ACTIVE_HANDOFF.md`.

**This fix was proven correct and did improve measurable quality -- but
listen #2 shows it was not sufficient to produce a convincing DJ
performance.** Two deeper findings, confirmed but deliberately not fixed
(see `ACTIVE_HANDOFF.md` for full detail), are the leading suspects for why:

- **Cross-edge anchor consistency**: a track's entry (as target of one
  handoff) and its own exit (as source of the next) are chosen
  independently, with no shared notion of "this track's one coherent
  appearance in the set." The renderer's anchor-shift correction (D044)
  papers over the resulting conflicts rather than the plan avoiding them.
- **Technique labels vs. actual DSP**: at least two of V2's technique
  families (`riser_impact`, `loop_shortening`) compile down to plain
  `crossfade` DSP with a layered sample/loop-stutter on top, not a
  structurally different mix. Different labels with near-identical
  underlying DSP is directly consistent with the user's "occasionally
  noticeable but not transformative" verdict.

## TEST RESULTS
- Complete repository regression: **1102 passed** (was 1095 at the prior
  investigation checkpoint), reverified after the performance-recovery fixes.
- All phase-specific suites (Phase 5 candidate composer: 41, Phase 7 set
  director: 18, Phase 10 certification: 6, etc.) pass.
- Passing tests are **not** evidence the DJ-likeness gate is met -- see
  `ACTIVE_HANDOFF.md`'s explicit warning against treating "technically
  clean" as "sounds like a DJ."

## KNOWN LIMITATIONS / TECHNICAL DEBT
- **The core product gate is not met, on two separate real listens.** This
  supersedes the older "Phase 10 gate not met" framing below -- it is now
  the single most important open item in the whole project.
- Cross-edge appearance consistency is now implemented upstream and tested;
  the renderer's old shift remains only as a legacy/manual-plan guard.
- Phase-5 `riser_impact` and `loop_shortening` now compile and execute a
  source-held build/target-landing choreography rather than plain crossfade.
- No creativity-budget system exists (research spec section 35) --
  confirmed absent, not yet proven to matter on short comparisons.
- For vocal-heavy real pairs, Candidate Composer can generate zero
  surviving candidates (confirmed Phase 10 benchmark finding, still true);
  no minimal-risk guaranteed-feasible fallback family exists.
- The anchor-shift fix (D044) remains a pragmatic, transparent correction,
  not a redesign of Phase 5's per-edge anchor independence (same item as
  cross-edge anchor consistency above, from the renderer's side).
- All earlier Phase 7/8/9 known limitations not superseded above still
  apply unchanged (forced zero-survivor handoffs -- now excluded by the
  investigation's fix 2 above --, weak discriminators in some
  constructions, inspection-level-only locks, no waveform/timeline
  visualization).

## CURRENT BLOCKERS
The postmortem is complete. No counterfactual cleared the explicit performance
floor, so there is no new audio listening artifact. Broader autonomy remains
blocked on product direction for joint next-track/template/cue selection and a
future human gate; technical tests cannot substitute for that decision.

## EXACT NEXT ACTION
Stop for user review of the Case-2 diagnosis. Do not render unqualified
alternatives, launch a second blind-selection round, tune frozen templates, or
resume Candidate Composer, Audition Lab, Set Director, UI, or full mixes.
