# DJenius V2 Active Handoff

## REFERENCE-BACKED AUTONOMOUS SELECTION GATE — READY FOR BLIND LISTENING

2026-09-15. Human listening passed both Round 2 fixes:

- `GEN_B8_02_FIX` = `PASS`; phrase-ending/instrumental-gap placement fixed
  the major source-entry problem and restored clearly audible DJ work.
- `GEN_F_02_FIX` = `PASS`; the self-contained vocal unit made the F behavior
  work substantially better.

The practical gate is musical acceptance, not endless polish. Freeze these
two files plus `GEN_B8_01`, `GEN_C3_01`, all four AUTO references, and their
four manual references. The active task is a constrained, explainable
reference-backed selector over exactly the four proven archetypes plus
mandatory `NO_SUITABLE_TEMPLATE`. Cue placement is part of selection. Evaluate
exactly eight unseen private pairs, render at most one chosen transition per
pair, preserve all candidate reasoning in a private manifest, and stop for
blind human listening. Candidate Composer, Audition Lab, Set Director, UI,
personalization, new families, and full mixes remain prohibited.

Implementation milestone: `core/reference_selector.py` now evaluates all four
approved templates, searches bounded nearby source/target downbeat windows,
retains every cue rejection, requires a named template-specific musical-story
contract, and returns either one instance or `NO_SUITABLE_TEMPLATE`. It does
not use the legacy aggregate pair fit value and has no imports from Candidate
Composer, Audition Lab, or Set Director. Source evidence includes section,
vocal completion/gaps, motif descriptors, transient/energy context; target
evidence includes cue/phrase/section cleanliness, vocal/drum/bass onset
proxies, density, and establishment; pair evidence includes tempo, groove,
harmony, energy, stems, and explicit overlap risks/deferred facts.

The eight-pair private panel was fixed before audio rendering using five
analysis-only strata and excludes every prior reference/generalization ordered
pair. Current deterministic decisions are four renders and four abstentions:

- `PAIR_01`: abstain.
- `PAIR_02`: F/reset-release; source launch shifted -28 beats.
- `PAIR_03`: B8/loop-build; source launch shifted -48 beats; target baseline.
- `PAIR_04`: B8/loop-build; source launch shifted -8 beats; target baseline.
- `PAIR_05`: C3/stem-echo; source launch shifted -36 beats; target baseline.
- `PAIR_06`, `PAIR_07`, `PAIR_08`: abstain.

No D2 render was forced: the restrained probe lacks a usable local source
window, and the other seven pairs do not satisfy D2's complete long-overlap
contract. The four rendered WAVs are finite, unclipped stereo 44.1 kHz PCM24;
the accepted listening set was hash-verified unchanged before and after both
render passes. Exact private outputs:

- `PAIR_02.wav` — F/reset-release —
  `e196d2d1904dbb3e5d178b12ccd9762fa77fc5aa5d12efcc8f5e1d82d6869f72`
- `PAIR_03.wav` — B8/loop-build —
  `746a0e472b6dfd466166fd1e795ffac5f5c45eac482b7d0d708f72c500f80c9b`
- `PAIR_04.wav` — B8/loop-build —
  `a7faf8bf62091d3f6d766511ccec6dfb782b443e8f3d8c15d90b179741513fc5`
- `PAIR_05.wav` — C3/stem-echo —
  `53d3e60cc46f98fc3b330d68f2e255ea4224db9337e6625c376d425f56c5099b`

The private manifest is
`/tmp/djenius_reference_dj_transition/autonomous_selection/AUTONOMOUS_SELECTION_MANIFEST.json`
(SHA-256 `6aff71a2cee3ebbb2e6ae109be88c2f601ed6826a97a6aa71aa7a2f82289f159`).
It contains identities, all four evaluations per pair, every rejection and
story-rule check, selected cues/shifts, choreography, provenance, and technical
checks. Focused reference-template/selector tests: **34 passed**. Complete
regression: **1136 passed in 81.99s**, with the two existing Typer/Click
deprecation warnings. Touched-file `ruff check` passes.

**STOP/GATE:** blind-listen only to `PAIR_02` through `PAIR_05`, then judge the
four rendered choices and the four abstentions. Do not proceed to Set Director,
Candidate Composer, Audition Lab, UI, personalization, new families, or full
mixes until the user passes this gate.

