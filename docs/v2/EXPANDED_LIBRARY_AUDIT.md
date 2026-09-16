# Expanded private-library and blind-context audit

This is a public-safe summary of a private, evidence-building checkpoint. It
does not modify F/C3/B8/D2, renderer behavior, production context thresholds,
or Set Director; no Pilot 5 or new creative audio was made.

## Blind context labels, revealed only after collection

The 12 listener labels were stored verbatim before the hidden pair mapping was
opened. The four labels remain distinct; `UNCERTAIN` is neither positive nor
negative. Private mapping and reasons are in
`/tmp/djenius_reference_dj_transition/expanded_library/CTX_LABEL_REVEAL.json`.

| Blind case | Provenance | Human label | Prior-anchor check |
| --- | --- | --- | --- |
| CTX_01 | new informative | BRIDGEABLE | — |
| CTX_02 | hidden context-negative anchor | MISMATCH | agrees |
| CTX_03 | new informative | BRIDGEABLE | — |
| CTX_04 | Pilot 4 transition 4 | UNCERTAIN | — |
| CTX_05 | new informative | BRIDGEABLE | — |
| CTX_06 | new informative | BRIDGEABLE | — |
| CTX_07 | new informative | MISMATCH | — |
| CTX_08 | Pilot 4 transition 2 | BRIDGEABLE | — |
| CTX_09 | Pilot 4 transition 3 | BRIDGEABLE | — |
| CTX_10 | new informative | MISMATCH | — |
| CTX_11 | Pilot 4 transition 1 | UNCERTAIN | — |
| CTX_12 | hidden context-positive anchor | UNCERTAIN | inconclusive retest |

Thus Pilot 4's four directed adjacencies are `UNCERTAIN`, `BRIDGEABLE`,
`BRIDGEABLE`, `UNCERTAIN` in set order. The earlier leading suspicion about
transition 4 is **not confirmed as a pair-level mismatch**. Production had
called all four `NATURAL_CONTINUATION`; the two middle labels suggest that
its natural-versus-bridgeable description may be too confident, but the
uncertain edges and anchor retest do not support a new gate threshold.
Two `MISMATCH` reasons explicitly cited rhythm and one cited tonal character;
one `BRIDGEABLE` reason described a sad-to-happy contrast as potentially
intentional. The labels therefore argue against either an energy-only rule
or an automatic same-mood requirement.

## Data separation and intake

The private root has 175 top-level audio files, all with supported extensions
and decodable audio streams (162 MP3, six M4A, five FLAC, two WAV). Two WAVs
are synthetic fixtures, leaving 173 real
recordings. A separate 35-file `fromDJ/` subtree is reference material and is
excluded from ordinary recursive song scanning by default. Directly scanning
the reference directory is still possible for shadow research. A real-root
scan returned 175 top-level files, zero `fromDJ/` leaks, and an explicit
reference-only scan returned 35 files. Focused tests protect this boundary.

Fifteen of the 173 real top-level recordings exceed ten minutes and include
long-form mix, podcast, concert, playlist, or extended-work candidates. The
normal single-song analyzer loads and separates entire tracks, so blindly
processing a 73-minute concert caused heavy swapping. These 15 are classified
`LONG_FORM_OR_EXTENDED_AUDIO_NEEDS_SONG_ROLE_REVIEW`; the graph audit is
explicitly limited to the remaining 158 ordinary-length candidate-song
files. This is a private batch/content-role decision, **not a new production
duration gate** or a claim that every long composition is unusable. No files
were moved or altered. One long-form file already had a valid analysis cache;
one more received one before the resume-safe job was stopped. Those caches
are preserved but do not make the files ordinary songs.

At initial inventory, 15/173 real recordings had valid version-6 acoustic
analysis, including 14/158 ordinary-length candidates. There were no exact
content-hash duplicate groups or same-normalized-title duplicate groups;
one copy-number filename family with differing durations is a *possible*,
unconfirmed alternate version. Other versions with unrelated naming cannot
be ruled out by those checks.
Only missing/stale ordinary-length entries are analyzed. Existing version-2
CLAP profiles are reused only when model/version and content hash match;
otherwise the already-installed local model fills the cache. No new model was
downloaded or adopted.

The bounded batch finished with **158/158** valid acoustic and **158/158**
matching local CLAP profiles. The ordinary-length acoustic analysis reused 14
existing entries and filled 144 misses; matching semantic profiles were reused
when valid and computed otherwise. All 158 source hashes were unchanged and
no `fromDJ/` file entered the analysis cache.

