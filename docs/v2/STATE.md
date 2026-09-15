# DJenius V2 State

## CURRENT PHASE
All roadmap phases (0-10) remain frozen. **There is no new roadmap phase.**
The user passed manual reference quality, same-pair automated reproduction,
new-pair generalization, and the two targeted source-entry fixes. The active
gate is blind human listening of a constrained autonomous selector over only
the four proven templates plus abstention. Candidate Composer, Audition Lab,
Set Director, UI, personalization, new families, and full mixes remain out of
scope.

## REFERENCE-BACKED AUTONOMOUS SELECTION (HUMAN GATE PENDING)

- `select_reference_transition` evaluates all four approved archetypes,
  searches bounded nearby source/target downbeat windows, and returns one
  template instance or `NO_SUITABLE_TEMPLATE`.
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
`3b1d882` - "Refine reference template entry eligibility". It contains
contextual cue refinement, inspectable eligibility/rejection evidence, two
controlled private renders, focused regression coverage, and durable
public-safe human labels. It was pushed to
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
The only immediate blocker is blind human listening of the four rendered
autonomous choices and review of the four abstentions. Technical checks cannot
establish musical appropriateness.

## EXACT NEXT ACTION
Stop for the user to blind-listen to `PAIR_02.wav` through `PAIR_05.wav` and
judge whether PAIR_01/06/07/08 correctly abstained. Record labels against the
manifest evidence. Do not tune, add pairs, broaden selection, or resume
Candidate Composer, Audition Lab, Set Director, UI, or full mixes.
