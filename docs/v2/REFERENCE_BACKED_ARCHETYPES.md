# Reference-Backed Performance Archetypes

## Purpose and gate

This layer converts one explicitly requested, human-approved performance
archetype into an analysis-anchored `PerformanceRecipe` and an executable
performance description. The same-pair reproduction gate has passed human
listening; the current question is whether analysis-only eligibility can place
that approved behavior on new pairs. The layer still does not choose an
archetype and is not connected to Candidate Composer, Audition Lab policy, Set
Director, the UI, or full-set rendering.

The implementation entry point is
`instantiate_reference_template(source, target, archetype, ...)`. Cue times
come from `TrackAnalysis` downbeats, sections, per-bar energy, and vocal
regions; the templates contain no approved-reference timestamps. The private
same-pair driver records the independently known manual anchors only for the
comparison manifest.

The current gate is human listening of exactly two new private real pairs per
archetype. Autonomous selection remains prohibited until that gate passes.

## Frozen human reference set

| Status | File | SHA-256 |
|---|---|---|
| strongest | `REFERENCE_F.wav` | `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48` |
| successful DJ-like edit | `REFERENCE_C3.wav` | `ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03` |
| acceptable loop/build/handoff | `B8_RESIDUAL_FIX.wav` | `47824cc9b923c708f261c7d3db82e46e2f910fec47b802111bcd26c1c5aa1205` |
| acceptable restrained blend | `REFERENCE_D2.wav` | `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586` |

These private files must never be overwritten. The private reproduction
driver verifies every hash both before and after rendering.

## Frozen automated reference set

| Human result | File | SHA-256 |
|---|---|---|
| best; genuinely enjoyable | `AUTO_F.wav` | `13c3691cf81b40467d8adce0c9cf2408206199500554648ef29ae32584ab6f2b` |
| good; DJ work clearly audible | `AUTO_C3.wav` | `0c89bb5f9024baacdb419556f2fbd8c4a1b60099b13a26a0dcc9738b16426a32` |
| acceptable; beyond generic AutoDJ behavior | `AUTO_B8.wav` | `f6ff0d862739e8c0b71993d3fc5ba1b4eb8a73468354d59f2f525ce747c5e3b1` |
| good for restrained/effect role | `AUTO_D2.wav` | `ab2dbd9156eb18b3c450495ffab8b21060841abe430e23d38f7b9340fc532634` |

These are also immutable regression-listening references. The generalization
driver verifies the full eight-file manual/automated hash set before and after
rendering; the same-pair reproduction driver protects the manual set.

## Permanent structural invariants

- Source loop/effect state is not destroyed or restarted at landing.
- Every post-release tail has an explicit, bounded lifetime.
- Target runway and postlanding body use one coherent target timeline.
- Target master and stems that meet in one performance use one shared
  multichannel time/stretch operation.
- Bass ownership is explicit and non-accidental.
- Target identity is normally established progressively.
- Full-target reveal completes the established target and may not introduce
  an unexplained timbral or loudness reset.
- Source effects connect A to B; they are not decoration applied only to A.
- Hard releases are prepared, and loop-length changes preserve musical phase.

## 1. Reset Release (`reset_release`)

Reference: `REFERENCE_F.wav`.

- Suitable source sections: bridge, build, drop, or energetic material ending
  immediately before a quiet outro/reset boundary.
- Suitable target sections: a sparse intro/pickup leading adjacently into a
  verse or other clear phrase entrance.
- BPM relationship: intended for large or incompatible natural-tempo
  relationships; it deliberately does not force a beatmatch.
- Beatgrid confidence: at least 0.80 for both tracks; analysis confidence at
  least 0.75.
- Vocal requirements: a usable outgoing vocal capture in the last source bar;
  target pickup may contain vocal material but must remain sparse.
- Stem requirements: source vocal; no target stems required.
- Target cue: one natural pickup downbeat immediately before the landing
  downbeat, using adjacent samples from the same target master.
- Phrase length and entry: four intact source bars, followed by one
  natural-time target reset/pickup bar.
