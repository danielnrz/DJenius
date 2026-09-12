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
| 4 | Groove / sampler layer | beat-aligned, safe added material | NEXT |
| 5 | Candidate composer | 3-8 meaningfully different feasible recipes | PENDING |
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

## Phase 4 - Groove / Sampler Layer
Build deterministic added-performance material in musical time without introducing automatic selection policy.

Required capabilities:
- typed one-shot/generated/pattern events with beat/bar position, duration, gain/envelope, owner IDs, deterministic seed where applicable, provenance, and bounds;
- procedural kick, snare, clap, closed/open hats, percussion overlays, short fills, noise riser, downlifter, impact, and an optional locally generated reverse-cymbal/sweep equivalent;
- quarter/eighth/sixteenth-note pattern sequencing and musical-time quantization;
- recipe/compiler integration rather than hidden renderer behavior;
- deterministic output, finite samples, overlap/peak safety, exact placement, stereo/mono support, invalid-parameter rejection, reproducible seeds, non-silence checks, and serialization/provenance coverage.

Phase 4 is a capability layer only. Candidate Composer / Set Director later decides when percussion, fills, risers, impacts, or other additions are musically appropriate. Do not add random automatic triggering.

## Phase gates
Every substantial phase: targeted tests, full regression where appropriate, private real-audio validation, Git diff/privacy review, docs update, coherent commit, push branch.

Phase 4 additionally requires synthetic render validation and short private real-audio previews proving percussion synchronization, fill landing, riser/impact landing, bounded loudness, and no repeated-event drift.

## Human listening gate
No merge to master until serious V2 candidates are rendered locally and the user completes the blind listening gate described in `DJENIUS_V2_RESEARCH_SPEC.md`.
