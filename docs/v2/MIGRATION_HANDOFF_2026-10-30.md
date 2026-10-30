# DJenius V2 — Migration and Future Development Handoff (2026-10-30)

**Repository:** https://github.com/danielnrz/DJenius
**Development branch:** `v2-professional-autonomous-dj` (do not assume default `master` is the latest V2)
**Last code/research checkpoint prior to this documentation:** `437ba877c407e8910ec84ad376439eb406030cf7` (2026-09-21).
**Purpose of this document:** reproducible cross-machine recovery and exact re-entry for a future Codex/Claude agent. This is *documentation only*; no model/renderer behavior was changed by creating it.

## What this project is

DJenius is a locally run DJ-mix and autonomous-performance research application. It scans/analyzes personal music, models BPM, beats, sections, key, vocals, energy and other musical cues, plans a set and renders audio. The normal Python CLI/FastAPI browser app includes classic mixing, segment performances, and V2 composition/audition/Set Director functionality. A later, **separate research path** supports four reference-backed transition archetypes (F, C3, B8, D2), constrained set planning, rhythmic-ownership experiments, and human listening comparisons. That reference-backed path is **not fully wired into the normal app**.

Core design goal: produce compelling, deliberate DJ performances, not merely technically compatible crossfades or passes on numeric metrics.

## Accurate completion picture

- V2 Phases 0–7 and 9 have historical documented technical acceptance.
- Phase 8 delivered a partial inspection/preview UI; a complete editing timeline is absent.
- Phase 10 provided continuous full-set rendering and technical evidence; the global professional-quality human acceptance gate **did not pass**.
- Later four-archetype reference experiments achieved bounded human positives, but autonomous *when/what/why* and whole-set storytelling remained unreliable.
- Most recent handoff described two final blind A/B comparisons as sealed and pending listening; their private `/tmp/djenius_reference_dj_transition/forensic_batch/` audio/scripts had disappeared by 2026-10-30. Written descriptions are not a substitute for the missing artifacts.
- Measured transition-to-native-tempo steps can reach about 5.04%; one such audible step received *positive* human feedback. Do not mechanically remove all tempo changes.

Authoritative detail: `docs/v2/ACTIVE_HANDOFF.md` (newest entries at top); `docs/v2/AGENT_PROTOCOL.md`; `docs/v2/DECISIONS.md`; `docs/v2/BENCHMARK.md`; `docs/v2/IMPLEMENTATION_PLAN.md`.

## Migration snapshot facts (observed 2026-10-30, before the handoff commit)

- Branch: `v2-professional-autonomous-dj`; HEAD `437ba87`, matched the locally recorded `origin/v2-professional-autonomous-dj` tracking ref.
- Source files had no tracked local modifications. Existing untracked `.claude/launch.json` was intentionally **not** added to GitHub.
- Three Git stashes were present, from Sep 5, Sep 7, and Sep 20. Preserve them; never automatically pop/apply them.
- The personal offline workspace contained `testMusic/`, `stems/`, `output/`, `outputs/`, `data/`, the root SQLite analysis cache, `.venv/`, `.git/`, `.codex_handoff/`, and other ignored items.
- The base CLI/app analysis cache `data/analysis_cache.db` had 17 current-version analyses, while the expanded-library root `djenius_cache.db` had 162; **do not replace one with the other**.
- FFmpeg was installed on the source host; Rubber Band was not on PATH. The saved venv had Python 3.13.9 and core packages, but appeared to lack optional Torch, Demucs and Transformers. The venv is a *reference artifact*, not a portable install.
- The original `/tmp/djenius_reference_dj_transition/` path was absent; the main repo and Desktop filename scan found no final forensic audio. Do not mark those artifacts recovered.
- The GitHub repository was observed to be **PUBLIC**. No private music/research audio or cache data should be pushed.

## GitHub versus offline backup

**GitHub** is for source code, public-safe agent instructions, architecture, anonymized benchmarks, tests and Git history. The active V2 branch is intentionally kept separate from master. Never push the external-drive private backup or content from ignored folders.

**The external-drive snapshot** is the recovery authority for private music, stems, output WAVs, caches, local notes, untracked files, historical stashes and Git metadata. See `README_RESTORE_FIRST.md` in the external migration folder and the SHA256 manifest. A Git clone alone does not recreate the working research system.

## Recovery on Linux / new computer

1. First verify the external media and manifest hashes. Create sufficient free disk space for the archive and extraction.
2. Extract the **full project archive** onto a Linux-native filesystem (ext4/btrfs/APFS where appropriate). Do **not** extract a working Git directory directly onto exFAT; symlinks and POSIX metadata may be lost.
3. Inspect `git status --short`, `git branch -vv`, `git stash list`, `git log -1`, and the contents of the two SQLite caches before starting services. The snapshot will contain the historical Git repository and should preserve its stash objects.
4. Rebuild `.venv` using the new system's Python (3.11+) and the checked-in `pyproject.toml`; do not assume the copied `.venv` will run on a different machine. Install FFmpeg and optionally Rubber Band. Optional Demucs/CLAP/Whisper/Ollama require separate setup and model availability checks.
5. For a controlled baseline, use a disposable project copy and isolated output/cache/model directories, not the frozen restored reference. Historical run count of 1,173 passing tests is **not** a fresh verification.
6. The established app can be launched (only after preservation/validation) with `djenius app` and viewed at `http://127.0.0.1:8765`. The CLI uses `djenius scan`, `analyze`, `plan`, `mix`, `auto`. These are established-mixer entry points and do not imply full integration of reference-backed research.
7. Ask for human listening only on **controlled, level-matched** rendered comparisons, preserving blind condition labels and private provenance.

### No-backup fallback

If only GitHub is available, clone it and `git switch v2-professional-autonomous-dj`. This recovers tracked code and documents, **not** private audio, caches, stashes, experiments, ignored reports, or the original running environment. This is a partial recovery, not a restored lab.

## Next engineering sequence

1. Preserve/verify the private migration snapshot and check for any old experiment export elsewhere (no destructive searches).
2. Build a clean, testable new-machine environment in isolation; record package versions and deterministic test results.
3. Restore both analysis caches as separate files and document which workflow consumes each. Check reference-backed invocation separately from the app.
4. Recover or regenerate the two independent final A/Bs: transition-only versus persistent tempo state, and four- versus eight-bar rhythmic ownership. Maintain identical controls and render parameters.
5. Use actual human listening outcomes to decide **when to perform vs. do nothing**, with controlled context and no unexplained FX.
6. Integrate demonstrated research improvements into the supported app incrementally, with technical, safety, and real-audio acceptance. Do not jump into another broad roadmap phase.

## Agent operational discipline

Read root `AGENTS.md` and `docs/v2/AGENT_PROTOCOL.md` before implementation. Respect branch invariants, privacy rules, provenance, private data separation and human quality gates. Avoid rewriting the historical `ACTIVE_HANDOFF.md` introduction as though old experiments were still available; record new dated findings explicitly.

**Checkpoint status:** migration preparation only. No claims of new test passes, professional listening approval, or repaired tempo behavior are made here.
