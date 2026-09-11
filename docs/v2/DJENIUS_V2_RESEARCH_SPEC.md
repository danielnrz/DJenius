# DJenius V2
## Professional Autonomous DJ Research and Product Specification

**Status:** Pre-coding research and design specification  
**Research date:** 8 September 2026  
**Purpose:** Define what DJenius must become before V2 implementation starts  
**Primary principle:** DJenius must stop behaving like an AutoDJ that merely orders songs and fades between them. It must plan and perform a set with the timing, musical judgment, variation, transition vocabulary, sound design, and self-evaluation expected from a skilled modern DJ.

---

# 1. Executive Summary

DJenius V1 proved that the project can reliably:

- scan a local music library;
- analyze BPM, key, loudness, energy, phrases, and other descriptors;
- cache analysis;
- order tracks;
- render continuous mixes;
- expose CLI and local web workflows;
- pass extensive deterministic tests;
- keep user audio local.

However, the first serious human listening test exposed the central product problem:

> The software works technically, but it does not yet sound like a DJ performance.

The current system is too close to playlist automation. It can choose a song, choose a transition point, and fade or apply a limited transition, but the resulting performance does not demonstrate the creative behavior heard in real DJ sets: phrase-aware layering, bass swaps, drum manipulation, FX chains, loops, fills, build-ups, drops, stem control, deliberate tempo resets, cue choreography, transition samples, mashup moments, and long-range set storytelling.

Professional and modern DJ systems make this gap very clear. Current tools provide capabilities such as:

- stem isolation and stem-specific crossfading;
- stem-specific FX;
- beat-synchronized loops and beat jumps;
- samplers and sequencers;
- drum replacement and drum fills;
- flexible beatgrids for tracks with changing tempo;
- automatic mix-point linking;
- dozens of delay, echo, reverb, filter, roll, gate, crusher, and modulation effects;
- hot cues and live edit systems;
- vinyl brake, backspin, reverse, scratch, and beatmasher behavior;
- live mashups and acapella/instrumental combinations;
- automatic transition families beyond volume fades;
- build-up and breakdown effects such as risers, noise, spiral, reverb-up/down, and impact-style transitions.

This specification therefore redefines DJenius.

DJenius V2 is not merely:

> "software that automatically makes a continuous mix."

The target is:

> **A fully local autonomous DJ performance engine that analyzes a user's music, plans a coherent musical journey, composes several plausible DJ performances for every handoff, auditions those candidates, chooses the strongest one, and renders a mix that plausibly sounds prepared by a skilled human DJ.**

The most important architectural change is that **transition selection must become transition composition and audition**.

Instead of:

```text
Track A -> choose fade -> Track B
```

V2 should operate more like:

```text
Understand A and B
-> identify usable musical phrases
-> generate multiple performance recipes
-> render short candidate previews
-> score musical and technical quality
-> reject bad candidates
-> select a technique that fits this moment in the whole set
-> render the chosen performance deterministically
```

The project should remain:

- local-first;
- privacy-preserving;
- deterministic where possible;
- explainable;
- inspectable;
- free/open-source oriented;
- usable without cloud APIs;
- safe when optional models or stem separation fail.

---

# 2. The Product Goal

## 2.1 Product vision

DJenius should act as a **personal autonomous DJ**, not an automatic playlist player.

Given a local folder of music and a high-level request such as:

```text
Make me a 45-minute energetic party set.
Start relatively familiar, build steadily, peak hard near the final third,
avoid long vocal clashes, use creative transitions but do not overdo effects.
```

DJenius should be able to:

1. understand every track deeply;
2. understand usable parts within each track;
3. decide which songs belong together;
4. decide where the set should rise, breathe, surprise, peak, and resolve;
5. decide how each transition should be performed;
6. create multiple transition candidates when there are several good options;
7. audition those candidates automatically;
8. choose a musically justified result;
9. render the complete performance;
10. explain what it did;
11. learn from the user's listening feedback.

The goal is not to imitate one particular DJ. The goal is to model **general professional DJ behavior** while allowing user-specific taste to develop over time.

---

# 3. What V1 Taught Us

The V1 engineering effort was valuable because it established the infrastructure needed for V2.

V1 already demonstrated that the project can support:

- deterministic rendering;
- real-audio QA;
- source/provenance checks;
- transition plans;
- caching;
- phrase-aware information;
- CLI and UI;
- local-only operation;
- user preferences;
- optional stems;
- real-music testing;
- robust Git and release workflows.

The problem is therefore not that DJenius lacks an application shell.

The problem is that its **performance model is too shallow**.

A transition can pass technical checks while still sounding:

- generic;
- predictable;
- mechanically timed;
- emotionally wrong;
- poorly staged;
- overlong;
- underdeveloped;
- random in track order;
- insufficiently creative;
- unlike a practiced DJ performance.

This creates a new V2 quality hierarchy:

```text
Level 1: File correctness
Level 2: Audio correctness
Level 3: Beat / phrase correctness
Level 4: Musical compatibility
Level 5: DJ technique appropriateness
Level 6: Set-level storytelling
Level 7: Human-perceived performance quality
```

V1 became strong at Levels 1-3 and partially addressed Level 4.

V2 must focus primarily on Levels 4-7.

---

# 4. Research: What Modern Professional DJ Systems Actually Provide

The following systems were reviewed as behavioral and feature references. They are **inspiration and benchmarks**, not dependencies that DJenius must copy.

---

## 4.1 rekordbox / AlphaTheta

rekordbox provides several capabilities directly relevant to DJenius V2.

### BPM and beatgrid analysis

rekordbox analyzes BPM and beat positions and allows manual correction. This reflects an essential professional principle: automated beat analysis is useful, but performance systems must represent uncertainty and allow correction.

### Key and phrase analysis

rekordbox exposes key analysis and phrase analysis so DJs can understand structure and anticipate where tracks develop.

### Mix Point Link

rekordbox can link specific mix-out and mix-in points so the next track begins at a musically prepared location automatically. The important lesson for DJenius is that **mix points are first-class objects**, not incidental timestamps.

### Stems

rekordbox supports separate control of:

- vocals;
- instruments;
- bass;
- drums.

It explicitly presents stems as a way to make live mashups and more precise transitions.

### Track editing

rekordbox Edit Mode supports operations such as:

- extending intros;
- extending outros;
- removing or shortening breaks.

This is important because professional DJs frequently prepare the source material rather than treating every commercial track as immutable.

### Groove Circuit

AlphaTheta's DDJ-GRV6 / rekordbox workflow includes Groove Circuit, which can:

- replace drum parts with other drum loops;
- create drum rolls;
- apply Trans effects;
- create fills;
- create build-ups;
- create breakdowns;
- apply release FX to drums.

This is extremely relevant to the user's observation that real DJs often add sounds and rhythmic material during transitions.

**DJenius implication:** V2 needs a groove/percussion layer, not only two-track blending.

---

## 4.2 Serato DJ Pro

Serato demonstrates a broad modern performance vocabulary.

### Stems

Serato can isolate:

- vocals;
- melody;
- bass;
- drums.

Serato explicitly promotes stems for:

- acapellas;
- instrumentals;
- smoother transitions;
- mashups.

Stem Pad FX add effects to separated elements rather than the entire track.

### Sampler

Serato's sampler can trigger:

- DJ stings;
- loops;
- acapellas;
- other samples.

### FX

Serato provides many built-in effects, including conventional and creative processing such as:

- filters;
- echoes;
- delays;
- large reverbs;
- bitcrushing;
- braker-style effects;
- noise-oriented effects.

### Serato Flip

Flip records and replays cue-point actions, enabling DJs to:

- extend intros/outros;
- shorten a track;
- skip parts;
- reorder sections;
- build custom edits;
- create transition versions.

### Advanced pad modes

Serato also supports performance operations such as:

- Beat Jump;
- Slicer;
- Stems FX;
- cue-driven edits.

**DJenius implication:** a professional autonomous system should not treat track playback as a simple linear interval. It should be able to create controlled edits and rearrangements.

---

## 4.3 Traktor Pro 4

Traktor Pro 4 provides another strong reference.

### Flexible beatgrids

Flexible beatgrids follow tempo changes inside tracks, enabling accurate:

- looping;
- beat jumps;
- beat effects;
- beat alignment.

This is particularly important when moving outside rigid electronic dance music into:

- disco;
- funk;
- live drums;
- older recordings;
- hip-hop edits;
- tracks with tempo drift.

### Stem separation

Traktor separates:

