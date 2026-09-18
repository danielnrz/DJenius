# Renderer capability versus human-liked DJ performance

This is a read-only audit of the current production and private experimental
renderers against six human-liked, 40-second real-DJ excerpts. It does **not**
authorize a new archetype, template change, audio variant, or Pilot 5. The
reference recordings and detailed measurements remain private under
`/tmp/djenius_reference_dj_transition/renderer_capability_audit/`.

## Blind reframe result

The sealed mapping was opened after the human verdict:
`REFRAME_BLIND_1` was the manipulated rhythmic-reframe performance;
`REFRAME_BLIND_2` was untouched control. Both were rated `LIKE`, but neither
was perceived as DJ work or as a different performance state. The performance
was called *too subtle*; the control sounded like ordinary playback. There was
no preference. The experiment fails its actual listening gate. Stop all
source-only gesture variants.

The held reframe lasted 7.663 seconds, so it did not fail because its
replacement drum layer was inaudible at −30 dB: that captured-drum layer measured only
2.23 dB below the transformed mix. But the four-bar drum phrase had been
captured from the **same source song**. Its 20 ms RMS-envelope correlation
with the naturally occurring drums in the held passage was `.931` (`.770`
after a 1 kHz high-pass). The original vocal continued at unity at its
natural source-time position; 30% of its bass stem and 25% of its other stem
remained. The output's upper rhythmic envelope still correlated `.798` with
the control. Across three two-second held blocks, level changed by only
`−2.12`, `−2.59`, and `−2.24 dB`; low-band level changed by `−2.02 dB`.
There was substantial *sample* difference (held waveforms correlate `.461`),
but not a new rhythmic/musical identity. Before preparation and after payoff,
the files were sample-identical.

This distinguishes two claims: the reframe altered the waveform and was
pleasant enough to be liked, but the human did not recognize a deliberate
DJ performance. Neither loudness nor a multi-bar action schedule is a
substitute for a perceptually changed musical owner.

## What the liked references actually establish

The human called all six excerpts DJ action and liked them. The table records
finished-audio observations, not presumed mixer controls. No excerpt has a
high-confidence original-song/stem alignment, so exact DJ actions remain
partly unidentifiable.

| Excerpt | Strongest supported audible structure | Unverified mechanism |
|---|---|---|
| DJREF_01 | Low-rich rhythmic bed → bass/level withdrawal around 20–22 s → staggered low return and fuller state. | Exact loop, filter, stem control, or second song. |
| DJREF_02 | Music clears around 16–20 s → stronger repeat-like bed; human hears processing continue over the music. | Delay/reverb type, feedback or wet/dry settings. |
| DJREF_03 | Stable 2 s repeat-like frame for roughly 12 s → near-mute/reset (`−21.5 dB` local two-second change) → strong return (`+25.6 dB`). | Added drums, exact tempo move, source identities. |
| DJREF_04 | Deep thinning → long sparse territory → later percussive/low-rich arrival; human hears concurrent extra music/layers. | Number and identities of independent music sources. |
| DJREF_05 | Human hears music plus drums; bass/level thin across roughly 10 s and sparse continuation persists. | Whether those drums were newly added, retained or native. |
| DJREF_06 | Full low-driven bed → large clearance (`−13.2 dB`) → sparse pulsing bridge → fuller return (`+12.1 dB`); human hears slowdown. | A measured monotonic deck-speed or pitch ramp. |

The disliked DJREF_07 had a brief effect/recovery followed by roughly
32 seconds of steady full bed. The neutral DJREF_08 also had several stages.
Thus stage count or extra FX alone does not explain preference. The recurring
perceptual property is that rhythm, density, bass or musical context changes
*consequentially* through a prepared state and a following state. DJREF_05
also warns against declaring maximal complexity mandatory.

The comparisons above are descriptive: the reference numbers are within
different finished masters, not level-matched A/B intervention sizes against
their unprocessed originals.

## Production DSP inventory: supported versus scheduled intent

