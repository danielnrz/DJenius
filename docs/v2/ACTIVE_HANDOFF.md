# DJenius V2 Active Handoff

## OWNERSHIP TEXTURE A/B FAILED — STRUCTURAL SALIENCE IS THE BOTTLENECK

2026-09-18. After the user's blind verdict, the sealed hashes were checked:
`OWNERSHIP_TEXTURE_BLIND_1` was **TRANSIENT_TEXTURE_CORRECTED** and
`OWNERSHIP_TEXTURE_BLIND_2` was the **PHASE_CORRECTED_BASELINE**, byte-identical
to the previous human-preferred phase render. The human noticed no specific
DJ action in either, heard both as essentially ordinary music, and found
no meaningful difference. The +3 dB donor upper-band treatment therefore
failed the perceptual test. **No more EQ/transient/brightness variants.**
The earlier ownership and phase blind preferences remain valid as local
comparisons, but this repeat result shows the gesture is not robustly
salient; do not blame the listener or promote it to production.

Seven private requested reports are in
`/tmp/djenius_reference_dj_transition/ownership_salience_followup/`.
On the exact phase-corrected render, the two-bar preparation differs from
untouched source by only `-0.67 dB` overall, with unchanged upper-transient
rate; the four-bar/`7.69 s` held state differs by `-1.67 dB` overall and
`-0.78 dB` in the main midrange; the release differs by `-0.57 dB`; then
`7.69 s` of payoff is sample-identical to normal playback. The drum/bass
transfer is real: source rhythm is roughly `34/26 dB` attenuated and the
donor owns the low band. But retained vocal plus harmonic/other source
material exceeds the donor by about `11 dB` across `170–2800 Hz`, so the
central arrangement can still read as an ordinary song variation. This is
a measured explanation for weak salience, **not** proof of the human's
moment-by-moment perception. Liked DJREF_03/05/06 show clearer sparse or
reset states in finished masters; their unknown stems/controls cannot be
assumed or copied.

The selected *next structural variable*, only if later authorized, is
**OWNERSHIP_STATE_CONTRAST**: vary attenuation depth of the retained source
`other`/harmonic-bed stem through the existing ownership envelope while
holding the vocal, donor, phase, timing, source drum/bass controls,
mastering, and payoff fixed. This tests whether a more legible sparse
vocal-plus-independent-rhythm state is what is missing. Entry cue and
unchanged payoff remain secondary contributors; phrase boundaries are not
certified. No new audio, production code, F/C3/B8/D2 change, context gate,
fifth archetype, or Pilot 5 was made in this follow-up. **Stop here.**

## OWNERSHIP DONOR TEXTURE-ONLY A/B — AWAITING BLIND HUMAN LISTENING

2026-09-18. The user authorized one private, two-condition blind A/B of the
phase-corrected rhythmic-ownership proof. The two listening WAVs and sealed
mapping are under
`/tmp/djenius_reference_dj_transition/rhythmic_ownership_texture_ab/`:
`OWNERSHIP_TEXTURE_BLIND_1.wav`, `OWNERSHIP_TEXTURE_BLIND_2.wav`,
`OWNERSHIP_TEXTURE_BLIND_MANIFEST.json`, plus
`OWNERSHIP_TEXTURE_RESPONSE_TEMPLATE.txt`. **Do not reveal the mapping
before the human verdict.** `OWNERSHIP_TEXTURE_ANALYSIS.json` contains the
private objective audit.

The baseline is byte-identical to the previous human-preferred
phase-corrected ownership render. The only intervention is a fixed
zero-phase, smooth +3 dB shelf on the *same donor* above 2 kHz, with
unity below 500 Hz. This was selected before rendering as a conservative
fraction of the measured ~9.7 dB upper-percussion deficit; it does not
try to clone source drums. Source/donor recordings, phase (`10,592`
sample advance), time-fit, stem routing, drum/bass attenuation, gain
envelopes, mastering transfer, length, and payoff are unchanged. The
two results are sample-identical outside the donor lane, and their raw
difference is accounted for by the donor shelf alone.

Measured donor 1–4 kHz and 4–10 kHz energy rose `2.75/3.00 dB`; donor and
finished-mix <250 Hz levels moved by less than `0.000001 dB`. Full/held
loudness changed only `+0.017/+0.049 LU`, with no clipping or unsafe
boundary jump. Kick-like and snare-like 16th-grid accent phase remained
essentially unchanged. These checks rule out a gross level, low-end, or
phase confound; **they do not establish a perceptual improvement**. Two
synthetic DSP tests passed; a verify-only rerender reproduced both blind
PCM24 WAVs byte-for-byte. Accepted reference audio remains frozen.

**Stop for human A/B listening.** No production F/C3/B8/D2 change,
ownership-lane promotion, context change, fifth archetype, target-song
render, or Pilot 5. If the treated version does not win on integration
and reduced amateur impression, do not generate more EQ variants.

## OWNERSHIP PHASE A/B HUMAN VERDICT — IMPROVED, NOT PRODUCTION-READY

2026-09-18. After receiving the blind verdict, the sealed mapping and WAV
SHA-256 hashes were verified: `OWNERSHIP_PHASE_BLIND_1` was
**PHASE_CORRECTED** and `OWNERSHIP_PHASE_BLIND_2` was **CURRENT_PHASE**
(byte-identical to the prior `OWNERSHIP_C.wav`). The human chose corrected
phase for overall preference, professionalism, and DJ-likeness; perceived
intentional rhythm control was `YES` versus `SOMEWHAT`. Both files were
`LIKE` and groove-coherent, but DJ work and amateur quality were still
`SOMEWHAT`. The corrected condition's new-musical-state rating was
`SOMEWHAT` versus `YES` for current phase. This supports a real
within-pair phase improvement, **not** an experienced-DJ-quality pass or
an instruction to maximize groove correlation.

Five private follow-up JSON reports are under
`/tmp/djenius_reference_dj_transition/rhythmic_ownership_phase_followup/`.
Low/mid 16th-grid accent correlation moved from `-.943/-.430` to
`+.940/+.937`; broadband onset correlation moved from `.016` to `.444`.
The donor remains a distinct track's drum stem, and the corrected finished
mix is rhythmically different from untouched source. No clipping or abrupt
entry/exit was found. The strongest *measured but unproven* remaining
material-quality candidate is donor upper-percussion/transient texture:
about `9.7 dB` less >1 kHz energy than the original drum stem. Entry and
payoff phrase alignment is uncertain; the final payoff is unchanged source
playback. None of those residual issues was isolated by this phase-only
human comparison.

For future experimental ownership work, provisionally require
**musically salient accent-phase compatibility**, preserving independent
rhythmic identity and verifying quality by human listening. This is not a
production numerical gate. The next recommended *single* test variable,
if separately authorized, is the same donor's upper-percussion/transient
spectral balance while holding corrected phase, source/donor material,
routing, levels, envelopes, duration, and payoff fixed. Do not render it
now. No new audio or production changes were made in this follow-up; the
ownership lane remains private. Pilot 5 remains paused.

## RHYTHMIC OWNERSHIP PHASE-ONLY A/B — AWAITING BLIND HUMAN LISTENING

2026-09-18. The user authorized a single controlled A/B to test the measured
donor-rhythm accent-phase error in the human-audible but amateur-sounding
ownership transfer. Private artifacts are in
`/tmp/djenius_reference_dj_transition/rhythmic_ownership_phase_ab/`.
Only `OWNERSHIP_PHASE_BLIND_1.wav` and `OWNERSHIP_PHASE_BLIND_2.wav` are
listening files. Their deterministic condition mapping is sealed in
`OWNERSHIP_PHASE_BLIND_MANIFEST.json`; **do not reveal it before the human
verdict**. The response form is `OWNERSHIP_PHASE_RESPONSE_TEMPLATE.txt`.

The correction was fixed *before rendering* from prior low- and mid-band
accent measurements: advance the existing independent drum signal by two
16th notes (`10,592` samples, `0.240181` s, half a beat). No donor tempo/stretch,
source interval, stem routing, gain, ownership timing/envelopes, mastering,
or payoff changed. The current-phase control is byte-identical to the
previous human-heard `OWNERSHIP_C.wav`; outside the donor-lane window the two
new renders are sample-identical. Low-band accent correlation changes from
`-.943` to `+.940`, mid-band from `-.430` to `+.937`, and broadband onset
correlation from `.016` to `.444`. These are alignment checks, **not** a
listening success claim. Both versions are unclipped and pass the same
sample-discontinuity audit. The private `OWNERSHIP_PHASE_ANALYSIS.json` records
the waveform/control proof and measurement limits.

Two synthetic phase-routing tests passed. A verify-only rerender reproduced
both blind PCM24 WAVs byte-for-byte without disclosing the mapping. No
production code, F/C3/B8/D2 choreography, context gate, or accepted audio
changed, so no full application regression is warranted. **Stop now for
human listening.** If corrected phase improves correlation but still sounds
amateur, do not keep making phase variants; move to the documented secondary
cause in a later, separately scoped task. Pilot 5 remains paused.

## RHYTHMIC OWNERSHIP BLIND REVEAL — DISTINCT DJ STATE, QUALITY GATE FAILED

2026-09-18. The user returned all three blind labels. The sealed hashes and
byte-identical blind copies were checked before mapping them to conditions:
`OWNERSHIP_BLIND_1` was **ADDITIVE**, `OWNERSHIP_BLIND_2` was **CONTROL**,
and `OWNERSHIP_BLIND_3` was **OWNERSHIP_TRANSFER**. The human rated all three
`LIKE`, but heard no DJ work or new state in additive/control. Only ownership
transfer was heard as DJ work and a new musical state; active rhythm control
was `SOMEWHAT`. It was the most DJ-like file, yet felt like an **amateur edit**
and was not preferred. Thus the foreground-ownership perceptibility threshold
passed, while the experienced-DJ/quality gate did **not**. Do not promote the
lane or change production choreography.

Seven private requested JSON reports plus reproducible read-only measurement
scripts are under
`/tmp/djenius_reference_dj_transition/rhythmic_ownership_followup/`.
The strongest measurable quality concern is rhythm **accent phase**, not
clicking or an abrupt gain mute. Source and independent low-band 16th-grid
patterns correlate `-.943` at their rendered phase, but about `+.947` with
an approximately two-16th-slot (half-beat) offset; corresponding mid-band
patterns change from `-.430` to `+.936`. This offset recurs through the
two-bar preparation, all four ownership bars, and the one-bar release. The
private donor search had checked tempo, level/steadiness and distinctness,
but not *accent-phase compatibility*. A downbeat/tempo match was therefore
insufficient for an integrated groove.

The central state genuinely clears source drums/bass by roughly `34/26 dB`
and retains vocal/harmonic source identity; its replacement is audible. But
the independent rhythm has about `9.7 dB` less >1 kHz transient energy than
the original source drum stem. The held full-mix level changes only about
`1.0–2.4 dB` from untouched playback across the four bars. Source vocals
remain active but uncut; lyric/syllable conflict is unproven. Entry and exit
gain envelopes are gradual and sample-click-safe; the return becomes
sample-identical original playback. The source section's internal four-bar
phrase phase is not certified, so entry/payoff phrase mismatch remains a
secondary uncertainty, not a diagnosed fact. Finished DJREF_04/05/06 audio
has more consequential staged thinning/pulsing/layering, but their exact
stems and controls are unknown; do not infer those details.

The **single recommended next variable**, if separately authorized, is the
independent lane's transient/accent phase relative to the source groove
(approximately an eighth-note correction), holding the same source, donor
rhythm, cue interval, envelopes, levels, mastering, and duration fixed. This
is a strong measured hypothesis, **not** proof of the human's subjective
cause or permission to render another version now. No new WAV, production
code, archetype, context rule, or Pilot 5 was created during this follow-up.
The existing handoff section below describes the pre-verdict experiment and
is retained as history.

## PRIVATE RHYTHMIC OWNERSHIP LANE PROOF — AWAITING BLIND HUMAN LISTENING

2026-09-18. The user explicitly authorized one source-only, three-way blind
rhythmic-ownership experiment after the renderer-capability audit. This
supersedes that audit's earlier prohibition on *further source-only renders*
for this one controlled proof only. Pilot 5, context gates, production
F/C3/B8/D2, the renderer, and the fifth-archetype decision remain frozen.
At session start, local and fetched origin HEAD matched `99a97cc`; the only
pre-existing untracked path was `.claude/`, untouched. No production code or
accepted reference audio was modified.

The private experiment and test-only reusable `IndependentRhythmLane` module
are under `/tmp/djenius_reference_dj_transition/rhythmic_ownership_proof/`.
One anonymous normal-library source uses a stable 16-bar, 30.720 s chorus
window with beatgrid confidence `.981`, prominent source identity, and cached
four-stem reconstruction error 25.30 dB below the full master. A distinct
normal-library drum stem (not `fromDJ`) uses a compatible 7-bar excerpt,
time-fit by only about 0.69%. Its held rhythmic envelope correlates `-.327`
with the original source drums, unlike the failed same-source repeat.

`OWNERSHIP_A.wav` is untouched source. `OWNERSHIP_B.wav` adds that independent
rhythm while source drums/bass stay intact. `OWNERSHIP_C.wav` uses the **exact
same external rhythmic material, gain, and timing** as B, but clears source
drums/bass over two bars, holds independent rhythmic ownership for four
bars (7.686 s), then restores the original rhythm over one bar before four
bars of normal payoff. All versions share the same 16-bar source interval,
downbeat clock, length, mastering transfer, and PCM format. No target song,
fromDJ waveform, echo, riser, slowdown, or creative extra effect was used.

In C's held state, the source drum/bass stem contributions are reduced
`33.98/26.02 dB`; the independent lane sits `4.86 dB` below the transformed
mix. The retained vocal+harmonic identity is `1.98 dB` below that mix. The
source-to-independent drum-envelope correlation is `-.327`; the A-to-C
mixed rhythmic-envelope correlation is `.199`. These are objective routing
and perceptibility checks, **not** proof that the human will hear skilled DJ
performance. Integrated loudness A/B/C is `-14.000/-13.800/-14.455 LUFS`
under one fixed gain/soft-clip transfer; all are finite and unclipped. Bar
boundary sample jumps are below ordinary global p99.9 transient deltas.

Exactly three deterministic blind copies, `OWNERSHIP_BLIND_1.wav` through
`OWNERSHIP_BLIND_3.wav`, and `OWNERSHIP_RESPONSE_TEMPLATE.txt` are ready. The
private mapping is sealed in `OWNERSHIP_BLIND_MANIFEST.json`; **do not reveal
it before the human verdict**. `OWNERSHIP_STATE_ANALYSIS.json` contains all
private provenance and stage evidence. Five synthetic private lane tests
passed; a verify-only rerender reproduced all six PCM24 WAV payloads
byte-for-byte and checked the sealed mapping without printing it. No full
application regression is warranted because production code did not change.

**Next action:** stop for the user's blind A/B/C listening response. If C is
not clearly more DJ-like than control and additive overlay, do not make more
rhythm-lane variants; reassess capability gaps as requested. No Pilot 5 or
song-to-song transition is authorized by this checkpoint.

## RENDERER / REAL-DJ CAPABILITY AUDIT — SOURCE-ONLY R&D STOPPED

2026-09-18. The user returned the reframe blind labels. Both clips were
`LIKE`, but neither was heard as DJ work or as a different performance state;
no preference. The private mapping is now unsealed: `REFRAME_BLIND_1` was the
rhythmic-reframe performance and `REFRAME_BLIND_2` untouched control. The
performance was called too subtle, control ordinary playback. The gate
**FAILED**. Do not create another source-only gesture/variant, promote this
reframe, modify frozen F/C3/B8/D2, or start Pilot 5.

The requested read-only audit traced legacy/typed-recipe DSP, the frozen
reference-template renderer, experimental scripts, cached stems, and the six
human-LIKED DJREF finished-audio timelines. Private outputs under
`/tmp/djenius_reference_dj_transition/renderer_capability_audit/` include
all ten requested JSON files plus a read-only measurement script/result.
Public-safe report: `docs/v2/RENDERER_DJ_CAPABILITY_AUDIT.md`.
The reframe's repeated same-source drum phrase had `.9306` correlation with
the natural drum envelope; the source vocal continued untouched, bass and
other retained `.30/.25`, and the held state was only about `2.1–2.6 dB`
quieter in two-second blocks despite a loop layer `2.23 dB` below the
performed mix. Waveform difference therefore did not create perceptually
distinct ownership. DJREF finished masters show more consequential
full/sparse/pulsed/layered states, but exact DJ controls are unverified
without aligned originals.

The renderer can already make convincing fixed two-deck stem/loop/tail
handoffs in F/C3/B8/D2. The demonstrated limitation is **not** an inability
to subtract a stem: it is the absence of a reusable independent foreground
rhythm/layer ownership executor outside bespoke templates, compounded in
the private experiment by replaying almost the same rhythm. The top future
primitive recommendation is a beat-addressed distinct rhythm-replacement
lane with explicit source-drum/bass clearance and independent timing,
gain/filter/release. This is a recommendation only, not an implementation
authorization. Synthetic deterministic DSP/ownership proof should precede
any separately authorized song-to-song human A/B. No new audio or production
change occurred during this audit; full application regression is not
indicated. Private JSON syntax, the original reframe WAV hashes, and all
four manual plus four automated accepted-reference hashes were reverified;
tracked changes are only this handoff and the public-safe report. **Stop for
user review.**

## SOURCE-ONLY RHYTHMIC REFRAME — HISTORICAL PRE-VERDICT CHECKPOINT

2026-09-17. The user returned the stop/restart blind labels: neither file
was perceived as DJ work or an intentional action, both rated OK, no
preference. The mapping has been unsealed and recorded privately in
`/tmp/djenius_reference_dj_transition/foreground_reset_gesture/RESET_HUMAN_VERDICT.json`:
`RESET_BLIND_1` was untouched control and `RESET_BLIND_2` was the
0.975 s stop/restart. This is a human FAIL despite technically foreground
silence; do not integrate or vary its duration.

The newly authorized task was exactly one private source-only multi-stage
rhythmic-reframe proof. No target, transition, production template change,
new archetype, or Pilot 5. The chosen normal-library 16-bar chorus window
has a stable native two-bar full-mix RMS span of only 0.262 dB, prominent
vocals and drums, strong beatgrid confidence .981, and stems whose summed
reconstruction is 25.3 dB below the source in error. Private outputs under
`/tmp/djenius_reference_dj_transition/rhythmic_reframe_proof/` are
`REFRAME_CONTROL.wav`, `REFRAME_PERFORMANCE.wav`, and exactly two blind
copies `REFRAME_BLIND_1.wav`/`REFRAME_BLIND_2.wav`. Their deterministic
assignment was sealed in `REFRAME_BLIND_MANIFEST.json` until the human
verdict, now disclosed above. `REFRAME_RESPONSE_TEMPLATE.txt` contains the
listening questions; `REFRAME_VALIDATION.json` and
`REFRAME_STAGE_ANALYSIS.json` contain private cue/level evidence.

