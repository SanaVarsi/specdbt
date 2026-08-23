# specdbt Phase 1 Plan B: Model Unit Tier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make specdbt compile a Gherkin scenario's Given/When/Then directly
to a dbt-native `unit_tests:` YAML entry and run it for real via `dbt test`
— reusing dbt's own fixture-injection, type-casting, and actual-vs-expected
diffing rather than reimplementing any of it — with `@unit`/`@integration`
tags (or a resource-kind default) routing each scenario to this tier or to
Plan A's macro/model integration tier, and incremental models tested in
both `is_incremental` branches.

**Architecture:** A new parallel orchestration interface,
`NativeTestCompiler` (spec §3, §10 — deliberately *not* an
`ExecutionAdapter` method), with one real implementation,
`ModelUnitTestCompiler`. It compiles a scenario's fixtures + row-table
`Then` into a generated `models/_specdbt_<run_id>.yml` unit test, runs
`dbt test --select unit_test:<project>.<name>` via the same `dbtRunner`
entrypoint Plan A uses, and translates dbt's own `status`/`message`/
`failures` into specdbt's `StepResult` format. This inverts the runner's
control flow for unit-tier scenarios: today's per-step execution
(`src/specdbt/runner.py::_run_scenario`) threads a `When` step's real
result into the `Then` step that checks it *after* it runs; the unit tier
hands dbt the *whole* scenario at once, since dbt does that comparison
itself — the `Then` step's table becomes an *input* to compilation,
collected before anything executes. `src/specdbt/runner.py` gains a tier
dispatcher in front of both paths. The `Then` step's row-table comparison
also changes for **both** tiers, fixing two orthogonality breaks a spike
found in dbt's own `expect: rows:` semantics (column-projection,
order-insensitive-but-count-sensitive) that specdbt's existing full-`dict`-
equality check didn't share.

**Tech Stack:** Python 3.12+, dbt-core 1.12.2, dbt-duckdb 1.11.0, PyYAML
6.0.3 (already present transitively via dbt-core; declared as a direct
dependency here since specdbt code now imports it directly — not a new
package, no new security check needed), pytest, click, gherkin-official
(all already installed and security-checked).

**Spec:** `docs/superpowers/specs/2026-08-23-specdbt-phase1-design-v2.md`
— read §3, §4, **§4.1** (Plan-B-time spike findings, added
2026-08-23 in commits `73d00d3`, `6f3c05f`, `d0d42fc`), §6, §10, §13.

## Global Constraints

- Branch: `phase-1-model-unit-tier` (already created off `main`, which
  already has Plan A merged — commit `fc718da`). Keep committing here; do
  not merge to `main` until this plan's Definition of Done (Task 13) passes.
