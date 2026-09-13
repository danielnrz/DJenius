# DJenius V2 State

## CURRENT PHASE
Phase 10 - Certification: **AUTONOMOUS PORTION COMPLETE**. The phase's actual
defining gate -- a blind V1-vs-V2 human listening comparison with a human
scorecard -- requires the user directly and has not happened. Ready to run
the privacy/diff gate, commit, and push the autonomous work; V2 is not
"done" until the human gate completes.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## PREVIOUS FROZEN COMMIT
`4f71818e2f2613d14db184c23901f43474ce04fd` - `Add V2 personalization` (Phase 9; a handoff-doc-only follow-up landed at `191dd40`).

## WORKING TREE STATE
Phase 10 production code (`djenius/audio/set_director_renderer.py`,
additions to `djenius/application.py`/`djenius/web/app.py`/
`djenius/web/static/*`), dedicated tests, and durable documentation are
complete locally and awaiting the final privacy/diff gate, coherent commit,
push, and local/remote HEAD verification. A real full-mix WAV rendered
during manual verification was delivered directly to the user (not written
to any tracked path); the private transition-benchmark script and its
anonymized JSON results live only under `/tmp/djenius_phase10_smoke`.

- Base V1 commit: `efcfcca6d21aeaa595b236306b025b70668106fd`.
- V1 master remains unchanged.

## COMPLETED WORK
- Phases 0-9 are frozen; Phase 9 is pushed at `4f71818e2f2613d14db184c23901f43474ce04fd` (handoff-doc-only follow-up at `191dd40`).
- New `djenius/audio/set_director_renderer.py::render_set_director_mix`: the first capability able to render an entire Set-Director-planned set into one continuous mix file, closing the gap Phase 8 explicitly deferred. Reuses the exact proven Phase 6 compile -> apply_transition -> splice pattern, just with full-track "before"/"after" windows instead of a bounded preview window.
- Discovered and fixed, on real music (not only synthetic fixtures): Phase 5 chooses each edge's anchors independently, so a shared middle track's target-entry point and its own later source-exit point are not guaranteed to land in timeline order. The renderer detects this and shifts the affected transition to start exactly where the previous edge ended, tracked transparently via `anchor_shift_sec` in provenance (D044).
- `LocalAppService.start_set_director_render` (background job) + `POST /api/set-director/plans/{plan_id}/render`, and a "Render full mix" button in the Set Director UI that hands the result to the existing "Now Playing" player -- no new playback UI needed.
- Small, directly-motivated hardening fix: `lock_set_director_candidate` now refuses to lock a hard-rejected candidate (D045), a gap the renderer's own guard made obvious.
- A private difficult-pair transition benchmark (research spec 30.4) classified every real pair in the existing anonymized 12-track library into the specification's 15 categories and ran one representative real pair per populated category through Candidate Composer + Audition Lab; full anonymized results in `BENCHMARK.md`.
- A real, technically-verified ~4:11 continuous V2 mix from 3 real tracks was rendered through the actual app and delivered directly to the user -- the first real artifact ready for their own blind listening comparison.

## TEST RESULTS
- Dedicated Phase 10 suite: **6 passed** (`tests/test_v2_phase10_certification.py`).
- One new `test_app.py` case: full HTTP render flow (plan -> render -> play -> confirm output metadata) plus a 404 check.
- Complete repository regression: **1092 passed** (1085 at the Phase 9 checkpoint + 7), same 2 pre-existing Typer/Click deprecation warnings, no async timeout failures.
- `ruff check` clean on every changed file (one pre-existing, unrelated unused-import warning in `application.py` predates this phase).
- Manual real-browser verification: planned a real 3-track set, rendered it into one continuous WAV through the actual UI, and verified the file directly (finite, -14.8 dBFS RMS, negligible clipping, correct duration). Delivered to the user. Full narrative in `BENCHMARK.md`.

## KNOWN LIMITATIONS / TECHNICAL DEBT
- **The Phase 10 defining gate is not met.** Everything autonomously achievable is done; the blind V1-vs-V2 human listening comparison with a human scorecard has not happened and cannot happen without the user.
- A real, specific, actionable gap surfaced by the transition benchmark: for vocal-heavy real pairs, Candidate Composer can currently generate zero surviving candidates (confirmed on two real representative pairs, auditioning every generated candidate). There is no minimal-risk fallback family (e.g. a restrained equal-power crossfade) guaranteed feasible regardless of vocal/loudness conditions. Set Director's own search would generally avoid placing such a pair adjacent when better alternatives exist, but a future phase should consider adding such a fallback family to Phase 5's repertoire.
- The anchor-shift fix (D044) is a pragmatic, transparent correction, not a full redesign of Phase 5's per-edge anchor independence; a future phase could instead make Set Director's search itself anchor-aware across adjacent edges, at the cost of Phase 7's current edge-caching simplicity.
- No V1-style baseline mix of the same real library was rendered this phase for a true side-by-side; the existing classic `/api/plans` + `/api/plans/{id}/render` path is unchanged and available whenever the user wants one.
- All Phase 7/8/9 known limitations (forced zero-survivor handoffs within a plan, `mean_selected_audition_score` as a weak discriminator in some constructions, inspection-level-only locks, no waveform/timeline visualization, inherited Phase 5/6 deferred metrics) still apply unchanged.

## CURRENT BLOCKERS
The single remaining blocker for calling V2 "done" per the research specification: the user's blind V1-vs-V2 listening comparison and scorecard. Nothing else in the roadmap is pending.

## EXACT NEXT ACTION
Run the Phase 10 privacy/diff gate over the exact tracked/untracked change set (confirm nothing under `testMusic/`, `*.db`, `/tmp`, `.claude/`, or any real track name entered the tracked set). If clean, stage the Phase 10 files, commit as `Add V2 full mix rendering`, push `origin/v2-professional-autonomous-dj`, and verify clean working tree plus exact local/remote HEAD equality. Then stop and wait for the user: offer to render a V1-style baseline of the same (or any) library and additional V2 mixes on request, but the actual blind comparison and scorecard are theirs to do.
