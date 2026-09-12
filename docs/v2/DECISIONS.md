# DJenius V2 Architectural Decisions

## D001 - Preserve V1 as immutable release baseline
**Decision:** V2 develops only on `v2-professional-autonomous-dj`; no merge to master before human listening acceptance.
**Why:** V1 is a verified 846-test baseline and must remain recoverable.
**Rejected:** direct development on master.

## D002 - V2 analysis is additive and backward compatible
**Decision:** extend `TrackAnalysis` with V2 fields while retaining existing V1 fields and deserialization tolerance.
**Why:** current planners/renderers and historical cached plans depend on the V1 schema.
**Rejected:** replacing the current analysis schema in one migration.

## D003 - Musical time becomes an explicit data layer
**Decision:** represent beat-in-bar, bar index, phrase/section and cue relationships explicitly; retain seconds as DSP coordinates.
**Why:** V2 composition requires beat/bar/phrase reasoning without destabilizing deterministic rendering.

## D004 - No new major dependency for Phase 1 core
**Decision:** implement Phase 1 core descriptors with the existing NumPy/SciPy/librosa stack.
**Why:** avoids license/hardware changes and establishes a deterministic fallback before evaluating optional structure models.
**Rejected for now:** making All-In-One, Essentia, or another model mandatory.

## D005 - Optional dependencies remain graceful
**Decision:** missing Demucs/semantic extras do not block V2 core. Existing cached stems may be used in private validation; future integration must remain optional and quality-scored.
**Why:** local-first operation must work on the base environment.

## D006 - Private benchmark data never enters Git
**Decision:** committed benchmark docs contain only aggregate/anonymized measurements; track names, private audio, stems, local listening reports and generated mixes remain ignored.
**Why:** privacy boundary is a product invariant.

## D007 - Analysis cache advances to version 6
**Decision:** invalidate V1 analysis-cache rows for normal cache reads after adding the V2 feature schema.
**Why:** silently returning version-5 rows with empty V2 fields would make planner behavior dependent on cache history. Source audio remains local; re-analysis is deterministic.

## D008 - Variable-tempo zones require sustained evidence
**Decision:** absorb tempo islands shorter than 24 detected beats into the closer neighboring zone before accepting a variable-tempo change.
**Why:** private real-track validation showed that fills and missed/doubled beats created false 4-11-beat tempo islands. Sustained changes still survive, including the controlled 120-to-100 BPM synthetic case.

## D009 - Stem activity is not stem-quality certification
**Decision:** Phase 1 stores activity/dynamics/onset summaries for cached stems and explicitly labels the method `activity_only_no_bleed_claim`.
**Why:** RMS/activity evidence is useful for planning, but it cannot honestly certify separation bleed/artifacts. A later dedicated quality metric must gate stem-heavy techniques.

## D010 - Typed recipes compile into the existing renderer contract
**Decision:** keep `PerformanceRecipe` above `PerformanceTransition`; compile V2 musical-time intent into the proven renderer-facing transition contract instead of replacing the V1/V9/V13/V14 renderer.
**Why:** Phase 2 needs a richer composition language without invalidating years of deterministic timing, provenance, and QA behavior.

## D011 - Recipe and action identity is content-derived
**Decision:** derive recipe/action IDs from canonical JSON using SHA-256 prefixes rather than counters, timestamps, or random UUIDs.
**Why:** identical musical recipes must serialize, compare, cache, and audit identically across runs.

## D012 - Phase 2 records the full action schedule even when legacy DSP is the executor
**Decision:** preserve action position, duration, quantization, ordering, parameters, clock BPM, and recipe duration in the compiled transition while mapping the five proof families to existing transition DSP.
**Why:** Phase 2 proves the representation/serialization/rendering boundary; Phase 3 can progressively execute richer action semantics without discarding Phase 2 provenance.

## D013 - Recipe validation is fail-closed
**Decision:** reject unsupported schemas/techniques, unsafe parameters, invalid musical positions, open/nested loops, unavailable stems, and out-of-bounds segments before compilation.
**Why:** arbitrary creative actions must never reach the renderer through permissive fallbacks.

