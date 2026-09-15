# DJenius V2 Benchmark

## V1 frozen baseline
- Commit: `efcfcca6d21aeaa595b236306b025b70668106fd`
- Full test suite: **846 passed in 17.96s**
- Doctor: all critical checks PASS
- Current cached V1 analyses: 17 tracks (analysis version 5)

## Existing-plan aggregate
A local aggregate scan of saved ignored plan artifacts found 18 plans and 87 classic transition records:

| Transition family | Count | Share |
|---|---:|---:|
| filter_sweep | 26 | 29.9% |
| phrase_cut | 23 | 26.4% |
| beatmatched_blend | 19 | 21.8% |
| bass_swap | 9 | 10.3% |
| loop_blend | 4 | 4.6% |
| crossfade | 3 | 3.4% |
| echo_out | 3 | 3.4% |

This is not a perceptual quality score, but it establishes a reproducible technique-diversity baseline and confirms concentration in a small set of safe families.

## Existing saved-plan trajectory evidence
- BPM: 95.7 / 119.52 / 136.0 min/mean/max across 103 saved track appearances.
- Mean energy: 0.698 / 0.745 / 0.836 min/mean/max across 103 saved track appearances.
- Unique Camelot labels: 10.

## Reused local V1 listening references
Existing ignored local WAVs include smooth and energetic certification/user mixes. Their audio remains local and is not listed with private track metadata in Git.

## V2 measurements
Phase 1 measurements will be appended after targeted, full-regression and private real-track validation.

## Final certification requirement
The release benchmark will include planned-vs-shuffled set metrics, technique diversity, audition ranking, private difficult-pair tests, multiple complete V2 sets, and blind V1-vs-V2 human listening. Automated metrics alone cannot release V2.

## Phase 1 - Analysis V2 gate
- V2 analysis schema: `2.0`; cache analysis version: 6.
- New targeted/synthetic tests: 10; targeted bundle with legacy model/phrasing tests re-verified at **65 passed in 0.86s**.
- Full regression re-verification: **856 passed in 17.95s**.
- Private real-track validation (3 tracks, anonymized): BPM confidence mean 0.981; beat counts 195/361/423; sustained tempo-zone counts after refinement 2/1/1; phrase profile counts 5/5/8; section profile counts 6/6/9; cue counts 6/6/9; groove-confidence values 1.0/1.0/1.0; cached stem activity profiles 4/4/4.
- The initial tempo-zone implementation produced 5/12/6 zones on the same tracks and was rejected as too jitter-sensitive before the phase gate.
- Privacy check: no testMusic, generated audio, stems, data caches, or private song names in the tracked Phase 1 change set.

## Phase 2 - Performance Recipe DSL gate
- New Phase 2 tests: **32 passed**.
- Related performance/renderer targeted bundle: **75 passed in 2.06s**.
- Complete regression: **888 passed in 15.83s** (Phase 1 baseline: 856).
- Five proof recipes serialize deterministically and compile into the existing renderer contract: EQ blend -> beatmatched blend, bass swap -> bass swap, phrase cut -> phrase cut, loop transition -> loop blend, echo release -> echo out.
- All five proof recipes rendered synthetic stereo audio successfully with clean provenance.
- Beatmatched compilation explicitly records time-stretch need and target-source consumption when BPMs differ.
- Recipe/action IDs are deterministic content hashes; round-trip serialization preserves identity and payload exactly.
- Privacy check: no testMusic, generated audio, stems, caches, or private song names entered the tracked Phase 2 change set.

## Phase 3 - Core DJ Technique Engine gate
- Dedicated Phase 3 suite: **40 passed in 1.76s**.
- Expanded renderer/technique gate: **144 passed in 5.65s**.
- Application-layer integration gate: **4 passed, 36 deselected in 0.92s**.
- Final complete repository regression: **928 passed in 24.01s**.
- Technique coverage: **12/12 implemented, 12/12 renderer-reachable, 12/12 synthetically validated, 12/12 private-real-audio smoke validated**.
- Technique families: EQ blend, bass swap, filter blend, phrase cut, echo out/release, reverb wash, loop transition, loop shortening, drum overlay, riser+impact, tempo reset, stem handoff.
- Private validation library contained 17 audio files; 15 had complete cached real stem sets. Only aggregate/anonymized evidence is recorded here.
- Bass swap and stem handoff executed real cached-stem DSP paths; drum overlay consumed target drums; explicit no-stem/invalid-stem fallback diagnostics were verified.
- Stem-path renders materially differed from their fallback renders, confirming the real-stem path was not only nominally flagged.
- Generated FX and stem/preparation provenance remained explicit in transition diagnostics.
- One earlier loaded full-suite run produced **921 passed, 3 failed** from fixed-timeout async polling (`job did not finish`). Those exact tests immediately passed alone (**3 passed in 4.70s**), and later unchanged full regressions passed at 928/928. This remains test-timing technical debt, not hidden history.
- Private previews/reports remained outside Git under `/tmp/djenius_phase3_private_smoke` during validation.

