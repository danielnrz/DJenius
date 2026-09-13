# DJenius V2 Implementation Plan

## Product target
DJenius V2 is a local autonomous DJ performance engine. The architectural target is set direction + richer track/section intelligence + multi-action performance recipes + candidate generation/audition + deterministic rendering + performance memory + user feedback.

## Phase status
| Phase | Scope | Gate | Status |
|---|---|---|---|
| 0 | Freeze and benchmark V1 | V1 baseline documented/reproducible | PASS |
| 1 | Analysis V2 | unit + synthetic + real-track validation | PASS |
| 2 | Performance Timeline / Recipe DSL | deterministic serialization/rendering | PASS |
| 3 | Core DJ technique engine | synthetic + real-audio technique gates | PASS |
| 4 | Groove / sampler layer | beat-aligned, safe added material | PASS |
| 5 | Candidate composer | 3-8 meaningfully different feasible recipes | PASS |
| 6 | Audition Lab | known bad candidates rank below good references | PASS |
| 7 | Set Director V2 | planned sets beat shuffled baselines | PASS |
| 8 | UI V2 | inspect/preview/override performance | PENDING |
| 9 | Personalization | feedback changes selection predictably | PENDING |
| 10 | Certification | automated + private + blind V1/V2 listening | PENDING |

## Phase 3 gate result
- Twelve required technique families are implemented and renderer-reachable: EQ blend, bass swap, filter blend, phrase cut, echo out/release, reverb wash, loop transition, loop shortening, drum overlay, riser+impact, tempo reset, and stem handoff.
- Dedicated suite: **40 passed**; expanded renderer/technique gate: **144 passed**; complete regression: **928 passed**.
- Direct `LocalAppService` integration verifies stem discovery/loading, real stem DSP for bass swap/stem handoff, target-drum preparation, and explicit invalid/missing-stem fallback.
- Private real-audio smoke validation reached all 12 families; no private media or metadata enters Git.

## Phase 4 - Groove / Sampler Layer - COMPLETE
Build deterministic added-performance material in musical time without introducing automatic selection policy.

Required capabilities:
- typed one-shot/generated/pattern events with beat/bar position, duration, gain/envelope, owner IDs, deterministic seed where applicable, provenance, and bounds;
- procedural kick, snare, clap, closed/open hats, percussion overlays, short fills, noise riser, downlifter, impact, and an optional locally generated reverse-cymbal/sweep equivalent;
- quarter/eighth/sixteenth-note pattern sequencing and musical-time quantization;
- recipe/compiler integration rather than hidden renderer behavior;
- deterministic output, finite samples, overlap/peak safety, exact placement, stereo/mono support, invalid-parameter rejection, reproducible seeds, non-silence checks, and serialization/provenance coverage.

Phase 4 is a capability layer only. Candidate Composer / Set Director later decides when percussion, fills, risers, impacts, or other additions are musically appropriate. Do not add random automatic triggering.

### Phase 4 gate result
- Dedicated suite: **58 passed**; frozen Phase 2/3 gate: **72 passed**; broad targeted renderer/provenance/application gate: **208 passed**; complete regression: **986 passed** with two Typer/Click dependency deprecation warnings and no async timeout failures.
- Five anonymized private real-audio scenarios passed: percussion bridge, drum fill before landing, riser+impact, downlifter reset, and offbeat-hats percussion. All had finite duration-correct output, zero clipping fraction, audible/bounded added layers, complete ownership/provenance, and clean provenance audit.
- Phase 3 combined `riser_impact` remains creative-FX owned. Phase 4 discrete riser/impact is groove/sample-layer owned. Duplicate event IDs, provenance count mismatches, and ownership conflicts fail closed.
- Quarter/eighth/sixteenth scheduling, deterministic seeds, DC-offset protection, and the backward-compatible empty sample-layer path are validated.
- Reverse sweep/cymbal is synthetically/provenance validated but was not part of the five real-audio smoke scenarios.

## Phase 5 - Candidate Composer
Generate a small deterministic set of feasible, meaningfully different transition recipes for each handoff; do not rank them by perceived quality.

Required architecture/gate:
- typed `TransitionCandidate`-style representation with deterministic candidate identity, intent, constraints, diagnostics, recipe, family/role, duration/complexity, requirements, feasibility/rejection diagnostics, provenance, and deterministic generation reason;
- use Phase 1 BPM/confidence, half/double-time hypotheses, bars/phrases/sections/confidence, energy/groove/vocal activity, cue candidates, stem availability, and boundaries, plus Phase 2/3/4 capabilities;
- enforce feasibility before candidate creation for overlap, phrase/downbeat anchors, bounds, loops, riser lead time, stems, tempo reset, and groove/sample-layer needs;
- normally produce **3-8** candidates with family-level diversity rather than parameter-near-duplicates;
- consider EQ blend, bass swap, filter blend, phrase cut, echo out, loop transition/shortening, riser+impact, drum/percussion bridge, tempo reset, and stem handoff only when context permits;
- identical analysis + set context + config + seed must yield the same ordered candidate set;
- every candidate carries a human-readable explanation/reason codes, but no Audition-Lab quality score;
- dedicated synthetic fixtures cover easy same-BPM, moderate/large tempo differences, vocal-heavy/instrumental overlaps, stem-rich/no-stem, strong drop, weak phrase confidence, and short boundaries;
- acceptance requires candidate serialization/IDs/order, bounds/phrase safety, eligibility/requirements, count/diversity, no impossible generation, changed-context sensitivity, candidate recipe compilation, anonymized private real-pair smoke, full regression, privacy audit, docs, commit, and push.

