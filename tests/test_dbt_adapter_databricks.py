"""Real end-to-end macro-tier execution against Databricks/Unity Catalog --
the one adapter this plan cannot validate in this environment (no
credentials). Skipped unless DATABRICKS_HOST is set; never required for the
rest of the suite, and never run in this repo's CI. See
docs/knowledge/databricks-validation-checklist.md for how to run it against a real
workspace."""

import os
from pathlib import Path

import pytest
import yaml

from specdbt.adapters.dbt_adapter import DbtExecutionAdapter
from specdbt.fixtures import Fixture

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABRICKS_HOST"),
    reason="set DATABRICKS_HOST/DATABRICKS_HTTP_PATH/DATABRICKS_CONN_SECRET/"
    "DATABRICKS_CATALOG/DATABRICKS_SCHEMA against a real workspace to run this "
    "test -- see docs/knowledge/databricks-validation-checklist.md",
)


@pytest.fixture
def scratch_dbt_project_databricks(tmp_path: Path) -> Path:
    project_dir = tmp_path / "scratch_project_databricks"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\n'
        'profile: scratch\nmodel-paths: ["models"]\n'
    )
    target = {
        "type": "databricks",
        "host": os.environ["DATABRICKS_HOST"],
        "http_path": os.environ["DATABRICKS_HTTP_PATH"],
        "catalog": os.environ.get("DATABRICKS_CATALOG", "main"),
        "schema": os.environ.get("DATABRICKS_SCHEMA", "default"),
        "token": os.environ["DATABRICKS_CONN_SECRET"],
    }
    (project_dir / "profiles" / "profiles.yml").write_text(
        yaml.safe_dump({"scratch": {"target": "dev", "outputs": {"dev": target}}})
    )
    (project_dir / "models" / "placeholder.sql").write_text("select 1 as id\n")
    return project_dir


def test_run_macro_materializes_fixtures_and_returns_real_computed_rows_on_databricks(
    scratch_dbt_project_databricks: Path,
):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project_databricks,
        profiles_dir=scratch_dbt_project_databricks / "profiles",
    )
    fixtures = [
        Fixture(
            name="orders",
            rows=[
                {"order_id": 1, "status": "placed"},
                {"order_id": 2, "status": "shipped"},
            ],
        )
    ]
    result = adapter.run_macro(
        "select order_id, upper(status) as status from {{ ref('orders') }} order by order_id",
        fixtures,
    )
    assert result.rows == [
        {"order_id": 1, "status": "PLACED"},
        {"order_id": 2, "status": "SHIPPED"},
    ]
