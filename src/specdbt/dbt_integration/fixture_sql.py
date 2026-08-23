"""Render a Fixture as a CREATE TABLE ... AS VALUES statement, for real
execution against a dbt target (spec §5.1)."""

from __future__ import annotations

from specdbt.fixtures import Fixture
from specdbt.sql_literals import render_sql_literal


def render_fixture_ctas(schema: str, fixture: Fixture) -> str:
    """`fixture.rows` must be non-empty -- fixtures.build_fixture already
    enforces this via FixtureBuildError. Columns come from the first row's
    key order; all rows in one fixture are assumed to share the same
    columns, matching how the Gherkin data table they came from is shaped."""
    columns = list(fixture.rows[0].keys())
    values_rows = [
        "(" + ", ".join(render_sql_literal(row[col]) for col in columns) + ")"
        for row in fixture.rows
    ]
    columns_clause = ", ".join(columns)
    values_clause = ", ".join(values_rows)
    return (
        f"create table {schema}.{fixture.name} as ("
        f"select * from (values {values_clause}) as t({columns_clause}))"
    )
