# DJenius V2 State

## CURRENT PHASE
Phase 7 - Set Director V2: **COMPLETE / READY TO FREEZE**. Phase 8 - UI V2 is the exact next implementation phase only after the Phase 7 privacy gate, commit, push, and local/remote HEAD verification.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## PREVIOUS FROZEN COMMIT
`c55b760b5cd9439f99f312fc47c8398334df5928` - `Add V2 audition lab` (Phase 6).

## WORKING TREE STATE
Phase 7 production code (`djenius/core/set_director.py`), dedicated tests
(`tests/test_v2_phase7_set_director.py`), and durable documentation are
complete locally and awaiting the final privacy/diff gate, coherent commit,
push, and local/remote HEAD verification. Private real-audio validation
artifacts remain only under `/tmp/djenius_phase7_smoke` and must not enter
Git.

- Base V1 commit: `efcfcca6d21aeaa595b236306b025b70668106fd`.
- V1 master remains unchanged.

## COMPLETED WORK
- Phases 0-6 are frozen; Phase 6 is pushed at `c55b760b5cd9439f99f312fc47c8398334df5928`.
- Phase 7 adds `djenius/core/set_director.py`: a deterministic, additive whole-set journey planner sitting above Phase 5 (Candidate Composer) and Phase 6 (Audition Lab), while leaving `djenius/core/planner.py` (the classic beam-search planner) completely untouched.
- Five explicit set arcs (smooth, warm-up-to-peak, peak-time, wave, open-format) each define a deterministic per-position target energy curve (`arc_energy_target`).
- Combinatorial audition cost is controlled by a fixed pipeline: a cheap, audio-free compatibility+arc-fit shortlist narrows next-track candidates before Phase 5 runs at all; only a configurable bounded number of the resulting Phase 5 candidates are ever rendered/audited by Phase 6; every `(source, target, context)` outcome is cached (`EdgeAuditionCache`); a hard compute ceiling falls back to a cheap-compatibility-only summary once hit.
- The beam search over track order is fully deterministic — no randomness is used for ordering decisions, only Phase 5's `seed` salts candidate-ID hashing, and every tie breaks on the track-id tuple lexicographically.
- A real (not merely cosmetic) tempo-reset budget exists: `CandidateSetContext.allow_tempo_reset` is actually gated by how many deliberate resets a path has already used relative to `SetDirectorConfig.effective_max_reset_budget(arc)`, so Phase 5 stops offering tempo-reset candidates once an arc's budget is spent.
- The objective is a transparent, decomposed, non-circular sum: handoff quality (Phase 6 score), energy-arc fit, BPM-journey fit, vocal pacing, groove continuity/contrast (arc-dependent), technique diversity, artist spacing, duration fit, and reset budget — each independently reported in `SetDirectorPlan.component_totals`.
- `measure_set_quality` computes validation facts (energy-arc error, peak-placement error, BPM-jump statistics, consecutive-vocal-heavy count, technique-repetition stats, artist-spacing violations, viable-audition-edge rate, mean selected-audition score, hard-rejection rate) entirely independently of the internal weighted objective, specifically to avoid circular "optimize X, validate with X" reasoning.
- `compare_to_shuffled_baselines` compares a planned order against many seeded shuffled orderings of the identical track pool on those independent metrics, using a neutral (non-technique-memory-chained) audition context so repeated pairs across shuffles are cache hits.
- Real-music validation: three set intents (warm-up-to-peak, smooth, open-format) were planned from the same 12-track anonymized real library and each beat 12 seeded shuffled baselines on the majority of independent metrics (see `BENCHMARK.md` for the full table); technique sequences were genuinely varied, not collapsed to one family.

## TEST RESULTS
- Dedicated Phase 7 suite: **17 passed in ~24s**.
- Broad targeted gate (analysis/recipe/technique/groove/candidate/audition/set-director/renderer/planner/scorer/model): **326 passed in ~31s**.
- Complete repository regression: **1079 passed in ~44s**, with **2 known Typer/Click dependency deprecation warnings** and no asynchronous timeout failures.
- `ruff check` clean on both new files.
- Real-music gate (12 anonymized tracks, 3 arcs, 12 shuffled baselines each): planned order won or tied on every independent metric in all three arcs, and strictly won on artist spacing and viable-audition-edge rate in all three. Full table in `BENCHMARK.md`.

## KNOWN LIMITATIONS / TECHNICAL DEBT
- With a small real library, a forced-length path can include a handoff where every audited candidate hard-rejects (0 survivors); Set Director reports this truthfully (`selected_family: None`, `handoff_quality: 0.0`) rather than fabricating a winner, but has no backtracking/path-abandonment mechanism yet to avoid accepting such a forced handoff. Observed once in the SET_B real-music run.
- `mean_selected_audition_score` is a weaker discriminator of ordering quality specifically when a library's BPM/key/vocal properties are close to uniform (a dedicated synthetic test isolates this on purpose) or when different arc positions steer Phase 5 toward different technique families independent of ordering quality. Reported for transparency; not treated as a hard pass/fail signal on its own.
- Set Director inherits every Phase 5/6 deferred metric (certified true peak, isolated-kick alignment, overlap-local harmonic quality, vocal intelligibility, stem bleed) since it audits through those same components unchanged.
- Set Director's automated shuffled-baseline win proves the planned order is measurably more coherent than random on independent, human-interpretable axes. It does **not** prove the set sounds like a professional human DJ performance; that remains for the later blind listening gate.

## CURRENT BLOCKERS
None for freezing Phase 7. Phase 8 - UI V2 must expose set trajectory, waveform structure, transition candidates, preview, performance timeline, creativity controls, and manual locks per the research specification (section 24 / Phase 8 in the roadmap), building on the now-available `SetDirectorPlan` diagnostics.

## EXACT NEXT ACTION
Run the Phase 7 privacy/diff gate over the exact tracked/untracked change set. If clean, stage only public-safe Phase 7 source/tests/docs; commit as `Add V2 set director`; push `origin/v2-professional-autonomous-dj`; verify clean working tree and exact local/remote HEAD equality. Only then begin Phase 8 UI V2.
