"""Generates and manages the temporary per-run macro file specdbt writes
into a target dbt project to materialize Given fixtures for real, and to
tear the ephemeral schema back down after (spec §5.1, §5.3).

The macro/model call under test is never written here -- it runs directly
via `dbt show --inline` (see adapters/dbt_adapter.py), not through this
file. Every statement here goes through a `{% set sql %}...{% endset %}`
block before `run_query(sql)` -- not an inlined `run_query("...")` string --
because fixture CTAS statements contain embedded `{{ dbt.string_literal(...) }}`
Jinja calls (from sql_literals.render_sql_literal / fixture_sql), which
themselves contain double quotes that would break an inlined double-quoted
argument. This pattern is verified against a real dbt-duckdb target.
"""

from __future__ import annotations

from pathlib import Path


def setup_macro_name(run_id: str) -> str:
    return f"_specdbt_{run_id}_setup"


def teardown_macro_name(run_id: str) -> str:
    return f"_specdbt_{run_id}_teardown"


def render_macro_file(run_id: str, schema: str, fixture_ctas_statements: list[str]) -> str:
    statements = [f"create schema if not exists {schema}", *fixture_ctas_statements]
    setup_blocks = "\n".join(
        f"  {{% set sql %}}\n  {statement}\n  {{% endset %}}\n  {{% do run_query(sql) %}}"
        for statement in statements
    )
    return (
        f"{{% macro {setup_macro_name(run_id)}() %}}\n"
        f"{setup_blocks}\n"
        f"{{% endmacro %}}\n\n"
        f"{{% macro {teardown_macro_name(run_id)}() %}}\n"
        f"  {{% set sql %}}\n"
        f"  drop schema if exists {schema} cascade\n"
        f"  {{% endset %}}\n"
        f"  {{% do run_query(sql) %}}\n"
        f"{{% endmacro %}}\n"
    )


def write_macro_file(project_dir: Path, run_id: str, content: str) -> Path:
    path = Path(project_dir) / "macros" / f"_specdbt_{run_id}.sql"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def delete_macro_file(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