## D014 - Phase 3 extends recipes through explicit technique operations
**Decision:** keep Phase 3 techniques inside the typed `PerformanceRecipe` -> compiler -> `PerformanceTransition` path, using explicit technique/preparation operations rather than renderer-only hidden behavior.
**Why:** every audible technique must remain serializable, testable, explainable, and compatible with the existing deterministic renderer contract.

## D015 - Stem DSP is validated at the renderer boundary and falls back explicitly
**Decision:** bass swap and stem handoff use cached full-track stems only after channel/coverage/finite/peak/signal validation and segment-local slicing. Invalid or unavailable stems produce explicit fallback provenance.
**Why:** cached stems are optional local inputs and must never cause silent corruption or ambiguous execution.

## D016 - Generated FX carry deterministic provenance
**Decision:** procedurally generated Phase 3 effects record effect type, deterministic seed, output sample bounds, and level in transition diagnostics.
**Why:** generated audio is still an audible source and must be attributable like track/stem material.

## D017 - Phase 3 application integration is part of the gate
**Decision:** technique validation includes direct `LocalAppService` coverage for application-side stem discovery/loading and renderer handoff, not only unit-level transition calls.
**Why:** a DSP path that is correct in isolation but unreachable through the actual application is not considered implemented.

## D018 - Fixed-timeout async regression failures are tracked as timing debt
**Decision:** retain the existing behavioral assertions after the observed 921-pass/3-timeout run because the same tests passed immediately alone and later unchanged full suites passed at 928/928.
**Why:** evidence indicates load-sensitive polling timing rather than a deterministic product regression; weakening assertions would hide a real test-infrastructure issue.

## D019 - Phase 4 procedural sounds precede external sample assets
**Decision:** implement the Groove / Sampler Layer first with deterministic project-owned DSP synthesis; external sample packs are not required for the initial architecture.
**Why:** this preserves reproducibility, licensing clarity, privacy, and provenance while establishing the musical-time scheduling system.

## D020 - Phase 4 event ownership is exclusive and auditable
**Decision:** Phase 3 combined `riser_impact` remains owned by `creative_fx_dsp` for Phase 3 recipes; Phase 4 discrete riser/impact and all new procedural pattern/sample events are owned by `groove_sample_layer`. The provenance auditor rejects duplicate riser/impact ownership, duplicate sample event IDs, and declared/rendered event-count mismatch.
**Why:** the same audible operation must never execute twice or become ambiguous in provenance as recipe semantics evolve.

## D021 - Phase 4 scheduling and synthesis are deterministic, bounded capability primitives
**Decision:** sample-layer actions use quarter/eighth/sixteenth musical grids, content-derived event/pattern IDs, deterministic seeds, finite/peak/DC safeguards, exact transition-local placement, and a no-op empty-layer compatibility path.
**Why:** Candidate Composer needs reproducible capabilities it can reason about without hidden renderer randomness or legacy-output changes.

## D022 - Candidate Composer is feasibility-first and does not rank sound quality
**Decision:** Phase 5 generates a small deterministic set of feasible, meaningfully different transition candidates, with explicit reasons/requirements/rejections. It does not render-and-rank candidates as though it knows which sounds best.
**Why:** generation/validation/explanation and perceptual audition are separate responsibilities. Audition Lab owns preview measurement, rejection, and ranking.

## D023 - Candidate identity and ordering are content/context derived
**Decision:** Phase 5 candidate IDs and ordered output must be reproducible for identical source/target analyses, set context, configuration, and seed; opaque UUIDs/timestamps are prohibited.
**Why:** deterministic candidate sets are required for caching, regression testing, provenance, and later audition comparisons.

## D024 - Candidate diversity is family-level by default
**Decision:** normally emit roughly 3-8 plausible candidates and prefer different technique families/roles over many near-identical parameter variants. Explicit parameter exploration is allowed only when it is intentional and explainable.
**Why:** the composer should present useful musical alternatives rather than inflate the search space before Audition Lab.