## Phase 4 - Groove / Sampler Layer gate
- Dedicated Phase 4 suite: **58 passed in 1.38s**.
- Frozen Phase 2 + Phase 3 gate: **72 passed in 1.71s**.
- Broad targeted renderer/provenance/application integration gate: **208 passed in 5.87s**.
- Complete repository regression: **986 passed in 28.99s** with **2 Typer/Click dependency deprecation warnings** and no asynchronous timeout failures.
- Five anonymized private real-audio smoke scenarios passed: percussion bridge, drum fill before landing, riser+impact, downlifter reset, and offbeat-hats percussion. Each had finite duration-correct output, `clipping_fraction = 0.0`, audible/bounded added layer, complete provenance/ownership, and a clean provenance audit.
- Source-analysis evidence for the real smoke: BPM 117.5, BPM confidence 0.976, analysis confidence 0.956. Riser/impact landing drift was approximately 2.307 ms; detected-beatgrid drift across tested scenarios remained roughly within 44 ms worst case for the selected real beatgrid window.
- Privacy boundary: private smoke artifacts remain only under `/tmp/djenius_phase4_smoke`; no private track identity/media is recorded in Git.

### Phase 4 capability matrix
| Capability | Implemented | Recipe reachable | Renderer reachable | Synthetically validated | Real-audio smoke validated | Provenance validated |
|---|---|---|---|---|---|---|
| Kick | YES | YES | YES | YES | YES | YES |
| Snare | YES | YES | YES | YES | YES | YES |
| Clap | YES | YES | YES | YES | YES | YES |
| Closed hat | YES | YES | YES | YES | YES | YES |
| Open hat | YES | YES | YES | YES | YES | YES |
| Percussion pattern | YES | YES | YES | YES | YES | YES |
| Drum fill | YES | YES | YES | YES | YES | YES |
| Riser | YES | YES | YES | YES | YES | YES |
| Downlifter | YES | YES | YES | YES | YES | YES |
| Impact | YES | YES | YES | YES | YES | YES |
| Reverse sweep/cymbal | YES | YES | YES | YES | NO | YES |

The `NO` above is deliberate: reverse sweep/cymbal passed deterministic synthesis, recipe/compiler, renderer, and provenance tests, but was not one of the five Phase 4 real-audio smoke scenarios.

### Phase 4 ownership/safety evidence
- Phase 3 `riser_impact` stays owned by creative FX DSP; Phase 4 discrete riser/impact stays owned by the groove/sample layer. The auditor rejects an ownership collision.
- Duplicate sample event IDs and declared/rendered sample-layer count mismatches are explicit provenance failures.
- Quarter/eighth/sixteenth scheduling, deterministic seeds, mono/stereo rendering, finite/non-silent checks, overlap peak protection, DC-offset protection, bounded event gains/levels, and exact event sample bounds are covered.
- Empty `sample_layer_events` preserves the legacy renderer path; serialized transitions missing the new field deserialize to an empty list.

## Phase 5 - Candidate Composer gate
- Dedicated Phase 5 suite: **40 passed in 0.42s**.
- Frozen Phase 2 + Phase 3 + Phase 4 + Phase 5 gate: **170 passed in 2.09s**.
- Broad V2 analysis/recipe/technique/groove/candidate/application/model/transition/renderer gate: **267 passed in 6.16s**.
- Complete repository regression: **1026 passed in 27.90s** with **2 existing Typer/Click dependency deprecation warnings** and no asynchronous timeout failures.
- Candidate generation is deterministic, feasibility-first, family-diverse, explanation-bearing, and compilation-gated. The default search envelope is 3-8 where context permits; the minimum is not a hard safety override.
- Confidence-gated half/double logic uses threshold **0.55** and is boundary-tested below/at/above threshold. Low-confidence apparent half/double relationships retain tempo-reset eligibility.
- Technique memory is soft-defer with deterministic floor fallback. Reintroduced repeats are explicit in reason codes/provenance; hard-infeasible recent families remain rejected; unmet floors report hard-feasibility exhaustion instead of inventing candidates.
- Six anonymized private current-V2 handoffs yielded candidate counts **8 / 7 / 3 / 4 / 7 / 4**, for **33 accepted candidates total**. **33/33** accepted recipes compiled successfully.
- Real-pair observations matched the intended feasibility boundary: vocal-heavy contexts suppressed inappropriate long blends/loops, stem handoffs required declared stems, build/riser families required landing evidence, and large primary-tempo mismatches retained reset eligibility when appropriate.
- `PAIR_03` changed only between equivalent tempo-relation representations to a higher-confidence equivalent; feasibility and family membership were unchanged.
- No real-pair case happened to exercise technique-memory fallback; that behavior is covered by focused deterministic tests instead.
- Privacy boundary: private track identities, raw analyses, audio/stems/previews, and `/tmp/djenius_phase5_smoke` artifacts remain outside Git.
- Phase 5 benchmark explicitly contains **no perceptual winner score**. Phase 6 Audition Lab will benchmark rendered candidate rejection/ranking, with the controlled acceptance requirement that known bad candidates rank below good references.

