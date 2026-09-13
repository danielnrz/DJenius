# DJenius V2 Multi-Agent Protocol

This file is PUBLIC-SAFE and durable. It defines the stable rules every future
coding agent (Claude, GPT/Codex, or otherwise) must follow when resuming work
on DJenius V2. It does not change per session; session-specific state belongs
in `ACTIVE_HANDOFF.md`.

## 1. Repository and branch

- Repository: `/home/daniel/Documents/Programming/DJenius` (origin:
  `https://github.com/danielnrz/DJenius.git`).
- Active branch: `v2-professional-autonomous-dj`.
- Never merge this branch to `master`/`main` before the planned human blind
  listening gate (see `DECISIONS.md` D001).

## 2. Required authority files to read at session start

In order, before doing any substantial work:

1. `docs/v2/AGENT_PROTOCOL.md` (this file).
2. `docs/v2/ACTIVE_HANDOFF.md` — exact live state as of the last session.
3. `docs/v2/STATE.md` — current phase and completed-work summary.
4. `docs/v2/IMPLEMENTATION_PLAN.md` — phase table and gates.
5. `docs/v2/DECISIONS.md` — architectural decisions and why they were made.
6. `docs/v2/BENCHMARK.md` — per-phase measured evidence.
7. The full research/specification document. It is expected at
   `docs/v2/DJENIUS_V2_RESEARCH_SPEC.md` in-repo and may also exist at
   `~/Downloads/DJenius_V2_Professional_Autonomous_DJ_Research_and_Specification.md`.
   Read the relevant sections in full when entering a new phase — do not rely
   only on grep excerpts or a previous agent's summary of it.
8. Recent `git log` on the active branch to understand what actually landed.

## 3. Research specification is product/domain authority

The research specification defines what DJenius V2 must become: a local
autonomous DJ that composes and auditions multiple plausible performances per
handoff and plans a whole-set journey, not a conventional AutoDJ. Do not
silently simplify the product back toward crossfade-and-order automation.
When a phase's required architecture is ambiguous, resolve the ambiguity in
favor of the specification's intent, and record the resolution in
`DECISIONS.md`.

## 4. Preserve unfinished local work

If the filesystem or `git status` shows work that is not described by
`ACTIVE_HANDOFF.md`, investigate it before doing anything else. Another agent
may have made local progress after the last handoff update, or a run may have
been interrupted mid-write. Treat the filesystem and Git history as more
authoritative than any single handoff document if they disagree.

## 5. Never reset/clean/stash/restore/recreate without explicit evidence and need

Do not run `git reset`, `git clean`, `git stash`, `git restore`, `git
checkout` over local changes, or recreate an unfinished implementation from
scratch, unless you have first inspected the existing state, understood why
it exists, and concluded — with evidence, not assumption — that discarding it
is correct. Prefer continuing or repairing existing unfinished work over
rewriting it.

## 6. Verify Git state before work

At session start, confirm: current branch, `git status --short`, local HEAD
SHA, and `origin/<branch>` HEAD SHA (via `git fetch` then compare). Report any
mismatch against `ACTIVE_HANDOFF.md` before proceeding, and treat the
observed state as ground truth.

## 7. Work autonomously

Once state is verified, proceed with implementation, testing, and validation
without pausing for the user to run routine commands. Use the terminal
directly. Ask the user only when a decision requires information that cannot
be recovered from the repository, docs, or research spec (for example: which
of two genuinely ambiguous product directions to take).

## 8. Tests and real-data/audio gates must support claims

Never report a capability as working without a passing test or a real-audio
smoke result to back it up. Prefer the pattern used in Phases 1-6: dedicated
suite -> targeted regression -> complete repository regression -> anonymized
private real-music validation -> privacy gate -> docs -> commit -> push.

## 9. Never equate automated PASS with professional human DJ quality

Automated gates (unit tests, synthetic known-good-vs-bad ordering, planned-
vs-shuffled set metrics) prove that the system behaves as designed. They do
not prove the output sounds like a skilled human DJ performance. State this
distinction explicitly in `BENCHMARK.md` and in any summary of results. The
blind human listening gate (Phase 10 / research spec section 31-32) remains
the only authority for that claim.

## 10. Private music, stems, caches, private reports, and track identities never enter Git

`.gitignore` already excludes `testMusic/`, audio extensions, `data/`,
`*.db`, `output/`, `outputs/`, stems, and generated mixes. Before every
commit, run `git status` and inspect the diff of anything unexpected. Private
real-track validation artifacts belong under `/tmp/djenius_phase<N>_smoke` (or
similar), never under a tracked path.

