# CTX2 labels and shadow DJ-demonstration mining

2026-09-17. This is a **diagnostic checkpoint**, not a production selection,
transition, renderer, model-training, or new-archetype change. Private track
identities, reference audio, fingerprints, and detailed derived metadata stay
outside Git under `/tmp/djenius_reference_dj_transition/`.

## Blind CTX2 labels

All sixteen four-way labels and the listener's exact reasons were persisted
before revealing the hidden case map. The public-safe verbatim labels are in
[`CTX2_HUMAN_CONTEXT_LABELS.json`](CTX2_HUMAN_CONTEXT_LABELS.json); private
case identities, cues, and graph evidence are in
`context_label_pack_2/CTX2_LABEL_REVEAL.json` and
`context_label_pack_2/CTX2_LABEL_ANALYSIS.json` beneath the private `/tmp`
root. Counts: **2 NATURAL, 6 BRIDGEABLE, 4 MISMATCH, 4 UNCERTAIN**.

| Blind stratum | Human results | Interpretation |
|---|---|---|
| Five F-heavy currently usable | `01 MISMATCH`; `08,09 NATURAL`; `10,16 BRIDGEABLE` | F coverage is not uniformly musically safe. `01` is a direct context-only false acceptance. |
| Four rare non-F usable | `04 B8 BRIDGEABLE`; `06 D2 BRIDGEABLE`; `07 C3 UNCERTAIN`; `11 D2 BRIDGEABLE` | Three are plausible intentional contrasts, not the NATURAL continuation production called them. One remains unresolved. |
| Three near-boundary rejects | `03 BRIDGEABLE`; `05 MISMATCH`; `15 UNCERTAIN` | `03` merits cue-specific follow-up, but a context-only BRIDGEABLE label does not prove the frozen performance works at the tested cue. |
| Four hidden anchors | `02 MISMATCH`; `12 UNCERTAIN`; `13 UNCERTAIN`; `14 MISMATCH` | The established negative `02` agrees; `12/13` are inconclusive retests; the prior positive `14` disagrees in this simplified listening format. Preserve both observations and provenance. |

The current graph marked `01` and `14` usable despite the new MISMATCH labels.
`14` also has contradictory earlier positive evidence, so it is a calibration
question, not a case to silently relabel. The graph rejected `03`, which the
listener called BRIDGEABLE only with a better region/timing. Production also
called `04/06/11` NATURAL although the human heard a bridgeable contrast.
`UNCERTAIN` is not a pass or reject. No threshold or production decision was
changed from this small, partly contradictory panel.

## Reference corpus and separation

The 35 `fromDJ/` files remain categorically excluded from normal track
discovery and autonomous set planning. All are long-form (about 13–39 min):
**25** have metadata/title and duration consistent with a mix/set, and **10**
have unknown long-form structure. These are *provisional reference types*;
neither filename nor duration proves song-to-song handoffs. No standalone
remix, mashup, bootleg, or individual edit is confidently identified in this
pass. A standalone edit would teach arrangement/effect timing; a confirmed
continuous mix would additionally teach handoffs and set pacing. The two
evidence types are not conflated.

## Original-recording alignment

The shadow aligner searches **158 ordinary-length real songs** against all 35
references. It uses ordered 24-second, 24-bin chroma blocks for retrieval,
tempo-tolerant frame verification, an independent log-spectral corroboration,
and a final waveform check for single-excerpt claims. Fingerprints are cached
privately; audio samples are not written as outputs or copied into Git. Two
nonoverlapping, temporally coherent matches are required for a full alignment.

Result: **zero high-confidence ordinary-original alignments** and **zero
waveform-confirmed ordinary-song excerpts**. One feature-level resemblance
had strong chroma/timbre similarity but failed waveform corroboration; its
identity remains **unconfirmed**. Two excluded long-form overlapping-mix
controls aligned, including one near-sample-identical control (waveform
correlation approximately `.999`). Thus the method recognizes straightforward
shared audio, but the present normal-song library gives it almost no matched
original material for these references. That limits *coverage*, not proof that
the references contain no DJ actions. Strongly transformed/short source use
can also evade this conservative matcher.

## Structured-change and repeat evidence

The earlier coarse pass nominated **673** multi-axis changes, capped at 20
per reference file. They are **not** 673 DJ transitions. A stricter in-memory
waveform check found **21** adjacent exact-like repeats in **9** reference
files, versus 305 repeat-like nominations from harmony/chroma alone. Of those
21, **15** precede a nominated structured change; **6** in **5** files precede
an energy and low-frequency reduction. These are recurring *finished-audio
observations*. A produced song may contain the repeat natively; source
originals and listener annotation are needed to call it a DJ loop or infer
intent. Energy/low-end arrivals, reductions and spectral movement likewise
cannot distinguish DJ EQ, target handoff, or the recording's own arrangement.

The private `DJ_ACTION_REGIONS.json` retains evidence and uncertainty for every
nomination. `DJ_CHOREOGRAPHY_TIMELINES.json` gives nine 2-second acoustic
snapshots around the thirty most informative regions, with approximate
four-beat-bar offsets **only** when the local tempo autocorrelation clears a
confidence check. These are observational timelines, not fabricated effect
control lists. `CONTEXT_TO_ACTION_EVIDENCE.json` retains preceding energy,
low-band, transient and spectral state, but makes no causal "DJs choose X when
Y" claim. The capped nomination set cannot estimate genuine transition
frequency, track establishment time, or a set's energy arc.

## Archetype comparison and next evidence gate

No action sequence is confirmed well enough to classify as a recurrent
real-DJ choreography. The observable short-repeat/reduction shape is
*compatible in broad outline* with F/C3/B8; staged low-end transfer is
compatible with B8/D2. This is a hypothesis map, not evidence that their
executions match these references. No genuinely missing fifth behavior is
demonstrated, and the circumstances in which experienced DJs choose such a
behavior are not yet established. Phrase/vocal state, bass ownership, effect
wet/dry, source/target identity and post-landing tail remain unresolved here.

The strongest next experiment is **targeted human listening of eight
anonymized reference regions** listed with precise private paths and time
bounds in `dj_demonstration_mining/DJ_REFERENCE_LISTENING_SHORTLIST.json`.
The list spans exact-like repetition followed by reduction/arrival, strong
changes without exact repetition, a spectral change, and one ambiguous
original-match control. Ask first whether an action is actually DJ-made
versus native arrangement, then LIKE/NEUTRAL/DISLIKE and what change is
audible. Only human-confirmed examples should be aligned more densely and
considered against F/C3/B8/D2. No reference audio was exported or copied.

Reusable shadow tooling is `djenius.research.demo_alignment` and
`djenius.research.demo_mining`. Both require explicit private inputs and
outside-repository outputs. They are disconnected from Set Director,
Candidate Composer, renderer, templates and production context gates. Pilot 5
remains paused.

For a deterministic private rerun, invoke the aligner with `--normal-root
testMusic --normal-inventory <private LIBRARY_INVENTORY.json>
--reference-root testMusic/fromDJ --output <private
ORIGINAL_ALIGNMENT_RESULTS.json>`, then invoke the miner with `--inventory
<private DJ_REFERENCE_INVENTORY.json> --regions <private
REFERENCE_REGION_CANDIDATES.json> --alignment <private
ORIGINAL_ALIGNMENT_RESULTS.json> --output-dir <private output directory>`.
The repeat cache stores only derived scalar evidence, not waveform arrays.