The 30.720 s source-only choreography is: four bars untouched; two bars
bringing forward one previously heard four-bar source-drum framework;
two bars reducing bass/harmony; four bars of sustained vocal-plus-foreground
drum state; then full original song returns exactly on a downbeat for four
bars. The same source interval and fixed mastering transfer are used for
both conditions. No impact, echo, slowdown, target, extra loop, or FX chain.
The performed rhythmic framework is 2.23 dB below the transformed mix,
not a background -30 dB decoration. The altered state lasts 7.663 s and
changes mid-band energy by -3.03 dB. Control and performance are
sample-identical before preparation and after payoff. Both are finite,
unclipped stereo 44.1 kHz PCM24; control/performance integrated loudness
is -14.000/-14.774 LUFS under the same fixed gain. The payoff seam's
adjacent-sample delta .1697 is below global p99.9 .2203. The private
verify-only pass re-rendered all four WAV payloads byte-for-byte,
re-decoded them, and verified sealed blind hashes without printing the
assignment. Human listening, not these signal checks, decides whether
the performance is DJ-like. No application regression was run because
production code was not changed. This historical checkpoint is superseded by
the failed human verdict above.

## SOURCE-ONLY FOREGROUND STOP/RESTART PROOF — HISTORICAL PRE-VERDICT CHECKPOINT

2026-09-17. The user explicitly authorized one private source-only blind
control versus phrase-boundary stop/restart gesture, with an optional single
tail version only if useful. Production F/C3/B8/D2, renderer, context gates,
Pilot 5, and all accepted references remain frozen. No target song or
song-to-song transition is permitted. Branch
`v2-professional-autonomous-dj`; local/fetched origin HEAD matched
`5c88ca6196d14587c22c2484c316c10a37f38944` at session start; only
pre-existing untracked `.claude/` was present. Selected one anonymous
normal-library passage: the last two beats of an instrumental bar have
about -15.8 dBFS source energy but negligible vocal energy, followed by
a vocal-led downbeat. An approximately 31.46 s downbeat-aligned excerpt
allows seven bars of lead-in and eight bars of continuation. The output is
under `/tmp/djenius_reference_dj_transition/foreground_reset_gesture/`:
`RESET_CONTROL.wav`, `RESET_GESTURE.wav`, and two byte-identical blind
copies `RESET_BLIND_1.wav`/`RESET_BLIND_2.wav`. The assignment was sealed
privately in `RESET_BLIND_MANIFEST.json` until the human verdict, now
received and disclosed above. `RESET_RESPONSE_TEMPLATE.txt` provides the requested
listening questions. The optional tail version was deliberately omitted
to isolate the clean stop/restart gesture.

Both files use the same exact 31.463 s source interval, sample clock,
fixed mastering gain/soft-clip transfer, and post-restart playback. The
gesture mutes 0.975 s from beat 3 of an instrumental bar and restarts on
the next analyzed downbeat. Original audio in that interval was active
at -15.78 dBFS; vocal-stem level was -52.26 dBFS, so the stopped material
is not an active vocal phrase and the original song did not contain a
native stop. Digital silence during the intervention is a foreground
change, not another -30 dB layer. The stop uses a 25 ms click guard and
restart uses a 12 ms click guard. Adjacent-sample deltas at stop/restart
are .01475/.00363 versus global p99.9 .20948. Control and gesture are
-14.000/-14.026 LUFS under the same mastering treatment, both peak .8442
and neither clips. Stereo 44.1 kHz PCM24 files are 31.463 s each.
The private builder's verify-only run regenerated both masters and both
blind copies byte-for-byte, re-decoded the PCM, checked the exact silent
gap, absence of clipping, and sealed blind hash/role consistency without
printing the mapping. Validation evidence is private in
`RESET_GESTURE_VALIDATION.json`. No production code, reference WAV, model,
template, renderer, or context gate changed; no target audio, FX tail,
Pilot 5, or fifth archetype. No full application regression is needed
for this private render. This historical checkpoint is superseded by the
failed human listening result above.

## PRIVATE RICHER-F BLIND FAILURE — DIAGNOSED; PRODUCTION FROZEN

2026-09-17. The user returned the blind result: both excerpts sounded like
beginner song joins, neither sounded like experienced DJ work, and there was
no meaningful preference. The sealed assignment is now revealed privately:
`RICH_F_BLIND_1` was current F and `RICH_F_BLIND_2` was the richer private
experiment. Six private evidence reports are in
`/tmp/djenius_reference_dj_transition/rich_f_failure_analysis/`.

The richer render was technically different, but only from 12.03 to 18.865 s
of a 37.799 s excerpt. The added repeated drum bar was 33-37 dB below the
unchanged full source; the first target-grid pulse was roughly -42.4 dBFS
before mastering. Late source low-end reduction was measurable (2.9 dB in
14-16 s), yet the target pickup/landing and all target material after 18.9 s
were identical. B had no foreground vocal/hook repeat, consequential
stop/restart, tempo move, or independent musical layer. Its 0.663 s
post-landing tail differed from A by roughly 29 dB below the mix. The
human's near-indistinguishable verdict is consistent with additions being
background decoration, not a new perceptual musical state.

The tested adjacency was `CTX2_10`, previously context-only `BRIDGEABLE`,
with an 18.21% tempo difference and only a 2.159 s target pickup. This
challenging pair/cue may contribute to both versions sounding weak, but this
test does **not** prove the ordered pair globally unsuitable. The strongest
liked real-DJ references show sustained foreground full-to-sparse-to-full
resets or audible new rhythmic/musical layers; the private F experiment did
not reproduce their perceptual magnitude or duration. The smallest *future*
test proposed is one isolated source-only, phrase-boundary stop/restart
comparison to establish whether that single foreground gesture is heard as
intentional DJ work before another target handoff. **Do not render that test
without separate authorization.**

No production code, frozen F/C3/B8/D2 choreography, renderer, context gates,
accepted reference WAV, or audio artifact was changed. No Pilot 5 or fifth
archetype. This is a diagnostic-only checkpoint; no application regression
is warranted. Stop for human review.

## PRIVATE RICHER-F CONTROLLED A/B — HISTORICAL PRE-VERDICT CHECKPOINT

2026-09-17. User authorized one private same-pair F-family A/B test, with
production F, eligibility, renderer, context gates, and Pilot 5 frozen.
Branch `v2-professional-autonomous-dj`; local/fetched origin HEAD matched
`dffa137bacf137563089a0f78e009b001893f62d` at session start; only
pre-existing untracked `.claude/` was present and remains untouched. The
selected expanded-library adjacency is anonymous `CTX2_10`: human-labelled
`BRIDGEABLE`, current selector chooses and accepts F, and the pair has a
material tempo/feel contrast with a valid source motif and sparse target
pickup. Private track identities, exact cues, and supporting evidence are in
`/tmp/djenius_reference_dj_transition/rich_f_ab_experiment/RICH_F_CHOREOGRAPHY_COMPARISON.json`.

Private outputs at that path are exactly `RICH_F_A_CURRENT.wav` (the exact
frozen production F render), `RICH_F_B_RICH.wav` (one experimental richer
F-family reframe), and two byte-identical blind copies named
`RICH_F_BLIND_1.wav`/`RICH_F_BLIND_2.wav`. The deterministic assignment is
sealed in `RICH_F_BLIND_MANIFEST.json` until the user's blind verdict, now
received and disclosed above. The private builder script is
`build_rich_f_ab.py`; it refuses to overwrite an existing WAV. B retains
the first two dry source bars, repeats one complete source-drum bar quietly
while source bass/harmony clears, carries source-derived upper rhythmic pulses
over the same natural
target pickup, and darkens a bounded vocal-delay schedule through landing.
No forced tempo ramp, fifth archetype, fromDJ waveform, or production code
change was used.

Both files are 37.799184 s, 44.1 kHz stereo PCM24 with identical source and
target cues, transition duration, landing sample, target input stream/trim,
and mastering gain/soft-clip/peak-cap transfer. Integrated loudness differs
only `0.0474 LU`; after B's `0.6634 s` postlanding source tail the final
target is sample-identical within `5.96e-8` before PCM quantization. Both
are finite and unclipped; all four WAVs have identical frame count, and the
blind copies match their sealed masters byte-for-byte. A is verified against
the current production render. The frozen manual `REFERENCE_F.wav` hash
remains unchanged. No application regression was run because production
code did not change. This historical checkpoint is superseded by the
post-verdict analysis above. Do not revise either file, change production F,
or start Pilot 5.

## REAL-DJ HUMAN LABELS AND DEEP ANALYSIS — COMPLETE

2026-09-17. Branch `v2-professional-autonomous-dj`; local and fetched origin
HEAD both `797673d8dca7dfafc8b5909234142c2448718ba4`. Only pre-existing
untracked `.claude/` was present and remains untouched. The eight human
DJREF action/preference labels and exact supplied descriptions were persisted
privately in
`/tmp/djenius_reference_dj_transition/dj_reference_deep_analysis/HUMAN_DJ_REFERENCE_LABELS.json`
before detailed waveform analysis. All eight are `DJ_ACTION`; six are `LIKE`,
one `DISLIKE`, one `NEUTRAL`. The exact 40-second unchanged clips were measured
at two-second resolution for level, low/high spectral balance, percussive
fraction, spectral changes, repeat likeness, and unverified local pulse.
Private requested deliverables are under
`/tmp/djenius_reference_dj_transition/dj_reference_deep_analysis/`:
ten named JSONs plus `PRIVATE_WAVEFORM_MEASUREMENTS.json` and the private
measurement script. Public-safe report:
[`DJ_REFERENCE_DEEP_ANALYSIS.md`](DJ_REFERENCE_DEEP_ANALYSIS.md).

The strongest observable sequence is `DJREF_03`: very close 2-second repeats
for about 12 seconds, a sharp pause/reduction, then fuller return. The
listener says this treatment makes sad/slow material usable in a remix.
`DJREF_06` similarly uses full -> sparse pulsing -> full; the human hears
slowdown, but a true tempo ramp is not independently established. `DJREF_04`
is human-heard as multi-layered; `DJREF_05` as music plus drums. No independent
original/stem alignment proves source identities or exact mixer controls.
Liked references generally evolve through consequential musical states;
disliked `DJREF_07` has a brief effect/return and a comparatively steady
remaining bed. Neutral `DJREF_08` shows that stage count alone is insufficient.
No fifth archetype is justified: the recurrent reset core is F-like, while
the distinctive multi-layer/drum/tempo variants lack independent repeated
confirmation. Best next experiment is a *future* private same-pair human A/B
test of frozen F against one manually specified richer reset on a
contextually difficult but plausibly transformable adjacency. No such
variant was implemented or rendered here. No extra follow-up listening pack
is required yet.

All eleven private JSONs parse; the eight IDs and six/one/one labels align
across labels, timelines, and measurements; `git diff --check` passes.
No production code or audio was changed, so no application regression was
run. Only public-safe report/handoff edits are intended for Git; pre-existing
`.claude/` remains untouched. Production gates, four archetypes, renderer,
and Pilot 5 remain frozen. Stop for human direction after the analysis.
The validated public-safe checkpoint was committed and pushed as `c7b8781`
(`Document human-labeled DJ reference choreography study`).

## CTX2 LABEL INGESTION + REAL-DJ SHADOW MINING — COMPLETE

2026-09-17. User supplied sixteen blind CTX2 labels. All sixteen four-way
labels and exact reasons were persisted privately in
`/tmp/djenius_reference_dj_transition/context_label_pack_2/CTX2_HUMAN_LABELS.json`
and JSON-validated **before** opening the hidden identity/anchor mapping.
Branch `v2-professional-autonomous-dj`, local/fetched origin HEAD both
`1930a2a8338a859f6f2548731dee11420c2e850e`; worktree initially clean
apart from pre-existing untracked `.claude/`, which remains untouched.
Current task: reveal/analyze the CTX2 map, then mine the 35 private `fromDJ/`
references in shadow mode with conservative alignment/action confidence.
CTX2 private mapping has now been revealed into `CTX2_LABEL_REVEAL.json` with
the prior-label provenance retained. CTX2: 2 NATURAL, 6 BRIDGEABLE, 4
MISMATCH, 4 UNCERTAIN. Hidden anchors: one agrees, two inconclusive, one
conflicts with its previous positive judgment under this context-only format.
Two production-usable cases are now context-only MISMATCH, including that
conflicting anchor; one rejected case is BRIDGEABLE, but cue/performance
feasibility remains unproven. No gates were changed.

Reusable shadow-only `demo_alignment.py` and `demo_mining.py` are added in
`djenius/research/`. Matching across 158 ordinary normal-library songs and
35 private references found **zero high-confidence original-song alignments**.
One 24-second harmonic/timbre feature resemblance failed direct waveform
corroboration and remains explicitly unconfirmed. Two separately excluded
long-form overlapping-mix controls *did* align, one near sample-identically;
the pipeline can recognize straightforward shared audio but current original
coverage is sparse. Of 35 references, 25 are provisional long-form mix/set
candidates and 10 remain structurally unknown; no standalone edit/mashup is
confirmed. The 673 capped coarse nominations yielded 21 exact-like waveform
repeats in nine files; 15 precede a nominated change and six in five files
precede energy/low-end reduction. None is yet attributable to a DJ control
versus native arrangement. No recurrent choreography or missing fifth
archetype is proven. Eight diverse, private path/time regions are shortlisted
for human action/preference listening under
`/tmp/djenius_reference_dj_transition/dj_demonstration_mining/`.

Private deliverables: CTX2 label/reveal/analysis JSONs; the requested nine
reference-mining JSONs plus an original-alignment control validation and a
conclusion. Public-safe durable report:
[`DJ_DEMONSTRATION_MINING.md`](DJ_DEMONSTRATION_MINING.md); blind labels:
[`CTX2_HUMAN_CONTEXT_LABELS.json`](CTX2_HUMAN_CONTEXT_LABELS.json).
NumPy/SciPy-only shadow tooling uses private derived caches and transient
in-memory low-rate audio; no waveform/cache/audio enters Git. Alignment
regenerated byte-for-byte for 158 songs x 35 references; nine mining JSONs
regenerated byte-for-byte. Focused shadow/discovery tests **15 passed**,
touched-file Ruff clean, 12/12 frozen accepted reference WAV hashes unchanged.
No full suite is required because production code was not changed.
Production context rules, four archetypes, renderer, and Pilot 5 are frozen.
The validated shadow-analysis checkpoint was committed/pushed as `dede3b8`
(`Ingest blind CTX2 labels and add shadow DJ demonstration mining`). The
only remaining local non-commit material is the pre-existing `.claude/` tree;
all private mining/label artifacts are outside Git. Next gate: human annotation
of the eight shortlisted reference regions. Do not infer a fifth archetype,
change context gates, or render Pilot 5 from unverified signal patterns.
No audio files, private identities, or source waveforms may enter Git.

## EXPANDED-LIBRARY BLIND CONTEXT PACK 2 — COMPLETE; AWAITING LABELS

2026-09-17. The user requested exactly sixteen context-only blind auditions:
five F-heavy usable edges, four informative rare non-F usable edges, three
near-boundary rejects, and four hidden established context anchors. Track
identities, anchor roles, and selection evidence belong only in private
`/tmp/djenius_reference_dj_transition/context_label_pack_2/` manifests.
Use the prior source/silence/target format with matched loudness and no
creative DJ transition, preserve four-way labels, and do not reveal mapping
before the listener responds. Production rules, CLAP/model, F/C3/B8/D2,
renderer, and Pilot 5 remain frozen. Session start branch
`v2-professional-autonomous-dj`, local/fetched origin HEAD `ed1e2a1`; only
pre-existing untracked `.claude/` was present and remains untouched.
Selection was frozen privately before audio render. It contains
5 F-heavy usable, 4 rare non-F usable (B8/C3/D2 represented), 3
performance-usable context-boundary rejects, and 4 hidden established
set-context anchors. The twelve new ordered pairs are absent from CTX1,
use twelve distinct source tracks and twelve distinct targets, and exclude
all fourteen original calibration tracks; no reverse-direction duplicate
was selected. The private selection JSON records every archetype, selected
phase/cues, current context evidence, threshold margins, acoustic trajectory,
and selection rationale. No identity mapping enters user-facing filenames or
Git. The complete pack is at
`/tmp/djenius_reference_dj_transition/context_label_pack_2/`: exactly
`CTX2_01.wav` through `CTX2_16.wav`, the private hidden manifest/selection
JSONs, and the four-way response template. Each clip is 36.75 s: 16 s native
source before its selected launch, 0.75 s digital silence, then 20 s native
target from its selected landing cue. Stereo 44.1 kHz PCM24, a shared
−18 LUFS per-segment target, constant gain only plus 5 ms click guards;
no beatmatching, pitch change, stem, effect, or creative transition. All
sixteen independently regenerated byte-for-byte, match their manifest hashes,
and passed sample-roundtrip, cue-bounds, exact-silence, finite-value,
two-channel, duration, and no-clipping checks. Post-treatment segment LUFS
spans −18.001233 to −18.000011; maximum sample peak is 0.733693.
Twelve frozen approved reference hashes and the Pilot-4 master hash remain
unchanged. No production code changed, so the full application suite was
not rerun for this diagnostic-only checkpoint. The private generator is
`/tmp/djenius_reference_dj_transition/build_context_label_pack_2.py`;
the `--verify-only` run passed. **Awaiting expanded-library blind context
labels.** Do not reveal the private mapping, infer labels, change gates, or
render Pilot 5 before the listener responds.

## EXPANDED LIBRARY + DJ REFERENCE STUDY — COMPLETE; NO PILOT 5

2026-09-16. The twelve blind context labels were stored verbatim before the
private mapping was revealed. Pilot-4's four edges are now `UNCERTAIN`,
`BRIDGEABLE`, `BRIDGEABLE`, `UNCERTAIN` in set order; no edge is confirmed as
a human pair-level mismatch. The hidden negative anchor agrees with its prior
human reject; the hidden positive anchor retested `UNCERTAIN`, so is
inconclusive, not negative. The private mapping/reasons and Pilot-4 label
replay are in `/tmp/djenius_reference_dj_transition/expanded_library/`.
Keep `NATURAL`, `BRIDGEABLE`, `MISMATCH`, and `UNCERTAIN` distinct.

The top level of `testMusic/` contains **175** decodable, supported audio
files, including two synthetic fixtures. Of the 173 real recordings, 15 are
over ten minutes and include uncertain long-form song/mix/concert/podcast
roles. They remain in place and are explicitly deferred from this
single-song graph batch: **158** ordinary-length recordings were analyzed.
This is **not** a new production duration gate. Initial valid acoustic cache
coverage was 14/158; incremental ingestion filled the 144 missing/stale
entries. Final validation found **158/158** valid version-6 acoustic analyses,
**158/158** matching version-2 local CLAP profiles, unchanged source hashes,
and **zero** `fromDJ/` files in the analysis cache. No new model was adopted.
No exact duplicate content was found; one possible filename-version/copy
family remains unconfirmed.

The separate **35-file** `fromDJ/` corpus is excluded from ordinary recursive
candidate scanning by default; explicit shadow reference scans still work.
Focused tests and a real-root scan verified 175 normal results with no
reference leaks. A malformed MP3 duration header revealed one genuine
incremental-cache ingestion defect; compressed-file semantic duration now
prefers ffprobe, with regression coverage. No transition template, renderer,
choreography, context threshold, or set planner gate changed.

