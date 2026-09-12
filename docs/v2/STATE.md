# DJenius V2 State

## CURRENT PHASE
Phase 6 - Audition Lab: **COMPLETE / READY TO FREEZE**. Phase 7 - Set Director V2 is the exact next implementation phase only after the Phase 6 privacy gate, commit, push, and local/remote HEAD verification.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## PREVIOUS FROZEN COMMIT
`a17d2aafa261536260eadc440ff5ea5379ce243d` - `Add V2 candidate composer` (Phase 5).

## WORKING TREE STATE
Phase 6 production code, regression tests, the one-sample Phase 4 sampler boundary fix found by Phase 6 integration, and durable documentation are complete locally and awaiting the final privacy/diff gate, coherent commit, push, and local/remote HEAD verification. Private real-audio validation artifacts remain only under `/tmp/djenius_phase6_smoke` and must not enter Git.

- Base V1 commit: `efcfcca6d21aeaa595b236306b025b70668106fd`.
- V1 master remains unchanged.

## COMPLETED WORK
- Phases 0-5 are frozen; Phase 5 is pushed at `a17d2aafa261536260eadc440ff5ea5379ce243d`.
- Phase 6 adds deterministic bounded candidate-preview rendering plus typed audition metrics, failures, rankings, decisions, provenance, and one-handoff selection.
- Every preview binds candidate/recipe/source/target identity, exact transition/context bounds, sample rate/channels/duration, render configuration, renderer provenance, sample-layer provenance, and deterministic audio SHA-256.
- Hard rejection occurs before soft ranking. NaN/Inf, render failure, broken bounds, candidate-transition clipping/unsafe peak proxy, catastrophic transition silence, severe boundary discontinuity, invalid stem/provenance use, and unstable declared stretch fail closed.
- Candidate-introduced peak/silence safety is measured on the rendered transition, while whole-preview peak/clipping remains audit metadata. This prevents pre-existing mastered source/target context from falsely rejecting every candidate.
- The inter-sample measure is explicitly a **4x polyphase oversampled/inter-sample peak proxy**, not an ITU/broadcast-certified true-peak meter.
- Active soft evidence covers beat-grid phase/onset/drift proxies, local tempo mismatch reporting, LF/bass/mud/HF/spectral-hole/continuity proxies, context-aware vocal collision, technique-aware energy behavior, and family-specific FX safety where applicable.
- Unsupported overlap-local harmonic quality, certified true peak, isolated-kick alignment, vocal intelligibility, and stem bleed remain explicitly deferred rather than represented as fabricated zeros.
- Soft components are normalized to `[0,1]`, weights are configurable, inapplicable beat/FX metrics are excluded from the active denominator, and equal scores use deterministic candidate-ID tie breaking.
- Phase 6 integration found and fixed a one-sample second-to-sample rounding residue for a generated event ending exactly on the transition boundary. Only a one-sample overrun is trimmed and recorded in provenance; larger overruns still fail closed.

## TEST RESULTS
- Dedicated Phase 6 suite: **36 passed in 2.92s**.
- Broad V2 analysis/recipe/technique/groove/candidate/audition/renderer/provenance/application/model gate: **315 passed in 7.90s**.
- Complete repository regression: **1062 passed in 25.28s**, with **2 known Typer/Click dependency deprecation warnings** and no asynchronous timeout failures.
- Four anonymized private real handoffs auditioned **8 / 7 / 3 / 4** candidates; all **22/22 rendered successfully** after the rounding fix.
- Hard rejections by pair: **0 / 4 / 0 / 2**. Survivors: **8 / 3 / 3 / 2**. Selected families: **loop_shortening / drum_bridge / stem_handoff / stem_handoff**.
- Survivor score spreads by pair: **0.209766 / 0.057835 / 0.088534 / 0.043897**; rankings did not collapse to identical scores or one universal technique.
- Exact rerun of one real handoff reproduced candidate IDs, preview bounds/hashes, metrics, hard-rejection decisions, scores, ordering, and winner exactly.
- Controlled real-preview damage gate: a 100 ms beat shift reduced score **0.783336 -> 0.713880**; severe LF collision reduced it to **0.701851**; clipping, severe discontinuity, catastrophic silence, and excessive FX-tail overgain were hard rejected. `KNOWN BAD < GOOD REFERENCE` passed.
- Component audit: **120** active real-smoke component values were all in `[0,1]`; no active component lacked a configured weight; the largest observed single active-weight share was **24.44%**.

## KNOWN LIMITATIONS / TECHNICAL DEBT
- Audition ranking remains a transparent deterministic heuristic, not human-perceived professional-DJ certification. Blind listening remains authoritative for release quality.
- The oversampled peak metric is a safety proxy, not standards-compliant true peak.
- Beat evidence uses a frame-energy onset proxy rather than isolated kick detection.
- Reliable preview-local harmonic/chroma quality, vocal intelligibility, and stem-bleed metrics are not yet available and remain deferred.
- Private smoke used four handoffs selected from the existing current-V2 local benchmark subset; it is evidence for Phase 6 behavior, not a statistically representative music corpus.

## CURRENT BLOCKERS
None for freezing Phase 6. Phase 7 must remain above handoff-level audition and reason about set-level ordering, pacing, energy arc, continuity/contrast, vocal density, BPM journey, planned resets, repetition avoidance, technique diversity, and local audition outcomes.

## EXACT NEXT ACTION
Run the Phase 6 privacy/diff gate over the exact tracked/untracked change set. If clean, stage only public-safe Phase 6 source/tests/docs plus the focused one-sample sampler boundary fix; commit as `Add V2 audition lab`; push `origin/v2-professional-autonomous-dj`; verify clean working tree and exact local/remote HEAD equality. Only then begin Phase 7 Set Director V2.
