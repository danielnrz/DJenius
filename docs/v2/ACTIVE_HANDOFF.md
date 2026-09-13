# DJenius V2 Active Handoff

## LAST VERIFIED TIME
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