The unchanged production decision stack evaluated **24,806** directed pairs
without audio rendering. **2,097** pass current rules, **2,094** remain after
explicit human-negative ordered-pair vetoes (8.44% density). The previous
14-track-only graph had 30/182 realistic edges. The expanded graph has a
130-track weak component, 28 isolates, a 56-track largest strong component,
and over 1.87 million five-track static paths observed before a count cap.
A separate stateful, plan-only replay found a valid five-track path in ten
candidate evaluations; it is not Pilot 5 or human-approved audio. F covers
1,968 of 2,094 usable edges, so connectivity is strongly F-dependent.
Crucially, two of the three blind `MISMATCH` edges would pass current context rules
without their explicit human vetoes. More library choice resolves the old
graph scarcity but does **not** prove set-level musical judgment.

The shadow DJ-reference inventory classified the 35 long-form files only
provisionally. A deterministic coarse acoustic scan nominated **673**
structured-change regions. Those are **not confirmed DJ handoffs or edits**;
the behavior/coverage catalog therefore claims no recurrent missing fifth
archetype. The reusable shadow-only region tool requires an explicit
`fromDJ/` root and private output; it cannot enter autonomous planning.
Detailed private artifacts are in
`/tmp/djenius_reference_dj_transition/dj_reference_study/`. Public-safe
reports are [EXPANDED_LIBRARY_AUDIT.md](EXPANDED_LIBRARY_AUDIT.md) and
[DJ_REFERENCE_STUDY.md](DJ_REFERENCE_STUDY.md).

Next best experiment: blind context-only listening on a small, stratified
selection of **new expanded-graph edges**, including F-heavy accepted edges,
rare non-F edges, and rejected near-boundary controls, before any Pilot 5.
Do not tune production gates from this audit alone. No new WAV was rendered;
12 frozen accepted reference hashes and the Pilot-4 master hash remain
unchanged. Focused tests pass and complete regression passes **1173/1173**
(two pre-existing Click/Typer deprecation warnings). Session started at
local/fetched remote HEAD `478869a` on `v2-professional-autonomous-dj`;
only pre-existing untracked `.claude/` was present and remains untouched.

## BLIND HUMAN SET-CONTEXT LABEL PACK — COMPLETE; LABELS RECEIVED

2026-09-16. Exactly twelve context-only, directed-pair blind auditions have
been rendered under `/tmp/djenius_reference_dj_transition/context_label_pack/`:
four Pilot-4 adjacencies, six previously unlabelled informative pairs, and two
hidden human-labelled anchors. The private manifest/selection report retain
the mapping and provenance; do **not** reveal either to the listener before
all twelve labels return. Only `CTX_01.wav` through `CTX_12.wav` and
`CONTEXT_LABEL_RESPONSE_TEMPLATE.txt` are user-facing. The six new pairs cover
close context, boundary cases, bridgeable contrast, a performance-feasible
context reject, whole-track/cue disagreement, and reverse direction. No
F/C3/B8/D2 choreography or creative processing was used.

Each WAV is 36.75 seconds: 16.0 s native source before the evaluated launch,
0.75 s exact digital silence, 20.0 s native target from the evaluated landing
cue. Stereo 44.1 kHz PCM24; constant gain only to a shared -18 LUFS per
segment plus 5 ms click guards. Independent validation confirmed exact file
count, twelve distinct directed pairs, cue bounds, 20 s target establishment,
silence, per-segment LUFS range `-18.0008` to `-18.0001`, finite samples,
maximum absolute sample peak `.545548`, no clipping, file hashes, and existing
Pilot-4 transition references on the four appropriate manifest rows. A fresh
process rebuilt all twelve WAVs byte-for-byte without overwriting them. The
Pilot-4 master SHA-256 remained unchanged
(`15e6a5746b9db3c0c7ba1c0291d5f794f343acde89da82c51641a9f9ff01307d`).
No production code/gate/model/renderer/template changed; no Pilot 5 or new
creative render. Full application regression was not run because production
code is untouched. At session start, branch `v2-professional-autonomous-dj`,
local and fetched origin HEAD both `f85e6c3`; only pre-existing untracked
`.claude/` was present and remains untouched. The listener has since supplied
all twelve labels; their verbatim ingestion and mapping are recorded in the
newer expanded-library handoff entry above.

## SHADOW MUSICAL-CONTEXT BENCHMARK — COMPLETE; NO PRODUCTION CHANGE

2026-09-16. The analysis-only benchmark is complete. Nine private JSONs and
diagnostic scripts are in
`/tmp/djenius_reference_dj_transition/context_shadow_benchmark/`; the
public-safe report is [SET_CONTEXT_SHADOW_BENCHMARK.md](SET_CONTEXT_SHADOW_BENCHMARK.md).
The dataset separates **3 unique human set-context passes**, **5 failures**,
**4 Pilot-4 pair-level uncertain cases**, and one history-only adjacency.
Source lead-in, pre-move, actual exit, target runway, landing, and two target
establishment windows were aligned to performed template anchors and bars.
Current CLAP plus acoustic trajectories showed one fragile `.003555` pass/fail
gap, but adjacent windows overlap/invert; two-track context exposes a possible
late-set pivot but is not a gate. A pinned, isolated musicnn PyTorch conversion
was benchmarked privately on the same cases (113 short patches, no project
installation, no production cache change). Its apparent first-establishment
separation disappears at later establishment; no consistent incremental value
was demonstrated. Essentia Discogs-EffNet and MERT were reviewed but not
downloaded; model/license fit is not established for production.

Conclusion **D**: current human context evidence is too small and Pilot-4
pair labels too ambiguous to justify any production change. TRACK_4 -> TRACK_5
remains the strongest combined-history suspect, **not** a human pair-level
reject; TRACK_1 -> TRACK_2 is a competing immediate-context outlier. The
Pilot-4 `RELEASE` label is unsupported as an *immediate* post-landing energy
description (`.732 -> .884 -> .901`), but an accepted `CONTEXT_BRIDGE` uses the
same target cue/rise, so a blanket rising-target veto would be wrong. Obtain
pair-specific listener labels and additional independent context examples
before changing gates or adopting a model. Pilot 4's transition engine,
production context gates, renderer, accepted WAVs, and choreography remain
frozen. No Pilot 5 or new WAV was created. Session start: branch
`v2-professional-autonomous-dj`, local/origin HEAD `c751d05` after fetch;
pre-existing untracked `.claude/` remains untouched. The Pilot-4 master SHA-256
was reverified unchanged (`15e6a5746b9db3c0c7ba1c0291d5f794f343acde89da82c51641a9f9ff01307d`);
all nine JSONs parse, `git diff --check` passed, and focused
context/semantic/joint-planner tests passed **45/45**. No production code changed,
so a full regression was not needed. The public-safe benchmark/report checkpoint
was committed and pushed on `v2-professional-autonomous-dj`; only the
pre-existing untracked `.claude/` remains outside Git.

## PILOT 4 SET-CONTEXT POSTMORTEM — COMPLETE; NEXT HUMAN/RESEARCH GATE

2026-09-16. Human listening finds Pilot 4's transitions substantially more
convincing: transition 1 smooth with successful target speed-up, transition 2
excellent in its intended subtlety, later moves good and repeated F not
objectionable. The dominant remaining failure is music selection/context:
some tracks do not feel like one musical journey. Freeze F/C3/B8/D2,
renderer, envelopes, speed-up, ownership choreography and calibrated gates.
No Pilot 5 or new audio. The forensic audit and public-safe report are in
`docs/v2/PILOT4_SET_CONTEXT_POSTMORTEM.md`; four requested private JSONs plus
an exact-cue offline CLAP diagnostic are in
`/tmp/djenius_reference_dj_transition/pilot4_context_postmortem/`.
At session start branch `v2-professional-autonomous-dj`, local/origin HEAD both
`c4b97e09161192ecb0be9210625fa286a24cc86d` after fetch; only pre-existing
untracked `.claude/` was present. The `hf-cli` skill was read for the model
inventory/research task; no model was downloaded or installed.

TRACK_4 -> TRACK_5 is the most likely set-context mismatch, **not** a confirmed
pair-specific human reject: it is Pilot 4's only previously untested ordered
edge. The planner called it NATURAL on just whole-track CLAP
and spectral anchors, while cue style/intensity, rhythm and harmony supplied
none. Its target lands in a rising build, and first two 20-second energy bands
rise `.822 -> .908`, although the whole-track mean and late peak made it pass
the RELEASE set-role gate. TRACK_2 -> TRACK_3 and TRACK_3 -> TRACK_4 repeat
previous human context-positive ordered pairs; TRACK_1 -> TRACK_2 is locally
excellent but not explicitly context-labelled. No exact offending edge was
named by the listener. The current cue-local CLAP feature is prompt scores
from four representative windows, not raw cue embeddings; the final target
window is 19 seconds before the actual build cue. An offline probe with the
already-cached CLAP model showed raw exact-cue cosine also cannot separate
known context passes/failures (approved `.474`, rejected `.862`). Semantic mood,
meter and instrumentation remain uncertain/unavailable. The short-history
state has no context-region memory or subthreshold-drift accounting.

The next scoped step is **not** a tuned threshold: benchmark a licensed
music-specific representation on actual cue and target-establishment windows
against the existing human labels, while inspecting a two-track context story
and phase-vs-post-landing trajectory in shadow mode. Do not promote a hard
gate or start Pilot 5 until this evidence is convincing. Frozen transition
engine and all accepted audio remain unchanged; Pilot 4 WAV hash verified
`15e6a5746b9db3c0c7ba1c0291d5f794f343acde89da82c51641a9f9ff01307d`.
Focused context/planner/semantic tests: **45 passed**. No production code
changed, so no full regression was needed.

## JOINT SET PILOT 4 — COMPLETE; HUMAN LISTENING GATE

2026-09-16. User authorized exactly one five-track/four-transition continuous
set from the frozen reference-calibrated checkpoint `f7a1d80`. Branch
`v2-professional-autonomous-dj`, local and origin HEAD verified equal after
fetch. The only pre-existing untracked work is `.claude/`, which must remain
untouched. Use realistic history: exclude genuine human-negative ordered
pairs, but permit prior neutral and positive edges. Do not change calibrated
selector/context gates, templates, choreography, renderer, or library; do not
start Pilot 5. Plan autonomously with existing joint production planner,
render only the complete valid path, create the requested plan/decision/context/
calibration traces and four listening excerpts, verify reference hashes,
focused and full regression, then commit/push and stop for human listening.

Planning milestone: four existing role-trajectory hypotheses were evaluated
with the production joint planner and only the ten genuine pair-level human
negatives excluded. All returned complete five-track paths. The disclosed
quality-first cross-trajectory ranking selected anonymous track indexes
`4 -> 2 -> 7 -> 13 -> 9`, archetypes `B8 -> D2 -> F -> F`, and
`OPEN -> HOLD -> BUILD -> PEAK -> RELEASE`; the measured mean energies are
`.745 -> .750 -> .747 -> .768 -> .698`. No track, archetype, or cue was
hand-selected. The selected plan/cues and production-file/reference hashes
are frozen in private
`/tmp/djenius_reference_dj_transition/joint_set_pilot_4/PILOT4_FROZEN_PLAN_LOCK.json`.
The plan was locked before audio rendering; it must not be replanned to improve
the outcome after hearing/rendering it.

Render milestone: that locked plan reproduced deterministically and rendered
as one continuous **523.551383 s** (8:43.55) stereo 44.1 kHz PCM24 set at
`/tmp/djenius_reference_dj_transition/joint_set_pilot_4/JOINT_SET_PILOT_4.wav`.
Sample peak `.95`, clipping fraction `0`; the four source-derived excerpts are
28.139683, 33.131973, 21.661315 and 23.658231 seconds. All four selected
edges clear calibrated local performance and set-flow/context gates; the first
three ordered edges have prior positive human evidence, while the last edge
is new. B8/D2 target clocks are shared multichannel maps; F target streams
are adjacent natural masters. The B8 source-loop tail remains continuous at
landing and ends 0.02 s before target vocal onset. Twelve accepted manual/
AUTO/generalization reference hashes plus Pilot 2 T1 and both controlled
context WAV hashes were verified unchanged before and after rendering.
Requested plan, decision, context and calibration traces are present. All
four excerpts were verified sample-exact against the continuous master; all
selected establishment/context/performance gates passed. Focused selector,
context, planner and structural tests: **135 passed**. Complete regression:
**1167 passed, two pre-existing Typer/Click deprecation warnings**. No
production code, frozen gate, or approved reference changed. User must now
listen to the uninterrupted set before excerpts; no Pilot 5 or further tuning
is authorized. Technical validation is not a human musical-quality claim.

Private hashes: `JOINT_SET_PILOT_4.wav`
`15e6a5746b9db3c0c7ba1c0291d5f794f343acde89da82c51641a9f9ff01307d`;
`TRANSITION_01.wav`
`3fe917a81bc7111beb3ab205d26175cab043ef6e15cdbf16c42b79c8f4869243`;
`TRANSITION_02.wav`
`d2646595e7508b38609b313f837a3f65f378f7cf658d55629e8f49d283e33a3c`;
`TRANSITION_03.wav`
`53849ad3b27a347b66452fa78277ad859df3c14c006727de9669d637990c0905`;
`TRANSITION_04.wav`
`6141e698cceb17cfd9dfcd04b813150196f1613f859695f22c1e63596bebcd4c`.

## REFERENCE CALIBRATION REPAIR — COMPLETE; STOP

2026-09-16. The complete private audit is in
`/tmp/djenius_reference_dj_transition/reference_calibration/` (six requested
JSONs); the public-safe summary and caveats are in
[REFERENCE_CALIBRATION_AUDIT.md](REFERENCE_CALIBRATION_AUDIT.md). This task
fixed selector-only acceptance contradictions in F, B8 and C3. Frozen
templates, renderer, context thresholds, historical labels and approved WAVs
were not changed. No new audio, Pilot 4, fifth archetype, or music acquisition.

At the exact recorded cues, all **19/19** human-approved local performances
now clear `USABLE_FOR_PERFORMANCE`; **9/9** recorded local failures still fail.
All **3/3** accepted context controls pass and **5/5** context failures fail
at their recorded phase under cue-local context replay. Four blind abstentions
remain unlabelled for listening. The private table records every named gate,
measured values, thresholds and numeric component margins. Six previously
false-rejected approved instances were repaired without track/cue whitelists:
F's bounded phrase-ending unit and quiet target runway; B8's locally stable
staged groove/bass replacement despite whole-track groove distance; C3's
audible stem ownership despite overlapping *raw* vocal regions. Generalized
synthetic tests protect all three patterns and nearby negative controls.

The 14-track directed graph changed from **9 to 31 / 182** statically usable
edges with no history restriction, and from **8 to 30 / 182** under realistic
human-negative exclusions. The realistic graph now has 98 four-track and 121
five-track simple static paths; the production joint planner independently
found a complete five-track **offline plan only**. This is outcome A:
calibration repair materially restored connectivity. It is not human approval
of the new edges or a reason to render another set without authorization.
F still covers 27 of 31 usable edges; the graph is sparse, so future listening
and broader validation matter, but current evidence does not establish a
missing fifth behavior or justify a numeric library-expansion target.

Focused selector/context/joint-planner/structural tests: **135 passed**. Full
regression: **1167 passed, 2 upstream Typer/Click deprecation warnings**.
The pre-existing untracked `.claude/` remains untouched. Stop for the next
human instruction; do not begin Pilot 4, acquire tracks, or change floors.

## TRANSITION GRAPH CONNECTIVITY AUDIT — COMPLETE; STOP

2026-09-16. Planning-only audit of all fourteen private tracks and **182**
directed non-self adjacencies is complete. No audio was rendered, and no
production thresholds, template, choreography, renderer, library, or Set
Director behavior changed. Detailed private artifacts are in
`/tmp/djenius_reference_dj_transition/transition_graph_audit/`; the durable
anonymous findings and caveats are in [TRANSITION_GRAPH_AUDIT.md](TRANSITION_GRAPH_AUDIT.md).

The production decision stack marks 23 pairs mechanically transitionable and
only nine statically usable in some declared set phase. Exact Pilot 3 history
exclusions leave six edges and no path beyond two tracks. Excluding only ten
genuine pair-level human negatives yields eight edges, with a three-track
longest static path; removing all history yields nine edges and still no
four- or five-track path. The offline production joint planner under the
realistic policy also reaches at most three tracks across all four Pilot 3
trajectories. There is **no valid five-track plan** and no new WAV.

Pilot 3 did not blanket-exclude all prior tests: its thirteen exclusions
comprised ten pair-level human negatives, one known-good calibration edge,
one D2-template-only rejection, and one F-cue-only rejection. Two musically
usable edges return under realistic history; novelty contributed, but cannot
alone explain the dead-end. Calibration exposes actual false negatives: the
current performance floor rejects approved F and B8 performances at their
approved cues; C3's current cue search moves the accepted target landing
12.93 s later before rejecting it. All three known accepted set-context
controls still pass. The present evidence supports **Conclusion E: combined
novelty starvation, a disconnected small pool under current rules, and
demonstrably over-conservative reference acceptance**. A recurring missing
fifth-archetype capability is **not** established.

Focused reference-template, musical-role, joint-planner, and cue-local-context
tests: **72 passed**. Because this audit made no production code change, the
full regression suite was not rerun. Keep all quality gates unchanged until
the approved-reference discrepancies are addressed on explicit evidence.
Do not start Pilot 4, add tracks/families, or render another set without a new
human gate.

## JOINT SET PILOT 3 — PLANNING DEAD END; HUMAN GATE PENDING

2026-09-15. Human listening passed `CONTEXT_NATURAL.wav` and
`CONTEXT_BRIDGE.wav` as acceptable and confirmed `CONTEXT_REJECT` was the
correct abstention. The context/bridgeability gate is closed. The authorized
task is one continuous constrained-planner Pilot 3: target five tracks/four
transitions and roughly 6–9 minutes, while retaining only frozen F/C3/B8/D2,
all performance/context/cue hard gates, all known human-negative ordered-pair
evidence, and the proven continuous renderer invariants. No legacy Set
Director, generic Candidate Composer, Audition Lab winner policy, new
archetype, template/renderer redesign, UI, personalization, or Pilot 4 is
authorized.

Delivered 2026-09-16. The joint planner now evaluates cue-local musical
context for every technically eligible and `USABLE_FOR_PERFORMANCE` frozen
archetype, rather than only the reference selector's first mechanical winner.
It may reselect an already-proven archetype when that is the one that clears
the independent context gate. No template, selector acceptance contract, DSP,
or renderer behavior changed.

The bounded fourteen-track library could not supply a five-track path after
hard-excluding all human-negative ordered pairs and the exact Pilot 2
transition-1 calibration adjacency. Four interpretable trajectories were
searched. Every one terminated after two tracks. The planner therefore used
the authorized longest-valid fallback: anonymous library indexes `4 -> 9`,
one frozen F transition, classified `NATURAL_CONTINUATION`. It did **not**
weaken a gate, reuse the frozen Pilot 2 adjacency, or force a third track.
This is a conservative planning success but **not** a successful five-track
Pilot 3 or proof of a complete set journey.

Private output is in
`/tmp/djenius_reference_dj_transition/joint_set_pilot_3/`:

- `JOINT_SET_PILOT_3.wav` — 122.783673 s, SHA-256
  `ec23dfe62ddce72562f50e666683138bde65dff154814f7f352850ea991d12c2`;
- `TRANSITION_01.wav` — 21.800635 s, SHA-256
  `7a9fbb9424d6a3438b29a9d17125e612e243a37ab6a66765c71fbb991012e251`;
- `JOINT_SET_PLAN.json`, `JOINT_SET_DECISIONS.json`, and
  `SET_CONTEXT_TRACE.json` contain the requested plan, every selected/rejected
  candidate, archetype/context/cue evidence, four trajectory attempts, and the
  terminal replanning dead end. No `TRANSITION_02..04.wav` exists because no
  additional adjacency passed every hard gate.

The set and excerpt are stereo 44.1 kHz PCM24, finite, and unclipped; the
continuous renderer and frozen target/tail invariants remain active. Focused
role/template/joint coverage: **61 passed**. Complete regression: **1164
passed in 87.93s**, with the same two Typer/Click dependency warnings. Touched
files pass Ruff and `git diff --check`; repository-wide Ruff still reports the
pre-existing legacy baseline and was not broadened into this task.

**STOP/GATE:** human listening may review the two-track fallback and its one
excerpt, but it cannot establish the requested five-track success criterion.
Do not create Pilot 4, lower any floor, reinstate a rejected adjacency, change
frozen choreography/renderer behavior, or reconnect the legacy Set Director,
Candidate Composer, or Audition Lab.

## MUSICAL CONTEXT / BRIDGEABILITY GATE — COMPLETE; HUMAN PASSED

2026-09-15. Pilot 2 transition 1 remains frozen positive evidence: D2 connects
an anonymous close-tempo pair as `NATURAL_CONTINUATION`; its WAV and decision
hashes were reverified unchanged. Transitions 2 and 3 are now both
`UNJUSTIFIED_DISCONTINUITY`, even though their F performances remain locally
feasible. The first has a cue-local style-distribution distance beyond the
unlabelled pool's 90th-percentile band plus a simultaneous style/intensity
shift; the second has style and intensity distances both beyond their
upper-quartile bands. The frozen F move is not a large enough explanation for
either contextual-world change, so both next tracks should have been rejected.

This resolves an apparent evidence conflict: `GEN_F_02_FIX` and Pilot 2
transition 2 use the same private pair and cues. The earlier PASS remains valid
for F's local choreography/source placement, while the newer whole-set verdict
shows that it is not a positive set-context adjacency. Performance feasibility
and musical bridgeability are independent labels.

No new model or dependency was added. Existing analysis already caches a local
CLAP track embedding and four representative-window relative semantic
distributions. Whole-track embedding alone did not separate the controls; the
smallest sufficient change compares the cached window distributions nearest
the actual source release and target landing. Values are interpreted only as
pool-relative musical-territory distances—not mood, genre, or lyrical facts.
All bands come from unlabelled pool/window quantiles, never human-label fitting.

`musical_role.py` now reports exactly `NATURAL_CONTINUATION`,
`INTENTIONAL_BRIDGEABLE_CONTRAST`, or `UNJUSTIFIED_DISCONTINUITY`. Intentional
contrast requires phase direction, remaining contrast budget, usable frozen F
reset/release choreography, cue-context evidence, at least two explicit
continuity anchors, and no unresolved cue-local style/intensity split. C3/B8/D2
remain natural-continuation tools under their frozen contracts. Technical
transitionability cannot override an unjustified discontinuity. A cue-search
defect was also fixed: performance acceptance is now evaluated for every
technically eligible cue before ranking, so one weak first cue cannot hide a
nearby cue that already satisfies the unchanged performance contract.

The controlled private panel is in
`/tmp/djenius_reference_dj_transition/musical_context_bridgeability/`:

- `CONTEXT_NATURAL.wav` — 34.966349 s, SHA-256
  `0bcbdce2f242b7a9cde86153c7033e81fe58e8dde95a8e8e482bc416ae2959ce`;
- `CONTEXT_BRIDGE.wav` — 39.076281 s, SHA-256
  `ab5534e6d10641fe7936805779ac89c566698866a78260ea9f177ec97e74df93`;
- `CONTEXT_REJECT` — documented abstention; no WAV was rendered;
- `MUSICAL_CONTEXT_DIAGNOSIS.json` — private identities, positive/negative
  feature audit, Pilot 2 postmortem, all four template results, exact cues,
  classifications, choreography, and render provenance; SHA-256
  `90af9218abdc2209a7b9635bd4139ae74fcc325039a3aa26039d17c892c3d100`.

Both WAVs are stereo 44.1 kHz PCM24 with zero clipped samples. Focused context,
semantic, selector, template, and joint-planner regression: **82 passed in
7.46s**. Complete regression: **1159 passed in 84.26s**. Ruff passes on all
touched Python files; `git diff --check` remains required before commit. These
checks establish determinism and technical correctness, not listening quality.

**HISTORICAL GATE RESULT:** the human accepted both rendered controls and the
documented abstention, which authorized the bounded Pilot 3 now recorded
above. The prohibition on altering frozen templates/renderer or reconnecting
the legacy Set Director/Candidate Composer/Audition Lab path remains active.

## JOINT SET PILOT 2 — COMPLETE; HUMAN GATE PENDING

2026-09-15. The first pilot's set-story failure is now explicit. Its planner had
no musical-role or short-term trajectory state, recorded genre/style as
unavailable, and had no mood evidence. The existing local semantic analyzer did
not clear its reliability floor for the human-described sad/bright contrast, so
the implementation correctly preserves that as human listening evidence rather
than fabricating an audio-model claim. Existing acoustic evidence did expose the
problematic HOLD adjacency as a straight-driving to compound-or-halftime
candidate change with a large tempo/groove-role discontinuity.

`musical_role.py` now derives an interpretable energy, dance-function, rhythmic,
vocal, optional reliable mood/style, and set-role profile. The joint planner
maintains recent energy/function/rhythm/reliable-mood state, a declared phase,
and an intentional-contrast budget. `PERFORMANCE_FEASIBILITY` and
`SET_FLOW_SUITABILITY` are independent hard gates; relationships are disclosed
as `NATURAL_CONTINUATION`, `INTENTIONAL_BRIDGEABLE_CONTRAST`, or
`UNJUSTIFIED_DISCONTINUITY`, never one opaque score. The old pilot now rejects:

- transition 1 because D2 no longer clears the source-launch/groove performance
  margin;
- transition 2 as an unjustified rhythmic-role discontinuity during HOLD;
- transition 3 because the target cannot serve the requested PEAK role or energy
  direction.

Exactly one second pilot was rendered. Its anonymous energy path is `.750 ->
.747 -> .770 -> .702`, with declared roles `OPEN -> HOLD -> PEAK -> RELEASE`
and frozen archetypes `D2 -> F -> F`. All three first-pilot human-rejected
adjacencies and the exact old sequence were hard-excluded. The repeated F was
not forced for variety: it survived the performance and flow gates and expresses
the peak and release actions. No renderer or frozen template choreography was
changed.

Private deliverables are in
`/tmp/djenius_reference_dj_transition/joint_set_pilot_2/`:

- `JOINT_SET_PILOT_2.wav` — 264.977052 s, stereo 44.1 kHz PCM24, SHA-256
  `39bd32bf146c4fff2ce9f9ff002956daa253fea70a9b0bc988a9722d576a4dd4`;
- `TRANSITION_01.wav` — D2, 33.131973 s,
  `ebfc13f67e03f97002b26c3408fe7281f7ea3d9968f73ad51f29540c2523a53a`;
- `TRANSITION_02.wav` — F, 22.636553 s,
  `19ef2adde58a217c64157da1c9a0fac73ce9b7cd688edd479bf84907fa507cb6`;
- `TRANSITION_03.wav` — F, 31.018957 s,
  `13e5c4fd38b472f9b2c1257fc8a8adaf4c2e206120e0791c22ee5a02f9522e8b`;
- `JOINT_SET_PLAN.json`, `JOINT_SET_DECISIONS.json`, and
  `SET_FLOW_POSTMORTEM.json` contain complete candidate tables, reliable and
  deferred evidence, state changes, old-vs-new decisions, choreography, and
  render provenance. Their SHA-256 values are respectively
  `554c2c602d4b72264fa963bb3ac6a2e47a4251277689f98971a21c822d71f4ed`,
  `63bba81332d004dce4ad9620e688f6aaaea0ec0ba47df00f9346a69856c869cb`,
  and `97ccf745ef1d2d940cf9f9692743df7865720f214374621b03c00a346750d8ef`.

The set peak is `.95`, clipping fraction is zero, and the six exact natural /
template boundary deltas are `.010425/.073514/.076625/.080537/.056854/.050126`.
All twelve accepted reference hashes were verified unchanged. Focused tests pass
at **66**; complete regression passes at **1154 passed in 88.07s**, with only
the two existing Typer/Click dependency warnings. These facts validate the
planner contract, determinism, continuity, and technical safety—not musical
quality.

**STOP/GATE:** human-listen to the three excerpts and continuous second pilot.
Do not render a third pilot, alter F/C3/B8/D2 or the renderer, or reconnect the
legacy Set Director, Candidate Composer, Audition Lab, UI, personalization, or
new families until the user evaluates this gate. The pre-existing untracked
`.claude/` directory remains untouched. Validated implementation checkpoint:
`1313c7f` (`Add flow-aware joint set planning`); a docs-only handoff commit
follows, so resolve the current branch tip from Git.

## CONSTRAINED JOINT SET-DIRECTOR PILOT — COMPLETE; HUMAN GATE PENDING

2026-09-15. One isolated four-track/three-transition joint-planning pilot is
complete. `joint_reference_set.py` jointly evaluates next-track set flow,
`PAIR_TRANSITIONABLE`, all four frozen archetypes, cue placement,
`USABLE_FOR_PERFORMANCE`, and the middle track's minimum establishment time.
It does not import or call the legacy Set Director, Candidate Composer, or
Audition Lab. A deterministic bounded path search rejects prior listening-test
ordered pairs and never admits an attractive but untransitionable track.
Validated implementation checkpoint: `4f2629fd2a4c8ca6f963f02084641eef1ef4aeab`
(`Add constrained joint reference set pilot`), pushed with local and remote
branch tips equal before this handoff-only finalization.

The private fourteen-track library could not provide four individually unused
tracks, so individual-track reuse was unavoidable; all prior manual,
generalization, and blind-test **ordered pair edges** were excluded. The chosen
anonymous path is `SET_TRACK_01 -> SET_TRACK_02 -> SET_TRACK_03 ->
SET_TRACK_04`, using `D2 -> F -> F`. Energy is `.747 -> .745 -> .770 ->
.707`. The first two tracks have close BPM/harmonic evidence for D2; the two F
resets carry the later material tempo contrasts. Variety is only a late
tie-breaker after performance and set-flow evidence, and consecutive use is a
soft preference rather than permission to choose a weaker transition.

`joint_reference_set_renderer.py` executes each frozen template intact and
keeps every tail through its declared postlanding establishment window. The
middle track then continues from the exact target source clock into natural
playback, and later enters its outgoing frozen performance through a 40 ms
sample-aligned seam. A slow gain bridge joins independently level-matched
windows; the assembled set receives one final uniform master pass. No
transition WAVs were concatenated to make the set: the excerpts are cut from
the final continuous set render.

Private deliverables are in
`/tmp/djenius_reference_dj_transition/joint_set_pilot/`:

- `JOINT_SET_PILOT.wav` — 391.595283 s, stereo 44.1 kHz PCM24, SHA-256
  `7ac329b346a29168184ed5797e603cf25f00c3cfaea8c04d235c0463673b3a71`;
- `TRANSITION_01.wav` — D2, 35.477188 s,
  `e3862cbc43085567bdb8c238794cceb3f05a22a2d06fb306311966a854c32a4e`;
- `TRANSITION_02.wav` — F, 22.868753 s,
  `b44f440c9511b8b93e641c4525c1f7a1ae328479dc669d1bb7e97d63cb1b29ad`;
- `TRANSITION_03.wav` — F, 29.254240 s,
  `96facb35b19a30650baf81885ce1be21c225d069c0a67cfbc63fed78ec027a81`;
- `JOINT_SET_PLAN.json` and `JOINT_SET_DECISIONS.json` contain the opening
  choice, every per-step candidate table, all four template evaluations,
  cue/establishment evidence, complete choreography, render provenance, and
  all rejection reasons.

The set has sample peak `.935026`, zero clipping, and exact-boundary maximum
sample deltas `.072240/.012311/.072921/.071492/.055813/.044374` at its six
natural/template joins. All twelve accepted reference WAVs were hash-verified
unchanged before the final render. Focused joint/reference tests pass at **45**;
complete regression passes at **1147 passed in 83.79s**, with the same two
Typer/Click dependency warnings. These facts prove deterministic planning,
continuity, and safety only. Whether the three moves and the sequence sound
like a convincing DJ set remains exclusively the pending human listening gate.

STOP. Do not render a second mini-set or reconnect the unrestricted Set
Director, Candidate Composer, Audition Lab, UI, personalization, generic
families, or new choreography before the user evaluates this pilot.

## AUTONOMOUS SELECTION POSTMORTEM — COMPLETE

2026-09-15. The first blind autonomous-selection gate failed human listening:
`PAIR_02 = FAIL_NOT_GOOD`, `PAIR_03 = FAIL_BETTER_THAN_02`,
`PAIR_04 = NEAR_PASS_BUT_NOT_GOOD`, and
`PAIR_05 = BEST_OF_ROUND_BUT_NOT_PASS`. None is a pass. The previous
abstentions (`PAIR_01`, `PAIR_06`, `PAIR_07`, `PAIR_08`) remain evidence to
audit rather than rerender. The active task is restricted to: blind calibration
replay on the four accepted generalization pairs; selection/cue/pair-suitability
postmortem; explicit `USABLE_FOR_PERFORMANCE` and `PAIR_TRANSITIONABLE` gates;
and only demonstrably credible frozen-template counterfactuals. Renderer,
approved template choreography, accepted references, Set Director, Candidate
Composer, Audition Lab, new families, and full mixes remain untouched.

Recovery verification: branch `v2-professional-autonomous-dj`; local and
remote-tracking HEAD both `f0febb705328a9565bd688f38217a1c14b14abfc` after
fetch; the worktree was otherwise clean except the pre-existing untracked
`.claude/` directory.

Diagnosis milestone: the untouched baseline selector failed blind calibration.
It chose B8 source bar 82 instead of accepted 93 for B8_01, C3 source bar 91
instead of accepted 89 for C3_01, and abstained on accepted F_02_FIX because
its proven intro pickup was absent from target search; only B8_02_FIX was exact.
Selector-only cue corrections now rediscover all four accepted templates and
exact source/target bar anchors. A new explicit `USABLE_FOR_PERFORMANCE` gate
separates technical eligibility from permission to render, and
`PAIR_TRANSITIONABLE` separately records whether any frozen behavior clears
that floor.

Postmortem result: PAIR_02-05 each fail the revised floor at their best nearby
cues and no other frozen archetype is credible. All four are marked
`SHOULD_HAVE_ABSTAINED`; zero ALT WAVs were created. PAIR_01/06/07/08 remain
abstentions and were appropriately conservative. The private report is
`/tmp/djenius_reference_dj_transition/autonomous_selection/postmortem/POSTMORTEM_DIAGNOSIS.json`
(SHA-256 `a535baa424f00c8daba58bb4d0bfa2f8704f2a59eafea67572f850743568aa08`),
and the updated private manifest SHA-256 is
`75b861d38cd9676830e3a3cd66d76aa3c24ae3c9b6a12ed7bce80bef56e3971a`.
All 12 accepted references and all four failed-round WAVs were hash-verified
unchanged. Focused selector/template tests: **40 passed**; focused structural
regression: **136 passed**. Touched-file ruff and `git diff --check` pass.
Complete repository regression: **1142 passed in 84.58s**, with the two
existing Typer/Click deprecation warnings. No test is currently running.

**STOP/GATE:** there are no counterfactual WAVs to listen to. This is a valid
and material result: every alternative would violate its own performance floor.
The experiment resolves to Case 2 (`PAIR_SELECTION_AND_ACCEPTANCE`), not an
alternative-template win. Do not launch a second blind round and do not
reconnect Set Director. The next product step requires user direction after
reviewing this diagnosis; when autonomy eventually resumes, next-track,
template, and cue choice must be joint.