| Primitive family | Actual production capability | Important limit |
|---|---|---|
| Gain, crossfade, EQ, bass swap, filtering | Implemented in `transitions.py`, `eq.py`, and bespoke reference-template bar envelopes. Accepted F/C3/B8/D2 already demonstrate audible two-deck ownership. | The typed `GAIN`, `EQ_*`, `FILTER_*` action schedule is not a general independent DSP lane. Many actions are recorded as intent while compilation chooses a family/existing operation. |
| Echo, delay, reverb, tails | Echo-out and fixed stem/vocal taps; F/C3 tails clear before landing, B8 has a continuous bounded postlanding loop/riser tail. `reverb_wash` has bounded wetness/decay. | No general long-lived FX bus with separately automatable feedback/filter/wet-dry and release. Generic reverb is shape-preserving within its source buffer. |
| Repeats/loops/hold | `loop_roll`, `loop_shorten`, and B8's state-continuous captured loop. | Generic repeats are bounded source-buffer transformations; no freely addressable, clocked hold/freeze or slice sequencer. |
| Tempo/speed | Fixed-window target beatmatch/time-fit exists; reference target master and stems share one coherent multichannel clock. A resampling `tape_stop` exists. | No independently scheduled whole-deck/source tempo ramp or validated pitch-coupled brake/restart performance. The DJREF_06 slowdown is heard by the user but not objectively identified as a monotonic ramp. |
| Stem and drum mixing | Optional cached four-stem separation; C3/B8/D2 selectively clear and reveal stems. Legacy bass swap/mashup exists. Target drums can be previewed. | No reusable, independently clocked stem/rhythm **replacement-and-ownership** lane executing typed `STEM_GAIN/MUTE/SOLO` across arbitrary bars. Generic procedural percussion is summed on top, not paired with source-drum clearance. |
| Sampler and extra layers | Beat-scheduled deterministic kick/snare/hat/noise/impact/reverse-cymbal one-shots; fixed templates combine source, target, stems, loop and FX. | The sampler has no prerecorded musical third-source lane; its procedural event level is bounded. A reverse cymbal is not reverse deck playback. DJREF_04's independent layer count is unverified. |
| Gate, beat jump, scratch/reverse | Phrase cut and fixed source release; typed `BEAT_JUMP`; private click-safe stop experiment. | No general rhythmic gate/slicer/beat-jump executor, backspin, track reverse or scratch. The private 0.975 s stop was an objective intervention but failed human listening. |

These claims come from the implementations—not technique names—in
`djenius/audio/transitions.py`, `djenius/audio/creative_fx.py`,
`djenius/audio/groove_sampler.py`, `djenius/audio/reference_template_renderer.py`,
`djenius/audio/joint_reference_set_renderer.py`, `djenius/audio/stems.py`,
`djenius/audio/transition_preparation.py`, and
`djenius/core/performance_recipe.py`. The private capability inventory records each
primitive's deterministic/timing/range/lifetime status and code symbol.

## Layering versus ownership

The hypothesis is **partly true**, not absolute. The generic sample layer
adds procedural events to an existing transition, and generic creative FX
transform one fixed source buffer. `PerformanceRecipe` has an expressive
action vocabulary, but the compiler maps most actions to existing transition
families and retains the detailed schedule mainly as provenance. This makes
adding a bounded decoration easier than instantiating an arbitrary,
independently routed musical state.

There is important counterevidence: C3/B8/D2 bespoke renderers already
remove source components and stage target rhythm/bass. The failed private
reframe even removed original source drums completely. Its failure therefore
does **not** prove DJenius lacks subtractive DSP or that simply muting harder
would succeed. The substitute rhythm was nearly the same rhythm; vocals and
musical phrase never changed ownership. The selected stem bundle's summed
reconstruction error was about 25.3 dB below the source, but that does not
certify absence of bleed/artifacts (DECISIONS D009). Current frozen
two-deck transitions remain human-approved; this audit does not revise them.

## Gap classification and next primitive

- **Supported and already audibly effective:** fixed phrase-aware
  gain/EQ/bass transfer, coherent target time-map, F/C3/B8/D2 target
  establishment, and bounded source tails on accepted pairs.
- **Supported but limited:** fixed-window tempo treatment, bounded echoes
  and loops, fixed-template stem control, and the shape-preserving tape-stop
  approximation.
- **Supported mainly as generic decoration:** summed procedural
  drums/impacts/noise and source-buffer reverb/filter effects without a
  corresponding independent source-component ownership contract.
- **Missing as reusable primitives:** an independently owned foreground
  rhythm-replacement lane; general rhythmic gate/slicer and beat-jump
  transport; independent musical-sample third lane; source reverse/backspin.
- **Not determinable from DJREF masters:** whether DJREF_04 has multiple
  independent songs, DJREF_05 truly adds drums, DJREF_06 truly brakes a
  deck, or any exact wet/dry/sidechain settings.

The highest-value next *primitive to investigate* is a beat-addressed
foreground rhythm-ownership/replacement lane. It would declare, together:
source-drum/bass clearance, one distinct compatible rhythm source (for
example a target drum stem), its own gain/filter/timing/release, and the
handoff back to full target. This generalizes a capability already used in
fixed C3/B8 formulas; it is **not** a fifth archetype or permission to make
every transition busier. It is supported by the liked layered/pulsed/music-
plus-drums impressions in DJREF_04/05/06, with the important uncertainty
that their exact source routing is unknown.

Before any user-facing audio, a future authorized implementation should
prove this routing on deterministic synthetic stems: bar/beat alignment,
actual source-drum removal, distinct rhythmic lane, single bass owner,
independent gain/filter/release, continuity, and clipping safety. Only then
would one controlled **song-to-song** human A/B test establish whether the
primitive improves experienced-DJ perception. Do not resume source-only
gesture R&D. A persistent FX bus is second priority; a full tempo brake is
third because DJREF_06 alone does not verify the exact time-domain control.

No production code, F/C3/B8/D2 choreography, renderer, context gate, model,
or audio was changed for this audit. Pilot 5 remains paused.
