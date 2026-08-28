# Contributing to DJenius

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/danielnrz/DJenius.git
   cd DJenius
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. Verify your setup:
   ```bash
   djenius doctor
   ```

## Running Tests

```bash
pytest tests/ -v
```

With coverage:

```bash
pytest tests/ -v --cov=djenius --cov-report=term-missing
```

## Project Structure

- `djenius/core/` - Models, scoring algorithms, set planning
- `djenius/audio/` - Audio analysis, transitions, rendering, library scanning
- `djenius/db/` - SQLite cache and file fingerprinting
- `djenius/utils/` - Key detection, audio math utilities
- `djenius/cli.py` - Typer CLI interface
- `tests/` - Automated test suite

## Guidelines

- Keep commits focused and well-described
- Run `pytest` before pushing
- Follow existing code style (type hints, docstrings)
- Do not commit audio files, cache databases, or test music
- All contributions should be your own work
