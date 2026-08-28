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
                profile = analyze_track(track.filepath, cache=cache)
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
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Plan a DJ set from the analyzed library."""
    _setup_logging(verbose)

    from djenius.core.models import EnergyProfile
    from djenius.core.planner import plan_set
    from djenius.audio.analyzer import analyze_track
    from djenius.audio.scanner import scan_directory

    lib_path = Path(library_path).expanduser().resolve()
    cache = _get_cache(cache_path)

    # Scan and analyze
    console.print(Panel("[bold]Planning DJ Set[/]", border_style="blue"))

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

    # Parse energy profile
    try:
        ep = EnergyProfile(energy)
    except ValueError:
        console.print(f"[red]Error:[/] Invalid energy profile: {energy}")
        console.print(f"Valid options: {[e.value for e in EnergyProfile]}")
        raise typer.Exit(1)

    # Plan
    console.print(f"\nPlanning with target duration {_format_duration(duration)}, energy={energy}...")

    set_plan = plan_set(
        tracks=profiles,
        target_duration_sec=duration,
        energy_profile=ep,
        max_tracks=max_tracks,
        seed=seed,
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


if __name__ == "__main__":
    app()
