"""Generates and manages the temporary per-run macro file specdbt writes
into a target dbt project to materialize Given fixtures for real, and to
tear the ephemeral schema back down after.

The macro/model call under test is never written here -- it runs directly
via `dbt show --inline` (see adapters/dbt_adapter.py), not through this
file.

Schema create/drop go through `adapter.create_schema(relation)` /
`adapter.drop_schema(relation)` -- BaseAdapter methods that already dispatch
to each adapter's correct DDL (verified present and `@available.parse_none`
in dbt-core's dbt/adapters/base/impl.py) -- instead of hand-written SQL, so
this works on any adapter, not just DuckDB (spec: macro-tier
adapter-dispatch design, 2026-08-30).

Fixture CTAS statements still go through a `{% set sql %}...{% endset %}`
block before `run_query(sql)` -- not an inlined `run_query("...")` string --
because they contain embedded `{{ dbt.cast(...) }}` Jinja calls (from
fixture_sql.py), which themselves contain double quotes that would break an
inlined double-quoted argument. This pattern is verified against a real
dbt-duckdb target.
"""

from __future__ import annotations

from pathlib import Path

from specdbt.dbt_integration.relation_expr import relation_expr


def setup_macro_name(run_id: str) -> str:
    return f"_specdbt_{run_id}_setup"


def teardown_macro_name(run_id: str) -> str:
    return f"_specdbt_{run_id}_teardown"


def render_macro_file(
    run_id: str,
    schema: str,
    fixture_ctas_statements: list[str],
    *,
    database: str | None = None,
) -> str:
    schema_relation = relation_expr(schema=schema, database=database)
    fixture_blocks = "\n".join(
        f"  {{% set sql %}}\n  {statement}\n  {{% endset %}}\n  {{% do run_query(sql) %}}"
        for statement in fixture_ctas_statements
    )
    return (
        f"{{% macro {setup_macro_name(run_id)}() %}}\n"
        f"  {{% do adapter.create_schema({schema_relation}) %}}\n"
        f"{fixture_blocks}\n"
        f"{{% endmacro %}}\n\n"
        f"{{% macro {teardown_macro_name(run_id)}() %}}\n"
        f"  {{% do adapter.drop_schema({schema_relation}) %}}\n"
        f"{{% endmacro %}}\n"
    )


def write_macro_file(project_dir: Path, run_id: str, content: str) -> Path:
    path = Path(project_dir) / "macros" / f"_specdbt_{run_id}.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def delete_macro_file(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