## D025 - Candidate floors never override hard feasibility
**Decision:** the configured Candidate Composer minimum is a diversity/search preference, not permission to manufacture or admit invalid candidates. Recent feasible families may be deterministically reintroduced only as a soft-memory fallback; hard-infeasible families remain rejected even when the floor is unmet.
**Why:** minimum-count pressure must never weaken stem, bounds, phrase, tempo, groove, compilation, or other safety/feasibility constraints. The composer reports `candidate_floor_unmet_due_to_hard_feasibility` when reality supplies fewer valid options.

## D026 - Half/double-time reset suppression requires confident alternative-tempo evidence
**Decision:** a non-primary tempo relation may suppress tempo-reset eligibility only when its effective delta satisfies the closeness gate and its hypothesis confidence is at least `0.55`. Low-confidence apparent half/double relations do not remove reset options.
**Why:** alternative tempo hypotheses are useful but uncertain; treating every apparent 2x/0.5x relation as authoritative can incorrectly eliminate the safest transition family.

## D027 - Technique memory is a soft defer policy
**Decision:** recent feasible technique families are deferred while enough non-recent feasible alternatives exist. They may be reintroduced in deterministic family order only when required to meet the configured candidate floor, and reintroduction must be explicit in diagnostics/provenance. Hard-infeasible recent families are never revived.
**Why:** repetition avoidance should improve variety without turning memory into a hard ban that collapses valid candidate supply.

## D028 - Audition Lab ranks rendered candidates; renderer remains an executor
**Decision:** Phase 6 owns bounded preview rendering orchestration, metrics, hard rejection, normalized scoring, ranking, and one-handoff selection in a dedicated typed layer. Ranking logic must not be hidden inside the renderer, and Candidate Composer feasibility rules should not be duplicated unless an interface defect is proven.
**Why:** generation, execution, technical validation, and quality comparison are distinct responsibilities. Keeping ranking outside renderer code preserves testability, transparency, and deterministic provenance.

## D029 - Audition hard rejection is separate from soft score
**Decision:** technically invalid previews fail closed before ranking; a high score in unrelated components can never rescue NaN/Inf, broken bounds/duration/provenance, catastrophic silence, unsafe clipping/peak, severe discontinuity/render failure, invalid stem use, or other hard technical failures.
**Why:** quality scoring is meaningful only over technically valid rendered performances.

## D030 - Initial Audition Lab ranking is transparent heuristic evidence, not human-quality certification
**Decision:** activate only metrics reliably supported by current rendered audio and analysis, normalize them transparently, keep weights configurable/documented, use stable deterministic tie-breaking, and explicitly defer unsupported harmonic/perceptual claims.
**Why:** the Phase 6 acceptance gate is controlled ordering of known-good vs known-bad references, not a claim that an automated score proves professional human DJ quality. The later blind listening gate remains authoritative for that question.

## D031 - Candidate peak/silence safety is transition-scoped; preview context remains audit evidence
**Decision:** hard peak/clipping, oversampled inter-sample peak proxy, RMS, and catastrophic-silence measurements used to judge candidate safety operate on the rendered transition region. Whole-preview peak/clipping remains reported separately for audit, while NaN/Inf and boundary integrity still cover the complete preview.
**Why:** private real-audio smoke showed that already-mastered source/target context can contain pre-existing samples at or slightly above 0 dBFS. Rejecting a candidate for unchanged context made entire handoffs unrankable even when the candidate transition itself was safe.
**Rejected:** raising the clipping threshold globally or silently normalizing preview inputs, both of which would weaken detection of candidate-introduced clipping.

## D032 - One-sample generated-event boundary residue is an explicit rounding trim
**Decision:** if independent seconds-to-samples rounding makes a valid generated event end exactly one sample beyond its transition buffer, trim that single terminal sample and record `rounding_trim_samples = 1` in sample-layer provenance. Any larger overrun remains a hard render error.
**Why:** a real 117.5 BPM riser/impact candidate exposed an exact one-sample conversion mismatch (`180154` event end vs `180153` transition samples). This is quantization residue, not musical out-of-bounds behavior, and must not make an otherwise valid candidate unrenderable.
**Rejected:** padding arbitrary overruns or loosening recipe bounds.
