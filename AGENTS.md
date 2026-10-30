# DJenius Agent Onboarding (Codex / Claude)

This repository is a local, research-oriented autonomous DJ system. **Do not assume a green test suite proves professional musical quality.**

## Start here, in this order
1. `docs/v2/MIGRATION_HANDOFF_2026-10-30.md` (migration checkpoint, limitations, recovery).
2. `docs/v2/AGENT_PROTOCOL.md` (binding agent safety/privacy and quality rules).
3. `docs/v2/ACTIVE_HANDOFF.md` (most recent detailed musical investigation, read newest sections first).
4. `docs/v2/DECISIONS.md`, `docs/v2/STATE.md`, `docs/v2/IMPLEMENTATION_PLAN.md`, `docs/v2/BENCHMARK.md`.
5. `docs/v2/DJENIUS_V2_RESEARCH_SPEC.md`, relevant source, tests, and Git history.

## First session on a new computer
- Inventory the current Git branch, HEAD, working tree and available archives before doing anything destructive.
- The active research branch is `v2-professional-autonomous-dj`, **not** default `master`.
- Restore the private offline migration archive before expecting music, stems, databases, or saved audio experiments. Those are intentionally **absent** from GitHub.
- Never reset, clean, pop/apply a stash, merge, rebase, force push, or overwrite a cache to 'fix' setup without explicit approval. Preserve the three recorded historical stashes.
- Treat `data/analysis_cache.db` and root `djenius_cache.db` as distinct research artifacts. Preserve both; do not merge blindly.
- Assume historical `/tmp/djenius_reference_dj_transition/` experiment audio/scripts are **missing** unless independently recovered from backups.
- Establish an isolated, reproducible environment and run tests in a disposable copy before altering DSP/planner behavior.
- Never commit/push private audio, stems, model weights, databases, credentials, lyrics, private reports, or real-track identities.
- Preserve the distinction between the regular app pipeline and the later reference-backed research pipeline; do not claim they are integrated.

## Immediate scientific/engineering objective
Reconstruct the outstanding blind listening comparisons for **tempo continuity** and **rhythmic ownership persistence**, then decide whether an intervention is musically needed. Tempo changes are not inherently defects: a measured change was positively reviewed. Do not start a broad redesign, new archetype, or a nominal 'Phase 11' without evidence.

At every session end, update the durable handoff with exact commands, state changes, tests, real-audio evidence, caveats, and next actions.