- Source actions: preserve the source phrase; capture a roughly 300 ms
  last-bar vocal fragment; make an 80 ms dry release.
- Shared territory: five filtered, progressively darker, alternating-stereo
  vocal taps decay over the target pickup fade.
- Bass ownership: source before release; intentional reset space; target at
  landing.
- Target reveal: pickup fades from silence to unity; adjacent full master
  enters at landing.
- Source release/tail: dry source ends before the reset; the final echo ends
  before landing (the accepted pair clears by about 41 ms).
- Landing/establishment: clean natural-master entrance and at least four,
  normally eight, uninterrupted target bars.
- Failure conditions: missing source vocal, no usable one-bar pickup,
  non-adjacent pickup/body samples, or an echo reaching the landing.
- May vary: capture location inside the last bar, tap damping, and safe target
  trim.
- Must not vary freely: source-then-reset ordering, the one-pickup-bar form,
  decreasing tap sequence, natural target tempo, or prelanding tail clearance.

## 2. Stem Echo Handoff (`stem_echo_handoff`)

Reference: `REFERENCE_C3.wav`.

- Suitable source sections: verse, build, drop, or outro with separable
  rhythmic/music/vocal material.
- Suitable target sections: intro into a strong drop or chorus.
- BPM relationship: beatmatchable, normally no more than 12% apart.
- Beatgrid confidence: at least 0.85; analysis confidence at least 0.80.
- Vocal requirements: outgoing vocal supports a late capture; incoming vocal
  remains withheld until landing.
- Stem requirements: source drums/other/vocals and target
  drums/other/vocals.
- Target cue: a stable four-bar landing-drum phrase, a strong phrase landing,
  and a coherent intro-to-body target clock.
- Phrase length and entry: eight bars. Target drum air starts at bar 1 and
  establishes rhythm across the first four bars.
- Source actions: release drums, other, vocal, and low end in sequence; capture
  the vocal before its dry release.
- Shared territory: target rhythm grows for four bars; target bass takes over
  at the midpoint; four damped/diffused source-vocal taps connect the late
  phrase.
- Bass ownership: source through bar 4; half-bar handoff; target from bar 5.
- Target reveal: rhythm, low end, upper context, then full master. Target vocal
  is absent before landing.
- Source release/tail: dry components clear sequentially; final echo clears
  before landing (about 239 ms on the accepted pair).
- Landing/establishment: the already-established target owns rhythm and bass
  when the full master appears; default eight postlanding bars.
- Failure conditions: missing stems, tempo difference above 12%, weak target
  drum phrase, or source/target vocal overlap.
- May vary: capture location, echo damping/cutoffs, and safe target trim.
- Must not vary freely: eight-bar form, four-bar drum phrase, midpoint bass
  transfer, incoming-vocal withholding, shared target clock, or tail bound.

## 3. Loop Build Coherent Handoff (`loop_build_coherent_handoff`)

Reference: `B8_RESIDUAL_FIX.wav`.

- Suitable source sections: build, drop, or energetic outro with one clean
  backing motif.
- Suitable target sections: intro into a sustained drop/chorus.
- BPM relationship: beatmatchable, normally no more than 12% apart.
- Beatgrid confidence: at least 0.85; analysis confidence at least 0.80.
- Vocal requirements: source vocal separation is needed so it is not baked
  into the loop; the first target-vocal onset must be measurable to bound the
  tail.
- Stem requirements: source vocal plus target drums/other/vocals.
- Target cue: an early strong drop bar with a stable two-bar low cadence. A
  sparse intake bar is rejected in favor of a nearby stronger bar only when
  per-bar energy and vocal evidence supports the choice.
- Phrase length and entry: eight bars. Target air/context precedes body;
  source loop begins at bar 5; target low becomes material late in bar 6.
- Source actions: dry source releases early; one phase-anchored backing motif
  repeats at 4 beats, then 2, then 1; a two-bar riser grows from zero.
- Shared territory: target rhythm and identity rise behind the same loop
  state; the loop and airy residue cross landing without a buffer restart.
