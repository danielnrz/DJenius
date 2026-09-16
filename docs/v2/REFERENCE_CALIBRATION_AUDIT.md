# Reference calibration audit

2026-09-16. This is a public-safe, anonymous summary of the private cue-level
audit in `/tmp/djenius_reference_dj_transition/reference_calibration/`. No audio
was rendered, no accepted reference was changed, and no set pilot was started.

## Decision

**Outcome A: calibration repair restores five-track planning connectivity.** The
old graph's 9/182 history-free usable directed edges became 31/182 under the
same musical/context rules. With genuinely human-negative ordered pairs
excluded but previously tested neutral/positive edges allowed, usable edges
rose from 8 to 30. The realistic graph has 98 simple four-track paths and 121
simple five-track paths; the production joint planner also found a complete
five-track **plan-only** path. These are feasibility results, not human approval
of a new set or evidence that every newly usable edge sounds good.

## Human evidence and gate replay

The private table traces 35 durable examples at their recorded source/target
cues. Labels are kept separate for local performance, set context, borderline
results, and unrendered abstention. The exact-cue replay has:

| Evidence layer | Accepted/preserved | Rejected/preserved |
| --- | ---: | ---: |
| Local performance | 19/19 | 9/9 original failed cues |
| Set context at recorded phase | 3/3 | 5/5 |

The set-context replay starts each historical adjacency with its source track's
initial state at the recorded phase; it does not claim to reproduce every
preceding set-state event. A locally approved performance can properly fail a
different set context. Four prior blind-test abstentions are recorded without
inventing listening labels. The private table contains each named gate, source
entry evidence, measured component values, required bands, and signed margins
where a numeric boundary exists. Disjunctive gates are preserved as explicit
branches, not reduced to a score.

Six false rejections of approved reference instances were found: manual and
AUTO F, manual and AUTO C3, and manual B8 and AUTO B8. They arose from three
general rule defects:

| Archetype | Contradictory measured evidence | Selector-only correction |
| --- | --- | --- |
| F | The approved effect begins with one complete vocal unit ending in 0.5341 s. The later floor demanded vocal inactivity and a boundary within 0.25 s although the frozen template already allowed a bounded phrase ending. Target runway vocal occupancy was 0.5181, but its energy was only 0.1771 before a 0.5646 lift. | Accept one well-covered, nearly completed unit inside the existing 0.75 s template tolerance. A moderately vocal target runway counts as reset space only when it is quiet and has a material landing lift. |
| B8 | Whole-track groove distance was 0.3658, above a later 0.20 long-overlap margin, while the approved cue had local rhythm/spectral loop stability 0.9939/0.9959, target bass change 0.6904, and lift 0.5812. | Retain the template's technical groove ceiling. Permit a wider *performance* margin only when stable local loop, bass handoff, lift, cadence and harmony jointly demonstrate deliberate groove replacement. |
| C3 | Approved source/shared raw densities were 0.7829/1.5267 and raw vocal regions overlapped; the effect boundary vocal activity was only 0.0464. Both vocal-stem confidence values were 1.0, with a manageable target drum/vocal ownership bar. | Evaluate the frozen stem-sequenced audible ownership rather than treating raw vocal-region overlap as collision. Require reliable stems, quiet effect entry, bounded density, harmony, target drums, and controlled first landing bar together. |

This is not a reference filename/cue/hash whitelist. F's incomplete or
continuing-vocal cues and loud target pickups still fail; the original bad B8
source entry still fails; C3 requires every staged-ownership safeguard. The
previous blind-performance failures remain below the floor. The known bad
set-context adjacencies still fail context at their recorded phases. A
leave-one-example-out *reasoning* check found each rule follows from the
choreography's audible mechanism and continues to reject a corresponding
counterexample; this is not a statistical validation claim.

## Graph and library implications

The realistic calibrated graph has density 30/182 = 0.1648, longest simple
static path eight tracks, and one complete offline production five-track plan.
The graph is still sparse: four tracks have no outgoing edge and six have no
incoming edge. F covers 27 of the 31 history-free usable edges; C3 covers 2,
B8 3, and D2 2 (two edges have multiple-template coverage). This concentration
is a future human-listening concern, not evidence yet for a fifth archetype.

The private directory has 17 audio files: 14 actual music tracks admitted by
the existing pilot policy, two synthetic test tones, and one other file outside
that policy. The 14-track pool spans four tracks below 100 BPM, two at 100–119,
seven at 120–139, and one at 140+; most analysis energies fall in 0.70–0.79.
No byte-identical duplicates were found. Byte hashes cannot establish that
two different encodes or versions are musically distinct. Because a complete
plan now exists, the pre-repair nine-edge graph cannot justify a numeric
library-expansion target. No music should be acquired on this evidence alone.

## Scope and next gate

Only `reference_selector.py` acceptance logic changed. Frozen performance
templates, renderer, context calibration, history labels and known-negative
exclusions were untouched. The current result resolves the graph's calibration
contradiction and permits later human-gated planning experiments; it does not
authorize Pilot 4, a new transition family, relaxed context rules, or library
expansion. Any future set must be rendered and human-listened before its new
edges become positive evidence.
