# specdbt Phase 1 Plan A: Macro Integration Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make specdbt run a real dbt macro end-to-end against a real DuckDB
target — Given fixtures materialized as real tables, the macro's real
Jinja/SQL executed for real, results diffed against Then expectations,
ephemeral state torn down after — proving the part dbt itself cannot do
natively (dbt-core#10547, open, no native mechanism).

**Architecture:** One new concrete `ExecutionAdapter`, `DbtExecutionAdapter`,
drives `dbtRunner` (dbt-core's own programmatic CLI entrypoint) against
whatever target a real dbt project's profile points at. Given fixtures are
materialized into a per-scenario ephemeral schema (`specdbt_<uuid>`) via a
generated macro file using `run_query()` — proven reliable across three
spikes. The macro/model call under test is never wrapped in a result table —
it runs directly through `dbt show --inline`, the only readback path a spike
found to be reliable for every macro shape tried, including introspective
ones. Two new Gherkin grammar pieces (a macro `When` step, a row-table `Then`
step) sit on top of the existing parser/fixture/reporter layers unchanged.

**Tech Stack:** Python 3.12+, dbt-core 1.12.2, dbt-duckdb 1.11.0, polars
1.43.2, pytest, click, gherkin-official (all already installed and
security-checked).

**Spec:** `docs/superpowers/specs/2026-08-23-specdbt-phase1-design-v2.md`

## Global Constraints

- Dependencies already added and security-checked: `dbt-core>=1.9,<2.0.0`
  (resolved 1.12.2), `dbt-duckdb>=1.9` (resolved 1.11.0), `polars>=1.20`
  (resolved 1.43.2). OSV.dev and `pip-audit` clean — commit `16dc9db`. Do not
  re-check unless adding a new dependency beyond these.
- `dbt_utils` is installed into `examples/dbt_utils_macros/` via
  `packages.yml` + `dbt deps`, not pip — already verified against the real
  `dbt-labs/dbt-utils` GitHub org (active, not archived, 1791 stars). Already
  run once; `dbt_packages/` is gitignored, so a fresh clone needs `dbt deps`
  run again before Task 12's example scenarios work (Task 12 handles this).
- Never push — local git repo only, no remote configured.
- TDD discipline: red, green, commit — per task, in that order.
- `DbtExecutionAdapter.run_model` is a documented stub that raises clearly.
  Integration-tier **model** testing is an extension point, not implemented
  in this plan (spec §10) — only `run_macro` is real. Do not "helpfully"
  implement it; it would silently produce wrong results (spec §10 explains
  why: a model's own `ref()`s are inside its SQL file, which this mechanism
  never touches).
- Never trust a `dbtRunner` "success: True" without verifying against the
  real `.duckdb` file the first time a new code path is written. Two
  unrelated cases in this exact mechanism reported success while silently
  not persisting (spec §5.1) — the mechanism specified below is what
  survived that scrutiny; trust it, but verify anew if you deviate from it.
- Always pass `--no-send-anonymous-usage-stats` on every `dbtRunner`
  invocation specdbt makes on the user's behalf.
- Branch: `phase-1-dbt-execution` (already created; dependency commits
  already on it). Keep committing here; do not merge to `main` until this
  plan's Definition of Done (Task 14) passes.
- Existing 60 Phase 0 tests must keep passing throughout — run the full
  suite (not just the new file) after every task.

---

### Task 1: `run_macro` on `ExecutionAdapter` and `FakeAdapter`

**Files:**
- Modify: `src/specdbt/adapters/base.py`
- Modify: `src/specdbt/adapters/fake_adapter.py`
- Test: `tests/test_adapters.py`

**Interfaces:**
- Produces: `ExecutionAdapter.run_macro(self, macro_call: str, fixtures:
  list[Fixture]) -> ExecutionResult` (abstract). `FakeAdapter.run_macro`
  (concrete, registry lookup identical in spirit to `run_model`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_adapters.py`:

```python
def test_fake_adapter_run_macro_returns_registered_result():
    adapter = FakeAdapter()
    result = ExecutionResult.of(rows=[{"a": 1}])
    adapter.register("select 1 as a", result)
    assert adapter.run_macro("select 1 as a", fixtures=[]) is result


def test_fake_adapter_run_macro_raises_for_unregistered_call():
    adapter = FakeAdapter()
    with pytest.raises(ModelNotRegisteredError):
        adapter.run_macro("select 1", fixtures=[])
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_adapters.py -v`
Expected: FAIL — `AttributeError: 'FakeAdapter' object has no attribute 'run_macro'`

- [ ] **Step 3: Implement**

In `src/specdbt/adapters/base.py`, add below the existing `run_model`
abstract method (inside the `ExecutionAdapter` class body):

```python
    @abstractmethod
    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        """Run `macro_call` -- a complete, real Jinja/SQL query string (not
        just a macro call expression; see spec §5.1/§6), with the given
        fixtures' ref()/source() substituted for their ephemeral relations
        -- and return the resulting rows."""
        raise NotImplementedError
```

Rewrite `src/specdbt/adapters/fake_adapter.py` in full:

```python
"""Phase 0's only concrete adapter: returns pre-registered canned results,
never computes anything from the fixtures it's given. Proves the pipeline
plumbing; DbtExecutionAdapter (Phase 1) provides real correctness for macros.
"""

from __future__ import annotations

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.fixtures import Fixture


class ModelNotRegisteredError(KeyError):
    """Raised when run_model()/run_macro() is asked for a name with no
    canned result registered."""


class FakeAdapter(ExecutionAdapter):
    def __init__(self) -> None:
        self._canned_results: dict[str, ExecutionResult] = {}

    def register(self, name: str, result: ExecutionResult) -> None:
        """Registers a canned result under `name` -- a model name
        (run_model) or the exact macro-call string a scenario's When step
        uses (run_macro). Same registry either way; FakeAdapter doesn't
        distinguish between the two kinds of caller."""
        self._canned_results[name] = result

    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        return self._lookup(model_name)

    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        return self._lookup(macro_call)

    def _lookup(self, name: str) -> ExecutionResult:
        try:
            return self._canned_results[name]
        except KeyError:
            raise ModelNotRegisteredError(
                f"no canned result registered for {name!r}"
            ) from None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_adapters.py -v`
Expected: PASS, all tests including the pre-existing ones.

- [ ] **Step 5: Full suite + commit**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check .`
Expected: all pass.

```bash
git add src/specdbt/adapters/base.py src/specdbt/adapters/fake_adapter.py tests/test_adapters.py
git commit -m "feat: add run_macro to ExecutionAdapter and FakeAdapter"
```

---

### Task 2: Cross-database SQL literal rendering

**Files:**
- Create: `src/specdbt/sql_literals.py`
- Test: `tests/test_sql_literals.py`

**Interfaces:**
- Consumes: `specdbt.typing_utils.Scalar` (existing: `bool | int | float | str`)
- Produces: `render_sql_literal(value: Scalar | None) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sql_literals.py`:

```python
from specdbt.sql_literals import render_sql_literal


def test_renders_none_as_null():
    assert render_sql_literal(None) == "NULL"


def test_renders_true_and_false():
    assert render_sql_literal(True) == "TRUE"
    assert render_sql_literal(False) == "FALSE"


def test_renders_int_and_float_as_raw_literals():
    assert render_sql_literal(42) == "42"
    assert render_sql_literal(18.2) == "18.2"
    assert render_sql_literal(-5) == "-5"


def test_renders_plain_string():
    assert render_sql_literal("brightsky") == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("brightsky")) }}'
    )


def test_escapes_single_quote_for_the_sql_layer_via_dbt_own_macros():
    # Correctness of the *SQL-level* escape (' -> '') is dbt's own job, via
    # escape_single_quotes -- verified empirically against a real dbt-duckdb
    # target in test_dbt_adapter.py::test_run_macro_handles_string_values_with_quotes.
    # This test only pins the *text* specdbt generates.
    assert render_sql_literal("O'Brien") == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("O\'Brien")) }}'
    )


def test_escapes_double_quote_and_backslash_for_the_jinja_argument_itself():
    assert render_sql_literal('say "hi"') == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("say \\"hi\\"")) }}'
    )
    assert render_sql_literal("back\\slash") == (
        '{{ dbt.string_literal(dbt.escape_single_quotes("back\\\\slash")) }}'
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_sql_literals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.sql_literals'`

- [ ] **Step 3: Implement**

Create `src/specdbt/sql_literals.py`:

```python
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
        "{{ dbt.string_literal(dbt.escape_single_quotes("
        f'"{_escape_for_jinja_arg(value)}"'
        ")) }}"
    )


def _escape_for_jinja_arg(value: str) -> str:
    """Escape for embedding inside a Jinja double-quoted string-literal
    argument -- this only protects the Jinja parser itself. SQL-level quote
    escaping happens later, at dbt compile time, via escape_single_quotes."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_sql_literals.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/sql_literals.py tests/test_sql_literals.py
git commit -m "feat: cross-database SQL literal rendering (sql_literals.render_sql_literal)"
```

---

### Task 3: Fixture-to-CTAS SQL rendering

**Files:**
- Create: `src/specdbt/dbt_integration/__init__.py` (empty)
- Create: `src/specdbt/dbt_integration/fixture_sql.py`
- Test: `tests/dbt_integration/__init__.py` (empty)
- Test: `tests/dbt_integration/test_fixture_sql.py`

**Interfaces:**
- Consumes: `specdbt.fixtures.Fixture` (existing), `render_sql_literal` (Task 2)
- Produces: `render_fixture_ctas(schema: str, fixture: Fixture) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/dbt_integration/__init__.py` (empty file).

Create `tests/dbt_integration/test_fixture_sql.py`:

```python
from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.fixtures import Fixture


def test_renders_ctas_with_values_for_multiple_rows():
    fixture = Fixture(
        name="orders",
        rows=[
            {"order_id": 1, "status": "placed"},
            {"order_id": 2, "status": "shipped"},
        ],
    )
    sql = render_fixture_ctas("specdbt_abc123", fixture)
    assert sql == (
        "create table specdbt_abc123.orders as ("
        "select * from (values "
        '(1, {{ dbt.string_literal(dbt.escape_single_quotes("placed")) }}), '
        '(2, {{ dbt.string_literal(dbt.escape_single_quotes("shipped")) }})'
        ") as t(order_id, status))"
    )


def test_renders_ctas_for_a_single_row():
    fixture = Fixture(name="a", rows=[{"x": 1}])
    sql = render_fixture_ctas("s", fixture)
    assert sql == "create table s.a as (select * from (values (1)) as t(x))"


def test_column_order_follows_first_row_key_order():
    fixture = Fixture(name="a", rows=[{"b": 1, "a": 2}])
    sql = render_fixture_ctas("s", fixture)
    assert "as t(b, a)" in sql
    assert "(1, 2)" in sql
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.dbt_integration'`

- [ ] **Step 3: Implement**

Create `src/specdbt/dbt_integration/__init__.py` (empty).

Create `src/specdbt/dbt_integration/fixture_sql.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/ -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/dbt_integration/ tests/dbt_integration/
git commit -m "feat: render_fixture_ctas -- fixture rows to CREATE TABLE ... AS VALUES"
```

---

### Task 4: `ref()`/`source()` substitution for fixture names

**Files:**
- Create: `src/specdbt/dbt_integration/ref_substitution.py`
- Test: `tests/dbt_integration/test_ref_substitution.py`

**Interfaces:**
- Produces: `substitute_fixture_refs(call_expr: str, schema: str,
  fixture_names: set[str]) -> str`

- [ ] **Step 1: Write the failing tests**

Create `tests/dbt_integration/test_ref_substitution.py`:

```python
from specdbt.dbt_integration.ref_substitution import substitute_fixture_refs


def test_substitutes_ref_to_a_known_fixture_with_a_relation_object():
    result = substitute_fixture_refs(
        "select * from {{ ref('orders') }}", "specdbt_abc", {"orders"}
    )
    assert result == (
        "select * from {{ api.Relation.create(schema='specdbt_abc', "
        "identifier='orders') }}"
    )


def test_substitutes_ref_used_as_a_macro_argument():
    result = substitute_fixture_refs(
        "{{ dbt_utils.star(from=ref('orders')) }}", "specdbt_abc", {"orders"}
    )
    assert result == (
        "{{ dbt_utils.star(from=api.Relation.create(schema='specdbt_abc', "
        "identifier='orders')) }}"
    )


def test_substitutes_source_to_a_known_fixture():
    result = substitute_fixture_refs(
        "select * from {{ source('raw', 'orders') }}", "specdbt_abc", {"orders"}
    )
    assert result == (
        "select * from {{ api.Relation.create(schema='specdbt_abc', "
        "identifier='orders') }}"
    )


def test_leaves_ref_to_an_unknown_name_untouched():
    result = substitute_fixture_refs(
        "select * from {{ ref('real_model') }}", "specdbt_abc", {"orders"}
    )
    assert result == "select * from {{ ref('real_model') }}"


def test_leaves_a_call_with_no_ref_or_source_untouched():
    result = substitute_fixture_refs(
        "{{ dbt_utils.generate_surrogate_key(['a', 'b']) }}", "specdbt_abc", {"orders"}
    )
    assert result == "{{ dbt_utils.generate_surrogate_key(['a', 'b']) }}"


def test_substitutes_double_quoted_ref():
    result = substitute_fixture_refs(
        'select * from {{ ref("orders") }}', "specdbt_abc", {"orders"}
    )
    assert result == (
        "select * from {{ api.Relation.create(schema='specdbt_abc', "
        "identifier='orders') }}"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/test_ref_substitution.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Create `src/specdbt/dbt_integration/ref_substitution.py`:

```python
"""Textually substitute ref()/source() calls to known fixture names with a
real Relation object pointing at the ephemeral schema, before a macro/model
query is handed to dbt (spec §5.1).

A fixture is not a real project node, so dbt's own ref() resolution can't
find it -- this substitution happens in specdbt's own preprocessing, before
the text is compiled by dbt at all. Substituting with an actual
api.Relation.create(...) call (not a bare "schema.table" string) matters: a
spike found some macros (dbt_utils.star()) need a real Relation object to
introspect columns from, not text -- a bare string breaks them silently.
"""

from __future__ import annotations

import re

_REF_RE = re.compile(r"""ref\(\s*['"]([^'"]+)['"]\s*\)""")
_SOURCE_RE = re.compile(r"""source\(\s*['"][^'"]+['"]\s*,\s*['"]([^'"]+)['"]\s*\)""")


def substitute_fixture_refs(call_expr: str, schema: str, fixture_names: set[str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in fixture_names:
            return match.group(0)
        return f"api.Relation.create(schema='{schema}', identifier='{name}')"

    call_expr = _SOURCE_RE.sub(_replace, call_expr)
    call_expr = _REF_RE.sub(_replace, call_expr)
    return call_expr
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/test_ref_substitution.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/dbt_integration/ref_substitution.py tests/dbt_integration/test_ref_substitution.py
git commit -m "feat: substitute_fixture_refs -- ref()/source() to ephemeral Relation"
```

---

### Task 5: Generated macro file (setup + teardown)

**Files:**
- Create: `src/specdbt/dbt_integration/macro_file.py`
- Test: `tests/dbt_integration/test_macro_file.py`

**Interfaces:**
- Produces: `setup_macro_name(run_id: str) -> str`,
  `teardown_macro_name(run_id: str) -> str`,
  `render_macro_file(run_id: str, schema: str, fixture_ctas_statements:
  list[str]) -> str`, `write_macro_file(project_dir: Path, run_id: str,
  content: str) -> Path`, `delete_macro_file(path: Path) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/dbt_integration/test_macro_file.py`:

```python
from pathlib import Path

from specdbt.dbt_integration.macro_file import (
    delete_macro_file,
    render_macro_file,
    setup_macro_name,
    teardown_macro_name,
    write_macro_file,
)


def test_macro_names_are_derived_from_run_id():
    assert setup_macro_name("abc123") == "_specdbt_abc123_setup"
    assert teardown_macro_name("abc123") == "_specdbt_abc123_teardown"


def test_render_macro_file_contains_setup_and_teardown_macros():
    text = render_macro_file(
        "abc123",
        "specdbt_abc123",
        ["create table specdbt_abc123.orders as (select 1)"],
    )
    assert "{% macro _specdbt_abc123_setup() %}" in text
    assert "{% macro _specdbt_abc123_teardown() %}" in text
    assert "create schema if not exists specdbt_abc123" in text
    assert "create table specdbt_abc123.orders as (select 1)" in text
    assert "drop schema if exists specdbt_abc123 cascade" in text
    # each statement goes through set/endset then run_query(sql) -- not an
    # inlined double-quoted string -- so embedded {{ }} Jinja expressions in
    # a fixture CTAS (from render_sql_literal) don't break the outer syntax
    assert text.count("{% do run_query(sql) %}") == 3  # schema + 1 fixture + teardown


def test_write_and_delete_macro_file(tmp_path: Path):
    path = write_macro_file(tmp_path, "abc123", "-- content --")
    assert path == tmp_path / "macros" / "_specdbt_abc123.sql"
    assert path.read_text() == "-- content --"
    delete_macro_file(path)
    assert not path.exists()


def test_delete_macro_file_is_a_noop_if_already_gone(tmp_path: Path):
    delete_macro_file(tmp_path / "macros" / "does_not_exist.sql")  # must not raise
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/dbt_integration/test_macro_file.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Create `src/specdbt/dbt_integration/macro_file.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/dbt_integration/test_macro_file.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/dbt_integration/macro_file.py tests/dbt_integration/test_macro_file.py
git commit -m "feat: generated macro file for fixture setup/teardown"
```

---

### Task 6: `DbtExecutionAdapter` skeleton + scratch dbt project test fixture

**Files:**
- Create: `src/specdbt/adapters/dbt_adapter.py`
- Create: `tests/conftest.py`
- Test: `tests/test_dbt_adapter.py`

**Interfaces:**
- Consumes: `ExecutionAdapter`, `ExecutionResult` (base.py), `Fixture`
  (fixtures.py)
- Produces: `DbtExecutionAdapter(project_dir, profiles_dir, *, target=None,
  allow_any_schema=False, keep_schema=False)`; exceptions
  `DbtInvocationError`, `ProdSchemaGuardError`,
  `ModelIntegrationTierNotImplementedError`; pytest fixture
  `scratch_dbt_project(tmp_path) -> Path`

- [ ] **Step 1: Write the failing tests**

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures. `scratch_dbt_project` is used by every test that
needs to run real dbt (spec §5.1's mechanism) against a minimal, disposable
DuckDB-backed project -- no network, no dbt_utils, just enough scaffolding
for dbtRunner to work."""

from pathlib import Path

import pytest


@pytest.fixture
def scratch_dbt_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "scratch_project"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: scratch\nversion: "1.0.0"\nconfig-version: 2\n'
        'profile: scratch\nmodel-paths: ["models"]\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(
        "scratch:\n"
        "  target: dev\n"
        "  outputs:\n"
        "    dev:\n"
        "      type: duckdb\n"
        '      path: "scratch.duckdb"\n'
        "      schema: main\n"
    )
    (project_dir / "models" / "placeholder.sql").write_text("select 1 as id\n")
    return project_dir
```

Create `tests/test_dbt_adapter.py`:

```python
from pathlib import Path

import pytest

from specdbt.adapters.dbt_adapter import (
    DbtExecutionAdapter,
    ModelIntegrationTierNotImplementedError,
    ProdSchemaGuardError,
)


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_dbt_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.adapters.dbt_adapter'`

- [ ] **Step 3: Implement**

Create `src/specdbt/adapters/dbt_adapter.py` (the `run_macro` body is a
placeholder `raise NotImplementedError` for now — Task 7 replaces it):

```python
"""Real execution against whatever dbt target a project's profile points at,
via dbtRunner -- the only concrete ExecutionAdapter that computes real
results instead of returning canned ones (spec §3, §5)."""

from __future__ import annotations

from pathlib import Path

from dbt.cli.main import dbtRunner

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.fixtures import Fixture


class DbtInvocationError(RuntimeError):
    """Raised when a dbtRunner.invoke() call fails."""


class ProdSchemaGuardError(RuntimeError):
    """Raised when the configured target name looks like production and
    allow_any_schema was not passed."""


class ModelIntegrationTierNotImplementedError(NotImplementedError):
    """Raised by run_model -- see spec §10. The macro-file substitution
    mechanism only works because a macro call's ref()/source() arguments
    are text specdbt's own call site controls. A model's ref()s are inside
    its own SQL file, which this mechanism never touches -- running it for
    real would use whatever real state those refs already resolve to, not
    the scenario's fixtures, silently producing wrong results."""


class DbtExecutionAdapter(ExecutionAdapter):
    def __init__(
        self,
        project_dir: Path,
        profiles_dir: Path,
        *,
        target: str | None = None,
        allow_any_schema: bool = False,
        keep_schema: bool = False,
    ) -> None:
        if target and "prod" in target.lower() and not allow_any_schema:
            raise ProdSchemaGuardError(
                f"target {target!r} looks like production -- refusing to run. "
                "Pass allow_any_schema=True (CLI: --allow-any-schema) if this "
                "is really what you want."
            )
        self._project_dir = Path(project_dir)
        self._profiles_dir = Path(profiles_dir)
        self._target = target
        self._keep_schema = keep_schema
        self._runner = dbtRunner()

    def run_model(self, model_name: str, fixtures: list[Fixture]) -> ExecutionResult:
        raise ModelIntegrationTierNotImplementedError(
            f"DbtExecutionAdapter.run_model({model_name!r}) is an extension "
            "point, not implemented -- see spec §2/§3/§10. Model testing "
            "today goes through FakeAdapter, or (a future plan) the unit tier."
        )

    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        raise NotImplementedError("implemented in Task 7")

    def _invoke(self, args: list[str]):
        full_args = [
            *args,
            "--project-dir",
            str(self._project_dir),
            "--profiles-dir",
            str(self._profiles_dir),
            "--quiet",
            "--no-send-anonymous-usage-stats",
        ]
        if self._target:
            full_args += ["--target", self._target]
        result = self._runner.invoke(full_args)
        if not result.success:
            raise DbtInvocationError(f"dbt {args[0]} failed: {result.exception}")
        return result
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_dbt_adapter.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/adapters/dbt_adapter.py tests/conftest.py tests/test_dbt_adapter.py
git commit -m "feat: DbtExecutionAdapter skeleton -- ctor, prod guard, run_model stub"
```

---

### Task 7: `DbtExecutionAdapter.run_macro` — the real mechanism

**Files:**
- Modify: `src/specdbt/adapters/dbt_adapter.py`
- Test: `tests/test_dbt_adapter.py`

**Interfaces:**
- Consumes: `render_fixture_ctas` (Task 3), `substitute_fixture_refs` (Task
  4), `render_macro_file`/`setup_macro_name`/`teardown_macro_name`/
  `write_macro_file`/`delete_macro_file` (Task 5)
- Produces: working `DbtExecutionAdapter.run_macro`

This task's tests actually invoke `dbtRunner` against a real DuckDB file via
`scratch_dbt_project` — slower than the rest of the suite (still well under
a second each) but this is deliberate: it's the only thing that actually
proves the mechanism, per the Global Constraints note about not trusting
reported success.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dbt_adapter.py`:

```python
import duckdb

from specdbt.adapters.dbt_adapter import DbtExecutionAdapter, DbtInvocationError
from specdbt.fixtures import Fixture


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
        "select order_id, upper(status) as status "
        "from {{ ref('orders') }} order by order_id",
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
        "select schema_name from information_schema.schemata "
        "where schema_name like 'specdbt_%'"
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
        "select schema_name from information_schema.schemata "
        "where schema_name like 'specdbt_%'"
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
```

(`import pytest` and `from pathlib import Path` already appear at the top of
this file from Task 6 — add `import duckdb`, `from specdbt.fixtures import
Fixture`, and `DbtInvocationError` to the existing import lines rather than
duplicating them.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_dbt_adapter.py -v`
Expected: FAIL — `NotImplementedError: implemented in Task 7`

- [ ] **Step 3: Implement**

In `src/specdbt/adapters/dbt_adapter.py`, replace the top-of-file imports —
add `import uuid` as the first stdlib import, and the three
`dbt_integration` imports alongside the existing local imports:

```python
from __future__ import annotations

import uuid
from pathlib import Path

from dbt.cli.main import dbtRunner

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.dbt_integration.fixture_sql import render_fixture_ctas
from specdbt.dbt_integration.macro_file import (
    delete_macro_file,
    render_macro_file,
    setup_macro_name,
    teardown_macro_name,
    write_macro_file,
)
from specdbt.dbt_integration.ref_substitution import substitute_fixture_refs
from specdbt.fixtures import Fixture
```

Then replace the `run_macro` method body:

```python
    def run_macro(self, macro_call: str, fixtures: list[Fixture]) -> ExecutionResult:
        run_id = uuid.uuid4().hex
        schema = f"specdbt_{run_id}"
        fixture_names = {fixture.name for fixture in fixtures}
        substituted_call = substitute_fixture_refs(macro_call, schema, fixture_names)
        fixture_ctas = [render_fixture_ctas(schema, fixture) for fixture in fixtures]
        macro_text = render_macro_file(run_id, schema, fixture_ctas)
        macro_path = write_macro_file(self._project_dir, run_id, macro_text)

        try:
            self._invoke(["run-operation", setup_macro_name(run_id)])
            show_result = self._invoke(
                ["show", "--inline", substituted_call, "--output", "json", "--limit", "-1"]
            )
            agate_table = show_result.result.results[0].agate_table
            rows = [
                dict(zip(agate_table.column_names, row, strict=True))
                for row in agate_table.rows
            ]
            return ExecutionResult.of(rows)
        finally:
            if not self._keep_schema:
                self._invoke(["run-operation", teardown_macro_name(run_id)])
                delete_macro_file(macro_path)
```

The rest of the class (`__init__`, `run_model`, `_invoke`) is unchanged from
Task 6.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_dbt_adapter.py -v`
Expected: PASS, all 9 tests in the file (4 from Task 6, 5 new).

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/adapters/dbt_adapter.py tests/test_dbt_adapter.py
git commit -m "feat: DbtExecutionAdapter.run_macro -- real end-to-end macro execution"
```

---

### Task 8: Gherkin grammar — macro `When` step

**Files:**
- Modify: `src/specdbt/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces: a `_WHEN_MACRO_RE` pattern and routing to `adapter.run_macro()`
  in `_run_scenario`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_runner.py`:

```python
MACRO_WHEN_SOURCE = """Feature: Macro when step

  Scenario: A macro call runs
    Given the following rows in "orders":
      | order_id | status |
      | 1        | placed |
    When the "select order_id from orders" macro runs
    Then "select order_id from orders" should have 1 row
"""


def test_run_feature_text_routes_macro_when_step_to_run_macro():
    adapter = FakeAdapter()
    adapter.register(
        "select order_id from orders", ExecutionResult.of(rows=[{"order_id": 1}])
    )
    report = run_feature_text(MACRO_WHEN_SOURCE, adapter)
    assert report.scenarios[0].passed is True


def test_run_feature_text_reports_unregistered_macro_as_a_failed_when_step():
    adapter = FakeAdapter()
    report = run_feature_text(MACRO_WHEN_SOURCE, adapter)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert scenario.steps[-1].passed is False
```

(This reuses Phase 0's existing prose `Then "X" should have N rows` pattern
against a macro-call name — proving the macro `When` step routes correctly
in isolation, independent of Task 9's new row-table `Then` step.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_runner.py -v`
Expected: FAIL — `ValueError: no When-step pattern matches: 'the "select order_id from orders" macro runs'`

- [ ] **Step 3: Implement**

In `src/specdbt/runner.py`, add below the existing `_WHEN_MODEL_RE`:

```python
_WHEN_MACRO_RE = re.compile(r'the "(.+)" macro runs$')
```

Replace the `elif step.type == "Action":` branch inside `_run_scenario`:

```python
            elif step.type == "Action":
                model_match = _WHEN_MODEL_RE.search(step.text)
                if model_match is not None:
                    model_name = model_match.group(1)
                    results[model_name] = adapter.run_model(model_name, list(fixtures.values()))
                    last_model = model_name
                else:
                    macro_match = _WHEN_MACRO_RE.search(step.text)
                    if macro_match is None:
                        raise ValueError(f"no When-step pattern matches: {step.text!r}")
                    macro_call = macro_match.group(1)
                    results[macro_call] = adapter.run_macro(macro_call, list(fixtures.values()))
                    last_model = macro_call
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/runner.py tests/test_runner.py
git commit -m "feat: macro When-step grammar -- routes to adapter.run_macro()"
```

---

### Task 9: Gherkin grammar — row-table `Then` step (canonical for both tiers)

**Files:**
- Modify: `src/specdbt/assertions.py`
- Modify: `src/specdbt/runner.py`
- Test: `tests/test_assertions.py`
- Test: `tests/test_runner.py`

Per spec §6: this is the **canonical** `Then` form (works for both unit and
integration tier); Phase 0's prose assertions remain supported as additional
integration-tier steps.

**Interfaces:**
- Modifies: `evaluate_then_step(text: str, ctx: ThenContext, table:
  list[list[str]] | None = None) -> None` — new optional `table` parameter,
  default `None` so every existing call site keeps working unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_assertions.py`:

```python
def test_produces_rows_passes_on_exact_match():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "a"], ["2", "b"]]
    evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)


def test_produces_rows_fails_on_mismatch():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "ZZZ"]]
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)


def test_produces_rows_requires_a_table():
    ctx = ThenContext(results={"m": ExecutionResult.of(rows=[])}, last_model="m")
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the "m" should produce the following rows:', ctx, table=None)


def test_produces_rows_works_with_a_macro_call_as_the_name():
    result = ExecutionResult.of(rows=[{"a": 1}])
    ctx = ThenContext(results={"select 1 as a": result}, last_model="select 1 as a")
    table = [["a"], ["1"]]
    evaluate_then_step(
        'the "select 1 as a" should produce the following rows:', ctx, table=table
    )
```

Add to `tests/test_runner.py`:

```python
ROW_TABLE_THEN_SOURCE = """Feature: Row table then

  Scenario: Exact rows match
    Given the following rows in "orders":
      | order_id | status |
      | 1        | placed |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | order_id | status  |
      | 1        | shipped |
"""


def test_run_feature_text_wires_step_table_into_row_table_then():
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"order_id": 1, "status": "shipped"}]))
    report = run_feature_text(ROW_TABLE_THEN_SOURCE, adapter)
    assert report.scenarios[0].passed is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_assertions.py tests/test_runner.py -v`
Expected: FAIL — `TypeError: evaluate_then_step() got an unexpected keyword argument 'table'`

- [ ] **Step 3: Implement**

In `src/specdbt/assertions.py`, add below the existing regex constants:

```python
_PRODUCES_ROWS_RE = re.compile(r'the "(.+)" should produce the following rows:$')
```

Change the `evaluate_then_step` signature and add the new case as the first
check inside it:

```python
def evaluate_then_step(
    text: str, ctx: ThenContext, table: list[list[str]] | None = None
) -> None:
    """Raise AssertionFailure if the expectation doesn't hold, or
    UnrecognizedStepError if the text matches no known pattern. None on
    success. `table` is the step's data table, if it has one -- only the
    row-table form (the canonical Then, spec §6) uses it."""
    if (m := _PRODUCES_ROWS_RE.match(text)) is not None:
        name = m.group(1)
        if not table:
            raise AssertionFailure(f"{text!r} requires a data table of expected rows")
        result = _lookup(ctx, name)
        header, *data_rows = table
        expected_rows = [
            {column: coerce_scalar(value) for column, value in zip(header, row, strict=True)}
            for row in data_rows
        ]
        if result.rows != expected_rows:
            raise AssertionFailure(
                f'"{name}" produced different rows than expected',
                expected=expected_rows,
                actual=result.rows,
            )
        return

    if (m := _ROW_COUNT_RE.match(text)) is not None:
