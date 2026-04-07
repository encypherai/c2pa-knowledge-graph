"""Tests for the CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from c2pa_kg.cli import cli


class TestListVersionsCommand:
    def test_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-versions"])
        assert result.exit_code == 0, f"Non-zero exit: {result.output}"

    def test_output_contains_versions(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-versions"])
        assert "2.4" in result.output

    def test_output_contains_multiple_versions(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-versions"])
        # Should list at least a few versions
        assert "1.0" in result.output

    def test_output_contains_dates(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-versions"])
        # Dates are in YYYY-MM-DD format
        assert "2026" in result.output or "2025" in result.output

    def test_output_has_header(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["list-versions"])
        # Header row includes "Version" and "Date"
        assert "Version" in result.output
        assert "Date" in result.output


class TestGenerateCommand:
    def test_bad_version_gives_clean_error(self, tmp_path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate",
            "--spec-source", str(tmp_path),
            "--version", "99.99",
            "--output-dir", str(tmp_path / "output"),
        ])
        # Should not crash with an unhandled exception
        assert result.exit_code != 0
        # Should mention the bad version
        exception_str = str(result.exception) if result.exception else ""
        assert "99.99" in result.output or "99.99" in exception_str

    def test_missing_spec_source_gives_error(self, tmp_path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, [
            "generate",
            "--spec-source", str(tmp_path / "nonexistent"),
            "--version", "2.4",
            "--output-dir", str(tmp_path / "output"),
        ])
        assert result.exit_code != 0

    def test_missing_required_options_gives_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["generate"])
        assert result.exit_code != 0


class TestCliGroup:
    def test_help_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_help_mentions_generate(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "generate" in result.output

    def test_help_mentions_list_versions(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "list-versions" in result.output

    def test_unknown_command_gives_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["not-a-real-command"])
        assert result.exit_code != 0
