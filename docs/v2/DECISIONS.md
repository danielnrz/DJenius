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

## D033 - Set Director is additive; the classic beam-search planner is untouched
**Decision:** Phase 7 lives entirely in a new `djenius/core/set_director.py`. `djenius/core/planner.py` (`plan_set`, `plan_ordered_set`, `_beam_search`) is not modified, imported into, or routed through by Set Director. Set Director reuses only stable, already-tested lower-level primitives (`score_compatibility` for a cheap shortlist, `compose_transition_candidates` for Phase 5, `audition_candidate`/`rank_auditions` for Phase 6).
**Why:** the legacy planner is stable, tested, production behavior with its own callers (CLI/web/app service). Set-level journey planning is a new, still-evolving capability; coupling it to the legacy planner's internals would risk destabilizing behavior neither Phase 7 nor its users asked to change.
**Rejected:** extending `plan_set`/`_beam_search` in place with arc/audition awareness.

## D034 - Combinatorial audition cost is controlled by a fixed shortlist -> bounded-audition -> cache pipeline
**Decision:** Set Director never auditions every possible next-track edge. A cheap, audio-free per-step shortlist (`_shortlist_next_tracks`, using `score_compatibility` plus arc-aware energy-delta fit and an artist-repetition penalty) narrows candidates before Phase 5 candidate generation runs at all. Of the resulting Phase 5 candidates, only `config.max_candidates_audited_per_edge` (sorted by deterministic candidate ID) are ever rendered and Phase-6-audited. Every `(source, target, context)` outcome is cached in `EdgeAuditionCache`, keyed by a digest that includes the technique-memory window, set-phase/role/energy-goal, composer/audition config, and seed. A hard `max_edges_to_audition` ceiling exists as a last-resort compute guard: once hit, further cache-miss edges get a cheap-compatibility-only `HandoffSummary` flagged `budget_exhausted` in diagnostics instead of a real render.
**Why:** naive planning would call Phase 5 + Phase 6 (which renders real bounded audio previews) for every ordered pair considered by the search, which is combinatorially unaffordable for anything beyond a handful of tracks and was explicitly flagged as a risk to guard against.
**Rejected:** exhaustive pairwise audition; caching only by `(source_id, target_id)` (rejected because it would silently ignore genuine technique-memory-driven differences in what Phase 5 offers at different points in a path).

## D035 - Set-level validation metrics are computed independently of the internal weighted objective
**Decision:** `measure_set_quality` (energy-arc error, peak-placement error, BPM-jump statistics, consecutive-vocal-heavy count, technique-repetition stats, artist-spacing violations, viable-audition-edge rate, mean selected-audition score, hard-rejection rate) is a standalone function over `(tracks, edges, arc)` that does not call or re-derive `SetDirectorConfig.weights` or the per-edge `_score_edge_components` scoring function. `compare_to_shuffled_baselines` calls this same independent function for both the planned order and every shuffled order.
**Why:** the user's brief explicitly warned against the circular-validation failure mode of "optimize `SetDirectorScore`, then evaluate using `SetDirectorScore`, then declare victory." Independent, human-interpretable facts are required so the shuffled-baseline gate proves something outside the scoring policy itself.
**Rejected:** reusing `_score_edge_components`'s output as the validation metric.

## D036 - The shuffled-baseline gate uses a neutral technique-memory context
**Decision:** `compare_to_shuffled_baselines` audits every shuffled ordering's edges under one fixed neutral `CandidateSetContext` (no technique-memory chain, `energy_goal=0.0`, `set_phase="DEVELOP"`), rather than replaying each shuffle's own positional context the way real planning would.
**Why:** this collapses each shuffle's edge cache keys down to plain `(source, target)` pairs, so many seeded shuffles of the same track pool mostly hit the cache instead of re-rendering, keeping "many deterministic seeded shuffled baselines, not one cherry-picked shuffle" affordable. The tradeoff is documented in code and in `ACTIVE_HANDOFF.md`: this makes `mean_selected_audition_score` a weaker discriminator when a library's BPM/key/vocal properties are held constant, since technique-family selection then depends more on context than on genuine transition quality differences.
**Rejected:** replaying full positional context per shuffle (correct but multiplies the render count by the technique-memory state space per shuffle, defeating the cache).

