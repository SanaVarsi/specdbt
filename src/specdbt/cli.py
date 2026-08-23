"""specdbt command-line interface."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import click

from specdbt.adapters.base import ExecutionResult
from specdbt.adapters.dbt_adapter import DbtExecutionAdapter
from specdbt.adapters.fake_adapter import FakeAdapter
from specdbt.reporter import render_feature_report, render_summary
from specdbt.runner import run_feature_file

_SCAFFOLD_FEATURE = """Feature: Example feature

  Scenario: Replace this with a real scenario
    Given the following rows in "example_source":
      | id | value |
      | 1  | hello |
    When the "example_model" model runs
    Then "example_model" should have 1 row
"""

_SCAFFOLD_CANNED = '''"""Hand-coded canned result for example.feature (Phase 0)."""
from specdbt.adapters.base import ExecutionResult

CANNED_RESULTS = {
    "example_model": ExecutionResult.of(rows=[{"id": 1, "value": "hello"}]),
}
'''


@click.group()
def cli() -> None:
    """specdbt -- BDD-style Given/When/Then testing for dbt models."""


@cli.command()
@click.argument("directory", type=click.Path(path_type=Path), default=Path("features"))
def init(directory: Path) -> None:
    """Scaffold DIRECTORY with one example .feature file and its canned result."""
    directory.mkdir(parents=True, exist_ok=True)
    example = directory / "example.feature"
    canned = example.with_suffix(".canned.py")
    if example.exists() or canned.exists():
        raise click.ClickException(f"{example} already exists, not overwriting")
    example.write_text(_SCAFFOLD_FEATURE)
    canned.write_text(_SCAFFOLD_CANNED)
    click.echo(f"created {example}")
    click.echo(f"created {canned}")


def _load_canned_results(path: Path) -> dict[str, ExecutionResult]:
    spec = importlib.util.spec_from_file_location(f"_specdbt_canned_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"could not load {path} as a Python module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return module.CANNED_RESULTS
    except AttributeError:
        raise click.ClickException(f"{path} does not define CANNED_RESULTS") from None


@cli.command()
@click.argument("target", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--engine",
    type=click.Choice(["fake", "dbt"]),
    default="fake",
    help="fake (default): FakeAdapter + co-located .canned.py. "
    "dbt: DbtExecutionAdapter, real execution.",
)
@click.option("--project-dir", "project_dir", type=click.Path(path_type=Path, exists=True))
@click.option("--profiles-dir", "profiles_dir", type=click.Path(path_type=Path, exists=True))
@click.option("--target", "dbt_target", default=None)
@click.option("--allow-any-schema", is_flag=True, default=False)
@click.option("--keep-schema", is_flag=True, default=False)
def run(
    target: Path,
    engine: str,
    project_dir: Path | None,
    profiles_dir: Path | None,
    dbt_target: str | None,
    allow_any_schema: bool,
    keep_schema: bool,
) -> None:
    """Parse and run the .feature file(s) under TARGET.

    --engine fake (default): each FEATURE.feature file may have a co-located
    FEATURE.canned.py exposing CANNED_RESULTS: dict[str, ExecutionResult],
    pre-registered into a fresh FakeAdapter before that file's scenarios run.

    --engine dbt: real execution via DbtExecutionAdapter against --project-dir
    (required) and --profiles-dir (defaults to --project-dir).
    """
    paths = sorted(target.glob("*.feature")) if target.is_dir() else [target]
    if not paths:
        raise click.ClickException(f"no .feature files found under {target}")

    dbt_adapter: DbtExecutionAdapter | None = None
    if engine == "dbt":
        if project_dir is None:
            raise click.ClickException("--project-dir is required with --engine dbt")
        dbt_adapter = DbtExecutionAdapter(
            project_dir=project_dir,
            profiles_dir=profiles_dir or project_dir,
            target=dbt_target,
            allow_any_schema=allow_any_schema,
            keep_schema=keep_schema,
        )

    reports = []
    for path in paths:
        if dbt_adapter is not None:
            adapter = dbt_adapter
        else:
            adapter = FakeAdapter()
            canned_path = path.with_suffix(".canned.py")
            if canned_path.exists():
                for model_name, result in _load_canned_results(canned_path).items():
                    adapter.register(model_name, result)
        reports.append(run_feature_file(path, adapter))

    for report in reports:
        click.echo(render_feature_report(report))
    click.echo(render_summary(reports))

    if any(not scenario.passed for report in reports for scenario in report.scenarios):
        sys.exit(1)


@cli.command()
@click.option("--from-model", "from_model", required=True)
@click.option("--fixtures", "fixtures_flag", is_flag=True, default=False)
def generate(from_model: str, fixtures_flag: bool) -> None:
    """AI-assisted scenario/fixture generation (Phase 3 -- not implemented yet)."""
    raise click.ClickException(
        "`specdbt generate` ships in Phase 3 -- see the AI integration plan doc."
    )


@cli.command(name="compile")
@click.argument("target", type=click.Path(path_type=Path, exists=True))
@click.option("--to", "to_format", type=click.Choice(["dbt-unit-tests"]), required=True)
def compile_(target: Path, to_format: str) -> None:
    """Compile .feature scenarios to native dbt unit tests (Phase 2 -- not implemented yet)."""
    raise click.ClickException("`specdbt compile` ships in Phase 2 -- see the roadmap doc.")


if __name__ == "__main__":
    cli()
