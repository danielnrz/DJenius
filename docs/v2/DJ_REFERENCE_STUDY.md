# Shadow DJ-reference study (expanded private library)

This checkpoint keeps the 35 files in `testMusic/fromDJ/` separate from the
normal candidate-song library. It does not copy reference audio into Git, render
reconstructions, change the four accepted F/C3/B8/D2 templates, or modify any
production musical gate.

## Inventory and evidence type

All 35 files are decodable MP3s lasting roughly 13–39 minutes. Filename and
container metadata suggest 22 continuous-mix/set candidates, six extended or
multi-track mix candidates, five long-form unknown candidates, and two unknown
structures. These are *provisional format categories*, not proof of source
track identities, DJ authorship at any particular time, or transition quality.
No short standalone-edit file can be established from duration alone.

A long-form mix might provide evidence about track-to-track handoffs and set
sequencing. A standalone remix/edit, if confirmed later, could provide evidence
about builds, repetition, drops, and effect timing, but not necessarily about
choosing one full song after another. The two evidence types must not be merged.

## Shadow region-discovery workflow

The private discovery pass decodes each reference as mono 11.025 kHz audio and
computes two-second RMS, six broad spectral-band fractions, spectral centroid,
flatness, and attack activity. For each point it compares adjacent ten-second
windows, requiring at least two unusually changed dimensions. It retains at
most 20 separated, high-change regions per file and records a 40-second review
window plus before/after values. A short onset-autocorrelation tempo hypothesis
is computed only for selected regions; half/double-time ambiguity remains
unresolved. Source audio and snippets are not emitted.

The reusable, shadow-only command is:

```bash
python -m djenius.research.reference_regions --reference-root testMusic/fromDJ --output /tmp/dj_reference_regions.json
```

It requires an explicit `fromDJ` root, refuses an output inside the
repository, marks every region unverified, and records whether an interrupted
discovery run completed. The durable implementation independently reproduced
the private pass's 35 files and 673 nominations.

The pass nominated **673 candidate change regions** in 35 files. Within the
top five nominations per file (175 regions), 50 had simultaneous energy and
attack rise, 49 had an energy/attack reduction, 173 changed low-frequency
*spectral balance*, 172 changed spectral/timbral descriptors, 169 changed attack
activity, and 37 had differing uncertain tempo hypotheses. These counts are
biased by top-rank selection and correlated descriptors; they are not rates of
DJ techniques. In particular, a one-channel finished mix cannot identify
bass *ownership*, distinguish a filter sweep from changing instrumentation,
or prove that a rise/drop was performed by the DJ rather than present in the
track's arrangement.

The current pass does **not** confirm vocal phrase completion, repeatable
motifs, loop shortening, source release, target preview, stem activity,
post-release tails, or a track-to-track handoff. A candidate region is a cue
for later inspection, never an automatic transition label. Region review
should record establishment, action onset and phrase alignment, vocal state,
tempo treatment, repetition, bass/source/target roles, build/drop shape,
tail and target establishment only when those elements can actually be heard
or measured with suitable source evidence.

## Comparison with the four approved archetypes

The nominated energy reductions and arrivals are *compatible in shape* with
F's reset/release or B8's build/handoff. Low-frequency balance changes are
compatible in shape with the deliberate bass transfer in D2/B8/C3. Timbral
and attack changes are compatible with staged reveals or EQ movement.
Compatibility in shape is not behavioral attribution. None of these signal
patterns can yet be responsibly classified as:

- A: already represented well;
- B: represented, but execution is simpler;
- C: not represented by F/C3/B8/D2; or
- D: not a transition behavior/out of scope.

The private coverage audit explicitly records `NOT_YET_ASSIGNABLE` for each
pattern. There is **no confirmed recurrent missing choreography** and no
evidence-based fifth-archetype proposal at this checkpoint. It is equally
premature to claim our existing archetypes match the detailed timing of these
references.

## Next reference-study gate

Inspect a small, stratified set of high-ranking regions across distinct files,
including energy rises, reductions, spectral changes, and tentative tempo
changes. Mark which regions are genuine DJ edits/handoffs versus native song
structure, then annotate only confirmed actions as abstract timing/ownership
descriptions. Compare those confirmed actions with F/C3/B8/D2 and human
preference before considering a fifth archetype. Do not reproduce a reference
waveform as a product objective.

Detailed private inventory, region nominations, signal catalog, coverage audit,
and conclusion remain under
`/tmp/djenius_reference_dj_transition/dj_reference_study/`.
