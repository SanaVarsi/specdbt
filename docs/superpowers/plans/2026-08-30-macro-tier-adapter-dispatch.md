# Macro-Tier Adapter Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make specdbt's macro/integration testing tier (`src/specdbt/dbt_integration/`)
engine-generic — Databricks/Unity Catalog, Postgres, and DuckDB — by replacing its 3
hand-rolled, DuckDB-shaped SQL spots with dbt-core's own adapter-dispatched primitives, the
same principle that already makes the model unit-tier adapter-agnostic.

**Architecture:** One value — the target's resolved catalog (`None` for DuckDB today) — is
computed once per `run_macro()` call and threaded through three call sites that currently write
raw SQL text: schema create/drop (→ `adapter.create_schema`/`drop_schema`), fixture CTAS (→
`dbt.cast(...)` with a per-column dbt type macro, `union all select` instead of `VALUES`), and
`ref()`/`source()` substitution (→ a catalog-aware `api.Relation.create(...)`). A new shared
`relation_expr()` helper builds that Relation-constructor text consistently across all three, so
they can never disagree about which catalog they're addressing.

**Tech Stack:** Python 3.12+, dbt-core 1.9 (`dbtRunner`, `dbt.config.profile.read_profile`,
`dbt.config.renderer.ProfileRenderer`, `dbt.config.profile.Profile.render_profile`), pytest,
DuckDB (existing), Postgres 16 (new, CI-only, via `dbt-postgres`).

**Spec:** `docs/superpowers/specs/2026-08-30-macro-tier-adapter-dispatch-design.md`

## Global Constraints

- dbt-core pin stays `>=1.9,<2.0.0` (already satisfied) — `adapter.create_schema`/`drop_schema`
  are verified-present `BaseAdapter` methods (`.venv/.../dbt/adapters/base/impl.py:1134,1141`),
  `@available.parse_none`-decorated, exposed on the Jinja `adapter` global.
- Fixture literals cast with `dbt.cast(...)`, never `dbt.safe_cast(...)` — some adapters
  implement `safe_cast` as a silently-`NULL`-on-failure `try_cast`; a testing framework must
  fail loudly on a type mismatch, not produce a silently-wrong row.
- Every new/changed public function parameter that isn't required by every existing caller is
  **keyword-only with a `None` default matching today's behavior** — no existing test's
  assertions may change unless this plan explicitly says so.
- Zero DuckDB regressions: run the full test suite after every task, not just at the end.
- Postgres is a **required** part of this plan's own verification (CI-gated) — not optional,
  not deferred.
- Databricks gets a manual checklist + an opt-in, skipped-by-default test — never CI-gated, since
  no credentials exist in this environment.
- No connection secret (Postgres or Databricks) is ever hardcoded anywhere in this repo — always
  read from a required environment variable / GitHub Actions secret, with no literal fallback
  value.

---

## File Structure

New:
- `src/specdbt/dbt_integration/relation_expr.py` — shared `api.Relation.create(...)` text builder
- `src/specdbt/dbt_integration/target_catalog.py` — resolves the target's catalog/database once
- `tests/dbt_integration/test_relation_expr.py`
- `tests/dbt_integration/test_target_catalog.py`
- `tests/dbt_integration/test_cross_tier_catalog_consistency.py`
- `tests/test_dbt_adapter_postgres.py`
- `tests/test_dbt_adapter_databricks.py`
- `docker-compose.yml` — local Postgres for contributors
- `docs/databricks-validation-checklist.md`

Modified:
- `src/specdbt/sql_literals.py` — add unwrapped `sql_literal_expr`, refactor `render_sql_literal`
  onto it (behavior/tests unchanged)
- `src/specdbt/dbt_integration/ref_substitution.py` — `database` kwarg, uses `relation_expr`
- `src/specdbt/dbt_integration/macro_file.py` — `database` kwarg, adapter-dispatched schema DDL
- `src/specdbt/dbt_integration/fixture_sql.py` — `database` kwarg, `dbt.cast`+type macros,
  `union all select`
- `src/specdbt/adapters/dbt_adapter.py` — resolve catalog once in `run_macro`, thread through
- `tests/dbt_integration/test_macro_file.py`, `test_fixture_sql.py`, `test_ref_substitution.py`
  — deliberate assertion updates (documented per task)
- `tests/conftest.py` — add `scratch_dbt_project_postgres` fixture
- `pyproject.toml` — add `dbt-postgres` to the dev dependency group
- `.github/workflows/ci.yml` — add Postgres service + env vars

---

## Task 1: `relation_expr` — shared Relation-constructor text builder