## Phase 6 - Audition Lab gate
- Dedicated Phase 6 suite: **36 passed in 2.92s**.
- Broad V2 analysis/recipe/technique/groove/candidate/audition/renderer/provenance/application/model gate: **315 passed in 7.90s**.
- Complete repository regression: **1062 passed in 25.28s** with **2 existing Typer/Click dependency deprecation warnings** and no asynchronous timeout failures.
- Four anonymized private real handoffs rendered **8 / 7 / 3 / 4** candidates (**22 total**). Hard rejections were **0 / 4 / 0 / 2** and survivors were **8 / 3 / 3 / 2**.
- Deterministic winner families were **loop_shortening / drum_bridge / stem_handoff / stem_handoff**. Survivor score spreads were **0.209766 / 0.057835 / 0.088534 / 0.043897**, so the real gate did not collapse to equal scores or one universal family.
- Exact rerun evidence: candidate IDs, preview bounds and deterministic audio hashes, metrics, hard-rejection decisions, scores, ordering, and selected winner reproduced exactly for one anonymous real handoff.
- Controlled real-preview damage: clean reference score **0.783336**; 100 ms beat shift **0.713880**; severe LF collision **0.701851**. Clipping/overgain, severe boundary discontinuity, catastrophic silence, and excessive FX-tail overgain were hard rejected. The defining `KNOWN BAD < GOOD REFERENCE` gate passed.
- Score-component audit covered **120** active real-smoke values: all were bounded in `[0,1]`, all active names mapped to configured weights, and the largest observed single active-weight share was **24.44%**. Non-applicable beat/FX metrics were omitted rather than represented as punitive zeros.
- The real gate exposed and fixed two defects before freeze: pre-existing source/target context peaks were incorrectly participating in candidate hard peak rejection, and a valid fractional-BPM impact could round one sample past the sample-layer buffer. Candidate safety is now transition-scoped with whole-preview audit fields; the one-sample terminal residue is trimmed and provenance-recorded while larger overruns remain errors.
- The oversampled/inter-sample peak measure remains a **4x polyphase proxy**, not certified true peak. Reliable overlap-local harmonic quality, isolated-kick alignment, vocal intelligibility, and stem bleed remain explicitly deferred.
- Privacy boundary: private track identities, raw analyses, source audio/stems, previews, and `/tmp/djenius_phase6_smoke` artifacts remain outside Git.

## Phase 7 - Set Director V2 gate
- Dedicated Set Director suite: **17 passed in ~24s**.
- Broad V2 gate (analysis/recipe/technique/groove/candidate/audition/set-director/renderer/planner/scorer/model): **326 passed in ~31s**.
- Complete repository regression: **1079 passed in ~44s** with the same pre-existing Typer/Click dependency deprecation warnings and no asynchronous timeout failures.
- `ruff check` on the new production/test files: all checks passed.
- Real-music gate: a 12-track anonymized library (`TRACK_00`-`TRACK_13` minus 2 files that failed to decode; one ~20-minute non-music outlier excluded by duration) was drawn from the existing private `testMusic/` corpus via the already-frozen Phase 1 analyzer (`djenius/audio/analyzer.py::analyze_track`, cache-hit for all 12). Three arcs were planned from the same pool and each compared against **12** seeded shuffled baselines of the same 12 tracks:

  | Set | Arc | Tracks | Handoffs | Duration vs target | energy_arc_error | peak_placement_error | artist_spacing | viable_audition_edge_rate | mean_selected_audition_score |
  |---|---|---:|---:|---|:---:|:---:|:---:|:---:|:---:|
  | SET_A | warmup_to_peak | 5 | 4 | 902s / 900s | **WIN** (0.260 vs 0.265) | **WIN** (0.486 vs 0.617) | **WIN** (0 vs 3.0) | **WIN** (1.00 vs 0.45) | tie (0.658 vs 0.661) |
  | SET_B | smooth | 6 | 5 | 1053s / 900s | tie (0.265 vs 0.263) | **WIN** (0.136 vs 0.288) | **WIN** (0 vs 3.08) | **WIN** (0.80 vs 0.54) | **WIN** (0.691 vs 0.655) |
  | SET_C | open_format | 6 | 5 | 993s / 900s | tie (0.201 vs 0.201) | **WIN** (0.136 vs 0.227) | **WIN** (0 vs 2.5) | **WIN** (1.00 vs 0.48) | **WIN** (0.680 vs 0.657) |

  ("WIN" = planned strictly beat the mean of 12 shuffled baselines; "tie" = within noise of the baseline mean.) The planned order won or tied on every independent metric in all three arcs, and strictly won on artist spacing and viable-audition-edge rate in all three.