One real MP3 had a malformed duration header: SoundFile reported about 5:38,
while ffmpeg decoded about 3:28. A representative CLAP window had landed
past EOF. The compressed-audio duration probe now prefers ffprobe with the
prior decoder fallback; a focused test and successful cache round-trip protect
this narrow ingestion fix. It does not alter context inference or thresholds.

## Expanded graph

The unchanged selector and joint set-flow stack evaluated all **24,806**
directed non-self pairs among the 158 bounded single-song candidates. It
rendered no audio. An edge passes when at least one declared set phase has a
valid joint decision. Explicit human-negative ordered-pair history is then a
separate veto:

| Audit | Usable before human-negative veto | Usable after veto | Density after veto |
| --- | ---: | ---: | ---: |
| Prior 14-track bounded audit | 31 / 182 | 30 / 182 | 16.48% |
| Expanded 158-track audit | 2,097 / 24,806 | **2,094 / 24,806** | **8.44%** |

Twelve ordered human-negative pairs are represented in the expanded pool;
three would otherwise pass current production rules. The original 14 tracks
have 36 usable edges when *recalibrated as part of the expanded pool*, versus
30 in the original 14-track-only calibration. This is a data-dependent
calibration comparison, not evidence that a code threshold was changed or
that six new choices are listener-approved.

There is a 130-track weakly connected component and 28 isolated tracks.
The largest strongly connected component has 56 tracks; 50 tracks have zero
outgoing edges and 75 have zero incoming edges. The exact number of simple
four-track paths is 552,227. A capped enumeration found **at least 1,870,257**
five-track static paths; this is a lower bound, not the total. A separate
plan-only replay under actual recent-history and establishment constraints
found a valid five-track path in ten candidate evaluations. That is a
*feasibility proof*, not a rendered or human-approved Pilot 5, nor a claim
that this particular path is the strongest musical story.

Of the 2,094 usable edges, F covers 1,968, D2 75, C3 41, and B8 18; seven
edges have more than one available archetype. Thus the graph is connected
enough to plan, but its apparent coverage is highly F-dependent. Across
usable edges, 614 have a natural-continuation option and 1,480 have an
intentional-bridgeable-contrast option. The primary rejection stage is
performance/cue acceptance for 20,778 edges and context or set-flow for
1,931; three more pass the rules but are vetoed by human-negative history.
Co-occurring evidence most often cites no eligible cue combination, weak
target establishment, or unclean source launch. Counts are descriptive,
not a basis for loosening gates.

The new blind labels reveal a remaining context problem despite this
connectivity. Two of the three `MISMATCH` auditions would have been accepted
by current production rules without their explicit human-history veto;
the third was already rejected. Several `BRIDGEABLE` auditions were called
`NATURAL_CONTINUATION`. These are diagnostic contradictions, not sufficient
evidence for a new threshold. The expanded choice set substantially resolves
*planning scarcity*, but it does not yet prove better set-level musical
judgment. A five-track path made solely of technically valid edges could
still sound contextually wrong.

## Library shape and limits

Among the 158 cached single-song candidates, BPM spans 76–172.3 (median
121.6); 104 lie in the 100–140 range. Mean-energy median is 0.727, with
10th–90th percentile 0.551–0.825. The existing interpretable rhythmic
proxy distributes 40 straight-driving, 42 swung, 29 compound/half-time
candidates, 22 mixed, 14 fast/double-time candidates, and 11 syncopated.
Its dance-function proxy yields 70 driving-dance, 49 rhythmic-song, and 39
atmospheric/sparse. These are analyzer descriptions, not certified meter or
genre labels.

Key estimates and their confidence are recorded privately; only 66/158
meet the descriptive 0.8 confidence cut, and harmonic decisions remain
subject to the existing production evidence gates. Relative CLAP style
scores most often put “pop” first, but only 43/158 clear the existing
style-reliability floor and **zero** have reliable semantic mood evidence.
They must not be treated as ground-truth genre/affect. Mutual top-three
CLAP neighborhoods include one 35-track group and many small groups or
singletons; 16 tracks are in the bottom decile of nearest-neighbor similarity.
The private inventory lists their indexes for later inspection. These
neighborhoods and the 28 transition-graph isolates expose coverage diversity
without pretending semantic clusters are human-confirmed musical worlds.

The next experiment should test *musical-context judgments on selected
expanded-library edges* before rendering another set: blind context-only
auditions spanning graph-usable natural/bridgeable edges, including F-heavy
and non-F coverage, plus rejected near-boundary controls. The two new
false-accepted mismatches make this more informative than simply producing
Pilot 5 from the now-connected graph. Keep existing transitions and gates
frozen while that evidence is collected.

Private detailed artifacts remain under
`/tmp/djenius_reference_dj_transition/expanded_library/`; no private audio,
track title, artist, or path is committed.
