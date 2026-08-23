# specdbt — Phase 1 Design v2 (replaces the Polars/DuckDB-reimplementation draft)

**Status: approved design, not yet an implementation plan.** Supersedes
`2026-08-23-specdbt-phase1-design.md` (kept for history, marked superseded).
This doc reflects a real architecture change made during review, not a
refinement of the old one — see §1.

## 1. Why this replaces v1

The original Phase 1 draft proposed reimplementing model logic in Polars and
DuckDB, with a `--parity` mode diffing the two reimplementations against each
other. Review surfaced three problems with that bet:

1. **It can't test macros at all.** A macro is a Jinja template, not a shape
   Polars can reimplement. The user's actual need — testing macros, which dbt
   itself has no native unit-test support for (open feature request,
   [dbt-core#10547](https://github.com/dbt-labs/dbt-core/issues/10547), filed
   Aug 2024, "Refinement needed," no maintainer commitment on shape or
   timeline) — was structurally out of reach for v1's design.
2. **It reintroduces exactly the drift risk Phase 0's own README flagged.**
   Two hand-maintained reimplementations of real SQL logic can each silently
   diverge from the truth; `--parity` mode only proves they agree with each
   other, not that either is correct.
3. **It doesn't generalize to Snowflake/Databricks.** A Polars reimplementation
   is one specific engine's semantics; real dbt projects run on whatever
   warehouse the team uses, and dialect differences (window functions, date
   arithmetic, type coercion) are exactly what a reimplementation would get
   subtly wrong per-warehouse.

v2's bet instead: **specdbt writes no execution logic of its own for models or
macros — it drives real dbt (`dbtRunner`, the same programmatic entrypoint dbt
Cloud/CLI use) against whatever adapter the project already targets, and adds
only a Gherkin front end and a Polars-based result comparison on top.**
Adapter-agnosticism is inherited from dbt's own adapter system, not rebuilt
inside specdbt.

## 2. Scope

**In scope:**
- `DbtExecutionAdapter` — real execution via `dbtRunner`, one implementation
  for all engines (see §3).
- Model testing via dbt's native `unit_tests:` YAML (§4), including
  incremental-model scenarios via `is_incremental` overrides and `input: this`.
- Macro testing via specdbt's own ephemeral-schema mechanism (§5) — the only
  option today, since dbt has no native equivalent (dbt-core#10547).
- Gherkin grammar additions for macro invocation and tier/adapter tags (§6).
- A style guide mandating declarative Gherkin, and a `specdbt docs` living-
  documentation command (§7).
- Example scenarios against jaffle_shop (models) and dbt_utils (macros),
  replacing the data-pulse examples (§8).
- Safety guardrails for a tool that now touches real (ephemeral) warehouse
  schemas, not just in-memory fakes (§9).

**Out of scope for Phase 1 (extension points only, not implemented):**
- Model testing via the integration tier (real ephemeral-schema deploy for
  models, not just macros) — architecturally supported by the same
  `DbtExecutionAdapter.run_model`, just not exercised by any Phase 1 example.
- Macro testing via a unit tier — no native dbt mechanism exists yet; see §5.4
  for the registered-but-empty extension point.
- Live Snowflake/Databricks validation — architecturally engine-agnostic by
  construction (nothing DuckDB-specific in specdbt's own code), but unproven
  against a real account. No credentials available to test with.
- Any AI feature (fixture synthesis, NL→Gherkin, edge-case advisor) — still
  Phase 3, per the original roadmap. §7's `@ai-generated` tag is a hook for
  that phase, not an implementation of it.

## 3. Architecture: one real adapter, two test tiers

`ExecutionAdapter` (Phase 0, `src/specdbt/adapters/base.py`) stays as the
interface for real engine execution, extended (see §10 for the exact diff).
`FakeAdapter` stays too, demoted to "what specdbt uses to test itself" — its
own test suite shouldn't need a live dbt project to run.

Phase 1 adds exactly one concrete real adapter, `DbtExecutionAdapter`, driving
`dbtRunner.invoke([...])`. This is deliberately the same CLI-shaped entrypoint
dbt Cloud and the dbt CLI use — confirmed via dbt Labs' own Fusion-engine posts
that Fusion is being built as a CLI-compatible drop-in (`dbt --version` etc.),
so building on this surface rather than internal manifest APIs is the
forward-compatible choice, not just the convenient one.

**Test tier is orthogonal to resource kind** (model vs. macro) — this was the
key correction from the first pass of this design, which had wrongly tied
"model = unit-tested" and "macro = integration-tested" together:

| | Unit tier (delegates to dbt-native fixtures) | Integration tier (specdbt's own ephemeral-schema execution) |
|---|---|---|
| **Model** | ✅ `unit_tests:` YAML + `dbt test` — Phase 1 proves this | Extension point only — same mechanism as macros, not exercised in Phase 1 |
| **Macro** | Extension point only — no native dbt mechanism exists (dbt-core#10547 open) | ✅ ephemeral schema + real run — Phase 1 proves this, and it's not a stopgap: see §5.5 |

Two tiers, two orchestration interfaces:

- **`ExecutionAdapter`** (real engine execution — integration tier). Extended
  in Phase 1 with `run_macro(macro_call, fixtures) -> ExecutionResult`
  alongside the existing `run_model(model_name, fixtures) -> ExecutionResult`.
- **`NativeTestCompiler`** (new, unit tier — delegates to whatever native
  fixture mechanism dbt ships for a given resource kind). A registry keyed by
  resource kind: `ModelUnitTestCompiler` registered in Phase 1; a macro slot
  left unregistered, raising a clear "not supported by dbt yet — see
  dbt-core#10547, use `@integration`" error if a scenario asks for it.

The runner (`src/specdbt/runner.py`) picks tier per scenario: explicit
`@unit`/`@integration` tag if present, else "unit if a compiler is registered
for this resource kind, else integration."

## 4. Model path: unit tier (dbt-native)

specdbt compiles each tagged-`@unit` model `Scenario` into a `unit_tests:`
YAML entry and runs it via `dbtRunner.invoke(["test", "--select",
f"unit_test:{project}.{name}"])`, translating dbt's own pass/fail and
actual-vs-expected diff into specdbt's existing report format
(`src/specdbt/reporter.py`). No ref/source-override logic of specdbt's own —
dbt's unit test runner already does this correctly, per-adapter, and specdbt
reusing it means Snowflake/Databricks support requires zero specdbt code, only
dbt itself supporting the adapter (which it already does).

**Incremental models are in scope**, not a punt — dbt's own `unit_tests:`
config supports this directly via `overrides: macros: is_incremental:
true/false` and a special `input: this` fixture representing "rows already in
the target table." specdbt's Gherkin shape for this: a
`Given the following rows already in "<model>"` step compiles to `input:
this`; which `is_incremental` branch a scenario exercises is either explicit
(a tag or step wording) or, if the model has an incremental config, specdbt
generates both branches from one scenario by default — exact step grammar is
an implementation-plan-time detail, not a design blocker.

**Accurate non-goals, inherited from dbt itself, not invented by specdbt:**
per dbt's own unit-test prerequisites, this path doesn't support Python
models, `materialized view` models, recursive SQL, or models outside the
current project, and doesn't support introspective queries. These aren't
specdbt limitations to work around — routing around them would mean
reimplementing the exact machinery this design deliberately avoids
reimplementing. A scenario hitting one of these gets a clear "dbt's native
unit tests don't support this — use `@integration`" error, since the
integration-tier extension point (§2) can, in principle, still test it.

### 4.1 Mechanism, corrected against a real spike (2026-08-23, plan-B time)

Three spikes against a scratch dbt-duckdb project (two unit tests, one
passing, one deliberately failing, on a model with an extra un-asserted
column) settled every open question §4 originally left as "implementation-
plan-time detail":

1. **Selector: `unit_test:{project}.{name}` is a real, working selector
   method** — resolves to exactly one node, verified against
   `dbtRunner.invoke(["test", "--select", "unit_test:probe.test_passes"])`.
   (Bare `--select {name}` also works, per dbt's own docs, since unit test
   names are project-unique — but the qualified form is what specdbt uses,
   since it's the one actually exercised in the spike and reads unambiguous
   at the call site.)
2. **`dbtRunnerResult.success` is `False` on a legitimate, well-formed test
   failure** — not just on a genuine invocation error. Confirmed: a
   deliberately-wrong `expect:` block produces `success=False` with
   `r.exception is None` and `r.result` populated with one `TestStatus.Fail`
   result. This means `DbtExecutionAdapter._invoke` (§5.1/Plan A's helper,
   which raises `DbtInvocationError` on `not result.success`) **cannot be
   reused as-is for `dbt test`** — a correctly-reported scenario failure
   would otherwise raise an exception instead of producing a clean specdbt
   failure report. The unit-tier compiler needs its own invoke path that
   only raises when `r.result is None` (confirmed empirically to mean a
   genuine parse/compile error — verified by pointing a unit test at a
   nonexistent model, which produced `r.result is None`,
   `r.exception = ParsingError(...)`, `r.success = False`) — a populated
   `r.result` with `r.success = False` means "ran, and at least one test
   failed," which is the normal path, not an error.
3. **`result.status` is a `TestStatus` enum** (`TestStatus.Pass` /
   `TestStatus.Fail`), not a plain string — but it compares equal to the
   plain strings `"pass"`/`"fail"` directly (`TestStatus` is string-valued),
   so `result.status == "pass"` works with no special import or `.value`
   access needed. `result.message` is `""` on pass, and on fail contains
   dbt's own actual-vs-expected diff wrapped in ANSI color escape codes
   (`\x1b[...m`) — strip with `re.sub(r"\x1b\[[0-9;]*m", "", message)`
   before handing to specdbt's reporter. `result.failures` is a plain `int`
   count (`0` or `1` in the spike, matching O31).
4. **`expect: rows:` compares only the columns it lists, not every column
   the model actually produces.** A `given:` fixture with an extra
   `extra_col` the `expect:` block never mentions still passes — dbt does
   column *projection* against `expect:`'s own header, not full-row
   equality against the model's real output shape. **This breaks §6's
   stated orthogonality** ("`Then` must mean the same thing regardless of
   tier") as originally written, since the integration tier's row-table
   `Then` currently does full `dict` equality
   (`result.rows != expected_rows`, `src/specdbt/assertions.py`). Fix,
   applied in Plan B: the row-table `Then` is redefined, for **both**
   tiers, as column-projection — only the columns named in the expected
   table's header are compared, any other column the actual result carries
   is ignored. This is a behavior change to the integration tier's existing
   comparison (Plan A's Task 9/10), tightened here so a scenario's meaning
   genuinely does not change when retagged `@unit`/`@integration`.
5. **No `partial_parse.msgpack` staleness problem for this pattern.** A
   brand-new unit-test YAML file, written to disk *after* the adapter's
   `dbtRunner()` instance already exists (mid-process, on the same instance
   Plan A's `DbtExecutionAdapter` builds once in `__init__` and reuses),
   was picked up correctly by the very next `invoke()` call on that same
   instance with no restart and no explicit re-parse step — the same
   proven-safe pattern as Plan A's generated macro file (§5.1).
6. **A unit test's `given: input: ref(...)`/`source(...)` targets must
   already exist as real, built relations in the target database** — not
   just parseable model files — or the run fails with `Compilation Error
   ... Not able to get columns for unit test '<input>' ... because the
   relation doesn't exist`, raised from dbt's own
   `macros/unit_test_sql/get_fixture_sql.sql`. Root cause: dbt introspects
   the *real* relation's column types to correctly cast each fixture row's
   values (this is what makes a bare `2018-01-01` string in a YAML fixture
   correctly become a real `DATE`, not stay a string) — it does not derive
   types from the model's compiled SQL alone. Verified precisely: a `dbt
   run --select <the given input's model>` before the unit test is both
   *necessary* (test fails without it) and *sufficient* (the model under
   test itself does **not** need to be separately built — only its
   `given:`-referenced ancestors do). This means **the unit tier is not
   fully ephemeral the way the macro/integration tier is (§5.3)** — it
   writes real materialized tables into the project's actually-configured
   target schema before any test runs, not a throwaway `specdbt_<uuid>`
   one. Consequence for Plan B: `ModelUnitTestCompiler` needs the same
   heuristic prod-schema guard `DbtExecutionAdapter` already has (§5.3),
   applied to *its* `dbt run` step; and the simplest correct sequencing is
   one `dbt run` for the whole project (dbt's own dependency graph already
   orders it correctly) once per `specdbt run --engine dbt` invocation that
   contains any unit-tier scenarios, not a per-scenario or per-input
   selective build — cheap for the example project's five models, and
   avoids specdbt reimplementing dbt's own ref-graph resolution just to
   compute a minimal `--select` set.

## 5. Macro path: integration tier (specdbt-native, real execution)

This is Phase 1's other proven cell, and the direct answer to "test macros
end-to-end against dbt's real execution."

### 5.1 Mechanism (corrected against a real spike — see note below)

One ephemeral schema per scenario run, named `specdbt_<uuid>`, created and
torn down through a **generated macro file**, invoked via
`dbtRunner.invoke(["run-operation", "<macro_name>", ...])`:

1. **Given → real tables.** specdbt writes a temporary macro file
   (`macros/_specdbt_<run_id>.sql`) into the target project containing a
   macro that first does `{% do run_query("create schema if not exists
   specdbt_<uuid>") %}` — **schema creation is not implicit**; a `CREATE
   TABLE` into a nonexistent schema fails, verified in the spike — then, per
   fixture, `{% do run_query(sql) %}` for a `CREATE TABLE ... AS` with a
   literal `VALUES` list, before invoking the whole macro via
   `run-operation`. String literals use the exact call chain dbt-core's own
   native unit-test fixture SQL generator uses internally (found in the
   installed package at
   `dbt/include/global_project/macros/unit_test_sql/get_fixture_sql.sql:95`):
   `dbt.string_literal(dbt.escape_single_quotes(value))` — **not**
   `dbt.string_literal()` alone, which a spike showed performs **no escaping
   at all** (`default__string_literal` is a bare `'{{ value }}'`; a raw
   `O'Brien` broke the generated SQL). `escape_single_quotes` is the macro
   that actually doubles `'` → `''`, adapter-dispatched the same way, so this
   chain is correct per-warehouse without specdbt reimplementing SQL escaping
   itself. Round-trip verified in the spike for embedded single quotes,
   double quotes, and backslashes.
2. **When → real query, read directly, no result table.** The `When` step's
   text is a *complete* query, real verbatim Jinja/SQL — no specdbt-invented
   call syntax (see §6) — not just a macro call expression. A second spike
   (below) found that wrapping a macro call in a `CREATE TABLE ... AS`
   executed via `run_query()` silently fails to persist for at least one real
   macro (`dbt_utils.star()`), while the identical call as a plain `SELECT`
   run through `dbt show --inline` works correctly every time. There is also
   no single wrapping shape that would work generically: `generate_surrogate_key()`
   expands to a scalar expression (needs `select {{ call }} as x from t`),
   `star()` expands to a column list (needs `select {{ call }} from t`, no
   `as`), and other macros may expand to neither shape. Rather than guess a
   macro's output shape, specdbt doesn't wrap at all — the scenario author
   writes the full query, and specdbt only does one thing to it before
   execution: textually substitutes any `ref()`/`source()` referring to a
   fixture name for the ephemeral fixture's real relation (specdbt's own
   preprocessing, not dbt's `ref` resolution — a fixture isn't a real project
   node).
3. **Result readback.** The substituted query is run directly via `dbt show
   --inline --output json`, then `result.result.results[0].agate_table` — an
   `agate` table with `.column_names` and `.rows`, converted to
   `list[dict]` with `[dict(zip(agate_tbl.column_names, row, strict=True))
   for row in agate_tbl.rows]` for `ExecutionResult`.
4. **Then → Polars diff** against the expected rows, using the same
   assertion vocabulary Phase 0 already built (`src/specdbt/assertions.py`).
5. **Teardown.** Schema dropped and the generated macro file deleted in a
   `finally` — runs whether the scenario passed, failed, or raised, not
   conditional on success.

**Corrections from real spikes, not docs reads — three separate findings:**

1. The design originally specified `run-operation --sql "<raw DDL>"` directly
   for both fixture setup and teardown. A scratch dbt+DuckDB project run
   through `dbtRunner` showed this reports `success: True` but **does not
   actually persist the DDL** — the table is absent from the DuckDB file
   afterward. Wrapping the same SQL in a real macro using `{% do
   run_query(sql) %}`, invoked via `run-operation <macro_name>`, does persist
   correctly — verified against the actual `.duckdb` file, not just the
   reported exit status.
2. A second spike, materializing fixtures against a real `dbt_utils`
   installation and exercising `generate_surrogate_key()` and `star()`,
   found that a **`CREATE TABLE ... AS` wrapping `dbt_utils.star()`, run via
   `run_query()` inside a `run-operation` macro, also reports `success: True`
   but does not persist** — reproduced on a fresh database file, with the
   fixture table and the *first* result table (`generate_surrogate_key`'s)
   both genuinely present, and only the `star()`-wrapping CTAS silently
   missing, regardless of whether it ran in the same macro invocation as the
   fixture setup or a fully separate one. The same `star()` call as a plain
   `SELECT` run through `dbt show --inline` returns correct data every time
   this was tried. This is the mechanism change described above: no result
   table, `show --inline` directly.
3. Confirmed empirically in the same spikes: `dbtRunner.invoke(...)` returns
   a `dbtRunnerResult(success, result, exception)` dataclass; `test --select
   test_type:unit` results carry `.status` (`'pass'`/`'fail'`), `.message`
   (dbt's own rendered actual-vs-expected diff — reusable directly for §4's
   model-unit-tier reporting, no diff-rendering of specdbt's own needed), and
   `.failures` per unit test; schema creation is not implicit — `CREATE
   TABLE` into a nonexistent schema fails, so an explicit `CREATE SCHEMA IF
   NOT EXISTS` is part of the fixture-setup mechanism.

Findings 1 and 2 are the same class of bug — dbt reporting success on a
`run_query()` DDL statement that doesn't actually commit — with different,
apparently unrelated triggers (a raw `--sql` flag; a specific introspective
macro's CTAS). Neither is documented anywhere I found. The practical
response to both is the same: **don't trust a reported success — verify
against the actual database file** — and, for finding 2 specifically, avoid
the pattern entirely rather than chase its root cause: fixture setup (proven
reliable across every spike) still goes through `run_query()` in a generated
macro; the macro/model call under test never does, it always goes through
`show --inline`.

### 5.2 Because fixtures are real tables, introspective macros are in scope

Unlike the model/unit-tier path, there's no inherited dbt limitation here —
`star()`, `run_query()`, anything needing to introspect a real relation works,
because the fixture *is* a real relation by the time the macro runs, and the
connection is live throughout. (An earlier pass of this design wrongly listed
introspective macros as a non-goal, carrying over reasoning from the
compile-only approach this doc replaced — corrected here.)

### 5.3 Safety guardrails

Real, possibly-shared warehouse connections change the risk profile from
Phase 0's in-memory `FakeAdapter`:
- Every specdbt-created object lives under `specdbt_<uuid>` — never the
  project's real schemas.
- The generated macro file (`macros/_specdbt_<run_id>.sql`) is the one
  artifact specdbt writes into the target project's own source tree, not just
  the warehouse — it is deleted in the same teardown as the schema drop, and
  named with a `_specdbt_` prefix + run id specifically so a crash-abandoned
  file is unambiguous to spot and safe to delete by hand.
- Teardown always runs, including on interrupt where feasible (best-effort,
  documented as such — not guaranteed if the process is hard-killed).
- `--keep-schema` debug flag skips teardown so a failure can be inspected by
  hand.
- A heuristic guard refuses to run against a target whose configured schema
  doesn't look like dev/test, with an explicit `--i-know-what-im-doing`
  override — a blunt check against accidentally pointing this at prod.

### 5.4 Forward-compat with dbt-core#10547

If dbt ships native macro unit testing, specdbt should be able to adopt it
without a rewrite — that's the reason for the `NativeTestCompiler` registry
(§3) existing as a seam now, even with its macro slot empty. Adding
`MacroUnitTestCompiler` later means implementing one class against an
interface that already exists; the Gherkin frontend, fixtures, assertions,
and reporter don't change — the same shape Phase 0's `ExecutionAdapter` used
to absorb this entire Phase 1 rewrite without the layers above it changing.

### 5.5 Integration tier is not a stopgap

Once a native macro unit test exists, the ephemeral-schema mechanism doesn't
get deleted — it stays available for both models and macros, because it
proves something a mocked/CTE-injected unit test structurally can't: real
adapter round-trip behavior (actual warehouse-side type coercion, actual
DDL/permission behavior, actual incremental-merge behavior end-to-end). Unit
and integration tiers are two different guarantees, not two implementations
of the same guarantee at different speeds.

## 6. Gherkin grammar additions

**`Then` must mean the same thing regardless of tier — this was wrong in the
first pass of this design and is corrected here.** That pass gave unit tier a
row-table `Then` (to map onto dbt's `expect: rows:`) and left integration
tier on Phase 0's prose assertions (`should have N rows`, `should be
unique`) as the *only* form. Since tier is supposed to be orthogonal to the
scenario (§3) — explicit tag or resolved automatically — a scenario whose
only `Then` is prose silently can't run as `@unit`, and one written as a row
table changes meaning if retagged. That breaks the orthogonality the tier
design depends on.

**Fix: the row-table `Then` is canonical for both tiers.**
`Then the "<model>" should produce the following rows:` + a data table works
identically whether the resolved tier is unit (maps directly to dbt's
`expect: rows:`) or integration (specdbt diffs the same table against its own
`ExecutionResult` with Polars — the mechanism §5.1 already builds), and, per
§4.1 finding 4, "identically" specifically means **column-projection**: only
the columns named in the expected table's header are compared, in both
tiers, matching dbt's own native `expect:` semantics exactly rather than
specdbt inventing a stricter one. Phase 0's
prose assertions (`should have N rows`, `should be unique`, `should not be
null`) remain supported, but only as *additional* steps in an
integration-tagged scenario, never as the sole `Then` in a scenario that
might resolve to unit tier — the unit-tier compiler has nothing to translate
them into. If a scenario tagged (or defaulted to) `@unit` has no row-table
`Then`, that's an error at compile time naming the fix (add a row-table
`Then`, or tag `@integration` explicitly), not a silent misroute.

- Models: `When the "<model_name>" model runs` — unchanged from Phase 0.
- Macros (new): `When the "select {{ dbt_utils.generate_surrogate_key(['order_id',
  'customer_id']) }} as order_key, order_id from {{ ref('orders') }}" macro
  runs` — a *complete* query, real Jinja/SQL verbatim, not a specdbt DSL.
  The scenario author writes the whole `select`, not just the macro call:
  §5.1's second spike found no wrapping shape that works generically across
  macros (`generate_surrogate_key()` expands to a scalar expression,
  `star()` to a bare column list — different shapes, no single template fits
  both), so specdbt does no structural wrapping at all, only the
  `ref()`/`source()` → fixture substitution.
- Incremental models (new): `Given the following rows already in "<model>"` →
  `input: this` (§4).
- Tags (new, all reuse standard Gherkin tag syntax, nothing invented):
  - `@unit` / `@integration` — explicit tier selection, overriding the
    resource-kind default from §3.
  - `@adapter:<name>` — optional, restricts a scenario to a specific adapter
    when its behavior is genuinely adapter-specific.
  - `@ai-generated` — provenance marker for the Phase 3 "AI proposes, human
    approves" rule (original vision doc): an AI-authored scenario carries this
    tag until a human reviews and removes it. Not implemented in Phase 1 (no
    AI generation exists yet) — reserved now so Phase 3 has a place to land.

## 7. Readable by both humans and machines — without inventing a dialect

Grounded in Cucumber's own official docs
(`cucumber.io/docs/bdd`, `cucumber.io/docs/bdd/better-gherkin`), not guessed:
BDD's stated premise is specifications "readable by both humans and
computers." No AI-specific Cucumber guidance exists yet (checked); the
mechanisms below are official Gherkin features specdbt just hadn't used.

- **Declarative, not imperative — mandatory, not a suggestion.** Cucumber's
  own before/after example contrasts `Given I type "x" in the email field /
  And I press "Submit"` (imperative, implementation detail) against `Given
  Free Frieda has a free subscription / When Free Frieda logs in` (declarative,
  intent). This is the same property that makes a scenario good context for
  an LLM to reason over or extend by analogy, and good "living documentation"
  for a non-technical reader — one property, not two. Codified as a rule in a
  new `docs/gherkin-style-guide.md`, checked when reviewing example/community
  contributions.
- **Doc strings with content-type annotations** (` ```markdown `, ` ```json `)
  — official Gherkin feature, reserved for scenarios needing a larger
  structured expected-payload blob, where it's clearer than a sprawling data
  table.
- **New `specdbt docs` CLI command** — Cucumber's own term for this is "living
  documentation." Renders a project's `.feature` files into one structured
  Markdown artifact, grouped by Feature/tag, annotated with last-run
  pass/fail freshness — built on the `FeatureReport`/`render_feature_report`
  structures Phase 0 already shipped, so this is genuinely small net-new work,
  not a new subsystem.

**Principle stated explicitly for contributors:** the AI-readiness story here
is "write good standard Gherkin," not "invent an AI-specific dialect."

## 8. Example projects

Replaces the data-pulse dogfood examples (kept in git history only):

- **jaffle_shop** (dbt Labs' official multi-adapter demo project, DuckDB-
  runnable out of the box) — model scenarios, unit tier.
- **dbt_utils** (dbt Labs' official macro package) — macro scenarios,
  integration tier. Its macros are explicitly `adapter.dispatch`-based (e.g.
  `generate_surrogate_key`, `date_trunc`, `star`) — the exact cross-warehouse
  macro shape this phase exists to prove against. `star()` additionally
  exercises the "introspective macros are in scope" claim from §5.2.

## 9. New dependencies (need the Phase 0 security check before install)

- `dbt-core` (PyPI)
- `dbt-duckdb` (PyPI)
- `polars` (PyPI)
- `dbt_utils` — installed via the target *example* project's `packages.yml`,
  not PyPI. Different supply-chain surface (dbt Hub / git-based package
  resolution, not pip) — needs its own short note in the security review
  rather than being silently treated as covered by the PyPI checks above.

**Checked and installed (2026-08-23):** OSV.dev clean for `dbt-core` 1.12.2,
`dbt-duckdb` 1.11.0, `duckdb` 1.5.5, `polars` 1.43.2, and transitive deps
`dbt-adapters` 1.24.5 / `dbt-common` 1.39.0; full-environment `pip-audit`
after `uv sync` reported no known vulnerabilities. Resolved under this
machine's 3-day `exclude-newer` uv policy — `dbt-core` 1.12.3 (published
2026-08-21, inside the window) was excluded in favor of 1.12.2.

## 10. What changes vs. Phase 0's `ExecutionAdapter`

Phase 0's own Phase 1 doc named this explicitly as a signal worth flagging:
"if either [adapter] needs to change [the `run_model`] interface, that's a
signal the Phase 0 abstraction has a gap worth naming before writing more code
against it." It does change:

- `run_model(model_name, fixtures) -> ExecutionResult` — signature unchanged.
  On `DbtExecutionAdapter` specifically, this raises clearly rather than
  silently ignoring `fixtures`: the macro-file substitution mechanism in §5.1
  only works because a macro call's `ref()`/`source()` arguments are text
  specdbt's own call site controls. A model's `ref()`s are inside its own SQL
  file, which this mechanism never touches — running it for real would use
  whatever real state those refs already resolve to, not the scenario's
  fixtures, which would silently produce wrong results. `FakeAdapter.run_model`
  is unaffected (registry lookup, no execution). Real model fixture override
  needs dbt's own manifest-level compilation (Plan B), which is why §2/§3
  already scope model-integration-tier as an extension point, not an
  implementation, for Phase 1.
- `run_macro(macro_call, fixtures) -> ExecutionResult` — new abstract method,
  the one `DbtExecutionAdapter` genuinely implements.
- New parallel interface `NativeTestCompiler` (§3) for the unit tier — not an
  `ExecutionAdapter` method, since delegating-to-dbt's-own-runner and
  driving-real-execution-directly are different enough operations that
  overloading one interface with both would blur what each call actually does.

## 11. CI story

A GitHub Actions workflow is included in this repo (inert until a remote
exists — this project stays local-only per the standing "never push" rule;
the workflow file documents intent and is ready the day that changes). It
runs the DuckDB-target example suite only, since that's the one adapter with
no live-credential requirement.

## 12. Definition of Done for Phase 1

- `specdbt run` executes at least 3 jaffle_shop model scenarios via the unit
  tier (`unit_tests:` + `dbt test`), including one incremental-model scenario
  exercising both `is_incremental` branches.
- `specdbt run` executes at least 2 dbt_utils macro scenarios via the
  integration tier, including one exercising an introspective macro
  (`star()`), with schema teardown verified (no leftover `specdbt_*` schema
  and no leftover `macros/_specdbt_*.sql` file after a run, pass or fail).
- `specdbt docs` renders a living-documentation Markdown artifact from the
  example scenarios.
- `docs/gherkin-style-guide.md` exists and the example scenarios conform to
  it (declarative, not imperative).
- All new dependencies security-checked and reported before install, per
  Phase 0's rule.
- Existing 60 Phase 0 tests plus new Phase 1 tests pass; `ruff` clean.
- Nothing pushed; still no git remote configured.

## 13. Implementation sequencing

Two independent plan docs, not one — the macro integration tier and the
model unit tier share only the interface boundary (§3), and their innards
don't depend on each other. **Plan A (macro integration tier) executes
first.** It's the part dbt genuinely cannot do natively (dbt-core#10547), it
exercises every new primitive this design introduces (literal rendering,
macro-file generation, `ref()`/`source()` substitution, `show --inline`
readback, Polars diff, teardown), and it's the part already grounded in a
real spike rather than documentation alone. Plan B (model unit tier — compile
Gherkin to `unit_tests:` YAML, shell to `dbt test`) is smaller, lower-risk,
reuses none of Plan A's machinery, and is written after Plan A lands. This
Definition of Done (§12) completes across both plans, not within either one
alone; each plan produces working, testable software on its own.

**Revised at Plan B write-time (2026-08-23):** three plans, not two. Plan B's
own scope is the unit tier itself plus the `@unit`/`@integration` tag routing
that selects it (§3) — inseparable from the tier, since routing *is* how a
scenario reaches it — plus `docs/gherkin-style-guide.md` (one static file,
no code dependency on either tier, trivial to fold in). `specdbt docs`
(living documentation) is deferred to a **Plan C**: it renders `.feature`
files via the existing `FeatureReport`/`render_feature_report` structures
Phase 0 already shipped, has zero dependency on which tier a scenario
resolves to, and stands alone under the same "each plan produces working,
testable software on its own" rule this section already established. §12's
Definition of Done completes across all three plans.
