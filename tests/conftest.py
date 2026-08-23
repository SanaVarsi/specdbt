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