```

(the rest of the function is unchanged — this new block goes in *before*
the existing `if (m := _ROW_COUNT_RE.match(text))...` check, which stays
exactly as it was).

In `src/specdbt/runner.py`, change the Then/And/But branch of `_run_scenario`:

```python
            else:  # "Outcome"
                evaluate_then_step(
                    step.text,
                    ThenContext(results=results, last_model=last_model),
                    table=step.table or None,
                )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_assertions.py tests/test_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/assertions.py src/specdbt/runner.py tests/test_assertions.py tests/test_runner.py
git commit -m "feat: row-table Then step -- canonical assertion form for both tiers"
```

---

### Task 10: Nicer failure output for row-table mismatches (Polars)

**Files:**
- Modify: `src/specdbt/assertions.py`
- Test: `tests/test_assertions.py`

Small, standalone improvement: render an actual-vs-expected table in the
failure message using Polars (already a security-checked dependency, not yet
used anywhere in the codebase) instead of just the raw Python list-of-dicts
repr `AssertionFailure.args` already carries.

**Interfaces:** no new public names — same `evaluate_then_step`, richer
`str(AssertionFailure)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_assertions.py`:

```python
def test_produces_rows_failure_message_shows_expected_and_actual_tables():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "ZZZ"]]
    with pytest.raises(AssertionFailure) as excinfo:
        evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)
    message = str(excinfo.value)
    assert "expected" in message
    assert "actual" in message
    assert "ZZZ" in message
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_assertions.py::test_produces_rows_failure_message_shows_expected_and_actual_tables -v`
Expected: FAIL — current message is `'"m" produced different rows than expected'`, contains neither "expected" table content nor "ZZZ".

(Note: the message *does* contain the literal word "expected" already — the
test's real assertion that matters is `"ZZZ" in message`, which fails first.)

- [ ] **Step 3: Implement**

In `src/specdbt/assertions.py`, add the import at the top:

```python
import polars as pl
```

Replace the row-count-mismatch branch added in Task 9:

```python
        if result.rows != expected_rows:
            expected_df = pl.DataFrame(expected_rows) if expected_rows else pl.DataFrame()
            actual_df = pl.DataFrame(result.rows) if result.rows else pl.DataFrame()
            raise AssertionFailure(
                f'"{name}" produced different rows than expected:\n'
                f"--- expected ---\n{expected_df}\n"
                f"--- actual ---\n{actual_df}",
                expected=expected_rows,
                actual=result.rows,
            )
        return
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_assertions.py -v`
Expected: PASS, all tests in the file.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/assertions.py tests/test_assertions.py
git commit -m "feat: render expected/actual tables with Polars on row-table mismatch"
```