- drums;
- bass;
- vocals;
- instruments.

### Pattern Player

Pattern Player adds sequenced percussion and drum-machine patterns directly into DJ sets.

This confirms that professional DJ performance can involve **adding new rhythmic content**, not only manipulating the two source tracks.

### FX

Traktor includes dozens of deck and mixer effects, including:

- delay;
- reverb;
- modulation;
- filters;
- other beat-synchronized processing.

### Ozone Maximizer

Traktor includes mastering/loudness protection to increase perceived loudness while protecting against distortion.

### Flux / reverse / hot-cue behavior

Traktor supports performance techniques such as:

- reverse;
- backspin-style manipulation;
- hot-cue jumping;
- returning to the underlying groove.

**DJenius implication:** timing-safe performance manipulation should be designed so creative actions can happen without permanently losing synchronization.

---

## 4.4 Algoriddim djay Pro

djay is especially important because it combines modern automation with creative DJ tools.

### Automix

Current Automix supports multiple automatic transition families such as:

- Fade;
- Filter;
- EQ;
- Echo;
- Dissolve;
- Neural Mix;
- other creative transition options.

It can also:

- choose automatic transition points;
- adjust transition duration in bars;
- sync BPM;
- perform tempo blending;
- manage song ranges.

### Crossfader FX

Crossfader FX goes beyond basic volume fading and includes effects such as:

- Echo;
- Filter;
- Tremolo;
- Sweep;
- Riser;
- Neural Mix transitions.

### Neural Mix

Neural Mix can independently manipulate:

- vocals;
- drums;
- bass;
- harmonics.

Modern versions add:

- stem crossfaders;
- stem-specific FX;
- stem-specific loop routing;
- echo tails when muting stems;
- stem-specific automatic transition behavior.

### Instant FX

Recent versions include operations such as:

- Echo Out;
- Vinyl Stop;
- short loops;
- Beatmasher;
- Neural Mix Echo Out.

### Sequencer and looper

djay also includes music-production-style tools that can:

- record loops;
- sequence loops;
- quantize them;
- synchronize them to the playing track.

### Fluid Beatgrid

Variable beatgrid support is used for cross-genre and changing-tempo material.

**DJenius implication:** the state of the art for automatic mixing is already beyond crossfades. V2 must aim beyond current AutoDJ behavior by adding **candidate generation and self-audition**, not merely catching up to one transition menu.

---

## 4.5 VirtualDJ

VirtualDJ demonstrates several other useful performance ideas.

### Stems + FX

Effects can be applied specifically to:

- vocals;
- melody;
- rhythm.

### Sampler and StemSwap

Its sampler can trigger samples and even swap stems with sampled material.

### Stems + FX pads

Examples include:

- vocal echo;
- vocal reverb;
- instrumental beat-grid processing;
- instrumental echo.

### Scratch pad

VirtualDJ provides predefined automated scratch patterns that can be triggered without losing the beatgrid.

### Intelligent Automix

VirtualDJ detects:

- song structure;
- beats;

and uses this information for automatic transition selection.

It also provides an Automix Editor for adjusting timing and transitions.

**DJenius implication:** an autonomous DJ should have editable performance actions and timing, while scratch/performance routines can be represented as reusable deterministic recipes.

---

## 4.6 Mixxx

Mixxx is important because it is open-source and shows the minimum feature vocabulary expected from capable DJ software:

- BPM detection;
- beat detection;
- key detection;
- sync;
- hot cues;
- looping;
- multiple decks;
- effects;
- samplers;
- harmonic mixing;
- variable BPM grids;
- Auto DJ.

Mixxx's documentation also makes an important conceptual distinction: automated mixing is useful, but it does not replace the decisions a DJ makes about rhythm, frequency, volume, and musical context.

**DJenius implication:** V2 should explicitly target the gap between AutoDJ and human performance rather than describing basic automation as "professional DJing."

---

# 5. Research: Dedicated DJ Performance Hardware

Modern DJ performance cannot be understood by looking only at software.

---

## 5.1 Pioneer DJ RMX-1000

The RMX-1000 is a particularly useful reference because it shows the kinds of sound manipulation DJs use to make transitions feel performed.

### Scene FX: Build-up

Examples include:

- Noise;
- Echo;
- Spiral Up;
- Reverb Up;
- band-pass echo.

### Scene FX: Breakdown

Examples include:

- high-pass echo;
- low-pass echo;
- Crush Echo;
- Spiral Down;
- Reverb Down.

### Isolator FX

Three-band frequency manipulation can be combined with:

- Cut/Add;
- Trans/Roll;
- Gate/Drive.

### X-Pad samples

Beat-synchronized samples include:

- Kick;
- Snare;
- Clap;
- Hi-hat.

Samples can be repeated/rolled at different rates.

### Release FX

Exit techniques include:

- Back Spin;
- Echo;
- Vinyl Brake.

This hardware directly explains part of what the user heard in professional DJ sets: the "sounds between songs" are often intentionally triggered percussion, noise, build-up effects, impacts, echoes, and release effects.

---

## 5.2 AlphaTheta RMX-IGNITE

The 2026 RMX-IGNITE continues the same concept with modernized:

- performance FX;
- live remix controls;
- enhanced sampler;
- Groove Roll.

The important design lesson is that a DJ performance system benefits from a **separate performance layer** on top of track playback.

DJenius V2 should therefore model:

```text
Source tracks
+
Performance controls
+
Additional synchronized material
=
DJ performance
```

rather than:

```text
Track A + Track B = transition
```

---

# 6. Research: How DJs Think About Track Order

A technically compatible track is not automatically the right next track.

Professional set construction combines several dimensions.

---

## 6.1 Harmonic compatibility

Camelot-style harmonic mixing is a useful starting point.

Safe basic moves commonly include:

- same key;
- one Camelot step up;
- one step down;
- relative major/minor across the same Camelot number.

However, key compatibility is only a shortlist mechanism.

A harmonically compatible track can still be completely wrong because of:

- genre;
- energy;
- rhythm;
- mood;
- vocal density;
- instrumentation;
- arrangement;
- audience expectations;
- the stage of the set.

DJenius must never use Camelot compatibility as the main definition of "good next song."

---

## 6.2 Tempo compatibility

BPM should be interpreted as a **tempo relationship**, not a raw difference.

The planner should recognize:

- near-equal tempo;
- time-stretchable tempo;
- half-time/double-time relationships;
- intentional BPM jumps;
- tempo reset opportunities;
- tracks with variable tempo;
- tempo corridors appropriate for the current set.

Examples:

```text
70 <-> 140
75 <-> 150
87 <-> 174
```

may be rhythmically related despite looking numerically distant.

---

## 6.3 Energy

Energy must be modeled over time, not only as one number per song.

For each track, DJenius should estimate an **energy envelope**:

```text
intro
-> build
-> verse
-> pre-chorus
-> chorus/drop
-> breakdown
-> second peak
-> outro
```

A DJ may mix from a low-energy region of one high-energy track into a high-energy region of another track.

Therefore transition planning should use **section-local energy**, not only track-level averages.

---

## 6.4 Groove

Two songs at 128 BPM can feel completely different.

DJenius should model:

- kick placement;
- snare/clap placement;
- swing;
- syncopation;
- percussion density;
- onset density;
- bass rhythmic pattern;
- drum timbre;
- straight vs shuffled feel;
- halftime/double-time feel.

Groove compatibility is one of the biggest missing pieces in naive AutoDJ systems.

---

## 6.5 Emotional and stylistic trajectory

Set planning should model:

- genre;
- subgenre;
- mood;
- aggression;
- warmth;
- darkness/brightness;
- tension;
- release;
- nostalgia;
- euphoria;
- sadness;
- vocal intensity;
- instrumentation;
- timbre.

The planner needs both:

- **continuity**, when the set should flow;
- **contrast**, when the set should create a memorable change.

---

# 7. The Core V2 Design Principle: Performance Recipes

A V2 transition must no longer be represented by only:

```text
type = filter_sweep
start = 123.4 s
duration = 16 s
```

It should be represented as a **performance recipe**.

Example:

