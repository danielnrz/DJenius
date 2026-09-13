# DJenius V2 Active Handoff

## LAST VERIFIED TIME
2026-09-13T15:10Z (updated after full end-to-end real-browser verification and all durable-doc updates for Phase 9)

## CURRENT PHASE
Phase 9 - Personalization: **COMPLETE**. Ready to run the privacy/diff gate,
commit, and push.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## LAST PUSHED COMMIT
`23a60951acafb32c69d168bb4a875e0931a5f0e9` - "Update handoff state after Phase 8 freeze push". Nothing has been pushed yet for Phase 9.

## LOCAL HEAD
`23a60951acafb32c69d168bb4a875e0931a5f0e9` (no commits made yet for Phase 9; all Phase 9 work is currently uncommitted in the working tree).

## REMOTE HEAD
`23a60951acafb32c69d168bb4a875e0931a5f0e9` (`origin/v2-professional-autonomous-dj`, matches local HEAD; no push has happened yet this phase).

## WORKING TREE
Not clean: Phase 9 changes are unstaged. `git status --short` currently shows:
```
 M djenius/application.py
 M djenius/core/set_director.py
 M djenius/web/app.py
 M djenius/web/static/app.js
 M djenius/web/static/index.html
 M djenius/web/static/styles.css
 M tests/test_app.py
?? .claude/                                    <- DO NOT COMMIT (session tooling)
?? tests/test_v2_phase9_personalization.py
```
No frozen Phase 0-8 core logic was rewritten; every Phase 9 change to
existing files is additive (new fields, new methods, new routes, new UI
elements appended to existing ones).

## CURRENT IMPLEMENTATION STATE
- `djenius/core/set_director.py`: `SetDirectorConfig` gained
  `technique_preferences: dict[str, float]` (family -> [0,1] preference,
  default `{}`, missing key = neutral 0.5), `liked_track_ids`/
  `disliked_track_ids: frozenset[str]` (default empty). `weights` gained
  `user_preference: 0.06`; the other eight weights were rebalanced down
  slightly so the total still sums to 1.0
  (handoff_quality 0.28->0.26, groove_continuity 0.08->0.06,
  technique_diversity 0.10->0.08, everything else unchanged).
  `EDGE_COMPONENTS` now includes `"user_preference"`.
  `_shortlist_next_tracks` applies a +0.08/-0.12 liked/disliked adjustment
  to its cheap per-track score (same scale as V1's own
  `liked_track_bonus`/`disliked_track_penalty`). `_score_edge_components`
  computes `user_preference` as
  `clip01(technique_preferences.get(selected_family, 0.5) + track_bonus)`
  where `track_bonus` is +0.15 if the handoff's target is liked, -0.20 if
  disliked. Module remains pure/DB-free (D043) -- these are just new plain
  fields the application layer populates.
- `djenius/application.py`: new `_set_director_learned_preferences()` reads
  `PreferenceProfile.get_preferred_transition_types(min_samples=2)` (mapped
  from [-1,1] to [0,1]) plus `get_liked_tracks()`/`get_disliked_tracks()`,
  and `_set_director_config(creativity)` now calls it and passes the result
  into every fresh `SetDirectorConfig`. New
  `save_set_director_feedback(plan_id, index, rating)`: resolves whichever
  technique family is *currently selected* (honoring a Phase 8 lock),
  reuses V1's exact rating-label vocabulary
  (`{"great":1.0,"good":0.7,"bad":-1.0,"too abrupt":-0.6,"too long":-0.4,
  "too weak":-0.3}` or a raw float), and calls
  `PreferenceProfile.rate_transition(source_id, target_id, family, score)`
  -- the SAME table/method V1's `save_transition_feedback` already uses
  (D041), so `/api/preferences`'s existing `preferred_transition_styles`
  and the Preferences tab already display it with no changes.
- `djenius/web/app.py`: new `SetDirectorFeedbackRequest` model and
  `POST /api/set-director/plans/{plan_id}/handoffs/{index}/feedback`.
- `djenius/web/static/index.html`/`app.js`/`styles.css`: new
  "Rate the technique used here" button row (Great/Good/Too abrupt/Bad) at
  the bottom of the Transition Inspector modal, wired to a new
  `rateHandoff(rating)` JS function. Cache-busting bumped to `?v=phase9-1`.
- New test file `tests/test_v2_phase9_personalization.py` (4 tests, pure
  `set_director.py`-level, no HTTP/DB). Two cases added/extended in
  `tests/test_app.py` for the full HTTP feedback flow and cross-plan
  learning.

## UNCOMMITTED FILES
See the `git status --short` block above. `.claude/` is session-local
Browser-preview tooling (also mirrored at
`/home/daniel/Documents/Programming/Music_Mode_Engine/.claude/launch.json`,
a different repository entirely) -- **never `git add` it**.

## TESTS COMPLETED
- Dedicated Phase 9 suite: **4 passed**
  (`pytest tests/test_v2_phase9_personalization.py -q`), covering: config
  validation now requires the `user_preference` weight key; a technique
  preference is reflected exactly in that component and produces the
  expected `total_score` ordering (liked > neutral > disliked) for a single
  forced edge (`beam_width=1`, to avoid a real subtlety documented below);
  a disliked track loses a controlled two-track choice to an
  otherwise-identical alternative; a liked track wins the analogous choice
  (both using `max_candidates_audited_per_edge=8` and `max_tracks=2` for the
  same reason, see "Known defects" below).
