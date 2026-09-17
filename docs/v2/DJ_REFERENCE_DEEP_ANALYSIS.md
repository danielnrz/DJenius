# Human-confirmed real-DJ choreography study

This is a shadow-only study of eight private 40-second DJ-reference excerpts.
All eight were heard by the human as `DJ_ACTION`: `DJREF_01`–`06` were
`LIKE`, `DJREF_07` was `DISLIKE`, and `DJREF_08` was `NEUTRAL`. The exact
descriptions are retained in private `HUMAN_DJ_REFERENCE_LABELS.json`.
No reference audio, source identities, waveform samples, or extracted audio
are committed. F/C3/B8/D2, renderer, context gates, and Pilot 5 remain frozen.

## Observable action sequences

Times below are relative to each 40-second excerpt. Local pulse trackers
suggest roughly 112–123 BPM, but beat/downbeat phase is unverified,
especially during sparse passages; claiming exact bars would be false
precision. The private timelines retain 2-second spectral, level,
percussive and repeat measurements.

| Clip | Human preference | Finished-audio sequence and limits |
|---|---|---|
| `DJREF_01` | LIKE | Full low-rich bed to ~20 s → bass/level collapse at 20–22 s (low-band fraction ~`.80` to ~`0`) → staggered low return and fuller final four seconds. Short repeat-like audio exists; loop control is unproved. |
| `DJREF_02` | LIKE | Music to ~16 s → reduced/cleared four seconds → stronger low-rich, strongly repeat-like bed from ~20 s. Human hears an effect continuing over music; wet/dry and source/target identity are not isolated. |
| `DJREF_03` | LIKE | ~4–16 s has unusually close adjacent 2-second waveform repetitions (`.966`–`.986` correlation) → ~17–20 s near-mute/reset (about `−21.5 dB` two-second change) → strong re-entry near 20 s (about `+25.6 dB`). Human hears continuing processing with pauses and says this makes sad/slow material work in a remix. |
| `DJREF_04` | LIKE | Strong reduction near 3 s → sparse territory through ~20 s → more percussive/low-rich material after ~20 s (percussive fraction rises to roughly `.38`–`.50`). Human hears multiple effects and concurrent extra music; independent source identities are not confirmed. |
| `DJREF_05` | LIKE | Low-rich material through ~14 s → gradual low/level reduction across ~14–24 s → quiet, low-light continuation. Human hears music plus drums, but we cannot tell added drums from retained or native arrangement without an original/stem alignment. |
| `DJREF_06` | LIKE | Loud low-driven music to ~20 s → strong clearance → ~23–30 s sparse percussive/pulsing bridge → fuller return near 30 s. Human hears echo, further processing, slowdown and music change. The heard slowdown is not an independently measured monotonic tempo ramp. |
| `DJREF_07` | DISLIKE | A brief reduction/recovery near 5–7 s, then a comparatively steady full bed for ~32 s. The listener described the echo/effect as ordinary/basic. |
| `DJREF_08` | NEUTRAL | Variable low-band texture to ~20 s → stronger full bed → short later dip. The listener hears echo and loop; tested adjacent 2/4/8-second waveform comparisons do not verify exact buffer reuse. |

These are observable phases, not counts of independently operated mixer
controls. The finished mix cannot uniquely identify delay, reverb, filter,
stems, a second track, or the exact dry/wet state. No original song in these
regions has a high-confidence source alignment. The excerpt may begin or end
within a longer action.

## Preference and choreography

The six liked clips each show three or four observable phases; the disliked
one shows two. The liked examples generally develop an effect into a
musically consequential change—rhythmic framing, low-end clearance,
layering, reduction/reset, or a stronger following state. `DJREF_07` changes
briefly and then remains relatively steady. This supports *evolving,
purposeful choreography* as a hypothesis, not an acceptance rule:
`DJREF_08` also has three phases but is neutral, and `DJREF_05` may be a
comparatively simple music-plus-drums gesture that the listener liked.
The human-liked persistent processing in `DJREF_02`/`03` also shows that
“echo is bad” would be the wrong lesson; effect fit and musical consequence
matter more than effect names or raw effect count.

`DJREF_03` is the strongest context-transformation example. It retains a
recognizable/repeated frame, creates bounded sparse space, and returns in a
stronger rhythmic context. That can explain the listener's report that a
sad/slow song becomes usable in the remix. It is **one perceived example**,
not proof that arbitrary mismatched A→B songs are rescuable. A proposed
`TRANSFORMABLE_CONTEXT` class remains shadow-only until identified pairs
and controlled human comparisons show that the treatment changes the
set-context judgment.

`DJREF_04` may involve richer shared musical territory than frozen C3's
target-drum runway/source-vocal echo/bass handoff. The human hears several
simultaneous layers; the waveform supports staged sparse-to-rhythmic
development, not their independent identities. `DJREF_05` supports the
appeal of music plus drums, but not a distinct, verified percussion bridge:
C3, B8 and D2 already introduce target rhythm. `DJREF_06` has a convincing
full→sparse pulse→full reset topology richer than frozen F's one-pickup-bar
release/taps; an actual deck-speed slowdown or different song cannot be
established from this finished excerpt alone.

## Archetype decision

There is **not enough evidence for a fifth archetype**. `DJREF_03` and
`DJREF_06` share a reduction/reset core, but that is F's existing principle;
their distinctive pulse, loop and slowdown details have not recurred in two
independently corroborated examples. The multi-layer and drum-bridge ideas
have one liked example each and no confirmed source separation. A larger
effect stack would risk reproducing the human-disliked `DJREF_07` outcome.

The highest-value next experiment is a **private, same-pair, human-gated
comparison** on one contextually difficult but plausibly transformable
adjacency: frozen F versus one manually specified richer F-family reset
using recognizable material, a bounded rhythmic/sparse bridge, clean
ownership clearance, and a clear re-entry. Keep the pair, cues and renderer
controlled. Ask whether this changes the *musical-context* judgment, not
only whether more DSP is audible. This is a recommendation only; no variant
was implemented or rendered in this checkpoint. No shorter follow-up
listening pack is needed before that controlled comparison.

Private artifacts are under
`/tmp/djenius_reference_dj_transition/dj_reference_deep_analysis/`.