```yaml
transition_id: T07
source: Track_A
target: Track_B

musical_context:
  source_section: chorus_out
  target_section: intro_to_drop
  bars: 16
  tempo_relation: compatible
  key_relation: 8A -> 9A
  energy_goal: +0.15
  vocal_policy: avoid_overlap

actions:
  - bar: 1
    action: start_target
    stems: drums
    gain_db: -12

  - bar: 5
    action: target_drum_gain
    ramp_db: [-12, -4]

  - bar: 9
    action: source_bass_kill
    curve: smooth_2bars

  - bar: 9
    action: target_bass_in
    curve: smooth_2bars

  - bar: 11
    action: noise_riser
    duration_beats: 8
    gain_db: -16

  - bar: 13
    action: source_loop
    beats: 4

  - bar: 14
    action: loop_shorten
    sequence: [4, 2, 1]

  - bar: 15
    action: source_echo
    feedback: 0.42
    wet: 0.28

  - bar: 16
    action: impact
    gain_db: -12

  - bar: 16
    action: release_source

  - bar: 16
    action: target_full_mix
```

This representation is essential because a real DJ transition is usually a **sequence of actions**, not one effect.

---

# 8. Required V2 Track Intelligence

Every track should receive a richer analysis profile.

---

## 8.1 Identity and metadata

Store:

- filepath;
- content hash;
- title;
- artist;
- album;
- duration;
- codec;
- sample rate;
- channels;
- user tags;
- analysis version;
- confidence metadata.

---

## 8.2 Rhythm

Required:

- global BPM;
- BPM confidence;
- local BPM over time;
- variable-tempo zones;
- beats;
- downbeats;
- beat index within bar;
- time signature estimate where possible;
- bar boundaries;
- phrase boundaries;
- onset strength;
- rhythmic density;
- swing/shuffle estimate;
- halftime/double-time hypotheses.

The system should explicitly keep alternative tempo hypotheses when ambiguity exists.

Example:

```text
primary BPM: 72.1
alternative BPM: 144.2
confidence: 0.61
```

---

## 8.3 Structure

Required functional sections:

- start;
- intro;
- verse;
- pre-chorus when detectable;
- chorus;
- drop;
- build;
- break;
- bridge;
- instrumental;
- solo;
- outro;
- end.

For each section:

- start/end;
- boundary confidence;
- label confidence;
- number of bars;
- energy mean;
- energy slope;
- vocal density;
- bass density;
- drum density;
- harmonic intensity;
- candidate mix-in score;
- candidate mix-out score;
- drop/landing strength.

---

## 8.4 Tonality

Required:

- global key;
- key confidence;
- Camelot representation;
- local key / tonal stability;
- chord estimates where practical;
- harmonic change rate;
- dissonance indicators.

DJenius should distinguish:

```text
global key compatible
```

from:

```text
the exact 16-bar overlap is harmonically compatible
```

The second is much more useful.

---

## 8.5 Loudness and dynamics

Required:

- integrated LUFS;
- short-term loudness;
- section-local loudness;
- true/sample peak;
- RMS;
- crest factor;
- loudness range;
- dynamic complexity;
- transient density.

---

## 8.6 Stems

Where local stem separation succeeds, maintain:

- vocals;
- drums;
- bass;
- other/harmonics.

For every stem calculate section-local:

- RMS;
- loudness;
- activity;
- onset density;
- spectral centroid;
- confidence/quality estimate;
- bleed/artifact indicator.

Stem quality must be considered before a stem-heavy transition is allowed.

---

## 8.7 Vocal intelligence

Required:

- vocal vs instrumental probability;
- active vocal regions;
- vocal density;
- lead-vocal confidence;
- overlap risk;
- sparse vs dense vocals;
- likely chorus vocals;
- likely rap/spoken/singing distinction when confidence is sufficient.

Optional later:

- lyrics;
- word-level timing;
- thematic similarity;
- explicit wordplay opportunities.

---

## 8.8 Timbre and style

Required local embeddings/descriptors should represent:

- timbre;
- instrumentation;
- production style;
- genre;
- subgenre;
- brightness;
- warmth;
- aggression;
- texture;
- acoustic/electronic character;
- danceability;
- mood.

---

# 9. Set Director: Planning the Whole Performance

V2 should introduce a dedicated **Set Director**.

The Set Director is different from the transition planner.

Its job is to decide:

```text
Where is this set going?
```

---

## 9.1 Set arc types

Built-in arc templates:

### Smooth journey

- coherent style;
- modest tempo movement;
- harmonic continuity;
- restrained FX;
- longer blends;
- gradual energy changes.

### Warm-up to peak

- lower-energy opening;
- increasing rhythmic density;
- controlled BPM lift;
- stronger tracks later;
- major peak in final third;
- optional cooldown.

### Peak-time

- high average energy;
- shorter setup;
- bolder transitions;
- drops;
- loops;
- drum manipulation;
- more aggressive performance.

### Wave

Repeated:

```text
build -> peak -> breathe -> rebuild
```

### Narrative

Prioritize:

- emotional progression;
- lyric/theme relationships;
- contrast;
- recognizable moments.

### Open-format party

Allow:

- larger genre changes;
- larger BPM moves;
- recognizable hooks;
- wordplay;
- echo/reset transitions;
- tempo resets;
- quick mixes;
- minimixes.

### Experimental/remix

Allow:

- stems;
- live mashups;
- drum swaps;
- looping;
- layered material;
- unusual key/tempo movement when audition passes.

---

## 9.2 Set-level constraints

The planner should penalize:

- same artist repeated too soon;
- same transition technique repeated too often;
- excessive key stasis;
- excessive key jumping;
- monotonous energy;
- constant high energy with no breathing room;
- repeated vocal-on-vocal transitions;
- repeated long blends;
- repeated hard cuts;
- excessive FX use;
- excessive tempo warping;
- too many consecutive songs from the same style cluster.

---

## 9.3 Technique memory

The planner must remember what it recently performed.

Example state:

```json
{
  "last_techniques": [
    "filter_blend",
    "filter_blend",
    "bass_swap"
  ],
  "recent_fx": ["echo", "filter"],
  "recent_stem_moves": ["drums_only"],
  "recent_transition_lengths_bars": [16, 16, 8]
}
```

Technique selection should include a **novelty/diversity penalty**.

This prevents the V1 problem where a technique such as `filter_sweep` dominates simply because it scores safely.

---

# 10. Transition Technique Library

DJenius V2 should eventually support a broad repertoire. Not every technique should be implemented in the first coding milestone, but the architecture must accommodate all of them.

---

## 10.1 Foundation transitions

### A. Equal-power crossfade

Use when:

- tracks are compatible;
- arrangement is sparse;
- user requests restraint;
- confidence is low.

Avoid as the default answer for everything.

### B. Long EQ blend

Typical sequence:

- incoming highs/mids;
- gradual channel blend;
- bass remains from outgoing;
- bass swap on phrase boundary;
- outgoing mids/highs removed.

Best for:

- house;
- techno;
- trance;
- compatible groove.

### C. Bass swap

Switch low-frequency ownership at a phrase boundary.

Requirements:

- strong beat alignment;
- compatible kicks/bass;
- low vocal risk.

### D. Filter blend

Use low-pass/high-pass movement to create space.

Must support:

- resonance control;
- wet/dry control;
- musical automation curves.

### E. Phrase cut

A short, clean switch exactly at a strong phrase/downbeat.

Useful when:

- long overlap would clash;
- source and target both have strong structural landmarks.

---

## 10.2 Drop-oriented transitions

### F. Drop swap

Align the outgoing phrase ending with the incoming drop.

### G. Double-drop / simultaneous drop

Use only when audition confirms:

- harmonic compatibility;
- bass compatibility;
- drum compatibility;
- no catastrophic masking.

### H. Breakdown-to-drop

Move from a sparse/breakdown region directly into a strong incoming drop.

### I. Slam cut

Fast intentional cut into the next track.

Must be distinguished from an accidental abrupt edit.

---

## 10.3 Echo / reverb transitions

### J. Echo out

- reduce or cut dry source;
- allow beat-synced echo tail;
- launch incoming phrase.

### K. Stem echo out

Apply echo only to:

- vocals;
- drums;
- instrumental;
- selected stem.

### L. Reverb wash

Extend selected content into a reverb tail while clearing the frequency spectrum for the next track.

### M. Reverb-up / reverb-down

Use as build/breakdown automation rather than static wet reverb.

---

## 10.4 Loop transitions

### N. Phrase loop

Create a 4/8/16-beat loop from a musically safe region.

### O. Loop shortening

Example:

```text
4 beats -> 2 -> 1 -> 1/2 -> release
```

### P. Loop roll

A temporary repeating slice that returns to the original timeline or transitions away.

### Q. Beatmasher / beat repeat

Rhythmic re-triggering with quantized subdivisions.

### R. Slicer-style transition

Chop a phrase into synchronized slices and re-sequence a short rhythmic pattern.

