# Pilot 4 set-context postmortem

2026-09-16. The listener liked Pilot 4's transitions, including the subtle
second move, and did not object to F occurring twice. The remaining complaint
is the musical journey, not transition DSP. This audit therefore changes **no**
renderer, template, choreography, envelope, speed behavior, calibrated gate, or
audio file. The detailed, private cue-level evidence is in
`/tmp/djenius_reference_dj_transition/pilot4_context_postmortem/`.

## Diagnosis

**TRACK_4 → TRACK_5 is the strongest *suspect*, not a confirmed pair-specific
human reject.** It is the only previously untested Pilot 4 ordered edge.
TRACK_2 → TRACK_3 repeats the accepted Pilot 2 first
adjacency, and TRACK_3 → TRACK_4 repeats the accepted `CONTEXT_NATURAL` ordered
pair at a nearby introductory cue. TRACK_1 → TRACK_2 has a strongly positive
local-transition verdict but no explicit whole-set-context label, so it remains
an alternative contributor. The listener did not identify an exact offending
adjacency, and cumulative set drift cannot be ruled out.

| Pilot 4 edge | Planner context | Whole-track CLAP cosine | Cached cue style / intensity distance | Context anchors | BPM | Mean energy | Cue sections |
| --- | --- | ---: | ---: | ---: | --- | --- | --- |
| 1 → 2 | Natural | .769 | .0206 / .0056 | 3 | 117.5 → 129.2 | .745 → .750 | build → drop |
| 2 → 3 | Natural | .874 | .0088 / .0191 | 4 | 129.2 → 123.0 | .750 → .747 | verse → intro |
| 3 → 4 | Natural | .914 | .0126 / .0172 | 5 | 123.0 → 112.3 | .747 → .768 | verse → intro |
| 4 → 5 | Natural | .880 | .0282 / .0246 | 2 | 112.3 → 129.2 | .768 → .698 | bridge → build |

The final edge's two anchors are whole-track embedding and whole-track spectral
similarity. It has **no** cue-style, cue-intensity, whole-track rhythm, or
harmonic continuity anchor. Its cue-style distance exceeds the pool's shift
band (.0248), though not its outlier band (.0301). Its intensity difference
falls below the joint style-plus-intensity shift requirement, tempo difference
is 15.0% rather than the rhythmic-jump predicate's 18%, and the coarse dance
roles change from `driving_dance` to `rhythmic_song`, not the specifically
forbidden `driving_dance` ↔ `atmospheric_or_sparse` pair. No contrast predicate
fires, so the edge is classified **NATURAL_CONTINUATION** by default. Both
tracks have broad “pop” relative CLAP estimates, while mood/valence labels are
below reliability and remain unknown. This is a conjunction/rule-scope blind
spot, not evidence for an arbitrary new cutoff.

The declared final set phase is **RELEASE**, accepted because whole-track mean
energy falls by .070 and the target's closing energy lies below its *eventual*
peak. But the actual target landing is in a labelled **build** section with
positive section energy slope (+.147) and mean section energy .839. The target's
first two 20-second bands after entry average .822 then .908, before falling
to .576 later. Thus the short-term audience experience need not be a release
even though the whole-track statistics satisfy the release gate. The source
bridge is vocal-heavy and the target becomes less vocal; that change is
measured, not given a speculative emotional label. The accepted
`CONTEXT_BRIDGE` reference uses this same target at its build cue after a
different source and explicitly classifies the change as a bridgeable contrast.
Pilot 4 calls its final edge natural instead.

## What the current features can and cannot say

Track analysis already provides BPM, beat/phrase/section boundaries, groove
proxies, energy and low/mid/high spectral content, local rhythm/chroma/spectral
descriptors, vocal activity, and stems. It does **not** reliably identify meter
(the `compound_or_halftime_candidate` heuristic is not a 6/8 diagnosis),
instrumentation or acoustic-versus-electronic production, or vocal affect.
The Pilot 4 mood/valence evidence is below the stated reliability floor.
Seven broad CLAP style prompts cannot establish that two songs have the same
musical purpose.

