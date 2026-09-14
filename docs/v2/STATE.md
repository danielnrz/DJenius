# DJenius V2 State

## CURRENT PHASE
All roadmap phases (0-10) remain frozen. **There is no new roadmap phase.**
The post-Phase-10 manual performance R&D gate has advanced: the user judged
F strongest, C3 successful, B8 acceptable after the B7/B8 structural fixes,
and D2 an acceptable restrained blend. Convincing DJ behavior is therefore
proven possible for these controlled performances. Do not keep polishing B8.

The active work is a narrower reference-reproduction gate: four explicit,
analysis-driven templates must reproduce those exact approved behaviors on
the same private pairs before any autonomous technique selection resumes.
Candidate Composer selection, Audition Lab policy, Set Director, UI, new
families, generalized pairs, and full mixes remain out of scope.

## REFERENCE-AUTOMATION CHECKPOINT (HUMAN GATE PENDING)

- Frozen manual SHA-256 and exact choreography are recorded in
  `REFERENCE_BACKED_ARCHETYPES.md`; the private render driver verifies the
  four hashes before and after every run.
- `core/reference_templates.py` provides four explicitly selected,
  deterministic templates. It derives anchors from analysis and emits a
  complete bar-relative `PerformanceRecipe` plus an auditable choreography
  contract. It performs no autonomous selection.
- `audio/reference_template_renderer.py` preserves B7/B8 permanently: target
  runway/body master and stems share one multichannel time map; a crossing
  source loop retains state; every tail has a checked endpoint.
- The same-pair outputs and machine-readable comparison manifest are in
  `/tmp/djenius_reference_dj_transition/automated/`. Every source/target cue
  matches the frozen manual choreography within 0.1 ms. The four manual WAV
  hashes remain unchanged.
- Focused reference-template tests pass (**14 passed**). The complete
  repository regression passes (**1116 passed**, 2 pre-existing dependency
  deprecation warnings).
- Human listening, not the deterministic or audio metrics, decides whether
  this reproduction gate passes.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## LATEST PERFORMANCE-RECOVERY COMMIT
`5571b573ae9c8e6e17333c9a387bb0d253271517` - "Add reference-backed DJ
performance templates". It contains the explicitly selected template and
renderer layer, regression coverage, durable archetype contract, and private
same-pair output metadata. It was pushed to
`origin/v2-professional-autonomous-dj`; resolve the current tip from Git rather
than treating this field as immutable.

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
The only immediate blocker is the manual-vs-automated same-pair listening
gate. Technical checks cannot establish that `AUTO_F`, `AUTO_C3`, `AUTO_B8`,
and `AUTO_D2` preserve the musical behavior of their accepted references.
Autonomous selection remains paused until the user accepts these renders.

## EXACT NEXT ACTION
Stop for the user to compare manual F vs `AUTO_F`, manual C3 vs `AUTO_C3`,
manual B8 vs `AUTO_B8`, and manual D2 vs `AUTO_D2`. If an automated version is
substantially worse, correct only the template/instantiation/rendering layer.
Do not generalize to new pairs or resume Candidate Composer, Audition Lab, Set
Director, UI, or full mixes.
