# DJenius V2 State

## CURRENT PHASE
Phase 8 - UI V2 (Set Director inspection slice): **COMPLETE / READY TO FREEZE**. Phase 9 - Personalization is the exact next implementation phase only after the Phase 8 privacy gate, commit, push, and local/remote HEAD verification.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## PREVIOUS FROZEN COMMIT
`4fd29e6e63486e4b15c50167279bdeb03377a83a` - `Add V2 set director` (Phase 7; a small `026d2a4` handoff-doc-only commit followed it, still Phase 7).

## WORKING TREE STATE
Phase 8 production code (`djenius/audio/track_audio.py`, additions to
`djenius/application.py`/`djenius/web/app.py`/`djenius/web/static/*`, and one
additive field on `djenius/core/set_director.py`'s `HandoffSummary`), a
dedicated backend test, and durable documentation are complete locally and
awaiting the final privacy/diff gate, coherent commit, push, and
local/remote HEAD verification. No private track data enters Git; manual
real-browser verification used the same real, already-gitignored `testMusic/`
library the Phase 7 real-music gate used, and only aggregate/structural
observations were written to any tracked file.

- Base V1 commit: `efcfcca6d21aeaa595b236306b025b70668106fd`.
- V1 master remains unchanged.

## COMPLETED WORK
- Phases 0-7 are frozen; Phase 7 is pushed at `4fd29e6e63486e4b15c50167279bdeb03377a83a`.
- Phase 8 bridges Set Director (Phase 7) into the actual running application for the first time -- through Phase 7, `plan_set_v2`/Candidate Composer/Audition Lab were only reachable from tests and throwaway scripts, never from the app a user actually runs.
- New `djenius/audio/track_audio.py`: shared robust stereo audio decode (soundfile -> librosa -> ffmpeg fallback tiers) feeding Set Director's `AudioProvider` from real library files.
- `LocalAppService` gains a parallel Set Director bridge (`start_set_director_plan`, `set_director_plan_view`, `set_director_handoff_view`, `lock_set_director_candidate`, `render_set_director_preview`) and `djenius/web/app.py` gains `/api/set-director/...` routes, entirely additive to the existing V1/V9/V14 plan/render pipeline (D038).
- `HandoffSummary` (Phase 7) gained one additive field, `candidates: dict[str, TransitionCandidate]`, retaining the real audited candidate objects (not just the winner's ID) so the Transition Inspector and any future full-mix renderer can use them directly (D039).
- New "Set Director" panel in the local web UI: set-arc selector, target duration, a creativity control (safe/balanced/creative), a track-trajectory view (BPM/key/energy per position), the nine Phase 7 objective components rendered transparently, a handoffs list, and a Transition Inspector modal per handoff (every audited candidate with score/rank or an honest hard-rejection reason, an in-browser audio preview player rendering the real bounded preview, and a "use this instead" manual lock that updates the plan record, not just the display) (D040).
- Incidental fix: a pre-existing dead-code bug in `djenius/web/static/app.js` (`renderPerformancePlan` referenced but never defined) threw on every page load and silently prevented the V9/segment-performance appearance-reorder buttons from ever being attached. Fixed by rebinding onto the actual `renderPlan` symbol. Also added `Cache-Control: no-store` on `/` and version query strings on static assets to prevent this class of stale-JS confusion going forward.

## TEST RESULTS
- New backend test: **1 passed** (`test_set_director_plan_inspect_lock_and_preview`), full HTTP flow against the real FastAPI app with real (tiny synthetic) audio.
- Complete repository regression: **1080 passed** (1079 at the Phase 7 checkpoint + 1), with the same 2 known Typer/Click dependency deprecation warnings and no asynchronous timeout failures.
- `ruff check` clean on every new/changed file (one pre-existing, unrelated unused-import warning in `application.py` predates this phase).
- Manual end-to-end verification via an actual browser against the real local app and the real anonymized `testMusic` library: scan/analyze -> plan a Set Director journey -> trajectory/component/handoff views render real data -> Transition Inspector shows real ranked survivors and honestly-labeled hard rejections -> real audio preview plays in-browser -> manual lock updates both the inspector and the trajectory view live and is confirmed persisted server-side. The pre-existing classic (non-Set-Director) plan UI was also re-verified working after the shared `renderPlan` bugfix. Full narrative in `BENCHMARK.md`; no private track data recorded.

## KNOWN LIMITATIONS / TECHNICAL DEBT
- Full continuous full-mix rendering of a Set-Director-planned set is not wired this phase; only bounded per-handoff preview rendering is exposed through the UI. `HandoffSummary.candidates` retains what a future full-mix renderer would need.
- Manual candidate locks are an inspection-level override (change what is displayed/exported as "selected" for one handoff) rather than a full re-plan honoring the lock as a hard constraint across the rest of the set (D040).
- Graphical waveform visualization and a bar/action-level performance-timeline widget (research spec section 24.2/24.5) are not implemented; textual generation reasons and human-readable plan reasons cover explainability instead.
- Stem-dependent candidates (e.g. `stem_handoff`) correctly hard-reject in the Transition Inspector with an honest reason rather than crashing, since this phase's audio bridge does not load/decode separated stems.
- All Phase 7 known limitations (forced zero-survivor handoffs on a small library, `mean_selected_audition_score` as a weak discriminator in some constructions, inherited Phase 5/6 deferred metrics, and the general "beats shuffled baselines is not the same as professional human DJ quality" caveat) still apply unchanged.

## CURRENT BLOCKERS
None for freezing Phase 8. Phase 9 - Personalization needs structured listening feedback that changes future technique/candidate selection predictably; the existing V1 feedback endpoints (`/api/feedback/*`) and preference store are a starting point, but nothing yet feeds Set Director's technique/candidate choices.

## EXACT NEXT ACTION
Run the Phase 8 privacy/diff gate over the exact tracked/untracked change set (confirm nothing under `testMusic/`, `*.db`, `/tmp`, `.claude/`, or any real track name entered the tracked set). If clean, stage the Phase 8 files, commit as `Add V2 Set Director UI`, push `origin/v2-professional-autonomous-dj`, and verify clean working tree plus exact local/remote HEAD equality. Only then begin Phase 9 - Personalization.