---

### Task 11: CLI `--engine dbt` wiring

**Files:**
- Modify: `src/specdbt/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Modifies: the `run` command — new options `--engine [fake|dbt]`
  (default `fake`), `--project-dir`, `--profiles-dir`, `--target`,
  `--allow-any-schema`, `--keep-schema`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_run_with_dbt_engine_executes_a_real_macro(tmp_path: Path):
    project_dir = tmp_path / "proj"
    (project_dir / "models").mkdir(parents=True)
    (project_dir / "profiles").mkdir()
    (project_dir / "dbt_project.yml").write_text(
        'name: proj\nversion: "1.0.0"\nconfig-version: 2\n'
        'profile: proj\nmodel-paths: ["models"]\n'
    )
    (project_dir / "profiles" / "profiles.yml").write_text(
        "proj:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
        '      path: "proj.duckdb"\n      schema: main\n'
    )
    (project_dir / "models" / "placeholder.sql").write_text("select 1 as id\n")

    features = tmp_path / "features"
    features.mkdir()
    (features / "orders.feature").write_text(
        "Feature: Orders\n\n"
        "  Scenario: Uppercase status\n"
        '    Given the following rows in "orders":\n'
        "      | order_id | status |\n"
        "      | 1        | placed |\n"
        "    When the \"select order_id, upper(status) as status from "
        "{{ ref('orders') }} order by order_id\" macro runs\n"
        "    Then the \"select order_id, upper(status) as status from "
        "{{ ref('orders') }} order by order_id\" should produce the "
        "following rows:\n"
        "      | order_id | status |\n"
        "      | 1        | PLACED |\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            str(features),
            "--engine",
            "dbt",
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(project_dir / "profiles"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "0 failure(s)" in result.output


def test_run_with_dbt_engine_requires_project_dir(tmp_path: Path):
    features = tmp_path / "features"
    features.mkdir()
    (features / "x.feature").write_text("Feature: F\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["run", str(features), "--engine", "dbt"])
    assert result.exit_code != 0
    assert "--project-dir is required" in result.output
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `Error: No such option: --engine`

- [ ] **Step 3: Implement**

In `src/specdbt/cli.py`, add the import:

```python
from specdbt.adapters.dbt_adapter import DbtExecutionAdapter
```

Replace the `run` command in full:

```python
@cli.command()
@click.argument("target", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--engine",
    type=click.Choice(["fake", "dbt"]),
    default="fake",
    help="fake (default): FakeAdapter + co-located .canned.py. "
    "dbt: DbtExecutionAdapter, real execution.",
)
@click.option("--project-dir", "project_dir", type=click.Path(path_type=Path, exists=True))
@click.option("--profiles-dir", "profiles_dir", type=click.Path(path_type=Path, exists=True))
@click.option("--target", "dbt_target", default=None)
@click.option("--allow-any-schema", is_flag=True, default=False)
@click.option("--keep-schema", is_flag=True, default=False)
def run(
    target: Path,
    engine: str,
    project_dir: Path | None,
    profiles_dir: Path | None,
    dbt_target: str | None,
    allow_any_schema: bool,
    keep_schema: bool,
) -> None:
    """Parse and run the .feature file(s) under TARGET."""
    paths = sorted(target.glob("*.feature")) if target.is_dir() else [target]
    if not paths:
        raise click.ClickException(f"no .feature files found under {target}")

    dbt_adapter: DbtExecutionAdapter | None = None
    if engine == "dbt":
        if project_dir is None:
            raise click.ClickException("--project-dir is required with --engine dbt")
        dbt_adapter = DbtExecutionAdapter(
            project_dir=project_dir,
            profiles_dir=profiles_dir or project_dir,
            target=dbt_target,
            allow_any_schema=allow_any_schema,
            keep_schema=keep_schema,
        )

    reports = []
    for path in paths:
        if dbt_adapter is not None:
            adapter = dbt_adapter
        else:
            adapter = FakeAdapter()
            canned_path = path.with_suffix(".canned.py")
            if canned_path.exists():
                for model_name, result in _load_canned_results(canned_path).items():
                    adapter.register(model_name, result)
        reports.append(run_feature_file(path, adapter))

    for report in reports:
        click.echo(render_feature_report(report))
    click.echo(render_summary(reports))

    if any(not scenario.passed for report in reports for scenario in report.scenarios):
        sys.exit(1)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/cli.py tests/test_cli.py