- Selected technique sequences were genuinely varied across the three real sets: SET_A used `echo_out, phrase_cut, drum_bridge, riser_impact`; SET_B used `echo_out, loop_shortening, drum_bridge, riser_impact` plus one forced zero-survivor handoff (see limitation below); SET_C used `riser_impact, riser_impact, phrase_cut, drum_bridge, echo_out`. No arc collapsed to one repeated family.
- Compute-cost control worked as designed: each of the three real plans considered on the order of 128-135 candidate next-track pairs, cheaply shortlisted down to 56-60, generated 207-212 Phase 5 candidates, and rendered/audited only 112-120 of them (2 per shortlisted edge) — end-to-end plan time was 12-13s and the 12-shuffle baseline comparison 16-19s each, on top of one-time cache-hit analysis and a ~1s resample-all-tracks step.
- Known limitation: SET_B's forced 6-track path included one handoff where every audited candidate hard-rejected (0 survivors out of 2 audited); Set Director reports this truthfully as `selected_family: None`, `handoff_quality: 0.0` rather than fabricating a winner, but has no backtracking/path-abandonment mechanism yet to avoid accepting a forced zero-survivor handoff when a small real library leaves no better local option.
- `mean_selected_audition_score` tied (rather than won) for SET_A and was closer than the other metrics for SET_B/SET_C; this matches the documented caveat (`DECISIONS.md` D036) that this particular metric is a weaker discriminator of ordering quality specifically, since Phase 5's technique-family choice is also steered by arc-position context, not only by which order is "better."
- Privacy boundary: private track identities, raw analyses, source/decoded audio, and all `/tmp/djenius_phase7_smoke` artifacts (including the throwaway driver scripts) remain outside Git; only anonymous `TRACK_NN`/`SET_A|B|C` labels and aggregate metrics are recorded here.

## Phase 8 - UI V2 (Set Director inspection slice) gate
- New backend test: **1 passed** (`test_set_director_plan_inspect_lock_and_preview`), exercising create-plan/poll/inspect/lock/preview/404 through the real FastAPI app with real (tiny synthetic) audio.
- Complete repository regression: **1080 passed** (1079 at the Phase 7 checkpoint + 1). `ruff check` clean on every new/changed file except one pre-existing, unrelated unused-import warning in `application.py` that predates this phase.
- Manual real-browser verification against the actual local app and the real anonymized `testMusic` library (12+ tracks, same corpus as the Phase 7 real-music gate): scanned/analyzed the real library through the existing UI, planned a Set Director journey (smooth arc, 4 real tracks selected to fit a 10-minute target), and confirmed:
  - the trajectory view showed real per-track BPM/key/energy;
  - the component-totals breakdown rendered all nine Phase 7 objective components as bars;
  - the handoffs list showed a real selected technique family and score per handoff;
  - opening the Transition Inspector on one real handoff listed 4 real audited candidates: 2 survivors (ranked, with real scores ~0.70 and ~0.70) and 2 correctly hard-rejected with honest reasons (one on preview clipping/peak safety, one on the undelivered-stems limitation documented in `IMPLEMENTATION_PLAN.md`);
  - clicking "Preview" on the runner-up candidate rendered a real bounded-preview WAV and played it in-browser (`<audio>` element advanced through real playback time);
  - clicking "Use this" locked that candidate; both the inspector modal and the underlying handoffs list updated immediately (no page reload) to show the new technique/score and a "locked" indicator;
  - re-fetching the plan view via the API independently confirmed the override was persisted server-side, not just rendered client-side.
  - a fresh classic (non-Set-Director) plan-creation request through the pre-existing UI still rendered correctly after the shared `renderPlan` bugfix, confirming no regression to the legacy path.
- No private track title, artist, or filepath appears in this entry or any other tracked file; the verification above is reported only in structural/aggregate terms.
- Known limitation carried forward (not a defect): full continuous full-mix rendering of a Set-Director-planned set is not wired this phase; only bounded per-handoff preview rendering is exposed. `HandoffSummary.candidates` (added this phase) retains the real `TransitionCandidate`/`PerformanceRecipe` needed for a future full-mix renderer.

