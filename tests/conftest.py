"""Shared pytest fixtures. `scratch_dbt_project` is used by every test that
needs to run real dbt (spec §5.1's mechanism) against a minimal, disposable
DuckDB-backed project -- no network, no dbt_utils, just enough scaffolding
for dbtRunner to work."""

import os
from pathlib import Path

import pytest
import yaml


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


@pytest.fixture
def scratch_dbt_project_postgres(tmp_path: Path) -> Path:
    """Mirrors scratch_dbt_project, but targets a real local Postgres via
    dbt-postgres -- the CI-gated second adapter this plan's own
    verification runs against (spec: macro-tier adapter-dispatch design,
    2026-08-30). `database` is set to the same database the connection
    uses (SPECDBT_PG_DBNAME) since Postgres, unlike Databricks/Snowflake,
    can't address a second catalog cross-database -- this still exercises
    the full catalog-threading pipeline end-to-end, just not cross-catalog
    addressing itself (that's Databricks-specific, see
    test_dbt_adapter_databricks.py)."""
    project_dir = tmp_path / "scratch_project_pg"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\n'
        'profile: scratch\nmodel-paths: ["models"]\n'
    )
    dbname = os.environ.get("SPECDBT_PG_DBNAME", "specdbt_test")
    target = {
        "type": "postgres",
        "host": os.environ.get("SPECDBT_PG_HOST", "localhost"),
        "port": int(os.environ.get("SPECDBT_PG_PORT", "5432")),
        "user": os.environ.get("SPECDBT_PG_USER", "specdbt"),
        "dbname": dbname,
        "database": dbname,
        "schema": "main",
        "threads": 1,
        "password": os.environ["SPECDBT_PG_SECRET"],
    }
    (project_dir / "profiles" / "profiles.yml").write_text(
        yaml.safe_dump({"scratch": {"target": "dev", "outputs": {"dev": target}}})
    )
    (project_dir / "models" / "placeholder.sql").write_text("select 1 as id\n")
    return project_dir