- `test_app.py -k set_director`: **2 passed** (one extended, one new),
  covering the full HTTP feedback flow and repeated feedback changing a
  freshly-built `SetDirectorConfig`'s `technique_preferences`.
- Complete repository regression: **1085 passed** (was 1080 at the Phase 8
  checkpoint), same 2 pre-existing Typer/Click deprecation warnings, no
  async timeout failures. Run twice (after implementation, again after doc
  edits) with identical results.
- `ruff check` on every changed Python file: clean except the same
  pre-existing, unrelated `application.py` `F401` from before Phase 7 (left
  alone, not introduced by this phase or Phase 8).
- Manual real-browser verification: opened the real Transition Inspector for
  a real handoff produced from the real `testMusic` library, clicked
  "★ Great", confirmed the toast
  ("Feedback saved: riser impact rated 'great'"), independently confirmed
  via a direct `fetch('/api/preferences')` that `preferred_transition_styles`
  now contained that family at `1.0`, and confirmed the *existing,
  unmodified* Preferences tab rendered it correctly -- no new frontend code
  was needed for that view since it already calls the same method Phase 9
  now also feeds.

## TESTS CURRENTLY RUNNING
None. The dev server used for manual verification was stopped
(`preview_stop`) before this handoff was written.

## TESTS STILL REQUIRED
None for the Phase 9 freeze itself.

## PRIVATE LOCAL ARTIFACTS
The manual browser verification read and wrote to this machine's real,
pre-existing `data/djenius_preferences.db` (already gitignored, not a new
path) -- it already contained real prior liked-track/mix-rating data from
actual past use of the app, confirmed only by hash-id counts, never by
title/artist, and none of that was written into any tracked file.

## KNOWN DEFECTS / OPEN QUESTIONS
- A real test-design subtlety was found while writing the dedicated suite:
  `TransitionCandidate` ids are content-hashed from (among other things) the
  source/target track ids. Two fixtures identical except for id can
  therefore have a *bounded* audition (`max_candidates_audited_per_edge`
  smaller than the full generated set) sample a genuinely different subset
  of the same underlying candidate pool, producing a real, non-preference
  difference in `handoff_quality` large enough to swamp a small preference
  signal. Worked around in tests by auditioning the full candidate set
  (`max_candidates_audited_per_edge=8`) when isolating a preference effect,
  and documented in `IMPLEMENTATION_PLAN.md`/`STATE.md` so a future agent
  doesn't rediscover this the hard way. Not a defect in the production code
  -- bounded sampling is exactly Phase 7's intended compute-cost control --
  just a real thing test authors must control for.
- Similarly, with more than `beam_width` tracks and ties at the opener slot,
  Set Director can explore a track's *reverse-direction* edge as a separate
  path (A->B and B->A can have different audition winners). Changing
  `technique_preferences` can therefore legitimately flip which whole path
  wins, not just an edge's score, when both directions are live options.
  This is correct behavior, not a defect, but means "does the SAME edge's
  score change" is a narrower and more reliable thing to test than "does
  track_ids[1] change" whenever more than one path is genuinely alive.
- Open product question (unchanged from Phase 8, D040): should a manual
  lock or a strong learned dislike eventually trigger a constrained re-plan
  rather than only affecting scoring/inspection? Still deferred to whichever
  future phase builds full-mix rendering.

## DECISIONS MADE THIS SESSION
Written to `DECISIONS.md` as D041-D043: (1) technique-family feedback reuses
V1's `transition_ratings` table rather than a new one; (2) personalization
is one new transparent weighted component plus a shortlist adjustment, not a
hidden multiplier or a fold into an existing component; (3)
`SetDirectorConfig`'s new preference fields are injected plain data,
preserving `set_director.py`'s existing DB-free purity.

## DO NOT REDO
- Do not redesign the personalization mechanism -- implemented, tested
  (pure unit tests + full HTTP flow + real-browser verification), and
  passing full regression.
- Do not add a new preferences table/schema for Set Director -- the reuse
  of V1's existing `transition_ratings` table is deliberate (D041).
- Do not re-run the manual browser verification again this session -- it
  already produced the results now recorded in `BENCHMARK.md`.

## EXACT NEXT ACTION
Run the Phase 9 privacy/diff gate (`git status`, `git diff` review --
confirm nothing under `testMusic/`, `*.db`, `/tmp`, `.claude/`, or any real
track name entered the tracked set). If clean, stage exactly the 9 files
listed under "Uncommitted files" (NOT `.claude/`), commit as
`Add V2 personalization`, push `origin/v2-professional-autonomous-dj`, and
verify clean working tree plus exact local/remote HEAD equality. Only then
consider Phase 10 - Certification -- and note explicitly to the user that
its defining gate (a blind V1-vs-V2 human listening comparison) needs their
direct participation and cannot be completed autonomously; everything else
in Phase 10 (full automated suite, private real-track benchmarks, multiple
full real sets) can be prepared autonomously, but the phase cannot be
declared complete without that human step.

## SAFE RECOVERY NOTES
- Every file change this session is additive to an existing file or a new
  file; no frozen Phase 0-8 behavior was rewritten.
- If you are a fresh agent picking this up: re-run `git fetch && git status
  --short && git log -1 --format='%H %s'` and compare against the HEAD SHAs
  recorded above before trusting this file. Then run `python -m pytest -q`
  to confirm the full regression still passes before committing.