## Phase 9 - Personalization gate
- Dedicated suite: **4 passed** (`tests/test_v2_phase9_personalization.py`): config validation requires the new `user_preference` weight key; a technique-family preference is reflected exactly in that component and shifts `total_score` in the expected direction (liked > neutral > disliked); a disliked track loses a controlled two-track choice to an equally-good alternative; a liked track wins the analogous choice.
- Two new/extended backend tests in `test_app.py`: the full HTTP feedback flow (rate a real handoff -> appears in `/api/preferences` -> unknown rating rejected with 400) and three repeated "bad" ratings against one technique family producing `technique_preferences[family] == 0.0` in a freshly-built `SetDirectorConfig`.
- Complete repository regression: **1085 passed** (1080 at the Phase 8 checkpoint + 5). `ruff check` clean on every changed file; the one pre-existing, unrelated unused-import warning in `application.py` is unchanged.
- Manual real-browser verification: rated a real Set Director handoff's technique family "great" through the Transition Inspector's new feedback buttons, confirmed the toast, confirmed `GET /api/preferences` reflected the rating, and confirmed the *pre-existing, unmodified* Preferences tab UI rendered it correctly with zero new frontend code for that view (it already called the same underlying preference method).
- No schema migration: technique-family feedback reuses V1's existing `transition_ratings` table (a free-text column, not enum-constrained) rather than introducing a parallel one -- V1's 8 legacy transition types and Set Director's 11 technique families coexist as different string values in the same aggregate with no conflict.
- Real-world context: this session's local dev preference database (pre-existing, from real prior use of the app, not created for this phase) already had 2 liked tracks and several mix ratings recorded; `_set_director_learned_preferences()` picked these up automatically the first time it ran, confirming the wiring activates on genuinely pre-existing user data, not only freshly-seeded test data. No private track identity is recorded here.
- No private track title, artist, or filepath appears in this entry or any other tracked file.

## Phase 10 - Certification gate (autonomous portion)
- Dedicated suite: **6 passed** (`tests/test_v2_phase10_certification.py`), plus **1** new `test_app.py` case for the full HTTP render flow.
- Complete repository regression: **1092 passed** (1085 at the Phase 9 checkpoint + 7). `ruff check` clean (one pre-existing, unrelated `application.py` warning unchanged).
- Real full-mix render (new capability this phase, `djenius/audio/set_director_renderer.py`): a genuine continuous mix was planned and rendered from 3 real `testMusic` tracks through the actual running app (smooth arc, target duration 8 min, 2 real handoffs, techniques `riser_impact` then `loop_shortening`). Measured directly on the rendered file:

  | Metric | Value |
  |---|---:|
  | Duration | 251.1s (~4:11) |
  | Sample rate | 22050 Hz stereo |
  | Finite | 100% |
  | RMS level | -14.8 dBFS |
  | Peak | 1.000 |
  | Clipping fraction (\|x\|>=0.999) | 3.6e-7 (~2 of 5.5M samples) |
  | Silence fraction (<-55 dBFS) | 1.3% |

  This file was delivered directly to the user as the first real artifact ready for their blind V1-vs-V2 comparison.
- Building the renderer surfaced a genuine architectural fact, confirmed on this same real plan (not only on synthetic fixtures): Phase 5 chooses each edge's anchors independently of its neighbors, so a shared middle track's target-entry point and its own later source-exit point are not guaranteed to be in timeline order. The renderer now detects and corrects this by shifting the affected transition to start exactly where the previous edge ended (`anchor_shift_sec` in provenance), rather than failing. See `DECISIONS.md` D044.
- Private difficult-pair transition benchmark (research spec 30.4), built from the same anonymized 12-track library the Phase 7 real-music gate used (`/tmp/djenius_phase10_smoke`, never committed):

  | Category | Real matches in library | Representative pair result |
  |---|---:|---|
  | same BPM / same key | 0 | not observed in this library |
  | same BPM / bad key | 8 | 7 generated, 1 survivor, `drum_bridge` selected (0.575) |
  | large BPM difference | 60 | 3 generated, 2 survivors, `echo_out` selected (0.785) |
  | half-time relation | 6 | 3 generated, 2 survivors, `echo_out` selected (0.590) |
  | vocal-heavy -> vocal-heavy | 72 | 3 generated, **0 survivors** (see below) |
  | instrumental -> vocal | 9 | 4 generated, **0 survivors** (see below) |
  | genre change | 0 | no reliable genre signal available to test against |
  | weak intro | 88 | 4 generated, 3 survivors, `echo_out` selected (0.652) |
  | weak outro | 22 | 3 generated, 2 survivors, `echo_out` selected (0.584) |
  | variable tempo | 42 | 4 generated, 3 survivors, `echo_out` selected (0.652) |
  | stem-friendly | 132 | 4 generated, 3 survivors, `echo_out` selected (0.652) |
  | stem-poor | 0 | every track in this library has declared stems |
  | short track | 22 | 4 generated, 3 survivors, `echo_out` selected (0.652) |
  | long ambient intro | 0 | not observed in this library |
  | strong double-drop candidate | 0 | not observed in this library |

  The two zero-survivor rows were independently confirmed by auditioning *every* generated candidate for that pair (not a bounded subset): one candidate hard-rejected on the already-documented missing-stems limitation, the others on genuine peak/clipping safety against already-loudly-mastered real vocal material. This is recorded as a real, specific, actionable gap -- Candidate Composer currently has no minimal-risk fallback family (e.g. a restrained equal-power crossfade) guaranteed feasible regardless of vocal/loudness conditions -- not smoothed over or re-sampled until a nicer result appeared.
