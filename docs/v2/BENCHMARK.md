# DJenius V2 Benchmark

## V1 frozen baseline
- Commit: `efcfcca6d21aeaa595b236306b025b70668106fd`
- Full test suite: **846 passed in 17.96s**
- Doctor: all critical checks PASS
- Current cached V1 analyses: 17 tracks (analysis version 5)

## Existing-plan aggregate
A local aggregate scan of saved ignored plan artifacts found 18 plans and 87 classic transition records:

| Transition family | Count | Share |
|---|---:|---:|
| filter_sweep | 26 | 29.9% |
| phrase_cut | 23 | 26.4% |
| beatmatched_blend | 19 | 21.8% |
| bass_swap | 9 | 10.3% |
| loop_blend | 4 | 4.6% |
| crossfade | 3 | 3.4% |
| echo_out | 3 | 3.4% |

This is not a perceptual quality score, but it establishes a reproducible technique-diversity baseline and confirms concentration in a small set of safe families.

## Existing saved-plan trajectory evidence
- BPM: 95.7 / 119.52 / 136.0 min/mean/max across 103 saved track appearances.
- Mean energy: 0.698 / 0.745 / 0.836 min/mean/max across 103 saved track appearances.
- Unique Camelot labels: 10.

## Reused local V1 listening references
Existing ignored local WAVs include smooth and energetic certification/user mixes. Their audio remains local and is not listed with private track metadata in Git.

## V2 measurements
Phase 1 measurements will be appended after targeted, full-regression and private real-track validation.

## Final certification requirement
The release benchmark will include planned-vs-shuffled set metrics, technique diversity, audition ranking, private difficult-pair tests, multiple complete V2 sets, and blind V1-vs-V2 human listening. Automated metrics alone cannot release V2.

## Phase 1 - Analysis V2 gate
- V2 analysis schema: `2.0`; cache analysis version: 6.
- New targeted/synthetic tests: 10; targeted bundle with legacy model/phrasing tests re-verified at **65 passed in 0.86s**.
- Full regression re-verification: **856 passed in 17.95s**.
- Private real-track validation (3 tracks, anonymized): BPM confidence mean 0.981; beat counts 195/361/423; sustained tempo-zone counts after refinement 2/1/1; phrase profile counts 5/5/8; section profile counts 6/6/9; cue counts 6/6/9; groove-confidence values 1.0/1.0/1.0; cached stem activity profiles 4/4/4.
- The initial tempo-zone implementation produced 5/12/6 zones on the same tracks and was rejected as too jitter-sensitive before the phase gate.
- Privacy check: no testMusic, generated audio, stems, data caches, or private song names in the tracked Phase 1 change set.

## Phase 2 - Performance Recipe DSL gate
- New Phase 2 tests: **32 passed**.
- Related performance/renderer targeted bundle: **75 passed in 2.06s**.
- Complete regression: **888 passed in 15.83s** (Phase 1 baseline: 856).
- Five proof recipes serialize deterministically and compile into the existing renderer contract: EQ blend -> beatmatched blend, bass swap -> bass swap, phrase cut -> phrase cut, loop transition -> loop blend, echo release -> echo out.
- All five proof recipes rendered synthetic stereo audio successfully with clean provenance.
- Beatmatched compilation explicitly records time-stretch need and target-source consumption when BPMs differ.
- Recipe/action IDs are deterministic content hashes; round-trip serialization preserves identity and payload exactly.
- Privacy check: no testMusic, generated audio, stems, caches, or private song names entered the tracked Phase 2 change set.