### Phase 5 gate result
- Dedicated Candidate Composer suite: **40 passed in 0.42s**. Frozen Phase 2/3/4/5 gate: **170 passed in 2.09s**. Broad V2 analysis/recipe/technique/groove/candidate/application/model/transition/renderer gate: **267 passed in 6.16s**. Complete regression: **1026 passed in 27.90s** with **2 existing Typer/Click dependency deprecation warnings** and no asynchronous timeout failures.
- Candidate identity/order are deterministic. Feasibility is checked before admission, and every accepted recipe passes the compiler gate. Family-level diversity is preferred; the candidate floor is a preference only and never permission to violate hard feasibility. If hard feasibility prevents the configured floor, diagnostics report `candidate_floor_unmet_due_to_hard_feasibility`.
- Half/double-time handling is confidence-gated. A non-primary relation must also be sufficiently close and have hypothesis confidence **>= 0.55** before it can suppress tempo-reset eligibility. Focused tests cover below, exactly at, and above the threshold.
- Technique memory is soft-defer. Recent feasible families are withheld while enough non-recent alternatives exist, then deterministically reintroduced only when required for the candidate floor, with `recent_repeat_required_for_candidate_floor` and provenance `repeat_allowed_to_meet_candidate_floor`. Hard-infeasible recent families are never reintroduced.
- Six anonymized private real handoffs produced **8 / 7 / 3 / 4 / 7 / 4** accepted candidates (**33 total**), and **33/33 compiled successfully**. Candidate sets varied by context and did not always hit the cap. Private identities and analyses remain outside Git under `/tmp/djenius_phase5_smoke`.
- Phase 5 performs **no perceptual ranking**. It generates, validates, and explains only. Phase 6 Audition Lab owns preview rendering, measurement, hard rejection, ranking, and one-handoff selection.

## Phase 6 - Audition Lab
Render short bounded previews of feasible candidates, measure them with transparent deterministic metrics, hard-reject technically invalid renders, rank surviving rendered performances, and select the best candidate for one handoff.

Required architecture/gate:
- configurable preview context around the handoff rather than full-set rendering or one blindly fixed duration; every preview binds candidate ID, recipe ID, internal source/target identity, exact bounds/duration, sample rate/channels, render configuration, and renderer provenance;
- typed audition results separating render state, hard rejection/failure, raw technical/beat/spectral/vocal/energy/FX measurements, normalized components, deterministic score, rank, decision reason, and provenance;
- hard technical invalidity (NaN/Inf, invalid duration/range/bounds/stems/provenance, catastrophic silence, unsafe clipping/peak, severe discontinuity/render failure, unstable stretch where detectable) is rejected before soft ranking;
- initial ranking uses only metrics actually supported by current analysis/rendered audio, with small configurable documented weights and stable tie-breaking. It is a heuristic automated score, not a claim of human perceptual truth;
- energy/FX/vocal interpretation is technique-aware: deliberate breakdowns, intentional vocal interaction, or inapplicable FX metrics must not be blindly penalized; unsupported harmonic precision must be explicitly deferred rather than fabricated;
- acceptance requires controlled synthetic known-good vs intentionally damaged ordering across multiple failure modes, useful monotonicity tests where possible, deterministic preview/metrics/rejection/score/order, candidate/recipe/provenance binding, all-rejected and single-survivor behavior, anonymized private real-music smoke, complete regression, privacy gate, durable docs, commit, and push;
- defining gate: **known bad candidates rank below good references**. Phase 6 may select one handoff winner, but must not redesign full-set ordering/storytelling; that remains Phase 7 Set Director V2.

### Phase 6 gate result
- Dedicated Audition Lab suite: **36 passed in 2.92s**; broad targeted V2/application/renderer/provenance gate: **315 passed in 7.90s**; complete repository regression: **1062 passed in 25.28s** with the same two Typer/Click dependency warnings and no async timeout failures.
- Four anonymized private handoffs rendered **8 / 7 / 3 / 4** candidates. Hard rejections were **0 / 4 / 0 / 2**, survivors **8 / 3 / 3 / 2**, and deterministic winners were **loop_shortening / drum_bridge / stem_handoff / stem_handoff**.
- One exact real-handoff rerun reproduced candidate IDs, preview bounds/audio hashes, metrics, rejection decisions, scores, ranking, and winner.
- Controlled real-preview damage passed the defining gate: 100 ms beat shift and severe LF collision scored below the clean reference; clipping, severe discontinuity, catastrophic silence, and excessive FX-tail overgain were hard rejected.
- A real-smoke review found two implementation defects before freeze: whole-preview peak gating incorrectly blamed pre-existing mastered context, and a fractional-BPM generated event could round one sample past the transition buffer. Candidate peak/silence safety is now transition-scoped with whole-preview audit fields, and only a one-sample terminal event residue is trimmed with explicit provenance.
- Active score components are normalized and configurable; inapplicable beat/FX metrics are omitted from the active denominator. Certified true peak, isolated-kick alignment, reliable overlap-local harmonic quality, vocal intelligibility, and stem bleed remain explicitly deferred.

