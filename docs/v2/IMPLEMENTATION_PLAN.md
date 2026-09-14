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
| 8 | UI V2 | inspect/preview/override performance | PASS (core slice; see notes) |
| 9 | Personalization | feedback changes selection predictably | PASS |
| 10 | Certification | automated + private + blind V1/V2 listening | AUTONOMOUS PORTION COMPLETE; awaiting the user's blind listening gate |

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

## Phase 8 - UI V2 (Set Director inspection slice)
Bridge Set Director (Phase 7) into the running local application and UI, since through Phase 7 nothing in the actual app ever called `plan_set_v2`/Candidate Composer/Audition Lab -- only the legacy `plan_set` planner was reachable from the CLI/web app.

Delivered this phase:
- `djenius/audio/track_audio.py`: shared robust stereo decode (soundfile -> librosa -> ffmpeg fallback tiers, matching the analyzer's strategy) for feeding Set Director's `AudioProvider`.
- `LocalAppService` (`djenius/application.py`) gains a Set Director bridge: `start_set_director_plan` (a background job that loads real analyzed library tracks, decodes real audio, and runs `plan_set_v2`), `set_director_plan_view` (trajectory + handoffs + component-total diagnostics), `set_director_handoff_view` (the Transition Inspector: every audited candidate with score/rank/hard-rejection reason), `lock_set_director_candidate` (manual override, honored by later views), and `render_set_director_preview` (renders one candidate's real bounded preview to a WAV served through the existing `/api/outputs/{filename}` path).
- New `/api/set-director/...` endpoints in `djenius/web/app.py`.
- A new "Set Director" panel in the existing local web UI: set-arc selector, target duration, a creativity control (safe/balanced/creative, mapped to `SetDirectorConfig` overrides), a track-trajectory view (BPM/key/energy per position), a component-totals breakdown (the same transparent objective components Phase 7 exposes), a handoffs list, and a Transition Inspector modal per handoff showing every audited candidate (family, score, rank, or hard-rejection reason), an in-browser audio preview player, and a "use this instead" lock control.
- Incidental fix: `djenius/web/static/app.js` had a pre-existing dead-code bug (`renderPerformancePlan` referenced but never defined) that threw a `ReferenceError` on every page load and silently prevented the V9/segment-performance appearance-reorder buttons (`moveAppearance`/`removeAppearance`) from ever being attached. Fixed by rebinding the wrapper onto the actual `renderPlan` symbol callers use. Also added a `Cache-Control: no-store` header to the `/` route and version query strings on the static asset tags, since the app's lack of any cache-busting made this exact class of "my JS change isn't showing up" bug easy to reintroduce.

Explicitly deferred (not fabricated as done):
- Full end-to-end rendering of a complete, continuous Set-Director-planned mix (stitching every handoff's chosen recipe into one final output file). Only bounded per-handoff *preview* rendering is wired this phase; `HandoffSummary.candidates` now retains the actual `TransitionCandidate` (including its `PerformanceRecipe`) so a future phase can build a full-mix renderer on top of exactly this data without redesigning Phase 7.
- Graphical waveform visualization and a bar/action-level performance-timeline widget (research spec section 24.2/24.5). The Transition Inspector's `generation_reason` text and the plan's `human_readable_reasons` cover explainability; visual waveform/timeline rendering is left for a future UI pass.
- Stem-dependent candidates (e.g. `stem_handoff`) correctly hard-reject in the Transition Inspector with an honest reason ("candidate requires stems but audition render did not receive them") rather than crashing, since this phase's bridge does not load/decode separated stems -- consistent with stems remaining optional/gated elsewhere in the app.

### Phase 8 gate result
- Dedicated backend suite: **1 new test** (`tests/test_app.py::test_set_director_plan_inspect_lock_and_preview`) exercising the full HTTP flow (create plan -> poll job -> fetch plan view -> fetch handoff/inspector view -> lock an alternate candidate -> confirm the lock is reflected in both views -> render and serve a preview WAV -> 404 on an unknown plan/out-of-range handoff) against real (tiny synthetic) audio through the real FastAPI app. Complete repository regression: **1080 passed** (was 1079 before this test).
- `ruff check` clean on every new/changed Python file (one pre-existing, unrelated unused-import warning in `application.py` predates this phase and was left alone).
- Manual end-to-end verification via an actual browser against the real local app and the real anonymized `testMusic` library (not just the automated test): scanned and analyzed the real library, planned a smooth-arc Set Director set, confirmed the trajectory/component/handoff views rendered real BPM/key/energy/technique/score data, opened the Transition Inspector for one real handoff and confirmed it listed a ranked survivor, a second survivor, and two candidates correctly hard-rejected (one on clipping safety, one on the undelivered-stems limitation above) with human-readable reasons, played a real rendered bounded-preview WAV of the runner-up candidate in-browser, locked it as the selection, and confirmed both the inspector and the trajectory/handoffs view updated to reflect the override without a page reload. Also verified the pre-existing classic (non-V2) plan-creation and rendering UI path still works after the shared `renderPlan` bugfix.
- No private track title/artist/filepath is recorded here or in any tracked file; the manual verification above is described only in aggregate/structural terms.

## Phase 9 - Personalization
Add structured listening feedback that changes future Set Director technique/track selection predictably, reusing V1's existing preference store rather than building a parallel one.

Delivered this phase:
- `SetDirectorConfig` (Phase 7) gains three additive fields: `technique_preferences: dict[str, float]` (family -> preference in [0,1], missing = neutral 0.5), `liked_track_ids`/`disliked_track_ids: frozenset[str]`. A new `user_preference` edge component (weight 0.06, rebalanced from the other eight so the total still sums to 1.0) blends the selected candidate's technique-family preference with a bonus/penalty when the handoff's target track is liked/disliked. The existing cheap shortlist (`_shortlist_next_tracks`) also gets a liked/disliked adjustment, mirroring how artist-spacing is already handled in both places -- one for compute-bounding, one for the real weighted decision.
- `LocalAppService._set_director_learned_preferences()` reads `PreferenceProfile.get_preferred_transition_types(min_samples=2)` and `get_liked_tracks()`/`get_disliked_tracks()`, converts ratings from [-1,1] to [0,1], and feeds them into a fresh `SetDirectorConfig` every time `start_set_director_plan` runs. Technique-family feedback is stored in the exact same `transition_ratings` table V1's own `rate_transition`/`get_preferred_transition_types` already use -- the column is free-text, not enum-constrained, so V1's 8 `TransitionType` values and Set Director's 11 technique families simply coexist as different strings in the same aggregate. No schema migration was needed.
- New `LocalAppService.save_set_director_feedback(plan_id, index, rating)` and `POST /api/set-director/plans/{plan_id}/handoffs/{index}/feedback` (rating vocabulary identical to V1's existing `save_transition_feedback`: "great"/"good"/"bad"/"too abrupt"/"too long"/"too weak", or a raw float). Rates whichever technique family is *currently selected* for that handoff (honoring a Phase 8 manual lock if one is set).
- New "Rate the technique used here" buttons in the Transition Inspector modal. Liked/disliked track feedback needed no new UI at all -- it reuses V1's existing like/dislike controls and `/api/feedback/track` endpoint verbatim, since Set Director now simply reads the same store. Learned technique preferences also show up for free in the existing "Preferences" tab (`preferred_transition_styles`), since that view already calls the same underlying method.

### Phase 9 gate result
- Dedicated tests: `tests/test_v2_phase9_personalization.py` (**4 passed**) proving the pure mechanism -- weight/component validation, a technique-family preference reflected exactly in the `user_preference` component regardless of direction (liked/neutral/disliked all produce the expected score and a correspondingly higher/lower `total_score`), and a disliked/liked *track* deterministically losing/winning a two-track choice against an otherwise-identical alternative once `max_candidates_audited_per_edge` is large enough to remove candidate-ID-hash sampling noise between the two options. Plus two new/extended `test_app.py` cases covering the full HTTP feedback flow (rate a real handoff, confirm it appears in `/api/preferences`, confirm an unknown rating string 400s) and confirming three repeated "bad" ratings against the same technique family produce `technique_preferences[family] == 0.0` in a subsequently-built `SetDirectorConfig`.
- Complete repository regression: **1085 passed** (was 1080 before this phase). `ruff check` clean on every changed file (the one pre-existing, unrelated `application.py` warning is unchanged from before this phase).
- Manual real-browser verification: rated a real handoff's technique family "great" through the actual UI, confirmed the toast and the resulting value in `/api/preferences`, and confirmed the *existing* Preferences tab rendered it with no new frontend code required for that view.
- A genuine test-design pitfall surfaced and is worth recording here rather than only in `DECISIONS.md`: because `TransitionCandidate` ids are content-hashed from (among other things) the source/target track ids, two synthetic fixtures that are identical except for their id can have a *bounded* audition sample a different subset of an otherwise-identical candidate pool, producing a real (not preference-related) difference in `handoff_quality`. Tests asserting a preference-driven outcome must either audition the full candidate set or otherwise control for this, or they will be flaky/misleading.

## Phase 10 - Certification
Run the full automated suite, a private difficult-pair transition benchmark, and multiple full real sets -- everything Phase 10 can do without a human. The one thing it cannot do autonomously, and the phase's actual defining gate, is a blind V1-vs-V2 human listening comparison with a human scorecard.

A major gap this phase closed first: through Phase 9, nothing could render a Set-Director-planned set into one continuous, listenable file -- only bounded per-handoff previews existed (Phase 8's known limitation). Phase 10 adds `djenius/audio/set_director_renderer.py::render_set_director_mix`, which reuses the exact proven Phase 6 compile -> apply_transition -> splice pattern with full-track "before"/"after" windows instead of a bounded preview window, wired into the app as `POST /api/set-director/plans/{plan_id}/render` and a "Render full mix" button.

Building this exposed a real, previously-latent architectural fact, confirmed on real music, not just synthetic fixtures: Phase 5 chooses each edge's anchors independently, so a shared middle track's target-entry point (from the edge before it) and its own later source-exit point (for the edge after it) are not guaranteed to land in timeline order. The renderer detects this and shifts the affected transition to start exactly where the previous edge ended, preserving the technique's overlap duration and DSP untouched (`anchor_shift_sec` in each handoff's render provenance) -- rather than failing the whole mix over what is usually a few seconds of independently-reasonable anchor disagreement.

### Phase 10 gate result
- Dedicated suite: **6 passed** (`tests/test_v2_phase10_certification.py`): continuous/finite full-mix rendering with an exact non-overlapping-splice check; honoring a Phase 8 manual lock; rejecting a hard-rejected override; rejecting a candidate that needs stems the renderer can't supply; the anchor-conflict-and-shift behavior itself, reproduced deterministically; and the two-track minimum. One new `test_app.py` case covers the full HTTP render flow (plan -> render -> play -> confirm output metadata) plus a 404 on an unknown plan. A small, directly-related hardening fix shipped alongside: `lock_set_director_candidate` now rejects locking a candidate audition already hard-rejected (previously it did not check, so the UI could lock a choice the renderer would then correctly refuse).
- Complete repository regression: **1092 passed** (was 1085 at the Phase 9 checkpoint: +6 dedicated, +1 app-level). `ruff check` clean on every changed file; the one pre-existing, unrelated unused-import warning in `application.py` is unchanged.
- Real full-mix render: planned and rendered a genuine ~4:11 continuous mix from 3 real `testMusic` tracks (smooth arc, 2 real handoffs) through the actual running app. Verified technically: fully finite, RMS ≈ -14.8 dBFS (a normal mix loudness), negligible clipping (~2 samples out of 5.5M, right at but not meaningfully over the safety ceiling). Delivered directly to the user as the first real artifact for their own blind-listening comparison.
- Private difficult-pair transition benchmark (research spec 30.4): classified every real pair in the anonymized 12-track library (reused from the Phase 7 real-music gate) into the specification's 15 difficult-pair categories using independent, already-analyzed evidence (BPM relationship, vocal density, camelot distance, declared stems, section mix-in/out scores, tempo-zone count), then ran one representative real pair per category with at least one match through Candidate Composer + Audition Lab. 10 of 15 categories had at least one real match in this library; `same_bpm_same_key`, `genre_change` (no reliable genre signal to test against), `stem_poor` (every track in this library has declared stems), `long_ambient_intro`, and `strong_double_drop_candidate` had none. A genuine finding, not a narrow-sampling artifact (confirmed by auditioning every generated candidate, not just a bounded subset): the two vocal-heavy-pair categories (`vocal_heavy_to_vocal_heavy`, `instrumental_to_vocal`) each produced **zero surviving candidates** for their real representative pair -- partly the known stems limitation, partly genuine peak-safety hard rejection on already-loudly-mastered real vocal tracks. Every other tested category produced at least one survivor. This is recorded as a real, specific, actionable gap (Candidate Composer currently has no minimal-risk fallback family, such as a restrained equal-power crossfade, that stays feasible regardless of vocal/loudness conditions) rather than smoothed over.
- No private track title, artist, or filepath appears in this entry or any other tracked file.

## Human listening gate
No merge to master until serious V2 candidates are rendered locally and the user completes the blind listening gate described in `DJENIUS_V2_RESEARCH_SPEC.md`. **This is now the single remaining blocker for calling V2 "done."** Phase 10 prepared everything it can without the user: a real, technically-verified full mix has been delivered to them (see above), and the same pipeline can render more (different arcs, a longer set, or a specific library) on request. A comparable V1-style bake of the same library would need to be rendered through the existing classic `/api/plans` + `/api/plans/{id}/render` path for a true side-by-side; this was not attempted this phase and is a reasonable next step whenever the user is ready to do the actual comparison.

## Post-roadmap reference-backed automation gate

Manual R&D has produced four accepted controlled references. Before any
autonomous planning resumes, DJenius must prove it can reconstruct those
performances from analysis and explicit templates:

- freeze F, C3, B8, and D2 by hash and durable choreography contract;
- instantiate one named archetype deterministically from source/target
  `TrackAnalysis`, without absolute cue timestamps;
- render through a dedicated executor that permanently enforces shared target
  timing, continuous loop/effect state, explicit tail lifetime, deliberate
  bass ownership, and target establishment;
- reproduce the four original private pairs as AUTO_F, AUTO_C3, AUTO_B8, and
  AUTO_D2;
- compare analysis-derived cues, musical-time actions, overlap/ownership,
  target stream, tails, and establishment in a machine-readable manifest;
- stop for manual reference-vs-automation listening.

Delivered: all four templates, four same-pair renders, focused coverage, and
the private comparison manifest. Focused tests pass at 14; full regression
passes at 1116. This layer is deliberately not wired into Candidate Composer,
Audition Lab selection, Set Director, UI, or full-set rendering. New-pair
generalization and those integrations remain prohibited until the user passes
the same-pair listening gate.