---

## 10.5 Drum and groove transitions

### S. Drum overlay

Bring in target drums before the rest of the target.

### T. Drum swap

Replace outgoing drums with:

- target drums;
- a compatible local loop;
- a generated/approved percussion pattern.

### U. Drum fill

Insert a 1/2/4-beat fill before the new phrase.

### V. Percussion bridge

Use hi-hat, shaker, clap, snare, or kick material to bridge a sparse transition.

### W. Pattern-player transition

Create a short synchronized drum pattern that temporarily connects two otherwise difficult tracks.

---

## 10.6 Build-up / breakdown FX

### X. Noise riser

Synthesize filtered white/pink noise with:

- increasing cutoff;
- increasing level;
- optional pitch movement.

### Y. Downlifter

Reverse energy direction into a breakdown or reset.

### Z. Impact

Use a short transient/low-frequency hit at the landing.

### AA. Cymbal / crash marker

Use sparingly at strong phrase boundaries.

### AB. Spiral / pitch-rise FX

Pitch/delay feedback rises into the landing.

### AC. Spiral-down

Descending pitch/delay effect for release.

### AD. Gate / Trans

Rhythmic volume gating synchronized to beat subdivisions.

### AE. Roll / Trans combination

Rhythmic repetition plus gating for builds and fills.

---

## 10.7 Tempo-change transitions

### AF. Gradual tempo blend

Slowly move source and/or target toward a shared tempo.

### AG. Half-time / double-time handoff

Recognize compatible metrical relationships.

### AH. Echo reset

Use echo tail to hide a larger BPM change.

### AI. Reverb reset

Use a wash to decouple rhythms.

### AJ. Brake reset

Use vinyl/tape stop, then launch the next track at its natural tempo.

### AK. Backspin reset

Use a short controlled backspin into a tempo/genre change.

### AL. Hard phrase reset

Intentional silence or impact at a phrase boundary followed by new BPM.

Silence must be musically intentional and short, not an accidental gap.

---

## 10.8 Stem transitions

### AM. Vocal-out / instrumental-in

Remove source vocal while retaining its drums or harmonics, then introduce target.

### AN. Acapella over instrumental

Use source vocal over target instrumental.

Requirements:

- vocal key compatibility;
- phrase alignment;
- lyric timing;
- stem quality.

### AO. Instrumental under acapella

Use target instrumental beneath source vocal.

### AP. Vocal swap

Replace one vocal with the other while preserving a common rhythmic/harmonic bed.

### AQ. Drum-stem swap

Outgoing harmony/vocal with incoming drums.

### AR. Bass-stem swap

Independent bass ownership transition.

### AS. Stem tease

Briefly introduce:

- a vocal hook;
- drum groove;
- instrumental motif;

before the full target arrives.

### AT. Stem mute FX

Mute selected stem with:

- echo tail;
- reverb tail;
- filter decay.

---

## 10.9 Hot-cue and edit transitions

### AU. Hot-cue jump

Jump to a prepared musical landmark.

### AV. Intro edit

Generate/choose an extended DJ-friendly intro.

### AW. Outro edit

Extend or create a safer mix-out region.

### AX. Cue choreography

Replay a short sequence of musically meaningful cue points.

### AY. Reprise

Return to a different region of a previously used track.

### AZ. Mini-mix

Use several short recognizable appearances within a compact time window.

---

## 10.10 Turntablism-inspired transitions

These are later-stage capabilities because bad implementation will sound artificial.

### BA. Vinyl brake

Tempo decelerates toward stop.

### BB. Tape stop

Pitch and speed fall together with a characteristic curve.

### BC. Backspin

Rapid reverse/pitch movement.

### BD. Reverse release

Brief reverse operation before landing.

### BE. Scratch routine

Quantized scratch gestures represented as deterministic motion envelopes.

### BF. Scratch fill

Very short scratch gesture used like a fill, not a full routine.

---

## 10.11 Creative relationship transitions

### BG. Wordplay

Transition between songs using related words/lyrics.

### BH. Toneplay

Use matching or complementary tonal motifs.

### BI. Hook-to-hook

Move recognizable hook into recognizable hook.

### BJ. Live mashup

Combine compatible stems/sections from two tracks for longer than a normal transition.

### BK. Genre shift

Deliberately move between genres using:

- rhythmic bridge;
- shared sample;
- tempo reset;
- stem bridge;
- echo/reverb reset.

### BL. BPM drop

Intentional tempo discontinuity used as a dramatic moment.

---

# 11. V2 Effect Library

The renderer should expose effects as modular DSP building blocks.

---

## 11.1 Mixer / EQ

Required:

- gain;
- trim;
- channel fader;
- equal-power crossfader;
- 3-band isolator;
- parametric EQ where useful;
- low-cut;
- high-cut;
- kill switches;
- pan;
- stereo width with safety limits.

---

## 11.2 Filters

Required:

- low-pass;
- high-pass;
- band-pass;
- resonant filter;
- filter sweep automation.

---

## 11.3 Delay family

Required:

- mono delay;
- stereo delay;
- ping-pong delay;
- beat-synced echo;
- dub echo;
- feedback automation;
- post-fader echo tails.

---

## 11.4 Reverb family

Required:

- short room;
- plate-like;
- large hall;
- wash;
- reverb-up;
- reverb-down;
- stem reverb;
- post-fader tails.

---

## 11.5 Rhythmic FX

Required:

- roll;
- loop roll;
- beat repeat;
- beatmasher;
- gate;
- trans;
- tremolo;
- stutter.

---

## 11.6 Modulation / texture

Later-stage:

- flanger;
- phaser;
- chorus;
- bitcrush;
- distortion;
- drive;
- resonator;
- pitch echo;
- spiral-style feedback.

---

## 11.7 Release FX

Required:

- echo release;
- vinyl brake;
- tape stop.

Later:

- backspin;
- reverse release.

---

# 12. Additional Sounds: What "The Sounds Between Songs" Should Become

DJenius needs a dedicated **Performance Sample & Synthesis System**.

It should support:

- risers;
- downlifters;
- impacts;
- kick;
- snare;
- clap;
- hi-hat;
- shaker;
- cymbal/crash;
- drum fills;
- sweeps;
- noise bursts;
- tonal stabs;
- sub impacts;
- reverse cymbals;
- percussion loops.

## 12.1 Do not blindly bundle copyrighted sample packs

Preferred approaches:

1. procedurally synthesize basic FX;
2. create our own generated sample library;
3. allow the user to add local sample packs;
4. support CC0/public-domain packs with a provenance manifest;
5. never copy samples from commercial DJ software.

## 12.2 Procedural synthesis should be first-class

Examples:

### Noise riser

```text
white/pink noise
-> bandpass or highpass
-> cutoff automation
-> amplitude envelope
-> optional stereo movement
```

### Impact

```text
short noise transient
+ low-frequency sine sweep
+ optional reverb tail
```

### Drum fill

Can be generated from approved one-shot samples and quantized to the current BPM.

This keeps DJenius local and legally clean.

---

# 13. Candidate Generation: The Biggest Architectural Change

For every transition, DJenius should create several plausible performance plans.

Example:

```text
A -> B

Candidate 1:
16-bar EQ blend + bass swap

Candidate 2:
8-bar drum-stem tease + filter + impact

Candidate 3:
echo-out + hard drop

Candidate 4:
4-beat loop -> loop roll -> riser -> drop

Candidate 5:
source acapella over target instrumental

Candidate 6:
vinyl brake reset + target intro
```

Not all candidates are always allowed.

The generator should use:

- section structure;
- phrase confidence;
- BPM relationship;
- groove;
- key;
- vocal activity;
- stem quality;
- energy goal;
- previous techniques;
- genre/style;
- user preference;
- global set arc.

---

# 14. Transition Feasibility Rules

Before rendering, techniques must pass hard feasibility checks.

Examples:

## Long blend requires

- stable beatgrid;
- acceptable tempo difference;
- sufficient phrase length;
- acceptable harmonic overlap;
- acceptable vocal overlap.

## Bass swap requires

- meaningful low-frequency energy in both tracks;
- aligned downbeat;
- acceptable kick interaction.

## Acapella overlay requires

- usable vocal stem;
- compatible key or safe key shift;
- aligned phrase;
- low lyric/vocal collision;
- sufficient stem quality.

## Drum swap requires

- strong drum stem;
- compatible groove or deliberate genre-change plan.

## Vinyl brake reset requires

- reset-style transition allowed;
- strong target landing;
- not recently overused.