- No private track title, artist, or filepath appears in this entry or any other tracked file.
- **What Phase 10 has not done, and cannot do autonomously**: the blind V1-vs-V2 human listening comparison with a human scorecard, which is the phase's actual defining gate. A real, technically-verified V2 mix has been handed to the user; producing a comparable V1-style bake of the same library and running the actual blind comparison is the explicit next step for the user, not for this session.

## Post-Phase-10 performance-recovery checkpoint

- Full regression: **1102 passed**; focused recovery gate: **110 passed**;
  touched-file `ruff check` and `git diff --check`: clean.
- Controlled private real-audio lab: one anonymous compatible pair, fixed
  anchors, 4 bars, plain crossfade plus 12 renderer families, cached stems.
  The audit exposed the old riser/impact output at `0.999954` correlation to
  crossfade; after two-deck build/landing choreography it is `0.853096`.
  Loop shortening is `0.724441`; phrase cut `0.556573`; echo release
  `0.849827`. These distances diagnose execution but do not prove quality.
- Final private set: five anonymous tracks, four handoffs, planned/rendered
  **661.228s / 661.228s**, final **-14.0 LUFS**, peak **-5.52 dBFS**,
  `echo_out / loop_shortening / drum_bridge / riser_impact`.
- Appearance coherence: all four renderer `anchor_shift_sec` values are 0.0;
  middle-track independent airtime is **33.599 / 130.888 / 191.989s** against
  protected establishment windows of roughly 14.9–16.3s.
- Determinism: three complete real-library recovery runs selected the same
  order/families/duration/appearance plan, including runs before and after the
  family-aware Audition spectral correction.
- Private review package:
  `/tmp/djenius_performance_lab/listening_checkpoint/`. Human acceptance is
  explicitly pending; the twice-failed DJ-likeness verdict remains authoritative
  until the user listens to this checkpoint.

## Reference-backed automation reproduction gate

- Human manual-R&D result: F is the strongest reference; C3 is a successful
  DJ-like edit; B8 is an acceptable loop/build/coherent-handoff performance;
  D2 is an acceptable restrained blend. This proves plausible DJ behavior on
  controlled pairs but does not validate autonomous selection.
- Frozen manual hashes: F
  `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`,
  C3 `ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03`,
  B8 `47824cc9b923c708f261c7d3db82e46e2f910fec47b802111bcd26c1c5aa1205`,
  D2 `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586`.
- Four deterministic, explicitly selected templates reproduce the same pairs
  from analysis-derived anchors. Every source/target anchor differs from the
  independently recorded manual anchor by less than 0.1 ms.
- Automated private hashes: AUTO_F
  `13c3691cf81b40467d8adce0c9cf2408206199500554648ef29ae32584ab6f2b`,
  AUTO_C3 `0c89bb5f9024baacdb419556f2fbd8c4a1b60099b13a26a0dcc9738b16426a32`,
  AUTO_B8 `f6ff0d862739e8c0b71993d3fc5ba1b4eb8a73468354d59f2f525ce747c5e3b1`,
  AUTO_D2 `ab2dbd9156eb18b3c450495ffab8b21060841abe430e23d38f7b9340fc532634`.
- Structural evidence: F uses adjacent natural target-master samples; C3,
  B8, and D2 use a shared multichannel target time map. F/C3 tails clear
  before landing, B8's state-continuous tail ends 20 ms before the measured
  incoming vocal, and D2 declares no effect tail. All files are finite stereo
  44.1 kHz PCM24 with no clipped samples.
- Focused template suite: **14 passed**. Complete repository regression:
  **1116 passed in 82.14s**, with only the two existing Typer/Click dependency
  deprecation warnings. Touched-file `ruff check` and `git diff --check` pass.
- Private evidence/output directory:
  `/tmp/djenius_reference_dj_transition/automated/`, including
  `REFERENCE_AUTOMATION_MANIFEST.json`. Metrics are diagnostic only; the gate
  remains manual F/C3/B8/D2 versus AUTO_F/AUTO_C3/AUTO_B8/AUTO_D2 listening.

## Reference-backed cross-pair generalization gate