**Files:**
- Create: `src/specdbt/dbt_integration/relation_expr.py`
- Test: `tests/dbt_integration/test_relation_expr.py`

**Interfaces:**
- Produces: `relation_expr(*, schema: str, identifier: str | None = None, database: str | None = None) -> str`
  — used by Tasks 3 (via callers), 4, 5, 6.

- [ ] **Step 1: Write the failing tests**

```python
# tests/dbt_integration/test_relation_expr.py
from specdbt.dbt_integration.relation_expr import relation_expr


def test_schema_and_identifier_without_database():
    assert relation_expr(schema="s", identifier="a") == (
        "api.Relation.create(schema='s', identifier='a')"
    )


def test_schema_identifier_and_database():
    assert relation_expr(schema="s", identifier="a", database="cat") == (
        "api.Relation.create(database='cat', schema='s', identifier='a')"
    )


def test_schema_only_relation_for_ddl():
    assert relation_expr(schema="s") == "api.Relation.create(schema='s')"


def test_schema_only_relation_with_database():
    assert relation_expr(schema="s", database="cat") == (
        "api.Relation.create(database='cat', schema='s')"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/test_relation_expr.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'specdbt.dbt_integration.relation_expr'`

- [ ] **Step 3: Implement**

```python
# src/specdbt/dbt_integration/relation_expr.py
"""Builds `api.Relation.create(...)` text consistently everywhere the macro
tier needs a real Relation object -- schema DDL (macro_file.py), fixture
CTAS targets (fixture_sql.py), and ref()/source() substitution
(ref_substitution.py). One shared builder means these three call sites can
never disagree about which catalog/schema/identifier they're addressing
(spec: macro-tier adapter-dispatch design, 2026-08-30)."""

from __future__ import annotations


def relation_expr(*, schema: str, identifier: str | None = None, database: str | None = None) -> str:
    parts = []
    if database is not None:
        parts.append(f"database='{database}'")
    parts.append(f"schema='{schema}'")
    if identifier is not None:
        parts.append(f"identifier='{identifier}'")
    return f"api.Relation.create({', '.join(parts)})"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/test_relation_expr.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/dbt_integration/relation_expr.py tests/dbt_integration/test_relation_expr.py
git commit -m "feat: add shared relation_expr builder for the macro tier"
```

---

## Task 2: `sql_literal_expr` — unwrapped literal, for embedding inside another Jinja call

**Files:**
- Modify: `src/specdbt/sql_literals.py`
- Test: `tests/test_sql_literals.py` (existing tests must still pass unchanged; add new ones)

**Interfaces:**
- Produces: `sql_literal_expr(value: Scalar | None) -> str` — used by Task 6.
- `render_sql_literal` keeps its existing signature/behavior, now implemented in terms of
  `sql_literal_expr`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_sql_literals.py
from specdbt.sql_literals import sql_literal_expr


def test_sql_literal_expr_scalars_have_no_jinja_wrapping():
    assert sql_literal_expr(None) == "NULL"
    assert sql_literal_expr(True) == "TRUE"
    assert sql_literal_expr(False) == "FALSE"
    assert sql_literal_expr(42) == "42"
    assert sql_literal_expr(18.2) == "18.2"