## Phase gates
Every substantial phase: targeted tests, full regression where appropriate, private real-audio validation, Git diff/privacy review, docs update, coherent commit, push branch.

Phase 4 additionally requires synthetic render validation and short private real-audio previews proving percussion synchronization, fill landing, riser/impact landing, bounded loudness, and no repeated-event drift.

## Phase 7 - Set Director V2
Plan the whole-set journey above individual handoffs: track order, energy arc, BPM journey, technique diversity, artist/vocal pacing, and reset budget, using bounded/cached Phase 5+6 audition rather than exhaustive pairwise rendering.

Required architecture/gate:
- explicit set arcs (smooth, warm-up-to-peak, peak-time, wave, open-format) with a deterministic per-position target energy curve;
- combinatorial cost controlled by a fixed pipeline: cheap audio-free shortlist -> Phase 5 candidate generation -> bounded Phase 6 audition (capped candidates per edge, hard compute ceiling) -> cached `HandoffSummary`, so repeated planning or many shuffled baselines do not re-render identical edges;
- a deterministic beam search over track order with no randomness in ordering decisions (seed only salts Phase 5 candidate-ID hashing), stable lexicographic tie-breaking, and a real (not merely reported) reset-tempo budget that actually gates candidate feasibility once spent;
- a transparent, decomposed, non-circular objective: handoff quality, energy-arc fit, BPM-journey fit, vocal pacing, groove continuity/contrast, technique diversity, artist spacing, duration fit, and reset budget, each independently inspectable in the plan's `component_totals`;
- independent validation metrics (`measure_set_quality`) computed without reference to the internal weighted objective, used to compare a planned order against many seeded shuffled baselines of the same track pool on energy-arc error, peak-placement error, BPM-jump statistics, vocal/artist pacing, technique repetition, viable-audition-edge rate, mean selected-audition score, and hard-rejection rate;
- defining gate: **planned sets beat shuffled baselines** on the majority of these independent metrics, evaluated as many deterministic seeded shuffles rather than one cherry-picked shuffle.

### Phase 7 gate result
- Dedicated Set Director suite: **17 passed in ~24s**. Broad V2 gate (analysis/recipe/technique/groove/candidate/audition/set-director/renderer/planner/scorer/model): **326 passed in ~31s**. Complete repository regression: **1079 passed in ~44s** with the same pre-existing Typer/Click dependency deprecation warnings and no async timeout failures.
- The dedicated suite includes a controlled "locally tempting but globally bad path" test: a next track that looks like the best possible pairing on paper (near-identical BPM/key) but is actually over-driven/clipped loses to a slightly less "perfect"-looking pairing that survives real audition, proving the search is driven by actual bounded audition evidence rather than the cheap compatibility shortlist alone.
- Three anonymized real-track set intents (warm-up-to-peak, smooth, open-format) were planned from a 12-track anonymized real library (`/tmp/djenius_phase7_smoke`, never committed) and each compared against 12 seeded shuffled baselines of the same pool. The planned order beat the shuffled baseline on energy-arc error, peak-placement error, artist spacing, and viable-audition-edge rate in every one of the three arcs; it also beat it on mean selected-audition score for two of three arcs (the third was a near-exact statistical tie, consistent with that metric's documented weak-discriminator caveat below).
- Known limitation surfaced by the real gate: with only a 12-track library, one arc's forced-length path included a handoff where every audited candidate hard-rejected (0 survivors); Set Director truthfully reports this as `selected_family: None` / `handoff_quality: 0` rather than fabricating a candidate, but currently has no backtracking/path-abandonment escape hatch to avoid such a forced handoff when no better local option remains.
- `mean_selected_audition_score` is an intentionally weak discriminator whenever a library holds BPM/key/vocal properties roughly constant (as one dedicated synthetic test does on purpose, to isolate energy-arc placement): different arc positions steer Phase 5 toward different technique families with genuinely different intrinsic audition scores, independent of whether the ordering itself is good or bad.
- Privacy boundary: private track identities, raw analyses, source audio, and `/tmp/djenius_phase7_smoke` artifacts remain outside Git; only anonymous `TRACK_NN` / `SET_A|B|C` labels and aggregate metrics are recorded here.

## Human listening gate
No merge to master until serious V2 candidates are rendered locally and the user completes the blind listening gate described in `DJENIUS_V2_RESEARCH_SPEC.md`.
