from pathlib import Path

from click.testing import CliRunner

from specdbt.cli import cli


def test_init_creates_example_feature_and_canned_files(tmp_path: Path):
    runner = CliRunner()
    target = tmp_path / "features"
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0, result.output
    assert (target / "example.feature").exists()
    assert (target / "example.canned.py").exists()


def test_init_refuses_to_overwrite_existing_scaffold(tmp_path: Path):
    runner = CliRunner()
    target = tmp_path / "features"
    runner.invoke(cli, ["init", str(target)])
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_run_reports_pass_for_the_scaffolded_example(tmp_path: Path):
    runner = CliRunner()
    target = tmp_path / "features"
    runner.invoke(cli, ["init", str(target)])
    result = runner.invoke(cli, ["run", str(target)])
    assert result.exit_code == 0, result.output
    assert "✓" in result.output
    assert "0 failure(s)" in result.output


def test_run_exits_nonzero_when_a_scenario_fails(tmp_path: Path):
    feature = tmp_path / "bad.feature"
    feature.write_text(
        "Feature: F\n\n"
        "  Scenario: S\n"
        '    Given the following rows in "a":\n'
        "      | c |\n"
        "      | 1 |\n"
        '    When the "missing" model runs\n'
        '    Then "missing" should have 1 row\n'
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(feature)])
    assert result.exit_code == 1


def test_run_errors_when_no_feature_files_found(tmp_path: Path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(empty_dir)])
    assert result.exit_code != 0
    assert "no .feature files found" in result.output


def test_generate_reports_not_implemented():
    runner = CliRunner()
    result = runner.invoke(cli, ["generate", "--from-model", "x"])
    assert result.exit_code != 0
    assert "Phase 3" in result.output


def test_compile_reports_not_implemented(tmp_path: Path):
    feature = tmp_path / "x.feature"
    feature.write_text("Feature: F\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["compile", str(feature), "--to", "dbt-unit-tests"])
    assert result.exit_code != 0
    assert "Phase 2" in result.output
