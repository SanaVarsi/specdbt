"""Textually substitute ref()/source() calls to known fixture names with a
real Relation object pointing at the ephemeral schema, before a macro/model
query is handed to dbt (spec §5.1).

A fixture is not a real project node, so dbt's own ref() resolution can't
find it -- this substitution happens in specdbt's own preprocessing, before
the text is compiled by dbt at all. Substituting with an actual
api.Relation.create(...) call (not a bare "schema.table" string) matters: a
spike found some macros (dbt_utils.star()) need a real Relation object to
introspect columns from, not text -- a bare string breaks them silently.

`database` (default None) threads the target's resolved catalog through, so
this relation matches the schema-DDL and fixture-CTAS relations built for
the same run (macro_file.py, fixture_sql.py) -- see relation_expr.py and the
macro-tier adapter-dispatch design spec.
"""

from __future__ import annotations

import re

from specdbt.dbt_integration.relation_expr import relation_expr

_REF_RE = re.compile(r"""ref\(\s*['"]([^'"]+)['"]\s*\)""")
_SOURCE_RE = re.compile(r"""source\(\s*['"][^'"]+['"]\s*,\s*['"]([^'"]+)['"]\s*\)""")


def substitute_fixture_refs(
    call_expr: str, schema: str, fixture_names: set[str], *, database: str | None = None
) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in fixture_names:
            return match.group(0)
        return relation_expr(schema=schema, identifier=name, database=database)

    call_expr = _SOURCE_RE.sub(_replace, call_expr)
    call_expr = _REF_RE.sub(_replace, call_expr)
    return call_expr
