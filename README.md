# DJenius

A fully local personal smart DJ application that analyzes your music library, plans DJ sets with intelligent transitions, and renders continuous DJ-style mixes.

## Features

- **Library Scanning** - Index your local music collection with metadata extraction
- **Audio Analysis** - BPM detection, key detection (Camelot notation), loudness (LUFS), energy profiling, phrase detection
- **Set Planning** - Beam-search optimization for track ordering with compatibility scoring
- **Transition Selection** - Intelligent transition type selection (crossfade, phrase cut, EQ swap, beatmatched blend, etc.)
- **Mix Rendering** - Continuous DJ mix output with LUFS normalization
- **Caching** - SQLite-backed analysis cache with file fingerprinting

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

The app keeps its local analysis cache, preferences, app state, and optional
stem cache under `data/`; rendered audio is written under `output/`. These
paths are ignored by Git and are never uploaded anywhere.

Use `djenius serve --port 9000` to choose another local port. The server binds
to localhost by default.

Optional local tools:

- **Demucs** enables advanced stem transitions when explicitly selected.
- **Ollama** enables optional local LLM request interpretation; deterministic
  parsing remains the default.
- **FFmpeg** is used for decoding formats that SoundFile cannot read.

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
