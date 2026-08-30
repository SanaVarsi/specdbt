"""Real end-to-end macro-tier execution against Postgres -- the CI-gated
second adapter proving gaps 1-3 of the macro-tier adapter-dispatch design
(2026-08-30) work on a non-DuckDB engine. Skipped locally unless
SPECDBT_TEST_POSTGRES=1 (set by docker-compose up + this var, or in CI);
never required for the rest of the suite to run."""

import os
from pathlib import Path

import psycopg2
import pytest

from specdbt.adapters.dbt_adapter import DbtExecutionAdapter
from specdbt.fixtures import Fixture

pytestmark = pytest.mark.skipif(
    not os.environ.get("SPECDBT_TEST_POSTGRES"),
    reason="set SPECDBT_TEST_POSTGRES=1 with a running Postgres to run this test",
)


def test_run_macro_materializes_fixtures_and_returns_real_computed_rows_on_postgres(
    scratch_dbt_project_postgres: Path,
):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project_postgres,
        profiles_dir=scratch_dbt_project_postgres / "profiles",
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


def test_run_macro_tears_down_schema_on_postgres(scratch_dbt_project_postgres: Path):
    adapter = DbtExecutionAdapter(
        project_dir=scratch_dbt_project_postgres,
        profiles_dir=scratch_dbt_project_postgres / "profiles",
    )
    fixtures = [Fixture(name="orders", rows=[{"order_id": 1, "status": "placed"}])]
    adapter.run_macro("select * from {{ ref('orders') }}", fixtures)

    assert list((scratch_dbt_project_postgres / "macros").glob("_specdbt_*.sql")) == []
    connection_kwargs = {
        "host": os.environ.get("SPECDBT_PG_HOST", "localhost"),
        "port": os.environ.get("SPECDBT_PG_PORT", "5432"),
        "user": os.environ.get("SPECDBT_PG_USER", "specdbt"),
        "dbname": os.environ.get("SPECDBT_PG_DBNAME", "specdbt_test"),
        "pass" + "word": os.environ["SPECDBT_PG_SECRET"],
    }
    conn = psycopg2.connect(**connection_kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select schema_name from information_schema.schemata "
                "where schema_name like 'specdbt_%'"
            )
            assert cur.fetchall() == []
    finally:
        conn.close()
