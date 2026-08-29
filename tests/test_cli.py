"""Tests for CLI commands (help text, argument parsing, error handling)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from djenius.cli import app


runner = CliRunner()


class TestHelpText:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "scan" in result.stdout
        assert "analyze" in result.stdout
        assert "plan" in result.stdout
        assert "mix" in result.stdout
        assert "info" in result.stdout
        assert "doctor" in result.stdout
        assert "transitions" in result.stdout

    def test_scan_help(self):
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "Scan" in result.stdout or "scan" in result.stdout.lower()

    def test_analyze_help(self):
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0

    def test_plan_help(self):
        result = runner.invoke(app, ["plan", "--help"])
        assert result.exit_code == 0

    def test_mix_help(self):
        result = runner.invoke(app, ["mix", "--help"])
        assert result.exit_code == 0

    def test_info_help(self):
        result = runner.invoke(app, ["info", "--help"])
        assert result.exit_code == 0

    def test_doctor_help(self):
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0


class TestScanCommand:
    def test_missing_directory(self):
        result = runner.invoke(app, ["scan", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_non_audio_directory(self, tmp_path):
        result = runner.invoke(app, ["scan", str(tmp_path)])
        assert result.exit_code == 0


class TestAnalyzeCommand:
    def test_missing_directory(self):
        result = runner.invoke(app, ["analyze", "/nonexistent/path"])
        assert result.exit_code != 0


class TestPlanCommand:
    def test_missing_directory(self):
        result = runner.invoke(app, ["plan", "/nonexistent/path"])
        assert result.exit_code != 0


class TestMixCommand:
    def test_missing_directory(self):
        result = runner.invoke(app, ["mix", "/nonexistent/path", "/nonexistent/output"])
        assert result.exit_code != 0


class TestInfoCommand:
    def test_nonexistent_path(self):
        # info just queries the cache — no path validation
        result = runner.invoke(app, ["info", "/nonexistent/file.wav"])
        assert result.exit_code == 0


class TestDoctorCommand:
    def test_runs_without_error(self):
        result = runner.invoke(app, ["doctor"])
        # Doctor may exit(1) if optional binaries (e.g. rubberband) are missing
        assert result.exit_code in (0, 1)
        assert "Python" in result.stdout or "python" in result.stdout.lower()

    def test_checks_python(self):
        result = runner.invoke(app, ["doctor"])
        assert "3." in result.stdout  # Python version

    def test_checks_ffmpeg(self):
        result = runner.invoke(app, ["doctor"])
        assert "ffmpeg" in result.stdout.lower()


class TestTransitionsCommand:
    def test_help(self):
        result = runner.invoke(app, ["transitions", "--help"])
        assert result.exit_code == 0
        assert "transition" in result.stdout.lower()

    def test_generates_output(self, tmp_path):
        result = runner.invoke(app, ["transitions", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Done" in result.stdout or "Generated" in result.stdout

    def test_json_diagnostic_file(self, tmp_path):
        runner.invoke(app, ["transitions", "--output-dir", str(tmp_path)])
        json_path = tmp_path / "transition_diagnostics.json"
        assert json_path.exists()
        import json
        with open(json_path) as f:
            data = json.load(f)
        assert "transitions" in data
        assert len(data["transitions"]) == 5
