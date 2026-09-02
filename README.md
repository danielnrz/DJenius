# DJenius

A fully local personal smart DJ application that analyzes your music library, plans DJ sets with intelligent transitions, and renders continuous DJ-style mixes.

## Features

- **Library Scanning** - Index your local music collection with metadata extraction
- **Audio Analysis** - BPM detection, key detection (Camelot notation), loudness (LUFS), energy profiling, phrase detection
- **Set Planning** - Beam-search optimization for track ordering with compatibility scoring
- **Transition Selection** - Intelligent transition type selection (crossfade, phrase cut, EQ swap, beatmatched blend, etc.)
- **Mix Rendering** - Continuous DJ mix output with LUFS normalization
- **Caching** - SQLite-backed analysis cache with file fingerprinting
- **Musical Feeling** - Optional local CLAP audio-text analysis for mood, activity, intensity, and broad style cues. Analysis samples representative windows across the track, stores window evidence, and leaves weak labels uncertain.
- **Lyrics and Meaning** - Optional local lyrics extraction, multilingual Whisper-family transcription, and validated local Ollama song-meaning estimates.
- **Intent-first selection** - Requests rank tracks for lyrical meaning and audio feeling before the safe technical planner orders transitions. Unknown evidence is labeled as fallback, reliable contradictions are excluded only when the request makes that explicit, and shorter coherent sets are preferred to unrelated padding.
- **Recoverable meaning analysis** - Transcript acquisition and meaning interpretation are cached as separate stages. Missing, stale, invalid, or failed meaning can be retried without retranscribing a valid local transcript.
- **Human corrections** - The Library view can save local theme, lyrical-mood, and audio-character corrections. Corrections overlay automatic evidence for this library without overwriting the raw model result.
- **Segment performance** - Short quick/club mixes can compose phrase-aligned musical appearances, return to a track using a different source region, and render an explicit audited performance timeline. Classic long-form planning remains the default for relaxed sets.

## Requirements

- Python 3.11+
- FFmpeg (for audio I/O)
- Rubberband CLI (for time-stretching, optional but recommended)

## Installation

```bash
git clone https://github.com/danielnrz/DJenius.git
cd DJenius
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

To enable local semantic analysis (downloads the CLAP model on the first
explicit semantic-analysis run), install the optional extra:

```bash
pip install -e ".[semantic]"
```

To enable optional local transcription and song-meaning analysis:

```bash
pip install -e ".[lyrics]"
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

### Local app

Launch the local DJenius interface:

```bash
djenius app
```

Then open `http://127.0.0.1:8765`. Enter a music folder, scan it, analyze any
missing tracks, and create a mix from a preset or a natural-language request.
Review and reorder the proposed set before rendering. Rendered WAV files and
the timeline markers appear in the Now Playing view.

In Create a mix, `Auto / Request decides` is the default. A free-form request
is the source of truth; a preset is used when no request is entered. The plan
shows the requested meaning, per-track match status, fallbacks, and intent
coverage so a small library is not silently padded with contradictory songs.

For a short performance, choose `Quick mix (adaptive handoffs)` or write
“quick mix” in the request. The plan shows each appearance, source
timestamps, section role, output time, intentional reprises, and the
pair-aware transition recipe. Handoffs use musical bar lengths and choose a
safe crossfade or beatmatched blend when a phrase cut is not justified. Every
source interval is checked before rendering. Choose `Classic long-form` for
the traditional one-pass track flow.

The app keeps its local analysis cache, preferences, app state, and optional
stem cache under `data/`; rendered audio is written under `output/`. These
paths are ignored by Git and are never uploaded anywhere.

Use `djenius serve --port 9000` to choose another local port. The server binds
to localhost by default.

Optional local tools:

- **Demucs** enables advanced stem transitions when explicitly selected.
- **Ollama** enables optional local LLM request interpretation; deterministic
  parsing remains the default. When enabled for a free-form request, the app
  sends that request to the configured local model and shows the parser source.
- **Semantic analysis** uses `laion/clap-htsat-unfused` locally through
  Transformers. It is an estimate, not ground truth: displayed values are
  relative model matches, not probabilities. It is cached by source file hash,
  model, and semantic analysis version. The model is loaded only by the
  explicit `Analyze musical feeling` action and released afterward. CUDA
  inference falls back to CPU if the local PyTorch/cuDNN installation is
  incompatible.
- **FFmpeg** is used for decoding formats that SoundFile cannot read.

- **Lyrics analysis** is explicit and optional. DJenius checks embedded lyrics,
  then local `.lrc` or `.txt` sidecars, and only then can use `faster-whisper`.
  Meaning interpretation stays on the configured local Ollama server. Lyrics
  are not downloaded or scraped. Singing is harder than speech, so low-confidence
  or repetitive transcriptions are rejected.

Audio feeling and lyrical meaning remain separate evidence in the cache and
planner. Missing lyrics never prevent standard analysis, planning, or rendering.

Song meaning status is reported separately from job completion: meaning-ready,
low-confidence, interpretation-failed, transcript-missing, unavailable, and
stale results remain distinguishable. The `Retry unresolved meaning` action
reuses valid transcripts whenever possible. All meaning data and corrections
stay in the local ignored `data/` directory.

## Future direction

The V9 performance layer is intentionally the first segment-based stage. A
future release can add richer mashup layering and live-style timeline editing
without changing deterministic source provenance or transition safety.

```bash
# Scan your music library
djenius scan /path/to/music

# Analyze tracks (BPM, key, energy, phrases)
djenius analyze /path/to/music

# Plan a 30-minute DJ set
djenius plan /path/to/music --duration 1800

# Render the mix
djenius mix output/set_plan.json --output output/my_mix.wav

# Check system health
djenius doctor
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `djenius scan` | Scan and index a music library |
| `djenius analyze` | Analyze tracks for BPM, key, energy, phrases |
| `djenius plan` | Plan a DJ set with intelligent track ordering |
| `djenius mix` | Render a planned set to an audio mix |
| `djenius info` | Show analysis cache information |
| `djenius doctor` | Check system dependencies and health |

## Supported Formats

MP3, FLAC, WAV, M4A, AAC, OGG, WMA, AIFF

## Architecture

DJenius uses a modular architecture with separation between the DJ "brain" (planning/scoring) and audio engine (DSP/rendering):

```
djenius/
  core/       # Models, scoring, set planning
  audio/      # Analysis, transitions, rendering, scanning
  db/         # SQLite caching
  utils/      # Key detection, audio math helpers
```

## License

MIT License - see [LICENSE](LICENSE) for details.