## 11. Use anonymous labels for private evidence

When reporting private real-music validation in `BENCHMARK.md`,
`ACTIVE_HANDOFF.md`, or commit messages, use anonymous identifiers (`PAIR_01`,
`SET_A`, `pair index 3`) and aggregate/derived metrics only. Never write a
real filename, title, or artist into a tracked file.

## 12. Update durable V2 docs at phase boundaries

At minimum, update `STATE.md`, `IMPLEMENTATION_PLAN.md`, and `BENCHMARK.md`
when a phase gate passes. Add new entries to `DECISIONS.md` for any
architectural choice made during implementation, especially ones that
resolved an ambiguity in the research spec or fixed a defect in a frozen
phase's interface.

## 13. Make small coherent commits only after appropriate validation

A commit should represent a working, tested increment: it should not mix
unrelated phases, and it should not be created merely to checkpoint
in-progress broken code. If a mid-phase checkpoint commit is genuinely needed
for handoff safety, say so explicitly in the commit message and in
`ACTIVE_HANDOFF.md`.

## 14. Push completed safe phase checkpoints

After a coherent commit that passes its validation gate, push to
`origin/v2-professional-autonomous-dj` and verify local/remote HEAD equality.

## 15. Never merge V2 to master before the planned human listening gate

See rule 1 / `DECISIONS.md` D001. This is a hard rule, not a default.

## 16. Keep architectural phase boundaries clear

Do not casually rewrite a frozen phase (see `STATE.md`/`IMPLEMENTATION_PLAN.md`
for what is currently frozen). If a later phase exposes a genuine interface
defect in a frozen phase, make the smallest justified fix, add regression
evidence proving the defect existed and is now fixed, and record it in
`DECISIONS.md` (see D031/D032 for the pattern used in Phase 6).

## 17. Explicitly defer unsupported metrics rather than fabricating precision

If a metric cannot be reliably computed with current analysis/audio evidence
(for example: certified true peak, overlap-local harmonic quality, vocal
intelligibility, stem bleed), mark it as deferred in code and docs rather than
inventing a number. This pattern is established in Phase 6 (`AuditionMetrics
.deferred`) and must continue.

## 18. Maintain `ACTIVE_HANDOFF.md` continuously

See the dedicated section below on cadence. The handoff file should lag
reality by no more than one atomic operation.

## 19. Stop safely before context/tool/quota exhaustion

See the "When to stop" section below. Do not spend the last available context
trying to squeeze in one more subsystem.

## 20. Another agent must be able to resume without asking the user what happened

`ACTIVE_HANDOFF.md` plus this file plus the durable docs plus `git log` must
be sufficient. If they are not sufficient, that is a defect in how the
previous session ended — fix it going forward, do not rely on the user to
fill gaps from memory.

---

## Handoff cadence

Update `ACTIVE_HANDOFF.md`:

- at session start, immediately after verifying state;
- after every significant implementation milestone;
- after meaningful test gates (dedicated suite, targeted regression, full
  regression, real-audio smoke);
- after discovering a defect that changes the plan;
- after starting a long-running process;
- after a coherent commit/push;
- before beginning a substantially new subsystem.

## When to stop for handoff

Stop and hand off (do not start a new large feature) when any of the
following is true:

- context appears roughly 80-85% consumed;
- remaining context feels insufficient to safely complete the next atomic
  task;
- tool/execution access is becoming unstable or repeatedly failing;
- repeated context compression is occurring;
- the user says a subscription/time limit is near;
- the platform reports a quota or execution warning.

When stopping:

1. Do not start another large feature.
2. Finish the current atomic operation if it is safe to do so.
3. Do not force a commit if validation is incomplete.
4. Preserve unfinished local work exactly as it is.
5. Update `ACTIVE_HANDOFF.md` to the exact live state.
6. Update `STATE.md` only if a durable phase boundary was actually reached.
7. If a validated coherent checkpoint is ready, commit and push it.
8. Otherwise leave the working tree intact and uncommitted.
9. Verify `git status`.
10. Report a concise handoff and stop.

The handoff report must state: last pushed commit, current phase, local HEAD,
remote HEAD, uncommitted files, tests completed, tests running, tests
missing, known blockers, exact next action, and whether
`ACTIVE_HANDOFF.md` was updated.