Validated implementation checkpoint: commit `cce15d2` ("Tighten reference
selector abstention gate"), pushed to
`origin/v2-professional-autonomous-dj`. This handoff finalization follows as a
docs-only commit; resolve the current tip from Git. Apart from the pre-existing
untracked `.claude/` directory, the worktree is clean.

## REFERENCE-BACKED AUTONOMOUS SELECTION GATE — READY FOR BLIND LISTENING

2026-09-15. Human listening passed both Round 2 fixes:

- `GEN_B8_02_FIX` = `PASS`; phrase-ending/instrumental-gap placement fixed
  the major source-entry problem and restored clearly audible DJ work.
- `GEN_F_02_FIX` = `PASS`; the self-contained vocal unit made the F behavior
  work substantially better.

The practical gate is musical acceptance, not endless polish. Freeze these
two files plus `GEN_B8_01`, `GEN_C3_01`, all four AUTO references, and their
four manual references. The active task is a constrained, explainable
reference-backed selector over exactly the four proven archetypes plus
mandatory `NO_SUITABLE_TEMPLATE`. Cue placement is part of selection. Evaluate
exactly eight unseen private pairs, render at most one chosen transition per
pair, preserve all candidate reasoning in a private manifest, and stop for
blind human listening. Candidate Composer, Audition Lab, Set Director, UI,
personalization, new families, and full mixes remain prohibited.

Implementation milestone: `core/reference_selector.py` now evaluates all four
approved templates, searches bounded nearby source/target downbeat windows,
retains every cue rejection, requires a named template-specific musical-story
contract, and returns either one instance or `NO_SUITABLE_TEMPLATE`. It does
not use the legacy aggregate pair fit value and has no imports from Candidate
Composer, Audition Lab, or Set Director. Source evidence includes section,
vocal completion/gaps, motif descriptors, transient/energy context; target
evidence includes cue/phrase/section cleanliness, vocal/drum/bass onset
proxies, density, and establishment; pair evidence includes tempo, groove,
harmony, energy, stems, and explicit overlap risks/deferred facts.

The eight-pair private panel was fixed before audio rendering using five
analysis-only strata and excludes every prior reference/generalization ordered
pair. Current deterministic decisions are four renders and four abstentions:

- `PAIR_01`: abstain.
- `PAIR_02`: F/reset-release; source launch shifted -28 beats.
- `PAIR_03`: B8/loop-build; source launch shifted -48 beats; target baseline.
- `PAIR_04`: B8/loop-build; source launch shifted -8 beats; target baseline.
- `PAIR_05`: C3/stem-echo; source launch shifted -36 beats; target baseline.
- `PAIR_06`, `PAIR_07`, `PAIR_08`: abstain.

No D2 render was forced: the restrained probe lacks a usable local source
window, and the other seven pairs do not satisfy D2's complete long-overlap
contract. The four rendered WAVs are finite, unclipped stereo 44.1 kHz PCM24;
the accepted listening set was hash-verified unchanged before and after both
render passes. Exact private outputs:

- `PAIR_02.wav` — F/reset-release —
  `e196d2d1904dbb3e5d178b12ccd9762fa77fc5aa5d12efcc8f5e1d82d6869f72`
- `PAIR_03.wav` — B8/loop-build —
  `746a0e472b6dfd466166fd1e795ffac5f5c45eac482b7d0d708f72c500f80c9b`
- `PAIR_04.wav` — B8/loop-build —
  `a7faf8bf62091d3f6d766511ccec6dfb782b443e8f3d8c15d90b179741513fc5`
- `PAIR_05.wav` — C3/stem-echo —
  `53d3e60cc46f98fc3b330d68f2e255ea4224db9337e6625c376d425f56c5099b`

The private manifest is
`/tmp/djenius_reference_dj_transition/autonomous_selection/AUTONOMOUS_SELECTION_MANIFEST.json`
(SHA-256 `6aff71a2cee3ebbb2e6ae109be88c2f601ed6826a97a6aa71aa7a2f82289f159`).
It contains identities, all four evaluations per pair, every rejection and
story-rule check, selected cues/shifts, choreography, provenance, and technical
checks. Focused reference-template/selector tests: **34 passed**. Complete
regression: **1136 passed in 81.99s**, with the two existing Typer/Click
deprecation warnings. Touched-file `ruff check` passes.

**STOP/GATE:** blind-listen only to `PAIR_02` through `PAIR_05`, then judge the
four rendered choices and the four abstentions. Do not proceed to Set Director,
Candidate Composer, Audition Lab, UI, personalization, new families, or full
mixes until the user passes this gate.

Validated implementation checkpoint: commit `6e3f2b8` ("Add constrained
reference transition selector"), pushed to
`origin/v2-professional-autonomous-dj`. This handoff finalization follows as a
docs-only commit; resolve the current tip from Git. Apart from the pre-existing
untracked `.claude/` directory, the worktree is clean.

## GENERALIZATION ROUND 2 — PASSED

2026-09-15. The user completed the first eight-render listening gate. Human
labels are authoritative engineering evidence, not machine-learning targets:

- `GEN_B8_01` = `PASS`; preserve unchanged as a successful new-pair reference.
- `GEN_B8_02` = `NEAR_PASS_SOURCE_ENTRY`; effect and target connection worked,
  but the source-to-effect entry was not smooth and may interrupt singing.
- `GEN_C3_01` = `PASS`; preserve unchanged as successful/near-successful.
- `GEN_C3_02` = `BORDERLINE`; diagnose against C3_01 before any rerender.
- `GEN_D2_01` = `REJECT`; derive the eligibility condition that should have
  refused this pair/template combination.
- `GEN_D2_02` = `BORDERLINE_PASS`; preserve rather than making it flashy.
- `GEN_F_01` = `REJECT_EFFECT_ENTRY`; onset was out of place and too sudden.
- `GEN_F_02` = `NEAR_PASS_EFFECT_ENTRY`; better than F_01 but has the same
  abrupt-onset defect.

Residual forensics confirms that source-entry context, rather than the fixed
target-side handoff, caused the B8_02 failure. Its old source fade began with
9.5782 seconds remaining in an active lyric unit and crossed a verse-to-outro
boundary; its loop also entered on active vocals. B8_01 instead sits in a
stable drop/repeated-hook context. The B8 fix moves the same-duration source
phrase 40 beats earlier: the fade begins on the final 0.3135 seconds of a
vocal phrase, the loop begins in instrumental space, and there is 1.4164
seconds of runway before the next vocal. A localized equal-power dry-to-loop
handoff over bars 4.00-4.22 removes the source-entry hole. Every target anchor,
component sample, gain, reveal, shared time map, tail, and establishment
parameter is unchanged; the successful B8_01/AUTO_B8 envelope is untouched.

F_01 and F_02 both released inside continuing vocal material. AUTO_F's
recognizable motif completes about 115 ms before release; old F_02 instead
released at high vocal level inside an incomplete unit. The F fix moves only
the four-bar source phrase 12 beats earlier to a downbeat gap after a
self-contained unit. Its target anchors, adjacent natural target samples,
gain, reset envelope, and choreography are unchanged.

C3_02 has no single local renderer defect. Compared with passing C3_01 it has
10.5691% versus 5.0407% stretch, groove distance 0.2286 versus 0.0575, source
arrangement density 0.8529 versus 0.3155, and a much more dominant source
vocal (-3.688 versus -10.877 dB relative to master). This compounds into a
borderline placement, so no C3 fix was fabricated. D2_01 likewise becomes an
explicit pre-render reject: global harmonic compatibility is 0.30 and shared
arrangement-density pressure is 1.7475, versus 0.70/1.4142 for borderline-pass
D2_02. No D2 render was made.

Exactly two new user-facing files are ready in
`/tmp/djenius_reference_dj_transition/generalization/`:

- `GEN_B8_02_FIX.wav` — SHA-256
  `2f8dc2e6bfd4c95b97cdcc38a1e7090504af4a4296c6968d9149b08825d3b1b6`
- `GEN_F_02_FIX.wav` — SHA-256
  `c54353a189650e6e52e35618e537b10e628cdbd1d05182379bc03ae8dc574430`

Both are finite, unclipped, stereo 44.1 kHz PCM24 and reproduced with the
same hashes after final metadata changes. `GENERALIZATION_MANIFEST.json`
contains the private detailed comparison; public-safe human labels, diagnoses,
rules, and hashes are durable in `REFERENCE_GENERALIZATION_LABELS.json`.
Focused tests: **24 passed**. Complete repository regression: **1126 passed in
82.45s**, with the two existing Typer/Click deprecation warnings. Touched-file
`ruff check` and `git diff --check` pass.

Validated implementation checkpoint: commit `3b1d882` ("Refine reference
template entry eligibility"), pushed to
`origin/v2-professional-autonomous-dj`. This handoff finalization follows as a
docs-only commit; resolve the current tip from Git. Apart from the pre-existing
untracked `.claude/` directory, the checkpoint worktree is clean.

Human result: both fixes were much better and passed the practical acceptance
threshold. B8's phrase-ending/instrumental-gap placement repaired the major
problem; F's self-contained vocal unit made the repeat behavior work far
better. Their hashes remain frozen in the active selector gate above.

## CROSS-PAIR GENERALIZATION GATE — READY FOR HUMAN LISTENING

2026-09-15. The user passed the first human reference-automation gate:
`AUTO_F` was the best and genuinely enjoyable; `AUTO_C3` made good, clearly
audible DJ work; `AUTO_B8` was acceptable and substantially beyond AutoDJ-like
behavior; `AUTO_D2` was good for its restrained role. The explicit template
layer therefore reproduces approved behavior without collapsing into generic
crossfades. The eight manual/automated references remain frozen at the hashes
below and were verified unchanged after this gate.

Validated generalization implementation checkpoint: commit
`2c6574483ed52dbc40ac19704f3f2b74d7bcef57` ("Add reference template
generalization gate"), pushed to `origin/v2-professional-autonomous-dj` with
local and remote HEAD equal immediately afterward. A docs-only handoff
finalization follows that commit; resolve the current tip from Git. The only
uncommitted worktree item after finalization is the pre-existing `.claude/`
directory, left untouched.

Exactly two new real private pairs per archetype are rendered in
`/tmp/djenius_reference_dj_transition/generalization/`. The directory contains
only the requested eight stereo 44.1 kHz PCM24 WAVs and
`GENERALIZATION_MANIFEST.json`. The manifest retains private source/target
identity, analysis-derived cues, BPM/stretch/key/energy/vocal/drum/bass/stem
evidence, instantiated choreography, adapted parameters, technical checks,
all rejected candidate pairs and reasons, and eligible-but-not-selected pairs.
Audition Lab was not invoked and none of these renders is claimed successful
before human listening.

| Render | Anonymous private pair | Selection evidence | SHA-256 |
|---|---|---|---|
| `GEN_F_01.wav` | `PRIVATE_12 -> PRIVATE_04` | 86.1 -> 117.5 BPM reset, relative 10A/10B keys, vocal hook into vocal-free pickup and +0.376 landing-energy lift | `81e2d58f6be6666089c19d3eaa847b38a89243a26d056822037f872cbef5e626` |
| `GEN_F_02.wav` | `PRIVATE_07 -> PRIVATE_12` | recognizable 123 -> 86.1 BPM hook/reset, adjacent 9A/10A keys, sparse pickup and +0.289 landing lift | `e926ca09eb9645d1f3e8a9ede0f335a2e90e17ce3942c9e2d9d4967e547f7247` |
| `GEN_C3_01.wav` | `PRIVATE_02 -> PRIVATE_03` | 5.04% tempo fit, groove distance 0.0575, capturable late vocal and active target drums | `2d019af332416fa5d62143daec7072f9f33f260b91d02e01e87db492258a55a9` |
| `GEN_C3_02.wav` | `PRIVATE_01 -> PRIVATE_03` | dense late source capture, strong target drum/drop phrase; 10.57% tempo change is retained as a caution | `0f313c8b42ac3587953fbe6ac65530f0d9e113c94a0ca2d33caa4ba7c35d7718` |
| `GEN_B8_01.wav` | `PRIVATE_03 -> PRIVATE_02` | 5.04% tempo fit, groove distance 0.0575, active backing motif, stable landing bass rise and 0.627 s vocal runway | `3871f3ae02b5fe4884b884a8218b22a7dd76de4fa668f9a8e22d105cd4809e4b` |
| `GEN_B8_02.wav` | `PRIVATE_07 -> PRIVATE_02` | compatible 9A/10B relation, active backing motif, stable drums/bass and 0.627 s vocal runway | `30949ccbed4236981f1efe331bd07aaba87f08a67d6916bf7944cb82d3f2ef58` |
| `GEN_D2_01.wav` | `PRIVATE_10 -> PRIVATE_01` | exact 136 BPM, groove distance 0.1408, close section energy and active target drums/bass; key risk is explicit | `7129d81e7009bb32652280dd8730f75c11e2bc893cc2e5bb999c6fb49db86c1e` |
| `GEN_D2_02.wav` | `PRIVATE_04 -> PRIVATE_07` | 4.47% tempo adjustment, compatible 10B/9A keys, close energy and target drum/bass support | `8b03200b8df27db82c5c6219280704bdfa5e04d959ad2dbb6170ef59112ff77d` |

The exhaustive analysis-only scan considered all 196 ordered candidates per
archetype in the 14-track private library. Counts `(selected / eligible but
not selected / rejected)` are F `2/60/134`, C3 `2/10/184`, B8 `2/3/191`, and
D2 `2/9/185`; same-track and original-reference pairs are explicit rejects.
This is feasibility/context evidence, not an automated listening score.

The new-pair run exposed one concrete renderer boundary defect: nearest-sample
rounding could place a B8 tail a few microseconds beyond its hard 20 ms
pre-vocal margin. The endpoint now rounds inward with `floor`, so quantization
can only shorten the tail. The source loop remains state-continuous and all
beatmatched targets still use a single shared multichannel time map. Focused
tests: **19 passed**. Complete repository regression: **1121 passed in
82.55s**, with the two pre-existing Typer/Click deprecation warnings. Touched
Python `ruff check` passes; the eight renders reproduced the same hashes on a
second complete run.

**STOP/GATE:** the user must listen to all eight `GEN_*` renders. Do not tune
them, add pairs/families, let Audition Lab select, integrate Candidate Composer
or Set Director, touch UI/personalization, or make full mixes. The next
question is only whether each approved choreography generalizes to these new
pairs as intentional DJ work.

## REFERENCE-BACKED AUTOMATION — SAME-PAIR RENDERS READY FOR HUMAN LISTENING
2026-09-14. The user judged B8 substantially better than the earlier B-series
and acceptable. Manual plausibility is no longer the blocking question. Do not
continue polishing B8. Freeze these four private files as the current
human-approved/accepted reference set:

Validated implementation checkpoint: commit
`5571b573ae9c8e6e17333c9a387bb0d253271517` ("Add reference-backed DJ
performance templates"), pushed to `origin/v2-professional-autonomous-dj`;
local and remote HEAD matched immediately after push. The only remaining
worktree item is the pre-existing untracked `.claude/` directory, left
untouched. A docs-only handoff finalization follows that implementation commit;
resolve the current tip from Git.

- `REFERENCE_F.wav` — strongest; SHA-256
  `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`
- `REFERENCE_C3.wav` — successful DJ-like edit; SHA-256
  `ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03`
- `B8_RESIDUAL_FIX.wav` — acceptable loop/build/handoff; SHA-256
  `47824cc9b923c708f261c7d3db82e46e2f910fec47b802111bcd26c1c5aa1205`
- `REFERENCE_D2.wav` — acceptable restrained blend; SHA-256
  `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586`

The reference-backed layer is implemented without touching autonomous
selection. `core/reference_templates.py` maps an explicitly requested
archetype plus source/target `TrackAnalysis` into deterministic analysis-
derived anchors, a complete bar-relative `PerformanceRecipe`, eligibility
evidence, and an executable choreography contract.
`audio/reference_template_renderer.py` executes only those selected templates
and permanently retains the structural fixes: target master/stems and runway/
body share one multichannel time map; source loop state crossing landing is
continuous; tail endpoints are explicit and checked.

The four private same-pair reproductions are ready:

- `automated/AUTO_F.wav` — SHA-256
  `13c3691cf81b40467d8adce0c9cf2408206199500554648ef29ae32584ab6f2b`
- `automated/AUTO_C3.wav` — SHA-256
  `0c89bb5f9024baacdb419556f2fbd8c4a1b60099b13a26a0dcc9738b16426a32`
- `automated/AUTO_B8.wav` — SHA-256
  `f6ff0d862739e8c0b71993d3fc5ba1b4eb8a73468354d59f2f525ce747c5e3b1`
- `automated/AUTO_D2.wav` — SHA-256
  `ab2dbd9156eb18b3c450495ffab8b21060841abe430e23d38f7b9340fc532634`

All are stereo 44.1 kHz PCM24. Every automated source/target cue reproduces
the corresponding frozen manual cue within 0.1 ms. F uses adjacent natural
target master; C3/B8/D2 report one shared FFmpeg multichannel target clock.
F's final echo clears 41.2 ms before landing, C3's clears 239.2 ms before,
B8's uninterrupted rhythmic/airy tail clears 20 ms before the measured target
vocal, and D2 declares no FX tail. The four frozen manual hashes were verified
unchanged after rendering.

Focused tests: **14 passed**. Complete repository regression: **1116 passed**
in 82.14 seconds, with only the two pre-existing Typer/Click dependency
deprecation warnings. Touched-file `ruff check` and `git diff --check` pass.
Machine-readable evidence is in private
`automated/REFERENCE_AUTOMATION_MANIFEST.json`; the full archetype contract is
in `REFERENCE_BACKED_ARCHETYPES.md`.

**STOP/GATE:** the user must compare manual F vs `AUTO_F`, manual C3 vs
`AUTO_C3`, manual B8 vs `AUTO_B8`, and manual D2 vs `AUTO_D2`. Numerical
similarity is not acceptance. If a reproduction is substantially worse,
change only the reference template/instantiation renderer. Do not test new
pairs, expose these templates to Candidate Composer, alter Audition Lab or Set
Director, touch UI, create new families, or render full mixes before approval.

## B8 RESIDUAL FIX — READY FOR B7-vs-B8 HUMAN LISTENING
2026-09-14. Residual-error forensics is complete. Exactly one new user-facing
render exists:

- private file: `/tmp/djenius_reference_dj_transition/B8_RESIDUAL_FIX.wav`
- SHA-256: `47824cc9b923c708f261c7d3db82e46e2f910fec47b802111bcd26c1c5aa1205`
- format: stereo 44.1 kHz PCM24, 40.0283 seconds
- transition start: 7.9877 seconds; landing: 24.0065 seconds
- focused two-bars-before/four-bars-after interval: approximately
  20.0127–31.9942 seconds
- integrated loudness: -14.134 LUFS; sample peak: 0.751554; clipped samples: 0
- deterministic rerender produced the same SHA-256

### Residual diagnosis

The B7 renderer corrections remain valid and are retained. No new hard DSP
splice, mastering reset, target gain reset, or sample-level click was found:

- The B7 shared-clock stem sum still reconstructs its target master with
  0.999662 correlation and 0.026310 RMS residual ratio.
- In the isolated target-only render, the half-bar landing change is only
  -0.354 dB full-band, -0.762 dB below 155 Hz, and +0.744 dB above 3 kHz.
- B7's landing-local maximum sample delta is only 0.531 times its global
  99.9th-percentile delta. C3 is 0.624 times; neither landing is an anomalous
  click/transient.
- B7 uses one fixed global gain and one memoryless soft clip across the whole
  file. Its only postlanding deck ramp is the already-declared target master
  gain from 0.88 to 1.0 over 0.62 bar.

The remaining defect is therefore choreography/tail-state, with two measured
parts:

1. **False bass/energy event before the real landing.** B7 previewed four bars
   of the target's low-frequency cue material. The fourth preview bar contains
   an internal pocket: its four low-band quarter-bars measured -31.310,
   -33.375, -16.221, and -15.917 dBFS. Energy therefore collapses, returns
   strongly half a bar early, and then falls again onto the nominal landing.
   C3's successful handoff uses the same cue but a stable two-bar target-low
   cadence and does not expose that four-bar pocket at this location.
2. **Wrong outgoing-FX frequency/lifetime handoff.** B7's isolated target gains
   0.744 dB above 3 kHz at landing, but the full B7 loses 5.486 dB from the
   final prelanding quarter-bar to the first postlanding quarter-bar. The
   difference is the outgoing riser: it reaches its peak at the boundary and
   has no wet release. Meanwhile the rhythmic source loop remains in the
   520–5200 Hz lead/vocal range until 1.5576 seconds after landing. The first
   annotated target vocal begins at 0.6802 performed seconds, leaving 0.8774
   seconds of unnecessary rhythmic/midrange overlap. Its onset-envelope
   correlation with the target drums is only 0.105 (best lag -29.0 ms), so the
   overlap is not reinforcing the target groove.

The target cue itself is retained. It is the same cue used by successful C3.
It is one bar after the detected drop boundary by deliberate design: the
classifier's first drop bar is 98.7% vocal-active and has a weak first-quarter
drum onset (0.368), whereas the current cue has a strong first-quarter onset
(3.310), substantially less vocal coverage (62.0%), and stable raw full/low
energy across its four-bar loop boundary (-0.28/+0.17 dB). Nearby cues either
lose downbeat strength, have more vocal coverage, or sit much deeper inside
the phrase. There is no evidence-based reason to move it for B8.

The immediate full-target reveal is also retained. The private staged-target
counterfactual made the half-bar high-band loss worse (-7.805 dB), while the
actual target-only reveal rises +0.744 dB. The staged reconstruction still
differs from the full master (first-bar correlation 0.98835, residual ratio
0.16086, full master 4.27 dB brighter above 3 kHz), but that difference is
helping replace outgoing spectrum rather than causing the residual failure.

Target playback is not one linear deck stream in B7: target drop drums/low are
previewed as a four-bar loop, intro other/vocal run linearly into the cue, and
the full master starts at the cue on landing. C3 uses the same four-bar drum
restart successfully, so this is a declared choreography choice rather than a
remaining renderer defect. F alone uses adjacent natural-tempo target-master
slices throughout.

### C3/F control comparison

- B7 introduces target drum air at bar 1, body at 3.5, low at 5.3 (material by
  5.65), and target vocal at 5.2 (material by 5.6); full spectrum appears at
  bar 8. Its final bar has eight simultaneously moving source/target layers,
  and its source loop originally survived 0.78 bar after landing.
- C3 introduces target rhythm at bar 0, target low at bar 4 (material by 4.5),
  withholds target vocal until the postlanding master, and reaches full
  spectrum at bar 8. Its four-layer final-bar handoff settles target gains to
  drums 0.90 / low 1.00 / upper 0.88, and its final source echo ends 0.2392
  seconds before landing.
- F has only two concurrent reset actions: one linear target-context fade over
  1.9273 seconds and one decaying source-vocal echo sequence. Its last echo
  ends 0.0412 seconds before landing; adjacent raw target master supplies the
  landing. F's large energy rise is therefore a promised reset, unlike B7's
  unintentional prelanding bass pocket/rebound.

### Private diagnostic renders

All use exact B7 timing and cover two bars before through four bars after the
landing. They are forensic tools, not DJ candidates:

- `DIAG_SOURCE_TAIL.wav` — processed outgoing source only
- `DIAG_TARGET_PRELAND.wav` — target contribution before landing only
- `DIAG_TARGET_POSTLAND.wav` — target contribution after landing only
- `DIAG_TARGET_CONTINUOUS.wav` — target across the boundary, no source
- `DIAG_SUM_NO_SOURCE_FX.wav` — B7 with outgoing FX suppressed
- `DIAG_SUM_NO_TARGET_FULL_REVEAL.wav` — staged target retained after landing

`DIAG_SUM_NO_SOURCE_FX` and `DIAG_TARGET_CONTINUOUS` are intentionally
sample-identical in the focused window: by two bars before landing, B7 has no
remaining dry source, only its loop/riser/tail effects. Machine-readable
evidence is in private `B7_RESIDUAL_DIAGNOSTICS.json` and
`B7_C3_F_RESIDUAL_COMPARISON.json`.

### Exact B8 correction and regression evidence

B8 changes only the smallest set supported by those controls:

1. The target cue, full reveal, landing, gains, and B7 shared-clock renderer
   stay fixed. Only the target-low preview uses the same cue's stable two-bar
   cadence instead of exposing its four-bar internal pocket.
2. B7's uninterrupted rhythmic loop state is preserved through landing, then
   released by 0.6602 seconds — 20 ms before the performed target-vocal onset
   — instead of continuing 0.8774 seconds into that vocal.
3. A band-limited, diffuse wet residue derived from the existing riser carries
   only its >3 kHz release across landing and decays at the same pre-vocal
   endpoint. No unrelated impact or new musical event was added.

The B8 final-bar low quarter-bars are now -16.669, -16.791, -16.599, and
-16.211 dBFS. The landing high-band quarter-step improved from -5.486 dB in B7
to -2.745 dB. The landing-local sample delta is 0.194494, below the file's
0.280035 global 99.9th-percentile delta, so the wet release did not create a
click-like seam transient. B8 preserves B7 up to the source release scope,
contains finite audio, and has no clipping.

**STOP/GATE:** compare only `B7_FIXED_BOUNDARY.wav` against
`B8_RESIDUAL_FIX.wav`. Human listening decides whether the already-good source
move now flows into TRACK_B as one intentional performance. Do not produce B9,
resume automation/UI/Set Director, create another transition family, or render
a full mix before that verdict.

## B7 HUMAN VERDICT — STRUCTURAL FIXES VALIDATED; RESIDUAL LANDING FORENSICS ACTIVE
2026-09-14. The user compared `B6_LANDING_3` with
`B7_FIXED_BOUNDARY` and judged B7 **definitely and significantly better**.
This validates that the shared target time-map and uninterrupted source-loop
state fixes below were real and audible; preserve them permanently. The core
perceptual complaint nevertheless remains: the transition into TRACK_B is
still not fully convincing, smooth, or DJ-like. Do not declare success, revert
B7, resume automation/UI/Set Director/full mixes, or guess B8 parameters.

That task is complete in the B8 section above; B7 remains the frozen comparison
baseline and its renderer fixes must not be reverted.

## STRUCTURAL LANDING-BOUNDARY INVESTIGATION — B7 READY FOR HUMAN LISTENING
2026-09-14T17:32:26Z (fresh Codex recovery after the prior thread-store
failure).
Repository authority was read in the required order, including the complete
research specification and implementation plan. After an approved
`git fetch`, local HEAD and `origin/v2-professional-autonomous-dj` both resolve
to `93bbc327dded3da74498de04bd54c9ed57161779`. The tracked worktree and index
are clean; the pre-existing untracked `.claude/` directory remains untouched.

The latest human verdict supersedes the listening-ready stop instruction below:
`B6_LANDING_3` was the best B6 treatment, but still exposes a discontinuous
handoff boundary; `B6_LANDING_2` improved the landing but dropped the source
effect too abruptly; `B6_LANDING_1` was poor when its source-side effect tried
to connect to TRACK_B. Autonomous planning, UI, long mixes, and new transition
families remain paused.

The requested trace is complete. A crucial provenance finding is that the B6
manual R&D files do **not** travel through `PerformanceRecipe`, recipe
compilation, `PerformanceTransition`, `apply_transition`, Audition Lab, or the
Set Director/full-set renderer. Their actual path is `prepare_material` ->
direct stem/full-mix/loop envelopes -> a 128-sample (2.902-ms) manual splice ->
one fixed whole-file gain/soft-clip pass. No recipe/compiler/production-DSP
state exists to reset in B6, and patching those production modules would not
change the controlled artifact.

Exact structural diagnosis:

- The B6 source tail is **not truncated at landing**. It measures about
  -24.19 dBFS over the last half-beat before landing, -28.60 dBFS over the
  first half-beat after it, and reaches about -65.07 dBFS in its final 50 ms
  before becoming exactly zero at its declared 0.78-bar endpoint.
- It nevertheless has a real lifetime defect 0.219 bar before landing: B4's
  active one-beat loop buffer ends on a nonzero sample, then B6 creates a new,
  differently filtered buffer whose first sample is exactly zero and fades it
  back in. The old last-sample-to-new-first-sample component delta is
  `0.05433497`; the following 50-ms full level rises by 4.33 dB. Thus B6_3's
  apparent continuation is actually teardown/restart.
- The primary target defect is stronger. Raw target stems reconstruct their
  master correctly (`corr=0.999646`, residual/master RMS `0.02689`). The lab
  then launches separate adaptive FFmpeg `atempo` jobs for the master and each
  stem/interval. After that independent processing, the reconstructed stems
  correlate only `0.302336` with the separately processed master and their
  residual is `1.17845` times the master RMS. The transition therefore changes
  from independently stretched intro stems plus repeated target-drop
  drum/low buffers to a separately stretched mastered full mix at landing.
  It is phase-cued, but it is not one coherent rendered target deck.
- B6_3 exposes both defects because it asks one perceptual gesture to cross the
  splice while target ownership also changes there. Across the landing
  half-seconds it changes +0.85 dB full-band, +2.25 dB below 155 Hz, and
  -5.55 dB above 3 kHz. The 128-sample guard prevents a digital click but
  cannot preserve filter/time-stretch state or make incoherent buffers equal.
- C3 uses the same underlying manual target reconstruction and therefore masks,
  rather than disproves, that renderer defect. Its choreography has target
  rhythm/low ownership established before landing and its source echo is
  already clearing, so its half-second full/low/mid movements stay roughly
  -0.47/-0.98/+0.91 dB. F avoids the defect: its target intro and target body
  are adjacent samples from one natural-tempo master at one trim, while the
  source echo has completed its separate reset role before the target downbeat.
- There is no boundary-local mastering change in B6: all material receives the
  same fixed gain `0.556776515` and one memoryless soft-clip pass. The observed
  change is upstream buffer/state reconstruction, not mastering.

Classification: the demonstrated fault is in the **private manual renderer's
buffer/time-map lifetime**, amplified by B6's choreography. It is not evidence
of a `PerformanceRecipe`/`apply_transition` production defect because those
paths are absent from this render. The smallest correct fix was therefore made
in the private controlled renderer only: the target master and all landing
stems are now processed together once as a ten-channel bundle under one shared
time map, and the active source loop is transferred through a 12-ms state
handoff into one phase-continuous post-landing tail rather than restarted.
Autonomous production code remains unchanged and paused.

Exactly one controlled output was rendered:

- `/tmp/djenius_reference_dj_transition/B7_FIXED_BOUNDARY.wav`
- SHA-256 `88ef7b56c481bd210aab2dcf3a4d06ca82e0cf466f33c2fab9f6caf915c8b19a`
- stereo 44.1-kHz PCM-24, 40.0283s, peak `0.644854`, zero clipped samples
- transition 16.0218s; landing unchanged at 24.007s
- shared-clock target reconstruction `corr=0.999662`, residual ratio `0.02631`
- source buffer handoff delta reduced from `0.05433497` to approximately
  `1.86e-9`; tail duration/envelope remains B6_3's 0.78-bar design
- deterministic rerender reproduced the exact B7 SHA-256 above; all frozen
  B6_3/C3/F/B4/D2/B5_TARGET_2 hashes remain unchanged

Private reproducibility/diagnosis files are `render_b7_fixed_boundary.py` and
`diagnose_boundary_structure.py`; `REFERENCE_NOTES.json` contains the B7
control and measurements. This is engineering evidence only. Stop for the
human B6_3-vs-B7 listening gate; do not create B8 or resume automation.

## LANDING MICRO-LAB — B6 LANDING 1/2/3 READY FOR HUMAN LISTENING
2026-09-14T14:31:46Z (Codex/GPT-5.6 Sol). Latest human verdict is now the
authority: B5_TARGET_2 is the winning target-entry direction and is frozen as
the working reference; its staged target reveal is noticeably better, but its
final ownership transfer is still not smooth. B5_TARGET_1 is not smooth enough
and B5_TARGET_3 is abandoned. The successful B4 source choreography, target
pair, target cue, and fixed mastering control remain unchanged. Automation and
all broad product work remain paused.

The private landing-only listening files are in
`/tmp/djenius_reference_dj_transition/`:

- `B6_LANDING_1.wav` — target remains in its staged spectral/stem state at the
  nominal downbeat, then reaches the mastered full mix across 1.25 target bars;
  SHA-256
  `5c0c76c8e214cbe08418e0afd1e99d3fb02b447d7c073a10557f4f804b01a6eb`
- `B6_LANDING_2.wav` — during only the final transition bar, the partial target
  reveal becomes a phrase-aligned full target-stem reconstruction before the
  normal mastered drop begins; SHA-256
  `5717fe223b1b1fd7431be7aeb6378b1db66d4302f0aee4fe4851a74be87306fe`
- `B6_LANDING_3.wav` — B5_TARGET_2's target reveal remains unchanged; B4's
  high-passed one-beat source motif continues through the target downbeat as a
  decaying tail while target gain reaches unity within 0.62 bar; SHA-256
  `38854dc9f50bb215cfeda0fe8ef434395381fb90d22083a7e172de1ccc9c9ad7`

Forensic diagnosis:

- Beat/cue phase is not the defect. Target drum and low-frequency landing
  references show 0.0 ms best lag and correlations of 1.000/0.999. The intro
  and post-landing audio are both fitted to the same 1.997-second performance
  bar. The cue therefore remains unchanged.
- B5_TARGET_2 changes by about +2.0 dB overall and +3.2 dB below 155 Hz while
  losing about 4.6 dB above 3 kHz across the landing half-seconds. Its staged
  target's partial drum/stem/EQ state becomes the mastered full target through
  only a 128-sample/2.9-ms seam. The content is phase-aligned; the spectral
  ownership state is not.
- B4's one-beat source loop stops before the boundary and its riser ends at the
  boundary, reinforcing the perceptual syntax "effect stops, full target
  starts."
- C3 keeps target low/rhythm continuous and changes full level by roughly
  -0.5 dB with low/mid changes within about 1 dB. F instead earns its larger
  landing contrast by clearly separating source release, echo decay, target
  context, and target downbeat. B5_TARGET_2 promises continuity, so its abrupt
  spectral pivot reads as a defect rather than a reset.

Every B6 output is sample-identical to frozen B5_TARGET_2 up to the start of the
eighth/final transition bar within one PCM-24 quantization step. LANDING_1 does
not change anything before the nominal landing; LANDING_2 changes only the
final bar's target reconstruction; LANDING_3 extends only the final source-loop
gesture and first target bar. Target remains the sole bass owner throughout all
three treatments. The transition still begins at 7.988s and lands at 24.007s.

`REFERENCE_NOTES.json` contains the full diagnosis, C3/F comparison, exact
variant differences, focused listening window, fixed-reference hashes, and
safety diagnostics. The frozen `B5_TARGET_2.wav` remains byte-identical,
SHA-256 `9a2a547f39a1ed45e640f8dcf90c1fc4b85d92e10e1411531667459fc3b3a8d9`.
C3, D2, F, and B4 also remain unchanged. All B6 WAVs are stereo 44.1-kHz PCM-24
with no clipped samples and no anomalous sample discontinuity at landing. The
private reproducibility/forensics aids are `render_b6_landing_lab.py` and
`analyze_b6_landing.py`. No production code changed. Stop here for the human
listening gate; do not return to automation.

## TARGET-ENTRY LAB — B5 TARGET 1/2/3 READY FOR HUMAN LISTENING
2026-09-14T14:11:42Z (Codex/GPT-5.6 Sol). Latest human verdict is now the
authority: A4 is too ordinary and is paused; B4's source-side loop manipulation
is genuinely DJ-like but its target handoff is bad; E3 has useful source-side
preparation but its target arrival is also wrong. F and C3 remain the successful
references, D2 remains the acceptable restrained reference, and E3 is not being
iterated until the target-entry lesson is established. Automation and all broad
product work remain paused.

The controlled private target-entry lab is ready in
`/tmp/djenius_reference_dj_transition/`:

- `B5_TARGET_1.wav` — early continuous rhythmic introduction, SHA-256
  `105a4dea78ad5da508ce29ac234b52a8761cfe03a69ff66ee6d1ac8e781ace06`
- `B5_TARGET_2.wav` — staged drum/stem/frequency/identity reveal, SHA-256
  `9a2a547f39a1ed45e640f8dcf90c1fc4b85d92e10e1411531667459fc3b3a8d9`
- `B5_TARGET_3.wav` — sparse tease into an alternate lower-vocal drop cue,
  SHA-256
  `524b58894058491f27f26cde4603ec1aad008c0481e2002cf041f367020ebb39`

All three retain B4's exact source-side contribution: source low/upper
envelopes, the same bar-2 phase-anchored `4 -> 2 -> 1` loop, the same shaped
riser, and the same source release. The raw source contribution is
sample-identical in every variant, SHA-256
`8071c0caddd8dfa03768708c930fa1559f0fed11dbff2dd76ecbb9d40ac9dc4b`.
They also use one fixed master gain (`0.556776515`) derived from the original B4
raw performance; per-variant loudness normalization is disabled so target entry
is the only experimental variable. TARGET_1 and TARGET_2 retain B4's target cue;
TARGET_3 changes only the target cue to test whether the original dense/vocal
arrival was itself unsuitable. The source track and choreography remain fixed.

Root cause isolated in B4: its target low, drum, and upper previews all withdrew
before landing while the source loop/riser also ended. That erased the shared
territory and made the full target reappear as a replacement. Target bass also
arrived before target identity was sufficiently established, while target vocal
identity remained absent until landing. C3 demonstrates continuity across the
landing and staged target ownership; F demonstrates separate perceptual roles
for source release, effect tail, target context, and full target entry. The new
variants test those principles without copying C3/F's effects.

`REFERENCE_NOTES.json` records the exact target-only change, hypothesis, and
bar-level choreography for each variant, plus listening times, fixed-source and
mastering controls, diagnostics, and preservation hashes. All three transitions
begin at 7.988s and land at 24.007s, followed by about eight clean target bars.
They are stereo 44.1-kHz PCM-24 and contain no clipped samples. Integrated
loudness is -14.079/-14.246/-14.320 LUFS under the fixed master gain; this is a
safety/control check, not acceptance evidence. The private reproducibility and
visual QA aids are `render_target_entry_lab.py` and
`TARGET_ENTRY_LAB_DIAGNOSTICS.png`.

B4, C3, D2, and F were hashed before and after rendering and remain byte-identical:
B4 `9060240f5aedd8d8a185f447d82eaa9279b099e64d2a08ea20d8b67ffee20a07`,
C3 `ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03`,
D2 `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586`,
and F `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`.
No production code changed. Stop here for the human listening gate; do not return
to automation or transfer anything to E3 yet.

## MUSICAL-CAUSALITY ROUND — A4/B4/E3 READY; C3/D2/F PRESERVED
2026-09-14T13:53:01Z (Codex/GPT-5.6 Sol). Latest human verdict is now the
authority: F remains the strongest gold reference; C3 is newly successful and
must not be redesigned; D2 is acceptable as the restrained/smooth category;
A3 still sounded like source -> unrelated effect -> target; B3's concept worked
but remained mechanical; E2 still sounded like an unearned total replacement.
Automation and all broad product work remain paused.

New private listening files in `/tmp/djenius_reference_dj_transition/`:

- `REFERENCE_A4.wav` — SHA-256
  `14eb04318b6cd695e347e70e05693b0fdf1d458835c87ffed6b69f906eed5db7`
- `REFERENCE_B4.wav` — SHA-256
  `9060240f5aedd8d8a185f447d82eaa9279b099e64d2a08ea20d8b67ffee20a07`
- `REFERENCE_E3.wav` — SHA-256
  `919cb480ad169fd828b69f7209abd19c34863569730b09f18f72743597447158`

Successful/acceptable files were frozen before rendering and remain
byte-identical afterward: C3
`ecdd7b694a3d9f5100f02e3aa62df0ec68cb90e874de1b863eec846a8a8eff03`,
D2 `5c1f72c9ae6edff9c7e51c0f6386f15abb72455a8421561cf242ef4864ade586`,
and F `947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`.
No C4 was created because no single certain micro-polish justified altering the
successful C3.

Root causes and fixes:

- **A4:** A3 already used the target's real drums, but kept the target's most
  recognizable pre-drop material—its vocal runway—out of the bridge. The
  percussion was related by provenance but anonymous to the listener. A4 first
  hands rhythmic ownership toward the target, clears the source vocal, then
  introduces the target's actual final intro vocal before delaying the two-beat
  bass swap until the target groove has been accepted. The landing completes a
  target identity already heard; no generated effect was added.
- **B4:** seam study across source motif candidates selected bar 2, which had
  the smallest boundary discontinuity and most even quarter-beat energy. B3's
  crossfaded simultaneous loop states could create phasing/flams even under
  smooth envelopes. B4 uses one phase-anchored motif with only sequential
  4-beat -> 2-beat -> 1-beat states. Halvings occur at the shared loop start;
  the half-beat flourish and synthetic impact remain removed; riser entrance
  starts at zero and the bass pocket is shorter.
- **E3:** the E/E2 pair was judged wrong for the technique: incompatible keys
  required hiding all target identity except drums, guaranteeing sudden total
  replacement. E3 uses a different exact-key pair with an eight-bar low-energy
  target runway into a stronger section. Target intro highs/mids/drums enter
  before the cut; source drums/vocal/harmony/bass clear sequentially; one short
  source-vocal throw marks release; target vocal lightly foreshadows identity;
  target bass remains reserved for the landing. A rejected first private E3
  render exposed another issue: the intro was about 5 dB quieter than the source
  and much quieter than its own landing, leaving preparation theoretical. The
  final E3 uses an intro-only deck return so target material becomes dominant in
  the final bar and the landing adds full range rather than the entire song.

`REFERENCE_NOTES.json` contains exact prior-version changes, causal rationale,
bar-level choreography, bass ownership, listening times, preservation hashes,
and private safety diagnostics. `render_remaining_round.py` and
`REMAINING_ROUND_DIAGNOSTICS.png` are private reproducibility/QA aids. A4/B4
transitions begin at 7.988s and land at 24.007s; E3 begins at 7.384s and lands
at 22.172s. All three WAVs are stereo 44.1-kHz PCM-24 with no clipped samples;
loop edit/landing deltas remain below ordinary high-percentile musical
transients. Human listening remains the only acceptance gate. No production
code changed. Stop here.

## SMOOTHNESS ROUND — A3/B3/C3/D2/E2 READY; F FROZEN AS GOLD
2026-09-14T13:28:28Z (Codex/GPT-5.6 Sol). The user listened to every manual
reference through A2-F. Human verdict: A2/B2/C2 improved their predecessors but
still lacked effect integration/smoothness; D was too ordinary; E was rough;
F was "REALLY GOOD" relative to the rest and is now the explicit gold
reference. `REFERENCE_F.wav` was frozen before work and remained byte-identical
after every render, SHA-256
`947a1a2556efb6e1d6b6ffd3ebb9c16c851d3d97bdd5026b57ec3bd5f1056f48`.
No F2 was made because no sufficiently certain micro-polish justified risking
the approved reference.

The new private human-listening files are under
`/tmp/djenius_reference_dj_transition/`:

- `REFERENCE_A3.wav`
- `REFERENCE_B3.wav`
- `REFERENCE_C3.wav`
- `REFERENCE_D2.wav`
- `REFERENCE_E2.wav`
- preserved `REFERENCE_F.wav`

`REFERENCE_NOTES.json` now includes the exact prior-version deltas, why each
change targets smoothness, transferable principles learned from F, bar-level
choreography, bass ownership, listening timestamps, and diagnostics. The
private reproducible script is `render_smoothness_round.py`; private visual QA
is `SMOOTHNESS_ROUND_DIAGNOSTICS.png`. No private track filename or identity is
present in Git or the notes.

Transferable explanation for F's success: it tells one sequential story rather
than stacking several actions; dry source, wet tail, target context, and target
full-range entry occupy different perceptual roles; one track owns bass at a
time; the wet signal comes from musical source material and decays into space;
and the target begins establishing before its landing completes the direction.
F's shorter duration helps because that pacing is coherent, not because
echo/reset is intrinsically superior.

Round changes:

- **A3:** uses a four-bar phrase of the real target drums, split into air/body.
  Target hats enter first, drum body waits for the two-beat bass handoff, and
  source drums fade separately from source music. This directly addresses the
  pasted-on percussion criticism without generated drums or louder FX.
- **B3:** loop sizes/filters no longer switch as hard stages. Raised-cosine
  crossfades overlap the 4/2/1/half-beat captures, the riser has a shaped
  zero-level entry, the bass pocket is narrower, and the disconnected synthetic
  impact is removed so the target's own transient is the payoff.
- **C3:** preserves the human-liked repeat/echo character. Target drum material
  is now a four-bar rather than two-bar repeat; drum/other/vocal/bass ownership
  changes sequentially; taps have edge guards, progressive damping, and short
  stereo diffusion. A too-dense first private render was rejected and reduced
  before packaging.
- **D2:** fixes D's root musical defect: its intro-derived target low band was
  nearly empty, making the stated bass swap inaudible. D2 uses target landing
  low-end and drums only after the swap, while high/mid/vocal ownership proceeds
  in a deliberate 12-bar sequence. No decorative FX were added.
- **E2:** retains the decisive phrase/drop cut but replaces the envelope cliff.
  A four-bar native target drum phrase splits into air/body anticipation;
  source low/mid/high release at separate times; musical energy remains until
  the final fraction of a beat; no unrelated impact or FX masks the cut.

All five new WAVs are stereo 44.1-kHz PCM-24 with zero clipped samples; landing
crossfade deltas remain below ordinary high-percentile musical transients. This
is safety evidence only—the user must decide whether they are musically smooth.
No repository production code changed. Set Director, Candidate Composer,
Audition Lab, UI, long mixes, and autonomous work remain paused. Stop at this
human gate.

## GOLD-REFERENCE ROUND 2 — A2 THROUGH F READY FOR HUMAN LISTENING
2026-09-14T13:08:26Z (Codex/GPT-5.6 Sol). The user listened to the first
handcrafted A/B/C package and gave the first positive performance verdict:
all three sounded noticeably more like real DJing and were much better than the
autonomous mixes. They are promising, not finished or frozen. Per explicit
instruction, all Set Director, Candidate Composer, Audition Lab, UI, broad
architecture, and autonomous work remains paused.

The updated private package remains at:

`/tmp/djenius_reference_dj_transition/`

New listening files are `REFERENCE_A2.wav`, `REFERENCE_B2.wav`,
`REFERENCE_C2.wav`, `REFERENCE_D.wav`, `REFERENCE_E.wav`, and
`REFERENCE_F.wav`. `REFERENCE_NOTES.json` has been replaced with the requested
anonymous bar-level choreography, selection rationale, listening timestamps,
changes from A/B/C, bass ownership, FX, and safety diagnostics. The original
A/B/C files remain available. `GOLD_REFERENCE_DIAGNOSTICS.png` and
`render_gold_references.py` are private reproducibility aids. No private track
filename or identity appears in the notes or Git.

Round-2 strategies are intentionally different:

- **A2** refines A into a real three-band blend: target highs first, mids later,
  a one-beat bass handoff, and ordered source release. No decorative FX.
- **B2** preserves the foreground `4 -> 2 -> 1 -> 1/2 beat` source loop, then
  deliberately removes low-end/drums during the final build pocket so the
  target drop and bounded impact have space to land.
- **C2** preserves the rhythmic stem/mashup identity but replaces overlapping
  half-bar echo chunks with one selected vocal transient and four discrete,
  beat-spaced, progressively darker alternating-stereo post-fader taps.
- **D** uses a different, adjacent-key/close-tempo pair for a patient 12-bar EQ
  blend. Instrumental frequency ownership develops first; source and target
  vocals hand off after the bass switch instead of colliding.
- **E** uses another pair with near tempo compatibility but deliberately
  incompatible keys. Only high-passed target drums are teased; bass, melody,
  and vocals remain out until a tight phrase-release pocket and hard full-drop
  landing. It is not a harmonic crossfade.
- **F** uses a compatible-key pair with radically different tempos. It refuses
  forced beatmatch: the source completes four natural-tempo bars, a captured
  vocal echoes post-fader through a roughly two-second beatless reset, the
  target intro enters at natural tempo, and its verse lands after the echo has
  cleared.

Private iteration rejected three defects before this checkpoint: D initially
lost too much body because its instrumental intro was quieter than its landing;
E initially left about half a second of dead air; F initially included two
seconds of genuinely silent target intro. The final renders correct those
decisions. All six are stereo 44.1-kHz PCM-24, have no clipped samples, no
accidental silence, and click-safe landing seams. The intentional low-end paths
are continuous in A2/C2/D, removed only for the designed buildup/cut/reset in
B2/E/F. Human listening remains the only acceptance gate. Stop here; do not
extract templates or return to automation until the user judges A2-F.

## PERFORMANCE RESET — HANDCRAFTED REFERENCE #1 READY FOR HUMAN LISTENING
2026-09-14T12:36:51Z (Codex/GPT-5.6 Sol). The user's new authority explicitly
pauses autonomous-planner, scoring, set-level, UI, and broad architecture work.
The only active gate is proving one manually choreographed real-track handoff.
Local HEAD and the existing remote-tracking ref were both
`af5400d6921fdbdde8bd626f785d27021c5e8fcd` at recovery; the pre-existing
untracked `.claude/` directory remains untouched. The repository and Downloads
research specifications were verified byte-identical (SHA-256
`de2605fe29f41594ff035c3333fcbc151576e06584119b4f712e59da3e8a224f`).

A private listening package is ready at:

`/tmp/djenius_reference_dj_transition/`

It contains `REFERENCE_A.wav`, `REFERENCE_B.wav`, `REFERENCE_C.wav`, and the
anonymous `REFERENCE_NOTES.json` requested by the user, plus a private
diagnostic image and reproducible private render script. No real track identity
was written to Git. All clips are about 40 seconds: ~8 seconds of source
context, an exact eight-detected-bar / 16.022-second performed transition, and
~16 seconds after the landing.

The manually selected pair has matching 10B keys, high-confidence beatgrids,
complete stems, a low-vocal energetic TRACK_A exit, and a clear TRACK_B drop.
Manual cue study found that TRACK_B's nominal section boundary leads into a
sparse pickup bar; using it produced a false 5–6 dB landing collapse. The final
cue deliberately skips that pickup and lands on TRACK_B's first sustained
full-power drop downbeat. A +6.4 dB target deck trim corrects a real mastering
level mismatch before choreography. The final half-second landing changes are
+0.62 dB (A), -0.22 dB (B's riser/impact resolution), and +0.14 dB (C), with
continuous low-end, zero clipping, and no accidental silence.

- **A:** restrained long stem/EQ blend, staged target drums/upper frequencies,
  explicit phrase-boundary bass ownership swap, then clean source release.
- **B:** foreground source loop progression `4 beats -> 2 -> 1 -> 1/2`, rising
  high-pass tension, a genuinely audible two-bar riser, bounded landing impact,
  and full target release. An earlier private pass proved the production
  riser/impact at its raw generator ceiling was effectively buried (~-46 dBFS),
  so only this selected build receives a local bounded return gain.
- **C:** early rhythmic stem handoff, short TRACK_A-vocal-over-TRACK_B-bed
  mashup, then a four-tap post-fader vocal echo release with no riser/impact.

This checkpoint intentionally made no repository production-code change. It is
a private performance-vocabulary proof built from the production analyzer,
cached stems, time-stretching, filters, loudness/limiting utilities, and
procedural FX. Do not return to automation until the user listens. If none is
approved, iterate on this performance/audio; if one is approved, freeze its
choreography as reference #1 and create a genuinely different reference #2.

## RESUMED PERFORMANCE-RECOVERY SESSION
2026-09-13T17:59:57Z (Codex/GPT-5.6 Sol). Recovered the repository in the
required authority order, read the complete research specification, and
verified that the original Downloads copy is byte-identical (SHA-256
`de2605fe29f41594ff035c3333fcbc151576e06584119b4f712e59da3e8a224f`).
After `git fetch origin`, local HEAD and
`origin/v2-professional-autonomous-dj` both equal
`bf224162444cfaf410392899153c0a7660fc52da`; the only pre-existing working
tree item is untracked `.claude/`, which remains untouched. The prior
handoff's private listening package is present under
`/tmp/djenius_v1_v2_listening/`. Active work is limited to the two mandated
questions: coherent cross-edge track appearances and technique-family
behavior through the actual recipe/compiler/renderer/audio path. At this
initial recovery instant, no production change had been made yet; the completed
checkpoint is recorded directly below.

### First resumed-session findings (recorded before production edits)
- Built the required private same-anchor real-audio lab at
  `/tmp/djenius_performance_lab/` (one anonymous compatible pair, 4 bars,
  plain crossfade plus all 12 Phase-3 techniques, cached real stems where
  available). The manifest records compiler actions/operations and aligned
  difference diagnostics; numeric distance is diagnostic only, never the
  human-audibility gate.
- `riser_impact` is confirmed to be almost literally the plain crossfade in
  the production output (`correlation=0.999954`, difference RMS only 0.00956
  of the crossfade RMS). Its generated riser/impact layer exists, but the
  recipe schedules the one-bar riser too early and the impact on beat 4 of
  the final bar rather than the drop downbeat; the base mix remains a
  gradual crossfade.
- `bass_swap` is also extremely close in full-band output on this real pair
  (`correlation=0.998385`, difference RMS ratio 0.056825), even with real
  stems supplied. This does not by itself prove the low-band ownership move
  is inaudible, but it makes a dedicated low-band/ownership audit necessary.
- `drum_bridge` compiles as the same `beatmatched_blend` used by `eq_blend`
  plus 32 procedural events. Its difference from a plain crossfade is
  dominated by the shared beatmatch/EQ path, so a direct drum-bridge-vs-EQ
  isolation comparison is required before claiming the added groove matters.
- The recipe compiler preserves typed action schedules as diagnostics but
  does not execute most action envelopes. It reduces selection primarily to
  one legacy transition type plus a small set of hard-coded operations.
- `phrase_cut` has a V2 splice-semantics defect: DSP uses only a tiny target
  seam at the end of the buffer, but both V2 preview and full-set renderers
  advance the target cursor by the entire multi-bar overlap. That skips the
  target material immediately after the declared landing anchor.
- `stem_handoff` is audibly distinct when the private lab supplies real
  stems (`correlation=0.926739` vs crossfade), but it is unreachable in the
  actual application path: the Set Director provider never loads cached
  stems, and `render_set_director_mix` unconditionally refuses every
  stem-requiring candidate even though `TrackAudio` already has a `stems`
  field.

### Performance-recovery implementation checkpoint
Production changes are now in the working tree and documented in
`docs/v2/PERFORMANCE_QUALITY_AUDIT.md`:

- Set Director schema 7.1 carries typed, path-dependent track appearances.
  Candidate Composer receives an entry/consumed-end/minimum-establishment
  envelope and rejects anchors or transition lengths that would squeeze the
  track before it has established. Appearance state participates in the edge
  cache key. The old renderer shift remains only as a legacy/manual-plan
  compatibility guard.
- Phrase-cut preview/full-set splicing and duration planning now advance the
  target cursor by the actual click-safe seam rather than silently skipping
  the whole nominal overlap.
- Cached stems now flow from the real application provider through full-set
  segment slicing/validation into renderer DSP. Missing required stems fail
  explicitly; they do not masquerade as a stem handoff over crossfade.
- Phase-5 EQ blend/drum bridge/build families compile a renderer-executed
  `mix_choreography` directive. EQ stages incoming upper frequencies before a
  deliberate bass switch; loop shortening and riser/impact hold the source
  build and land the full target at 75%; drum bridge creates bounded space for
  its generated groove. The riser is scheduled in the penultimate bar and its
  impact is now on beat 1 of the landing bar.
- Echo release now captures the preceding source beat into a bounded
  post-fader tail, removes the dry source quickly, and gives the target clear
  space instead of adding echo over an ordinary long fade.
- Audition Lab's generic spectral metric now has bounded family-specific
  intent allowances. Collision, mud, holes, and excess beyond the allowance
  remain penalized; this corrects the damage model rather than adding a
  creative bonus.

Validation is complete for this checkpoint: focused recovery coverage passes
at **110 passed**; the complete repository regression passes at **1102 passed**
with only the two pre-existing Typer/Click deprecation warnings. `ruff check`
on every touched production/test file and `git diff --check` are clean.

The final real recovery render produced exact plan/render duration agreement at
**661.228s**, zero anchor shifts, and the sequence `echo_out /
loop_shortening / drum_bridge / riser_impact`. Its three middle tracks received
**33.599 / 130.888 / 191.989s** of independent airtime. The identical plan was
selected on three complete deterministic runs, including before and after the
bounded Audition spectral-intent correction. The finalized private package is:

`/tmp/djenius_performance_lab/listening_checkpoint/`

It contains full `V1 / previous V2 / recovery V2` links, controlled fixed-anchor
family comparisons, contextual clips for all four selected recovery handoffs,
and an anonymized manifest. **Human gate remains pending; do not call this
product failure resolved based on the engineering evidence.**

## LATEST VERIFIED TIME
2026-09-13T18:48:49Z (final private recovery render completed; full 1102-test
regression and lint/diff checks completed immediately beforehand)

## PERFORMANCE-RECOVERY COMMIT
The validated production/test/audit checkpoint was committed and pushed as
`32b2d3d6e679495d0edd7818fd2a787cb512608e` (`Recover V2 DJ performance
choreography`). This final handoff-status edit follows that production commit;
use `git log -1` and the remote ref as authority for its own docs-only SHA.
The only remaining untracked item is the pre-existing `.claude/` directory,
which was not touched or staged.

## PRIOR HANDOFF VERIFIED TIME (historical)
2026-09-13T20:05Z (user is transferring development to a different coding
agent -- GPT-5.6 Sol -- after this update; this session is stopping per
explicit instruction, not because work is finished)

## CURRENT PHASE
**Not Phase 8/9/10 work, and no new roadmap phase should start.** This is a
cross-phase, unplanned performance-quality investigation, now in its
**second round**. See `docs/v2/STATE.md` for the durable roadmap-level
summary (also updated this turn, kept consistent with this file) -- that
file records phase completion history unchanged; this file has the
operational detail.

## SECOND HUMAN LISTENING RESULT (read this first -- supersedes any "the
## fixes solved it" framing from earlier in this investigation)

The user personally listened again, this time to the fixed V2 code (the
four defects below already fixed, comparison rerendered). Their verdict,
recorded as close to verbatim as possible because it is the actual product
gate, not a paraphrase to soften:

> V2 is NOT obviously different from V1 overall. I can occasionally notice
> loops, builds, drops, echo, bass changes, and similar V2 techniques.
> Those actions are subtle/small. The difference can be noticed from time
> to time, but it is not transformative. Most importantly: it still does
> NOT feel like a real DJ is actively performing. I did not have moments
> where I clearly thought: "yes, that was a real DJ move."

**Explicit instruction accompanying this: treat it as an unresolved
product-quality failure.** The project's purpose is not to contain
correctly-labeled DJ techniques or technically valid DSP -- it is for
DJenius to actually behave and sound like an intentional autonomous DJ,
per the research specification. The four fixes below were real, verified,
and did measurably improve duration/family-diversity/audit-coverage -- but
this second listen proves they were **not sufficient**, and the user does
not want that treated as progress that lowers the bar.

The two "still-open" findings from the first round (cross-edge anchor
consistency, and technique labels compiling to near-identical DSP) are
explicitly called out by the user as highly relevant to this exact result
and are almost certainly implicated in why "loops, builds, drops, echo,
bass changes" register as noticeable-but-small rather than as a real DJ
move.

## CURRENT BRANCH
`v2-professional-autonomous-dj`

## GIT STATE (verified immediately before this handoff update)
- Local HEAD: `43288c69bff8d3ef7b66a473d63e20bf01138b45`
- Remote HEAD (`origin/v2-professional-autonomous-dj`, via `git fetch`):
  `43288c69bff8d3ef7b66a473d63e20bf01138b45` -- **equal to local**.
- `git status --short`: only `?? .claude/` (untracked session-tooling
  directory; never `git add` it; not part of the product).
- This handoff update (this file + `docs/v2/STATE.md`) will be committed
  and pushed immediately after being written, which will advance both
  local and remote HEAD by one commit. **Re-run `git log -1 --format='%H %s'`
  and `git fetch && git rev-parse origin/v2-professional-autonomous-dj`
  before trusting a specific SHA** -- the "LAST PUSHED COMMIT" line below
  names the commit this update itself becomes, so check it matches.

## LAST PUSHED COMMIT
Immediately before this update: `43288c69bff8d3ef7b66a473d63e20bf01138b45`
- "Update handoff with V2 listening-investigation findings and spec audit"
(docs only). The four production fixes themselves landed one commit
earlier at `89bfda5d0265d38cb1247fdb319f0ec1bcebe320` - "Fix real V2
planning defects found by human listening comparison". This update's own
commit (docs only: this file + `STATE.md`) will be the new HEAD after it
is pushed -- verify its SHA with `git log -1` rather than trusting a
number written before the commit existed.

## ALL FILES CHANGED THIS INVESTIGATION (across both commits so far)
- `djenius/core/candidate_composer.py` -- `_choose_anchor` position
  weighting fix.
- `djenius/core/set_director.py` -- audit budget/ordering fix, unrenderable-
  edge exclusion, real-anchor duration bookkeeping.
- `tests/test_v2_phase5_candidate_composer.py` -- new
  `test_choose_anchor_weighs_position_not_just_a_tiebreak`.
- `tests/test_v2_phase7_set_director.py` -- new
  `test_plan_never_selects_a_hard_rejected_edge` and
  `test_planned_duration_is_far_closer_to_the_actual_render_than_before`;
  fixed two tests whose manual-verification logic needed to match the
  production ordering change.
- `docs/v2/ACTIVE_HANDOFF.md` (this file) -- rewritten twice this
  investigation (once after the fixes, once now after the second listen).
- `docs/v2/STATE.md` -- reconciled this turn to stop describing Phase 10 as
  the open item and instead describe performance-quality/DJ-likeness as the
  single open, cross-phase gate.
No other tracked files changed. No real track names, artists, or filepaths
were introduced into any tracked file at any point.

## WORKING TREE
Clean aside from untracked `.claude/` (verified above).

## WHAT HAPPENED, IN ORDER

1. **First listen** (pre-fix): user rendered/listened to a private V1-vs-V2
   sanity comparison (4-track subset, same library/target duration/
   loudness) and could not hear a clear difference at all. Declared this a
   failure and mandated a root-cause investigation, explicitly forbidding
   "explaining it away" via passing tests/QA/provenance.
2. Investigation found **four real, independent, verified production
   defects**, all fixed, regression-tested, full 1095-test suite green,
   committed at `89bfda5`:
   - `SetDirectorConfig.max_candidates_audited_per_edge` was 4 while
     Candidate Composer generates up to 8, ordered by content-hash id --
     silently excluded whole technique families (the longer, more elaborate
     `eq_blend`/`filter_blend`/`phrase_cut`/`loop_transition`) from ever
     being auditioned for some real handoffs. **Fix:** raised to 8, added
     `_family_diverse_order` so a bounded budget samples across families
     before repeating one.
   - The beam search could select an edge where **every** audited candidate
     hard-rejected on real audition (`survivor_count == 0`) -- such a plan
     crashes at render time (`SetDirectorRenderError`). **Fix:** infeasible
     edges are excluded from beam expansion; a starved beam finishes where
     it stands instead of being forced through one.
   - `_choose_anchor`'s position preference (`directional`) was a tuple
     tie-breaker that only mattered on an *exact* score tie -- which real,
     continuously-varying cue scores essentially never produce. Anchors
     routinely landed deep inside a track regardless of position; one real
     track got only ~15s of standalone airtime out of 209s. **Fix:** folded
     into the primary score as a bounded (0.35) weighted term.
   - `_estimate_overlap_sec` assumed every track contributes close to its
     full length once a flat ~16-bar overlap is subtracted. Real anchors
     land far from track boundaries, so this overstated a real plan's
     duration by ~236s (664.0s planned vs 427.8s actually rendered).
     **Fix:** duration bookkeeping now uses each edge's real
     selected-candidate anchors.
   - A **fifth, deeper gap was found and documented but deliberately NOT
     fixed**: a middle track's entry anchor (edge before it) and its own
     exit anchor (edge after it) are still chosen independently -- Candidate
     Composer has no notion of "the edge before/after." The renderer's
     `anchor_shift_sec` correction (D044) absorbs the conflict at render
     time. Still happens after the fix (confirmed: the same TRACK_02
     handoff still needs a 14.86s shift in the fresh comparison-A render).
3. Reran the exact same end-to-end comparison, unchanged script, same seed/
   library/target. **Measured improvement:**
   - V2 rendered duration: 427.8s -> **589.2s** against the 600s target.
   - V2 track count: 4 -> **5 tracks**.
   - `candidates_rendered`: previously partial; now **270/270** generated
     candidates fully audited (100%, was capped before).
   - V1 unchanged (504.8s, same order/techniques) -- no V1 code touched.
   - Technique sequence: `riser_impact, loop_shortening, echo_out,
     drum_bridge` -- all 4 distinct (spec section 34's "no single technique
     > 40%" target: met).
4. Built comparison (B), the controlled performance comparison: same fixed
   track order for both systems (V1's own comparison-A order), each system
   picks its own technique.
   Script: `/tmp/djenius_v1_v2_listening/render_comparison_b_controlled.py`.
   V1 chose `filter_sweep, filter_sweep, phrase_cut`; V2 (same 3 pairs)
   chose `riser_impact, drum_bridge, phrase_cut` -- agreed with V1 on the
   last pair, diverged on the first two. The same TRACK_02 anchor-shift
   (14.86s) reappeared, confirming it is order-independent.
5. Built the private per-handoff review package (comparison A only):
   `/tmp/djenius_v1_v2_listening/handoff_clips/` (7 clips, each ~6s
   pre-roll + transition + ~6s post-roll, cut using `render_mix`'s own
   diagnostics JSON and `render_set_director_mix`'s own provenance --
   exact absolute positions, not re-estimated) and
   `/tmp/djenius_v1_v2_listening/handoff_review_manifest.json` (per-handoff
   technique, sections, why chosen, every candidate considered with
   rejection reasons, scores). All anonymized. Delivered to the user via
   `SendUserFile` in the prior turn.
6. Audited V2 against `docs/v2/DJENIUS_V2_RESEARCH_SPEC.md` (verified
   identical to the copy at `~/Downloads/...` via `diff`). Findings below.
7. **User listened a second time, to the post-fix V2 render.** Verdict
   quoted in full at the top of this file: occasional, subtle, non-
   transformative differences; does not feel like a real DJ performing.
   Treated explicitly as still-unresolved, not progress that satisfies the
   gate.

## SPEC AUDIT FINDINGS (grounded in `docs/v2/DJENIUS_V2_RESEARCH_SPEC.md`)

- **Section 32 (V1 vs V2 Blind Comparison)**: literal spec source of the
  gate both listens have now failed. Requires V2 to "win clearly" on
  musical intent, transition variety, creative performance, set coherence,
  DJ-likeness -- passing automated tests is explicitly stated to be
  insufficient. **Status: failed twice.**
- **Section 34 (Transition Diversity Acceptance)**: "No single technique
  > 40% of transitions" -- comparison A meets this numerically (4 distinct
  techniques / 4 transitions). BUT the same section also asks for "short,
  medium, and long transitions where appropriate" -- comparison A's 4
  techniques (`riser_impact`, `loop_shortening`, `echo_out`, `drum_bridge`)
  are **all** short, hard-coded to `bars=4` in `candidate_composer.py`
  (`phase3_recipe(..., bars=4)`, not `choose_bars()`).
  `eq_blend`/`filter_blend` (longer 8-16 bar treatments) were fully, fairly
  audited this time and genuinely lost on score for these specific real
  pairs -- not excluded by a bug. **This is very likely a leading
  contributor to the second listening failure**: technique-family
  diversity alone (satisfying the letter of section 34) does not produce
  audible/structural diversity if every winning family is short and
  similar in shape.
- **Section 16 (Candidate Ranking)** vs. actual `AuditionConfig.weights`
  (`djenius/core/audition_lab.py`): spec suggests `phrase_fit` at the
  highest weight (0.18) plus `groove_fit`/`harmonic_fit`/
  `technique_context_fit`/`novelty`; actual weights are
  `technical_margin 0.16, beat_stability 0.22, spectral_cleanliness 0.18,
  vocal_safety 0.14, energy_goal_fit 0.20, fx_safety 0.10`. **Verified this
  specific absence is correct layering, not a bug**: phrase/groove/harmonic
  fit are track-pair-level properties fixed once upstream (shared by every
  technique candidate for a pair), not technique-choice-level -- they
  wouldn't discriminate between DSP options for the same pair. `novelty`/
  `technique_context_fit` are the one plausible small real gap, partially
  covered by Set Director's `technique_diversity` edge component but not
  reproduced inside Audition Lab itself.
- **Section 35 (Creativity Budget)**: not implemented at all anywhere in
  `set_director.py`. Not proven to matter yet on short 4-5 track
  comparisons.
- **Definition of Done (section 43) "Human listening" checklist**,
  "Transitions no longer feel mostly like fades": checked the DSP
  compilation table in `candidate_composer.py` (~line 742). `riser_impact`
  and `loop_shortening` -- **2 of comparison A's 4 chosen techniques** --
  both compile to plain `crossfade` DSP with a layered
  riser/impact sample or loop-stutter on top, not a structurally different
  mix. `echo_out`/`drum_bridge` do use genuinely different DSP
  (`echo_out`, `beatmatched_blend`). **This is the single most concrete,
  spec-grounded explanation on file for the second listening result**:
  half of what V2 selected in the flagship comparison render is
  "crossfade plus a small layer," which is exactly consistent with
  "occasionally noticeable... subtle/small... not transformative."

## PRIVATE LOCAL ARTIFACTS (all outside git; comparison/review package)
Everything under `/tmp/djenius_v1_v2_listening/` (not reproducible via
`git checkout` -- intentionally outside version control):
- `v1_baseline.wav` / `v2_current.wav` -- comparison (A) full mixes. User
  listened to these (the fixed V2 version) for the second verdict above.
  Per explicit instruction, do not compress or modify.
- `comparison_metadata.json` -- reflects the fixed code (5 tracks, 589.2s).
- `v1_controlled.wav` / `v2_controlled.wav` + `comparison_b_controlled_metadata.json`
  -- comparison (B), controlled/fixed-order.
- `v1_baseline_diagnostics.json` / `v1_controlled_diagnostics.json` --
  `render_mix`'s own absolute-timeline diagnostics.
- `handoff_clips/V1_HANDOFF_00-02.wav`, `V2_HANDOFF_00-03.wav` -- per-handoff
  review clips, comparison (A) only, delivered to the user.
- `handoff_review_manifest.json` -- private review manifest, comparison (A)
  only, delivered to the user.
- `investigate_01_inspect_plans.py` / `investigate_01_v2.log`,
  `investigate_02_full_candidates.py` / `investigate_02_v2.log` --
  diagnostic scripts + fresh (post-fix) output.
- `build_review_package.py` / `render_comparison_b_controlled.py` /
  `render_comparison.py` -- throwaway scripts, self-contained,
  deterministic (seed=0), call only production functions.
All anonymous (`TRACK_NN` labels only); nothing here is referenced from any
tracked file.

## TESTS COMPLETED
- `tests/test_v2_phase7_set_director.py`: 18 passed (was 17).
- `tests/test_v2_phase5_candidate_composer.py`: 41 passed (was 40).
- Full repository regression: **1095 passed**, reverified immediately
  before this handoff update (clean, no flakes across two independent runs
  this investigation).
- Manually reproduced the pre-fix defect (monkeypatched exclusion check
  disabled) and confirmed it produces the old broken, unrenderable plan --
  proof the new regression tests catch a real defect, not a hypothetical.
- Reran both real 12-track comparisons (A and B) end-to-end through the
  fixed code, not just unit tests.
- **None of the above tests, or the full suite passing, are evidence the
  DJ-likeness gate is met.** The second human listen is the only test that
  actually measures the thing the project is for, and it did not pass.

## TESTS STILL REQUIRED
- No unit/regression test is missing for the four fixes already made.
- Not yet built: clips/manifest for comparison (B).
- The gate that matters is not a test the agent can write: a **third**
  human listen, after whatever the next agent does to address DJ-likeness
  directly, using the review package's clips/manifest to inspect specific
  handoffs alongside the user's specific complaint if they give one
  (e.g. "handoff 2 didn't feel like anything").

## KNOWN DEFECTS / OPEN QUESTIONS, NOW RE-PRIORITIZED BY THE SECOND LISTEN

1. **Technique labels vs. actual DSP** (was priority 2, now the leading
   suspect given the second listen's exact wording). `riser_impact` and
   `loop_shortening` compile to plain `crossfade`. If the next agent
   changes only one thing, understanding and fixing this mapping --
   whether by giving these families (and any others found to be similarly
   thin) real distinct DSP treatment, or by having Audition Lab/Set
   Director weight genuinely-differentiated techniques higher when
   candidates are otherwise close -- is the most directly evidenced lever
   for the user's actual complaint.
2. **Cross-edge anchor consistency** (unchanged from first round). A
   track's entry (as target of one handoff) and its own exit (as source of
   the next) are chosen independently -- no shared notion of "this track's
   one coherent appearance in the set." `anchor_shift_sec` (D044) papers
   over the resulting conflicts at render time rather than the plan
   avoiding them; this is very plausibly part of why staging/anticipation
   ("DJ-style anticipation of the NEXT handoff while the current track is
   playing," explicitly named in the user's priority list below) doesn't
   come through -- the system isn't planning a track's single coherent
   appearance, so it can't obviously anticipate handing it off well.
   **Designed, not implemented**: extend `compose_transition_candidates`
   with an optional `minimum_source_time_sec: float = 0.0` parameter
   (backward compatible, default preserves all existing Phase 5 tests);
   `_choose_anchor`'s source-anchor cue filter would additionally exclude
   any cue with `time_sec < minimum_source_time_sec`; Set Director's beam
   loop threads through the previous edge's real target-consumption end.
   Not attempted -- would touch a heavily-tested, otherwise-frozen Phase 5
   module.
3. **Short-technique dominance** (spec section 34's duration-variety
   clause): even with fully fair auditing, the short 4-bar families keep
   winning on these real pairs; `eq_blend`/`filter_blend` (longer, more
   substantial treatments) lose on score, not on unfair exclusion.
4. **No creativity-budget system** (spec section 35) -- confirmed absent.
5. Carried over, unchanged, still true: two vocal-heavy difficult-pair
   categories in the Phase 10 transition benchmark produced zero surviving
   candidates even when every generated candidate was fully audited; no
   minimal-risk guaranteed-feasible fallback family exists.

## DECISIONS MADE THIS INVESTIGATION
Not yet written to `DECISIONS.md` as lettered D-entries. If continuing,
consider adding D046-D049 for the four fixes (family-diverse audit
ordering, unrenderable-edge exclusion, anchor position-weighting,
real-anchor duration bookkeeping), matching the project's existing
convention (D044/D045 cover the Phase 10 anchor-shift/lock-refusal
decisions).

## DO NOT REDO
- Do not re-investigate whether the four fixed defects (audit budget/
  ordering, unrenderable-edge exclusion, anchor position weighting,
  duration bookkeeping) are real -- confirmed, fixed, tested, proven via
  rerender. Re-litigating wastes effort already spent.
- Do not treat those four fixes as having solved, or made significant
  progress toward, DJ-likeness -- the second listen is explicit that they
  did not. They fixed real defects and are worth keeping; they are not
  the answer to the actual product question.
- Do not casually retune `AuditionConfig.weights` or
  `vocal_heavy_threshold` (0.55) without new evidence -- checked directly
  against real handoff data; the rejections they cause
  (`vocal_overlap_too_dense`, `weak_or_non_downbeat_phrase_anchor`,
  `target_drop_not_strong`) are musically legitimate for the audio
  inspected, not miscalibration.
- Do not compress or otherwise modify `v1_baseline.wav` / `v2_current.wav`
  unless the user asks.
- Do not start Phase 8 UI, Phase 9/10 follow-on work, or any new roadmap
  phase. Performance quality is the only thing to work on.
- Do not attempt to fix DJ-likeness by making effects louder, more
  frequent, or more extreme -- explicit user instruction: "the goal is
  intentional DJ performance, not flashy effects." A louder riser is not a
  more intentional one.

## EXACT NEXT ACTION (for the next agent -- GPT-5.6 Sol)
The user's stated top priority, verbatim in intent: **make V2 audibly and
behaviorally DJ-like.** Investigate the full pipeline end to end -- Set
Director -> track appearance/anchors -> Candidate Composer -> Audition Lab
-> PerformanceRecipe -> technique compiler -> PerformanceTransition ->
renderer -> final mastering -- to determine why sophisticated decisions
are producing only small audible differences. Areas the user explicitly
named as focus points (not a checklist to mechanically complete, a set of
leads):
- technique-specific DSP actually reaching the output (start here --
  directly evidenced, see finding #1 above);
- cross-edge appearance planning (finding #2 above);
- stronger but musically appropriate technique execution;
- meaningful buildup/release;
- bass ownership;
- loops that sound intentional;
- stem usage;
- drop swaps; phrase cuts; echo releases; drum/percussion bridges;
  riser/impact staging;
- transitions that differ meaningfully in sound and structure (not just
  label);
- enough time for tracks to establish themselves before handing off;
- DJ-style anticipation of the next handoff while the current track plays;
- avoiding conservative Audition Lab selection that reduces everything
  toward a safe crossfade.

Use the private review package (clips + manifest under
`/tmp/djenius_v1_v2_listening/`) to inspect real handoff data rather than
re-deriving it from scratch. Do not start with UI polish or a broad new
feature phase. Do not make the fix be "louder/flashier FX."

## SAFE RECOVERY NOTES
- The four fixes (`89bfda5`) and both handoff-doc updates are committed
  and pushed; this is a clean, buildable checkpoint. Confirm via
  `git fetch && git log -1 --format='%H %s'` and
  `git rev-parse origin/v2-professional-autonomous-dj`, then
  `python -m pytest -q` for the 1095-test regression.
- The private `/tmp/djenius_v1_v2_listening/` tree is not reproducible by
  `git checkout`. If lost, the scripts listed under "PRIVATE LOCAL
  ARTIFACTS" are self-contained/deterministic (seed=0) and regenerate
  everything except the pre-fix (first-listen) comparison numbers, which
  exist only as text in this file and the session transcripts.
- If the next agent is tempted to declare victory after another fix: it
  needs a **third** real human listen before claiming the gate is met. Two
  rounds of "we found and fixed real defects" have already not been
  enough; do not repeat the pattern of assuming a plausible-sounding fix
  closes the gate without the user confirming by ear.
