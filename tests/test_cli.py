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


def test_run_with_dbt_engine_executes_a_real_macro(tmp_path: Path):
    project_dir = tmp_path / "proj"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: proj\nversion: "1.0.0"\nconfig-version: 2\nprofile: proj\nmodel-paths: ["models"]\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(
        "proj:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        '      path: "proj.duckdb"\n      schema: main\n'
    )
    (project_dir / "models" / "placeholder.sql").write_text("select 1 as id\n")

    features = tmp_path / "features"
    features.mkdir()
    (features / "orders.feature").write_text(
        "Feature: Orders\n\n"
        "  Scenario: Uppercase status\n"
        '    Given the following rows in "orders":\n'
        "      | order_id | status |\n"
        "      | 1        | placed |\n"
        '    When the "select order_id, upper(status) as status from '
        "{{ ref('orders') }} order by order_id\" macro runs\n"
        '    Then the "select order_id, upper(status) as status from '
        "{{ ref('orders') }} order by order_id\" should produce the "
        "following rows:\n"
        "      | order_id | status |\n"
        "      | 1        | PLACED |\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            str(features),
            "--engine",
            "dbt",
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir / "profiles"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "0 failure(s)" in result.output


def test_run_with_dbt_engine_requires_project_dir(tmp_path: Path):
    features = tmp_path / "features"
    features.mkdir()
    (features / "x.feature").write_text("Feature: F\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(features), "--engine", "dbt"])
    assert result.exit_code != 0
    assert "--project-dir is required" in result.output


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
