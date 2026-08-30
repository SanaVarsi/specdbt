"""Render a Fixture as a CREATE TABLE ... AS SELECT ... UNION ALL statement,
for real execution against a dbt target (spec §5.1).

Column types are Python-value-derived (the only information available --
many fixture names aren't real manifest nodes, so
adapter.get_columns_in_relation isn't usable for the common case), but made
explicit and adapter-dispatched via dbt.cast(...) + a per-column dbt type
macro, instead of relying on implicit VALUES-clause type inference --
which is not guaranteed identical across engines (an all-NULL column,
mixed int/float precision). dbt.cast, not dbt.safe_cast: some adapters
implement safe_cast as a silently-NULL-on-failure try_cast, wrong for a
testing framework, which should fail loudly on a type mismatch. The
`select ... union all select ...` shape matches dbt-core's own native
unit-test fixture generator, avoiding VALUES's cross-engine column-aliasing
and implicit-coercion quirks (spec: macro-tier adapter-dispatch design,
2026-08-30).
"""

from __future__ import annotations

from specdbt.dbt_integration.relation_expr import relation_expr
from specdbt.fixtures import Fixture
from specdbt.sql_literals import sql_literal_expr


def _dbt_type_macro(values: list) -> str:
    if any(isinstance(v, float) for v in values):
        return "dbt.type_float()"
    if any(isinstance(v, str) for v in values):
        return "dbt.type_string()"
    if any(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "dbt.type_bigint()"
    if any(isinstance(v, bool) for v in values):
        return "dbt.type_boolean()"
    return "dbt.type_string()"  # all-NULL column


def render_fixture_ctas(schema: str, fixture: Fixture, *, database: str | None = None) -> str:
    """`fixture.rows` must be non-empty -- fixtures.build_fixture already
    enforces this via FixtureBuildError. Columns come from the first row's
    key order; all rows in one fixture are assumed to share the same
    columns, matching how the Gherkin data table they came from is shaped."""
    columns = list(fixture.rows[0].keys())
    column_types = {col: _dbt_type_macro([row[col] for row in fixture.rows]) for col in columns}

    select_rows = [
        "select "
        + ", ".join(
            f"{{{{ dbt.cast({sql_literal_expr(row[col])}, {column_types[col]}) }}}} as {col}"
            for col in columns
        )
        for row in fixture.rows
    ]
    body = "\nunion all\n".join(select_rows)
    relation = relation_expr(schema=schema, identifier=fixture.name, database=database)
    return f"create table {{{{ {relation} }}}} as (\n{body}\n)"
