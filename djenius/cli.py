"""DJenius CLI - Typer-based command interface."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich import box

from djenius import __version__

app = typer.Typer(
    name="djenius",
    help="DJenius - Your personal AI DJ.",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _get_cache(cache_path: str):
    """Create AnalysisCache, ensuring its directory exists."""
    from djenius.db.cache import AnalysisCache
    path = Path(cache_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return AnalysisCache(str(path))


def _serve_local(host: str, port: int):
    """Run the local web application."""
    try:
        import uvicorn
        from djenius.web.app import app as web_app
    except ImportError as exc:
        console.print("[red]Web app dependencies are missing. Install with 'pip install -e .'.[/]")
        raise typer.Exit(1) from exc
    console.print(f"[green]DJenius is running at http://{host}:{port}[/]")
    uvicorn.run(web_app, host=host, port=port, log_level="info")


@app.command(name="serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (localhost by default)"),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Local web port"),
):
    """Launch the local DJenius web application."""
    _serve_local(host, port)


@app.command(name="app")
def app_command(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (localhost by default)"),
    port: int = typer.Option(8765, "--port", min=1, max=65535, help="Local web port"),
):
    """Launch the local DJenius web application."""
    _serve_local(host, port)


@app.command()
def scan(
    library_path: str = typer.Argument(..., help="Path to music library"),
    cache_path: str = typer.Option(
        "data/analysis_cache.db", "--cache", "-c",
        help="Path to SQLite cache database"
    ),
    recursive: bool = typer.Option(True, "--recursive/--flat", help="Scan subdirectories"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Scan a music library directory and index tracks."""
    _setup_logging(verbose)

    lib_path = Path(library_path).expanduser().resolve()
    if not lib_path.exists():
        console.print(f"[red]Error:[/] Directory not found: {lib_path}")
        raise typer.Exit(1)

    console.print(Panel(f"[bold]Scanning Library[/]\n{lib_path}", border_style="blue"))

    from djenius.audio.scanner import scan_directory

    cache = _get_cache(cache_path)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning...", total=None)

        tracks = scan_directory(
            str(lib_path),
            recursive=recursive,
        )
        progress.update(task, completed=len(tracks), total=len(tracks))

    console.print(f"\n[green]Found {len(tracks)} tracks[/]\n")

    # Show summary
    table = Table(title="Library Summary", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    total_duration = sum(t.duration_sec for t in tracks)
    table.add_row("Total Tracks", str(len(tracks)))
    table.add_row("Total Duration", _format_duration(total_duration))

    # Format breakdown
    formats = {}
    for t in tracks:
        ext = Path(t.filepath).suffix.lower()
        formats[ext] = formats.get(ext, 0) + 1
    for ext, count in sorted(formats.items()):
        table.add_row(f"Format: {ext}", str(count))

    # Total file size
    total_size = sum(
        Path(t.filepath).stat().st_size for t in tracks
        if Path(t.filepath).exists()
    )
    table.add_row("Total Size", f"{total_size / (1024*1024):.1f} MB")

    console.print(table)

    # Cache info
    cached = cache.count()
    console.print(f"\n[dim]Cache: {cached} tracks analyzed and cached[/]")


@app.command()
def analyze(
    library_path: str = typer.Argument(..., help="Path to music library"),
    cache_path: str = typer.Option(
        "data/analysis_cache.db", "--cache", "-c",
        help="Path to SQLite cache database"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Re-analyze cached tracks"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Analyze tracks in the library (BPM, key, energy, phrases)."""
    _setup_logging(verbose)

    lib_path = Path(library_path).expanduser().resolve()
    if not lib_path.exists():
        console.print(f"[red]Error:[/] Directory not found: {lib_path}")
        raise typer.Exit(1)

    console.print(Panel(f"[bold]Analyzing Library[/]\n{lib_path}", border_style="blue"))

    from djenius.audio.scanner import scan_directory
    from djenius.audio.analyzer import analyze_track

    cache = _get_cache(cache_path)

    # Scan first
    tracks = scan_directory(str(lib_path))
    console.print(f"Found {len(tracks)} tracks\n")

    analyzed = 0
    skipped = 0
    failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing...", total=len(tracks))

        for track in tracks:
            if not force and cache.has(track.filepath):
                skipped += 1
                progress.advance(task)
                continue

            try:
                profile = analyze_track(track.filepath, force=force, cache=cache)
                analyzed += 1
            except Exception as e:
                logging.getLogger(__name__).warning("Failed to analyze %s: %s", track.title, e)
                failed += 1

            progress.advance(task)

    console.print(f"\n[green]Analysis complete:[/]")
    console.print(f"  Analyzed: {analyzed}")
    console.print(f"  Skipped (cached): {skipped}")
    console.print(f"  Failed: {failed}")

    # Show some analysis results
    if analyzed > 0:
        console.print("\n[bold]Sample Analysis Results:[/]")
        table = Table(box=box.SIMPLE)
        table.add_column("Track", style="cyan", max_width=30)
        table.add_column("BPM", justify="right")
        table.add_column("Key", justify="center")
        table.add_column("LUFS", justify="right")
        table.add_column("Energy", justify="right")

        for track in tracks[:10]:
            profile = cache.get(track.filepath)
            if profile:
                table.add_row(
                    track.title or Path(track.filepath).stem,
                    f"{profile.bpm:.1f}" if profile.bpm else "—",
                    profile.camelot or "—",
                    f"{profile.analysis.integrated_lufs:.1f}" if profile.analysis else "—",
                    f"{profile.mean_energy:.2f}" if profile.mean_energy else "—",
                )

        console.print(table)


@app.command()
def plan(
    library_path: str = typer.Argument(..., help="Path to music library"),
    output: str = typer.Option(
        "output/set_plan.json", "--output", "-o",
        help="Output path for the set plan JSON"
    ),
    duration: float = typer.Option(1800.0, "--duration", "-d", help="Target duration in seconds"),
    energy: str = typer.Option(
        "steady", "--energy", "-e",
        help="Energy profile: steady, slow_build, warmup_to_peak, wave, peak_early, peak_late, cooldown"
    ),
    cache_path: str = typer.Option(
        "data/analysis_cache.db", "--cache", "-c",
        help="Path to SQLite cache database"
    ),
    max_tracks: Optional[int] = typer.Option(None, "--max-tracks", help="Maximum tracks"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed"),
    request: Optional[str] = typer.Option(
        None, "--request", "-r",
        help="Natural language description of desired set (e.g. 'chill mix 30 min')"
    ),
    preset: Optional[str] = typer.Option(
        None, "--preset", "-p",
        help="Preset name: chill, smooth, balanced, energetic, peak, late_night, vocal_safe, experimental"
    ),
    use_llm: bool = typer.Option(
        False, "--use-llm/--no-llm",
        help="Use Ollama LLM for advanced intent parsing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Plan a DJ set from the analyzed library.

    Supports natural language requests via --request, e.g.:
        djenius plan library --request "smooth 30 min set with no vocal clash"
        djenius plan library --preset chill --duration 2400
    """
    _setup_logging(verbose)

    from djenius.core.models import EnergyProfile
    from djenius.core.planner import plan_set
    from djenius.core.intent import make_intent
    from djenius.core.nl_parser import parse_request
    from djenius.audio.analyzer import analyze_track
    from djenius.audio.scanner import scan_directory

    lib_path = Path(library_path).expanduser().resolve()
    cache = _get_cache(cache_path)

    # Build intent from request/preset or legacy flags
    intent = None
    effective_energy = energy
    effective_duration = duration

    if request:
        intent = parse_request(request, use_llm=use_llm)
        console.print(Panel(
            f"[bold]Planning DJ Set[/]\n"
            f"Request: {request}\n"
            f"Parsed intent: preset={intent.preset}, energy={intent.energy_profile.value if intent.energy_profile else 'auto'}, "
            f"transition={intent.transition_style}, duration={intent.target_duration_sec:.0f}s",
            border_style="blue",
        ))
        # Use intent-derived values
        if intent.target_duration_sec:
            effective_duration = intent.target_duration_sec
    elif preset:
        intent = make_intent(preset)
        console.print(Panel(
            f"[bold]Planning DJ Set[/]\n"
            f"Preset: {preset}",
            border_style="blue",
        ))
        if intent.target_duration_sec:
            effective_duration = intent.target_duration_sec
    else:
        console.print(Panel("[bold]Planning DJ Set[/]", border_style="blue"))

    # Scan and analyze
    tracks = scan_directory(str(lib_path))
    console.print(f"Found {len(tracks)} tracks")

    # Analyze all tracks
    profiles = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing...", total=len(tracks))
        for track in tracks:
            try:
                profile = analyze_track(track.filepath, cache=cache)
                profiles.append(profile)
            except Exception as e:
                logging.getLogger(__name__).warning("Skipping %s: %s", track.title, e)
            progress.advance(task)

    console.print(f"Analyzed {len(profiles)} tracks")

    if len(profiles) < 2:
        console.print("[red]Error:[/] Need at least 2 tracks to plan a set")
        raise typer.Exit(1)

    # Parse energy profile (legacy mode)
    ep = None
    if not intent or not intent.energy_profile:
        try:
            ep = EnergyProfile(effective_energy)
        except ValueError:
            console.print(f"[red]Error:[/] Invalid energy profile: {effective_energy}")
            console.print(f"Valid options: {[e.value for e in EnergyProfile]}")
            raise typer.Exit(1)

    # Get preference bonuses if available
    preference_bonuses = None
    try:
        from djenius.db.preferences import PreferenceProfile
        prefs = PreferenceProfile.default()
        preference_bonuses = prefs.get_scoring_bonuses()
    except Exception:
        pass

    # Plan
    console.print(f"\nPlanning with target duration {_format_duration(effective_duration)}...")

    set_plan = plan_set(
        tracks=profiles,
        target_duration_sec=effective_duration,
        energy_profile=ep,
        max_tracks=max_tracks,
        seed=seed,
        intent=intent,
        preference_bonuses=preference_bonuses,
    )

    # Display results
    console.print(f"\n[green]Set planned:[/]")
    table = Table(title="DJ Set Plan", box=box.ROUNDED)
    table.add_column("#", style="dim", width=3)
    table.add_column("Track", style="cyan", max_width=35)
    table.add_column("BPM", justify="right")
    table.add_column("Key")
    table.add_column("Duration", justify="right")
    table.add_column("Transition", style="yellow")

    for i, track in enumerate(set_plan.tracks):
        transition_info = ""
        if i < len(set_plan.transitions):
            t = set_plan.transitions[i]
            transition_info = f"{t.transition_type.value}\n({t.overlap_duration:.1f}s overlap)"

        table.add_row(
            str(i + 1),
            track.title,
            f"{track.bpm:.1f}" if track.bpm else "—",
            track.camelot or "—",
            _format_duration(track.duration_sec),
            transition_info,
        )

    console.print(table)

    console.print(f"\n[bold]Set Stats:[/]")
    console.print(f"  Total tracks: {len(set_plan.tracks)}")
    console.print(f"  Duration: {_format_duration(set_plan.total_duration_sec)}")
    console.print(f"  Target duration: {_format_duration(set_plan.target_duration_sec)}")
    console.print(f"  Avg transition confidence: {set_plan.avg_transition_confidence:.0%}")
    console.print(f"  Overall score: {set_plan.score:.2f}")

    # Show explanations if available
    if set_plan.human_readable_reasons:
        console.print(f"\n[bold]Plan Explanations:[/]")
        for reason in set_plan.human_readable_reasons:
            console.print(f"  - {reason}")

    # Save plan
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plan_dict = set_plan.to_dict()
    with open(output_path, "w") as f:
        json.dump(plan_dict, f, indent=2, default=str)

    console.print(f"\n[dim]Plan saved to {output_path}[/]")


@app.command()
def mix(
    plan_path: str = typer.Argument(..., help="Path to set plan JSON"),
    output: str = typer.Option(
        "output/mix.wav", "--output", "-o",
        help="Output audio file path"
    ),
    output_format: str = typer.Option(
        "wav", "--format", "-f",
        help="Output format: wav or mp3"
    ),
    target_lufs: float = typer.Option(-14.0, "--lufs", help="Target loudness in LUFS"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Render a planned set to an audio mix."""
    _setup_logging(verbose)

    from djenius.core.models import SetPlan
    from djenius.audio.renderer import render_mix

    plan_file = Path(plan_path)
    if not plan_file.exists():
        console.print(f"[red]Error:[/] Plan file not found: {plan_file}")
        raise typer.Exit(1)

    console.print(Panel("[bold]Rendering DJ Mix[/]", border_style="blue"))

    # Load plan
    with open(plan_file) as f:
        plan_dict = json.load(f)

    plan = SetPlan.from_dict(plan_dict)
    console.print(f"Loaded plan with {len(plan.tracks)} tracks")

    # Render
    console.print(f"\nRendering to {output} ({output_format}, {target_lufs} LUFS)...")

    result = render_mix(
        plan=plan,
        output_path=output,
        output_format=output_format,
        target_lufs=target_lufs,
        progress_callback=lambda p, m: None,  # Suppress during CLI render
    )

    # Display results
    console.print(f"\n[green]Mix rendered successfully![/]")
    table = Table(box=box.ROUNDED)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Output", result["output_path"])
    table.add_row("Duration", _format_duration(result["duration_sec"]))
    table.add_row("Format", f"{result['format'].upper()}, {result['channels']}ch, {result['sample_rate']}Hz")
    table.add_row("Peak", f"{result['peak_db']:.1f} dB")
    if result.get("final_lufs") is not None:
        table.add_row("LUFS", f"{result['final_lufs']}")
    table.add_row("Transitions", str(result["transitions_rendered"]))
    table.add_row("Render time", _format_duration(result["render_time_sec"]))
    table.add_row("File size", f"{result['file_size_mb']} MB")

    console.print(table)

    if result.get("diagnostics"):
        console.print("\n[bold]Transition Details:[/]")
        diag_table = Table(box=box.SIMPLE)
        diag_table.add_column("From", style="cyan")
        diag_table.add_column("To", style="cyan")
        diag_table.add_column("Type", style="yellow")
        diag_table.add_column("Overlap", justify="right")
        diag_table.add_column("Confidence", justify="right")

        for d in result["diagnostics"]:
            diag_table.add_row(
                d["from"][:25],
                d["to"][:25],
                d["type"],
                f"{d['overlap_sec']:.1f}s",
                f"{d['confidence']:.0%}",
            )

        console.print(diag_table)


@app.command()
def info(
    library_path: str = typer.Argument(..., help="Path to music library"),
    cache_path: str = typer.Option(
        "data/analysis_cache.db", "--cache", "-c",
        help="Path to SQLite cache database"
    ),
):
    """Show analysis cache information."""
    cache = _get_cache(cache_path)

    table = Table(title="Analysis Cache", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    count = cache.count()
    table.add_row("Cached Tracks", str(count))

    if count > 0:
        # Show some cached entries
        console.print(table)
        console.print("\n[bold]Cached Entries:[/]")
        profiles = cache.get_all_profiles()
        entry_table = Table(box=box.SIMPLE)
        entry_table.add_column("Track", style="cyan", max_width=35)
        entry_table.add_column("BPM", justify="right")
        entry_table.add_column("Key")
        entry_table.add_column("LUFS", justify="right")

        for p in profiles[:20]:
            entry_table.add_row(
                p.title[:35],
                f"{p.bpm:.1f}" if p.bpm else "—",
                p.camelot or "—",
                f"{p.analysis.integrated_lufs:.1f}" if p.analysis else "—",
            )

        console.print(entry_table)
    else:
        console.print(table)
        console.print("[dim]No tracks analyzed yet. Run 'djenius analyze' first.[/]")


def _format_duration(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    if seconds < 0:
        return "—"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


@app.command()
def doctor():
    """Check system health and dependencies."""
    import shutil
    import sys

    checks: list[tuple[str, bool, str]] = []

    # Python version
    py_ok = sys.version_info >= (3, 11)
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python >= 3.11", py_ok, py_ver))

    # Core dependencies
    core_deps = [
        "librosa", "numpy", "scipy", "soundfile",
        "pyloudnorm", "pyrubberband", "xxhash", "mutagen",
        "typer", "rich",
    ]
    for dep in core_deps:
        try:
            mod = __import__(dep)
            ver = getattr(mod, "__version__", "ok")
            checks.append((f"Import {dep}", True, str(ver)))
        except ImportError:
            checks.append((f"Import {dep}", False, "not installed"))

    # System binaries
    for binary in ("ffmpeg", "ffprobe"):
        path = shutil.which(binary)
        checks.append((f"Binary: {binary}", path is not None, path or "not found"))

    # Optional binary: rubberband CLI (not required, pyrubberband works via library)
    rubberband_path = shutil.which("rubberband")
    checks.append(("Binary: rubberband (optional)", rubberband_path is not None, rubberband_path or "not found (pyrubberband works via library)"))

    # Stereo audio processing capability
    try:
        import numpy as np
        from djenius.audio.transitions import apply_transition
        from djenius.utils.audio_math import equal_power_crossfade
        # Test stereo crossfade
        test_stereo = np.random.randn(44100, 2).astype(np.float32) * 0.1
        result = apply_transition(test_stereo, test_stereo, 44100, "crossfade", 22050, 0, 0)
        stereo_ok = result.ndim == 2 and result.shape[1] == 2
        checks.append(("Stereo processing", stereo_ok, "stereo transitions supported" if stereo_ok else "mono only"))
    except Exception as e:
        checks.append(("Stereo processing", False, str(e)))

    # Time-stretch backend
    try:
        import pyrubberband
        # Test if pyrubberband works
        import numpy as np
        test_audio = np.random.randn(44100).astype(np.float32) * 0.1
        # Try a simple time-stretch
        stretched = pyrubberband.time_stretch(test_audio, 44100, 1.0)
        stretch_ok = len(stretched) > 0
        checks.append(("Time-stretch (pyrubberband)", stretch_ok, "working" if stretch_ok else "failed"))
    except Exception as e:
        checks.append(("Time-stretch (pyrubberband)", False, str(e)))

    # Writable working directory
    cwd = Path.cwd()
    writable = cwd.is_dir() and os.access(cwd, os.W_OK)
    checks.append(("Writable cwd", writable, str(cwd)))

    # SQLite
    try:
        import sqlite3 as _sqlite3
        _sqlite3.connect(":memory:").close()
        checks.append(("SQLite", True, "ok"))
    except Exception as e:
        checks.append(("SQLite", False, str(e)))

    # Ollama (optional)
    ollama_ok = False
    ollama_detail = "not found"
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                ollama_ok = True
                ollama_detail = "running"
    except Exception:
        ollama_detail = "not running (optional)"
    checks.append(("Ollama (optional)", ollama_ok, ollama_detail))

    # Stem separation (optional)
    try:
        from djenius.audio.stems import stems_available, gpu_available
        stems_ok = stems_available()
        gpu_ok = gpu_available()
        if stems_ok:
            stem_detail = f"demucs installed, GPU={'yes' if gpu_ok else 'no (CPU only)'}"
        else:
            stem_detail = "not installed (install with: pip install djenius[stems])"
        checks.append(("Stem separation (optional)", stems_ok, stem_detail))
    except Exception as e:
        checks.append(("Stem separation (optional)", False, str(e)))

    # V5: Preference database
    try:
        from djenius.db.preferences import PreferenceProfile
        prefs = PreferenceProfile.default()
        checks.append(("Preference database", True, f"ok ({prefs.count()} entries)"))
    except Exception as e:
        checks.append(("Preference database", False, str(e)))

    # V5: Intent parsing
    try:
        from djenius.core.nl_parser import parse_deterministic
        test_intent = parse_deterministic("smooth 30 min set")
        checks.append(("Intent parser", True, f"ok (test: preset={test_intent.preset})"))
    except Exception as e:
        checks.append(("Intent parser", False, str(e)))

    # Runtime dependency for explicit local Ollama parsing
    try:
        import httpx
        checks.append(("httpx (Ollama runtime)", True, getattr(httpx, "__version__", "ok")))
    except ImportError:
        checks.append(("httpx (Ollama runtime)", False, "not installed (reinstall DJenius)"))

    # Semantic analysis remains optional because its model is large.
    try:
        from djenius.audio.semantic import semantic_dependencies_available, semantic_model_name
        semantic_ok = semantic_dependencies_available()
        checks.append(("Semantic analysis (optional)", semantic_ok, semantic_model_name() if semantic_ok else "install with: pip install -e '.[semantic]'"))
    except Exception as e:
        checks.append(("Semantic analysis (optional)", False, str(e)))

    # Lyrics transcription is optional and lazy; model weights are never
    # downloaded by doctor.
    try:
        from djenius.audio.lyrics import lyrics_dependencies_available, DEFAULT_TRANSCRIPTION_MODEL
        lyrics_ok = lyrics_dependencies_available()
        checks.append(("Lyrics transcription (optional)", lyrics_ok, DEFAULT_TRANSCRIPTION_MODEL if lyrics_ok else "install with: pip install -e '.[lyrics]'"))
    except Exception as e:
        checks.append(("Lyrics transcription (optional)", False, str(e)))

    # Display
    table = Table(title="DJenius Doctor", box=box.ROUNDED)
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    all_critical_pass = True
    for label, ok, detail in checks:
        status = "[green]PASS[/]" if ok else "[red]FAIL[/]"
        if not ok and "optional" not in label.lower():
            all_critical_pass = False
        table.add_row(label, status, detail)

    console.print(table)

    if all_critical_pass:
        console.print("\n[green]All critical checks passed.[/]")
    else:
        console.print("\n[red]Some critical checks failed. See above for details.[/]")
        raise typer.Exit(1)


@app.command()
def auto(
    library_path: str = typer.Argument(..., help="Path to music library"),
    output: str = typer.Option(
        "output/mix.wav", "--output", "-o",
        help="Output audio file path"
    ),
    output_format: str = typer.Option(
        "wav", "--format", "-f",
        help="Output format: wav or mp3"
    ),
    duration: float = typer.Option(1800.0, "--duration", "-d", help="Target duration in seconds"),
    energy: str = typer.Option(
        "steady", "--energy", "-e",
        help="Energy profile: steady, slow_build, warmup_to_peak, wave, peak_early, peak_late, cooldown"
    ),
    target_lufs: float = typer.Option(-14.0, "--lufs", help="Target loudness in LUFS"),
    cache_path: str = typer.Option(
        "data/analysis_cache.db", "--cache", "-c",
        help="Path to SQLite cache database"
    ),
    max_tracks: Optional[int] = typer.Option(None, "--max-tracks", help="Maximum tracks"),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed"),
    request: Optional[str] = typer.Option(
        None, "--request", "-r",
        help="Natural language description of desired set (e.g. 'chill mix 30 min')"
    ),
    preset: Optional[str] = typer.Option(
        None, "--preset", "-p",
        help="Preset name: chill, smooth, balanced, energetic, peak, late_night, vocal_safe, experimental"
    ),
    use_llm: bool = typer.Option(
        False, "--use-llm/--no-llm",
        help="Use Ollama LLM for advanced intent parsing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Full pipeline: scan -> analyze -> plan -> render -> master -> save.

    One command to create a complete DJ mix from your music library.

    Supports natural language requests via --request, e.g.:
        djenius auto library --request "energetic peak time 45 min" -o output/peak.wav
        djenius auto library --preset smooth --duration 2400
    """
    _setup_logging(verbose)

    from djenius.core.models import EnergyProfile
    from djenius.core.planner import plan_set
    from djenius.core.intent import make_intent
    from djenius.core.nl_parser import parse_request
    from djenius.audio.analyzer import analyze_track
    from djenius.audio.scanner import scan_directory
    from djenius.audio.renderer import render_mix

    console.print(Panel("[bold]DJenius Auto Pipeline[/]", border_style="blue"))

    lib_path = Path(library_path).expanduser().resolve()
    if not lib_path.exists():
        console.print(f"[red]Error:[/] Directory not found: {lib_path}")
        raise typer.Exit(1)

    cache = _get_cache(cache_path)

    # Build intent from request/preset or legacy flags
    intent = None
    effective_energy = energy
    effective_duration = duration

    if request:
        intent = parse_request(request, use_llm=use_llm)
        console.print(f"\n[bold blue]Parsed intent:[/] preset={intent.preset}, "
                      f"energy={intent.energy_profile.value if intent.energy_profile else 'auto'}, "
                      f"transition={intent.transition_style}, "
                      f"duration={intent.target_duration_sec:.0f}s")
        if intent.target_duration_sec:
            effective_duration = intent.target_duration_sec
    elif preset:
        intent = make_intent(preset)
        console.print(f"\n[bold blue]Using preset:[/] {preset}")

    # Step 1: Scan
    console.print("\n[bold blue]1. Scanning library...[/]")
    tracks = scan_directory(str(lib_path))
    console.print(f"   Found {len(tracks)} tracks")

    if len(tracks) < 2:
        console.print("[red]Error:[/] Need at least 2 tracks to create a mix")
        raise typer.Exit(1)

    # Step 2: Analyze
    console.print("\n[bold blue]2. Analyzing tracks...[/]")
    profiles = []
    analyzed = 0
    skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing...", total=len(tracks))
        for track in tracks:
            try:
                profile = analyze_track(track.filepath, cache=cache)
                profiles.append(profile)
                analyzed += 1
            except Exception as e:
                logging.getLogger(__name__).warning("Skipping %s: %s", track.title, e)
            progress.advance(task)

    console.print(f"   Analyzed {analyzed} tracks ({skipped} cached)")

    # Step 3: Plan
    console.print("\n[bold blue]3. Planning set...[/]")
    ep = None
    if not intent or not intent.energy_profile:
        try:
            ep = EnergyProfile(effective_energy)
        except ValueError:
            console.print(f"[red]Error:[/] Invalid energy profile: {effective_energy}")
            raise typer.Exit(1)

    # Get preference bonuses if available
    preference_bonuses = None
    try:
        from djenius.db.preferences import PreferenceProfile
        prefs = PreferenceProfile.default()
        preference_bonuses = prefs.get_scoring_bonuses()
    except Exception:
        pass

    set_plan = plan_set(
        tracks=profiles,
        target_duration_sec=effective_duration,
        energy_profile=ep,
        max_tracks=max_tracks,
        seed=seed,
        intent=intent,
        preference_bonuses=preference_bonuses,
    )

    console.print(f"   Planned {len(set_plan.tracks)} tracks")
    console.print(f"   Duration: {_format_duration(set_plan.total_duration_sec)}")
    console.print(f"   Score: {set_plan.score:.2f}")

    # Show plan explanations
    if set_plan.human_readable_reasons:
        console.print("\n[bold]Plan Explanations:[/]")
        for reason in set_plan.human_readable_reasons:
            console.print(f"  - {reason}")

    # Step 4: Render
    console.print(f"\n[bold blue]4. Rendering mix...[/]")

    result = render_mix(
        plan=set_plan,
        output_path=output,
        output_format=output_format,
        target_lufs=target_lufs,
        progress_callback=lambda p, m: None,
    )

    # Display results
    console.print(f"\n[bold green]5. Mix complete![/]")
    table = Table(box=box.ROUNDED)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Output", result["output_path"])
    table.add_row("Duration", _format_duration(result["duration_sec"]))
    table.add_row("Format", f"{result['format'].upper()}, {result['channels']}ch, {result['sample_rate']}Hz")
    table.add_row("Peak", f"{result['peak_db']:.1f} dB")
    if result.get("final_lufs") is not None:
        table.add_row("LUFS", f"{result['final_lufs']}")
    table.add_row("Transitions", str(result["transitions_rendered"]))
    table.add_row("Render time", _format_duration(result["render_time_sec"]))
    table.add_row("File size", f"{result['file_size_mb']} MB")

    console.print(table)

    # Save plan
    plan_output = Path(output).with_suffix(".plan.json")
    plan_dict = set_plan.to_dict()
    with open(plan_output, "w") as f:
        json.dump(plan_dict, f, indent=2, default=str)

    console.print(f"\n[dim]Set plan saved to {plan_output}[/]")

    # Show transition details
    if result.get("diagnostics"):
        console.print("\n[bold]Transition Details:[/]")
        diag_table = Table(box=box.SIMPLE)
        diag_table.add_column("From", style="cyan")
        diag_table.add_column("To", style="cyan")
        diag_table.add_column("Type", style="yellow")
        diag_table.add_column("Overlap", justify="right")

        for d in result["diagnostics"]:
            diag_table.add_row(
                d["from"][:25],
                d["to"][:25],
                d["type"],
                f"{d['overlap_sec']:.1f}s",
            )

        console.print(diag_table)

    console.print(f"\n[green]Done! Your mix is ready at {result['output_path']}[/]")


@app.command()
def transitions(
    output_dir: str = typer.Option(
        "outputs/transition_auditions",
        help="Directory to write audition WAVs and diagnostics JSON."
    ),
    stereo: bool = typer.Option(
        True,
        help="Generate stereo auditions."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
):
    """Generate audition WAV files and diagnostics for all transition types.

    Creates WAV previews of each transition (crossfade, beatmatched_blend,
    bass_swap, filter_sweep, echo_out) with a transition_diagnostics.json
    file containing metadata about each.
    """
    _setup_logging(verbose)
    console.print("[bold]DJenius - Transition Diagnostics[/]\n")

    from djenius.audio.diagnostics import generate_transition_auditions

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating transition auditions...", total=None)
        result = generate_transition_auditions(output_dir, stereo=stereo)
        progress.update(task, description="Done!")

    console.print(f"\n[green]Generated {len(result['files'])} files in {result['output_dir']}[/]\n")

    # Display diagnostics table
    table = Table(title="Transition Diagnostics", box=box.ROUNDED)
    table.add_column("Type", style="cyan")
    table.add_column("Channels", justify="right")
    table.add_column("Output Samples", justify="right")
    table.add_column("RMS Energy", justify="right")
    table.add_column("Peak dB", justify="right")

    for d in result["diagnostics"]:
        table.add_row(
            d["type"],
            str(d["channels"]),
            f"{d['output_samples']:,}",
            f"{d['rms_energy']:.4f}",
            f"{d['peak_db']:.1f}",
        )

    console.print(table)

    console.print(f"\n[dim]Diagnostics JSON: {result['json_path']}[/]")


@app.command()
def report(
    set_plan_path: str = typer.Argument(
        help="Path to a SetPlan JSON file (from djenius auto --save-plan)."
    ),
    output_dir: str = typer.Option(
        "outputs/diagnostics",
        help="Directory to write the diagnostic report JSON."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging."),
):
    """Generate a V4 diagnostic report for a completed set plan.

    Reads a SetPlan JSON file and produces a detailed diagnostic report
    with per-track analysis, per-transition V4 context, and energy
    trajectory visualization.
    """
    _setup_logging(verbose)
    console.print("[bold]DJenius - Set Diagnostic Report[/]\n")

    from djenius.core.models import SetPlan
    from djenius.audio.diagnostics import generate_set_diagnostic_report

    with open(set_plan_path) as f:
        plan_data = json.load(f)

    set_plan = SetPlan.from_dict(plan_data)

    result = generate_set_diagnostic_report(set_plan, output_dir)

    report = result["report"]
    summary = report["set_plan_summary"]

    console.print(f"[green]Report written to {result['json_path']}[/]\n")
    console.print(f"Tracks: {summary['track_count']}")
    console.print(f"Transitions: {summary['transition_count']}")
    console.print(f"Duration: {summary['total_duration_sec']:.0f}s / {summary['target_duration_sec']:.0f}s target")
    console.print(f"Energy Profile: {summary['energy_profile']}")
    console.print(f"Avg Confidence: {summary['avg_confidence']:.3f}")

    # Show energy trajectory
    energies = report["energy_trajectory"]["energies"]
    console.print(f"\n[bold]Energy Trajectory:[/]")
    for i, e in enumerate(energies):
        bar_len = int(e * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        console.print(f"  Track {i+1}: [{bar}] {e:.3f}")

    # Show transitions summary
    if report["transitions"]:
        console.print(f"\n[bold]Transitions:[/]")
        for t in report["transitions"]:
            vocal_info = ""
            if t["vocal"]["source_has_vocals"] and t["vocal"]["target_has_vocals"]:
                vocal_info = " [yellow](dual vocal)[/]"
            elif t["vocal"]["source_has_vocals"] or t["vocal"]["target_has_vocals"]:
                vocal_info = " [yellow](vocal)[/]"

            console.print(
                f"  {t['source_title']} -> {t['target_title']}: "
                f"{t['transition_type']} (conf={t['confidence']:.2f})"
                f"{vocal_info}"
            )


@app.command()
def feedback(
    plan_path: str = typer.Argument(..., help="Path to set plan JSON"),
    rating: int = typer.Argument(..., help="Overall rating 1-5"),
    track_ratings: Optional[str] = typer.Option(
        None, "--tracks", "-t",
        help='Track-specific ratings: "Track Name=4,Other Track=2"'
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Log feedback for a rendered mix.

    Example:
        djenius feedback output/mix.plan.json 4 --tracks "My Song=5,Another=3"
    """
    _setup_logging(verbose)

    plan_file = Path(plan_path)
    if not plan_file.exists():
        console.print(f"[red]Error:[/] Plan file not found: {plan_file}")
        raise typer.Exit(1)

    from djenius.db.preferences import PreferenceProfile
    from djenius.core.models import SetPlan

    # Load plan to extract metadata
    with open(plan_file) as f:
        plan_data = json.load(f)
    plan = SetPlan.from_dict(plan_data)

    # Validate rating
    rating = max(1, min(5, rating))

    prefs = PreferenceProfile.default()

    # Parse track ratings
    track_ratings_dict = {}
    if track_ratings:
        for pair in track_ratings.split(","):
            if "=" in pair:
                name, score = pair.rsplit("=", 1)
                try:
                    track_ratings_dict[name.strip()] = int(score)
                except ValueError:
                    pass

    # Log feedback
    prefs.log_mix_feedback(
        mix_id=plan_data.get("set_id", "unknown"),
        rating=rating,
        track_ratings=track_ratings_dict if track_ratings_dict else None,
    )

    console.print(f"[green]Feedback logged:[/] rating={rating}")
    if track_ratings_dict:
        for name, score in track_ratings_dict.items():
            console.print(f"  {name}: {score}")

    # Show current preference summary
    summary = prefs.summary()
    if summary.get("transition_ratings"):
        console.print(f"\n[bold]Your preferences so far:[/]")
        for tt, counts in summary["transition_ratings"].items():
            total = counts["liked"] + counts["neutral"] + counts["disliked"]
            if total > 0:
                like_pct = counts["liked"] / total * 100
                console.print(f"  {tt}: {like_pct:.0f}% liked ({total} ratings)")

    if summary.get("track_feedback"):
        console.print(f"\n[bold]Track feedback:[/]")
        for track, rating in summary["track_feedback"].items():
            console.print(f"  {track}: {rating}")


@app.command()
def like(
    track_name: str = typer.Argument(..., help="Name or ID of the track to like"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Mark a track as liked (will be preferred in future sets)."""
    _setup_logging(verbose)

    from djenius.db.preferences import PreferenceProfile

    prefs = PreferenceProfile.default()
    prefs.like_track(track_name)
    console.print(f"[green]Liked:[/] {track_name}")


@app.command()
def dislike(
    track_name: str = typer.Argument(..., help="Name or ID of the track to dislike"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Mark a track as disliked (will be avoided in future sets)."""
    _setup_logging(verbose)

    from djenius.db.preferences import PreferenceProfile

    prefs = PreferenceProfile.default()
    prefs.dislike_track(track_name)
    console.print(f"[yellow]Disliked:[/] {track_name}")


@app.command()
def explain(
    plan_path: str = typer.Argument(..., help="Path to set plan JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Show human-readable explanations for a set plan."""
    _setup_logging(verbose)

    plan_file = Path(plan_path)
    if not plan_file.exists():
        console.print(f"[red]Error:[/] Plan file not found: {plan_file}")
        raise typer.Exit(1)

    from djenius.core.models import SetPlan
    from djenius.core.explanations import explain_set_plan

    with open(plan_file) as f:
        plan_data = json.load(f)

    plan = SetPlan.from_dict(plan_data)
    reasons = explain_set_plan(plan)

    if reasons:
        console.print(Panel("[bold]Plan Explanations[/]", border_style="blue"))
        for reason in reasons:
            console.print(f"  - {reason}")
    else:
        console.print("[dim]No explanations available for this plan.[/]")

    # Show transition details
    if plan.transitions:
        console.print(f"\n[bold]Transition Details:[/]")
        for i, t in enumerate(plan.transitions):
            source = plan.tracks[i].title if i < len(plan.tracks) else "?"
            target = plan.tracks[i+1].title if i+1 < len(plan.tracks) else "?"
            console.print(
                f"  {source} -> {target}: {t.transition_type.value} "
                f"(conf={t.confidence:.2f}, overlap={t.overlap_duration:.1f}s)"
            )


@app.command(name="preferences")
def show_preferences(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Show your current preference profile."""
    _setup_logging(verbose)

    from djenius.db.preferences import PreferenceProfile

    prefs = PreferenceProfile.default()
    summary = prefs.summary()

    if not any([
        summary.get("transition_ratings"),
        summary.get("track_feedback"),
        summary.get("bpm_preference"),
        summary.get("energy_preference"),
    ]):
        console.print("[dim]No preferences recorded yet. Use 'feedback', 'like', or 'dislike' to build your profile.[/]")
        return

    console.print(Panel("[bold]Your DJ Preferences[/]", border_style="blue"))

    # Transition preferences
    if summary.get("transition_ratings"):
        console.print("\n[bold]Transition Type Preferences:[/]")
        table = Table(box=box.SIMPLE)
        table.add_column("Type", style="cyan")
        table.add_column("Liked", justify="right")
        table.add_column("Neutral", justify="right")
        table.add_column("Disliked", justify="right")
        table.add_column("Total", justify="right")

        for tt, counts in summary["transition_ratings"].items():
            total = counts["liked"] + counts["neutral"] + counts["disliked"]
            if total > 0:
                table.add_row(
                    tt,
                    str(counts["liked"]),
                    str(counts["neutral"]),
                    str(counts["disliked"]),
                    str(total),
                )

        console.print(table)

    # Track preferences
    if summary.get("track_feedback"):
        console.print("\n[bold]Track Feedback:[/]")
        for track, rating in summary["track_feedback"].items():
            emoji = "+" if rating == "liked" else "-"
            color = "green" if rating == "liked" else "yellow"
            console.print(f"  [{color}]{emoji} {track}[/]")

    # BPM preference
    if summary.get("bpm_preference"):
        bpm_pref = summary["bpm_preference"]
        console.print(f"\n[bold]BPM Preference:[/] {bpm_pref['min']:.0f} - {bpm_pref['max']:.0f} BPM")

    # Energy preference
    if summary.get("energy_preference"):
        energy_pref = summary["energy_preference"]
        console.print(f"[bold]Energy Preference:[/] {energy_pref['min']:.2f} - {energy_pref['max']:.2f}")

    # Scoring bonuses (for debugging)
    bonuses = prefs.get_scoring_bonuses()
    console.print(f"\n[bold]Scoring Bonuses:[/]")
    console.print(f"  Liked tracks bonus: +0.08")
    console.print(f"  Disliked tracks penalty: -0.12")
    console.print(f"  BPM in range bonus: +0.05")
    console.print(f"  Energy in range bonus: +0.05")


if __name__ == "__main__":
    app()