- Spec grounding is empirical, not docs-derived — every mechanism below was
  verified against a real dbt-duckdb scratch project before this plan was
  written (spec §4.1, findings 1–8). Do not deviate from what's specified
  without re-verifying the same way; trust it, but verify anew if you do
  (same standing rule Plan A's Global Constraints established).
- **Selector:** `dbt test --select f"unit_test:{project_name}.{name}"`
  resolves to exactly one node — verified (§4.1 finding 1).
- **`dbtRunnerResult.success` is `False` on a legitimately failing unit
  test — this is normal, not an error.** Only `result.result is None`
  signals a genuine invocation failure (parse/compile error) for a `dbt
  test` call (§4.1 finding 2). A `dbt seed`/`dbt run` prebuild call is the
  opposite: any `success is False` there is fatal and must raise, since a
  broken upstream relation silently breaks every unit test that needs it.
  Two different invoke helpers exist for exactly this reason — do not
  collapse them into one.
- **`result.status` compares equal to plain strings `"pass"`/`"fail"`**
  directly, no `.value`/enum import needed (§4.1 finding 3).
  **`result.message` carries ANSI color escapes on failure** — strip with
  `re.compile(r"\x1b\[[0-9;]*m").sub("", message)` before it reaches a
  `StepResult`.
- **Row-table `Then` is column-projected, multiset-compared, for both
  tiers** (§4.1 findings 4, 7; spec §6) — only the columns named in the
  expected table's header are compared; row order doesn't matter; row
  *count* (duplicates) does. This is a real behavior change to Plan A's
  existing integration-tier comparison, tightened here so a scenario's
  meaning doesn't change when retagged `@unit`/`@integration`.
- **The unit tier is not ephemeral like the macro/integration tier.** A
  unit test's `given: input: ref()/source()/this` targets must already
  exist as real, built relations in the target's actually-configured
  schema — not a throwaway `specdbt_<uuid>` one — or dbt fails trying to
  introspect their column types (§4.1 finding 6). `input: this` needs the
  model under test itself built too (§4.1 finding 8). This plan's
  `ModelUnitTestCompiler` runs one `dbt seed` + `dbt run` for the *whole*
  project, once per compiler instance (not per scenario), before any unit
  test — the simplest correct choice, since dbt's own dependency graph
  already orders it and it's cheap for the example project's five models.
  It uses the **same prod-schema guard** `DbtExecutionAdapter` already has
  (extracted to a shared module in Task 7) — because this step, unlike
  Plan A's macro mechanism, writes real tables into the project's real
  target.
- **`@unit`/`@integration` tag resolution** (spec §3): explicit tag wins;
  else "unit" if a `NativeTestCompiler` is registered for the scenario's
  resource kind (model vs. macro, from its `When` step), else
  "integration". The macro slot is never registered in this plan — no
  native dbt mechanism exists yet (dbt-core#10547, open) — a `@unit`-tagged
  or defaulted macro scenario gets a clear error naming the fix.
- **Incremental branch grammar, decided at plan-write time** (spec §4 left
  this open deliberately): one Gherkin scenario per branch, not
  auto-generation of both branches from a single scenario. A scenario
  tagged `@incremental_model` gets an explicit `overrides: macros:
  is_incremental: <bool>` in its compiled YAML — `true` if it has an
  `And the following rows already in "<model>":` step (compiles to
  `input: this`), `false` if it doesn't. This is a deliberate,
  documented-here deviation from spec §4's "generate both branches from
  one scenario" phrasing: two explicit scenarios is simpler to compile
  correctly and produces the same DoD-required coverage.
- **Scope boundary, explicit:** `@adapter:<name>` and `@ai-generated` tags
  are parsed (they're just tag strings, captured by `Scenario.tags` like
  any other) but have **no enforcement logic** in this plan — spec §6
  itself doesn't define what should check `@adapter:`, and `@ai-generated`
  is a Phase 3 hook. Do not add speculative handling for either; a tag
  with no defined runtime behavior yet is not a gap in this plan, it's
  matching what the spec actually specifies. `specdbt docs` (living
  documentation) is out of scope entirely — deferred to Plan C (spec §13,
  revised 2026-08-23) — it has no dependency on either tier and stands
  alone.
- Never push — local git repo only, no remote configured.
- TDD discipline: red, green, commit — per task, in that order.
- Always pass `--no-send-anonymous-usage-stats` on every `dbtRunner`
  invocation specdbt makes on the user's behalf (same as Plan A).
- Existing 101 tests (60 Phase 0 + 41 Plan A) must keep passing throughout
  — run the full suite (not just the new file) after every task.

---

### Task 1: `rows_from_data_table` — shared Given/Then table-to-rows helper

**Files:**
- Modify: `src/specdbt/typing_utils.py`
- Modify: `src/specdbt/fixtures.py`
- Modify: `src/specdbt/assertions.py`
- Test: `tests/test_typing_utils.py`

Both `fixtures.py` (Given → `Fixture.rows`) and `assertions.py` (row-table
`Then` → `expected_rows`) already do the identical "header + data rows →
`list[dict]` via `coerce_scalar`" conversion inline. Task 6 needs the exact
same conversion a third time, for the unit tier's compiler. Extracting it
now avoids a third copy.

**Interfaces:**
- Produces: `rows_from_data_table(table: list[list[str]]) -> list[dict]` —
  caller must ensure `table` is non-empty (both existing call sites already
  check this before calling; the helper itself doesn't re-check, matching
  existing call-site responsibility).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_typing_utils.py`:

```python
from specdbt.typing_utils import coerce_scalar, rows_from_data_table


def test_rows_from_data_table_zips_header_with_each_data_row():
    table = [["id", "name"], ["1", "a"], ["2", "b"]]
    assert rows_from_data_table(table) == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]


def test_rows_from_data_table_coerces_each_cell():
    table = [["id", "flag", "note"], ["1", "true", "NULL"]]
    assert rows_from_data_table(table) == [{"id": 1, "flag": True, "note": None}]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_typing_utils.py -v`
Expected: FAIL — `ImportError: cannot import name 'rows_from_data_table'`

- [ ] **Step 3: Implement**

In `src/specdbt/typing_utils.py`, add below `coerce_scalar`:

```python
def rows_from_data_table(table: list[list[str]]) -> list[dict]:
    """Turn a Gherkin data table (header row + data rows, both raw strings)
    into a list of dicts with coerced scalar values -- shared by every step
    kind that reads a data table: Given fixtures (fixtures.py), the
    integration tier's row-table Then (assertions.py), and the unit tier's
    compiler (native_unit_tests/model_compiler.py, Task 6). Caller must
    ensure table is non-empty."""
    header, *data_rows = table
    return [
        {column: coerce_scalar(value) for column, value in zip(header, row, strict=True)}
        for row in data_rows
    ]
```

In `src/specdbt/fixtures.py`, change the import and the body of
`build_fixture`:

```python
from specdbt.typing_utils import rows_from_data_table
```

(replaces the existing `from specdbt.typing_utils import coerce_scalar` —
`fixtures.py` no longer calls `coerce_scalar` directly.)

Replace the tail of `build_fixture`:

```python
    name = match.group(1)
    rows = rows_from_data_table(step.table)
    return Fixture(name=name, rows=rows)
```

(the `if not step.table: raise FixtureBuildError(...)` check immediately
above this, in the existing function, is unchanged — still runs first.)

In `src/specdbt/assertions.py`, add `rows_from_data_table` to the existing
`from specdbt.typing_utils import coerce_scalar` import line (import both),
then in the `_PRODUCES_ROWS_RE` branch of `evaluate_then_step`, replace:

```python
        header, *data_rows = table
        expected_rows = [
            {column: coerce_scalar(value) for column, value in zip(header, row, strict=True)}
            for row in data_rows
        ]
```

with:

```python
        expected_rows = rows_from_data_table(table)
```

(`coerce_scalar` is still used elsewhere in `assertions.py` — the
`_ROW_FIELD_RE` branch — so the import stays, just gains a second name.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_typing_utils.py tests/test_fixtures.py tests/test_assertions.py -v`
Expected: PASS, all tests including every pre-existing one (behavior is
identical — this is a pure extraction, no logic change).

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/typing_utils.py src/specdbt/fixtures.py src/specdbt/assertions.py tests/test_typing_utils.py
git commit -m "refactor: extract rows_from_data_table -- shared by fixtures, assertions, and (Task 6) the unit-tier compiler"
```

---

### Task 2: `Scenario.tags` in the parser

**Files:**
- Modify: `src/specdbt/parser.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Modifies: `Scenario` dataclass gains `tags: list[str] = field(default_factory=list)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_parser.py`:

```python
TAGGED_SAMPLE = """Feature: Tagged

  @unit @incremental_model
  Scenario: Has tags
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | c |
      | 1 |


  Scenario: Has no tags
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | c |
      | 1 |
"""


def test_scenario_tags_are_captured_with_leading_at_sign():
    feature = parse_feature_text(TAGGED_SAMPLE)
    assert feature.scenarios[0].tags == ["@unit", "@incremental_model"]


def test_scenario_with_no_tags_has_an_empty_tags_list():
    feature = parse_feature_text(TAGGED_SAMPLE)
    assert feature.scenarios[1].tags == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_parser.py -v`
Expected: FAIL — `AttributeError: 'Scenario' object has no attribute 'tags'`

- [ ] **Step 3: Implement**

In `src/specdbt/parser.py`, change the `Scenario` dataclass:

```python
@dataclass
class Scenario:
    name: str
    steps: list[Step] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
```

In `parse_feature_text`, inside the `for child in feature_node["children"]:`
loop, after `scenario_node = child.get("scenario")` / the `if
scenario_node is None: continue` check, add before the `steps: list[Step]
= []` line:

```python
        tags = [tag["name"] for tag in scenario_node.get("tags", [])]
```

Then change the final `scenarios.append(...)` call at the end of the loop
body:

```python
        scenarios.append(Scenario(name=scenario_node["name"], steps=steps, tags=tags))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_parser.py -v`
Expected: PASS, all tests.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/parser.py tests/test_parser.py
git commit -m "feat: Scenario.tags -- parses gherkin-official's tag AST, needed for @unit/@integration routing"
```

---

### Task 3: Row-table `Then` — column-projection, multiset comparison

**Files:**
- Modify: `src/specdbt/assertions.py`
- Test: `tests/test_assertions.py`

Fixes the two orthogonality breaks spec §4.1 findings 4 and 7 found: dbt's
own `expect: rows:` only compares the columns it lists (ignores others the
model produces) and is order-insensitive but duplicate-count-sensitive.
Plan A's existing full-`dict`-equality check did neither — this task makes
it match dbt's real semantics, for both tiers, per spec §6.

**Interfaces:**
- Modifies: `evaluate_then_step`'s `_PRODUCES_ROWS_RE` branch only — no
  signature change.
- Renames: `_PRODUCES_ROWS_RE` (private) → `PRODUCES_ROWS_RE` (public) —
  Task 6's compiler needs the identical pattern and must not drift from it.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_assertions.py`:

```python
def test_produces_rows_ignores_row_order():
    result = ExecutionResult.of(rows=[{"id": 2, "name": "b"}, {"id": 1, "name": "a"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "a"], ["2", "b"]]
    evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)


def test_produces_rows_ignores_unlisted_actual_columns():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a", "extra": 999}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "a"]]
    evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)


def test_produces_rows_is_sensitive_to_duplicate_row_counts():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a"}, {"id": 1, "name": "a"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "a"]]  # only one copy expected, actual has two
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)


def test_produces_rows_still_fails_when_a_value_genuinely_differs():
    result = ExecutionResult.of(rows=[{"id": 1, "name": "a"}])
    ctx = ThenContext(results={"m": result}, last_model="m")
    table = [["id", "name"], ["1", "ZZZ"]]
    with pytest.raises(AssertionFailure):
        evaluate_then_step('the "m" should produce the following rows:', ctx, table=table)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_assertions.py -v`
Expected: `test_produces_rows_ignores_row_order` and
`test_produces_rows_ignores_unlisted_actual_columns` FAIL (current code
does full-`dict` list equality, which is order- and column-set-sensitive).
`test_produces_rows_is_sensitive_to_duplicate_row_counts` and
`test_produces_rows_still_fails_when_a_value_genuinely_differs` already
pass against the old code by coincidence — that's fine, they still assert
the right thing after Step 3.

- [ ] **Step 3: Implement**

In `src/specdbt/assertions.py`, add to the imports at the top:

```python
from collections import Counter
```

Rename the constant (search-replace both the definition and its one use
site in `evaluate_then_step`):

```python
PRODUCES_ROWS_RE = re.compile(r'the "(.+)" should produce the following rows:$')
```

Replace the whole `_PRODUCES_ROWS_RE`/now-`PRODUCES_ROWS_RE` branch body
inside `evaluate_then_step`:

```python
    if (m := PRODUCES_ROWS_RE.match(text)) is not None:
        name = m.group(1)
        if not table:
            raise AssertionFailure(f"{text!r} requires a data table of expected rows")
        result = _lookup(ctx, name)
        header = table[0]
        expected_rows = rows_from_data_table(table)
        projected_actual_rows = [{column: row.get(column) for column in header} for row in result.rows]
        expected_counts = Counter(tuple(row[c] for c in header) for row in expected_rows)
        actual_counts = Counter(tuple(row[c] for c in header) for row in projected_actual_rows)
        if actual_counts != expected_counts:
            expected_df = pl.DataFrame(expected_rows) if expected_rows else pl.DataFrame()
            actual_df = (
                pl.DataFrame(projected_actual_rows) if projected_actual_rows else pl.DataFrame()
            )
            raise AssertionFailure(
                f'"{name}" produced different rows than expected (only columns '
                f"{header} are compared; row order doesn't matter, row count "
                f"does):\n"
                f"--- expected ---\n{expected_df}\n"
                f"--- actual (projected) ---\n{actual_df}",
                expected=expected_rows,
                actual=projected_actual_rows,
            )
        return

    if (m := _ROW_COUNT_RE.match(text)) is not None:
```

(the rest of the function — `_ROW_COUNT_RE` onward — is unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_assertions.py -v`
Expected: PASS, all tests including the pre-existing ones (the pre-existing
tests all use matching column sets already, so projection is a no-op for
them; they use matching row order too, so multiset comparison is also a
no-op — no regressions, only new capability).

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/assertions.py tests/test_assertions.py
git commit -m "fix: row-table Then is column-projected + multiset-compared, matching dbt's own expect: rows: semantics (spec §4.1 findings 4, 7)"
```

---

### Task 4: `NativeTestCompiler` interface, `CompilerRegistry`, `resolve_tier`

**Files:**
- Create: `src/specdbt/native_unit_tests/__init__.py` (empty)
- Create: `src/specdbt/native_unit_tests/compiler.py`
- Create: `tests/native_unit_tests/__init__.py` (empty)
- Create: `tests/native_unit_tests/test_compiler.py`

**Interfaces:**
- Produces: `NativeTestCompiler` (ABC, method `run(self, scenario:
  Scenario) -> list[StepResult]`); `CompilerRegistry` (methods `register`,
  `get`); `resolve_tier(tags: list[str], resource_kind: str, registry:
  CompilerRegistry) -> str`; `get_compiler_or_raise(registry:
  CompilerRegistry, resource_kind: str) -> NativeTestCompiler`;
  `UnitTierNotSupportedError`; `TAG_UNIT`, `TAG_INTEGRATION`.

- [ ] **Step 1: Write the failing tests**

Create `tests/native_unit_tests/__init__.py` (empty file).

Create `tests/native_unit_tests/test_compiler.py`:

```python
import pytest

from specdbt.native_unit_tests.compiler import (
    CompilerRegistry,
    NativeTestCompiler,
    UnitTierNotSupportedError,
    get_compiler_or_raise,
    resolve_tier,
)
from specdbt.parser import Scenario
from specdbt.reporter import StepResult


class _StubCompiler(NativeTestCompiler):
    def run(self, scenario: Scenario) -> list[StepResult]:
        return [StepResult("Then", "stub", passed=True)]


def test_registry_get_returns_none_when_nothing_registered():
    registry = CompilerRegistry()
    assert registry.get("model") is None


def test_registry_get_returns_the_registered_compiler():
    registry = CompilerRegistry()
    compiler = _StubCompiler()
    registry.register("model", compiler)
    assert registry.get("model") is compiler


def test_resolve_tier_explicit_unit_tag_wins():
    registry = CompilerRegistry()  # nothing registered
    assert resolve_tier(["@unit"], "macro", registry) == "unit"


def test_resolve_tier_explicit_integration_tag_wins_over_a_registered_compiler():
    registry = CompilerRegistry()
    registry.register("model", _StubCompiler())
    assert resolve_tier(["@integration"], "model", registry) == "integration"


def test_resolve_tier_rejects_both_tags_at_once():
    registry = CompilerRegistry()
    with pytest.raises(ValueError):
        resolve_tier(["@unit", "@integration"], "model", registry)


def test_resolve_tier_defaults_to_unit_when_a_compiler_is_registered():
    registry = CompilerRegistry()
    registry.register("model", _StubCompiler())
    assert resolve_tier([], "model", registry) == "unit"


def test_resolve_tier_defaults_to_integration_when_no_compiler_is_registered():
    registry = CompilerRegistry()
    assert resolve_tier([], "macro", registry) == "integration"


def test_get_compiler_or_raise_returns_the_registered_compiler():
    registry = CompilerRegistry()
    compiler = _StubCompiler()
    registry.register("model", compiler)
    assert get_compiler_or_raise(registry, "model") is compiler


def test_get_compiler_or_raise_names_dbt_core_10547_for_an_unregistered_kind():
    registry = CompilerRegistry()
    with pytest.raises(UnitTierNotSupportedError, match="dbt-core#10547"):
        get_compiler_or_raise(registry, "macro")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/native_unit_tests/test_compiler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.native_unit_tests'`

- [ ] **Step 3: Implement**

Create `src/specdbt/native_unit_tests/__init__.py` (empty).

Create `src/specdbt/native_unit_tests/compiler.py`:

```python
"""Unit-tier orchestration interface (spec §3, §10) -- delegates to
whatever native fixture mechanism dbt ships for a given resource kind.
Deliberately not an ExecutionAdapter method: delegating-to-dbt's-own-runner
(this) and driving-real-execution-directly (ExecutionAdapter.run_macro) are
different enough operations that overloading one interface would blur what
each call actually does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from specdbt.parser import Scenario
from specdbt.reporter import StepResult

TAG_UNIT = "@unit"
TAG_INTEGRATION = "@integration"


class NativeTestCompiler(ABC):
    @abstractmethod
    def run(self, scenario: Scenario) -> list[StepResult]:
        """Compile `scenario` to whatever dbt-native mechanism this
        resource kind supports, run it for real, and return one StepResult
        per originally-authored Given/When/Then step, in step order. May
        raise; callers translate any exception into a single failed
        StepResult."""
        raise NotImplementedError


class UnitTierNotSupportedError(NotImplementedError):
    """Raised when a scenario resolves to @unit for a resource kind with no
    registered NativeTestCompiler (spec §3, §5.4) -- today, macros: dbt has
    no native mechanism yet (dbt-core#10547, open)."""


class CompilerRegistry:
    """Explicit, per-caller registry -- not a module-level singleton,
    matching how ExecutionAdapter instances are already passed around
    explicitly rather than through global state."""

    def __init__(self) -> None:
        self._compilers: dict[str, NativeTestCompiler] = {}

    def register(self, resource_kind: str, compiler: NativeTestCompiler) -> None:
        self._compilers[resource_kind] = compiler

    def get(self, resource_kind: str) -> NativeTestCompiler | None:
        return self._compilers.get(resource_kind)


def resolve_tier(tags: list[str], resource_kind: str, registry: CompilerRegistry) -> str:
    """"unit" if @unit tag present, "integration" if @integration tag
    present (a scenario tagged both is an error), else "unit" if a
    compiler is registered for `resource_kind`, else "integration" (spec
    §3). Does not itself check whether a "unit"-resolved resource_kind
    actually has a compiler registered -- see get_compiler_or_raise."""
    if TAG_UNIT in tags and TAG_INTEGRATION in tags:
        raise ValueError(f"scenario tagged both {TAG_UNIT} and {TAG_INTEGRATION}")
    if TAG_UNIT in tags:
        return "unit"
    if TAG_INTEGRATION in tags:
        return "integration"
    return "unit" if registry.get(resource_kind) is not None else "integration"


def get_compiler_or_raise(registry: CompilerRegistry, resource_kind: str) -> NativeTestCompiler:
    compiler = registry.get(resource_kind)
    if compiler is None:
        raise UnitTierNotSupportedError(
            f"@unit is not supported for {resource_kind} resources yet -- dbt "
            "has no native mechanism (dbt-core#10547 open); tag this scenario "
            "@integration instead."
        )
    return compiler
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/native_unit_tests/test_compiler.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/native_unit_tests/ tests/native_unit_tests/__init__.py tests/native_unit_tests/test_compiler.py
git commit -m "feat: NativeTestCompiler interface, CompilerRegistry, resolve_tier -- unit/integration tier routing (spec §3)"
```

---

### Task 5: Generated unit-test YAML — render/write/delete

**Files:**
- Create: `src/specdbt/native_unit_tests/yaml_file.py`
- Create: `tests/native_unit_tests/test_yaml_file.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `unit_test_name(run_id: str) -> str`, `render_unit_test_yaml(*,
  run_id: str, model_name: str, given: list[dict], expect_rows: list[dict],
  is_incremental: bool | None) -> str`, `write_unit_test_yaml(project_dir:
  Path, run_id: str, content: str) -> Path`, `delete_unit_test_yaml(path:
  Path) -> None`

**Scope boundary, explicit:** `coerce_scalar`'s `None` (from a Gherkin
`NULL` literal) passes through `yaml.safe_dump` as YAML's native `null`,
which dbt's own unit-test fixture schema is documented to accept — but no
task in this plan exercises a `NULL`-valued fixture row end-to-end against
a real `dbt test` invocation (no DoD scenario needs one). Treat this path
as plausible, not verified, until a real scenario needs it.

- [ ] **Step 1: Declare the direct dependency**

In `pyproject.toml`, add `"pyyaml>=6.0"` to the `dependencies` list (already
resolves to 6.0.3, already present transitively via `dbt-core` and already
covered by Plan A's full-environment `pip-audit` — no new install, no new
security check, just an explicit direct dependency since this task's code
imports it directly).

Run: `uv sync` — expect no new packages downloaded, just the lockfile
recording the now-direct dependency.

- [ ] **Step 2: Write the failing tests**

Create `tests/native_unit_tests/test_yaml_file.py`:

```python
from pathlib import Path

import yaml

from specdbt.native_unit_tests.yaml_file import (
    delete_unit_test_yaml,
    render_unit_test_yaml,
    unit_test_name,
    write_unit_test_yaml,
)


def test_unit_test_name_derived_from_run_id():
    assert unit_test_name("abc123") == "_specdbt_abc123"


def test_render_unit_test_yaml_structure_for_a_simple_model():
    text = render_unit_test_yaml(
        run_id="abc123",
        model_name="stg_customers",
        given=[{"input": "ref('raw_customers')", "rows": [{"id": 1, "first_name": "a"}]}],
        expect_rows=[{"customer_id": 1}],
        is_incremental=None,
    )
    parsed = yaml.safe_load(text)
    assert parsed == {
        "unit_tests": [
            {
                "name": "_specdbt_abc123",
                "model": "stg_customers",
                "given": [
                    {"input": "ref('raw_customers')", "rows": [{"id": 1, "first_name": "a"}]}
                ],
                "expect": {"rows": [{"customer_id": 1}]},
            }
        ]
    }


def test_render_unit_test_yaml_includes_is_incremental_override_when_given():
    text = render_unit_test_yaml(
        run_id="abc123", model_name="m", given=[], expect_rows=[], is_incremental=True
    )
    parsed = yaml.safe_load(text)
    assert parsed["unit_tests"][0]["overrides"] == {"macros": {"is_incremental": True}}


def test_render_unit_test_yaml_omits_overrides_when_is_incremental_is_none():
    text = render_unit_test_yaml(
        run_id="abc123", model_name="m", given=[], expect_rows=[], is_incremental=None
    )
    parsed = yaml.safe_load(text)
    assert "overrides" not in parsed["unit_tests"][0]


def test_render_unit_test_yaml_supports_input_this():
    text = render_unit_test_yaml(
        run_id="abc123",
        model_name="incr",
        given=[{"input": "this", "rows": [{"id": 1}]}],
        expect_rows=[{"id": 2}],
        is_incremental=True,
    )
    parsed = yaml.safe_load(text)
    assert parsed["unit_tests"][0]["given"] == [{"input": "this", "rows": [{"id": 1}]}]


def test_write_and_delete_unit_test_yaml(tmp_path: Path):
    path = write_unit_test_yaml(tmp_path, "abc123", "unit_tests: []\n")
    assert path == tmp_path / "models" / "_specdbt_abc123.yml"
    assert path.read_text() == "unit_tests: []\n"
    delete_unit_test_yaml(path)
    assert not path.exists()


def test_delete_unit_test_yaml_is_a_noop_if_already_gone(tmp_path: Path):
    delete_unit_test_yaml(tmp_path / "models" / "does_not_exist.yml")  # must not raise
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/native_unit_tests/test_yaml_file.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.native_unit_tests.yaml_file'`

- [ ] **Step 4: Implement**

Create `src/specdbt/native_unit_tests/yaml_file.py`:

```python
"""Renders a compiled unit test as a dbt-native `unit_tests:` YAML entry,
and writes/deletes the generated file specdbt writes into the target
project (spec §4, §4.1) -- mirrors dbt_integration/macro_file.py's
render/write/delete shape for the macro tier.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def unit_test_name(run_id: str) -> str:
    return f"_specdbt_{run_id}"


def render_unit_test_yaml(
    *,
    run_id: str,
    model_name: str,
    given: list[dict],
    expect_rows: list[dict],
    is_incremental: bool | None,
) -> str:
    """`given` is a list of {"input": <"ref('x')" | "source('a','b')" |
    "this">, "rows": list[dict]} dicts, already compiled by
    native_unit_tests.model_compiler.compile_scenario (Task 6).
    `is_incremental`: None omits the overrides block entirely (models that
    don't call is_incremental()); True/False emits an explicit
    overrides: macros: is_incremental: <bool> (spec §4.1 finding 8 -- dbt
    requires this be explicit for any unit test on a model that does)."""
    entry: dict = {
        "name": unit_test_name(run_id),
        "model": model_name,
        "given": [{"input": g["input"], "rows": g["rows"]} for g in given],
        "expect": {"rows": expect_rows},
    }
    if is_incremental is not None:
        entry["overrides"] = {"macros": {"is_incremental": is_incremental}}
    return yaml.safe_dump({"unit_tests": [entry]}, sort_keys=False)


def write_unit_test_yaml(project_dir: Path, run_id: str, content: str) -> Path:
    path = Path(project_dir) / "models" / f"{unit_test_name(run_id)}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def delete_unit_test_yaml(path: Path) -> None:
    Path(path).unlink(missing_ok=True)
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/native_unit_tests/test_yaml_file.py -v`
Expected: PASS.

- [ ] **Step 6: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add pyproject.toml uv.lock src/specdbt/native_unit_tests/yaml_file.py tests/native_unit_tests/test_yaml_file.py
git commit -m "feat: render/write/delete generated unit_tests: YAML (spec §4, §4.1)"
```

---

### Task 6: `compile_scenario` — Gherkin scenario → `CompiledUnitTest`

**Files:**
- Create: `src/specdbt/native_unit_tests/model_compiler.py`
- Create: `tests/native_unit_tests/test_model_compiler.py`

Pure function — no dbt invocation, no file I/O. Also introduces the
incremental-model Given step grammar (`And the following rows already in
"<model>":` → `input: this`) and the `@incremental_model` tag.

**Scope boundary, explicit:** every ordinary Given fixture compiles to
`input: ref('<name>')` — never `source(...)`. Existing Given-step grammar
(`the following rows in "<name>":`, shared with Plan A's macro tier) never
distinguished ref from source, so `compile_scenario` can't either without a
new step form. `render_unit_test_yaml` (Task 5) accepts an arbitrary
`input:` string generically, so adding `source()` support later is a
`compile_scenario`-only change, not a YAML-rendering one — not a gap this
plan needs to close, since no Plan B example needs it (jaffle_shop's
staging models `ref()` their seeds, they don't `source()` them).

**Interfaces:**
- Consumes: `Scenario`, `Step` (parser.py), `PRODUCES_ROWS_RE`
  (assertions.py, Task 3), `rows_from_data_table` (typing_utils.py, Task 1)
- Produces: `CompiledUnitTest` (dataclass: `model_name: str`, `given:
  list[dict]`, `expect_rows: list[dict]`, `is_incremental: bool | None`,
  `given_steps: list[Step]`, `when_step: Step | None`, `then_step: Step |
  None`); `compile_scenario(scenario: Scenario) -> CompiledUnitTest`;
  `UnitTestCompileError`; `TAG_INCREMENTAL_MODEL`

- [ ] **Step 1: Write the failing tests**

Create `tests/native_unit_tests/test_model_compiler.py`:

```python
import pytest

from specdbt.native_unit_tests.model_compiler import UnitTestCompileError, compile_scenario
from specdbt.parser import parse_feature_text

SIMPLE_SOURCE = """Feature: F

  @unit
  Scenario: Simple
    Given the following rows in "raw_customers":
      | id | first_name |
      | 1  | Michael    |
    When the "stg_customers" model runs
    Then the "stg_customers" should produce the following rows:
      | customer_id | first_name |
      | 1           | Michael    |
"""


def test_compiles_model_name_given_and_expect():
    scenario = parse_feature_text(SIMPLE_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.model_name == "stg_customers"
    assert compiled.given == [
        {"input": "ref('raw_customers')", "rows": [{"id": 1, "first_name": "Michael"}]}
    ]
    assert compiled.expect_rows == [{"customer_id": 1, "first_name": "Michael"}]
    assert compiled.is_incremental is None


def test_tracks_original_steps_for_reporting():
    scenario = parse_feature_text(SIMPLE_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert len(compiled.given_steps) == 1
    assert compiled.given_steps[0].text.startswith('the following rows in "raw_customers"')
    assert compiled.when_step.text == 'the "stg_customers" model runs'
    assert compiled.then_step.text.startswith('the "stg_customers" should produce')


MULTI_GIVEN_SOURCE = """Feature: F

  @unit
  Scenario: Two inputs
    Given the following rows in "stg_orders":
      | order_id |
      | 1        |
    And the following rows in "stg_payments":
      | payment_id | order_id |
      | 1          | 1        |
    When the "orders" model runs
    Then the "orders" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_multiple_given_steps_each_become_a_given_entry():
    scenario = parse_feature_text(MULTI_GIVEN_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert [g["input"] for g in compiled.given] == ["ref('stg_orders')", "ref('stg_payments')"]


INCREMENTAL_SOURCE = """Feature: F

  @unit @incremental_model
  Scenario: Incremental mode
    Given the following rows in "stg_orders":
      | order_id | order_date |
      | 2        | 2018-01-02 |
    And the following rows already in "order_history":
      | order_id | order_date |
      | 1        | 2018-01-01 |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id | order_date |
      | 2        | 2018-01-02 |
"""


def test_already_in_step_compiles_to_input_this_and_sets_is_incremental_true():
    scenario = parse_feature_text(INCREMENTAL_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.is_incremental is True
    assert {"input": "this", "rows": [{"order_id": 1, "order_date": "2018-01-01"}]} in compiled.given


FULL_REFRESH_SOURCE = """Feature: F

  @unit @incremental_model
  Scenario: Full refresh mode
    Given the following rows in "stg_orders":
      | order_id |
      | 1        |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_incremental_model_tag_without_already_in_step_sets_is_incremental_false():
    scenario = parse_feature_text(FULL_REFRESH_SOURCE).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.is_incremental is False


def test_no_incremental_model_tag_leaves_is_incremental_none_even_with_already_in_step():
    # @incremental_model is what turns "already in" wording into an actual
    # overrides block -- without the tag, is_incremental stays unset even if
    # an "already in" step is (unusually) present, matching spec §4.1
    # finding 8's exception being opt-in, not inferred from step wording alone.
    scenario = parse_feature_text(INCREMENTAL_SOURCE.replace("@incremental_model ", "")).scenarios[0]
    compiled = compile_scenario(scenario)
    assert compiled.is_incremental is None


PROSE_THEN_SOURCE = """Feature: F

  @unit
  Scenario: Prose then has nothing to translate to
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then "m" should have 1 row
"""


def test_prose_then_step_raises_unit_test_compile_error():
    scenario = parse_feature_text(PROSE_THEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError, match="canonical"):
        compile_scenario(scenario)


MACRO_WHEN_SOURCE = """Feature: F

  @unit
  Scenario: Macro when step has no unit mechanism
    Given the following rows in "orders":
      | order_id |
      | 1        |
    When the "select order_id from orders" macro runs
    Then the "select order_id from orders" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_macro_when_step_raises_unit_test_compile_error_naming_dbt_core_10547():
    scenario = parse_feature_text(MACRO_WHEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError, match="dbt-core#10547"):
        compile_scenario(scenario)


NO_THEN_SOURCE = """Feature: F

  @unit
  Scenario: Missing then
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
"""


def test_scenario_with_no_then_step_raises_unit_test_compile_error():
    scenario = parse_feature_text(NO_THEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError, match="no row-table Then"):
        compile_scenario(scenario)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/native_unit_tests/test_model_compiler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.native_unit_tests.model_compiler'`

- [ ] **Step 3: Implement**

Create `src/specdbt/native_unit_tests/model_compiler.py`:

```python
"""Compiles a Gherkin Scenario (Given fixtures, incremental tag/step
wording, canonical row-table Then) into the pieces render_unit_test_yaml
needs (spec §4, §4.1, §6). Pure -- no dbt invocation, no file I/O; also
carries the original Step objects so the caller can echo real step text
back into StepResults, matching how the integration tier's report reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from specdbt.assertions import PRODUCES_ROWS_RE
from specdbt.parser import Scenario, Step
from specdbt.typing_utils import rows_from_data_table

_GIVEN_ROWS_RE = re.compile(r'the following rows in "([^"]+)":')
_GIVEN_ROWS_ALREADY_IN_RE = re.compile(r'the following rows already in "([^"]+)":')
_WHEN_MODEL_RE = re.compile(r'the "([^"]+)" model runs$')

TAG_INCREMENTAL_MODEL = "@incremental_model"


class UnitTestCompileError(ValueError):
    """Raised when a scenario resolved to the unit tier can't be compiled to
    a unit_tests: YAML entry -- names the fix, per spec §6."""


@dataclass
class CompiledUnitTest:
    model_name: str
    given: list[dict]
    expect_rows: list[dict]
    is_incremental: bool | None
    given_steps: list[Step] = field(default_factory=list)
    when_step: Step | None = None
    then_step: Step | None = None


def compile_scenario(scenario: Scenario) -> CompiledUnitTest:
    model_name: str | None = None
    given: list[dict] = []
    given_steps: list[Step] = []
    expect_rows: list[dict] | None = None
    has_already_in = False
    when_step: Step | None = None
    then_step: Step | None = None

    for step in scenario.steps:
        if step.type == "Context":
            given_steps.append(step)
            already_in_match = _GIVEN_ROWS_ALREADY_IN_RE.search(step.text)
            if already_in_match is not None:
                has_already_in = True
                if not step.table:
                    raise UnitTestCompileError(f"Given step has no data table: {step.text!r}")
                given.append({"input": "this", "rows": rows_from_data_table(step.table)})
                continue
            rows_match = _GIVEN_ROWS_RE.search(step.text)
            if rows_match is None:
                raise UnitTestCompileError(
                    "@unit scenario's Given step doesn't match a supported "
                    f"fixture pattern: {step.text!r}"
                )
            if not step.table:
                raise UnitTestCompileError(f"Given step has no data table: {step.text!r}")
            fixture_name = rows_match.group(1)
            given.append(
                {"input": f"ref('{fixture_name}')", "rows": rows_from_data_table(step.table)}
            )
        elif step.type == "Action":
            when_step = step
            model_match = _WHEN_MODEL_RE.search(step.text)
            if model_match is None:
                raise UnitTestCompileError(
                    "@unit scenario's When step must be 'the \"<model>\" model "
                    "runs' -- macro unit testing has no native dbt mechanism yet "
                    f"(dbt-core#10547); tag @integration instead. Got: {step.text!r}"
                )
            model_name = model_match.group(1)
        else:  # "Outcome"
            then_step = step
            then_match = PRODUCES_ROWS_RE.match(step.text)
            if then_match is None:
                raise UnitTestCompileError(
                    "@unit scenario's Then step must be the canonical "
                    '"...should produce the following rows:" form (spec §6) -- '
                    f"prose assertions have nothing to translate to in the "
                    f"unit tier. Got: {step.text!r}"
                )
            if not step.table:
                raise UnitTestCompileError(f"{step.text!r} requires a data table of expected rows")
            expect_rows = rows_from_data_table(step.table)

    if when_step is None or model_name is None:
        raise UnitTestCompileError(f'@unit scenario "{scenario.name}" has no When step')
    if then_step is None or expect_rows is None:
        raise UnitTestCompileError(
            f'@unit scenario "{scenario.name}" has no row-table Then step -- '
            "add one, or tag @integration explicitly (spec §6)"
        )

    is_incremental: bool | None = None
    if TAG_INCREMENTAL_MODEL in scenario.tags:
        is_incremental = has_already_in

    return CompiledUnitTest(
        model_name=model_name,
        given=given,
        expect_rows=expect_rows,
        is_incremental=is_incremental,
        given_steps=given_steps,
        when_step=when_step,
        then_step=then_step,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/native_unit_tests/test_model_compiler.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/native_unit_tests/model_compiler.py tests/native_unit_tests/test_model_compiler.py
git commit -m "feat: compile_scenario -- Gherkin to CompiledUnitTest, including input: this and @incremental_model (spec §4, §6)"
```

---

### Task 7: Shared prod guard + `ModelUnitTestCompiler` — the real mechanism

**Files:**
- Create: `src/specdbt/adapters/prod_guard.py`
- Modify: `src/specdbt/adapters/dbt_adapter.py`
- Create: `src/specdbt/native_unit_tests/model_unit_test_compiler.py`
- Modify: `tests/conftest.py`
- Create: `tests/native_unit_tests/test_model_unit_test_compiler.py`
- Test: `tests/test_dbt_adapter.py` (existing import path stays valid,
  verify only)

This task's new tests actually invoke `dbtRunner` against a real DuckDB
file — the only thing that proves the mechanism (same reasoning as Plan
A's Task 7 note about not trusting reported success).

**Interfaces:**
- Produces (`prod_guard.py`): `ProdSchemaGuardError`,
  `guard_against_prod_target(target: str | None, allow_any_schema: bool)
  -> None`
- Produces (`model_unit_test_compiler.py`): `DbtInvocationError`,
  `ModelUnitTestCompiler(project_dir, profiles_dir, *, target=None,
  allow_any_schema=False)` implementing `NativeTestCompiler`
- Consumes: `guard_against_prod_target` (this task), `compile_scenario`
  (Task 6), `render_unit_test_yaml`/`write_unit_test_yaml`/
  `delete_unit_test_yaml`/`unit_test_name` (Task 5)

- [ ] **Step 1: Extract the shared prod guard**

Create `src/specdbt/adapters/prod_guard.py`:

```python
"""Shared prod-schema heuristic guard (spec §5.3) -- used by every real-
execution path that touches a dbt target: DbtExecutionAdapter (macro/model
integration tier, ephemeral) and ModelUnitTestCompiler (model unit tier --
its prebuild step, spec §4.1 finding 6, writes real tables into the
project's actually-configured schema, not an ephemeral one, so it needs the
same guard).
"""

from __future__ import annotations


class ProdSchemaGuardError(RuntimeError):
    """Raised when the configured target name looks like production and
    allow_any_schema was not passed."""


def guard_against_prod_target(target: str | None, allow_any_schema: bool) -> None:
    if target and "prod" in target.lower() and not allow_any_schema:
        raise ProdSchemaGuardError(
            f"target {target!r} looks like production -- refusing to run. "
            "Pass allow_any_schema=True (CLI: --allow-any-schema) if this "
            "is really what you want."
        )
```

In `src/specdbt/adapters/dbt_adapter.py`, replace the existing
`ProdSchemaGuardError` class definition and its inline check. Change the
import block at the top:

```python
from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.adapters.prod_guard import ProdSchemaGuardError, guard_against_prod_target
```

Delete the existing `class ProdSchemaGuardError(RuntimeError): ...`
definition entirely (it now lives in `prod_guard.py`; the import above
re-exports the name so `from specdbt.adapters.dbt_adapter import
ProdSchemaGuardError` — used by `tests/test_dbt_adapter.py` — keeps
working unchanged).

Replace the inline guard in `DbtExecutionAdapter.__init__`:

```python
        if target and "prod" in target.lower() and not allow_any_schema:
            raise ProdSchemaGuardError(
                f"target {target!r} looks like production -- refusing to run. "
                "Pass allow_any_schema=True (CLI: --allow-any-schema) if this "
                "is really what you want."
            )
```

with:

```python
        guard_against_prod_target(target, allow_any_schema)
```

- [ ] **Step 2: Run the existing dbt_adapter suite to confirm the refactor is behavior-preserving**

Run: `uv run pytest tests/test_dbt_adapter.py -v`
Expected: PASS, all pre-existing tests unchanged (this step has no new
test of its own — it's a refactor, proven by the existing suite still
passing).

- [ ] **Step 3: Add a scratch project fixture with a real ref() edge**

In `tests/conftest.py`, add below the existing `scratch_dbt_project`
fixture:

```python
@pytest.fixture
def scratch_dbt_project_with_upstream(tmp_path: Path) -> Path:
    """Unlike scratch_dbt_project's single placeholder model, this one has
    a real ref() edge (upstream_model -> downstream_model) -- unit testing
    needs something to override, and something to build first (spec §4.1
    finding 6: the given input must already be a real, built relation for
    dbt to introspect its column types)."""
    project_dir = tmp_path / "scratch_project_upstream"
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
    (project_dir / "models" / "upstream_model.sql").write_text(
        "select 1 as id, 'placed' as status\n"
    )
    (project_dir / "models" / "downstream_model.sql").write_text(
        "select id, upper(status) as status from {{ ref('upstream_model') }}\n"
    )
    return project_dir
```

- [ ] **Step 4: Write the failing tests**

Create `tests/native_unit_tests/test_model_unit_test_compiler.py`:

```python
from pathlib import Path

import pytest

from specdbt.adapters.prod_guard import ProdSchemaGuardError
from specdbt.native_unit_tests.model_compiler import UnitTestCompileError
from specdbt.native_unit_tests.model_unit_test_compiler import (
    DbtInvocationError,
    ModelUnitTestCompiler,
)
from specdbt.parser import parse_feature_text

PASSING_SOURCE = """Feature: F

  @unit
  Scenario: Uppercases status
    Given the following rows in "upstream_model":
      | id | status |
      | 1  | placed |
    When the "downstream_model" model runs
    Then the "downstream_model" should produce the following rows:
      | id | status |
      | 1  | PLACED |
"""

FAILING_SOURCE = """Feature: F

  @unit
  Scenario: Wrong expectation
    Given the following rows in "upstream_model":
      | id | status |
      | 1  | placed |
    When the "downstream_model" model runs
    Then the "downstream_model" should produce the following rows:
      | id | status |
      | 1  | ZZZ    |
"""

BAD_MODEL_SOURCE = """Feature: F

  @unit
  Scenario: References a model that doesn't exist
    Given the following rows in "upstream_model":
      | id |
      | 1  |
    When the "does_not_exist" model runs
    Then the "does_not_exist" should produce the following rows:
      | id |
      | 1  |
"""

PROSE_THEN_SOURCE = """Feature: F

  @unit
  Scenario: Prose then not allowed in unit tier
    Given the following rows in "upstream_model":
      | id |
      | 1  |
    When the "downstream_model" model runs
    Then "downstream_model" should have 1 row
"""


def test_refuses_a_target_that_looks_like_production(tmp_path: Path):
    with pytest.raises(ProdSchemaGuardError):
        ModelUnitTestCompiler(project_dir=tmp_path, profiles_dir=tmp_path, target="prod")


def test_compile_error_propagates_without_touching_dbt_at_all(tmp_path: Path):
    # tmp_path is not a real dbt project -- if this reached dbtRunner it
    # would fail with a *different* error than UnitTestCompileError, so this
    # also proves compile_scenario runs before _ensure_project_prebuilt.
    compiler = ModelUnitTestCompiler(project_dir=tmp_path, profiles_dir=tmp_path)
    scenario = parse_feature_text(PROSE_THEN_SOURCE).scenarios[0]
    with pytest.raises(UnitTestCompileError):
        compiler.run(scenario)


def test_run_translates_a_passing_unit_test_to_all_passing_step_results(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    step_results = compiler.run(scenario)
    assert len(step_results) == 3  # Given, When, Then
    assert all(r.passed for r in step_results)


def test_run_translates_a_failing_unit_test_with_ansi_stripped_diff(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(FAILING_SOURCE).scenarios[0]
    step_results = compiler.run(scenario)
    assert step_results[0].passed is True  # Given
    assert step_results[1].passed is True  # When
    assert step_results[2].passed is False  # Then
    assert "\x1b[" not in step_results[2].error
    assert "ZZZ" in step_results[2].error


def test_run_tears_down_the_generated_yaml_file_on_pass_and_on_fail(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    for source in (PASSING_SOURCE, FAILING_SOURCE):
        scenario = parse_feature_text(source).scenarios[0]
        compiler.run(scenario)
        assert list((scratch_dbt_project_with_upstream / "models").glob("_specdbt_*.yml")) == []


def test_run_raises_dbt_invocation_error_when_the_model_does_not_exist(
    scratch_dbt_project_with_upstream: Path,
):
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(BAD_MODEL_SOURCE).scenarios[0]
    with pytest.raises(DbtInvocationError):
        compiler.run(scenario)
    assert list((scratch_dbt_project_with_upstream / "models").glob("_specdbt_*.yml")) == []


def test_run_works_across_multiple_calls_on_the_same_compiler_instance(
    scratch_dbt_project_with_upstream: Path,
):
    # exercises the prebuild-once-not-per-scenario path (spec §4.1 finding 6)
    compiler = ModelUnitTestCompiler(
        project_dir=scratch_dbt_project_with_upstream,
        profiles_dir=scratch_dbt_project_with_upstream / "profiles",
    )
    scenario = parse_feature_text(PASSING_SOURCE).scenarios[0]
    first = compiler.run(scenario)
    second = compiler.run(scenario)
    assert all(r.passed for r in first)
    assert all(r.passed for r in second)
```

- [ ] **Step 5: Run to verify it fails**

Run: `uv run pytest tests/native_unit_tests/test_model_unit_test_compiler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'specdbt.native_unit_tests.model_unit_test_compiler'`

- [ ] **Step 6: Implement**

Create `src/specdbt/native_unit_tests/model_unit_test_compiler.py`:

```python
"""Real unit-tier orchestration for models: compiles a Scenario to a
generated unit_tests: YAML file, runs it for real via dbtRunner, and
translates dbt's own pass/fail + diff into specdbt's StepResult format
(spec §4, §4.1). The only NativeTestCompiler this plan registers -- the
macro slot stays unregistered (spec §5.4, dbt-core#10547).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import yaml as _yaml
from dbt.cli.main import dbtRunner

from specdbt.adapters.prod_guard import guard_against_prod_target
from specdbt.native_unit_tests.compiler import NativeTestCompiler
from specdbt.native_unit_tests.model_compiler import compile_scenario
from specdbt.native_unit_tests.yaml_file import (
    delete_unit_test_yaml,
    render_unit_test_yaml,
    unit_test_name,
    write_unit_test_yaml,
)
from specdbt.parser import Scenario
from specdbt.reporter import StepResult

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class DbtInvocationError(RuntimeError):
    """Raised when a dbtRunner.invoke() call itself fails to run -- a
    seed/run prebuild step failing outright, or a test invocation whose
    result.result is None (a genuine parse/compile error, spec §4.1
    finding 2) -- never for a unit test that ran and legitimately failed;
    that case is translated into a failed StepResult instead."""


class ModelUnitTestCompiler(NativeTestCompiler):
    def __init__(
        self,
        project_dir: Path,
        profiles_dir: Path,
        *,
        target: str | None = None,
        allow_any_schema: bool = False,
    ) -> None:
        guard_against_prod_target(target, allow_any_schema)
        self._project_dir = Path(project_dir)
        self._profiles_dir = Path(profiles_dir)
        self._target = target
        self._runner = dbtRunner()
        self._prebuilt = False

    def run(self, scenario: Scenario) -> list[StepResult]:
        compiled = compile_scenario(scenario)
        self._ensure_project_prebuilt()

        run_id = uuid.uuid4().hex
        project_name = self._project_name()
        yaml_text = render_unit_test_yaml(
            run_id=run_id,
            model_name=compiled.model_name,
            given=compiled.given,
            expect_rows=compiled.expect_rows,
            is_incremental=compiled.is_incremental,
        )
        yaml_path = write_unit_test_yaml(self._project_dir, run_id, yaml_text)
        try:
            selector = f"unit_test:{project_name}.{unit_test_name(run_id)}"
            result = self._invoke_test(["test", "--select", selector])
            test_result = result.result.results[0]
            passed = test_result.status == "pass"
            message = _ANSI_RE.sub("", test_result.message or "") if not passed else None

            given_results = [
                StepResult(s.keyword, s.text, passed=True) for s in compiled.given_steps
            ]
            when_result = StepResult(compiled.when_step.keyword, compiled.when_step.text, passed=True)
            then_result = StepResult(
                compiled.then_step.keyword, compiled.then_step.text, passed=passed, error=message
            )
            return [*given_results, when_result, then_result]
        finally:
            delete_unit_test_yaml(yaml_path)

    def _ensure_project_prebuilt(self) -> None:
        """One dbt seed + dbt run for the whole project, once per compiler
        instance -- not per scenario. Necessary and sufficient for every
        given: input: ref()/source()/this target to be a real,
        introspectable relation before any unit test runs (spec §4.1
        findings 6, 8)."""
        if self._prebuilt:
            return
        self._invoke_must_succeed(["seed"])
        self._invoke_must_succeed(["run"])
        self._prebuilt = True

    def _project_name(self) -> str:
        project_yml = self._project_dir / "dbt_project.yml"
        return _yaml.safe_load(project_yml.read_text())["name"]

    def _invoke_must_succeed(self, args: list[str]):
        result = self._raw_invoke(args)
        if not result.success:
            raise DbtInvocationError(f"dbt {args[0]} failed: {result.exception}")
        return result

    def _invoke_test(self, args: list[str]):
        """Unlike _invoke_must_succeed, result.success == False is the
        NORMAL outcome of a legitimately failing unit test (spec §4.1
        finding 2) -- only result.result is None (dbt couldn't even run: a
        parse/compile error) is a real invocation failure here."""
        result = self._raw_invoke(args)
        if result.result is None:
            raise DbtInvocationError(f"dbt {args[0]} failed to run: {result.exception}")
        return result

    def _raw_invoke(self, args: list[str]):
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
        return self._runner.invoke(full_args)
```

- [ ] **Step 7: Run to verify it passes**

Run: `uv run pytest tests/native_unit_tests/test_model_unit_test_compiler.py -v`
Expected: PASS, all tests.

- [ ] **Step 8: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/adapters/prod_guard.py src/specdbt/adapters/dbt_adapter.py src/specdbt/native_unit_tests/model_unit_test_compiler.py tests/conftest.py tests/native_unit_tests/test_model_unit_test_compiler.py
git commit -m "feat: ModelUnitTestCompiler -- real dbt test execution for the unit tier (spec §4, §4.1)"
```

---

### Task 8: Runner integration — tier dispatch

**Files:**
- Modify: `src/specdbt/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Modifies: `run_feature_text(source, adapter, compiler_registry:
  CompilerRegistry | None = None)`, `run_feature_file(path, adapter,
  compiler_registry: CompilerRegistry | None = None)` — new optional third
  parameter, default `None`, so every existing 2-arg call site (Plan A's
  own tests) keeps working unchanged.
- Produces: `_detect_resource_kind(scenario: Scenario) -> str`,
  `_run_integration_tier_scenario` (renamed from the old `_run_scenario`,
  body unchanged).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_runner.py`:

```python
from specdbt.native_unit_tests.compiler import CompilerRegistry, NativeTestCompiler
from specdbt.parser import Scenario
from specdbt.reporter import StepResult


class _StubCompiler(NativeTestCompiler):
    def __init__(self, step_results):
        self._step_results = step_results

    def run(self, scenario: Scenario) -> list[StepResult]:
        return self._step_results


UNTAGGED_MODEL_SOURCE = """Feature: F

  Scenario: Untagged model scenario
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | c |
      | 1 |
"""


def test_untagged_model_scenario_defaults_to_unit_tier_when_a_compiler_is_registered():
    registry = CompilerRegistry()
    registry.register("model", _StubCompiler([StepResult("Then", "x", passed=True)]))
    adapter = FakeAdapter()  # never touched -- unit tier doesn't use the adapter
    report = run_feature_text(UNTAGGED_MODEL_SOURCE, adapter, registry)
    assert report.scenarios[0].passed is True


def test_untagged_model_scenario_uses_integration_tier_when_no_compiler_registered():
    registry = CompilerRegistry()  # no "model" compiler registered
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    report = run_feature_text(UNTAGGED_MODEL_SOURCE, adapter, registry)
    assert report.scenarios[0].passed is True  # ran through the real integration path


INTEGRATION_TAGGED_SOURCE = """Feature: F

  @integration
  Scenario: Explicitly integration-tagged
    Given the following rows in "a":
      | c |
      | 1 |
    When the "m" model runs
    Then the "m" should produce the following rows:
      | c |
      | 1 |
"""


def test_integration_tag_bypasses_a_registered_unit_compiler():
    registry = CompilerRegistry()
    registry.register(
        "model", _StubCompiler([StepResult("Then", "x", passed=False, error="should never run")])
    )
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    report = run_feature_text(INTEGRATION_TAGGED_SOURCE, adapter, registry)
    assert report.scenarios[0].passed is True  # used the adapter, not the stub compiler


UNIT_TAGGED_MACRO_SOURCE = """Feature: F

  @unit
  Scenario: Unit-tagged macro has nowhere to go
    Given the following rows in "orders":
      | order_id |
      | 1        |
    When the "select order_id from orders" macro runs
    Then the "select order_id from orders" should produce the following rows:
      | order_id |
      | 1        |
"""


def test_unit_tagged_macro_scenario_fails_clearly_with_no_macro_compiler_registered():
    registry = CompilerRegistry()  # macro slot never registered, spec §5.4
    adapter = FakeAdapter()
    report = run_feature_text(UNIT_TAGGED_MACRO_SOURCE, adapter, registry)
    scenario = report.scenarios[0]
    assert scenario.passed is False
    assert "dbt-core#10547" in scenario.steps[0].error


def test_run_feature_text_without_a_registry_arg_still_works_integration_only():
    # backward compatibility: Plan A's own existing 2-arg call sites get an
    # implicit empty CompilerRegistry(), so every scenario resolves to the
    # integration tier exactly as it did before this plan.
    adapter = FakeAdapter()
    adapter.register("m", ExecutionResult.of(rows=[{"c": 1}]))
    report = run_feature_text(UNTAGGED_MODEL_SOURCE, adapter)
    assert report.scenarios[0].passed is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_runner.py -v`
Expected: FAIL — `TypeError: run_feature_text() takes 2 positional arguments but 3 were given`

- [ ] **Step 3: Implement**

Replace `src/specdbt/runner.py` in full:

```python
"""Wires parser -> fixtures -> adapter -> assertions -> reporter into one
pipeline (spec: docs/superpowers/specs/2026-08-23-specdbt-phase0-design.md,
2026-08-23-specdbt-phase1-design-v2.md §3/§10). Tier resolution (spec §3)
picks, per scenario, between two entirely different control paths: the
integration tier below executes step-by-step, threading results forward as
each step runs; the unit tier hands the WHOLE scenario to a
NativeTestCompiler, since dbt's own unit-test runner does the given/when/
then work itself -- the Then step's table there is an *input* to
compilation, read before anything executes, not a check performed after.
"""

from __future__ import annotations

import re
from pathlib import Path

from specdbt.adapters.base import ExecutionAdapter, ExecutionResult
from specdbt.assertions import ThenContext, evaluate_then_step
from specdbt.fixtures import Fixture, build_fixture
from specdbt.native_unit_tests.compiler import (
    CompilerRegistry,
    get_compiler_or_raise,
    resolve_tier,
)
from specdbt.parser import Scenario, parse_feature_text
from specdbt.reporter import FeatureReport, ScenarioReport, StepResult

_WHEN_MODEL_RE = re.compile(r'the "([^"]+)" model runs$')
_WHEN_MACRO_RE = re.compile(r'the "(.+)" macro runs$')


def run_feature_text(
    source: str, adapter: ExecutionAdapter, compiler_registry: CompilerRegistry | None = None
) -> FeatureReport:
    feature = parse_feature_text(source)
    registry = compiler_registry if compiler_registry is not None else CompilerRegistry()
    scenario_reports = [_run_scenario(scenario, adapter, registry) for scenario in feature.scenarios]
    return FeatureReport(name=feature.name, scenarios=scenario_reports)


def run_feature_file(
    path: Path, adapter: ExecutionAdapter, compiler_registry: CompilerRegistry | None = None
) -> FeatureReport:
    return run_feature_text(Path(path).read_text(), adapter, compiler_registry)


def _detect_resource_kind(scenario: Scenario) -> str:
    for step in scenario.steps:
        if step.type == "Action":
            if _WHEN_MODEL_RE.search(step.text) is not None:
                return "model"
            if _WHEN_MACRO_RE.search(step.text) is not None:
                return "macro"
            raise ValueError(f"no When-step pattern matches: {step.text!r}")
    raise ValueError(f'scenario "{scenario.name}" has no When step')


def _run_scenario(
    scenario: Scenario, adapter: ExecutionAdapter, registry: CompilerRegistry
) -> ScenarioReport:
    resource_kind = _detect_resource_kind(scenario)
    tier = resolve_tier(scenario.tags, resource_kind, registry)

    if tier == "unit":
        try:
            compiler = get_compiler_or_raise(registry, resource_kind)
            step_results = compiler.run(scenario)
        except Exception as exc:  # noqa: BLE001 -- any compile/run error becomes one failed step
            step_results = [StepResult("Scenario", scenario.name, passed=False, error=str(exc))]
        return ScenarioReport(name=scenario.name, steps=step_results)

    return _run_integration_tier_scenario(scenario, adapter)


def _run_integration_tier_scenario(scenario: Scenario, adapter: ExecutionAdapter) -> ScenarioReport:
    fixtures: dict[str, Fixture] = {}
    results: dict[str, ExecutionResult] = {}
    last_model: str | None = None
    step_results: list[StepResult] = []

    for step in scenario.steps:
        try:
            if step.type == "Context":
                fixture = build_fixture(step)
                fixtures[fixture.name] = fixture
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
            else:  # "Outcome"
                evaluate_then_step(
                    step.text,
                    ThenContext(results=results, last_model=last_model),
                    table=step.table or None,
                )
        except Exception as exc:  # noqa: BLE001 -- any step-level error becomes a failed step
            step_results.append(StepResult(step.keyword, step.text, passed=False, error=str(exc)))
            break
        else:
            step_results.append(StepResult(step.keyword, step.text, passed=True))

    return ScenarioReport(name=scenario.name, steps=step_results)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_runner.py -v`
Expected: PASS, all tests including every pre-existing one (2-arg calls
still work via the default `None` → empty registry → integration tier for
everything, exactly Plan A's behavior).

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/runner.py tests/test_runner.py
git commit -m "feat: runner tier dispatch -- @unit routes to NativeTestCompiler, @integration/default keeps Plan A's step-by-step path"
```

---

### Task 9: CLI wiring — `--engine dbt` registers the unit-tier compiler

**Files:**
- Modify: `src/specdbt/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Modifies: the `run` command's `--engine dbt` branch — builds a
  `CompilerRegistry` with `ModelUnitTestCompiler` registered under
  `"model"`, passed through to `run_feature_file`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_run_with_dbt_engine_and_unit_tagged_scenario_uses_the_model_unit_test_compiler(
    tmp_path: Path,
):
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
    (project_dir / "models" / "upstream.sql").write_text("select 1 as id, 'placed' as status\n")
    (project_dir / "models" / "downstream.sql").write_text(
        "select id, upper(status) as status from {{ ref('upstream') }}\n"
    )

    features = tmp_path / "features"
    features.mkdir()
    (features / "unit.feature").write_text(
        "Feature: Unit\n\n"
        "  @unit\n"
        "  Scenario: Uppercase status\n"
        '    Given the following rows in "upstream":\n'
        "      | id | status |\n"
        "      | 1  | placed |\n"
        '    When the "downstream" model runs\n'
        '    Then the "downstream" should produce the following rows:\n'
        "      | id | status |\n"
        "      | 1  | PLACED |\n"
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
    assert "1 scenario(s)" in result.output
    assert "0 failure(s)" in result.output
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_run_with_dbt_engine_and_unit_tagged_scenario_uses_the_model_unit_test_compiler -v`
Expected: FAIL — the scenario reports a failure, since `--engine dbt`
today builds no `CompilerRegistry` at all, so `@unit` gets the "not
supported" error against whatever resource kind it resolves against
`resource_kind="model"` with an empty registry — `0 failure(s)` won't
appear in output.

- [ ] **Step 3: Implement**

In `src/specdbt/cli.py`, add to the imports:

```python
from specdbt.native_unit_tests.compiler import CompilerRegistry
from specdbt.native_unit_tests.model_unit_test_compiler import ModelUnitTestCompiler
```

In the `run` command, replace the `dbt_adapter` construction block:

```python
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
```

with:

```python
    dbt_adapter: DbtExecutionAdapter | None = None
    compiler_registry: CompilerRegistry | None = None
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
        compiler_registry = CompilerRegistry()
        compiler_registry.register(
            "model",
            ModelUnitTestCompiler(
                project_dir=project_dir,
                profiles_dir=profiles_dir or project_dir,
                target=dbt_target,
                allow_any_schema=allow_any_schema,
            ),
        )
```

And the loop that builds `reports`:

```python
        reports.append(run_feature_file(path, adapter))
```

becomes:

```python
        reports.append(run_feature_file(path, adapter, compiler_registry))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS, all tests.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add src/specdbt/cli.py tests/test_cli.py
git commit -m "feat: specdbt run --engine dbt registers ModelUnitTestCompiler -- @unit scenarios now runnable from the CLI"
```

---

### Task 10: `docs/gherkin-style-guide.md`

**Files:**
- Create: `docs/gherkin-style-guide.md`

Static content, no code. Per spec §7/§12 DoD, this needs to exist and the
example scenarios (Task 12) need to conform to it.

- [ ] **Step 1: Write the file**

Create `docs/gherkin-style-guide.md`:

```markdown
# specdbt Gherkin Style Guide

specdbt invents no Gherkin dialect. Every rule below is a constraint on how
you use features standard Gherkin already has, grounded directly in
Cucumber's own BDD guidance (`cucumber.io/docs/bdd`,
`cucumber.io/docs/bdd/better-gherkin`) — not a specdbt-specific convention.

## Write declarative scenarios, not imperative ones

A scenario states *what* should be true, not the steps a human would click
through to get there. This is the one property that makes a scenario both
good living documentation for a non-technical reader and good context for
an LLM to extend by analogy — not two separate goals.

**Imperative (avoid):**

```gherkin
Given I insert a row into "raw_customers" with id 1
And I run dbt on "stg_customers"
And I query "stg_customers"
Then the first row's customer_id column equals 1
```

**Declarative (required):**

```gherkin
Given the following rows in "raw_customers":
  | id | first_name |
  | 1  | Michael    |
When the "stg_customers" model runs
Then the "stg_customers" should produce the following rows:
  | customer_id | first_name |
  | 1           | Michael    |
```

The declarative version states the transformation's *contract* (rename
`id` to `customer_id`, pass `first_name` through) — it reads the same
whether a human, an LLM, or `specdbt docs` (a future command, not yet
built) is the audience.

## Name scenarios by business behavior, not mechanism

`Scenario: Uppercases status` describes what a person cares about.
`Scenario: Test case 3` or `Scenario: upper() macro call` does not — it
requires opening the scenario body to learn anything.

## Data tables are the default; doc strings are the escape hatch

The row-table `Given`/`Then` forms (`the following rows in "<x>":` /
`the "<x>" should produce the following rows:`) are how almost every
scenario in this project expresses fixtures and expectations — see every
example under `examples/`. Gherkin's doc-string syntax with a content-type
annotation (` ```markdown `, ` ```json `) is reserved for the rare case
where an expected payload is a large structured blob a data table would
make unreadable. No scenario in this project needs it yet — this section
exists so a future one that does knows the mechanism is sanctioned, not
invented ad hoc.

## Tag scenarios for what's actually true about them, not for routing tricks

`@unit` / `@integration` (spec §3) state which tier a scenario needs — use
them only when the resource-kind default (model → unit, macro →
integration) is wrong for a specific scenario, not as a habit. `@incremental_model`
(spec §4.1 finding 8) states a real fact about the model under test — it
belongs on every scenario for an incremental model, not just the ones that
happen to need `input: this`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/gherkin-style-guide.md
git commit -m "docs: gherkin style guide -- declarative scenarios, spec §7/§12"
```

---

### Task 11: jaffle_shop example project scaffold

**Files:**
- Create: `examples/jaffle_shop/dbt_project.yml`
- Create: `examples/jaffle_shop/profiles/profiles.yml`
- Create: `examples/jaffle_shop/seeds/raw_customers.csv`
- Create: `examples/jaffle_shop/seeds/raw_orders.csv`
- Create: `examples/jaffle_shop/seeds/raw_payments.csv`
- Create: `examples/jaffle_shop/models/staging/stg_customers.sql`
- Create: `examples/jaffle_shop/models/staging/stg_orders.sql`
- Create: `examples/jaffle_shop/models/staging/stg_payments.sql`
- Create: `examples/jaffle_shop/models/staging/schema.yml`
- Create: `examples/jaffle_shop/models/customers.sql`
- Create: `examples/jaffle_shop/models/orders.sql`
- Create: `examples/jaffle_shop/models/schema.yml`
- Create: `examples/jaffle_shop/models/order_history.sql`

All staging/mart model and seed content below is the real
`dbt-labs/jaffle-shop-classic` project (fetched 2026-08-23, `main` branch)
— not paraphrased, not invented — except `order_history.sql`, which is
specdbt's own addition (spec §12 DoD needs an incremental-model scenario;
jaffle-shop-classic itself has none). This satisfies spec §8's "jaffle_shop
... model scenarios, unit tier" example-project requirement.

- [ ] **Step 1: Project config**

Create `examples/jaffle_shop/dbt_project.yml`:

```yaml
name: 'jaffle_shop'

config-version: 2
version: '0.1'

profile: 'jaffle_shop'

model-paths: ["models"]
seed-paths: ["seeds"]

target-path: "target"
clean-targets:
    - "target"
    - "dbt_modules"
    - "logs"

require-dbt-version: [">=1.0.0", "<2.0.0"]

models:
  jaffle_shop:
      materialized: table
      staging:
        materialized: view
```

Create `examples/jaffle_shop/profiles/profiles.yml`:

```yaml
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "jaffle_shop.duckdb"
      schema: main
```

- [ ] **Step 2: Seeds**

Create `examples/jaffle_shop/seeds/raw_customers.csv`:

```
id,first_name,last_name
1,Michael,P.
2,Shawn,M.
3,Kathleen,P.
```

Create `examples/jaffle_shop/seeds/raw_orders.csv`:

```
id,user_id,order_date,status
1,1,2018-01-01,returned
2,3,2018-01-02,completed
3,94,2018-01-04,completed
```

Create `examples/jaffle_shop/seeds/raw_payments.csv`:

```
id,order_id,payment_method,amount
1,1,credit_card,1000
2,2,credit_card,2000
3,3,coupon,100
```

- [ ] **Step 3: Staging models**

Create `examples/jaffle_shop/models/staging/stg_customers.sql`:

```sql
with source as (

    {#-
    Normally we would select from the table here, but we are using seeds to load
    our data in this project
    #}
    select * from {{ ref('raw_customers') }}

),

renamed as (

    select
        id as customer_id,
        first_name,
        last_name

    from source

)

select * from renamed
```

Create `examples/jaffle_shop/models/staging/stg_orders.sql`:

```sql
with source as (

    {#-
    Normally we would select from the table here, but we are using seeds to load
    our data in this project
    #}
    select * from {{ ref('raw_orders') }}

),

renamed as (

    select
        id as order_id,
        user_id as customer_id,
        order_date,
        status

    from source

)

select * from renamed
```

Create `examples/jaffle_shop/models/staging/stg_payments.sql`:

```sql
with source as (

    {#-
    Normally we would select from the table here, but we are using seeds to load
    our data in this project
    #}
    select * from {{ ref('raw_payments') }}

),

renamed as (

    select
        id as payment_id,
        order_id,
        payment_method,

        -- `amount` is currently stored in cents, so we convert it to dollars
        amount / 100 as amount

    from source

)

select * from renamed
```

Create `examples/jaffle_shop/models/staging/schema.yml`:

```yaml
version: 2

models:
  - name: stg_customers
    columns:
      - name: customer_id
        tests:
          - unique
          - not_null

  - name: stg_orders
    columns:
      - name: order_id
        tests:
          - unique
          - not_null
      - name: status
        tests:
          - accepted_values:
              values: ['placed', 'shipped', 'completed', 'return_pending', 'returned']

  - name: stg_payments
    columns:
      - name: payment_id
        tests:
          - unique
          - not_null
      - name: payment_method
        tests:
          - accepted_values:
              values: ['credit_card', 'coupon', 'bank_transfer', 'gift_card']
```

- [ ] **Step 4: Mart models**

Create `examples/jaffle_shop/models/customers.sql`:

```sql
with customers as (

    select * from {{ ref('stg_customers') }}

),

orders as (

    select * from {{ ref('stg_orders') }}

),

payments as (

    select * from {{ ref('stg_payments') }}

),

customer_orders as (

        select
        customer_id,

        min(order_date) as first_order,
        max(order_date) as most_recent_order,
        count(order_id) as number_of_orders
    from orders

    group by customer_id

),

customer_payments as (

    select
        orders.customer_id,
        sum(amount) as total_amount

    from payments

    left join orders on
         payments.order_id = orders.order_id

    group by orders.customer_id

),

final as (

    select
        customers.customer_id,
        customers.first_name,
        customers.last_name,
        customer_orders.first_order,
        customer_orders.most_recent_order,
        customer_orders.number_of_orders,
        customer_payments.total_amount as customer_lifetime_value

    from customers

    left join customer_orders
        on customers.customer_id = customer_orders.customer_id

    left join customer_payments
        on  customers.customer_id = customer_payments.customer_id

)

select * from final
```

Create `examples/jaffle_shop/models/orders.sql`:

```sql
{% set payment_methods = ['credit_card', 'coupon', 'bank_transfer', 'gift_card'] %}

with orders as (

    select * from {{ ref('stg_orders') }}

),

payments as (

    select * from {{ ref('stg_payments') }}

),

order_payments as (

    select
        order_id,

        {% for payment_method in payment_methods -%}
        sum(case when payment_method = '{{ payment_method }}' then amount else 0 end) as {{ payment_method }}_amount,
        {% endfor -%}

        sum(amount) as total_amount

    from payments

    group by order_id

),

final as (

    select
        orders.order_id,
        orders.customer_id,
        orders.order_date,
        orders.status,

        {% for payment_method in payment_methods -%}

        order_payments.{{ payment_method }}_amount,

        {% endfor -%}

        order_payments.total_amount as amount

    from orders


    left join order_payments
        on orders.order_id = order_payments.order_id

)

select * from final
```

Create `examples/jaffle_shop/models/schema.yml`:

```yaml
version: 2

models:
  - name: customers
    description: This table has basic information about a customer, as well as some derived facts based on a customer's orders

    columns:
      - name: customer_id
        description: This is a unique identifier for a customer
        tests:
          - unique
          - not_null

  - name: orders
    description: This table has basic information about orders, as well as some derived facts based on payments

    columns:
      - name: order_id
        tests:
          - unique
          - not_null
        description: This is a unique identifier for an order

      - name: customer_id
        description: Foreign key to the customers table
        tests:
          - not_null
          - relationships:
              to: ref('customers')
              field: customer_id

      - name: status
        tests:
          - accepted_values:
              values: ['placed', 'shipped', 'completed', 'return_pending', 'returned']
```

(trimmed from the real repo's `schema.yml` to the tests that matter for
this example — `amount`/payment-method-column not-null tests are omitted
since they add no new coverage over what Task 12's unit-tier scenarios
already exercise; `description:` fields on individual payment columns are
likewise omitted as non-functional prose the real file carries.)

- [ ] **Step 5: The incremental model (specdbt's own addition)**

Create `examples/jaffle_shop/models/order_history.sql`:

```sql
{{ config(materialized='incremental') }}

select order_id, customer_id, order_date, status
from {{ ref('stg_orders') }}
{% if is_incremental() %}
where order_date > (select max(order_date) from {{ this }})
{% endif %}
```

This is specdbt's own addition, not part of jaffle-shop-classic — the
smallest possible incremental model, adapted directly from dbt's own
`is_incremental()` documentation pattern to jaffle_shop's real `stg_orders`
columns. It exists solely so Task 12 has a real incremental model to test
both `is_incremental` branches against (spec §12 DoD).

- [ ] **Step 6: Commit**

```bash
git add examples/jaffle_shop/
git commit -m "feat: jaffle_shop example project -- real jaffle-shop-classic staging/mart models + a custom incremental model (spec §8, §12)"
```

---

### Task 12: jaffle_shop unit-test example scenarios

**Files:**
- Create: `examples/jaffle_shop/features/stg_customers.feature`
- Create: `examples/jaffle_shop/features/customers.feature`
- Create: `examples/jaffle_shop/features/order_history.feature`
- Create: `tests/test_examples_jaffle_shop.py`

Satisfies spec §12 DoD: "at least 3 jaffle_shop model scenarios via the
unit tier... including one incremental-model scenario exercising both
`is_incremental` branches" — four scenarios total (stg_customers,
customers, order_history × 2 branches), all real, all unit-tier.

- [ ] **Step 1: Write the failing test**

Create `tests/test_examples_jaffle_shop.py`:

```python
"""End-to-end: real jaffle_shop models against a real DuckDB target, run
through the actual CLI a user would run (spec §8, §12 DoD)."""

import subprocess
import sys
from pathlib import Path

EXAMPLE_PROJECT = Path(__file__).parent.parent / "examples" / "jaffle_shop"


def test_jaffle_shop_unit_examples_all_pass():
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
    assert "4 scenario(s)" in result.stdout
    assert "0 failure(s)" in result.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_examples_jaffle_shop.py -v`
Expected: FAIL — `no .feature files found` (directory doesn't exist yet).

- [ ] **Step 3: Implement**

Create `examples/jaffle_shop/features/stg_customers.feature`:

```gherkin
Feature: stg_customers renames the raw seed's id column

  @unit
  Scenario: Renames id to customer_id, passes names through unchanged
    Given the following rows in "raw_customers":
      | id | first_name | last_name |
      | 1  | Michael    | P.        |
    When the "stg_customers" model runs
    Then the "stg_customers" should produce the following rows:
      | customer_id | first_name | last_name |
      | 1           | Michael    | P.        |
```

Create `examples/jaffle_shop/features/customers.feature`:

```gherkin
Feature: customers aggregates order and payment history per customer

  @unit
  Scenario: Computes order stats and lifetime value for a customer with two completed orders
    Given the following rows in "stg_customers":
      | customer_id | first_name | last_name |
      | 1           | Michael    | P.        |
    And the following rows in "stg_orders":
      | order_id | customer_id | order_date | status    |
      | 10       | 1           | 2018-01-01 | completed |
      | 11       | 1           | 2018-02-01 | completed |
    And the following rows in "stg_payments":
      | payment_id | order_id | payment_method | amount |
      | 100        | 10       | credit_card    | 10.00  |
      | 101        | 11       | credit_card    | 20.00  |
    When the "customers" model runs
    Then the "customers" should produce the following rows:
      | customer_id | first_name | last_name | first_order | most_recent_order | number_of_orders | customer_lifetime_value |
      | 1           | Michael    | P.        | 2018-01-01  | 2018-02-01         | 2                 | 30.00                    |
```

Create `examples/jaffle_shop/features/order_history.feature`:

```gherkin
Feature: order_history loads incrementally by order_date

  @unit @incremental_model
  Scenario: Full refresh loads every row from stg_orders
    Given the following rows in "stg_orders":
      | order_id | customer_id | order_date | status  |
      | 1        | 1           | 2018-01-01 | placed  |
      | 2        | 1           | 2018-01-02 | shipped |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id | customer_id | order_date | status  |
      | 1        | 1           | 2018-01-01 | placed  |
      | 2        | 1           | 2018-01-02 | shipped |

  @unit @incremental_model
  Scenario: Incremental mode only loads rows newer than what's already in the table
    Given the following rows in "stg_orders":
      | order_id | customer_id | order_date | status    |
      | 1        | 1           | 2018-01-01 | placed    |
      | 2        | 1           | 2018-01-02 | shipped   |
      | 3        | 1           | 2018-01-03 | completed |
    And the following rows already in "order_history":
      | order_id | customer_id | order_date | status |
      | 1        | 1           | 2018-01-01 | placed |
    When the "order_history" model runs
    Then the "order_history" should produce the following rows:
      | order_id | customer_id | order_date | status    |
      | 2        | 1           | 2018-01-02 | shipped   |
      | 3        | 1           | 2018-01-03 | completed |
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_examples_jaffle_shop.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add examples/jaffle_shop/features/ tests/test_examples_jaffle_shop.py
git commit -m "feat: real jaffle_shop unit-tier example scenarios -- stg_customers, customers, order_history (both is_incremental branches)"
```

---

### Task 13: Definition of Done verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -v`
Expected: all tests pass — the 101 from Phase 0 + Plan A, plus every test
added in Tasks 1–12. Note the exact final count in the commit message.

- [ ] **Step 2: Lint and format**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: both clean. If not, run `uv run ruff check --fix . && uv run
ruff format .`, re-run the full suite to confirm no behavioral change, and
commit the autofix separately (`style: apply ruff format/lint autofixes`)
before continuing.

- [ ] **Step 3: Manual CLI smoke test against the real example project**

```bash
cd examples/jaffle_shop
uv run --project ../.. specdbt run features --engine dbt --project-dir . --profiles-dir profiles
```

Expected output includes `4 scenario(s)`, `0 failure(s)`, and no leftover
`models/_specdbt_*.yml` file afterward — verify with:

```bash
ls models/ 2>/dev/null | grep _specdbt || echo "clean: no leftover unit-test yaml files"
```

- [ ] **Step 4: Check against this plan's slice of the spec's Definition of Done**

From spec §12 — this plan covers the model-unit-tier half (spec §13,
revised): the macro integration tier is Plan A (already merged), living
documentation (`specdbt docs`) is Plan C (not yet written):

- [x] `specdbt run` executes ≥3 jaffle_shop model scenarios via the unit
      tier, including one incremental-model scenario exercising both
      `is_incremental` branches — Task 12 (4 scenarios total)
- [x] `docs/gherkin-style-guide.md` exists and the example scenarios
      conform to it (declarative, not imperative) — Task 10, and every
      scenario in Task 12 written declaratively from the start
- [x] All new dependencies security-checked before install — PyYAML was
      already present transitively and already covered by Plan A's
      full-environment `pip-audit`; Task 5 only declares it as a direct
      dependency, no new package installed, no new check needed
- [x] Existing 101 tests plus new Plan B tests pass; `ruff` clean —
      Steps 1–2
- [x] Nothing pushed; no git remote configured

Not in this plan's scope (spec §13, deferred to Plan C): `specdbt docs`
living-documentation command. Not enforced by this plan (documented as an
explicit scope boundary in Global Constraints, not a gap): `@adapter:<name>`
and `@ai-generated` tags have no runtime behavior defined by the spec yet.

- [ ] **Step 5: Final commit**

```bash
git log --oneline phase-1-model-unit-tier ^main
git status
```

Expected: clean working tree, every task committed individually (not
squashed), branch `phase-1-model-unit-tier` ahead of `main` by exactly the
commits made in this plan plus the three spec-correction commits made
before it (`73d00d3`, `6f3c05f`, `d0d42fc`). Do not merge to `main` yet —
report the branch state and this Definition of Done checklist back to the
user before merging, per the standing practice of merging via the
`finishing-a-development-branch` skill once a branch is confirmed complete.