Hard constraints should prevent silly technique choices before expensive rendering.

---

# 15. The Audition Lab

This is the defining V2 component.

DJenius should automatically render short transition previews before committing to the full set.

---

## 15.1 Preview window

For example:

```text
16-32 seconds before handoff
+
transition
+
16-32 seconds after handoff
```

This is enough to judge most transition behavior without rendering the full set.

---

## 15.2 Technical metrics

Reject candidates with:

- NaN/Inf;
- clipping;
- excessive true peak;
- unintended silence;
- discontinuity/click;
- invalid source range;
- out-of-bounds stem use;
- broken duration;
- phase discontinuity;
- unstable time-stretch;
- severe stem artifacts.

---

## 15.3 Beat metrics

Measure:

- downbeat alignment;
- beat phase error;
- onset coincidence;
- kick alignment;
- sync drift;
- local tempo mismatch.

---

## 15.4 Spectral metrics

Measure:

- low-frequency collision;
- bass masking;
- spectral mud;
- excessive high-frequency buildup;
- spectral holes;
- transition spectral continuity.

---

## 15.5 Vocal metrics

Measure:

- vocal-on-vocal overlap;
- vocal density;
- stem bleed;
- intelligibility proxy;
- whether vocals were intentionally or accidentally chopped.

---

## 15.6 Harmonic metrics

Measure:

- local chroma compatibility;
- key clash;
- dissonance increase;
- tonal stability during the overlap.

---

## 15.7 Energy metrics

Measure:

- energy dip;
- energy spike;
- desired slope;
- drop strength;
- buildup shape;
- landing strength.

The candidate should be evaluated relative to the **intended performance goal**.

A deliberate breakdown should not be penalized simply for lower energy.

---

## 15.8 FX quality metrics

Detect:

- overlong reverb;
- echo feedback runaway;
- riser too loud;
- impact too loud;
- modulation depth too extreme;
- effect masking target drop;
- excessive effect density.

---

## 15.9 Technique appropriateness score

The system should ask:

```text
Is this technically valid?
Is it musically plausible?
Does it fit this style?
Does it fit the global set moment?
Is it too similar to the last transition?
```

---

# 16. Candidate Ranking

One possible conceptual score:

```text
candidate_score =
    0.18 * phrase_fit
  + 0.14 * groove_fit
  + 0.12 * harmonic_fit
  + 0.12 * energy_goal_fit
  + 0.10 * vocal_safety
  + 0.10 * spectral_cleanliness
  + 0.08 * beat_stability
  + 0.06 * technique_context_fit
  + 0.05 * user_preference
  + 0.05 * novelty
  - hard_penalties
```

This is only a starting framework.

Weights should become:

- style-specific;
- technique-specific;
- learnable from user feedback.

The crucial improvement is that the system ranks **rendered performances**, not abstract technique names alone.

---

# 17. Performance Grammar

V2 should define a reusable grammar of DJ actions.

Example action primitives:

```text
LOAD
START
STOP
GAIN
FADE
CROSSFADER
EQ_LOW
EQ_MID
EQ_HIGH
FILTER_LP
FILTER_HP
STEM_MUTE
STEM_SOLO
STEM_GAIN
LOOP_START
LOOP_END
LOOP_LENGTH
BEAT_JUMP
HOT_CUE
ROLL
GATE
ECHO
DELAY
REVERB
RISER
IMPACT
SAMPLE
DRUM_PATTERN
TEMPO_RAMP
KEY_SHIFT
VINYL_BRAKE
TAPE_STOP
BACKSPIN
REVERSE
SCRATCH
```

Every action should be:

- timestamped in musical time;
- quantized where appropriate;
- deterministic;
- inspectable;
- serializable;
- testable.

---

# 18. Musical Time Must Become Primary

V1 still relies heavily on seconds.

V2 should reason primarily in:

```text
beat
bar
phrase
section
```

Seconds remain the rendering coordinate system, but decisions should be expressed as musical time.

Example:

```text
Transition starts:
phrase 8
bar 1
beat 1

Bass swap:
bar 9
beat 1

Riser:
bar 13 beat 1 -> bar 16 beat 1

Target drop:
bar 17 beat 1
```

This is much closer to how a DJ thinks.

---

# 19. Variable Tempo and Flexible Beatgrids

Rigid BPM assumptions are not enough.

V2 needs:

```text
tempo_zone = {
  start_time,
  end_time,
  bpm,
  beat_phase,
  confidence
}
```

This enables:

- disco;
- funk;
- live drums;
- older songs;
- tempo-drifting recordings;
- cross-genre sets.

If beat confidence drops, the system should automatically restrict techniques that depend on precise synchronization.

---

# 20. Cue Intelligence

Every analyzed track should generate candidate cues.

Examples:

- safe intro;
- first clean downbeat;
- first verse;
- first chorus;
- first drop;
- breakdown;
- build;
- second drop;
- clean outro;
- final phrase.

Each cue needs:

```text
time
beat
bar
section
confidence
vocal_state
energy
use_cases
```

Example:

```json
{
  "time": 94.22,
  "section": "breakdown",
  "bar": 1,
  "confidence": 0.91,
  "use_cases": [
    "mix_in",
    "echo_reset",
    "acapella_overlay"
  ]
}
```

---

# 21. Genre-Aware Performance Policies

These should be heuristics, not laws.

---

## 21.1 House / techno

Favor:

- longer phrased blends;
- EQ mixing;
- bass swaps;
- filters;
- loops;
- subtle delays;
- drum overlays;
- tension/release;
- precise 8/16/32-bar structure.

---

## 21.2 Trance

Favor:

- harmonic progression;
- long phrases;
- breakdown/drop staging;
- reverbs;
- filters;
- risers;
- careful energy arcs.

---

## 21.3 Hip-hop / R&B

Favor:

- shorter transitions;
- phrase cuts;
- echo outs;
- cue jumps;
- wordplay;
- toneplay;
- acapella/instrumental techniques;
- scratches;
- tempo resets;
- beat juggling later.

---

## 21.4 Pop / open-format

Favor:

- recognizable hooks;
- faster track turnover;
- echo reset;
- riser/drop;
- stems;
- wordplay;
- quick cuts;
- genre changes;
- BPM changes;
- minimixes.

---

## 21.5 Drum & bass

Favor:

- double-time awareness;
- double drops where safe;
- phrase alignment;
- bass compatibility;
- rapid cue work;
- loops;
- high-energy transitions.

---

## 21.6 Chill / lounge

Favor:

- subtle blends;
- harmonic continuity;
- low FX density;
- long fades/EQ;
- gentle filtering;
- low surprise.

Again, the candidate auditioner should override generic heuristics when the actual audio disagrees.

---

# 22. User Taste and Personalization

DJenius is a personal DJ. It should learn.

After listening, the user should be able to mark:

```text
transition: good
transition: bad
too much effect
too boring
vocals clash
bad song choice
bad timing
too abrupt
great surprise
great song pairing
great energy change
```

The system should learn separate preferences for:

- track order;
- transition length;
- FX intensity;
- stem use;
- tempo changes;
- genre transitions;
- vocal overlap;
- creativity;
- repeated artists;
- set energy shape.

---

# 23. Preference Learning

V2 should start simple.

Store pairwise and categorical feedback locally.

Example:

```json
{
  "transition_id": "T07",
  "rating": -1,
  "reasons": [
    "too_much_reverb",
    "bad_vocal_overlap"
  ]
}
```

Then update:

```text
user_fx_reverb_preference -= small_step
user_vocal_overlap_tolerance -= small_step
```

Later, pairwise ranking can learn:

```text
Candidate B preferred over Candidate A
```

without needing large model training.

---

# 24. UI Requirements

The V2 UI should evolve from "generate mix" toward "inspect and direct a DJ performance."

---

## 24.1 Library view

Show:

- BPM;
- tempo confidence;
- key/Camelot;
- energy;
- genre/style;
- vocals;
- structure confidence;
- stem availability;
- analysis warnings.

---

## 24.2 Track detail

Show waveform with:

- beats;
- downbeats;
- bars;
- phrase boundaries;
- sections;
- vocal regions;
- energy curve;
- cue points;
- mix-in candidates;
- mix-out candidates.

---

## 24.3 Set Director view

Show:

- full track order;
- BPM trajectory;
- energy trajectory;
- key movement;
- genre movement;
- vocal density;
- transition techniques.

The user should be able to see whether the set is actually a journey.

---

## 24.4 Transition Inspector

For every handoff show:

```text
Candidate A: EQ blend
Score: 0.88

Candidate B: drum swap + riser
Score: 0.91

Candidate C: echo out
Score: 0.80
```

Allow:

- preview;
- select alternate candidate;
- regenerate candidates;
- lock technique;
- lock mix point;
- adjust creativity.

---

## 24.5 Performance timeline

Advanced view should show actions such as:

```text
Bar 1  incoming drums
Bar 5  target gain +3 dB
Bar 9  bass swap
Bar 13 loop source
Bar 15 echo
Bar 16 riser + impact
Bar 17 target drop
```

---

## 24.6 Creativity control

A user-facing slider:

```text
Safe -------- Balanced -------- Creative -------- Wild
```

This should affect:

- technique risk;
- FX density;
- stem usage;
- tempo jumps;
- mashups;
- drum replacement;
- cue manipulation;
- candidate diversity.

It must not disable hard audio-safety constraints.

---

# 25. Proposed V2 Architecture

```text
+---------------------------------------------------+
|                DJenius V2                         |
+---------------------------------------------------+

[Local Music Library]
        |
        v
[Analysis Engine]
  - rhythm
  - beatgrid
  - sections
  - key/chords
  - energy
  - groove
  - stems
  - vocals
  - embeddings
        |
        v
[Track Performance Profile]
        |
        +----------------------+
        |                      |
        v                      v
[Set Director]          [Cue / Section Intelligence]
        |                      |
        +-----------+----------+
                    |
                    v
          [Transition Composer]
                    |
           generate N recipes
                    |
                    v
             [Audition Lab]
          render short previews
                    |
          +---------+---------+
          | metrics + ranking |
          +---------+---------+
                    |
                    v
          [Performance Timeline]
                    |
                    v
       [Deterministic DSP Renderer]
                    |
                    v
           [Master Audio QA]
                    |
                    v
              [Final Mix]
                    |
                    v
          [Listening Feedback]
                    |
                    v
           [Preference Store]
```

---

# 26. Local Technology Research

The project should continue to prefer free/local components, but licenses must be reviewed before distribution.

---

## 26.1 All-In-One Music Structure Analyzer

`mir-aidj/all-in-one` can predict:

- BPM;
- beats;
- downbeats;
- beat positions;
- functional segment boundaries;
- segment labels such as intro, verse, chorus, bridge, outro.

It also exposes frame-level activations and embeddings.

**Strong candidate for V2 structure analysis.**

---

## 26.2 Demucs

Demucs can locally separate:

- drums;
- bass;
- vocals;
- other.

The maintained Demucs repository notes that v4 is based on Hybrid Transformer Demucs.

License: MIT in the original project.

**Strong candidate for optional/high-quality stem analysis.**

Stem separation must remain:

- cached;
- optional;
- failure-tolerant;
- quality-scored.

---

## 26.3 Essentia

Essentia can provide a very large analysis vocabulary:

- beats;
- BPM;
- onset rate;
- danceability;
- spectral features;
- loudness;
- key;
- chords;
- tuning;
- tonal descriptors;
- dynamic complexity;
- machine-learning embeddings/classifiers.

This is attractive technically.

However:

- Essentia library licensing is AGPLv3 for non-commercial/open use;
- pre-trained models may have non-commercial restrictions;
- commercial distribution requires careful licensing review.

**Use only after explicit dependency/license review.**

---

## 26.4 Spotify Pedalboard

Pedalboard provides local DSP including:

- compressor;
- gain;
- limiter;
- high-pass/low-pass filters;
- ladder filter;
- delay;
- reverb;
- pitch shift;
- distortion;
- phaser;
- chorus;
- bitcrush;
- VST3 loading.

This makes it attractive for prototyping V2 effects.

However Pedalboard itself is GPLv3 and includes GPL-related dependencies.

**Good prototyping option, but license implications must be reviewed before choosing the permanent renderer stack.**

---

## 26.5 Rubber Band

Rubber Band provides high-quality:

- time stretching;
- pitch shifting.

It allows tempo and pitch to be changed independently.

Important license point:

- GPL for open-source use;
- separate commercial licensing available.

DJenius already has experience with Rubber Band-compatible workflows, but distribution policy must be explicit.

---

## 26.6 LAION CLAP

CLAP provides joint audio/text embeddings and includes music-oriented checkpoints.

Potential uses:

- mood similarity;
- style similarity;
- semantic search;
- prompt-to-track matching;
- transition context embeddings.

It should remain optional because:

- model size and dependencies are non-trivial;
- semantic embeddings should not override direct musical evidence.

---

## 26.7 MOSS-Music - research candidate

Recent open music-understanding work such as MOSS-Music demonstrates that models can perform:

- music captioning;
- lyrics transcription;
- structural analysis;
- key/tempo/chord reasoning;
- instrument recognition;
- long-form music QA.

This is interesting for later research.

It is **not required for the first V2 implementation**, and model size/license/hardware suitability must be evaluated before integration.

---

# 27. DSP Implementation Strategy

V2 should not depend entirely on one third-party effect library.

Prefer a layered strategy.

### Native/core DSP

Implement simple, critical, deterministic operations ourselves where practical:

- gain;
- fades;
- crossfade curves;
- 3-band EQ;
- filter sweeps;
- sample mixing;
- noise synthesis;
- simple delay;
- simple gate;
- loop/roll;
- envelope automation.

### High-quality external local components

Use approved libraries for harder problems:

- time stretch;
- pitch shift;
- source separation;
- advanced reverb if necessary.

### Plugin support later

Optional VST3 support could let advanced users supply their own effects, but V2 must sound good without proprietary plugins.

---

# 28. Sound Safety Rules

Creative performance must never bypass safety.

Hard rules:

- no NaN/Inf;
- no digital clipping;
- true/sample peak ceiling;
- reasonable loudness target;
- no accidental silence;
- no click discontinuities;
- no invalid source reads;
- no unbounded echo feedback;
- no runaway reverb;
- no >100% wet transition unless explicitly valid;
- no untracked hidden audio layers;
- every additional sample has provenance.

---

# 29. Provenance V2

Every audible event should be explainable.

Example:

```json
{
  "output_range": [405.20, 406.00],
  "sources": [
    {
      "type": "track",
      "track_id": "A",
      "source_range": [188.2, 189.0],
      "stem": "vocals"
    },
    {
      "type": "track",
      "track_id": "B",
      "source_range": [16.0, 16.8],
      "stem": "drums"
    },
    {
      "type": "generated_fx",
      "generator": "noise_riser_v1",
      "seed": 42
    }
  ]
}
```

This allows QA to reason about complex multi-layer performances.

---

# 30. Testing Strategy

V2 must add a new test category:

> **Perceptual DJ behavior tests**

Traditional unit tests remain necessary but insufficient.

---

## 30.1 Unit tests

Examples:

- FX continuity;
- automation curves;
- beat quantization;
- loop length;
- stem routing;
- candidate feasibility;
- set-score components.

---

## 30.2 Synthetic audio tests

Use:

- impulses;
- sine tones;
- click tracks;
- known BPM;
- known downbeats;
- known phase;
- controlled stems.

These verify DSP correctness.

---

## 30.3 Real-music tests

Use private local music.

Never commit source tracks.

Test:

- structure analysis;
- candidate generation;
- render quality;
- style-specific behavior;
- BPM ambiguity;
- variable tempo;
- vocal collision;
- stem artifacts.

---

## 30.4 Transition benchmark suite

Create a private local benchmark of difficult pairs:

```text
same BPM / same key
same BPM / bad key
large BPM difference
half-time relation
vocal-heavy -> vocal-heavy
instrumental -> vocal
genre change
weak intro
weak outro
variable tempo
stem-friendly
stem-poor
short track
long ambient intro
strong double-drop candidate
```

---

# 31. Human Listening Benchmark

Automated metrics cannot fully judge DJ taste.

V2 requires structured human listening.

For each transition rate 1-5:

- musicality;
- timing;
- smoothness;
- creativity;
- energy control;
- vocal handling;
- bass handling;
- FX taste;
- surprise;
- professionalism;
- desire to keep the transition.

For full sets rate:

- track order;
- journey/story;
- pacing;
- variety;
- peak placement;
- transition variety;
- overall DJ-likeness.

---

# 32. V1 vs V2 Blind Comparison

A crucial release test:

Render the same source library using:

- V1-style baseline;
- V2.

Hide filenames.

Listen blindly.

V2 should win clearly on:

- musical intent;
- transition variety;
- creative performance;
- set coherence;
- DJ-likeness.

