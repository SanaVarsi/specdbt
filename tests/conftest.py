"""Shared pytest fixtures. `scratch_dbt_project` is used by every test that
needs to run real dbt (spec §5.1's mechanism) against a minimal, disposable
DuckDB-backed project -- no network, no dbt_utils, just enough scaffolding
for dbtRunner to work."""

from pathlib import Path

import pytest


@pytest.fixture
def scratch_dbt_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "scratch_project"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\n'
        'profile: scratch\nmodel-paths: ["models"]\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(
        "scratch:\n"
        "  target: dev\n"
        "  outputs:\n"
        "    dev:\n"
        "      type: duckdb\n"
        '      path: "scratch.duckdb"\n'
        "      schema: main\n"
    )
    (project_dir / "models" / "placeholder.sql").write_text("select 1 as id\n")
    return project_dir


@pytest.fixture
def scratch_dbt_project_with_upstream(tmp_path: Path) -> Path:
    """Unlike scratch_dbt_project's single placeholder model, this one has
    a real ref() edge (upstream_model -> downstream_model) -- unit testing
    needs something to override, and something to build first (spec §4.1
    finding 6: the given input must already be a real, built relation for
    dbt to introspect its column types)."""
    project_dir = tmp_path / "scratch_project_upstream"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\n'
        'profile: scratch\nmodel-paths: ["models"]\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(
        "scratch:\n"
        "  target: dev\n"
        "  outputs:\n"
        "    dev:\n"
        "      type: duckdb\n"
        '      path: "scratch.duckdb"\n'
        "      schema: main\n"
    )
    (project_dir / "models" / "upstream_model.sql").write_text(
        "select 1 as id, 'placed' as status\n"
    )
    (project_dir / "models" / "downstream_model.sql").write_text(
        "select id, upper(status) as status from {{ ref('upstream_model') }}\n"
    )
    return project_dir


@pytest.fixture
def scratch_dbt_project_with_upstream_custom_model_paths(tmp_path: Path) -> Path:
    """Same shape as scratch_dbt_project_with_upstream, but model-paths is
    "transform" instead of dbt's default "models" -- reproduces final
    review finding 1 (write_unit_test_yaml hardcoded "models", so the
    generated unit-test YAML landed somewhere dbt never parses)."""
    project_dir = tmp_path / "scratch_project_custom_paths"
    (project_dir / "transform").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\n'
        'profile: scratch\nmodel-paths: ["transform"]\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(
        "scratch:\n"
        "  target: dev\n"
        "  outputs:\n"
        "    dev:\n"
        "      type: duckdb\n"
        '      path: "scratch.duckdb"\n'
        "      schema: main\n"
    )
    (project_dir / "transform" / "upstream_model.sql").write_text(
        "select 1 as id, 'placed' as status\n"
    )
    (project_dir / "transform" / "downstream_model.sql").write_text(
        "select id, upper(status) as status from {{ ref('upstream_model') }}\n"
    )
    return project_dir