- The user passed all four same-pair automated reproductions: AUTO_F was best
  and genuinely enjoyable; AUTO_C3 was good with clear DJ work; AUTO_B8 was
  acceptable and well beyond generic AutoDJ behavior; AUTO_D2 was good for
  its restrained role.
- Analysis-only eligibility scanned all **196 ordered pairs per archetype** in
  a 14-track private real library. After self-pair and original-pair exclusion,
  counts `(selected / eligible-not-selected / rejected)` were F `2/60/134`,
  C3 `2/10/184`, B8 `2/3/191`, and D2 `2/9/185`.
- Exactly eight unique new pairs were rendered. All files are stereo 44.1 kHz
  PCM24, finite, and free of clipped samples; a second complete render
  reproduced all eight SHA-256 hashes exactly. Private identities and detailed
  evidence remain in `generalization/GENERALIZATION_MANIFEST.json`.
- Structural checks prove adjacent natural target master for F, one shared
  multichannel target clock for C3/B8/D2, explicit bass ownership and target
  establishment, uninterrupted B8 loop state, and bounded effect tails.
- The new pairs exposed and fixed a sample-quantization defect: B8's hard
  pre-vocal tail endpoint now rounds inward and therefore cannot overrun its
  20 ms margin by nearest-sample rounding.
- Focused suite: **19 passed**. Complete regression: **1121 passed in 82.55s**
  with the same two dependency deprecation warnings. These measurements prove
  deterministic execution and rule enforcement, not perceptual success; the
  eight-file human listening gate is pending.

## Generalization Round 2: eligibility and source entry

- Human labels: B8_01 and C3_01 pass; B8_02 and F_02 are entry-related
  near-passes; F_01 and D2_01 reject; C3_02 is borderline; D2_02 is a
  borderline pass. The labels are recorded in
  `REFERENCE_GENERALIZATION_LABELS.json` and are not ML targets.
- B8_02's old fade began with 9.5782 seconds remaining in an active lyric
  unit and its loop began on active vocals. The controlled replacement moves
  the same-duration source phrase 40 beats earlier: fade on the last 0.3135
  seconds of a phrase, loop in an instrumental gap, then 1.4164 seconds before
  the next vocal. Its target contribution is sample-identical to B8_02.
- AUTO_F completes its recognizable motif about 115 ms before release. Old
  F_02 releases inside a continuing lyric; the replacement moves its source
  phrase 12 beats earlier to a downbeat gap after a self-contained unit while
  retaining the exact target and reset choreography.
- C3_02 versus C3_01: tempo stretch 10.5691%/5.0407%, groove distance
  0.2286/0.0575, source density 0.8529/0.3155, and source-vocal dominance
  -3.688/-10.877 dB relative to master. This is compound eligibility evidence,
  not one local defect, so no C3 rerender was made.
- D2_01 versus D2_02: global harmonic compatibility 0.30/0.70 and shared
  arrangement-density pressure 1.7475/1.4142. D2 now rejects below 0.50
  harmonic compatibility or above 1.65 shared-density pressure.
- Exactly two user-facing fixes were produced: B8
  `2f8dc2e6bfd4c95b97cdcc38a1e7090504af4a4296c6968d9149b08825d3b1b6`
  and F `c54353a189650e6e52e35618e537b10e628cdbd1d05182379bc03ae8dc574430`.
  Both are finite, unclipped stereo 44.1 kHz PCM24 and deterministic.
- Focused suite: **24 passed**; complete regression: **1126 passed in 82.45s**
  with the same two dependency warnings. Human listening remains the gate.

## Constrained autonomous reference-template selection gate

- Human listening passed both Round-2 source-entry fixes. The frozen accepted
  set now contains four manual, four AUTO, and four new-pair references; all
  twelve hashes are durable in `REFERENCE_GENERALIZATION_LABELS.json` and
  were verified unchanged before/after both private selector render runs.
- Eight unseen ordered pairs were fixed before audio rendering using
  analysis-only strata: two material tempo contrasts, two progressive target
  cases, one vocal/stem-edit probe, one restrained-overlap probe, and two
  explicit conflict-pressure probes. Every prior reference/generalization
  ordered pair was excluded.
- Decisions: PAIR_02 F/reset-release (source cue -28 beats); PAIR_03 B8
  (-48 beats); PAIR_04 B8 (-8 beats); PAIR_05 C3 (-36 beats). All selected
  target landings retain their baseline cues. PAIR_01/06/07/08 abstain. No D2
  pair met its entire explicit long-overlap story, so no D2 was forced.