If it does not, V2 is not done even if every automated test passes.

---

# 33. Anti-Randomness Tests

The user's V1 listening impression was that track selection felt random.

Therefore V2 needs explicit tests proving otherwise.

For the same library:

1. generate planned order;
2. generate many shuffled orders;
3. calculate set-quality metrics;
4. verify planned set significantly outperforms random baselines;
5. inspect whether the planner produces a meaningful energy/style path.

Also ensure different seeds do not create nonsensical variation.

Randomness may diversify among **good alternatives**. It must never replace decision-making.

---

# 34. Transition Diversity Acceptance

A full V2 set should not simply replace `filter_sweep` with another repeated technique.

For a sufficiently diverse library, acceptance should require:

- multiple transition families;
- no single technique dominating without a documented musical reason;
- short, medium, and long transitions where appropriate;
- some restrained transitions;
- some creative transitions;
- safe fallback when confidence is low.

Example non-binding target:

```text
No single technique > 40% of transitions
unless the selected style explicitly calls for it.
```

---

# 35. Creativity Budget

Too many effects also sounds amateur.

Each set should have a creativity budget.

Example:

```text
subtle move       cost 1
stem tease        cost 2
loop build        cost 2
riser + impact    cost 3
live mashup       cost 4
scratch routine   cost 4
dramatic reset    cost 3
```

A smooth set may have:

```text
budget = 15
```

An experimental set:

```text
budget = 40
```

This prevents constant over-performance.

---

# 36. Effect Repetition Rules

Avoid:

```text
echo out
echo out
echo out
echo out
```

Track recent effect usage and penalize repeated chains.

Also distinguish:

```text
effect family
```

from:

```text
exact preset
```

Two filter transitions can still feel different if their choreography is different, but repeated identical recipes should be heavily penalized.

---

# 37. Transition Templates vs Generative Composition

V2 should use both.

### Templates

Safe reusable structures:

- 16-bar EQ blend;
- 8-bar bass swap;
- 4-bar echo release;
- loop-shortening build.

### Composer

Adjust templates based on:

- section length;
- vocals;
- energy;
- groove;
- target drop;
- set position.

The composer should not produce arbitrary DSP graphs with no constraints.

---

# 38. Performance Recipe Validation

Before rendering, validate:

```text
all actions within track bounds
all bars valid
all stems available
all FX parameters safe
no two bass owners unless intentional
no impossible cue jumps
no invalid loop
no target begins after its landing
no source ends before required action
```

The renderer should reject invalid recipes loudly.

---

# 39. Explainability

Every transition should be able to answer:

```text
Why this song next?
Why this mix point?
Why this technique?
Why this transition length?
Why these FX?
Why were other candidates rejected?
```

Example:

```text
Selected: 8-bar stem drum swap + echo release

Reasons:
- outgoing chorus has dense vocals;
- target intro has clean drums;
- BPM difference is 2.1%;
- target key is harmonically compatible;
- long full-spectrum overlap scored poorly because of vocal collision;
- previous two transitions were long blends, so a shorter technique improves variety;
- preview candidate scored 0.91 vs 0.82 for EQ blend and 0.79 for filter sweep.
```

---

# 40. Optional Local Language Model Role

A local language model can help with:

- interpreting user requests;
- describing set narratives;
- suggesting high-level performance intentions;
- interpreting lyrics/themes;
- explaining choices.

It should **not** directly process raw PCM or issue arbitrary renderer commands without validation.

Architecture:

```text
Local LLM proposes intent
-> deterministic planner constrains it
-> performance composer validates it
-> renderer executes approved recipe
```

---

# 41. V2 Priority Tiers

The complete vision is large. Implementation must be staged.

---

## P0 - Required for V2 to deserve the name

- improved beat/downbeat/phrase structure;
- section-local energy;
- groove features;
- robust cue intelligence;
- better Set Director;
- transition technique memory;
- performance recipe representation;
- at least 10 genuinely different high-quality transition families;
- sampler/percussion layer;
- procedural riser/impact FX;
- loops and loop rolls;
- echo/reverb release;
- drum overlay/drum swap;
- stems for selected transitions;
- candidate generation;
- preview rendering;
- automatic audition/ranking;
- transition inspector UI;
- human listening benchmark;
- V1-vs-V2 blind evaluation.

---

## P1 - Strong professional expansion

- live mashups;
- acapella/instrumental transitions;
- extended edit generation;
- hot-cue choreography;
- phrase-level reprises;
- genre-specific performance policies;
- tempo reset toolkit;
- advanced drum pattern player;
- beatmasher/slicer;
- vinyl/tape stop;
- backspin;
- preference learning;
- user sample packs;
- VST3 optional support.

---

## P2 - Advanced performance research

- automated scratch routines;
- wordplay detection;
- toneplay;
- lyric-aware hook matching;
- advanced multi-deck performances;
- 3/4-deck layering;
- generative percussion;
- controller/live-performance mode;
- real-time autonomous mixing;
- advanced music-language models;
- adaptive crowd-response input if a privacy-safe local signal is ever defined.

---

# 42. Recommended Coding Roadmap

---

## Phase 0 - Freeze and benchmark V1

Do not destroy the V1 baseline.

Create a repeatable benchmark:

- fixed private library;
- fixed V1 mixes;
- fixed metrics;
- listening notes.

**Output:** V1 baseline package.

---

## Phase 1 - Analysis V2

Implement:

- improved beat/downbeat representation;
- variable tempo zones;
- section confidence;
- section-local energy;
- groove descriptors;
- cue candidates;
- stronger vocal/stem activity representation.

**Gate:** analysis visualizations make musical sense on real tracks.

---

## Phase 2 - Performance Timeline / Recipe DSL

Implement the new transition representation.

No fancy FX yet.

Prove that recipes can express:

- EQ blend;
- bass swap;
- phrase cut;
- loop;
- echo release.

**Gate:** deterministic recipe serialization and rendering.

---

## Phase 3 - Core DJ Technique Engine

Implement high-value techniques:

1. EQ blend;
2. bass swap;
3. filter blend;
4. phrase cut;
5. echo out;
6. reverb wash;
7. loop transition;
8. loop shortening;
9. drum overlay;
10. riser + impact;
11. tempo reset;
12. stem handoff.

**Gate:** each technique passes both synthetic and real-audio listening tests.

---

## Phase 4 - Groove / Sampler Layer

Implement:

- sample engine;
- kick/snare/clap/hat;
- percussion overlays;
- drum fills;
- procedural risers;
- impacts;
- drum swap;
- pattern player.

**Gate:** added sounds stay beat-aligned and do not overwhelm the source.

---

## Phase 5 - Candidate Composer

For each handoff:

- generate 3-8 feasible recipes;
- respect global style;
- respect technique memory;
- reject invalid candidates before render.

**Gate:** candidates are meaningfully different.

---

## Phase 6 - Audition Lab

Render previews and score:

- beat;
- bass;
- vocals;
- harmony;
- loudness;
- energy;
- FX;
- novelty.

**Gate:** known bad candidates rank below good references.

---

## Phase 7 - Set Director V2

Replace greedy/random-feeling ordering with long-range planning.

Use:

- energy arc;
- tempo path;
- harmonic path;
- groove;
- style;
- vocals;
- diversity;
- set phase.

**Gate:** planned sets beat shuffled baselines.

---

## Phase 8 - UI V2

Add:

- set trajectory;
- waveform structure;
- transition candidates;
- preview;
- performance timeline;
- creativity controls;
- manual locks.

**Gate:** user can understand and override the DJ.

---

## Phase 9 - Personalization

Add structured listening feedback.

**Gate:** repeated feedback changes future technique selection predictably.

---

## Phase 10 - V2 certification

Run:

- full automated suite;
- private transition benchmark;
- multiple full real sets;
- blind V1 vs V2 listening;
- human scorecard.

No release until V2 is clearly more DJ-like than V1.

---

# 43. V2 Definition of Done

DJenius V2 is done only if all of the following are true.

### Analysis

- [ ] Beat/downbeat confidence works.
- [ ] Variable-tempo tracks can be represented.
- [ ] Phrase/section structure is usable.
- [ ] Local energy curves are reliable enough for planning.
- [ ] Vocal regions are usable.
- [ ] Stem quality is scored.
- [ ] Groove information influences decisions.

### Set planning

- [ ] Order is demonstrably better than random baselines.
- [ ] Energy arc is intentional.
- [ ] Tempo arc is intentional.
- [ ] Harmonic compatibility is used but not over-weighted.
- [ ] Artist/style repetition is controlled.
- [ ] Vocal pacing is controlled.
- [ ] Set has meaningful peaks and breathing room.

