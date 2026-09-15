# DJenius V2 State

## CURRENT PHASE
All roadmap phases (0-10) remain frozen. **There is no new roadmap phase.**
The user passed the manual-reference and automated same-pair reproduction
gates for F, C3, B8, and D2, then supplied labels for the first eight new-pair
renders. The active gate is now human listening of two targeted source-entry
fixes. Candidate Composer, Audition Lab selection, Set Director, UI,
personalization, new families, and full mixes remain out of scope.

## GENERALIZATION ROUND 2 CHECKPOINT (HUMAN GATE PENDING)

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
- Human listening of the two fixes, not eligibility or technical metrics,
  decides whether this gate passes.

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
The only immediate blocker is the eight-render cross-pair human listening
gate. Technical checks cannot establish that the fixed F/C3/B8/D2
choreographies make intentional musical sense on their selected new pairs.
Autonomous selection remains paused.

## EXACT NEXT ACTION
Stop for the user to listen to `GEN_F_01/02`, `GEN_C3_01/02`,
`GEN_B8_01/02`, and `GEN_D2_01/02`. Record success/failure against the
manifest's eligibility evidence. Do not tune, add pairs, broaden scoring, or
resume Candidate Composer, Audition Lab, Set Director, UI, or full mixes.