- Render hashes: PAIR_02
  `e196d2d1904dbb3e5d178b12ccd9762fa77fc5aa5d12efcc8f5e1d82d6869f72`,
  PAIR_03
  `746a0e472b6dfd466166fd1e795ffac5f5c45eac482b7d0d708f72c500f80c9b`,
  PAIR_04
  `a7faf8bf62091d3f6d766511ccec6dfb782b443e8f3d8c15d90b179741513fc5`,
  PAIR_05
  `53d3e60cc46f98fc3b330d68f2e255ea4224db9337e6625c376d425f56c5099b`.
  All are finite, unclipped stereo 44.1 kHz PCM24 and reproduced byte-for-byte.
- The private manifest contains every evaluation, rejection count, story
  check, cue rank/shift, instance, provenance, and technical metric. Semantic
  lyric completeness, stem bleed, and exact stem-transient onset remain
  explicitly deferred rather than fabricated.
- Focused suite: **34 passed**; complete regression: **1136 passed in 81.99s**
  with the two existing dependency warnings. These establish deterministic
  decision/execution, not musical quality; blind human listening is the gate.

## Autonomous selector postmortem and counterfactual gate

- Human listening rejected all four rendered choices as passes. Relative
  ordering was PAIR_05 best, then PAIR_04, PAIR_03, and PAIR_02, but none met
  the practical acceptance threshold.
- The untouched baseline selector was replayed blind on four accepted
  generalization pairs. It found B8 for both B8 controls and C3 for C3_01, but
  selected source bars `82/44/91` instead of accepted `93/44/89`, and
  abstained on F_02_FIX instead of selecting accepted source/target bars
  `51/4`. This proves real cue-search/ranking defects independent of the four
  failed pairs.
- Selector-only corrections admit the proven clean F intro pickup, retain an
  equally-safe analysis phrase rather than drifting to an arbitrary hook, and
  recognize the sparse/quiet-boundary C3 case whose frozen stem choreography
  controls raw vocal overlap. The revised replay recovers **4/4 exact
  template/source-bar/target-bar choices**.
- The new second gate is an explicit list of archetype-specific checks, not a
  score. It covers motif completion/boundary/reset space for F; quiet edit
  boundary/stem confidence/groove/harmony/density for C3; motif stability,
  backing, groove/harmony, tail runway, payoff, and bass transfer for B8; and
  sustained tempo/groove/harmony/density/energy/vocal/bass space for D2.
- Re-evaluation at best nearby cues marks PAIR_02-05 all
  `PAIR_TRANSITIONABLE = NO`. PAIR_02 has only an F candidate but its motif is
  not complete at effect onset and target reset space is weak. PAIR_03's best
  B8 cue lacks backing/groove margin. PAIR_04's B8 lacks groove/harmonic
  margin. PAIR_05's only C3 option lacks density/groove/harmonic margin.
- No other frozen archetype clears its own strong floor on any failed pair,
  so **zero counterfactual WAVs** were rendered. This is the requested Case 2:
  pair selection/acceptance, not an alternative-template win.
- The four prior abstentions remain abstentions under the new floor. Detailed
  private identities/evidence are in `POSTMORTEM_DIAGNOSIS.json`; public-safe
  labels and hashes are in `REFERENCE_SELECTOR_LABELS.json`.
- Focused selector/template suite: **40 passed**; broader recipe/technique/
  transition regression: **136 passed**; complete repository regression:
  **1142 passed in 84.58s**, with only the two existing Typer/Click dependency
  warnings. Touched-file ruff and `git diff --check` pass.

## Constrained joint set-director pilot

- Private library: fourteen analyzable tracks. Individual-track reuse was
  unavoidable at this library size, but every prior manual, generalization,
  and blind-test ordered pair was excluded before planning.
- One deterministic four-track path cleared set-flow, pair-transitionability,
  template-acceptance, cue, and establishment gates. Anonymous mean-energy
  trajectory: `.747 -> .745 -> .770 -> .707`; frozen archetypes: `D2 -> F ->
  F`. The repeated F reflects the only hard-qualified edges on that path;
  diversity remained a post-quality preference.
- Continuous output duration: **391.595283 s**, stereo 44.1 kHz PCM24, sample
  peak `.935026`, clipping fraction `0`. Six natural/template joins use 40 ms
  sample-aligned seams; their exact-boundary maximum sample deltas are
  `.072240/.012311/.072921/.071492/.055813/.044374`.
- Transition excerpt durations: **35.477188 / 22.868753 / 29.254240 s**. Each
  is sliced from the final set and contains two source bars before the move
  and four target bars after landing.
- All twelve accepted reference WAV hashes were verified unchanged before the
  final render. Focused joint/reference suite: **45 passed**. Complete
  regression: **1147 passed in 83.79s**, with the same two dependency warnings.
- This benchmark proves deterministic joint planning, hard rejection,
  continuous cursor/tail handling, finite output, and absence of clipping. It
  does **not** prove DJ quality, transition appropriateness, or set-flow
  success; those claims remain pending human listening of the one pilot.