- Bass ownership: source through bar 4; controlled tease/space; target takes
  ownership from late bar 6 through landing. The target low preview repeats a
  stable two-bar cadence so no false final-bar bass hole appears.
- Target reveal: air/high context, drum body and identity, low end, full
  master. Runway master/stems and postlanding body share one time map.
- Source release/tail: rhythmic loop and band-limited riser residue continue
  across landing but finish 20 ms before the measured target-vocal onset.
- Landing/establishment: full target arrives on the analysis-derived cue; its
  first gain ramp is continuous and it remains established for eight bars.
- Failure conditions: missing stems, tempo difference above 12%, no target
  vocal bound, unstable two-bar low cadence, a loop restart, or tail/vocal
  overlap.
- May vary: analysis-selected motif/capture bar, safe deck trim, and the exact
  tail endpoint implied by target vocal onset.
- Must not vary freely: eight-bar form, 4/2/1 sequence, phase continuity,
  two-bar low preview, shared target time map, reveal order, or bounded tail.

## 4. Restrained Ownership Blend (`restrained_ownership_blend`)

Reference: `REFERENCE_D2.wav`.

- Suitable source sections: verse or outro that can support a long controlled
  release.
- Suitable target sections: a long intro/build/verse runway leading into real
  bass and drum material.
- BPM relationship: close and beatmatchable, normally no more than 8% apart.
- Beatgrid confidence: at least 0.85; analysis confidence at least 0.80.
- Vocal requirements: outgoing and incoming vocals must transfer
  sequentially, never claim ownership simultaneously.
- Stem requirements: source vocal plus target drums/other/vocals.
- Target cue: a twelve-bar coherent runway ending at a clear section entrance
  with real landing bass/drums.
- Phrase length and entry: twelve bars. Target highs and mids develop first;
  bass and drums wait until bars 9-10.
- Source actions: keep source bass through eight complete bars; release source
  low/mid/high/vocal with separate raised-cosine ramps.
- Shared territory: long upper-band blend, one explicit late bass transfer,
  then target drums and vocal.
- Bass ownership: source through bar 8; half-bar transfer; target thereafter.
- Target reveal: highs, mids, bass, drums, vocal, then full master.
- Source release/tail: bands reach zero progressively by landing; no decorative
  or postlanding FX tail.
- Landing/establishment: restrained completion of a target already understood
  by the listener; default eight postlanding bars.
- Failure conditions: missing stems, tempo difference above 8%, insufficient
  runway, or simultaneous vocal ownership.
- May vary: safe deck trim and small band-ramp offsets. A 12-to-16-bar length
  range is not enabled until future human validation.
- Must not vary freely: eight-bar source-bass hold, late bass-before-drums
  sequence, sequential vocal handoff, shared target time map, or no-FX rule.

## Reproduction evidence

Private outputs and the complete machine-readable comparison are in:

`/tmp/djenius_reference_dj_transition/automated/`

The manifest records frozen/manual and automated hashes, analysis-derived cue
differences, bar-relative action schedules, bass ownership, target stream/time
map, tail lifetime, target-establishment period, renderer provenance, and
technical audio measurements. The user passed this same-pair reproduction gate
on 2026-09-15.

## Cross-pair generalization evidence

`assess_reference_template_pair(...)` now returns deterministic, explainable
analysis-only evidence plus either an instantiated template or explicit
`NOT SUITABLE` reasons. It checks the template's structural feasibility and
archetype-specific cue context: phrase/downbeat bounds, BPM/stretch, global
key relation, groove descriptors, source/target energy, cue-local bass ratio,
vocal windows/onset, section density, and stem presence/activity. Its
`fit_score` only orders plausible pairs for this bounded experiment; it is not
an Audition Lab score or a claim of perceptual quality.

The private generalization output and full manifest are in:

`/tmp/djenius_reference_dj_transition/generalization/`

The manifest includes eight selected new real pairs, every instantiated
action/anchor/adaptation, and all rejected or eligible-but-not-selected pairs.
The user must listen before any result is called successful or exposed to
autonomous planning.