Validated implementation checkpoint: commit `6e3f2b8` ("Add constrained
reference transition selector"), pushed to
`origin/v2-professional-autonomous-dj`. This handoff finalization follows as a
docs-only commit; resolve the current tip from Git. Apart from the pre-existing
untracked `.claude/` directory, the worktree is clean.

## GENERALIZATION ROUND 2 — PASSED

2026-09-15. The user completed the first eight-render listening gate. Human
labels are authoritative engineering evidence, not machine-learning targets:

- `GEN_B8_01` = `PASS`; preserve unchanged as a successful new-pair reference.
- `GEN_B8_02` = `NEAR_PASS_SOURCE_ENTRY`; effect and target connection worked,
  but the source-to-effect entry was not smooth and may interrupt singing.
- `GEN_C3_01` = `PASS`; preserve unchanged as successful/near-successful.
- `GEN_C3_02` = `BORDERLINE`; diagnose against C3_01 before any rerender.
- `GEN_D2_01` = `REJECT`; derive the eligibility condition that should have
  refused this pair/template combination.
- `GEN_D2_02` = `BORDERLINE_PASS`; preserve rather than making it flashy.
- `GEN_F_01` = `REJECT_EFFECT_ENTRY`; onset was out of place and too sudden.
- `GEN_F_02` = `NEAR_PASS_EFFECT_ENTRY`; better than F_01 but has the same
  abrupt-onset defect.

Residual forensics confirms that source-entry context, rather than the fixed
target-side handoff, caused the B8_02 failure. Its old source fade began with
9.5782 seconds remaining in an active lyric unit and crossed a verse-to-outro
boundary; its loop also entered on active vocals. B8_01 instead sits in a
stable drop/repeated-hook context. The B8 fix moves the same-duration source
phrase 40 beats earlier: the fade begins on the final 0.3135 seconds of a
vocal phrase, the loop begins in instrumental space, and there is 1.4164
seconds of runway before the next vocal. A localized equal-power dry-to-loop
handoff over bars 4.00-4.22 removes the source-entry hole. Every target anchor,
component sample, gain, reveal, shared time map, tail, and establishment
parameter is unchanged; the successful B8_01/AUTO_B8 envelope is untouched.

F_01 and F_02 both released inside continuing vocal material. AUTO_F's
recognizable motif completes about 115 ms before release; old F_02 instead
released at high vocal level inside an incomplete unit. The F fix moves only
the four-bar source phrase 12 beats earlier to a downbeat gap after a
self-contained unit. Its target anchors, adjacent natural target samples,
gain, reset envelope, and choreography are unchanged.

C3_02 has no single local renderer defect. Compared with passing C3_01 it has
10.5691% versus 5.0407% stretch, groove distance 0.2286 versus 0.0575, source
arrangement density 0.8529 versus 0.3155, and a much more dominant source
vocal (-3.688 versus -10.877 dB relative to master). This compounds into a
borderline placement, so no C3 fix was fabricated. D2_01 likewise becomes an
explicit pre-render reject: global harmonic compatibility is 0.30 and shared
arrangement-density pressure is 1.7475, versus 0.70/1.4142 for borderline-pass
D2_02. No D2 render was made.

Exactly two new user-facing files are ready in
`/tmp/djenius_reference_dj_transition/generalization/`:

- `GEN_B8_02_FIX.wav` — SHA-256
  `2f8dc2e6bfd4c95b97cdcc38a1e7090504af4a4296c6968d9149b08825d3b1b6`
- `GEN_F_02_FIX.wav` — SHA-256
  `c54353a189650e6e52e35618e537b10e628cdbd1d05182379bc03ae8dc574430`

Both are finite, unclipped, stereo 44.1 kHz PCM24 and reproduced with the
same hashes after final metadata changes. `GENERALIZATION_MANIFEST.json`
contains the private detailed comparison; public-safe human labels, diagnoses,
rules, and hashes are durable in `REFERENCE_GENERALIZATION_LABELS.json`.
Focused tests: **24 passed**. Complete repository regression: **1126 passed in
82.45s**, with the two existing Typer/Click deprecation warnings. Touched-file
`ruff check` and `git diff --check` pass.

Validated implementation checkpoint: commit `3b1d882` ("Refine reference
template entry eligibility"), pushed to
`origin/v2-professional-autonomous-dj`. This handoff finalization follows as a
docs-only commit; resolve the current tip from Git. Apart from the pre-existing
untracked `.claude/` directory, the checkpoint worktree is clean.

Human result: both fixes were much better and passed the practical acceptance
threshold. B8's phrase-ending/instrumental-gap placement repaired the major
problem; F's self-contained vocal unit made the repeat behavior work far
better. Their hashes remain frozen in the active selector gate above.

## CROSS-PAIR GENERALIZATION GATE — READY FOR HUMAN LISTENING

2026-09-15. The user passed the first human reference-automation gate:
`AUTO_F` was the best and genuinely enjoyable; `AUTO_C3` made good, clearly
audible DJ work; `AUTO_B8` was acceptable and substantially beyond AutoDJ-like
behavior; `AUTO_D2` was good for its restrained role. The explicit template
layer therefore reproduces approved behavior without collapsing into generic
crossfades. The eight manual/automated references remain frozen at the hashes
below and were verified unchanged after this gate.

Validated generalization implementation checkpoint: commit
`2c6574483ed52dbc40ac19704f3f2b74d7bcef57` ("Add reference template
generalization gate"), pushed to `origin/v2-professional-autonomous-dj` with
local and remote HEAD equal immediately afterward. A docs-only handoff
finalization follows that commit; resolve the current tip from Git. The only
uncommitted worktree item after finalization is the pre-existing `.claude/`
directory, left untouched.

Exactly two new real private pairs per archetype are rendered in
`/tmp/djenius_reference_dj_transition/generalization/`. The directory contains
only the requested eight stereo 44.1 kHz PCM24 WAVs and
`GENERALIZATION_MANIFEST.json`. The manifest retains private source/target
identity, analysis-derived cues, BPM/stretch/key/energy/vocal/drum/bass/stem
evidence, instantiated choreography, adapted parameters, technical checks,
all rejected candidate pairs and reasons, and eligible-but-not-selected pairs.
Audition Lab was not invoked and none of these renders is claimed successful
before human listening.

| Render | Anonymous private pair | Selection evidence | SHA-256 |
|---|---|---|---|
| `GEN_F_01.wav` | `PRIVATE_12 -> PRIVATE_04` | 86.1 -> 117.5 BPM reset, relative 10A/10B keys, vocal hook into vocal-free pickup and +0.376 landing-energy lift | `81e2d58f6be6666089c19d3eaa847b38a89243a26d056822037f872cbef5e626` |
| `GEN_F_02.wav` | `PRIVATE_07 -> PRIVATE_12` | recognizable 123 -> 86.1 BPM hook/reset, adjacent 9A/10A keys, sparse pickup and +0.289 landing lift | `e926ca09eb9645d1f3e8a9ede0f335a2e90e17ce3942c9e2d9d4967e547f7247` |
| `GEN_C3_01.wav` | `PRIVATE_02 -> PRIVATE_03` | 5.04% tempo fit, groove distance 0.0575, capturable late vocal and active target drums | `2d019af332416fa5d62143daec7072f9f33f260b91d02e01e87db492258a55a9` |
| `GEN_C3_02.wav` | `PRIVATE_01 -> PRIVATE_03` | dense late source capture, strong target drum/drop phrase; 10.57% tempo change is retained as a caution | `0f313c8b42ac3587953fbe6ac65530f0d9e113c94a0ca2d33caa4ba7c35d7718` |
| `GEN_B8_01.wav` | `PRIVATE_03 -> PRIVATE_02` | 5.04% tempo fit, groove distance 0.0575, active backing motif, stable landing bass rise and 0.627 s vocal runway | `3871f3ae02b5fe4884b884a8218b22a7dd76de4fa668f9a8e22d105cd4809e4b` |
| `GEN_B8_02.wav` | `PRIVATE_07 -> PRIVATE_02` | compatible 9A/10B relation, active backing motif, stable drums/bass and 0.627 s vocal runway | `30949ccbed4236981f1efe331bd07aaba87f08a67d6916bf7944cb82d3f2ef58` |
| `GEN_D2_01.wav` | `PRIVATE_10 -> PRIVATE_01` | exact 136 BPM, groove distance 0.1408, close section energy and active target drums/bass; key risk is explicit | `7129d81e7009bb32652280dd8730f75c11e2bc893cc2e5bb999c6fb49db86c1e` |
| `GEN_D2_02.wav` | `PRIVATE_04 -> PRIVATE_07` | 4.47% tempo adjustment, compatible 10B/9A keys, close energy and target drum/bass support | `8b03200b8df27db82c5c6219280704bdfa5e04d959ad2dbb6170ef59112ff77d` |

The exhaustive analysis-only scan considered all 196 ordered candidates per
archetype in the 14-track private library. Counts `(selected / eligible but
not selected / rejected)` are F `2/60/134`, C3 `2/10/184`, B8 `2/3/191`, and
D2 `2/9/185`; same-track and original-reference pairs are explicit rejects.
This is feasibility/context evidence, not an automated listening score.

The new-pair run exposed one concrete renderer boundary defect: nearest-sample
rounding could place a B8 tail a few microseconds beyond its hard 20 ms
pre-vocal margin. The endpoint now rounds inward with `floor`, so quantization
can only shorten the tail. The source loop remains state-continuous and all
beatmatched targets still use a single shared multichannel time map. Focused
tests: **19 passed**. Complete repository regression: **1121 passed in
82.55s**, with the two pre-existing Typer/Click deprecation warnings. Touched
Python `ruff check` passes; the eight renders reproduced the same hashes on a
second complete run.

**STOP/GATE:** the user must listen to all eight `GEN_*` renders. Do not tune
them, add pairs/families, let Audition Lab select, integrate Candidate Composer
or Set Director, touch UI/personalization, or make full mixes. The next
question is only whether each approved choreography generalizes to these new
pairs as intentional DJ work.

## REFERENCE-BACKED AUTOMATION — SAME-PAIR RENDERS READY FOR HUMAN LISTENING
2026-09-14. The user judged B8 substantially better than the earlier B-series
and acceptable. Manual plausibility is no longer the blocking question. Do not
continue polishing B8. Freeze these four private files as the current
human-approved/accepted reference set:

Validated implementation checkpoint: commit
`5571b573ae9c8e6e17333c9a387bb0d253271517` ("Add reference-backed DJ
performance templates"), pushed to `origin/v2-professional-autonomous-dj`;
local and remote HEAD matched immediately after push. The only remaining
worktree item is the pre-existing untracked `.claude/` directory, left
untouched. A docs-only handoff finalization follows that implementation commit;
resolve the current tip from Git.

- `REFERENCE_F.wav` — strongest; SHA-256
  `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`
- `REFERENCE_C3.wav` — successful DJ-like edit; SHA-256
  `ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03`
- `B8_RESIDUAL_FIX.wav` — acceptable loop/build/handoff; SHA-256
  `47824cc9b923c708f261c7d3db82e46e2f910fec47b802111bcd26c1c5aa1205`
- `REFERENCE_D2.wav` — acceptable restrained blend; SHA-256
  `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586`

The reference-backed layer is implemented without touching autonomous
selection. `core/reference_templates.py` maps an explicitly requested
archetype plus source/target `TrackAnalysis` into deterministic analysis-
derived anchors, a complete bar-relative `PerformanceRecipe`, eligibility
evidence, and an executable choreography contract.
`audio/reference_template_renderer.py` executes only those selected templates
and permanently retains the structural fixes: target master/stems and runway/
body share one multichannel time map; source loop state crossing landing is
continuous; tail endpoints are explicit and checked.

The four private same-pair reproductions are ready:

- `automated/AUTO_F.wav` — SHA-256
  `13c3691cf81b40467d8adce0c9cf2408206199500554648ef29ae32584ab6f2b`
- `automated/AUTO_C3.wav` — SHA-256
  `0c89bb5f9024baacdb419556f2fbd8c4a1b60099b13a26a0dcc9738b16426a32`
- `automated/AUTO_B8.wav` — SHA-256
  `f6ff0d862739e8c0b71993d3fc5ba1b4eb8a73468354d59f2f525ce747c5e3b1`
- `automated/AUTO_D2.wav` — SHA-256
  `ab2dbd9156eb18b3c450495ffab8b21060841abe430e23d38f7b9340fc532634`

All are stereo 44.1 kHz PCM24. Every automated source/target cue reproduces
the corresponding frozen manual cue within 0.1 ms. F uses adjacent natural
target master; C3/B8/D2 report one shared FFmpeg multichannel target clock.
F's final echo clears 41.2 ms before landing, C3's clears 239.2 ms before,
B8's uninterrupted rhythmic/airy tail clears 20 ms before the measured target
vocal, and D2 declares no FX tail. The four frozen manual hashes were verified
unchanged after rendering.

Focused tests: **14 passed**. Complete repository regression: **1116 passed**
in 82.14 seconds, with only the two pre-existing Typer/Click dependency
deprecation warnings. Touched-file `ruff check` and `git diff --check` pass.
Machine-readable evidence is in private
`automated/REFERENCE_AUTOMATION_MANIFEST.json`; the full archetype contract is
in `REFERENCE_BACKED_ARCHETYPES.md`.

**STOP/GATE:** the user must compare manual F vs `AUTO_F`, manual C3 vs
`AUTO_C3`, manual B8 vs `AUTO_B8`, and manual D2 vs `AUTO_D2`. Numerical
similarity is not acceptance. If a reproduction is substantially worse,
change only the reference template/instantiation renderer. Do not test new
pairs, expose these templates to Candidate Composer, alter Audition Lab or Set
Director, touch UI, create new families, or render full mixes before approval.

## B8 RESIDUAL FIX — READY FOR B7-vs-B8 HUMAN LISTENING
2026-09-14. Residual-error forensics is complete. Exactly one new user-facing
render exists:

- private file: `/tmp/djenius_reference_dj_transition/B8_RESIDUAL_FIX.wav`
- SHA-256: `47824cc9b923c708f261c7d3db82e46e2f910fec47b802111bcd26c1c5aa1205`
- format: stereo 44.1 kHz PCM24, 40.0283 seconds
- transition start: 7.9877 seconds; landing: 24.0065 seconds
- focused two-bars-before/four-bars-after interval: approximately
  20.0127–31.9942 seconds
- integrated loudness: -14.134 LUFS; sample peak: 0.751554; clipped samples: 0
- deterministic rerender produced the same SHA-256

### Residual diagnosis

The B7 renderer corrections remain valid and are retained. No new hard DSP
splice, mastering reset, target gain reset, or sample-level click was found:

- The B7 shared-clock stem sum still reconstructs its target master with
  0.999662 correlation and 0.026310 RMS residual ratio.
- In the isolated target-only render, the half-bar landing change is only
  -0.354 dB full-band, -0.762 dB below 155 Hz, and +0.744 dB above 3 kHz.
- B7's landing-local maximum sample delta is only 0.531 times its global
  99.9th-percentile delta. C3 is 0.624 times; neither landing is an anomalous
  click/transient.
- B7 uses one fixed global gain and one memoryless soft clip across the whole
  file. Its only postlanding deck ramp is the already-declared target master
  gain from 0.88 to 1.0 over 0.62 bar.

The remaining defect is therefore choreography/tail-state, with two measured
parts:

1. **False bass/energy event before the real landing.** B7 previewed four bars
   of the target's low-frequency cue material. The fourth preview bar contains
   an internal pocket: its four low-band quarter-bars measured -31.310,
   -33.375, -16.221, and -15.917 dBFS. Energy therefore collapses, returns
   strongly half a bar early, and then falls again onto the nominal landing.
   C3's successful handoff uses the same cue but a stable two-bar target-low
   cadence and does not expose that four-bar pocket at this location.
2. **Wrong outgoing-FX frequency/lifetime handoff.** B7's isolated target gains
   0.744 dB above 3 kHz at landing, but the full B7 loses 5.486 dB from the
   final prelanding quarter-bar to the first postlanding quarter-bar. The
   difference is the outgoing riser: it reaches its peak at the boundary and
   has no wet release. Meanwhile the rhythmic source loop remains in the
   520–5200 Hz lead/vocal range until 1.5576 seconds after landing. The first
   annotated target vocal begins at 0.6802 performed seconds, leaving 0.8774
   seconds of unnecessary rhythmic/midrange overlap. Its onset-envelope
   correlation with the target drums is only 0.105 (best lag -29.0 ms), so the
   overlap is not reinforcing the target groove.

The target cue itself is retained. It is the same cue used by successful C3.
It is one bar after the detected drop boundary by deliberate design: the
classifier's first drop bar is 98.7% vocal-active and has a weak first-quarter
drum onset (0.368), whereas the current cue has a strong first-quarter onset
(3.310), substantially less vocal coverage (62.0%), and stable raw full/low
energy across its four-bar loop boundary (-0.28/+0.17 dB). Nearby cues either
lose downbeat strength, have more vocal coverage, or sit much deeper inside
the phrase. There is no evidence-based reason to move it for B8.

The immediate full-target reveal is also retained. The private staged-target
counterfactual made the half-bar high-band loss worse (-7.805 dB), while the
actual target-only reveal rises +0.744 dB. The staged reconstruction still
differs from the full master (first-bar correlation 0.98835, residual ratio
0.16086, full master 4.27 dB brighter above 3 kHz), but that difference is
helping replace outgoing spectrum rather than causing the residual failure.

Target playback is not one linear deck stream in B7: target drop drums/low are
previewed as a four-bar loop, intro other/vocal run linearly into the cue, and
the full master starts at the cue on landing. C3 uses the same four-bar drum
restart successfully, so this is a declared choreography choice rather than a
remaining renderer defect. F alone uses adjacent natural-tempo target-master
slices throughout.

### C3/F control comparison

- B7 introduces target drum air at bar 1, body at 3.5, low at 5.3 (material by
  5.65), and target vocal at 5.2 (material by 5.6); full spectrum appears at
  bar 8. Its final bar has eight simultaneously moving source/target layers,
  and its source loop originally survived 0.78 bar after landing.
- C3 introduces target rhythm at bar 0, target low at bar 4 (material by 4.5),
  withholds target vocal until the postlanding master, and reaches full
  spectrum at bar 8. Its four-layer final-bar handoff settles target gains to
  drums 0.90 / low 1.00 / upper 0.88, and its final source echo ends 0.2392
  seconds before landing.
- F has only two concurrent reset actions: one linear target-context fade over
  1.9273 seconds and one decaying source-vocal echo sequence. Its last echo
  ends 0.0412 seconds before landing; adjacent raw target master supplies the
  landing. F's large energy rise is therefore a promised reset, unlike B7's
  unintentional prelanding bass pocket/rebound.

### Private diagnostic renders

All use exact B7 timing and cover two bars before through four bars after the
landing. They are forensic tools, not DJ candidates:

- `DIAG_SOURCE_TAIL.wav` — processed outgoing source only
- `DIAG_TARGET_PRELAND.wav` — target contribution before landing only
- `DIAG_TARGET_POSTLAND.wav` — target contribution after landing only
- `DIAG_TARGET_CONTINUOUS.wav` — target across the boundary, no source
- `DIAG_SUM_NO_SOURCE_FX.wav` — B7 with outgoing FX suppressed
- `DIAG_SUM_NO_TARGET_FULL_REVEAL.wav` — staged target retained after landing

`DIAG_SUM_NO_SOURCE_FX` and `DIAG_TARGET_CONTINUOUS` are intentionally
sample-identical in the focused window: by two bars before landing, B7 has no
remaining dry source, only its loop/riser/tail effects. Machine-readable
evidence is in private `B7_RESIDUAL_DIAGNOSTICS.json` and
`B7_C3_F_RESIDUAL_COMPARISON.json`.

### Exact B8 correction and regression evidence

B8 changes only the smallest set supported by those controls:

1. The target cue, full reveal, landing, gains, and B7 shared-clock renderer
   stay fixed. Only the target-low preview uses the same cue's stable two-bar
   cadence instead of exposing its four-bar internal pocket.
2. B7's uninterrupted rhythmic loop state is preserved through landing, then
   released by 0.6602 seconds — 20 ms before the performed target-vocal onset
   — instead of continuing 0.8774 seconds into that vocal.
3. A band-limited, diffuse wet residue derived from the existing riser carries
   only its >3 kHz release across landing and decays at the same pre-vocal
   endpoint. No unrelated impact or new musical event was added.

The B8 final-bar low quarter-bars are now -16.669, -16.791, -16.599, and
-16.211 dBFS. The landing high-band quarter-step improved from -5.486 dB in B7
to -2.745 dB. The landing-local sample delta is 0.194494, below the file's
0.280035 global 99.9th-percentile delta, so the wet release did not create a
click-like seam transient. B8 preserves B7 up to the source release scope,
contains finite audio, and has no clipping.

**STOP/GATE:** compare only `B7_FIXED_BOUNDARY.wav` against
`B8_RESIDUAL_FIX.wav`. Human listening decides whether the already-good source
move now flows into TRACK_B as one intentional performance. Do not produce B9,
resume automation/UI/Set Director, create another transition family, or render
a full mix before that verdict.

## B7 HUMAN VERDICT — STRUCTURAL FIXES VALIDATED; RESIDUAL LANDING FORENSICS ACTIVE
2026-09-14. The user compared `B6_LANDING_3` with
`B7_FIXED_BOUNDARY` and judged B7 **definitely and significantly better**.
This validates that the shared target time-map and uninterrupted source-loop
state fixes below were real and audible; preserve them permanently. The core
perceptual complaint nevertheless remains: the transition into TRACK_B is
still not fully convincing, smooth, or DJ-like. Do not declare success, revert
B7, resume automation/UI/Set Director/full mixes, or guess B8 parameters.

That task is complete in the B8 section above; B7 remains the frozen comparison
baseline and its renderer fixes must not be reverted.

## STRUCTURAL LANDING-BOUNDARY INVESTIGATION — B7 READY FOR HUMAN LISTENING
2026-09-14T17:32:26Z (fresh Codex recovery after the prior thread-store
failure).
Repository authority was read in the required order, including the complete
research specification and implementation plan. After an approved
`git fetch`, local HEAD and `origin/v2-professional-autonomous-dj` both resolve
to `93bbc327dded3da74498de04bd54c9ed57161779`. The tracked worktree and index
are clean; the pre-existing untracked `.claude/` directory remains untouched.

The latest human verdict supersedes the listening-ready stop instruction below:
`B6_LANDING_3` was the best B6 treatment, but still exposes a discontinuous
handoff boundary; `B6_LANDING_2` improved the landing but dropped the source
effect too abruptly; `B6_LANDING_1` was poor when its source-side effect tried
to connect to TRACK_B. Autonomous planning, UI, long mixes, and new transition
families remain paused.

The requested trace is complete. A crucial provenance finding is that the B6
manual R&D files do **not** travel through `PerformanceRecipe`, recipe
compilation, `PerformanceTransition`, `apply_transition`, Audition Lab, or the
Set Director/full-set renderer. Their actual path is `prepare_material` ->
direct stem/full-mix/loop envelopes -> a 128-sample (2.902-ms) manual splice ->
one fixed whole-file gain/soft-clip pass. No recipe/compiler/production-DSP
state exists to reset in B6, and patching those production modules would not
change the controlled artifact.

Exact structural diagnosis:

- The B6 source tail is **not truncated at landing**. It measures about
  -24.19 dBFS over the last half-beat before landing, -28.60 dBFS over the
  first half-beat after it, and reaches about -65.07 dBFS in its final 50 ms
  before becoming exactly zero at its declared 0.78-bar endpoint.
- It nevertheless has a real lifetime defect 0.219 bar before landing: B4's
  active one-beat loop buffer ends on a nonzero sample, then B6 creates a new,
  differently filtered buffer whose first sample is exactly zero and fades it
  back in. The old last-sample-to-new-first-sample component delta is
  `0.05433497`; the following 50-ms full level rises by 4.33 dB. Thus B6_3's
  apparent continuation is actually teardown/restart.
- The primary target defect is stronger. Raw target stems reconstruct their
  master correctly (`corr=0.999646`, residual/master RMS `0.02689`). The lab
  then launches separate adaptive FFmpeg `atempo` jobs for the master and each
  stem/interval. After that independent processing, the reconstructed stems
  correlate only `0.302336` with the separately processed master and their
  residual is `1.17845` times the master RMS. The transition therefore changes
  from independently stretched intro stems plus repeated target-drop
  drum/low buffers to a separately stretched mastered full mix at landing.
  It is phase-cued, but it is not one coherent rendered target deck.
- B6_3 exposes both defects because it asks one perceptual gesture to cross the
  splice while target ownership also changes there. Across the landing
  half-seconds it changes +0.85 dB full-band, +2.25 dB below 155 Hz, and
  -5.55 dB above 3 kHz. The 128-sample guard prevents a digital click but
  cannot preserve filter/time-stretch state or make incoherent buffers equal.
- C3 uses the same underlying manual target reconstruction and therefore masks,
  rather than disproves, that renderer defect. Its choreography has target
  rhythm/low ownership established before landing and its source echo is
  already clearing, so its half-second full/low/mid movements stay roughly
  -0.47/-0.98/+0.91 dB. F avoids the defect: its target intro and target body
  are adjacent samples from one natural-tempo master at one trim, while the
  source echo has completed its separate reset role before the target downbeat.
- There is no boundary-local mastering change in B6: all material receives the
  same fixed gain `0.556776515` and one memoryless soft-clip pass. The observed
  change is upstream buffer/state reconstruction, not mastering.

Classification: the demonstrated fault is in the **private manual renderer's
buffer/time-map lifetime**, amplified by B6's choreography. It is not evidence
of a `PerformanceRecipe`/`apply_transition` production defect because those
paths are absent from this render. The smallest correct fix was therefore made
in the private controlled renderer only: the target master and all landing
stems are now processed together once as a ten-channel bundle under one shared
time map, and the active source loop is transferred through a 12-ms state
handoff into one phase-continuous post-landing tail rather than restarted.
Autonomous production code remains unchanged and paused.

Exactly one controlled output was rendered:

- `/tmp/djenius_reference_dj_transition/B7_FIXED_BOUNDARY.wav`
- SHA-256 `88ef7b56c481bd210aab2dcf3a4d06ca82e0cf466f33c2fab9f6caf915c8b19a`
- stereo 44.1-kHz PCM-24, 40.0283s, peak `0.644854`, zero clipped samples
- transition 16.0218s; landing unchanged at 24.007s
- shared-clock target reconstruction `corr=0.999662`, residual ratio `0.02631`
- source buffer handoff delta reduced from `0.05433497` to approximately
  `1.86e-9`; tail duration/envelope remains B6_3's 0.78-bar design
- deterministic rerender reproduced the exact B7 SHA-256 above; all frozen
  B6_3/C3/F/B4/D2/B5_TARGET_2 hashes remain unchanged

Private reproducibility/diagnosis files are `render_b7_fixed_boundary.py` and
`diagnose_boundary_structure.py`; `REFERENCE_NOTES.json` contains the B7
control and measurements. This is engineering evidence only. Stop for the
human B6_3-vs-B7 listening gate; do not create B8 or resume automation.

## LANDING MICRO-LAB — B6 LANDING 1/2/3 READY FOR HUMAN LISTENING
2026-09-14T14:31:46Z (Codex/GPT-5.6 Sol). Latest human verdict is now the
authority: B5_TARGET_2 is the winning target-entry direction and is frozen as
the working reference; its staged target reveal is noticeably better, but its
final ownership transfer is still not smooth. B5_TARGET_1 is not smooth enough
and B5_TARGET_3 is abandoned. The successful B4 source choreography, target
pair, target cue, and fixed mastering control remain unchanged. Automation and
all broad product work remain paused.

The private landing-only listening files are in
`/tmp/djenius_reference_dj_transition/`:

- `B6_LANDING_1.wav` — target remains in its staged spectral/stem state at the
  nominal downbeat, then reaches the mastered full mix across 1.25 target bars;
  SHA-256
  `5c0c76c8e214cbe08418e0afd1e99d3fb02b447d7c073a10557f4f804b01a6eb`
- `B6_LANDING_2.wav` — during only the final transition bar, the partial target
  reveal becomes a phrase-aligned full target-stem reconstruction before the
  normal mastered drop begins; SHA-256
  `5717fe223b1b1fd7431be7aeb6378b1db66d4302f0aee4fe4851a74be87306fe`
- `B6_LANDING_3.wav` — B5_TARGET_2's target reveal remains unchanged; B4's
  high-passed one-beat source motif continues through the target downbeat as a
  decaying tail while target gain reaches unity within 0.62 bar; SHA-256
  `38854dc9f50bb215cfeda0fe8ef434395381fb90d22083a7e172de1ccc9c9ad7`

Forensic diagnosis:

- Beat/cue phase is not the defect. Target drum and low-frequency landing
  references show 0.0 ms best lag and correlations of 1.000/0.999. The intro
  and post-landing audio are both fitted to the same 1.997-second performance
  bar. The cue therefore remains unchanged.
- B5_TARGET_2 changes by about +2.0 dB overall and +3.2 dB below 155 Hz while
  losing about 4.6 dB above 3 kHz across the landing half-seconds. Its staged
  target's partial drum/stem/EQ state becomes the mastered full target through
  only a 128-sample/2.9-ms seam. The content is phase-aligned; the spectral
  ownership state is not.
- B4's one-beat source loop stops before the boundary and its riser ends at the
  boundary, reinforcing the perceptual syntax "effect stops, full target
  starts."
- C3 keeps target low/rhythm continuous and changes full level by roughly
  -0.5 dB with low/mid changes within about 1 dB. F instead earns its larger
  landing contrast by clearly separating source release, echo decay, target
  context, and target downbeat. B5_TARGET_2 promises continuity, so its abrupt
  spectral pivot reads as a defect rather than a reset.

Every B6 output is sample-identical to frozen B5_TARGET_2 up to the start of the
eighth/final transition bar within one PCM-24 quantization step. LANDING_1 does
not change anything before the nominal landing; LANDING_2 changes only the
final bar's target reconstruction; LANDING_3 extends only the final source-loop
gesture and first target bar. Target remains the sole bass owner throughout all
three treatments. The transition still begins at 7.988s and lands at 24.007s.

`REFERENCE_NOTES.json` contains the full diagnosis, C3/F comparison, exact
variant differences, focused listening window, fixed-reference hashes, and
safety diagnostics. The frozen `B5_TARGET_2.wav` remains byte-identical,
SHA-256 `9a2a547f39a1ed45e640f8dcf90c1fc4b85d92e10e1411531667459fc3b3a8d9`.
C3, D2, F, and B4 also remain unchanged. All B6 WAVs are stereo 44.1-kHz PCM-24
with no clipped samples and no anomalous sample discontinuity at landing. The
private reproducibility/forensics aids are `render_b6_landing_lab.py` and
`analyze_b6_landing.py`. No production code changed. Stop here for the human
listening gate; do not return to automation.

## TARGET-ENTRY LAB — B5 TARGET 1/2/3 READY FOR HUMAN LISTENING
2026-09-14T14:11:42Z (Codex/GPT-5.6 Sol). Latest human verdict is now the
authority: A4 is too ordinary and is paused; B4's source-side loop manipulation
is genuinely DJ-like but its target handoff is bad; E3 has useful source-side
preparation but its target arrival is also wrong. F and C3 remain the successful
references, D2 remains the acceptable restrained reference, and E3 is not being
iterated until the target-entry lesson is established. Automation and all broad
product work remain paused.

The controlled private target-entry lab is ready in
`/tmp/djenius_reference_dj_transition/`:

- `B5_TARGET_1.wav` — early continuous rhythmic introduction, SHA-256
  `105a4dea78ad5da508ce29ac234b52a8761cfe03a69ff66ee6d1ac8e781ace06`
- `B5_TARGET_2.wav` — staged drum/stem/frequency/identity reveal, SHA-256
  `9a2a547f39a1ed45e640f8dcf90c1fc4b85d92e10e1411531667459fc3b3a8d9`
- `B5_TARGET_3.wav` — sparse tease into an alternate lower-vocal drop cue,
  SHA-256
  `524b58894058491f27f26cde4603ec1aad008c0481e2002cf041f367020ebb39`

All three retain B4's exact source-side contribution: source low/upper
envelopes, the same bar-2 phase-anchored `4 -> 2 -> 1` loop, the same shaped
riser, and the same source release. The raw source contribution is
sample-identical in every variant, SHA-256
`8071c0caddd8dfa03768708c930fa1559f0fed11dbff2dd76ecbb9d40ac9dc4b`.
They also use one fixed master gain (`0.556776515`) derived from the original B4
raw performance; per-variant loudness normalization is disabled so target entry
is the only experimental variable. TARGET_1 and TARGET_2 retain B4's target cue;
TARGET_3 changes only the target cue to test whether the original dense/vocal
arrival was itself unsuitable. The source track and choreography remain fixed.

Root cause isolated in B4: its target low, drum, and upper previews all withdrew
before landing while the source loop/riser also ended. That erased the shared
territory and made the full target reappear as a replacement. Target bass also
arrived before target identity was sufficiently established, while target vocal
identity remained absent until landing. C3 demonstrates continuity across the
landing and staged target ownership; F demonstrates separate perceptual roles
for source release, effect tail, target context, and full target entry. The new
variants test those principles without copying C3/F's effects.

`REFERENCE_NOTES.json` records the exact target-only change, hypothesis, and
bar-level choreography for each variant, plus listening times, fixed-source and
mastering controls, diagnostics, and preservation hashes. All three transitions
begin at 7.988s and land at 24.007s, followed by about eight clean target bars.
They are stereo 44.1-kHz PCM-24 and contain no clipped samples. Integrated
loudness is -14.079/-14.246/-14.320 LUFS under the fixed master gain; this is a
safety/control check, not acceptance evidence. The private reproducibility and
visual QA aids are `render_target_entry_lab.py` and
`TARGET_ENTRY_LAB_DIAGNOSTICS.png`.

B4, C3, D2, and F were hashed before and after rendering and remain byte-identical:
B4 `9060240f5aedd8d8a185f447d82eaa9279b099e64d2a08ea20d8b67ffee20a07`,
C3 `ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03`,
D2 `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586`,
and F `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`.
No production code changed. Stop here for the human listening gate; do not return
to automation or transfer anything to E3 yet.

## MUSICAL-CAUSALITY ROUND — A4/B4/E3 READY; C3/D2/F PRESERVED
2026-09-14T13:53:01Z (Codex/GPT-5.6 Sol). Latest human verdict is now the
authority: F remains the strongest gold reference; C3 is newly successful and
must not be redesigned; D2 is acceptable as the restrained/smooth category;
A3 still sounded like source -> unrelated effect -> target; B3's concept worked
but remained mechanical; E2 still sounded like an unearned total replacement.
Automation and all broad product work remain paused.

New private listening files in `/tmp/djenius_reference_dj_transition/`:

- `REFERENCE_A4.wav` — SHA-256
  `14eb04318b6cd695e347e70e05693b0fdf1d458835c87ffed6b69f906eed5db7`
- `REFERENCE_B4.wav` — SHA-256
  `9060240f5aedd8d8a185f447d82eaa9279b099e64d2a08ea20d8b67ffee20a07`
- `REFERENCE_E3.wav` — SHA-256
  `919cb480ad169fd828b69f7209abd19c34863569730b09f18f72743597447158`

Successful/acceptable files were frozen before rendering and remain
byte-identical afterward: C3
`ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03`,
D2 `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586`,
and F `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`.
No C4 was created because no single certain micro-polish justified altering the
successful C3.

Root causes and fixes:

- **A4:** A3 already used the target's real drums, but kept the target's most
  recognizable pre-drop material—its vocal runway—out of the bridge. The
  percussion was related by provenance but anonymous to the listener. A4 first
  hands rhythmic ownership toward the target, clears the source vocal, then
  introduces the target's actual final intro vocal before delaying the two-beat
  bass swap until the target groove has been accepted. The landing completes a
  target identity already heard; no generated effect was added.
- **B4:** seam study across source motif candidates selected bar 2, which had
  the smallest boundary discontinuity and most even quarter-beat energy. B3's
  crossfaded simultaneous loop states could create phasing/flams even under
  smooth envelopes. B4 uses one phase-anchored motif with only sequential
  4-beat -> 2-beat -> 1-beat states. Halvings occur at the shared loop start;
  the half-beat flourish and synthetic impact remain removed; riser entrance
  starts at zero and the bass pocket is shorter.
- **E3:** the E/E2 pair was judged wrong for the technique: incompatible keys
  required hiding all target identity except drums, guaranteeing sudden total
  replacement. E3 uses a different exact-key pair with an eight-bar low-energy
  target runway into a stronger section. Target intro highs/mids/drums enter
  before the cut; source drums/vocal/harmony/bass clear sequentially; one short
  source-vocal throw marks release; target vocal lightly foreshadows identity;
  target bass remains reserved for the landing. A rejected first private E3
  render exposed another issue: the intro was about 5 dB quieter than the source
  and much quieter than its own landing, leaving preparation theoretical. The
  final E3 uses an intro-only deck return so target material becomes dominant in
  the final bar and the landing adds full range rather than the entire song.

`REFERENCE_NOTES.json` contains exact prior-version changes, causal rationale,
bar-level choreography, bass ownership, listening times, preservation hashes,
and private safety diagnostics. `render_remaining_round.py` and
`REMAINING_ROUND_DIAGNOSTICS.png` are private reproducibility/QA aids. A4/B4
transitions begin at 7.988s and land at 24.007s; E3 begins at 7.384s and lands
at 22.172s. All three WAVs are stereo 44.1-kHz PCM-24 with no clipped samples;
loop edit/landing deltas remain below ordinary high-percentile musical
transients. Human listening remains the only acceptance gate. No production
code changed. Stop here.

## SMOOTHNESS ROUND — A3/B3/C3/D2/E2 READY; F FROZEN AS GOLD
2026-09-14T13:28:28Z (Codex/GPT-5.6 Sol). The user listened to every manual
reference through A2-F. Human verdict: A2/B2/C2 improved their predecessors but
still lacked effect integration/smoothness; D was too ordinary; E was rough;
F was "REALLY GOOD" relative to the rest and is now the explicit gold
reference. `REFERENCE_F.wav` was frozen before work and remained byte-identical
after every render, SHA-256
`947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`.
No F2 was made because no sufficiently certain micro-polish justified risking
the approved reference.

The new private human-listening files are under
`/tmp/djenius_reference_dj_transition/`:

- `REFERENCE_A3.wav`
- `REFERENCE_B3.wav`
- `REFERENCE_C3.wav`
- `REFERENCE_D2.wav`
- `REFERENCE_E2.wav`
- preserved `REFERENCE_F.wav`

`REFERENCE_NOTES.json` now includes the exact prior-version deltas, why each
change targets smoothness, transferable principles learned from F, bar-level
choreography, bass ownership, listening timestamps, and diagnostics. The
private reproducible script is `render_smoothness_round.py`; private visual QA
is `SMOOTHNESS_ROUND_DIAGNOSTICS.png`. No private track filename or identity is
present in Git or the notes.

Transferable explanation for F's success: it tells one sequential story rather
than stacking several actions; dry source, wet tail, target context, and target
full-range entry occupy different perceptual roles; one track owns bass at a
time; the wet signal comes from musical source material and decays into space;
and the target begins establishing before its landing completes the direction.
F's shorter duration helps because that pacing is coherent, not because
echo/reset is intrinsically superior.

Round changes:

- **A3:** uses a four-bar phrase of the real target drums, split into air/body.
  Target hats enter first, drum body waits for the two-beat bass handoff, and
  source drums fade separately from source music. This directly addresses the
  pasted-on percussion criticism without generated drums or louder FX.
- **B3:** loop sizes/filters no longer switch as hard stages. Raised-cosine
  crossfades overlap the 4/2/1/half-beat captures, the riser has a shaped
  zero-level entry, the bass pocket is narrower, and the disconnected synthetic
  impact is removed so the target's own transient is the payoff.
- **C3:** preserves the human-liked repeat/echo character. Target drum material
  is now a four-bar rather than two-bar repeat; drum/other/vocal/bass ownership
  changes sequentially; taps have edge guards, progressive damping, and short
  stereo diffusion. A too-dense first private render was rejected and reduced
  before packaging.
- **D2:** fixes D's root musical defect: its intro-derived target low band was
  nearly empty, making the stated bass swap inaudible. D2 uses target landing
  low-end and drums only after the swap, while high/mid/vocal ownership proceeds
  in a deliberate 12-bar sequence. No decorative FX were added.
- **E2:** retains the decisive phrase/drop cut but replaces the envelope cliff.
  A four-bar native target drum phrase splits into air/body anticipation;
  source low/mid/high release at separate times; musical energy remains until
  the final fraction of a beat; no unrelated impact or FX masks the cut.

All five new WAVs are stereo 44.1-kHz PCM-24 with zero clipped samples; landing
crossfade deltas remain below ordinary high-percentile musical transients. This
is safety evidence only—the user must decide whether they are musically smooth.
No repository production code changed. Set Director, Candidate Composer,
Audition Lab, UI, long mixes, and autonomous work remain paused. Stop at this
human gate.

## GOLD-REFERENCE ROUND 2 — A2 THROUGH F READY FOR HUMAN LISTENING
2026-09-14T13:08:26Z (Codex/GPT-5.6 Sol). The user listened to the first
handcrafted A/B/C package and gave the first positive performance verdict:
all three sounded noticeably more like real DJing and were much better than the
autonomous mixes. They are promising, not finished or frozen. Per explicit
instruction, all Set Director, Candidate Composer, Audition Lab, UI, broad
architecture, and autonomous work remains paused.

The updated private package remains at:

`/tmp/djenius_reference_dj_transition/`

New listening files are `REFERENCE_A2.wav`, `REFERENCE_B2.wav`,
`REFERENCE_C2.wav`, `REFERENCE_D.wav`, `REFERENCE_E.wav`, and
`REFERENCE_F.wav`. `REFERENCE_NOTES.json` has been replaced with the requested
anonymous bar-level choreography, selection rationale, listening timestamps,
changes from A/B/C, bass ownership, FX, and safety diagnostics. The original
A/B/C files remain available. `GOLD_REFERENCE_DIAGNOSTICS.png` and
`render_gold_references.py` are private reproducibility aids. No private track
filename or identity appears in the notes or Git.

Round-2 strategies are intentionally different:

- **A2** refines A into a real three-band blend: target highs first, mids later,
  a one-beat bass handoff, and ordered source release. No decorative FX.
- **B2** preserves the foreground `4 -> 2 -> 1 -> 1/2 beat` source loop, then
  deliberately removes low-end/drums during the final build pocket so the
  target drop and bounded impact have space to land.
- **C2** preserves the rhythmic stem/mashup identity but replaces overlapping
  half-bar echo chunks with one selected vocal transient and four discrete,
  beat-spaced, progressively darker alternating-stereo post-fader taps.
- **D** uses a different, adjacent-key/close-tempo pair for a patient 12-bar EQ
  blend. Instrumental frequency ownership develops first; source and target
  vocals hand off after the bass switch instead of colliding.
- **E** uses another pair with near tempo compatibility but deliberately
  incompatible keys. Only high-passed target drums are teased; bass, melody,
  and vocals remain out until a tight phrase-release pocket and hard full-drop
  landing. It is not a harmonic crossfade.
- **F** uses a compatible-key pair with radically different tempos. It refuses
  forced beatmatch: the source completes four natural-tempo bars, a captured
  vocal echoes post-fader through a roughly two-second beatless reset, the
  target intro enters at natural tempo, and its verse lands after the echo has
  cleared.

Private iteration rejected three defects before this checkpoint: D initially
lost too much body because its instrumental intro was quieter than its landing;
E initially left about half a second of dead air; F initially included two
seconds of genuinely silent target intro. The final renders correct those
decisions. All six are stereo 44.1-kHz PCM-24, have no clipped samples, no
accidental silence, and click-safe landing seams. The intentional low-end paths
are continuous in A2/C2/D, removed only for the designed buildup/cut/reset in
B2/E/F. Human listening remains the only acceptance gate. Stop here; do not
extract templates or return to automation until the user judges A2-F.

## PERFORMANCE RESET — HANDCRAFTED REFERENCE #1 READY FOR HUMAN LISTENING
2026-09-14T12:36:51Z (Codex/GPT-5.6 Sol). The user's new authority explicitly
pauses autonomous-planner, scoring, set-level, UI, and broad architecture work.
The only active gate is proving one manually choreographed real-track handoff.
Local HEAD and the existing remote-tracking ref were both
`af5400d6921fdbdde8bd626f785d27021c5e8fcd` at recovery; the pre-existing
untracked `.claude/` directory remains untouched. The repository and Downloads
research specifications were verified byte-identical (SHA-256
`de2605fe29f41594ff035c3333fcbc151576e06584119b4f712e59da3e8a224f`).

A private listening package is ready at:

`/tmp/djenius_reference_dj_transition/`

It contains `REFERENCE_A.wav`, `REFERENCE_B.wav`, `REFERENCE_C.wav`, and the
anonymous `REFERENCE_NOTES.json` requested by the user, plus a private
diagnostic image and reproducible private render script. No real track identity
was written to Git. All clips are about 40 seconds: ~8 seconds of source
context, an exact eight-detected-bar / 16.022-second performed transition, and
~16 seconds after the landing.

The manually selected pair has matching 10B keys, high-confidence beatgrids,
complete stems, a low-vocal energetic TRACK_A exit, and a clear TRACK_B drop.
Manual cue study found that TRACK_B's nominal section boundary leads into a
sparse pickup bar; using it produced a false 5–6 dB landing collapse. The final
cue deliberately skips that pickup and lands on TRACK_B's first sustained
full-power drop downbeat. A +6.4 dB target deck trim corrects a real mastering
level mismatch before choreography. The final half-second landing changes are
+0.62 dB (A), -0.22 dB (B's riser/impact resolution), and +0.14 dB (C), with
continuous low-end, zero clipping, and no accidental silence.

- **A:** restrained long stem/EQ blend, staged target drums/upper frequencies,
  explicit phrase-boundary bass ownership swap, then clean source release.
- **B:** foreground source loop progression `4 beats -> 2 -> 1 -> 1/2`, rising
  high-pass tension, a genuinely audible two-bar riser, bounded landing impact,
  and full target release. An earlier private pass proved the production
  riser/impact at its raw generator ceiling was effectively buried (~-46 dBFS),
  so only this selected build receives a local bounded return gain.
- **C:** early rhythmic stem handoff, short TRACK_A-vocal-over-TRACK_B-bed
  mashup, then a four-tap post-fader vocal echo release with no riser/impact.

This checkpoint intentionally made no repository production-code change. It is
a private performance-vocabulary proof built from the production analyzer,
cached stems, time-stretching, filters, loudness/limiting utilities, and
procedural FX. Do not return to automation until the user listens. If none is
approved, iterate on this performance/audio; if one is approved, freeze its
choreography as reference #1 and create a genuinely different reference #2.

## RESUMED PERFORMANCE-RECOVERY SESSION
2026-09-13T17:59:57Z (Codex/GPT-5.6 Sol). Recovered the repository in the
required authority order, read the complete research specification, and
verified that the original Downloads copy is byte-identical (SHA-256
`de2605fe29f41594ff035c3333fcbc151576e06584119b4f712e59da3e8a224f`).
After `git fetch origin`, local HEAD and
`origin/v2-professional-autonomous-dj` both equal
`bf224162444cfaf410392899153c0a7660fc52da`; the only pre-existing working
tree item is untracked `.claude/`, which remains untouched. The prior
handoff's private listening package is present under
`/tmp/djenius_v1_v2_listening/`. Active work is limited to the two mandated
questions: coherent cross-edge track appearances and technique-family
behavior through the actual recipe/compiler/renderer/audio path. At this
initial recovery instant, no production change had been made yet; the completed
checkpoint is recorded directly below.

### First resumed-session findings (recorded before production edits)
- Built the required private same-anchor real-audio lab at
  `/tmp/djenius_performance_lab/` (one anonymous compatible pair, 4 bars,
  plain crossfade plus all 12 Phase-3 techniques, cached real stems where
  available). The manifest records compiler actions/operations and aligned
  difference diagnostics; numeric distance is diagnostic only, never the
  human-audibility gate.
- `riser_impact` is confirmed to be almost literally the plain crossfade in
  the production output (`correlation=0.999954`, difference RMS only 0.00956
  of the crossfade RMS). Its generated riser/impact layer exists, but the
  recipe schedules the one-bar riser too early and the impact on beat 4 of
  the final bar rather than the drop downbeat; the base mix remains a
  gradual crossfade.
- `bass_swap` is also extremely close in full-band output on this real pair
  (`correlation=0.998385`, difference RMS ratio 0.056825), even with real
  stems supplied. This does not by itself prove the low-band ownership move
  is inaudible, but it makes a dedicated low-band/ownership audit necessary.
- `drum_bridge` compiles as the same `beatmatched_blend` used by `eq_blend`
  plus 32 procedural events. Its difference from a plain crossfade is
  dominated by the shared beatmatch/EQ path, so a direct drum-bridge-vs-EQ
  isolation comparison is required before claiming the added groove matters.
- The recipe compiler preserves typed action schedules as diagnostics but
  does not execute most action envelopes. It reduces selection primarily to
  one legacy transition type plus a small set of hard-coded operations.
- `phrase_cut` has a V2 splice-semantics defect: DSP uses only a tiny target
  seam at the end of the buffer, but both V2 preview and full-set renderers
  advance the target cursor by the entire multi-bar overlap. That skips the
  target material immediately after the declared landing anchor.
- `stem_handoff` is audibly distinct when the private lab supplies real
  stems (`correlation=0.926739` vs crossfade), but it is unreachable in the
  actual application path: the Set Director provider never loads cached
  stems, and `render_set_director_mix` unconditionally refuses every
  stem-requiring candidate even though `TrackAudio` already has a `stems`
  field.

### Performance-recovery implementation checkpoint
Production changes are now in the working tree and documented in
`docs/v2/PERFORMANCE_QUALITY_AUDIT.md`:

- Set Director schema 7.1 carries typed, path-dependent track appearances.
  Candidate Composer receives an entry/consumed-end/minimum-establishment
  envelope and rejects anchors or transition lengths that would squeeze the
  track before it has established. Appearance state participates in the edge
  cache key. The old renderer shift remains only as a legacy/manual-plan
  compatibility guard.
- Phrase-cut preview/full-set splicing and duration planning now advance the
  target cursor by the actual click-safe seam rather than silently skipping
  the whole nominal overlap.
- Cached stems now flow from the real application provider through full-set
  segment slicing/validation into renderer DSP. Missing required stems fail
  explicitly; they do not masquerade as a stem handoff over crossfade.
- Phase-5 EQ blend/drum bridge/build families compile a renderer-executed
  `mix_choreography` directive. EQ stages incoming upper frequencies before a
  deliberate bass switch; loop shortening and riser/impact hold the source
  build and land the full target at 75%; drum bridge creates bounded space for
  its generated groove. The riser is scheduled in the penultimate bar and its
  impact is now on beat 1 of the landing bar.
- Echo release now captures the preceding source beat into a bounded
  post-fader tail, removes the dry source quickly, and gives the target clear
  space instead of adding echo over an ordinary long fade.
- Audition Lab's generic spectral metric now has bounded family-specific
  intent allowances. Collision, mud, holes, and excess beyond the allowance
  remain penalized; this corrects the damage model rather than adding a
  creative bonus.

Validation is complete for this checkpoint: focused recovery coverage passes
at **110 passed**; the complete repository regression passes at **1102 passed**
with only the two pre-existing Typer/Click deprecation warnings. `ruff check`
on every touched production/test file and `git diff --check` are clean.

The final real recovery render produced exact plan/render duration agreement at
**661.228s**, zero anchor shifts, and the sequence `echo_out /
loop_shortening / drum_bridge / riser_impact`. Its three middle tracks received
**33.599 / 130.888 / 191.989s** of independent airtime. The identical plan was
selected on three complete deterministic runs, including before and after the
bounded Audition spectral-intent correction. The finalized private package is:

`/tmp/djenius_performance_lab/listening_checkpoint/`

It contains full `V1 / previous V2 / recovery V2` links, controlled fixed-anchor
family comparisons, contextual clips for all four selected recovery handoffs,
and an anonymized manifest. **Human gate remains pending; do not call this
product failure resolved based on the engineering evidence.**

## LATEST VERIFIED TIME
2026-09-13T18:48:49Z (final private recovery render completed; full 1102-test
regression and lint/diff checks completed immediately beforehand)

## PERFORMANCE-RECOVERY COMMIT
The validated production/test/audit checkpoint was committed and pushed as
`32b2d3d6e679495d0edd7818fd2a787cb512608e` (`Recover V2 DJ performance
choreography`). This final handoff-status edit follows that production commit;
use `git log -1` and the remote ref as authority for its own docs-only SHA.
The only remaining untracked item is the pre-existing `.claude/` directory,
which was not touched or staged.

## PRIOR HANDOFF VERIFIED TIME (historical)
2026-09-13T20:05Z (user is transferring development to a different coding
agent -- GPT-5.6 Sol -- after this update; this session is stopping per
explicit instruction, not because work is finished)

## CURRENT PHASE
**Not Phase 8/9/10 work, and no new roadmap phase should start.** This is a
cross-phase, unplanned performance-quality investigation, now in its
**second round**. See `docs/v2/STATE.md` for the durable roadmap-level
summary (also updated this turn, kept consistent with this file) -- that
file records phase completion history unchanged; this file has the
operational detail.

## SECOND HUMAN LISTENING RESULT (read this first -- supersedes any "the
## fixes solved it" framing from earlier in this investigation)

The user personally listened again, this time to the fixed V2 code (the
four defects below already fixed, comparison rerendered). Their verdict,
recorded as close to verbatim as possible because it is the actual product
gate, not a paraphrase to soften:

> V2 is NOT obviously different from V1 overall. I can occasionally notice
> loops, builds, drops, echo, bass changes, and similar V2 techniques.
> Those actions are subtle/small. The difference can be noticed from time
> to time, but it is not transformative. Most importantly: it still does
> NOT feel like a real DJ is actively performing. I did not have moments
> where I clearly thought: "yes, that was a real DJ move."

**Explicit instruction accompanying this: treat it as an unresolved
product-quality failure.** The project's purpose is not to contain
correctly-labeled DJ techniques or technically valid DSP -- it is for
DJenius to actually behave and sound like an intentional autonomous DJ,
per the research specification. The four fixes below were real, verified,
and did measurably improve duration/family-diversity/audit-coverage -- but
this second listen proves they were **not sufficient**, and the user does
not want that treated as progress that lowers the bar.

The two "still-open" findings from the first round (cross-edge anchor
consistency, and technique labels compiling to near-identical DSP) are
explicitly called out by the user as highly relevant to this exact result
and are almost certainly implicated in why "loops, builds, drops, echo,
bass changes" register as noticeable-but-small rather than as a real DJ
move.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## GIT STATE (verified immediately before this handoff update)
- Local HEAD: `43288c69bff8d3ef7b66a473d63e20bf01138b45`
- Remote HEAD (`origin/v2-professional-autonomous-dj`, via `git fetch`):
  `43288c69bff8d3ef7b66a473d63e20bf01138b45` -- **equal to local**.
- `git status --short`: only `?? .claude/` (untracked session-tooling
  directory; never `git add` it; not part of the product).
- This handoff update (this file + `docs/v2/STATE.md`) will be committed
  and pushed immediately after being written, which will advance both
  local and remote HEAD by one commit. **Re-run `git log -1 --format='%H %s'`
  and `git fetch && git rev-parse origin/v2-professional-autonomous-dj`
  before trusting a specific SHA** -- the "LAST PUSHED COMMIT" line below
  names the commit this update itself becomes, so check it matches.

## LAST PUSHED COMMIT
Immediately before this update: `43288c69bff8d3ef7b66a473d63e20bf01138b45`
- "Update handoff with V2 listening-investigation findings and spec audit"
(docs only). The four production fixes themselves landed one commit
earlier at `89bfda5d0265d38cb1247fdb319f0ec1bcebe320` - "Fix real V2
planning defects found by human listening comparison". This update's own
commit (docs only: this file + `STATE.md`) will be the new HEAD after it
is pushed -- verify its SHA with `git log -1` rather than trusting a
number written before the commit existed.

## ALL FILES CHANGED THIS INVESTIGATION (across both commits so far)
- `djenius/core/candidate_composer.py` -- `_choose_anchor` position
  weighting fix.
- `djenius/core/set_director.py` -- audit budget/ordering fix, unrenderable-
  edge exclusion, real-anchor duration bookkeeping.
- `tests/test_v2_phase5_candidate_composer.py` -- new
  `test_choose_anchor_weighs_position_not_just_a_tiebreak`.
- `tests/test_v2_phase7_set_director.py` -- new
  `test_plan_never_selects_a_hard_rejected_edge` and
  `test_planned_duration_is_far_closer_to_the_actual_render_than_before`;
  fixed two tests whose manual-verification logic needed to match the
  production ordering change.
- `docs/v2/ACTIVE_HANDOFF.md` (this file) -- rewritten twice this
  investigation (once after the fixes, once now after the second listen).
- `docs/v2/STATE.md` -- reconciled this turn to stop describing Phase 10 as
  the open item and instead describe performance-quality/DJ-likeness as the
  single open, cross-phase gate.
No other tracked files changed. No real track names, artists, or filepaths
were introduced into any tracked file at any point.

## WORKING TREE
Clean aside from untracked `.claude/` (verified above).

## WHAT HAPPENED, IN ORDER

1. **First listen** (pre-fix): user rendered/listened to a private V1-vs-V2
   sanity comparison (4-track subset, same library/target duration/
   loudness) and could not hear a clear difference at all. Declared this a
   failure and mandated a root-cause investigation, explicitly forbidding
   "explaining it away" via passing tests/QA/provenance.
2. Investigation found **four real, independent, verified production
   defects**, all fixed, regression-tested, full 1095-test suite green,
   committed at `89bfda5`:
   - `SetDirectorConfig.max_candidates_audited_per_edge` was 4 while
     Candidate Composer generates up to 8, ordered by content-hash id --
     silently excluded whole technique families (the longer, more elaborate
     `eq_blend`/`filter_blend`/`phrase_cut`/`loop_transition`) from ever
     being auditioned for some real handoffs. **Fix:** raised to 8, added
     `_family_diverse_order` so a bounded budget samples across families
     before repeating one.
   - The beam search could select an edge where **every** audited candidate
     hard-rejected on real audition (`survivor_count == 0`) -- such a plan
     crashes at render time (`SetDirectorRenderError`). **Fix:** infeasible
     edges are excluded from beam expansion; a starved beam finishes where
     it stands instead of being forced through one.
   - `_choose_anchor`'s position preference (`directional`) was a tuple
     tie-breaker that only mattered on an *exact* score tie -- which real,
     continuously-varying cue scores essentially never produce. Anchors
     routinely landed deep inside a track regardless of position; one real
     track got only ~15s of standalone airtime out of 209s. **Fix:** folded
     into the primary score as a bounded (0.35) weighted term.
   - `_estimate_overlap_sec` assumed every track contributes close to its
     full length once a flat ~16-bar overlap is subtracted. Real anchors
     land far from track boundaries, so this overstated a real plan's
     duration by ~236s (664.0s planned vs 427.8s actually rendered).
     **Fix:** duration bookkeeping now uses each edge's real
     selected-candidate anchors.
   - A **fifth, deeper gap was found and documented but deliberately NOT
     fixed**: a middle track's entry anchor (edge before it) and its own
     exit anchor (edge after it) are still chosen independently -- Candidate
     Composer has no notion of "the edge before/after." The renderer's
     `anchor_shift_sec` correction (D044) absorbs the conflict at render
     time. Still happens after the fix (confirmed: the same TRACK_02
     handoff still needs a 14.86s shift in the fresh comparison-A render).
3. Reran the exact same end-to-end comparison, unchanged script, same seed/
   library/target. **Measured improvement:**
   - V2 rendered duration: 427.8s -> **589.2s** against the 600s target.
   - V2 track count: 4 -> **5 tracks**.
   - `candidates_rendered`: previously partial; now **270/270** generated
     candidates fully audited (100%, was capped before).
   - V1 unchanged (504.8s, same order/techniques) -- no V1 code touched.
   - Technique sequence: `riser_impact, loop_shortening, echo_out,
     drum_bridge` -- all 4 distinct (spec section 34's "no single technique
     > 40%" target: met).
4. Built comparison (B), the controlled performance comparison: same fixed
   track order for both systems (V1's own comparison-A order), each system
   picks its own technique.
   Script: `/tmp/djenius_v1_v2_listening/render_comparison_b_controlled.py`.
   V1 chose `filter_sweep, filter_sweep, phrase_cut`; V2 (same 3 pairs)
   chose `riser_impact, drum_bridge, phrase_cut` -- agreed with V1 on the
   last pair, diverged on the first two. The same TRACK_02 anchor-shift
   (14.86s) reappeared, confirming it is order-independent.
5. Built the private per-handoff review package (comparison A only):
   `/tmp/djenius_v1_v2_listening/handoff_clips/` (7 clips, each ~6s
   pre-roll + transition + ~6s post-roll, cut using `render_mix`'s own
   diagnostics JSON and `render_set_director_mix`'s own provenance --
   exact absolute positions, not re-estimated) and
   `/tmp/djenius_v1_v2_listening/handoff_review_manifest.json` (per-handoff
   technique, sections, why chosen, every candidate considered with
   rejection reasons, scores). All anonymized. Delivered to the user via
   `SendUserFile` in the prior turn.
6. Audited V2 against `docs/v2/DJENIUS_V2_RESEARCH_SPEC.md` (verified
   identical to the copy at `~/Downloads/...` via `diff`). Findings below.
7. **User listened a second time, to the post-fix V2 render.** Verdict
   quoted in full at the top of this file: occasional, subtle, non-
   transformative differences; does not feel like a real DJ performing.
   Treated explicitly as still-unresolved, not progress that satisfies the
   gate.

## SPEC AUDIT FINDINGS (grounded in `docs/v2/DJENIUS_V2_RESEARCH_SPEC.md`)

- **Section 32 (V1 vs V2 Blind Comparison)**: literal spec source of the
  gate both listens have now failed. Requires V2 to "win clearly" on
  musical intent, transition variety, creative performance, set coherence,
  DJ-likeness -- passing automated tests is explicitly stated to be
  insufficient. **Status: failed twice.**
- **Section 34 (Transition Diversity Acceptance)**: "No single technique
  > 40% of transitions" -- comparison A meets this numerically (4 distinct
  techniques / 4 transitions). BUT the same section also asks for "short,
  medium, and long transitions where appropriate" -- comparison A's 4
  techniques (`riser_impact`, `loop_shortening`, `echo_out`, `drum_bridge`)
  are **all** short, hard-coded to `bars=4` in `candidate_composer.py`
  (`phase3_recipe(..., bars=4)`, not `choose_bars()`).
  `eq_blend`/`filter_blend` (longer 8-16 bar treatments) were fully, fairly
  audited this time and genuinely lost on score for these specific real
  pairs -- not excluded by a bug. **This is very likely a leading
  contributor to the second listening failure**: technique-family
  diversity alone (satisfying the letter of section 34) does not produce
  audible/structural diversity if every winning family is short and
  similar in shape.
- **Section 16 (Candidate Ranking)** vs. actual `AuditionConfig.weights`
  (`djenius/core/audition_lab.py`): spec suggests `phrase_fit` at the
  highest weight (0.18) plus `groove_fit`/`harmonic_fit`/
  `technique_context_fit`/`novelty`; actual weights are
  `technical_margin 0.16, beat_stability 0.22, spectral_cleanliness 0.18,
  vocal_safety 0.14, energy_goal_fit 0.20, fx_safety 0.10`. **Verified this
  specific absence is correct layering, not a bug**: phrase/groove/harmonic
  fit are track-pair-level properties fixed once upstream (shared by every
  technique candidate for a pair), not technique-choice-level -- they
  wouldn't discriminate between DSP options for the same pair. `novelty`/
  `technique_context_fit` are the one plausible small real gap, partially
  covered by Set Director's `technique_diversity` edge component but not
  reproduced inside Audition Lab itself.
- **Section 35 (Creativity Budget)**: not implemented at all anywhere in
  `set_director.py`. Not proven to matter yet on short 4-5 track
  comparisons.
- **Definition of Done (section 43) "Human listening" checklist**,
  "Transitions no longer feel mostly like fades": checked the DSP
  compilation table in `candidate_composer.py` (~line 742). `riser_impact`
  and `loop_shortening` -- **2 of comparison A's 4 chosen techniques** --
  both compile to plain `crossfade` DSP with a layered
  riser/impact sample or loop-stutter on top, not a structurally different
  mix. `echo_out`/`drum_bridge` do use genuinely different DSP
  (`echo_out`, `beatmatched_blend`). **This is the single most concrete,
  spec-grounded explanation on file for the second listening result**:
  half of what V2 selected in the flagship comparison render is
  "crossfade plus a small layer," which is exactly consistent with
  "occasionally noticeable... subtle/small... not transformative."

## PRIVATE LOCAL ARTIFACTS (all outside git; comparison/review package)
Everything under `/tmp/djenius_v1_v2_listening/` (not reproducible via
`git checkout` -- intentionally outside version control):
- `v1_baseline.wav` / `v2_current.wav` -- comparison (A) full mixes. User
  listened to these (the fixed V2 version) for the second verdict above.
  Per explicit instruction, do not compress or modify.
- `comparison_metadata.json` -- reflects the fixed code (5 tracks, 589.2s).
- `v1_controlled.wav` / `v2_controlled.wav` + `comparison_b_controlled_metadata.json`
  -- comparison (B), controlled/fixed-order.
- `v1_baseline_diagnostics.json` / `v1_controlled_diagnostics.json` --
  `render_mix`'s own absolute-timeline diagnostics.
- `handoff_clips/V1_HANDOFF_00-02.wav`, `V2_HANDOFF_00-03.wav` -- per-handoff
  review clips, comparison (A) only, delivered to the user.
- `handoff_review_manifest.json` -- private review manifest, comparison (A)
  only, delivered to the user.
- `investigate_01_inspect_plans.py` / `investigate_01_v2.log`,
  `investigate_02_full_candidates.py` / `investigate_02_v2.log` --
  diagnostic scripts + fresh (post-fix) output.
- `build_review_package.py` / `render_comparison_b_controlled.py` /
  `render_comparison.py` -- throwaway scripts, self-contained,
  deterministic (seed=0), call only production functions.
All anonymous (`TRACK_NN` labels only); nothing here is referenced from any
tracked file.

## TESTS COMPLETED
- `tests/test_v2_phase7_set_director.py`: 18 passed (was 17).
- `tests/test_v2_phase5_candidate_composer.py`: 41 passed (was 40).
- Full repository regression: **1095 passed**, reverified immediately
  before this handoff update (clean, no flakes across two independent runs
  this investigation).
- Manually reproduced the pre-fix defect (monkeypatched exclusion check
  disabled) and confirmed it produces the old broken, unrenderable plan --
  proof the new regression tests catch a real defect, not a hypothetical.
- Reran both real 12-track comparisons (A and B) end-to-end through the
  fixed code, not just unit tests.
- **None of the above tests, or the full suite passing, are evidence the
  DJ-likeness gate is met.** The second human listen is the only test that
  actually measures the thing the project is for, and it did not pass.

## TESTS STILL REQUIRED
- No unit/regression test is missing for the four fixes already made.
- Not yet built: clips/manifest for comparison (B).
- The gate that matters is not a test the agent can write: a **third**
  human listen, after whatever the next agent does to address DJ-likeness
  directly, using the review package's clips/manifest to inspect specific
  handoffs alongside the user's specific complaint if they give one
  (e.g. "handoff 2 didn't feel like anything").

## KNOWN DEFECTS / OPEN QUESTIONS, NOW RE-PRIORITIZED BY THE SECOND LISTEN

1. **Technique labels vs. actual DSP** (was priority 2, now the leading
   suspect given the second listen's exact wording). `riser_impact` and
   `loop_shortening` compile to plain `crossfade`. If the next agent
   changes only one thing, understanding and fixing this mapping --
   whether by giving these families (and any others found to be similarly
   thin) real distinct DSP treatment, or by having Audition Lab/Set
   Director weight genuinely-differentiated techniques higher when
   candidates are otherwise close -- is the most directly evidenced lever
   for the user's actual complaint.
2. **Cross-edge anchor consistency** (unchanged from first round). A
   track's entry (as target of one handoff) and its own exit (as source of
   the next) are chosen independently -- no shared notion of "this track's
   one coherent appearance in the set." `anchor_shift_sec` (D044) papers
   over the resulting conflicts at render time rather than the plan
   avoiding them; this is very plausibly part of why staging/anticipation
   ("DJ-style anticipation of the NEXT handoff while the current track is
   playing," explicitly named in the user's priority list below) doesn't
   come through -- the system isn't planning a track's single coherent
   appearance, so it can't obviously anticipate handing it off well.
   **Designed, not implemented**: extend `compose_transition_candidates`
   with an optional `minimum_source_time_sec: float = 0.0` parameter
   (backward compatible, default preserves all existing Phase 5 tests);
   `_choose_anchor`'s source-anchor cue filter would additionally exclude
   any cue with `time_sec < minimum_source_time_sec`; Set Director's beam
   loop threads through the previous edge's real target-consumption end.
   Not attempted -- would touch a heavily-tested, otherwise-frozen Phase 5
   module.
3. **Short-technique dominance** (spec section 34's duration-variety
   clause): even with fully fair auditing, the short 4-bar families keep
   winning on these real pairs; `eq_blend`/`filter_blend` (longer, more
   substantial treatments) lose on score, not on unfair exclusion.
4. **No creativity-budget system** (spec section 35) -- confirmed absent.
5. Carried over, unchanged, still true: two vocal-heavy difficult-pair
   categories in the Phase 10 transition benchmark produced zero surviving
   candidates even when every generated candidate was fully audited; no
   minimal-risk guaranteed-feasible fallback family exists.

## DECISIONS MADE THIS INVESTIGATION
Not yet written to `DECISIONS.md` as lettered D-entries. If continuing,
consider adding D046-D049 for the four fixes (family-diverse audit
ordering, unrenderable-edge exclusion, anchor position-weighting,
real-anchor duration bookkeeping), matching the project's existing
convention (D044/D045 cover the Phase 10 anchor-shift/lock-refusal
decisions).

## DO NOT REDO
- Do not re-investigate whether the four fixed defects (audit budget/
  ordering, unrenderable-edge exclusion, anchor position weighting,
  duration bookkeeping) are real -- confirmed, fixed, tested, proven via
  rerender. Re-litigating wastes effort already spent.
- Do not treat those four fixes as having solved, or made significant
  progress toward, DJ-likeness -- the second listen is explicit that they
  did not. They fixed real defects and are worth keeping; they are not
  the answer to the actual product question.
- Do not casually retune `AuditionConfig.weights` or
  `vocal_heavy_threshold` (0.55) without new evidence -- checked directly
  against real handoff data; the rejections they cause
  (`vocal_overlap_too_dense`, `weak_or_non_downbeat_phrase_anchor`,
  `target_drop_not_strong`) are musically legitimate for the audio
  inspected, not miscalibration.
- Do not compress or otherwise modify `v1_baseline.wav` / `v2_current.wav`
  unless the user asks.
- Do not start Phase 8 UI, Phase 9/10 follow-on work, or any new roadmap
  phase. Performance quality is the only thing to work on.
- Do not attempt to fix DJ-likeness by making effects louder, more
  frequent, or more extreme -- explicit user instruction: "the goal is
  intentional DJ performance, not flashy effects." A louder riser is not a
  more intentional one.

## EXACT NEXT ACTION (for the next agent -- GPT-5.6 Sol)
The user's stated top priority, verbatim in intent: **make V2 audibly and
behaviorally DJ-like.** Investigate the full pipeline end to end -- Set
Director -> track appearance/anchors -> Candidate Composer -> Audition Lab
-> PerformanceRecipe -> technique compiler -> PerformanceTransition ->
renderer -> final mastering -- to determine why sophisticated decisions
are producing only small audible differences. Areas the user explicitly
named as focus points (not a checklist to mechanically complete, a set of
leads):
- technique-specific DSP actually reaching the output (start here --
  directly evidenced, see finding #1 above);
- cross-edge appearance planning (finding #2 above);
- stronger but musically appropriate technique execution;
- meaningful buildup/release;
- bass ownership;
- loops that sound intentional;
- stem usage;
- drop swaps; phrase cuts; echo releases; drum/percussion bridges;
  riser/impact staging;
- transitions that differ meaningfully in sound and structure (not just
  label);
- enough time for tracks to establish themselves before handing off;
- DJ-style anticipation of the next handoff while the current track plays;
- avoiding conservative Audition Lab selection that reduces everything
  toward a safe crossfade.

Use the private review package (clips + manifest under
`/tmp/djenius_v1_v2_listening/`) to inspect real handoff data rather than
re-deriving it from scratch. Do not start with UI polish or a broad new
feature phase. Do not make the fix be "louder/flashier FX."

## SAFE RECOVERY NOTES
- The four fixes (`89bfda5`) and both handoff-doc updates are committed
  and pushed; this is a clean, buildable checkpoint. Confirm via
  `git fetch && git log -1 --format='%H %s'` and
  `git rev-parse origin/v2-professional-autonomous-dj`, then
  `python -m pytest -q` for the 1095-test regression.
- The private `/tmp/djenius_v1_v2_listening/` tree is not reproducible by
  `git checkout`. If lost, the scripts listed under "PRIVATE LOCAL
  ARTIFACTS" are self-contained/deterministic (seed=0) and regenerate
  everything except the pre-fix (first-listen) comparison numbers, which
  exist only as text in this file and the session transcripts.
- If the next agent is tempted to declare victory after another fix: it
  needs a **third** real human listen before claiming the gate is met. Two
  rounds of "we found and fixed real defects" have already not been
  enough; do not repeat the pattern of assuming a plausible-sounding fix
  closes the gate without the user confirming by ear.