## D037 - Tempo-hypothesis matching requires genuine closeness, not just "least bad of three"
**Decision:** `bpm_relationship`'s half/double (or other non-primary) hypothesis match is only accepted when its delta is within `hypothesis_match_threshold_pct` (default 8%) of the source BPM. Otherwise the pair is reported as a primary-tempo relationship at the raw delta, even if a hypothesis was nominally "closer than primary."
**Why:** without this bound, two BPMs that are unrelated by any reasonable musical standard (e.g. 72 and 101) could still resolve to a spurious "half/double" label merely because 101's half (50.5) happens to be arithmetically closer to 72 than 101 itself is — silently misreporting a real tempo jump as a safe relationship.
**Rejected:** always picking the arithmetically closest of primary/half/double regardless of absolute closeness.

## D038 - Phase 8 bridges Set Director into the application without touching the legacy plan/render pipeline
**Decision:** `LocalAppService` gets an entirely separate Set Director bridge (`start_set_director_plan`, `set_director_plan_view`, `set_director_handoff_view`, `lock_set_director_candidate`, `render_set_director_preview`) and its own `/api/set-director/...` routes and UI panel, rather than making `plan_set_v2` a new `performance_style` option inside the existing `start_plan`/`plan_view`/`start_render` path.
**Why:** the existing plan/render pipeline is built entirely around `SetPlan`/`TransitionPlan`/`PerformanceTimeline` (V1/V9/V14 models) and a full-mix renderer that consumes them. Set Director's output (`SetDirectorPlan`/`HandoffSummary`/`TransitionCandidate`) is a different shape with no full-mix renderer behind it yet. Forcing it through the existing view/render functions would require either a lossy adapter or premature design of a full-mix Candidate-Composer-recipe renderer. A parallel bridge keeps both paths simple and correct; unifying them is a decision for whichever future phase actually builds full-mix rendering from Set Director's chosen recipes.
**Rejected:** adapting `SetDirectorPlan` into the existing `SetPlan`/`plan_view` shape now.