“Cue-local CLAP” in the current production gate means distance between
*prompt-score distributions* from the nearest of four representative 10-second
windows; the raw cue embedding is not cached. The embedding cosine in the
table is a mean-of-four **whole-track** embedding comparison. On the final
edge the selected target prompt window is centered **19.0 seconds before**
the target cue and samples its intro, while the selected cue is in a build.
Other accepted edges also have window/section mismatch, so fixing that
sampling issue alone is not proven to fix the set.

A diagnostic-only, offline probe using the **already cached** CLAP model
embedded 10 seconds around the actual cues. It did not change production or
download a model. Exact-cue cosine did **not** separate human outcomes: the
accepted `CONTEXT_NATURAL` pair was about .474, while the rejected Pilot 2
third adjacency was about .862. Exact-cue prompt-score differences also
overlap. The final Pilot 4 edge was about .782. A diagnostic Essentia
10-second danceability estimate likewise overlaps accepted and rejected
cases; it is not a reliable single-number gate. The lesson is not “use a
different CLAP threshold.”

The calibration set contains three unique explicit context passes and five
unique context failures; `GEN_F_02_FIX` is correctly a **local performance**
pass but later **set-context** failure and duplicates the Pilot 2 second
ordered pair. Whole-track cosine overlaps: a rejected Pilot 1 adjacency
(.881) exceeds an accepted Pilot 2 adjacency (.874). Cue style distance is
also not monotonic across all human labels. With this sample size, fitting a
classifier or a threshold to Pilot 4 would be overfitting.

## Set-history limitation

`SetFlowState` retains recent track IDs, energy, coarse dance/rhythmic labels,
reliable moods, a phase, and a contrast-event count. It does **not** retain a
music-context/production-style region, the previous two cue-level profiles,
or accumulated *subthreshold* contrast. All four Pilot 4 edges were called
natural, leaving contrast count at zero. The path ranking therefore sees a
valid `OPEN → HOLD → BUILD → PEAK → RELEASE` scalar trajectory but cannot ask
whether several locally acceptable changes collectively form one musical
world. Whole-track CLAP similarity to the previous two tracks does not itself
show an obvious numerical drift, so short history is a necessary diagnostic
dimension, **not yet a proven sole fix**.

## Music-specific representation options—research only

The smallest plausible *challenger* is [Essentia's Discogs-EffNet music
embedding](https://essentia.upf.edu/models.html), optionally with its
MTG-Jamendo genre/mood-theme and MagnaTagATune heads. It was trained for
music style/similarity rather than generic audio-text alignment; the [official
weight index](https://essentia.upf.edu/models/feature-extractors/discogs-effnet/)
lists roughly 18 MB weights. It may expose timbre/style/instrumentation
differences the present representation misses, but this is a hypothesis, not
an empirical result on DJenius. The installed Essentia build lacks its
TensorFlow predictor, so dependency/inference integration is not presently
plug-and-play. Essentia states MTG-created model weights are CC BY-NC-SA 4.0
or separately licensed; production use needs license review.

[Discogs-MAEST](https://essentia.upf.edu/models/feature-extractors/maest/)
offers a music transformer comparator but its 10-second ONNX weights are about
344 MB and local predictor support is absent. [MERT-v1-95M](https://huggingface.co/m-a-p/MERT-v1-95M)
offers self-supervised music embeddings (95M parameters, five-second training
context), but is not cached, uses custom model code and carries a CC BY-NC
license. Neither has been downloaded, installed, or tested here. More labels
do not automatically make a better DJ context decision; any challenger must
demonstrate incremental value over the present cues, acoustic descriptors,
and explicit bridgeability on the **same human-labelled adjacencies**.

## Smallest justified next change before another set

Do **not** change a production cutoff or launch Pilot 5 from this ambiguous
whole-set label. The next scoped development step is a *shadow-only*,
cacheable cue-and-establishment context profile: compare the actual source
launch, target entry, and first established target section, and retain the
last two track-context profiles for an inspectable story check. Benchmark a
licensed music-specific embedding/tag representation (Discogs-EffNet first,
subject to license/dependency approval) against the labelled passes/failures.
Also check whether declared `RELEASE` is supported by the **post-landing**
energy/section trajectory rather than a late whole-track peak. Only promote a
new hard set-flow rule if it preserves accepted natural and cross-style bridge
cases while catching repeated context failures. The transition engine stays
frozen throughout.

No new audio, Pilot 5, model installation, or production-planner mutation is
part of this postmortem.