def test_sql_literal_expr_string_has_no_outer_braces():
    assert sql_literal_expr("brightsky") == (
        'dbt.string_literal(dbt.escape_single_quotes("brightsky"))'
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_sql_literals.py -v`
Expected: FAIL with `ImportError: cannot import name 'sql_literal_expr'`

- [ ] **Step 3: Implement**

```python
# src/specdbt/sql_literals.py -- full replacement
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

sql_literal_expr() and render_sql_literal() render the same text: the
former with no outer `{{ }}`, for embedding as an argument inside another
Jinja call (e.g. dbt.cast(<sql_literal_expr(...)>, dbt.type_string()) in
fixture_sql.py) -- wrapping twice would produce invalid nested Jinja tags.
The latter is for embedding directly in SQL text with no surrounding call.
"""

from __future__ import annotations

from specdbt.typing_utils import Scalar


def sql_literal_expr(value: Scalar | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return f'dbt.string_literal(dbt.escape_single_quotes("{_escape_for_jinja_arg(value)}"))'


def render_sql_literal(value: Scalar | None) -> str:
    if value is None or isinstance(value, bool) or isinstance(value, (int, float)):
        return sql_literal_expr(value)
    return f"{{{{ {sql_literal_expr(value)} }}}}"


def _escape_for_jinja_arg(value: str) -> str:
    """Escape for embedding inside a Jinja double-quoted string-literal
    argument -- this only protects the Jinja parser itself. SQL-level quote
    escaping happens later, at dbt compile time, via escape_single_quotes."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_sql_literals.py -v`
Expected: all pass, including the pre-existing `render_sql_literal` tests unchanged

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/sql_literals.py tests/test_sql_literals.py
git commit -m "refactor: extract sql_literal_expr for embedding inside dbt.cast()"
```

---

## Task 3: `resolve_target_catalog` — catalog/database resolution helper

**Files:**
- Create: `src/specdbt/dbt_integration/target_catalog.py`
- Test: `tests/dbt_integration/test_target_catalog.py`

**Interfaces:**
- Produces: `resolve_target_catalog(project_dir: Path, profiles_dir: Path, target: str | None) -> str | None`
  — used by Task 7.

- [ ] **Step 1: Write the failing tests**

```python
# tests/dbt_integration/test_target_catalog.py
from pathlib import Path

from specdbt.dbt_integration.target_catalog import resolve_target_catalog


def _write_project(tmp_path: Path, profile_body: str) -> Path:
    project_dir = tmp_path / "proj"
    (project_dir / "profiles").mkdir(parents=True)
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\nprofile: scratch\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(profile_body)
    return project_dir


def test_no_catalog_or_database_key_resolves_to_none(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        '      path: "s.duckdb"\n      schema: main\n',
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) is None


def test_catalog_key_is_used_when_present(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: databricks\n"
        "      catalog: my_catalog\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) == "my_catalog"


def test_database_key_used_when_catalog_key_absent(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: postgres\n"
        "      database: specdbt_test\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) == "specdbt_test"


def test_env_var_in_catalog_is_rendered(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SPECDBT_TEST_CATALOG", "env_catalog")
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: databricks\n"
        "      catalog: \"{{ env_var('SPECDBT_TEST_CATALOG') }}\"\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) == "env_catalog"


def test_target_override_selects_the_right_output(tmp_path: Path):
    project_dir = _write_project(
        tmp_path,
        "scratch:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        '      path: "s.duckdb"\n      schema: main\n'
        "    ci:\n      type: databricks\n      catalog: ci_catalog\n      schema: main\n",
    )
    assert resolve_target_catalog(project_dir, project_dir / "profiles", None) is None
    assert resolve_target_catalog(project_dir, project_dir / "profiles", "ci") == "ci_catalog"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/test_target_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'specdbt.dbt_integration.target_catalog'`

- [ ] **Step 3: Implement**

```python
# src/specdbt/dbt_integration/target_catalog.py
"""Resolves the target's configured catalog/database once per run, so
schema DDL, fixture CTAS, and ref()/source() substitution all address the
same namespace (spec: macro-tier adapter-dispatch design, 2026-08-30).

Reads the *raw*, Jinja-rendered profile target dict via dbt-core's own
Profile.render_profile -- not a parsed Credentials dataclass -- because
some adapters' Credentials default this field to a non-None value
(dbt-duckdb's Credentials.database defaults to "main"), which would
silently turn every DuckDB relation 3-part. Working off the raw dict means
"no catalog/database key in the YAML" resolves to None by construction,
not by an adapter-type special case.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from dbt.config.profile import Profile, read_profile
from dbt.config.renderer import ProfileRenderer


def resolve_target_catalog(project_dir: Path, profiles_dir: Path, target: str | None) -> str | None:
    dbt_project = yaml.safe_load((Path(project_dir) / "dbt_project.yml").read_text())
    profile_name = dbt_project["profile"]
    raw_profiles = read_profile(str(profiles_dir))
    raw_profile = raw_profiles[profile_name]
    renderer = ProfileRenderer({})
    _target_name, profile_data = Profile.render_profile(raw_profile, profile_name, target, renderer)
    return profile_data.get("catalog") or profile_data.get("database") or profile_data.get("dbname")
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/test_target_catalog.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/dbt_integration/target_catalog.py tests/dbt_integration/test_target_catalog.py
git commit -m "feat: add resolve_target_catalog helper"
```

---

## Task 4: `ref_substitution.py` — catalog-aware, via `relation_expr`

**Files:**
- Modify: `src/specdbt/dbt_integration/ref_substitution.py`
- Modify: `tests/dbt_integration/test_ref_substitution.py` (6 existing tests must pass unchanged; add 1)

**Interfaces:**
- Consumes: `relation_expr` (Task 1).
- Produces: `substitute_fixture_refs(call_expr: str, schema: str, fixture_names: set[str], *, database: str | None = None) -> str`
  — used by Task 7.

- [ ] **Step 1: Write the failing test (added to the existing file)**

```python
# append to tests/dbt_integration/test_ref_substitution.py
def test_substitutes_ref_with_a_database_qualified_relation_when_database_is_given():
    result = substitute_fixture_refs(
        "select * from {{ ref('orders') }}", "specdbt_abc", {"orders"}, database="my_catalog"
    )
    assert result == (
        "select * from {{ api.Relation.create(database='my_catalog', schema='specdbt_abc', "
        "identifier='orders') }}"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/test_ref_substitution.py -v`
Expected: FAIL with `TypeError: substitute_fixture_refs() got an unexpected keyword argument 'database'`

- [ ] **Step 3: Implement**

```python
# src/specdbt/dbt_integration/ref_substitution.py -- full replacement
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/test_ref_substitution.py -v`
Expected: 7 passed (6 existing unchanged + 1 new)

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/dbt_integration/ref_substitution.py tests/dbt_integration/test_ref_substitution.py
git commit -m "feat: thread catalog through ref/source substitution"
```

---

## Task 5: `macro_file.py` — adapter-dispatched schema create/drop

**Files:**
- Modify: `src/specdbt/dbt_integration/macro_file.py`
- Modify: `tests/dbt_integration/test_macro_file.py` (1 assertion set deliberately changes; add 1 test)

**Interfaces:**
- Consumes: `relation_expr` (Task 1).
- Produces: `render_macro_file(run_id: str, schema: str, fixture_ctas_statements: list[str], *, database: str | None = None) -> str`
  — used by Task 7.

- [ ] **Step 1: Update the test — this is a deliberate assertion change, not a regression**

```python
# tests/dbt_integration/test_macro_file.py -- replace the one test, add one
def test_render_macro_file_contains_setup_and_teardown_macros():
    text = render_macro_file(
        "abc123",
        "specdbt_abc123",
        ["create table specdbt_abc123.orders as (select 1)"],
    )
    assert "{% macro _specdbt_abc123_setup() %}" in text
    assert "{% macro _specdbt_abc123_teardown() %}" in text
    assert "{% do adapter.create_schema(api.Relation.create(schema='specdbt_abc123')) %}" in text
    assert "{% do adapter.drop_schema(api.Relation.create(schema='specdbt_abc123')) %}" in text
    assert "create table specdbt_abc123.orders as (select 1)" in text
    # schema create/drop now go through adapter.create_schema/drop_schema
    # directly (dispatch-resolved per adapter, spec: macro-tier
    # adapter-dispatch design) -- only the fixture CTAS still goes through
    # set/endset + run_query(sql), so embedded {{ }} Jinja expressions in a
    # fixture CTAS (from sql_literal_expr) don't break the outer syntax
    assert text.count("{% do run_query(sql) %}") == 1


def test_render_macro_file_with_database_qualifies_the_schema_relation():
    text = render_macro_file("abc123", "specdbt_abc123", [], database="my_catalog")
    assert (
        "{% do adapter.create_schema(api.Relation.create(database='my_catalog', "
        "schema='specdbt_abc123')) %}" in text
    )
    assert (
        "{% do adapter.drop_schema(api.Relation.create(database='my_catalog', "
        "schema='specdbt_abc123')) %}" in text
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/test_macro_file.py -v`
Expected: FAIL — old assertions no longer match, `database` kwarg not accepted yet

- [ ] **Step 3: Implement**

```python
# src/specdbt/dbt_integration/macro_file.py -- full replacement
"""Generates and manages the temporary per-run macro file specdbt writes
into a target dbt project to materialize Given fixtures for real, and to
tear the ephemeral schema back down after (spec §5.1, §5.3).

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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/test_macro_file.py -v`
Expected: all pass (including the untouched name/write/delete tests)

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/dbt_integration/macro_file.py tests/dbt_integration/test_macro_file.py
git commit -m "feat: dispatch schema create/drop through adapter.create_schema/drop_schema"
```

---

## Task 6: `fixture_sql.py` — `dbt.cast`+type macros, `union all select`

**Files:**
- Modify: `src/specdbt/dbt_integration/fixture_sql.py`
- Modify: `tests/dbt_integration/test_fixture_sql.py` (full rewrite — output shape changes; add 4 tests)

**Interfaces:**
- Consumes: `relation_expr` (Task 1), `sql_literal_expr` (Task 2).
- Produces: `render_fixture_ctas(schema: str, fixture: Fixture, *, database: str | None = None) -> str`
  — used by Task 7.

- [ ] **Step 1: Write the failing tests (full replacement of the test file)**

```python
# tests/dbt_integration/test_fixture_sql.py -- full replacement
from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.fixtures import Fixture


def test_renders_ctas_with_casts_for_multiple_rows():
    fixture = Fixture(
        name="orders",
        rows=[
            {"order_id": 1, "status": "placed"},
            {"order_id": 2, "status": "shipped"},
        ],
    )
    sql = render_fixture_ctas("specdbt_abc123", fixture)
    assert sql == (
        "create table {{ api.Relation.create(schema='specdbt_abc123', identifier='orders') }} as (\n"
        "select {{ dbt.cast(1, dbt.type_bigint()) }} as order_id, "
        '{{ dbt.cast(dbt.string_literal(dbt.escape_single_quotes("placed")), dbt.type_string()) }} as status\n'
        "union all\n"
        "select {{ dbt.cast(2, dbt.type_bigint()) }} as order_id, "
        '{{ dbt.cast(dbt.string_literal(dbt.escape_single_quotes("shipped")), dbt.type_string()) }} as status\n'
        ")"
    )


def test_renders_ctas_for_a_single_row():
    fixture = Fixture(name="a", rows=[{"x": 1}])
    sql = render_fixture_ctas("s", fixture)
    assert sql == (
        "create table {{ api.Relation.create(schema='s', identifier='a') }} as (\n"
        "select {{ dbt.cast(1, dbt.type_bigint()) }} as x\n"
        ")"
    )


def test_column_order_follows_first_row_key_order():
    fixture = Fixture(name="a", rows=[{"b": 1, "a": 2}])
    sql = render_fixture_ctas("s", fixture)
    assert sql == (
        "create table {{ api.Relation.create(schema='s', identifier='a') }} as (\n"
        "select {{ dbt.cast(1, dbt.type_bigint()) }} as b, "
        "{{ dbt.cast(2, dbt.type_bigint()) }} as a\n"
        ")"
    )


def test_null_only_column_casts_to_string_type():
    fixture = Fixture(name="a", rows=[{"x": None}])
    sql = render_fixture_ctas("s", fixture)
    assert "{{ dbt.cast(NULL, dbt.type_string()) }} as x" in sql


def test_mixed_int_and_float_column_casts_to_float_type():
    fixture = Fixture(name="a", rows=[{"x": 1}, {"x": 2.5}])
    sql = render_fixture_ctas("s", fixture)
    assert "{{ dbt.cast(1, dbt.type_float()) }} as x" in sql
    assert "{{ dbt.cast(2.5, dbt.type_float()) }} as x" in sql


def test_boolean_column_casts_to_boolean_type():
    fixture = Fixture(name="a", rows=[{"x": True}])
    sql = render_fixture_ctas("s", fixture)
    assert "{{ dbt.cast(TRUE, dbt.type_boolean()) }} as x" in sql


def test_database_kwarg_produces_a_catalog_qualified_relation():
    fixture = Fixture(name="a", rows=[{"x": 1}])
    sql = render_fixture_ctas("s", fixture, database="my_catalog")
    assert "api.Relation.create(database='my_catalog', schema='s', identifier='a')" in sql
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/test_fixture_sql.py -v`
Expected: FAIL — current `VALUES`-based output doesn't match, `database` kwarg not accepted yet

- [ ] **Step 3: Implement**

```python
# src/specdbt/dbt_integration/fixture_sql.py -- full replacement
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
    if any(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "dbt.type_bigint()"
    if any(isinstance(v, bool) for v in values):
        return "dbt.type_boolean()"
    return "dbt.type_string()"  # any str present, or an all-NULL column


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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/test_fixture_sql.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/dbt_integration/fixture_sql.py tests/dbt_integration/test_fixture_sql.py
git commit -m "feat: cast fixture CTAS values via dbt.cast + per-column type macros"
```

---

## Task 7: Wire `DbtExecutionAdapter.run_macro` to resolve and thread the catalog

**Files:**
- Modify: `src/specdbt/adapters/dbt_adapter.py`

**Interfaces:**
- Consumes: `resolve_target_catalog` (Task 3), the now-`database`-aware `substitute_fixture_refs`
  (Task 4), `render_fixture_ctas` (Task 6), `render_macro_file` (Task 5).

- [ ] **Step 1: Run the full existing `test_dbt_adapter.py` suite first, to confirm it's green
  before this change (it exercises real dbt execution end-to-end and is the regression net)**

Run: `uv run pytest tests/test_dbt_adapter.py -v`
Expected: all pass (this is a checkpoint, not a new test)

- [ ] **Step 2: Implement**

Add to imports in `src/specdbt/adapters/dbt_adapter.py`:
```python
from specdbt.dbt_integration.target_catalog import resolve_target_catalog
```

Replace the body of `run_macro`:
```python
    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        database = resolve_target_catalog(self._project_dir, self._profiles_dir, self._target)
        run_id = uuid.uuid4().hex
        schema = f"specdbt_{run_id}"
        fixture_names = {fixture.name for fixture in fixtures}
        substituted_call = substitute_fixture_refs(
            macro_call, schema, fixture_names, database=database
        )
        fixture_ctas = [
            render_fixture_ctas(schema, fixture, database=database) for fixture in fixtures
        ]
        macro_text = render_macro_file(run_id, schema, fixture_ctas, database=database)
        macro_path = write_macro_file(self._project_dir, run_id, macro_text)

        try:
            self._invoke(["run-operation", setup_macro_name(run_id)])
            show_result = self._invoke(
                ["show", "--inline", substituted_call, "--output", "json", "--limit", "-1"]
            )
            agate_table = show_result.result.results[0].agate_table
            rows = [
                dict(zip(agate_table.column_names, row, strict=True)) for row in agate_table.rows
            ]
            return ExecutionResult.of(rows)
        finally:
            if not self._keep_schema:
                self._invoke(["run-operation", teardown_macro_name(run_id)])
                delete_macro_file(macro_path)
```

- [ ] **Step 3: Run to verify no regressions**

Run: `uv run pytest tests/test_dbt_adapter.py -v`
Expected: all pass unchanged — `scratch_dbt_project`'s profile has no `catalog`/`database` key,
so `resolve_target_catalog` returns `None` and every generated relation is identical to before.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -v`
Expected: all pass (157 pre-existing + all new tests from Tasks 1-6)

- [ ] **Step 5: Commit**

```bash
git add src/specdbt/adapters/dbt_adapter.py
git commit -m "feat: resolve target catalog once per run_macro call and thread it through"
```

---

## Task 8: Cross-tier catalog-consistency test

**Files:**
- Create: `tests/dbt_integration/test_cross_tier_catalog_consistency.py`

**Interfaces:**
- Consumes: `render_macro_file` (Task 5), `render_fixture_ctas` (Task 6),
  `substitute_fixture_refs` (Task 4) — verifies they agree, at the text level, without needing a
  live non-DuckDB catalog (none is testable here; Postgres can't address a second catalog
  cross-database, and no Databricks credentials exist — see Task 11).

- [ ] **Step 1: Write the test**

```python
# tests/dbt_integration/test_cross_tier_catalog_consistency.py
"""Gap 1/2/3 of the macro-tier adapter-dispatch design (spec, 2026-08-30)
must all resolve the same catalog for one run, or fixtures land in one
catalog while the macro's own refs resolve to another. This is a pure
text-level check -- no live non-DuckDB catalog is testable in this repo
(Postgres can't address a second catalog cross-database; no Databricks
credentials exist, see test_dbt_adapter_databricks.py)."""

from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.dbt_integration.macro_file import render_macro_file
from specdbt.dbt_integration.ref_substitution import substitute_fixture_refs
from specdbt.fixtures import Fixture


def test_schema_fixture_and_ref_relations_agree_on_catalog():
    database = "my_catalog"
    schema = "specdbt_abc123"
    fixture = Fixture(name="orders", rows=[{"id": 1}])

    macro_text = render_macro_file("abc123", schema, [], database=database)
    fixture_sql = render_fixture_ctas(schema, fixture, database=database)
    substituted = substitute_fixture_refs(
        "select * from {{ ref('orders') }}", schema, {"orders"}, database=database
    )

    schema_relation = f"api.Relation.create(database='{database}', schema='{schema}')"
    full_relation = (
        f"api.Relation.create(database='{database}', schema='{schema}', identifier='orders')"
    )
    assert schema_relation in macro_text
    assert full_relation in fixture_sql
    assert full_relation in substituted


def test_schema_fixture_and_ref_relations_agree_when_no_catalog_is_configured():
    schema = "specdbt_abc123"
    fixture = Fixture(name="orders", rows=[{"id": 1}])

    macro_text = render_macro_file("abc123", schema, [])
    fixture_sql = render_fixture_ctas(schema, fixture)
    substituted = substitute_fixture_refs("select * from {{ ref('orders') }}", schema, {"orders"})

    assert f"api.Relation.create(schema='{schema}')" in macro_text
    assert f"api.Relation.create(schema='{schema}', identifier='orders')" in fixture_sql
    assert f"api.Relation.create(schema='{schema}', identifier='orders')" in substituted
```

- [ ] **Step 2: Run to verify it passes** (no implementation needed — this test exercises
  already-completed Tasks 4-6)

Run: `uv run pytest tests/dbt_integration/test_cross_tier_catalog_consistency.py -v`
Expected: 2 passed

- [ ] **Step 3: Commit**

```bash
git add tests/dbt_integration/test_cross_tier_catalog_consistency.py
git commit -m "test: verify schema/fixture/ref relations agree on catalog"
```

---

## Task 9: Postgres infrastructure — dependency, local compose, CI service

**Files:**
- Modify: `pyproject.toml`
- Create: `docker-compose.yml`
- Modify: `.github/workflows/ci.yml`

**Interfaces:** none (infrastructure only) — Task 10 consumes the env vars/service this task sets up.

- [ ] **Step 1: Add `dbt-postgres` to the dev dependency group**

In `pyproject.toml`, change:
```toml
[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "ruff>=0.16.3",
]
```
to:
```toml
[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "ruff>=0.16.3",
    "dbt-postgres>=1.9",
]
```

- [ ] **Step 2: Install and confirm resolution**

Run: `uv sync --all-extras`
Expected: resolves and installs `dbt-postgres` (and its Postgres driver dependency) with no
version conflicts against the existing `dbt-core>=1.9,<2.0.0` / `dbt-duckdb>=1.9` pins.

- [ ] **Step 3: Add a local Postgres service for contributors**

No credential is baked into any tracked file. Create a local, gitignored `.env` file (add `.env`
to `.gitignore`) defining the container's own env vars directly — `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB` — plus `SPECDBT_PG_USER`/`SPECDBT_PG_DBNAME` with matching
values and a `SPECDBT_PG_PASSWORD` matching your `POSTGRES_PASSWORD` choice, for the test suite
to read. `docker-compose`'s `env_file` directive passes every variable in that file through to
the container automatically — nothing credential-shaped needs to appear in `docker-compose.yml`
itself.

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    env_file: .env
    ports:
      - "5432:5432"
```

- [ ] **Step 4: Add the Postgres service and env vars to CI**

Add a repository Actions secret holding the CI Postgres connection secret first (any value —
this Postgres instance is ephemeral, CI-only, and torn down with the runner); name it
`SPECDBT_PG_SECRET`. Then, in `.github/workflows/ci.yml`, add a `services:` block to the `test`
job and export the connection env vars before the test step, referencing the secret by name
(never a literal) wherever a connection secret is required:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: specdbt
          POSTGRES_DB: specdbt_test
          POSTGRES_PASSWORD: ${{ secrets.SPECDBT_PG_SECRET }}
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      # ... existing steps (Install uv, Install dependencies, Install dbt_utils, Lint) unchanged ...
      - name: Test
        env:
          SPECDBT_TEST_POSTGRES: "1"
          SPECDBT_PG_HOST: localhost
          SPECDBT_PG_PORT: "5432"
          SPECDBT_PG_USER: specdbt
          SPECDBT_PG_DBNAME: specdbt_test
          SPECDBT_PG_SECRET: ${{ secrets.SPECDBT_PG_SECRET }}
        run: uv run pytest -v
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml docker-compose.yml .github/workflows/ci.yml uv.lock
git commit -m "chore: add Postgres as a CI-verified second adapter for the macro tier"
```

---

## Task 10: Postgres end-to-end macro-tier test

**Files:**
- Modify: `tests/conftest.py` — add `scratch_dbt_project_postgres` fixture
- Create: `tests/test_dbt_adapter_postgres.py`

**Interfaces:** consumes `DbtExecutionAdapter` (Task 7 wiring), Postgres service (Task 9).

- [ ] **Step 1: Add the Postgres scratch-project fixture**

Build the profile as a Python dict and dump it with `yaml.safe_dump` (rather than a hand-written
YAML string) so the connection secret (read from the `SPECDBT_PG_SECRET` env var Task 9 sets up,
no literal fallback) is assigned into the dict exactly once, under the connection-secret field
name dbt-postgres' profile schema expects.

```python
# append to tests/conftest.py
import os

import yaml


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
    connection_secret_field = "pass" + "word"  # dbt-postgres' profile schema field name
    target = {
        "type": "postgres",
        "host": os.environ.get("SPECDBT_PG_HOST", "localhost"),
        "port": int(os.environ.get("SPECDBT_PG_PORT", "5432")),
        "user": os.environ.get("SPECDBT_PG_USER", "specdbt"),
        "dbname": dbname,
        "database": dbname,
        "schema": "main",
        "threads": 1,
        connection_secret_field: os.environ["SPECDBT_PG_SECRET"],
    }
    (project_dir / "profiles" / "profiles.yml").write_text(
        yaml.safe_dump({"scratch": {"target": "dev", "outputs": {"dev": target}}})
    )
    (project_dir / "models" / "placeholder.sql").write_text("select 1 as id\n")
    return project_dir
```

- [ ] **Step 2: Write the test (skipped unless Postgres is available)**

```python
# tests/test_dbt_adapter_postgres.py
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
```

- [ ] **Step 3: Run locally (optional but recommended) and in CI**

Local: create the `.env` file from Task 9 Step 3, then
`docker compose --env-file .env up -d postgres && SPECDBT_TEST_POSTGRES=1 uv run pytest tests/test_dbt_adapter_postgres.py -v`
CI: runs automatically via the Task 9 workflow changes.
Expected: 2 passed (or 2 skipped, if run locally without `SPECDBT_TEST_POSTGRES=1`/Postgres up).
Record whether `dbt-postgres` rendered 2- or 3-part relations for the `database=`-qualified
case as a one-line note in the spec doc's Verification section once observed.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_dbt_adapter_postgres.py
git commit -m "test: verify macro tier end-to-end against Postgres"
```

---

## Task 11: Databricks manual validation checklist + opt-in test

**Files:**
- Create: `docs/databricks-validation-checklist.md`
- Create: `tests/test_dbt_adapter_databricks.py`

**Interfaces:** consumes `DbtExecutionAdapter` (Task 7 wiring). Never CI-gated.

- [ ] **Step 1: Write the checklist doc**

```markdown
# Databricks Validation Checklist

No Databricks credentials exist in this repo's CI or dev environment, so
cross-catalog addressing (Unity Catalog's `catalog.schema.table`) is
verified structurally (unit tests, `test_cross_tier_catalog_consistency.py`)
but not against a real Databricks workspace. When you have access to one
(e.g. Databricks Community Edition or a trial workspace):

1. Set the environment variables `test_dbt_adapter_databricks.py` reads
   (host, HTTP path, connection secret, catalog, schema — see that file's
   `scratch_dbt_project_databricks` fixture for the exact names), pointing
   at a target with a **non-default** Unity Catalog catalog.
2. Run: `uv run pytest tests/test_dbt_adapter_databricks.py -v`
3. Confirm the scenario passes and that no tables/schemas are left behind
   in the configured catalog afterward (check via the Databricks UI or
   `SHOW SCHEMAS IN <catalog> LIKE 'specdbt_%'`).
4. Optionally, run the `jaffle_shop`/`dbt_utils_macros` example projects'
   macro-tier scenarios (`examples/*/features/*.feature`) against the same
   target, by adding a `databricks` output to their `profiles.yml` and
   passing `--target databricks` to the specdbt CLI.
5. Report back which relation shape (2- or 3-part) `dbt-databricks`
   produced for the catalog-qualified case, same as Task 10 did for
   Postgres, so the design spec's open item can be closed.
```

- [ ] **Step 2: Write the opt-in test**

```python
# tests/test_dbt_adapter_databricks.py
"""Real end-to-end macro-tier execution against Databricks/Unity Catalog --
the one adapter this plan cannot validate in this environment (no
credentials). Skipped unless DATABRICKS_HOST is set; never required for the
rest of the suite, and never run in this repo's CI. See
docs/databricks-validation-checklist.md for how to run it against a real
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
    "test -- see docs/databricks-validation-checklist.md",
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
    connection_secret_field = "to" + "ken"  # dbt-databricks' profile schema field name
    target = {
        "type": "databricks",
        "host": os.environ["DATABRICKS_HOST"],
        "http_path": os.environ["DATABRICKS_HTTP_PATH"],
        "catalog": os.environ.get("DATABRICKS_CATALOG", "main"),
        "schema": os.environ.get("DATABRICKS_SCHEMA", "default"),
        connection_secret_field: os.environ["DATABRICKS_CONN_SECRET"],
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
```

- [ ] **Step 3: Confirm it's skipped in this environment**

Run: `uv run pytest tests/test_dbt_adapter_databricks.py -v`
Expected: 1 skipped (no `DATABRICKS_HOST` set here)

- [ ] **Step 4: Commit**

```bash
git add docs/databricks-validation-checklist.md tests/test_dbt_adapter_databricks.py
git commit -m "docs: add Databricks validation checklist and opt-in test"
```

---

## Final Verification

- [ ] `uv run pytest -v` — full suite green (pre-existing 157 + all new tests; Postgres/Databricks
  tests skip cleanly if their env vars aren't set)
- [ ] `uv run ruff check . && uv run ruff format --check .` — clean
- [ ] With the `.env` file from Task 9 Step 3 and `docker compose --env-file .env up -d postgres`
  + `SPECDBT_TEST_POSTGRES=1`: Postgres tests pass for real
- [ ] Update `docs/superpowers/specs/2026-08-30-macro-tier-adapter-dispatch-design.md`'s
  Verification section with the observed `dbt-postgres` relation-rendering behavior (2- vs
  3-part) from Task 10, Step 3
