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
