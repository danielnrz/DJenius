# DJenius V2 State

## CURRENT PHASE
All roadmap phases (0-10) have their autonomous portions complete and
pushed. **There is no active roadmap phase and none should be started.**
Phase 10's actual defining gate -- the human blind V1-vs-V2 listening
comparison -- has now been run **twice** by the user, and **has not passed
either time**:

1. First listen (pre-fix): V1 and V2 were not meaningfully distinguishable
   at all.
2. Second listen (post-fix, current V2 code): V2 techniques (loops, builds,
   drops, echo, bass changes) are occasionally noticeable, but "subtle/
   small," "not transformative," and -- the user's own words -- **"it still
   does NOT feel like a real DJ is actively performing... I did not have
   moments where I clearly thought: 'yes, that was a real DJ move.'"**

**PERFORMANCE QUALITY / DJ-LIKENESS IS NOW THE PROJECT'S SINGLE OPEN,
UNRESOLVED, CROSS-PHASE GATE.** This is not a defect in any one phase's
own acceptance criteria -- every phase's own dedicated tests and the full
1095-test regression suite pass. It is a product-level gate above and
across all phases (research spec section 32/43), and it is the only thing
standing between "V2 is technically complete" and "V2 is done." Do not
interpret the phase-completion history below as contradicting this: the
phases built the right machinery; the machinery is not yet producing an
audibly convincing autonomous DJ performance.

## PERFORMANCE-RECOVERY CHECKPOINT (HUMAN GATE PENDING)

The two leading root causes above have now been corrected in a validated local
checkpoint:

- Set Director schema 7.1 plans a typed, path-dependent `TrackAppearance` and
  protects an explicit establishment window before the next transition. The
  real recovery set rendered with zero anchor shifts; its middle tracks had
  33.599–191.989 seconds of independent airtime.
- Phrase-cut target-cursor semantics, full-set stem delivery, Phase-5
  EQ/build/landing choreography, riser/impact musical placement, post-fader
  echo release, and family-aware Audition spectral damage modeling were fixed
  through the actual production path.
- The private fixed-anchor family audit and full V1/previous-V2/recovery-V2
  listening package are at `/tmp/djenius_performance_lab/`; the durable matrix
  is `docs/v2/PERFORMANCE_QUALITY_AUDIT.md`.
- Focused recovery tests pass at 110; complete regression passes at **1102
  passed**. This evidence protects implementation only. It does **not** close
  the twice-failed human DJ-quality gate.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## LATEST PERFORMANCE-RECOVERY COMMIT
`32b2d3d6e679495d0edd7818fd2a787cb512608e` - "Recover V2 DJ performance
choreography". It contains the production fixes, regression coverage, durable
technique audit, and private-package metadata references described above, and
was pushed to `origin/v2-professional-autonomous-dj`. A docs-only handoff
finalization may follow it; resolve the current tip from Git rather than this
historical field.

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
Not a missing feature or a failing test. The blocker is that **V2 does not
yet sound and behave like an intentional, skilled autonomous DJ**, per two
independent real human listens using the actual current code. Do not treat
this as closeable by more automated verification alone -- closing it
requires actual audible/behavioral improvement, then a third human listen.

## EXACT NEXT ACTION
Do **not** start UI or broad feature work. Human-listen to the new private
checkpoint against V1 and previous V2. If recognizable intent/taste still does
not clear the gate, use the contextual and controlled clips to identify which
specific move fails (especially bass swap or drum bridge) and continue the
smallest production-path correction. Do not close the project from tests or
distance metrics alone.
