from pathlib import Path

import duckdb
import pytest

from specdbt.adapters.dbt_adapter import (
    DbtExecutionAdapter,
    DbtInvocationError,
    ModelIntegrationTierNotImplementedError,
    ProdSchemaGuardError,
)
from specdbt.fixtures import Fixture


def test_refuses_a_target_that_looks_like_production(tmp_path: Path):
    with pytest.raises(ProdSchemaGuardError):
        DbtExecutionAdapter(project_dir=tmp_path, profiles_dir=tmp_path, target="prod")


def test_allow_any_schema_overrides_the_guard(tmp_path: Path):
    adapter = DbtExecutionAdapter(
        project_dir=tmp_path, profiles_dir=tmp_path, target="prod", allow_any_schema=True
    )
    assert adapter is not None


def test_no_target_does_not_trigger_the_guard(tmp_path: Path):
    adapter = DbtExecutionAdapter(project_dir=tmp_path, profiles_dir=tmp_path)
    assert adapter is not None


def test_run_model_raises_not_implemented(scratch_dbt_project: Path):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project, profiles_dir=scratch_dbt_project / "profiles"
    )
    with pytest.raises(ModelIntegrationTierNotImplementedError):
        adapter.run_model("placeholder", [])


def test_run_macro_materializes_fixtures_and_returns_real_computed_rows(
    scratch_dbt_project: Path,
):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project, profiles_dir=scratch_dbt_project / "profiles"
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


def test_run_macro_handles_string_values_with_quotes(scratch_dbt_project: Path):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project, profiles_dir=scratch_dbt_project / "profiles"
    )
    fixtures = [Fixture(name="customers", rows=[{"id": 1, "name": "O'Brien"}])]
    result = adapter.run_macro("select * from {{ ref('customers') }}", fixtures)
    assert result.rows == [{"id": 1, "name": "O'Brien"}]


def test_run_macro_tears_down_schema_and_macro_file_on_success(
    scratch_dbt_project: Path,
):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project, profiles_dir=scratch_dbt_project / "profiles"
    )
    fixtures = [Fixture(name="orders", rows=[{"order_id": 1, "status": "placed"}])]
    adapter.run_macro("select * from {{ ref('orders') }}", fixtures)

    assert list((scratch_dbt_project / "macros").glob("_specdbt_*.sql")) == []
    con = duckdb.connect(str(scratch_dbt_project / "scratch.duckdb"))
    schemas = con.execute(
        "select schema_name from information_schema.schemata where schema_name like 'specdbt_%'"
    ).fetchall()
    assert schemas == []


def test_run_macro_tears_down_even_when_the_query_fails(scratch_dbt_project: Path):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project, profiles_dir=scratch_dbt_project / "profiles"
    )
    fixtures = [Fixture(name="orders", rows=[{"order_id": 1, "status": "placed"}])]
    with pytest.raises(DbtInvocationError):
        adapter.run_macro("select * from this_is_not_valid_sql(((", fixtures)

    assert list((scratch_dbt_project / "macros").glob("_specdbt_*.sql")) == []
    con = duckdb.connect(str(scratch_dbt_project / "scratch.duckdb"))
    schemas = con.execute(
        "select schema_name from information_schema.schemata where schema_name like 'specdbt_%'"
    ).fetchall()
    assert schemas == []


def test_keep_schema_skips_teardown(scratch_dbt_project: Path):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project,
        profiles_dir=scratch_dbt_project / "profiles",
        keep_schema=True,
    )
    fixtures = [Fixture(name="orders", rows=[{"order_id": 1, "status": "placed"}])]
    adapter.run_macro("select * from {{ ref('orders') }}", fixtures)
    assert list((scratch_dbt_project / "macros").glob("_specdbt_*.sql")) != []