## D039 - `HandoffSummary` retains the real audited `TransitionCandidate` objects, not just IDs
**Decision:** `HandoffSummary.candidates: dict[str, TransitionCandidate]` (added in Phase 8, additive to the Phase 7 dataclass) holds every candidate that was actually audited for that edge, keyed by candidate ID.
**Why:** the Transition Inspector needs each candidate's technique family, intended role, and generation reason -- not just the winner's -- and a future full-mix renderer will need the actual `PerformanceRecipe` behind whichever candidate a session (or a user's manual lock) selects. Re-deriving candidates by replaying `compose_transition_candidates` with the exact original context is possible but fragile and wasteful; keeping the already-computed objects is simpler and guaranteed consistent with what was actually audited.
**Rejected:** re-composing candidates on demand from stored context metadata.

## D040 - Manual candidate locks are an inspection-level override, not a re-plan
**Decision:** `lock_set_director_candidate` only changes which already-audited candidate is treated as "selected" for display/export purposes at one handoff (recorded in an `overrides` map on the stored plan record). It does not re-run the beam search, does not change technique-memory context for downstream handoffs, and does not require the locked candidate to have been the audition winner.
**Why:** a full re-plan honoring a lock as a hard constraint (and propagating its effect on technique-memory/energy-arc context to every later handoff) is a substantially larger feature -- effectively re-running Phase 7's search with pinned edges -- and was out of scope for this phase's "user can understand and override" gate, which only requires the user's choice to visibly take effect. This is called out explicitly in `IMPLEMENTATION_PLAN.md` and `STATE.md` as a scoping decision, not hidden as if full replanning already happened.
**Rejected:** silently re-running the full search on every lock (too slow for an interactive UI action and out of scope this phase); pretending a re-plan happened when it did not.

## D041 - Technique-family feedback reuses V1's `transition_ratings` table rather than a new one
**Decision:** Set Director technique-family feedback (Phase 9) is stored via the exact same `PreferenceProfile.rate_transition`/`get_preferred_transition_types` methods and `transition_ratings` SQLite table that V1's classic planner already uses, passing a technique-family string (e.g. `"drum_bridge"`) in the same `transition_type` column V1 uses for its own `TransitionType.value` strings.
**Why:** the column is free-text (not a SQL enum/check constraint), and the underlying concept -- "how much does the user like this style of transition" -- is identical across V1 and V2 vocabularies. Reusing proven, tested storage and read paths avoids a schema migration, avoids a second near-duplicate table, and means the existing `/api/preferences` endpoint and its UI display Set Director feedback with zero new code.
**Rejected:** a new `technique_family_ratings` table mirroring `transition_ratings`' schema.

## D042 - Personalization is expressed as one new weighted objective component plus a shortlist adjustment, not a hidden multiplier
**Decision:** learned technique-family preference and liked/disliked-track signal are combined into one new, transparent `user_preference` component (weight 0.06, taken from rebalancing the other eight so the total still sums to 1.0) in `_score_edge_components`, plus a liked/disliked adjustment inside the existing cheap shortlist heuristic (`_shortlist_next_tracks`) -- mirroring exactly how artist-spacing avoidance already works in both places in Phase 7.
**Why:** Phase 7 deliberately built the objective as "small, configurable, decomposed... expose component diagnostics" specifically so a future signal like this could be added without inventing a parallel, opaque scoring path. Keeping personalization as one named, independently-inspectable component (visible in `SetDirectorPlan.component_totals` and every edge's `component_scores`) preserves that transparency instead of silently rescaling other components or hiding the effect inside `handoff_quality`.
**Rejected:** folding preference into the existing `handoff_quality` (Phase 6 audition) score, which would conflate "this candidate technically sounds good" with "this user has said they like this technique" -- two genuinely different kinds of evidence Phase 6/7 already took care to keep separate.

## D043 - `SetDirectorConfig.technique_preferences`/`liked_track_ids`/`disliked_track_ids` are injected data, not a DB dependency
**Decision:** `djenius/core/set_director.py` gains three new fields that hold already-computed preference data (plain dicts/frozensets), populated by the application layer (`LocalAppService._set_director_learned_preferences`) before constructing `SetDirectorConfig`. `set_director.py` itself never imports `PreferenceProfile` or touches SQLite.
**Why:** preserves the module's existing purity (every dependency is either a pure function or an injected callable/`AudioProvider`), which is exactly what made it straightforward to unit-test Phases 7-9 without any database fixture. The application layer remains the only place that talks to persistent storage, consistent with the rest of `LocalAppService`'s existing design.
**Rejected:** having `set_director.py` read the preference database directly.

## D044 - Full-mix rendering corrects cross-edge anchor conflicts by shifting, not failing
**Decision:** `djenius/audio/set_director_renderer.py` detects when a shared middle track's compiled source-exit point (chosen independently for the edge where it is the source) lands earlier than where the previous edge already consumed that track (as its target), and shifts the transition to start exactly at that boundary -- preserving the technique's overlap duration and DSP untouched, only moving its absolute position in the track. The shift amount is recorded in that handoff's render provenance (`anchor_shift_sec`) rather than hidden.
**Why:** Phase 5's `_choose_anchor` picks a track's entry/exit point per edge in total isolation, scored by cue quality (confidence, mix-in/out score, downbeat, drop-landing) with track position only a tie-breaker -- a reasonable policy for a single edge, but with no guarantee that a middle track's two independently-chosen anchors land in timeline order once multiple edges are stitched together. This was never exposed before Phase 10 because nothing earlier needed cross-edge timeline consistency (Phase 6 renders one bounded preview at a time). Confirmed to occur on real music, not only synthetic fixtures, in the very first real full-mix render attempted. Failing the whole mix over what is usually a few seconds of independently-reasonable disagreement would make full-mix rendering unusable for most real multi-track plans; a small, transparent, provenance-tracked shift keeps the mix continuous and correct without touching Phase 5's frozen, extensively-tested anchor-selection logic.
**Rejected:** (a) hard-failing the whole mix on any such conflict -- too fragile for real multi-track sets, confirmed by testing; (b) re-deriving the conflicting edge's candidate from scratch with a "not before this timestamp" constraint threaded through Set Director's search -- correct in principle, but would require Candidate Composer to accept path-dependent constraints and would break Phase 7's edge-caching model (edges are currently cacheable independent of which path reached them); a substantially larger change deferred to a future phase if the shift-based fix proves insufficient in practice.

## D045 - Locking a hard-rejected candidate is now explicitly refused
**Decision:** `lock_set_director_candidate` (Phase 8) now raises `ValueError` if the requested candidate's audition was hard-rejected, instead of accepting any candidate id present in the handoff.
**Why:** building the full-mix renderer's own hard-rejection guard made it obvious the existing lock endpoint had no equivalent check -- a user could lock a candidate the renderer would then correctly refuse to render, an avoidable dead end. Small, directly motivated by Phase 10 work already touching this exact code path; not a speculative hardening pass.
**Rejected:** leaving the gap and only handling it at render time (the user would discover the mistake later, at render, instead of immediately when locking).

## D046 - Track appearances are path-dependent Set Director state
**Decision:** Set Director schema 7.1 carries a typed `TrackAppearance` for each track and passes its entry-consumption point plus minimum establishment window to Candidate Composer as a `SourceAppearanceConstraint`. The constraint participates in the edge-cache key, and candidate anchors/durations that would start the next transition too early are rejected during composition. The renderer's D044 anchor shift remains only for backward compatibility with legacy or manually assembled plans.
**Why:** independently valid A→B and B→C handoffs do not imply a coherent appearance for B. The previous render-time shift could prevent overlap corruption but could not plan establishment, useful independent airtime, or a musically ordered entry→feature→exit story.
**Supersedes:** D044 as the policy for newly planned sets; D044 remains the compatibility behavior at the renderer boundary.

## D047 - Phase-5 expressive families compile two-deck choreography, not labels over legacy fades
**Decision:** Phase-5 EQ blend, drum bridge, loop shortening, and riser/impact recipes compile an explicit `mix_choreography` operation. The renderer executes deliberate bass ownership, build holds, arrangement pockets, and phrase landings; Phase-2/3 behavior remains frozen for backward compatibility.
**Why:** the controlled real-audio lab proved that the old riser/impact output was almost identical to plain crossfade despite correct names/actions. Typed actions are only meaningful if the final two-deck envelope embodies the move.
**Rejected:** globally increasing FX gain or changing frozen recipe behavior.

## D048 - Target cursor advance follows audible splice semantics
**Decision:** preview, Set Director duration planning, and full-set rendering share `target_cursor_advance_samples`. Phrase cut advances only past its click-safe seam; ordinary overlaps advance by their rendered target consumption, including time-stretch semantics.
**Why:** the former phrase-cut path rendered mostly outgoing audio but skipped an entire multi-bar interval of the incoming track afterward, contradicting the declared landing and corrupting duration/appearance bookkeeping.

## D049 - Required stems remain attached through the production full-set path
**Decision:** the application provider loads available cached stems into `TrackAudio`; full-set rendering slices and validates the source/target stem windows and passes them into transition DSP. Required-stem absence is an explicit render error, never a silent sophisticated-family-to-crossfade downgrade.
**Why:** a stem handoff that only works in an isolated lab but cannot receive stems from the application is not a production implementation.

## D050 - Audition damage metrics are bounded by declared technique intent
**Decision:** Audition Lab's spectral metric retains universal collision/mud/hole protection but applies small family-specific allowances to continuity movement and expected high-frequency buildup for techniques that deliberately restructure frequency space. Excess beyond those bounds is still penalized, and no score-only creativity bonus is added.
**Why:** a riser, filter move, phrase cut, bass handoff, or stem mashup should not lose solely because it performed its declared safe transformation. The evaluator must distinguish intended behavior from the same change appearing in a family that did not declare it.

## D051 - Approved performances become explicit templates before autonomous choices resume
**Decision:** the F, C3, B8, and D2 human references are frozen by SHA-256 and represented by four explicitly selected, deterministic `TrackAnalysis`-to-`PerformanceRecipe` templates. The new layer cannot choose a template and is not connected to Candidate Composer, Audition Lab policy, Set Director, UI, or full-set rendering until same-pair automated reconstructions pass human listening.
**Why:** automation must first reproduce proven musical behavior. Separating instantiation from selection prevents ranking or planning changes from concealing a failure to reproduce the accepted choreography.

## D052 - Reference templates own a coherent target clock and explicit tail contract
**Decision:** every beatmatched reference template renders its target master and participating stems together through one multichannel timing/stretch operation spanning runway and postlanding material. Source effects crossing landing retain their buffer state and declare an auditable endpoint; other templates must clear their effect before landing.
**Why:** the B7/B8 investigation proved that independently stretched target material and restarted source-loop state were audible renderer defects. They are permanent invariants, not optional artistic parameters.
