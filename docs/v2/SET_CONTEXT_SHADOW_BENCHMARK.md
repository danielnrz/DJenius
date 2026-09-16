# Set-context shadow benchmark

2026-09-16. This is **analysis only**. Pilot 4 audio, its accepted transition
choreography, the renderer, the four archetypes, and production musical-context
gates remain unchanged. No Pilot 5 was planned or rendered. Nine detailed,
private JSON artifacts and the reproducible diagnostic scripts are under
`/tmp/djenius_reference_dj_transition/context_shadow_benchmark/`; private
track identities and embedding vectors are not committed.

## Human evidence and performed alignment

The durable evidence contains **three distinct set-context passes**, **five
set-context failures**, and **four Pilot-4 adjacencies with uncertain pair-level
set-context labels**. Pilot 4's local transition praise is recorded separately;
it is not silently converted into pairwise context approval. Its final adjacency
is a suspect, **not** a human-labelled reject. A locally successful edit on the
same ordered pair as a set-context failure is also not counted as a context
pass. One additional earlier adjacency is used solely to reconstruct set
history. The rejected controlled context pair was evaluated but not rendered.

For each performed transition, the probe uses the actual template source start,
source release, target runway and target landing anchors. Windows are laid out
in performed bars: source long lead-in (bars −32 to −16, clipped to the prior
landing), pre-move (−16 to 0), actual exit; then target runway, landing bars
0–4, establishment bars 4–12, and later establishment bars 12–20. Windows
are derived from anchor times and bar spans, rather than approximate
whole-track CLAP representative windows. This measures **native track content
at performed cue coordinates**, not the effect-processed continuous mix.
Acoustic analysis includes energy and slope, low-frequency drive, rhythmic and
vocal activity, local spectral/rhythm/chroma vectors, section-weighted
arrangement density, and BPM/harmonic confidence. Meter and semantic affect
remain unavailable or unreliable; no 6/8 or mood claim is inferred.

## Current-feature result

The most promising descriptive CLAP feature was source pre-move to the
target's **second** establishment window. Its lowest human pass had cosine
`.865893`, while the highest human failure had `.862338`—a gap of only
`.003555` across three passes and five failures. Source-exit to target-cue and
earlier establishment comparisons overlap or invert. The apparent late-window
gap depends on individual boundary cases and related tracks; it is not a
defensible production threshold. Current production already accepts the three
known context passes and rejects the five known failures, so these cases cannot
demonstrate incremental decision accuracy. No classifier was fitted.

Two-track history adds a useful *question*, not a proven gate. Pilot 4's final
target is the most distant from the preceding two-track context centroid among
edges with history (CLAP cosine `.801` versus `.888` and `.911` for the preceding
two adjacencies). Yet its first adjacency is the largest immediate
source-pre-to-target-establishment outlier (cosine `.734`; final adjacency
`.817`). The listener did not label either pair individually. A prior rejected
set-context edge can have high recent-context similarity, so history cosine
alone is not enough. The sequence may contain cumulative drift rather than one
bad splice.

## Music-specific challenger—private shadow only

After the existing features remained inconclusive, one small
[musicnn](https://github.com/jordipons/musicnn) MTT music-tagging representation
was probed on the **same windows and labels**. The original project describes
music-specific pooled features, 50 broad tags, and roughly three-second
analysis patches in its [documentation](https://github.com/jordipons/musicnn/blob/master/DOCUMENTATION.md).
An isolated [third-party PyTorch conversion](https://huggingface.co/oriyonay/musicnn-pytorch)
at a pinned revision supplied the 3.1 MB safetensors weights. Its Python module
was inspected, loaded locally with a strict state match, and run on CPU over
113 unique three-second patches. No `trust_remote_code`, pickle weights,
package installation, production dependency, or DJenius cache mutation was
used. Tag activations are diagnostics, not ground-truth genre or mood labels.

This challenger did **not** establish a robust gain. Source pre-move to the
*first* establishment window gives passes `.933–.973` and failures
`.804–.925`, another narrow apparent gap. At the following establishment
window, passes `.911–.953` and failures `.845–.952` substantially overlap;
source-exit to target-cue overlaps too. The uncertain Pilot-4 final edge looks
more unusual at the later establishment stage, but the first edge is more
unusual at immediate arrival. It does not consistently resolve the durable
contradictions or identify the human-perceived set mismatch.

Model licensing and maintenance prevent quiet adoption. [Original musicnn's
ISC notice](https://github.com/jordipons/musicnn/blob/master/LICENSE.md)
permits broad use of the original repository; the conversion declares
Apache-2.0, but converted-weight provenance/inference parity and any separate
distribution constraints need review. The original TensorFlow-1-era stack is
not a practical direct dependency for DJenius's Python 3.13 environment.
[Essentia Discogs-EffNet](https://essentia.upf.edu/models.html) is a plausible
music-style/similarity comparator, but Essentia's official pages conflict on
the exact noncommercial model licence ([catalogue](https://essentia.upf.edu/models.html)
versus [licensing page](https://essentia.upf.edu/licensing_information.html)),
the installed library lacks the needed TensorFlow predictor, and its library
licence/dependencies need separate distribution review. It was not downloaded.
[MERT-v1-95M](https://huggingface.co/m-a-p/MERT-v1-95M) is much heavier and
its model card is noncommercial; it was not downloaded. “Downloadable” is not
treated as “production-licensed.”

## Set-state semantics

The planner indexes a proposed role sequence before evaluating each candidate;
the target then passes broad whole-track role and mean-energy checks. The
state is assigned the proposed phase after acceptance. Thus the final Pilot-4
`RELEASE` describes an expected path position more than the performed target's
first bars. The target's actual bar-aligned energy rises from `.732` at landing
to `.884` and `.901` in the two establishment windows. It is **not an
immediate, sustained release**. A later release or reset-then-rebuild is
possible, but the current state does not encode that explanation.

Crucially, the human-accepted `CONTEXT_BRIDGE` uses the same target cue and
the same rising post-landing sequence after a different source. A rule that
rejects any rising target under `RELEASE` would destroy known positive
evidence. This is a semantic diagnosis, not authorization to change the gate.

## Conclusion and next evidence

**D — the human set-context evidence is too small and Pilot-4 pair labels too
ambiguous to justify a production change.** Exact-cue trajectories and short
history are useful to inspect, but not sufficient to promote a new hard rule.
The tested music-specific model did not add clear, consistent value, so no new
local model is justified for production. The final Pilot-4 adjacency remains
the strongest *combined-history* suspect, while the first adjacency is a
competing immediate-context outlier. Neither is a confirmed human pair reject.

The smallest justified production change is **none**. The next evidence should
be a targeted pair-level human listening annotation of Pilot-4 edges—especially
first versus final—and further independent accepted/rejected set-context
examples at performed cues. Only then should a shadow cue-to-establishment and
short-history rule be checked for both positive preservation and negative
rejection. Pilot 5, threshold tuning, and transition changes remain paused.