git commit -m "feat: specdbt run --engine dbt -- real execution from the CLI"
```

---

### Task 12: Real `dbt_utils` example scenarios (generate_surrogate_key, star)

**Files:**
- Create: `examples/dbt_utils_macros/features/generate_surrogate_key.feature`
- Create: `examples/dbt_utils_macros/features/star.feature`
- Test: `tests/test_examples_dbt_utils_macros.py`

Uses the real `examples/dbt_utils_macros/` project already scaffolded
(`dbt_project.yml`, `profiles/profiles.yml`, `packages.yml` pinning
`dbt-labs/dbt_utils`, already security-checked). This satisfies spec §12's
DoD requirement for macro scenarios including one exercising an
introspective macro (`star()`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_examples_dbt_utils_macros.py`:

```python
"""End-to-end: real dbt_utils macros against a real DuckDB target, run
through the actual CLI a user would run (spec §8, §12 DoD)."""

import subprocess
import sys
from pathlib import Path

EXAMPLE_PROJECT = Path(__file__).parent.parent / "examples" / "dbt_utils_macros"
# The venv's own `dbt` console script, resolved by sibling path rather than
# PATH lookup -- a bare "dbt" could silently pick up an unrelated system
# install; sys.executable's directory is where `uv sync` put this venv's own.
DBT_BIN = Path(sys.executable).parent / "dbt"


def test_dbt_utils_macro_examples_all_pass():
    if not (EXAMPLE_PROJECT / "dbt_packages").exists():
        subprocess.run(
            [str(DBT_BIN), "deps", "--profiles-dir", "profiles"],
            cwd=EXAMPLE_PROJECT,
            check=True,
            capture_output=True,
        )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "specdbt.cli",
            "run",
            str(EXAMPLE_PROJECT / "features"),
            "--engine",
            "dbt",
            "--project-dir",
            str(EXAMPLE_PROJECT),
            "--profiles-dir",
            str(EXAMPLE_PROJECT / "profiles"),
        ],
        capture_output=True,
        text=True,
        cwd=EXAMPLE_PROJECT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 scenario(s)" in result.stdout
    assert "0 failure(s)" in result.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_examples_dbt_utils_macros.py -v`