### Performance

- [ ] Transition is a multi-action recipe.
- [ ] At least 10 distinct transition families work well.
- [ ] Loops work.
- [ ] Echo/reverb release works.
- [ ] Drum/percussion additions work.
- [ ] Risers/impacts work.
- [ ] Bass swaps work.
- [ ] Stem transitions work when stems are trustworthy.
- [ ] Tempo resets work.
- [ ] FX repetition is controlled.

### Audition

- [ ] Multiple candidates are generated.
- [ ] Short previews are rendered automatically.
- [ ] Bad candidates are rejected.
- [ ] Ranking uses actual rendered audio evidence.
- [ ] Selection is explainable.

### Audio safety

- [ ] No clipping.
- [ ] No NaN/Inf.
- [ ] No accidental silence.
- [ ] No clicks.
- [ ] No invalid provenance.
- [ ] Loudness remains controlled.
- [ ] Effects cannot run away.

### UX

- [ ] User can preview transitions.
- [ ] User can choose alternate candidate.
- [ ] User can lock songs/points/techniques.
- [ ] User can control creativity.
- [ ] User can provide feedback.

### Human listening

- [ ] V2 clearly beats V1 in blind listening.
- [ ] Transitions no longer feel mostly like fades.
- [ ] Track order no longer feels random.
- [ ] Added sounds feel deliberate.
- [ ] Effects sound tasteful.
- [ ] Full set feels like a performance.

---

# 44. Research Conclusion

The most important conclusion is that DJenius does **not** need one more transition effect.

It needs a different performance model.

Modern DJ systems show that creative DJing combines:

- structure;
- beatgrids;
- cues;
- stems;
- loops;
- samples;
- effects;
- rhythm manipulation;
- track edits;
- transition timing;
- set storytelling.

The V2 system should therefore be built around four new ideas:

## 1. Set Director

Plans the musical journey.

## 2. Transition Composer

Creates a multi-action DJ performance, not one effect label.

## 3. Audition Lab

Listens computationally to several rendered possibilities before committing.

## 4. Performance Memory

Keeps the set varied and learns the user's taste.

If these four components work, the rest of the DJ tools become meaningful.

Without them, adding 50 effects would only produce a more complicated random AutoDJ.

---

# 45. Research Sources

The following sources informed this specification. Commercial products are used as feature references only.

## Professional DJ software and hardware

1. **rekordbox 7 Overview - AlphaTheta / rekordbox**  
   BPM/grid analysis, key/phrase analysis, Mix Point Link, stems.  
   https://rekordbox.com/en/feature/overview/

2. **rekordbox Professional Features**  
   Track Edit mode and performance preparation.  
   https://rekordbox.com/en/feature/professional/

3. **AlphaTheta DDJ-GRV6**  
   Groove Circuit, drum swap, drum roll/trans, build-ups and breakdowns.  
   https://alphatheta.com/en/product/dj-controller/ddj-grv6/black/

4. **AlphaTheta - Introducing DDJ-GRV6**  
   Live drum remixing and stem manipulation.  
   https://alphatheta.com/en/information/introducing-ddj-grv6-4-channel-performance-dj-controller/

5. **Serato DJ Pro**  
   Stems, sampler, FX, 4-deck operation.  
   https://serato.com/dj/pro

6. **Serato DJ Pro Expansions**  
   FX and Serato Flip.  
   https://serato.com/dj/pro/expansions

7. **Native Instruments Traktor Pro 4**  
   Flexible beatgrids, stems, Pattern Player, effects, Ozone Maximizer.  
   https://www.native-instruments.com/products/traktor-pro/

8. **Algoriddim djay Pro**  
   Neural Mix, Fluid Beatgrid, Crossfader Fusion, sequencer and looper.  
   https://www.algoriddim.com/djay-pro-mac

9. **djay Automix Settings**  
   Automatic, Fade, Filter, EQ, Echo, Neural Mix and tempo behavior.  
   https://help.algoriddim.com/user-manual/djay-pro-mac/settings/automix

10. **djay Crossfader FX**  
    Echo, filters, tremolo, sweeps, risers, stem effects.  
    https://help.algoriddim.com/user-manual/djay-pro-windows/dj-tools/effects/crossfader-fx

11. **djay Neural Mix**  
    Stem-level vocals/drums/bass/harmonic control.  
    https://help.algoriddim.com/user-manual/djay-pro-mac/neural-mix

12. **djay release notes**  
    Stem crossfaders, mute FX, Echo Out, Vinyl Stop, loops, Beatmasher.  
    https://www.algoriddim.com/djay-pro-mac/releasenotes

13. **VirtualDJ Effects**  
    Deck/master FX and stem-specific FX.  
    https://virtualdj.com/manuals/virtualdj/interface/decks/decksadvanced/effects.html

14. **VirtualDJ Pads**  
    Stems, sampler, StemSwap, stem FX, scratch patterns.  
    https://virtualdj.com/manuals/virtualdj/interface/decks/decksadvanced/pads.html

15. **VirtualDJ Features**  
    Intelligent Automix and editors.  
    https://virtualdj.com/products/virtualdj/features.html

16. **Mixxx 2.6 Manual**  
    Beat/key analysis, hot cues, looping, effects, samplers, variable tempo, Auto DJ.  
    https://manual.mixxx.org/2.6/en/

17. **Pioneer DJ RMX-1000**  
    Scene FX, Isolator FX, X-Pad samples, Release FX.  
    https://www.pioneerdj.com/en/product/dj-effectors/rmx-1000/

18. **AlphaTheta RMX-IGNITE**  
    Modern live performance effector and sampler.  
    https://alphatheta.com/en/information/meet-the-next-gen-rmx-ignite-effector/

## DJ technique and set-planning references

19. **Digital DJ Tips - Transitions Toolbox announcement**  
    Documents a modern transition vocabulary including wordplay, toneplay, live mashups, genre shifts, BPM drops, minimixes, stems, loops, hot cues and effects.  
    https://www.digitaldjtips.com/our-brand-new-dj-transitions-course-is-here/

20. **Mixed In Key - Build a Harmonic DJ Set**  
    Key, BPM, energy, arrangement, genre, groove and cue points.  
    https://mixedinkey.com/workflows/build-a-harmonic-dj-set/

21. **Mixed In Key - Plan a DJ Set with Harmonic Mixing**  
    Harmonic movement, BPM movement, energy and cue planning.  
    https://mixedinkey.com/workflows/plan-a-dj-set-with-harmonic-mixing/

22. **Mixed In Key - Camelot Wheel**  
    Basic harmonic relationships and energy-aware track choice.  
    https://mixedinkey.com/camelot-wheel/

## Local/open-source implementation research

23. **All-In-One Music Structure Analyzer**  
    Tempo, beats, downbeats, sections and labels.  
    https://github.com/mir-aidj/all-in-one

24. **Demucs**  
    Local drums/bass/vocals/other source separation.  
    https://github.com/vvigot/demucs

25. **Essentia Documentation**  
    Rhythm, tonal, loudness, spectral, danceability and machine-learning descriptors.  
    https://essentia.upf.edu/documentation.html

26. **Essentia Music Extractor**  
    Detailed rhythm and tonal descriptors.  
    https://essentia.upf.edu/streaming_extractor_music.html

27. **Essentia Licensing**  
    AGPL/commercial licensing and model restrictions.  
    https://essentia.upf.edu/licensing_information.html

28. **Spotify Pedalboard**  
    Local audio effects and processing.  
    https://github.com/spotify/pedalboard

29. **Rubber Band Library**  
    Time stretching and pitch shifting.  
    https://github.com/breakfastquay/rubberband

30. **LAION CLAP**  
    Local audio/text embeddings and music checkpoints.  
    https://github.com/LAION-AI/CLAP

31. **MOSS-Music**  
    Research reference for richer local music understanding.  
    https://github.com/OpenMOSS/MOSS-Music

---

# 46. Final Project Statement

**DJenius V2 is a local autonomous DJ performance system.**

It should not merely decide:

```text
what song comes next
```

It must decide:

```text
why that song comes next,
which musical regions should interact,
what a skilled DJ could plausibly do at that handoff,
which combination of EQ, stems, loops, samples, FX and timing best serves the moment,
whether the rendered result actually works,
and how that transition contributes to the journey of the entire set.
```

The final product should make a listener think:

> "Someone actually performed this."

That is the V2 target.
