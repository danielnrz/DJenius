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
| 6 | Audition Lab | known bad candidates rank below good references | PENDING |
| 7 | Set Director V2 | planned sets beat shuffled baselines | PENDING |
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

## Phase gates
Every substantial phase: targeted tests, full regression where appropriate, private real-audio validation, Git diff/privacy review, docs update, coherent commit, push branch.

Phase 4 additionally requires synthetic render validation and short private real-audio previews proving percussion synchronization, fill landing, riser/impact landing, bounded loudness, and no repeated-event drift.

## Human listening gate
No merge to master until serious V2 candidates are rendered locally and the user completes the blind listening gate described in `DJENIUS_V2_RESEARCH_SPEC.md`.