Expected: FAIL — `no .feature files found` (directory doesn't exist yet).

- [ ] **Step 3: Implement**

Create `examples/dbt_utils_macros/features/generate_surrogate_key.feature`:

```gherkin
Feature: generate_surrogate_key produces a stable, deterministic hash

  Scenario: Same input fields always produce the same key
    Given the following rows in "orders":
      | order_id | status  |
      | 1        | placed  |
      | 2        | shipped |
    When the "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }} order by order_id" macro runs
    Then the "select order_id, {{ dbt_utils.generate_surrogate_key(['order_id', 'status']) }} as order_key from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | order_key                        |
      | 1        | 3b8d3a0710139623574ed352387c1401 |
      | 2        | 5294b8cfc5826a1b7fe812d14a7c02c4 |
```

(the expected hashes are taken directly from a spike run against this exact
macro call and these exact input rows against dbt_utils 1.4.1 — a real,
verified value, not a placeholder)

Create `examples/dbt_utils_macros/features/star.feature`:

```gherkin
Feature: star selects every real column of a fixture — introspective macro

  Scenario: star expands to the fixture's actual columns, unchanged
    Given the following rows in "orders":
      | order_id | status  |
      | 1        | placed  |
      | 2        | shipped |
    When the "select {{ dbt_utils.star(from=ref('orders')) }} from {{ ref('orders') }} order by order_id" macro runs
    Then the "select {{ dbt_utils.star(from=ref('orders')) }} from {{ ref('orders') }} order by order_id" should produce the following rows:
      | order_id | status  |
      | 1        | placed  |
      | 2        | shipped |
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_examples_dbt_utils_macros.py -v`
Expected: PASS. (First run installs `dbt_utils` via `dbt deps` if
`dbt_packages/` is missing — a real network call to dbt Hub/GitHub; this is
the one test in the suite that isn't fully hermetic, and that's inherent to
testing against a real third-party dbt package.)

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add examples/dbt_utils_macros/features/ tests/test_examples_dbt_utils_macros.py
git commit -m "feat: real dbt_utils example scenarios (generate_surrogate_key, star)"
```

---

### Task 13: CI workflow (spec §11 — DuckDB-target only, inert until pushed)

**Files:**
- Create: `.github/workflows/ci.yml`

This repo has no remote and nothing gets pushed (standing rule) — this file
is dormant until that changes, but writing it now means CI is ready the day
it does, and it doubles as the canonical "how to run this from a clean
checkout" recipe (`dbt deps` + `uv sync` + `pytest`) for a human doing the
same thing locally.

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Install dbt_utils for the example project
        working-directory: examples/dbt_utils_macros
        run: uv run --project ../.. dbt deps --profiles-dir profiles

      - name: Lint
        run: |
          uv run ruff check .
          uv run ruff format --check .

      - name: Test
        run: uv run pytest -v
```

- [ ] **Step 2: Verify it's well-formed YAML**

Run: `uv run python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo OK`
Expected: `OK`. (No GitHub Actions runner to actually execute this against —
there's no remote — so syntactic validity is what's checkable locally; the
real test is Steps 1–4 of Task 14 passing, since this file runs the same
commands.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow (dormant -- no remote configured yet)"
```

---

### Task 14: Definition of Done verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -v`
Expected: all tests pass — the pre-existing 60 from Phase 0, plus every test
added in Tasks 1–12 (~45 new tests). Note the exact final count in the
commit message.

- [ ] **Step 2: Lint and format**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: both clean. If not, run `uv run ruff check --fix . && uv run ruff
format .`, re-run the full suite to confirm no behavioral change, and commit
the autofix separately (`style: apply ruff format/lint autofixes`) before
continuing — same pattern as Phase 0.

- [ ] **Step 3: Manual CLI smoke test against the real example project**

```bash
cd examples/dbt_utils_macros
uv run --project ../.. specdbt run features --engine dbt --project-dir . --profiles-dir profiles
```

Expected output includes `2 scenario(s)`, `0 failure(s)`, and no leftover
`specdbt_*` schema or `macros/_specdbt_*.sql` file afterward — verify with:

```bash
ls macros/ 2>/dev/null | grep _specdbt || echo "clean: no leftover macro files"
uv run --project ../.. python3 -c "
import duckdb
con = duckdb.connect('dbt_utils_macros.duckdb')
print(con.execute(\"select schema_name from information_schema.schemata where schema_name like 'specdbt_%'\").fetchall())
"
```

Expected: empty list, "clean: no leftover macro files".

- [ ] **Step 4: Check against this plan's slice of the spec's Definition of Done**

From spec §12 — this plan covers the macro half only (model unit tier is a
separate, not-yet-written plan):

- [x] `specdbt run` executes ≥2 dbt_utils macro scenarios via the
      integration tier, including one introspective macro (`star()`) — Task 12
- [x] Schema teardown verified, pass or fail, no leftover schema or macro
      file — Task 7's tests + Step 3 above
- [x] All new dependencies security-checked before install — done before
      Task 1 even started (commit `16dc9db`, `379a61f`)
- [x] Existing Phase 0 tests plus new tests pass; `ruff` clean — Steps 1–2
- [x] Nothing pushed; no git remote configured
- [x] CI workflow exists (spec §11), dormant until a remote is added — Task 13

Not in this plan's scope (spec §13, deferred to the model-unit-tier plan):
model unit tier, `docs/gherkin-style-guide.md`, `specdbt docs` command,
`@unit`/`@integration`/`@adapter:`/`@ai-generated` tags, `NativeTestCompiler`
registry, incremental-model `input: this` grammar.

- [ ] **Step 5: Final commit**

```bash
git log --oneline phase-1-dbt-execution ^main
git status
```

Expected: clean working tree, every task committed individually (not
squashed), branch `phase-1-dbt-execution` ahead of `main` by exactly the
commits made in this plan plus the earlier spec/dependency commits. Do not
merge to `main` yet — report the branch state and this Definition of Done
checklist back to the user before merging, per the standing practice of
merging via the `finishing-a-development-branch` skill once a branch is
confirmed complete.
