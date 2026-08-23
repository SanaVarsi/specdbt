"""Cross-database SQL literal rendering for fixture rows executed against a
real dbt target (spec §5.1).

Numbers/booleans/NULL are rendered as raw ANSI SQL literals (portable across
DuckDB/Snowflake/Databricks). Strings are rendered as a Jinja call using the
exact chain dbt-core's own native unit-test fixture SQL generator uses
internally (found in the installed package at
dbt/include/global_project/macros/unit_test_sql/get_fixture_sql.sql):
dbt.string_literal(dbt.escape_single_quotes(value)) -- NOT dbt.string_literal()
alone, which performs no escaping at all (verified empirically:
default__string_literal is a bare '{{ value }}'; a raw apostrophe broke the
generated SQL in a spike before this fix).
"""

from __future__ import annotations

from specdbt.typing_utils import Scalar


def render_sql_literal(value: Scalar | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return (
        f'{{{{ dbt.string_literal(dbt.escape_single_quotes("{_escape_for_jinja_arg(value)}")) }}}}'
    )


def _escape_for_jinja_arg(value: str) -> str:
    """Escape for embedding inside a Jinja double-quoted string-literal
    argument -- this only protects the Jinja parser itself. SQL-level quote
    escaping happens later, at dbt compile time, via escape_single_quotes."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
