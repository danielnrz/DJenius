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
