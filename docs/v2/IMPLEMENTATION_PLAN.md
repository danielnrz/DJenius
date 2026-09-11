# DJenius V2 Implementation Plan

## Product target
DJenius V2 is a local autonomous DJ performance engine. The architectural target is set direction + richer track/section intelligence + multi-action performance recipes + candidate generation/audition + deterministic rendering + performance memory + user feedback.

## Phase status
| Phase | Scope | Gate | Status |
|---|---|---|---|
| 0 | Freeze and benchmark V1 | V1 baseline documented/reproducible | PASS |
| 1 | Analysis V2 | unit + synthetic + real-track validation | PASS |
| 2 | Performance Timeline / Recipe DSL | deterministic serialization/rendering | IN PROGRESS |
| 3 | Core DJ technique engine | synthetic + real-audio technique gates | PENDING |
| 4 | Groove / sampler layer | beat-aligned, safe added material | PENDING |
| 5 | Candidate composer | 3-8 meaningfully different feasible recipes | PENDING |
| 6 | Audition Lab | known bad candidates rank below good references | PENDING |
| 7 | Set Director V2 | planned sets beat shuffled baselines | PENDING |
| 8 | UI V2 | inspect/preview/override performance | PENDING |
| 9 | Personalization | feedback changes selection predictably | PENDING |
| 10 | Certification | automated + private + blind V1/V2 listening | PENDING |

## Phase 1 tasks
- Preserve all V1 fields and behavior; add a backward-compatible V2 analysis layer.
- Add explicit beat positions in bars, tempo hypotheses, local tempo zones, phrase confidence profiles, richer section profiles, groove descriptors, vocal activity, and typed cue candidates.
- Keep decisions in musical time while seconds remain the rendering coordinate.
- Add synthetic controlled tests for regular tempo, tempo changes, section/cue bounds, groove descriptors, and serialization.
- Re-analyze private real tracks without committing track names/audio and inspect numerical invariants.
- Run full V1 regression suite before Phase 1 is accepted.

## Phase gates
Every substantial phase: targeted tests, full regression where appropriate, private real-audio validation, Git diff/privacy review, docs update, coherent commit, push branch.

## Human listening gate
No merge to master until serious V2 candidates are rendered locally and the user completes the blind listening gate described in DJENIUS_V2_RESEARCH_SPEC.md.
